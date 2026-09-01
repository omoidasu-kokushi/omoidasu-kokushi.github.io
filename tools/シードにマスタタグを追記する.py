#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同梱シードの各肢タグへ、中項目→対応表のマスタタグを追記する（案A'）。

なぜ要るか：
  V2.05 でタグマスタは 74→103 になったが、シード453問は再タグ付けされず、
  マスタ内タグは 1,365中21（1.5%）・球のあるテーマは 103中14 のまま。
  新規購入者の概念アナライザーが初日ほぼ空になる（claude/20260901_…判断待ち_V1.01）。

方式（案A'）：
  自由タグ（#ハインリッヒの法則 等）は消さず、対応表から引いたマスタタグを
  各肢のタグ配列へ「追記」する。二重追記はしない（何度流しても同じ結果）。
  対応表の正は 20260828_中項目→概念タグ_対応表_V1.00（.json / .tsv どちらも可）。

使い方：
  python3 tools/シードにマスタタグを追記する.py --selftest
  python3 tools/シードにマスタタグを追記する.py 対応表.json           # 検算のみ（書かない）
  python3 tools/シードにマスタタグを追記する.py 対応表.json --write   # questions.js を書き換え

書き換え後は 版番号・CACHE_NAME・?v= の3箇所同時（questions.js は配布物）。
"""
import io
import json
import os
import re
import sys
import tempfile

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QJS = os.path.join(APP, "questions.js")
HEAD = 'const SEED_QUESTIONS_TSV = ['
TAIL = '].join("\\n");'
COL_MEDIUM = 4   # 0単元 1目標 2ランク 3大項目 4中項目 5小項目 … 11タグ
COL_TAGS = 11


def norm(s):
    return re.sub(r"\s+", " ", str(s)).strip()


def load_master(src):
    tags = set(re.findall(r'tag:\s*"(#[^"]+)"', src))
    if len(tags) < 50:
        raise SystemExit("マスタタグの抽出に失敗（%d件）。questions.js の形が変わった？" % len(tags))
    return tags


def split_seed_block(src):
    i = src.index(HEAD)
    j = src.index(TAIL, i)
    return src[:i + len(HEAD)], src[i + len(HEAD):j], src[j:]


def parse_rows(block):
    rows = []
    for ln in block.splitlines():
        m = re.match(r'^\s*"((?:[^"\\]|\\.)*)"\s*,?\s*$', ln)
        if m:
            rows.append(json.loads('"' + m.group(1) + '"').split("\t"))
    if not rows:
        raise SystemExit("シード行を1つも読めなかった。questions.js の形が変わった？")
    return rows


def build_rows_js(rows):
    lits = [json.dumps("\t".join(c), ensure_ascii=False) for c in rows]
    return "\n  " + ",\n  ".join(lits) + "\n"


def load_mapping(path):
    """対応表を読む。返り値: {正規化キー: set(マスタタグ候補)}。
    .json: dict{キー:[タグ…]} / dict{キー:{既定:[…]}} / list[{中項目|key…, tags|既定…}]
    .tsv : 1列目キー。ヘッダに「既定」を含む列があればその列だけ、無ければ行内の全 #タグ。"""
    mp = {}
    if path.lower().endswith((".tsv", ".txt", ".csv")):
        lines = io.open(path, encoding="utf-8-sig").read().splitlines()
        sep = "\t" if "\t" in lines[0] else ","
        head = [norm(h) for h in lines[0].split(sep)]
        default_cols = [i for i, h in enumerate(head) if "既定" in h]
        for ln in lines[1:]:
            if not ln.strip():
                continue
            cells = ln.split(sep)
            key = norm(cells[0])
            src_cells = [cells[i] for i in default_cols if i < len(cells)] \
                if default_cols else cells[1:]
            tags = set(re.findall(r"#[^\s,、/｜|\]\[\"']+", " ".join(src_cells)))
            if key:
                mp.setdefault(key, set()).update(tags)
    else:
        data = json.load(io.open(path, encoding="utf-8-sig"))
        if isinstance(data, dict):
            items = [(norm(k), v, [norm(k)]) for k, v in data.items()]
        else:
            items = []
            for d in data:
                med = d.get("中項目") or d.get("中項目名") or d.get("medium") \
                    or d.get("key") or d.get("num_code") or d.get("code") \
                    or d.get("name")
                if med is None:
                    continue
                med = norm(med)
                keys = [med]
                if d.get("major"):
                    keys.append(norm(d["major"]) + "|" + med)
                    if d.get("unit"):
                        keys.append(norm(d["unit"]) + "|" +
                                    norm(d["major"]) + "|" + med)
                items.append((med, d, keys))
        conflict = set()
        for med, v, keys in items:
            if isinstance(v, dict):
                v = v.get("既定") or v.get("default") or v.get("tags") \
                    or v.get("タグ") or []
            if isinstance(v, str):
                v = re.findall(r"#[^\s,、/｜|\]\[\"']+", v) or [v]
            tags = set("#" + str(t).lstrip("#") for t in v if str(t).strip())
            for k in keys:
                if k in mp and mp[k] != tags:
                    conflict.add(k)     # 同名キーで中身が割れたら、そのキーは使わない
                mp.setdefault(k, set()).update(tags)
        for k in conflict:
            mp.pop(k, None)
    if not mp:
        raise SystemExit("対応表からキーを1つも読めなかった: " + path)
    return mp


