# -*- coding: utf-8 -*-
"""括弧と欠字の化けを直す V1.00（2026-09-07）

アプリの取り込みが「lost_bad 41件／13行」と報告したので、全部を目で見た。
**山かっこ〈〉が別の字に化けている**のが正体だった。

    第114回 午前問88   ポリオ?急性灰白髄炎C      → ポリオ〈急性灰白髄炎〉
    第114回 午前問9    Kaup?カウプC指数         → Kaup〈カウプ〉指数
    第113回 午後問28   法律u男女雇用機会均等法x   → 法律〈男女雇用機会均等法〉
    第113回 午後問20   Simsuシムスx位           → Sims〈シムス〉位

  開き〈 が ? か u に、閉じ 〉 が C か x に化ける。
  u / x は V2.64 で既に分かっていた。**? / C は今回の実測で分かった。**

もう1つ、括弧ではない欠字が2種類あった。

    大W骨・大W動脈  → 大腿骨・大腿動脈   （W が 腿 の位置に入っている）
    中枢から末?へ   → 末梢              （? が 梢 の位置に入っている）

【壊してはいけないもの】
  W も u も x も C も ? も、**本物の文字として出てくる**。

    WHO憲章 ／ Wernicke〈ウェルニッケ〉野 ／ ビタミンC ／ COPD

  実測で WHO 3件・Wernicke 2件があった。W を一律に 腿 へ替えたら壊れる。
  そこで直すのは **前後が揃っているときだけ**にした。

    ・「大W」の2文字が揃ったときだけ 大腿 にする（W単独は触らない）
    ・「末?」の2文字が揃ったときだけ 末梢 にする
    ・? と C、u と x が **対になっている**ときだけ 〈 〉 にする
      （間に別の ? C u x を挟まない・中身は24文字まで）

  それ以外の ? W u x C は **触らず、数えて報告する**。人が見て決める。

使い方
  python3 括弧と欠字の化けを直す_V1.00.py --in 入力.json --out 出力.json
  python3 括弧と欠字の化けを直す_V1.00.py --dir フォルダ --outdir 出力フォルダ
  python3 括弧と欠字の化けを直す_V1.00.py --selftest
"""
import glob, io, json, os, re, sys

JP = r"ぁ-んァ-ヶ一-龥"

# --- 対になっているときだけ直す（開き→閉じ） ---
PAIRS = [
    # ?…C  … 中に別の ? C を挟まない。中身は1〜24文字。
    (re.compile(r"([" + JP + r"A-Za-z0-9])\?([^?C\n]{1,24})C"), r"\1〈\2〉"),
    # u…x
    (re.compile(r"([" + JP + r"A-Za-z0-9])u([^ux\n]{1,24})x"), r"\1〈\2〉"),
]

# --- 前後が揃っているときだけ直す欠字 ---
LOST = [
    (re.compile(r"大W(?=[骨動])"), "大腿"),   # 大W骨・大W動脈。WHO/Wernicke は「大」が前に無い
    (re.compile(r"末\?"), "末梢"),            # 末?循環・中枢から末?へ
]

# --- 直さず数えるだけ ---
WATCH = re.compile(r"[" + JP + r"]\s?[?WuxC]\s?[" + JP + r"]")


def fix_text(s):
    """1つの文字列を直す。戻り値は (直した文字列, 直した件数)。"""
    if not isinstance(s, str) or not s:
        return s, 0
    n = 0
    # 欠字を先に直す。「末?」を先に潰さないと、後ろの C と対に見えることがある。
    for rx, rep in LOST:
        s, k = rx.subn(rep, s)
        n += k
    for rx, rep in PAIRS:
        while True:
            s2, k = rx.subn(rep, s)
            n += k
            if not k:
                break
            s = s2
    return s, n


def watch_text(s):
    return [m.group(0) for m in WATCH.finditer(s or "")]


FIELDS = ["stem", "overall_explanation", "unit", "major", "medium", "target",
          "sub_item", "evidence"]
ATOM = ["text", "statement", "explanation"]


def fix_question(q, stat, watch):
    src = q.get("source") or "?"
    for f in FIELDS:
        if f in q:
            q[f], n = fix_text(q[f])
            stat["fixed"] = stat.get("fixed", 0) + n
            for w in watch_text(q.get(f)):
                watch.setdefault(w, set()).add(src)
    for a in q.get("atoms") or []:
        for f in ATOM:
            if f in a:
                a[f], n = fix_text(a[f])
                stat["fixed"] = stat.get("fixed", 0) + n
                for w in watch_text(a.get(f)):
                    watch.setdefault(w, set()).add(src)
    return q


