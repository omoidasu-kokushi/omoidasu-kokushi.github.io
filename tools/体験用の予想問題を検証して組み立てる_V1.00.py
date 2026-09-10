# -*- coding: utf-8 -*-
"""体験用の予想問題（無料版の模試）を検証して、取り込み用の1本にまとめる V1.00

2026-09-10 作成。**この版はまだ1度も実行していません**（作った時点で
Linux側の作業環境が落ちたため）。まず --selftest を通してから使ってください。

【何をするか】
  res_free/M*.json を全部読み、
    1. 注文（batches_free/M*.txt）どおりに返ってきたかを確かめる
    2. 作問指示 V1.00 の確認項目 A〜F を確かめる
    3. 中身の質（タグ・statement・数値の裏づけ・HTML・ですます調）を確かめる
    4. NGが無ければ、取り込み用のJSONを1本にまとめて出す
  NGがあるときは**出しません**（--force で強行できます）。

【過去問の検証（仕上げ検証）と何が違うか】
  過去問は「入力と一字一句同じか」を見ますが、体験用は**新しく作る**ので
  比べる相手が本文にありません。代わりに**注文書**と突き合わせます。
  単元・大項目・中項目・ランク・出題形式・肢数・正解数は全部こちらが決めた値なので、
  一致しなければ作問側の逸脱です。

【使い方】
  python 体験用の予想問題を検証して組み立てる_V1.00.py
  python 体験用の予想問題を検証して組み立てる_V1.00.py --base <分類フォルダ>
  python 体験用の予想問題を検証して組み立てる_V1.00.py --selftest
"""
import collections
import datetime
import glob
import io
import json
import os
import re
import statistics
import sys

# 作問指示 V1.00 の単元別問題数
QUOTA = {
    'free_a': {'必修': 6, '成人看護学': 4, '老年看護学': 3, '小児看護学': 2,
               '基礎看護学': 2, '母性看護学': 2, '疾病の成り立ちと回復の促進': 2,
               '精神看護学': 2, '在宅看護論／地域・在宅看護論': 2,
               '人体の構造と機能': 2, '健康支援と社会保障制度': 2,
               '看護の統合と実践': 1},
    'free_b': {'必修': 14, '成人看護学': 8, '老年看護学': 5, '小児看護学': 5,
               '基礎看護学': 4, '母性看護学': 4, '疾病の成り立ちと回復の促進': 4,
               '精神看護学': 4, '在宅看護論／地域・在宅看護論': 3,
               '人体の構造と機能': 3, '健康支援と社会保障制度': 3,
               '看護の統合と実践': 3},
}

# 一問一答に回る条件（掃除 V1.10 の judge_splittable と同じ規則）。
# **同じ規則を2か所に持つときは、片方だけ直さないこと**（2026-09-09の教訓）。
SPLIT_NG_WORDS = ["最も", "もっとも", "誤っている", "誤りはどれ", "間違っている",
                  "正しくないのは", "適切でないのは", "不適切", "ではないのはどれ",
                  "当てはまらない", "あてはまらない", "除くのはどれ", "該当しないのは"]
COMBO_RE = re.compile(r"[①-⑳]|[a-e]，|[a-e]、")
NEG_RE = re.compile(r"(ない。?$|なし$|禁忌|適さない|不要)")
SPEECH_RE = re.compile(r"^[「｢]")
LEAK_RE = re.compile(r"(誤りである|誤っている|不適切である)")
SPLIT_MAX_LEN = 20

BAD_HTML = re.compile(r"<\s*(script|img|iframe|object|embed)\b|\son\w+\s*=", re.I)
DESU_RE = re.compile(r"(です|ます)[。、]")


def nkey(s):
    return re.sub(r"\s+", "", str(s or ""))


def numbers(s):
    """文中の数値を拾う（仕上げ検証と同じ規則）。
    英字の直後の数字は語の一部なので拾わない（N95・B12・SpO2）。"""
    t = re.sub(r"<[^>]+>", " ", str(s or ""))
    return set(re.findall(r"(?<![A-Za-z])(\d[\d,\.]*)", t))


def canon(n):
    return n.replace(",", "").rstrip(".").lstrip("0") or "0"


def load_orders(base):
    """バッチが頼んだ内容を M番号 → [注文] で返す。"""
    out = {}
    for f in sorted(glob.glob(os.path.join(base, "batches_free", "M*.txt"))):
        name = os.path.basename(f)[:-4]
        t = io.open(f, encoding="utf-8-sig").read()
        i = t.find('{"orders"')
        if i < 0:
            continue
        try:
            out[name] = json.loads(t[i:])["orders"]
        except Exception:
            continue
    return out