def keys_for(cols):
    """シード行から対応表キーの候補（当たりやすい順）。"""
    unit, major, medium = norm(cols[0]), norm(cols[3]), norm(cols[COL_MEDIUM])
    return [medium,
            major + "|" + medium,
            unit + "|" + major + "|" + medium,
            re.sub(r"^[A-Za-zА-я0-9一-九①-⑳]+[\.．、]\s*", "", medium)]


def apply_mapping(rows, mp, master):
    stat = {"追記延べ": 0, "未対応中項目": set(), "使ったキー": set(),
            "マスタ外(対応表側)": set()}
    for cols in rows:
        while len(cols) <= COL_TAGS:
            cols.append("")
        hit = None
        for k in keys_for(cols):
            if k in mp:
                hit = k
                break
        if hit is None:
            stat["未対応中項目"].add(norm(cols[COL_MEDIUM]))
            continue
        stat["使ったキー"].add(hit)
        add = set()
        for t in mp[hit]:
            (add if t in master else stat["マスタ外(対応表側)"]).add(t)
        try:
            t2 = json.loads(cols[COL_TAGS]) if cols[COL_TAGS].strip() else []
        except Exception:
            t2 = []
        if not isinstance(t2, list) or not t2:
            t2 = [[]]
        t2 = [x if isinstance(x, list) else [x] for x in t2]
        for atom in t2:
            for t in sorted(add):
                if t not in atom:
                    atom.append(t)
                    stat["追記延べ"] += 1
        cols[COL_TAGS] = json.dumps(t2, ensure_ascii=False,
                                    separators=(",", ":"))
    return stat


def tally(rows, master):
    total = hits = 0
    themes = set()
    for cols in rows:
        try:
            flat = [t for a in json.loads(cols[COL_TAGS]) for t in
                    (a if isinstance(a, list) else [a])]
        except Exception:
            flat = []
        total += len(flat)
        for t in flat:
            if t in master:
                hits += 1
                themes.add(t)
    return total, hits, themes


def run(map_path, write, qjs=QJS):
    src = io.open(qjs, encoding="utf-8").read()
    master = load_master(src)
    pre, block, post = split_seed_block(src)
    rows = parse_rows(block)
    mp = load_mapping(map_path)
    t0, h0, th0 = tally(rows, master)
    stat = apply_mapping(rows, mp, master)
    t1, h1, th1 = tally(rows, master)
    print("問題数 %d ／ マスタ %d件 ／ 対応表キー %d件" % (len(rows), len(master), len(mp)))
    print("延べタグ  %d → %d（追記 %d）" % (t0, t1, stat["追記延べ"]))
    print("マスタ内  %d (%.1f%%) → %d (%.1f%%)" %
          (h0, 100.0 * h0 / max(t0, 1), h1, 100.0 * h1 / max(t1, 1)))
    print("球のあるテーマ  %d → %d ／ %d" % (len(th0), len(th1), len(master)))
    print("対応表の未使用キー %d件" % (len(mp) - len(stat["使ったキー"])))
    if stat["未対応中項目"]:
        print("【要確認】対応表に無い中項目 %d件:" % len(stat["未対応中項目"]))
        for k in sorted(stat["未対応中項目"]):
            print("  -", k)
    if stat["マスタ外(対応表側)"]:
        print("【要確認】対応表にあるがマスタに無いタグ（追記しなかった）:",
              sorted(stat["マスタ外(対応表側)"]))
    if write:
        io.open(qjs, "w", encoding="utf-8").write(pre + build_rows_js(rows) + post)
        print("questions.js を書き換えた（git diff で確認 → 版番号3箇所を忘れない）")
    else:
        print("（検算のみ。書き換えは --write）")
    return stat, (t0, h0, len(th0)), (t1, h1, len(th1))