def run_dir(src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    stat, watch = {}, {}
    n_files = n_q = 0
    for f in sorted(glob.glob(os.path.join(src_dir, "*.json"))):
        try:
            d = json.loads(io.open(f, encoding="utf-8-sig").read())
        except Exception:
            continue
        n_files += 1
        for q in (d.get("questions") or []):
            fix_question(q, stat, watch)
            n_q += 1
        io.open(os.path.join(out_dir, os.path.basename(f)), "w", encoding="utf-8").write(
            json.dumps(d, ensure_ascii=False, indent=1))
    print("読んだ %d本 / %d問 → %s" % (n_files, n_q, out_dir))
    print("  直した化け %d件" % stat.get("fixed", 0))
    if watch:
        print("  直さず見張っているもの（人が決める）:")
        for w in sorted(watch, key=lambda x: -len(watch[x]))[:20]:
            print("    %-10r %2d問  例: %s" % (w, len(watch[w]), sorted(watch[w])[0]))
    else:
        print("  直さず見張っているもの: なし")


def selftest():
    cases = [
        # 直すもの
        ("ポリオ?急性灰白髄炎Cと結核", "ポリオ〈急性灰白髄炎〉と結核"),
        ("Kaup?カウプC指数", "Kaup〈カウプ〉指数"),
        ("一次救命処置?BLSCで回復体位", "一次救命処置〈BLS〉で回復体位"),
        ("法律u男女雇用機会均等法xに規定", "法律〈男女雇用機会均等法〉に規定"),
        ("Simsuシムスx位", "Sims〈シムス〉位"),
        ("Duchenneuデュシェンヌx型", "Duchenne〈デュシェンヌ〉型"),
        ("右大W骨前面を図に示す", "右大腿骨前面を図に示す"),
        ("大W動脈は下肢", "大腿動脈は下肢"),
        ("中枢から末?への一方向", "中枢から末梢への一方向"),
        ("末?循環不全", "末梢循環不全"),
        # 壊してはいけないもの
        ("WHO憲章の前文において", "WHO憲章の前文において"),
        ("Wernicke〈ウェルニッケ〉野", "Wernicke〈ウェルニッケ〉野"),
        ("ビタミンCを摂取する", "ビタミンCを摂取する"),
        ("COPDの患者", "COPDの患者"),
        ("世界保健機関〈WHO〉の設立", "世界保健機関〈WHO〉の設立"),
        ("Quality of Life", "Quality of Life"),
        # 2つ入っていても両方直す
        ("法律?障害者総合支援法Cと法律?感染症法C",
         "法律〈障害者総合支援法〉と法律〈感染症法〉"),
        # ビタミンCが後ろにあっても、先の対だけを直す
        ("ポリオ?急性灰白髄炎CとビタミンC", "ポリオ〈急性灰白髄炎〉とビタミンC"),
    ]
    bad = 0
    for src, want in cases:
        got, _ = fix_text(src)
        good = (got == want)
        print(("  ok  " if good else "  NG  ") + src[:34]
              + ("" if good else "   << 得:%r 期:%r" % (got, want)))
        bad += (0 if good else 1)
    # 何度かけても同じ
    once, _ = fix_text("ポリオ?急性灰白髄炎C")
    twice, _ = fix_text(once)
    good = (once == twice)
    print(("  ok  " if good else "  NG  ") + "冪等")
    bad += (0 if good else 1)
    print("\n%d/%d  括弧と欠字" % (len(cases) + 1 - bad, len(cases) + 1))
    sys.exit(1 if bad else 0)


def main():
    a = sys.argv
    if "--selftest" in a:
        return selftest()
    if "--dir" in a:
        src = a[a.index("--dir") + 1]
        out = a[a.index("--outdir") + 1] if "--outdir" in a else (src + "_fixed")
        return run_dir(src, out)
    if "--in" in a:
        src = a[a.index("--in") + 1]
        out = a[a.index("--out") + 1]
        d = json.loads(io.open(src, encoding="utf-8-sig").read())
        stat, watch = {}, {}
        for q in (d.get("questions") or []):
            fix_question(q, stat, watch)
        io.open(out, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False))
        print("直した化け %d件 → %s" % (stat.get("fixed", 0), out))
        return
    print(__doc__)


if __name__ == "__main__":
    main()