def load_results(base):
    """返ってきた出力を M番号 → [問題] で返す。読めないものは別に返す。"""
    out, broken = {}, []
    for f in sorted(glob.glob(os.path.join(base, "res_free", "M*.json"))):
        name = os.path.basename(f)[:-5]
        try:
            d = json.loads(io.open(f, encoding="utf-8-sig").read())
        except Exception as e:
            broken.append((name, str(e)[:70]))
            continue
        qs = d.get("questions") if isinstance(d, dict) else d
        out[name] = qs or []
    return out, broken


def load_tag_master(base):
    """概念タグマスタをアプリの questions.js から読む。正はアプリ側（§24）。"""
    for p in (os.path.expanduser("~/omo/questions.js"),
              os.path.join(base, "..", "..", "..", "omo", "questions.js"),
              os.path.join(base, "questions.js")):
        try:
            t = io.open(p, encoding="utf-8").read()
            m = re.findall(r'tag:\s*"(#[^"]+)"', t)
            if m:
                return set(m)
        except Exception:
            continue
    return set()


def judge_splittable(q):
    """一問一答に回るか（掃除 V1.10 と同じ規則）。ここでは数えるだけ。"""
    stem = str(q.get("stem") or "")
    if q.get("question_type") != "single":
        return False
    if any(w in stem for w in SPLIT_NG_WORDS):
        return False
    if q.get("case_key") or "次の文を読み" in stem:
        return False
    if q.get("image_url"):
        return False
    atoms = [str(a.get("text") or "").strip() for a in (q.get("atoms") or [])]
    if not atoms:
        return False
    if any(COMBO_RE.search(t) or NEG_RE.search(t) or SPEECH_RE.search(t) for t in atoms):
        return False
    if any(LEAK_RE.search(str(a.get("statement") or "")) for a in (q.get("atoms") or [])):
        return False
    return max(len(t) for t in atoms) <= SPLIT_MAX_LEN