def selftest():
    d = tempfile.mkdtemp()
    row1 = "必修\t目標Ⅰ\tS\t1. 健康\tB. 健康に関する指標\ta. 総人口\tsingle\t問\t" \
           '["① あ","② い"]\t[1]\t解説"引用"あり\t[["#総人口"],["#人口静態"]]\t'
    row2 = "成人\t目標Ⅱ\tA\t3. 呼吸\tZ. 対応表に無い中項目\ta\tsingle\t問\t" \
           '["① あ"]\t[0]\t解説\t[["#自由"]]\t'
    qjs = os.path.join(d, "questions.js")
    io.open(qjs, "w", encoding="utf-8").write(
        '/* mini */\nconst CONCEPT_TAGS_MASTER = [\n' +
        "".join('  { tag: "#M%02d", label: "m", category: "c" },\n' % i
                for i in range(60)) +
        '  { tag: "#人口静態", label: "l", category: "c" },\n' +
        '  { tag: "#保健統計指標", label: "l", category: "c" },\n];\n' +
        HEAD + "\n  " + json.dumps(row1, ensure_ascii=False) + ",\n  " +
        json.dumps(row2, ensure_ascii=False) + "\n" + TAIL + "\n")
    ok = True

    def chk(name, cond):
        nonlocal ok
        print(("  ok  " if cond else "  NG  ") + name)
        ok = ok and bool(cond)

    # 形式1: JSON（既定つきdict）。マスタ外タグ混入も検査
    mj = os.path.join(d, "m.json")
    json.dump({"B. 健康に関する指標":
               {"既定": ["#人口静態", "#保健統計指標", "#マスタ外"]}},
              io.open(mj, "w", encoding="utf-8"), ensure_ascii=False)
    stat, b, a = run(mj, write=False, qjs=qjs)
    chk("各肢へ追記し、肢内の重複だけ足さない（この例では3件）",
        stat["追記延べ"] == 3)
    chk("未対応の中項目が挙がる", stat["未対応中項目"] == {"Z. 対応表に無い中項目"})
    chk("マスタ外タグは追記せず報告", stat["マスタ外(対応表側)"] == {"#マスタ外"})
    chk("球テーマ数が増える", a[2] > b[2])

    # --write → 再実行で追記0（何度流しても同じ）
    run(mj, write=True, qjs=qjs)
    stat2, b2, _ = run(mj, write=False, qjs=qjs)
    chk("書き換え後も読み戻せる（行数維持）", b2[0] > 0)
    chk("2回目は追記0（二重追記しない）", stat2["追記延べ"] == 0)
    src2 = io.open(qjs, encoding="utf-8").read()
    chk("外側のコードは無傷", src2.startswith("/* mini */") and TAIL in src2)
    chk('エスケープ往復（解説の"引用"）', '解説\\"引用\\"あり' in src2)

    # 形式2: TSV（既定列あり）
    mt = os.path.join(d, "m.tsv")
    io.open(mt, "w", encoding="utf-8").write(
        "中項目\t既定タグ\t候補\nB. 健康に関する指標\t#人口静態 #保健統計指標\t#候補X\n")
    mp = load_mapping(mt)
    chk("TSVの既定列だけ読む（候補は読まない）",
        mp["B. 健康に関する指標"] == {"#人口静態", "#保健統計指標"})

    # 形式3: 実物スキーマ（unit/major/medium・defaultは#無し文字列・同名mediumの衝突）
    mr = os.path.join(d, "real.json")
    json.dump([
        {"unit": "必修", "major": "1. 健康", "medium": "B. 健康に関する指標",
         "default": "人口静態", "candidates": ["人口静態", "保健統計指標"]},
        {"unit": "成人", "major": "9. 場", "medium": "A. かぶる中項目",
         "default": "人口静態"},
        {"unit": "老年", "major": "2. 別", "medium": "A. かぶる中項目",
         "default": "保健統計指標"},
    ], io.open(mr, "w", encoding="utf-8"), ensure_ascii=False)
    mp = load_mapping(mr)
    chk("実物形式: defaultの#無し文字列を1タグとして読む",
        mp["B. 健康に関する指標"] == {"#人口静態"})
    chk("実物形式: candidatesは読まない",
        "#保健統計指標" not in mp["B. 健康に関する指標"])
    chk("実物形式: 同名mediumで中身が割れたら素のキーを捨て複合キーで引ける",
        "A. かぶる中項目" not in mp
        and mp["9. 場|A. かぶる中項目"] == {"#人口静態"}
        and mp["老年|2. 別|A. かぶる中項目"] == {"#保健統計指標"})

    print("\nselftest:", "全通過" if ok else "失敗あり")
    return 0 if ok else 1


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    if "--selftest" in args:
        sys.exit(selftest())
    write = "--write" in args
    paths = [a for a in args if not a.startswith("--")]
    if not paths:
        print(__doc__)
        sys.exit(2)
    run(paths[0], write)