def verify(base):
    orders = load_orders(base)
    results, broken = load_results(base)
    master = load_tag_master(base)
    ng, warn, rows = [], [], []

    for name in sorted(broken):
        ng.append(("%s" % name[0], "読めない：%s" % name[1]))

    for name in sorted(orders):
        want = orders[name]
        got = results.get(name)
        if got is None:
            warn.append((name, "まだ返ってきていない"))
            continue
        if len(got) != len(want):
            ng.append((name, "問数が違う（頼んだ %d／返り %d）" % (len(want), len(got))))
        for i, q in enumerate(got):
            o = want[i] if i < len(want) else {}
            tag = "%s-%d" % (name, i + 1)
            # --- 1. 注文どおりか（こちらが決めた値。ずれたら逸脱） ---
            for k in ("unit", "major", "medium", "rank", "variant", "pool",
                      "question_type", "select_count"):
                if o and q.get(k) != o.get(k):
                    ng.append((tag, "%s が注文と違う（%r ≠ %r）"
                               % (k, q.get(k), o.get(k))))
            atoms = q.get("atoms") or []
            if o and len(atoms) != o.get("atom_count"):
                ng.append((tag, "肢の数が注文と違う（%d ≠ %s）"
                           % (len(atoms), o.get("atom_count"))))
            nc = sum(1 for a in atoms if a.get("is_correct"))
            if o and nc != o.get("select_count"):
                ng.append((tag, "正解の数が注文と違う（%d ≠ %s）"
                           % (nc, o.get("select_count"))))
            # --- 2. 作問指示の A・B・E ---
            if q.get("pool") != "mock":
                ng.append((tag, "pool が mock でない（%r）" % q.get("pool")))
            if q.get("variant") not in ("free_a", "free_b"):
                ng.append((tag, "variant が free_a/free_b でない（%r）" % q.get("variant")))
            if q.get("source") is not None:
                ng.append((tag, "source は null のはず（%r）" % q.get("source")))
            if q.get("origin_key") is not None:
                ng.append((tag, "origin_key は null のはず（%r）" % q.get("origin_key")))
            if q.get("unit") == "必修" and nc >= 2:
                ng.append((tag, "必修に「2つ選べ」は作らない"))
            # --- 3. 中身 ---
            if not atoms:
                ng.append((tag, "肢が無い"))
            for a in atoms:
                num = a.get("original_num")
                if not str(a.get("text") or "").strip():
                    ng.append((tag, "肢%s の本文が空" % num))
                if not str(a.get("statement") or "").strip():
                    ng.append((tag, "肢%s の statement が空" % num))
                elif str(a.get("statement")).strip() == str(a.get("text") or "").strip():
                    warn.append((tag, "肢%s の statement が肢の本文と同じ" % num))
                if not str(a.get("explanation") or "").strip():
                    ng.append((tag, "肢%s の解説が空" % num))
                for t in (a.get("tags") or []):
                    if master and t not in master:
                        ng.append((tag, "肢%s のタグ「%s」が概念タグマスタに無い" % (num, t)))
                if o and o.get("tag_candidates") and \
                        not set(a.get("tags") or []) & set(o["tag_candidates"]):
                    warn.append((tag, "肢%s のタグが候補の外" % num))
            if o and o.get("sub_candidates"):
                if (q.get("sub_item") or "") not in o["sub_candidates"]:
                    warn.append((tag, "sub_item が候補の外（%r）" % q.get("sub_item")))
            texts = [("問題文", q.get("stem")), ("全体解説", q.get("overall_explanation"))]
            texts += [("肢%s" % a.get("original_num"), a.get("explanation")) for a in atoms]
            for where, t in texts:
                if BAD_HTML.search(str(t or "")):
                    ng.append((tag, "%s に使ってはいけないHTMLがある" % where))
                body = re.sub(r"[「｢][^」｣]{0,200}[」｣]", "", str(t or ""))
                if DESU_RE.search(body):
                    ng.append((tag, "%s がですます調" % where))
            # 数値の裏づけ（肢・問題文・evidence のどれかにあること）
            okn = set()
            for a in atoms:
                okn |= numbers(a.get("text"))
            okn |= numbers(q.get("stem")) | numbers(q.get("evidence"))
            okn = {canon(x) for x in okn} | {str(i) for i in range(1, 10)}
            for where, t in texts[1:]:
                for n in numbers(t):
                    if canon(n) not in okn:
                        warn.append((tag, "%s の数値「%s」に裏づけが無い" % (where, n)))
            rows.append((name, q))

    # --- 4. 作問指示の C・D・F（全体で見る） ---
    for v in ("free_a", "free_b"):
        sub = [q for _, q in rows if q.get("variant") == v]
        if not sub:
            continue
        cu = collections.Counter(q.get("unit") for q in sub)
        for u, need in QUOTA[v].items():
            if cu.get(u, 0) != need:
                (ng if len(sub) >= sum(QUOTA[v].values()) else warn).append(
                    ("%s" % v, "単元「%s」が %d問（表は %d問）" % (u, cu.get(u, 0), need)))
        cr = collections.Counter(q.get("rank") for q in sub)
        if cr.get("C", 0) > len(sub) * 0.3:
            ng.append((v, "Cランクが3割を超えている（%d/%d）" % (cr.get("C", 0), len(sub))))
    med = collections.Counter((q.get("unit"), q.get("medium")) for _, q in rows)
    for k, c in med.items():
        if c > 1:
            ng.append(("全体", "中項目「%s｜%s」を %d回使っている" % (k[0], k[1], c)))
    stems = collections.Counter(nkey(q.get("stem")) for _, q in rows)
    for k, c in stems.items():
        if c > 1:
            ng.append(("全体", "同じ問題文が %d回（%s…）" % (c, k[:24])))

    return ng, warn, rows


def report(base, ng, warn, rows):
    print("返ってきた問題 %d問（バッチ %d本ぶん）"
          % (len(rows), len(set(n for n, _ in rows))))
    if not rows:
        return
    for v in ("free_a", "free_b"):
        sub = [q for _, q in rows if q.get("variant") == v]
        if not sub:
            continue
        need = sum(QUOTA[v].values())
        cr = collections.Counter(q.get("rank") for q in sub)
        cf = collections.Counter(
            ("2つ選べ" if (q.get("select_count") or 1) >= 2
             else "%d肢" % len(q.get("atoms") or [])) for q in sub)
        alen = [len(str(a.get("text") or "")) for q in sub for a in (q.get("atoms") or [])]
        olen = [len(str(q.get("overall_explanation") or "")) for q in sub]
        spl = sum(1 for q in sub if judge_splittable(q))
        print("  %s %d/%d問" % (v, len(sub), need))
        print("       ランク %s ／ 形式 %s" % (dict(cr), dict(cf)))
        print("       肢の字数 中央値%d／21字超 %d肢（%.0f%%）"
              % (statistics.median(alen),
                 sum(1 for x in alen if x > SPLIT_MAX_LEN),
                 100.0 * sum(1 for x in alen if x > SPLIT_MAX_LEN) / max(len(alen), 1)))
        print("       全体解説 中央値%d字（過去問レーンは311字・仕様§4-4は200〜400字）"
              % statistics.median(olen))
        print("       一問一答に回る %d問（%.0f%%）" % (spl, 100.0 * spl / len(sub)))
    print()
    if ng:
        print("NG（このままでは取り込まない） %d件" % len(ng))
        for a, b in ng[:40]:
            print("    %-12s %s" % (a, b))
        if len(ng) > 40:
            print("    …ほか %d件" % (len(ng) - 40))
    else:
        print("NG なし")
    if warn:
        cc = collections.Counter(re.sub(r"[0-9]+", "N", b) for _, b in warn)
        print("確認（取り込みは止めない） %d件" % len(warn))
        for k, c in cc.most_common(8):
            print("    %4d件 %s" % (c, k[:70]))


def assemble(base, rows, force=False):
    """取り込み用の1本にまとめる。**NGがあるときは呼ばない**（呼び出し側で判定）。"""
    out = []
    for name, q in rows:
        r = dict(q)
        r["pool"] = "mock"
        r.setdefault("source", None)
        r.setdefault("origin_key", None)
        # 一問一答の可否は**この規則を正とする**（掃除 V1.09 と同じ考え方）。
        # 作問側の値は使わない。1問ずつの判断は揺れるが、規則は揺れない。
        r["is_splittable"] = judge_splittable(q)
        out.append(r)
    outd = os.path.join(base, "out")
    os.makedirs(outd, exist_ok=True)
    p = os.path.join(outd, "%s_取り込み用_体験用の模試_V1.00.json"
                     % datetime.datetime.now().strftime("%Y%m%d"))
    io.open(p, "w", encoding="utf-8").write(
        json.dumps({"questions": out}, ensure_ascii=False, indent=1))
    spl = sum(1 for q in out if q.get("is_splittable"))
    print()
    print("取り込み用 %d問 → %s" % (len(out), os.path.basename(p)))
    print("  一問一答に回る %d問（%.0f%%）" % (spl, 100.0 * spl / max(len(out), 1)))
    print("  ※ アプリの設定 → 一括インポート →「ファイルから取り込む」で入れます。")
    return p


def selftest():
    R = []

    def ok(n, c, d=""):
        R.append((bool(c), n, str(d)))

    ok("空白を詰めた鍵", nkey("第111回  午前問1") == "第111回午前問1")
    ok("数値を拾う（英字の直後は拾わない）",
       numbers("SpO2 97 % と 1,200 人") == {"97", "1,200"}, sorted(numbers("SpO2 97 % と 1,200 人")))
    ok("桁区切りをそろえる", canon("1,200") == "1200")

    good = {"question_type": "single", "stem": "検査用の問題はどれか。",
            "atoms": [{"original_num": 1, "is_correct": True, "text": "短い言葉",
                       "statement": "短い言葉である。"},
                      {"original_num": 2, "is_correct": False, "text": "別の言葉",
                       "statement": "別の言葉である。"}]}
    ok("短い肢は一問一答に回る", judge_splittable(good) is True)
    long_atom = json.loads(json.dumps(good))
    long_atom["atoms"][0]["text"] = "あ" * 25
    ok("21字を超える肢があれば回さない", judge_splittable(long_atom) is False)
    neg = json.loads(json.dumps(good))
    neg["atoms"][0]["text"] = "適さない。"
    ok("否定形の肢があれば回さない", judge_splittable(neg) is False)
    leak = json.loads(json.dumps(good))
    leak["atoms"][0]["statement"] = "これは誤りである。"
    ok("statement に答えがあれば回さない", judge_splittable(leak) is False)
    rel = json.loads(json.dumps(good))
    rel["stem"] = "最も適切なのはどれか。"
    ok("相対判断の設問は回さない", judge_splittable(rel) is False)

    ok("危険なHTMLを見つける", bool(BAD_HTML.search('<img src=x onerror=y>')))
    ok("普通のHTMLは通す", not BAD_HTML.search("<b>太字</b><table><tr><td>あ</td></tr></table>"))
    ok("ですます調を見つける", bool(DESU_RE.search("これは正しいです。")))
    ok("かぎかっこの中は見ない（呼び出し側で外す）",
       not DESU_RE.search(re.sub(r"[「｢][^」｣]{0,200}[」｣]", "", "A さんは「飲み忘れたんです。」と話した。")))
    ok("free_a は30問・free_b は60問",
       sum(QUOTA["free_a"].values()) == 30 and sum(QUOTA["free_b"].values()) == 60)

    bad = [x for x in R if not x[0]]
    for g, n, d in R:
        print(("  ok  " if g else "  NG  ") + n + ("" if g else "   << " + d))
    print("\n%d/%d  体験用の検証" % (len(R) - len(bad), len(R)))
    return 1 if bad else 0


def main():
    base = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else "."
    force = "--force" in sys.argv
    ng, warn, rows = verify(base)
    report(base, ng, warn, rows)
    if ng and not force:
        print()
        print("NGがあるので、取り込み用のJSONは作りませんでした。")
        print("直してから、もう一度この道具を走らせてください（--force で強行できます）。")
        return
    if not rows:
        return
    assemble(base, rows, force)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    main()
