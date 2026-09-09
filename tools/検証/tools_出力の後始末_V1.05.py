# -*- coding: utf-8 -*-
"""tools_出力の後始末_V1.04.py

V1.04 で足したこと（V1.03 までの働きは1つも消していません）

  ⑤ タグ・小項目・分類の中黒の化けを直す
     `・`(U+30FB) が `·`(U+00B7) `･`(U+FF65) に化ける。見た目がほぼ同じ。
     実測：#医療安全·アクシデント防止 が、概念タグマスタの
     #医療安全・アクシデント防止 と一字違いになり「マスタに無い」と数えられていた。
     3種13件。**本文には掛けない**（本文の中黒は別の意味を持ちうる）。

  ⑥ タグを概念タグマスタの表記へ寄せる
     正規化して一致するなら、マスタの表記に書き直す。
     マスタの正はアプリの questions.js（103個）。ここで作らない。

  ⑦ 名前が1語だけ違うタグを、対応表で寄せる（TAG_ALIAS）
     実測1件：#投薬・注射・点滴管理 → #与薬・注射・点滴管理
     機械が勝手に近い名前へ寄せると事故になるので、**表に書いたものだけ**直す。

  ⑧ 説明文をタグにしてしまったものを落とす
     実測1件：#ハロペリドールなどの油性注射剤（該当なし、標準値表・論点キーワードより）
     「（該当なし」を含むものだけ。それ以外のマスタ外タグは**落としません**。
     落とすと作問側に返す手がかりが消えるので、検証で NG として残します。

  助詞ツールを V1.00 → V1.01 へ（`of the` のような2語つづきに対応。実測8件）

--- 以下 V1.03 まで ---
出力の後始末 V1.03（2026-09-08）

V1.03：**分類4欄（unit / major / medium / target）を入力バッチから写し直す。**

  【なぜ】分類名そのものが壊れていた（実測23件）。

      人体の構造と機能            → 人人体 の構造と機能
      4. 社会保険制度の基本        → 4. Social 保険制度の基本
      5. 社会福祉の基本            → 5. 社会福祉 the 基本
      A. 人体の基本的な構造と正常な機能 → A. 人体の基本的な構造 and 正常な機能
      B. がん患者の集学的治療と…     → B. がn患者の集学的治療と…
      疾病の成り立ちと回復の促進     → 疾病の成り立ちと回復 of the 促進
      在宅看護論／地域・在宅看護論    → **In_progress**
      …知識を問う。                → …理解を問う。（5件・化けではなく書き換え）

    分類が壊れると出題基準の照合が外れ、3階層ツリーが割れる。

  【なぜ機械で直してよいのか】
    分類は LM が考えるものではなく、**入力から写すだけ**のもの。
    共通仕様 §3-5「分類は出題基準の表記を一字も変えない」が規則で、
    入力バッチの値が正。写し間違いを元に戻すのは、書き換えではなく**復旧**。

    「知識→理解」のような語の置き換えは化け直しでは救えない
    （意味が変わるので機械では判断できない）。入力から写すなら確実に戻る。

  写した件数と、写す前の値は必ず報告する。黙って直さない。

【V1.02 の説明】

V1.02：括弧の化けが**3組**あることが分かったので、道具を V1.01 に差し替えた。
  〈→? 〉→C ／ 〈→u 〉→x ／ **〈→V 〉→Z（今回）**
  手前の文字にアクセント付きラテン文字（Barré の é）も認める。

【V1.01 の説明】

V1.01：**括弧と欠字の化け**も同じ一度で直す。V1.00 の動きは1つも消していない。
  アプリの取り込みが「lost_bad 41件」と報告したので全部を見たら、
  山かっこ〈〉が別の字に化けていた。
      ポリオ?急性灰白髄炎C  → ポリオ〈急性灰白髄炎〉
      法律u男女雇用機会均等法x → 法律〈男女雇用機会均等法〉
      大W骨 → 大腿骨 ／ 末? → 末梢
  開き〈 が ? か u に、閉じ 〉 が C か x に化ける。u/x は既知、**?/C は今回分かった**。
  直し方は tools/括弧と欠字の化けを直す_V1.01.py をそのまま使う（規則を二重に持たない）。
  WHO・Wernicke・ビタミンC・COPD は壊さない（対になっているときだけ直す）。

【V1.00 の説明】

**検証に掛ける前**に、機械で片づく汚れを落とす。

【なぜ結合時ではなく検証の前なのか（実測でつまずいた点）】
  はじめ、結合ツール（tools/仕上げ結果を結合する_V1.02.py）に掃除を足した。
  ところが結合は**検証に通った問題だけ**を出すので、
  `#in_progress` を持つ問題は先にNGで落ちていて、掃除する相手がいなかった。
  実測：直した件数 0。

  順序が逆だった。**掃除 → 検証 → 結合**が正しい。
  掃除すればNGが減り、その問題が配布物に入る。

【res_finish は触らない】
  作問（PAD）が書き続けるフォルダなので、書き換えると衝突する。
  掃除した版を res_finish_clean/ へ別に出す。元は残る。

【落とすもの・直すもの】
  ① 作業中の印（#in_progress など）を tags から落とす
     残すとアプリの概念ランキングに「#in_progress」がそのまま載る（実測）。
     作業中の印であってデータではない。
  ② 英単語化けを直す（of / is が日本語に挟まれているときだけ）
     本文・全体解説・分類名・小項目・evidence・肢・**タグ**に掛ける。
     直し方は tools/助詞の英単語化けを直す_V1.00.py をそのまま使う（規則を二重に持たない）。

【直さないもの】
  「#投薬・注射・点滴管理 → #与薬・注射・点滴管理」のような誤記は寄せない。
  投薬と与薬は別の語で、意味が変わりうる。数えて報告し、**人が決める**。
  直すつもりで壊すほうが害が大きい。

使い方
  python3 tools_出力の後始末_V1.00.py                 # res_finish → res_finish_clean
  python3 tools_出力の後始末_V1.00.py --selftest
"""
import glob, importlib.util, io, json, os, re, shutil, sys, unicodedata

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "res_finish")
DST = os.path.join(BASE, "res_finish_clean")

# 化けの直し方は既にある道具をそのまま使う（規則を二重に持たない）
def _load(path, name):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m

_garble = _load(os.path.expanduser("~/omo/tools/助詞の英単語化けを直す_V1.01.py"), "_garble")
# V1.01：括弧と欠字の化け（?→〈 / C→〉 / u→〈 / x→〉 / 大W→大腿 / 末?→末梢）
_kakko = _load(os.path.expanduser("~/omo/tools/括弧と欠字の化けを直す_V1.01.py"), "_kakko")

WORK_TAGS = {"#in_progress", "#inprogress", "#作業中", "#todo", "#wip"}
FIELDS = ["stem", "overall_explanation", "unit", "major", "medium", "target",
          "sub_item", "evidence"]
ATOM_FIELDS = ["text", "statement", "explanation"]

# 日本語に挟まれた**小文字だけ**の英単語を見張る（直さない）。
# 大文字を含む語はほぼ医学略語（AED・ALS・HBV…）で、日本語に挟まれて出るのが正常。
WATCH_EN = re.compile(_garble.J + r"\s?\b([a-z][a-z-]{1,20})\b\s?" + _garble.J)
OK_EN = {"of", "dopa", "mmHg", "kcal", "mg", "kg", "cm", "mm", "mL", "dL"}


def fix_text(s, stat, watch, src):
    if not isinstance(s, str) or not s:
        return s
    out, n = _garble.fix_text(s)
    if n:
        stat["直した化け"] = stat.get("直した化け", 0) + n
    # V1.01：括弧と欠字。対になっているときだけ直す（本物の C・W・u・x は壊さない）
    out, n2 = _kakko.fix_text(out)
    if n2:
        stat["直した括弧・欠字"] = stat.get("直した括弧・欠字", 0) + n2
    for w in _kakko.watch_text(out):
        watch.setdefault("《" + w + "》", set()).add(src)
    for w in _garble.watch_text(out):
        watch.setdefault(w, set()).add(src)
    for m in WATCH_EN.finditer(out):
        w = m.group(1)
        if w not in OK_EN:
            watch.setdefault(w, set()).add(src)
    return out


def clean_question(q, stat, watch, unknown):
    src = q.get("source") or "?"
    for f in FIELDS:
        if f in q:
            q[f] = fix_text(q[f], stat, watch, src)
    # V1.04：マスタと一字一句で比べる欄にだけ、中黒の化けを直す
    for f in ("sub_item",) + tuple(CLASS_FIELDS):
        if isinstance(q.get(f), str):
            q[f], n = _garble.fix_nakaguro(q[f])
            if n:
                stat["直した中黒"] = stat.get("直した中黒", 0) + n
    for a in q.get("atoms") or []:
        for f in ATOM_FIELDS:
            if f in a:
                a[f] = fix_text(a[f], stat, watch, src)
        tags = a.get("tags")
        if isinstance(tags, list):
            out = []
            for t in tags:
                if not isinstance(t, str):
                    continue
                key = t.strip().lower().replace("＿", "_")
                if key in WORK_TAGS:
                    stat["落とした作業中の印"] = stat.get("落とした作業中の印", 0) + 1
                    continue
                fixed = fix_text(t, stat, watch, src)
                fixed = fix_tag(fixed, stat)      # V1.04
                if fixed is None:
                    continue
                if fixed != t:
                    stat["直したタグ"] = stat.get("直したタグ", 0) + 1
                if fixed not in out:
                    out.append(fixed)
            a["tags"] = out
    return q


# V1.04 ---------------------------------------------------------------
# 名前が1語だけ違うものは、機械に判断させない。ここに書いたものだけ寄せる。
TAG_ALIAS = {
    "#投薬・注射・点滴管理": "#与薬・注射・点滴管理",   # 実測1件（第114回 午前問18）
    "#回家療養支援・訪問看護": "#在宅療養支援・訪問看護",  # 実測1件（第111回 午前問71）
                                                    # 「在宅」が「回家」に化けた
    "#グン剤・注射・点滴管理": "#与薬・注射・点滴管理",   # 実測1件（第111回 午後問22）
                                                    # 「与薬」が「グン剤」に化けた
}
# 説明文をタグにしてしまった印。これを含むタグだけ落とす。
TAG_JUNK = ("（該当なし", "(該当なし")


def load_tag_master():
    """概念タグマスタ（103個）をアプリの questions.js から読む。
    正はアプリ側（§24：データ契約を二重に持たない）。
    見つからなければ空を返し、寄せをまるごと見送る。"""
    for p in [os.path.expanduser("~/omo/questions.js"),
              "/sessions/ecstatic-wizardly-dijkstra/mnt/owner/omo/questions.js"]:
        try:
            t = io.open(p, encoding="utf-8").read()
            k = t.index("CONCEPT_TAGS_MASTER = [")
            blk = t[k:t.index("\n];", k)]
            m = re.findall(r'"(#[^"]+)"', blk)
            if m:
                return {normtag(x): x for x in m}
        except Exception:
            continue
    return {}


def normtag(v):
    """タグを比べるための形。中黒3種と空白を落とす。"""
    t = unicodedata.normalize("NFKC", str(v or ""))
    for c in ("\u00b7", "\uff65", "\u2027", "\u30fb"):
        t = t.replace(c, "")
    return t.replace(" ", "").replace("\u3000", "")


TAG_MASTER = load_tag_master()


def fix_tag(t, stat):
    """タグ1つを直す。落とすときは None を返す。"""
    if any(j in t for j in TAG_JUNK):
        stat["落とした説明文タグ"] = stat.get("落とした説明文タグ", 0) + 1
        return None
    t2, n = _garble.fix_nakaguro(t)
    if n:
        stat["直した中黒"] = stat.get("直した中黒", 0) + n
    if t2 in TAG_ALIAS:
        stat["対応表で寄せたタグ"] = stat.get("対応表で寄せたタグ", 0) + 1
        t2 = TAG_ALIAS[t2]
    hit = TAG_MASTER.get(normtag(t2))
    if hit and hit != t2:
        stat["マスタの表記へ寄せた"] = stat.get("マスタの表記へ寄せた", 0) + 1
        t2 = hit
    return t2


def load_reference():
    """入力バッチ（作問へ渡した元）を source で引けるようにする。

    分類の正はここ。ext_v4.json ではない（検証ツールと同じ出どころを使う）。"""
    ref = {}
    for f in sorted(glob.glob(os.path.join(BASE, "batches_finish_v2", "F*.txt"))):
        txt = io.open(f, encoding="utf-8-sig").read()
        j = json.loads(txt[txt.index("\n{\n"):])
        for q in j.get("questions", []):
            ref[re.sub(r"\s+", "", q.get("source") or "")] = q
    return ref


CLASS_FIELDS = ["unit", "major", "medium", "target"]


def restore_class(q, ref, stat, restored):
    """分類4欄を入力バッチから写し直す。変えたものは全部記録する。"""
    o = ref.get(re.sub(r"\s+", "", q.get("source") or ""))
    if not o:
        stat["入力バッチに無いsource"] = stat.get("入力バッチに無いsource", 0) + 1
        return q
    for f in CLASS_FIELDS:
        want = o.get(f)
        if want is None:
            continue
        if q.get(f) != want:
            restored.append((q.get("source"), f, q.get(f), want))
            q[f] = want
            stat["写し直した分類"] = stat.get("写し直した分類", 0) + 1
    return q


# ================= V1.05（2026-09-09）でここから足した3つ =================
#
# どれも「作問AIに書かせる必要がなかったもの」を、こちらで機械的に確定させる。
# AIに毎回きちんと書かせようとして失敗し続けるより、
# **導出できるものは導出する**ほうが確実で、しかも作り直しの回数が減る。
# 実測：この3つでNGが 33問 → 13問 に減った。

JP = r'\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u3005\u30FC'


def fix_halfwidth_punct(t, stat):
    """日本語に挟まれた半角の , . を、全角の 、。 に戻す（V1.05）。

    実測4問：「入院後, A さん」「死去後,食事量」「病室から出ていこうとした. 看護師が」
    「最近, 足がつる」。読点・句点が半角に化けている。
    **両隣が日本語のときだけ**直す。1,000 や 1.7 は両隣が数字なので触らない。
    Duchenne, A のように片側がラテン文字のものも触らない。
    """
    if not isinstance(t, str) or not t:
        return t, 0
    n = 0

    def rep(m):
        nonlocal n
        n += 1
        return m.group(1) + ('、' if m.group(2) == ',' else '。')

    # **左隣が日本語のときだけ**直す。右隣は見ない。
    # 実測「入院後, A さんから」のように、右隣がラテン文字のことがあるため
    # （元の文は「入院後、A さんから」で、読点だけが半角に化けていた）。
    # 左隣が数字・ラテン文字のものは触らないので、1,000 / 1.7 / mg/dL, 基準値 /
    # Duchenne, A は無傷。半角のあとの空白は、全角の読点・句点に戻すときに落とす。
    t = re.sub('([%s])([,.])[ \u3000]?' % JP, rep, t)
    if n:
        stat["直した半角の読点・句点"] = stat.get("直した半角の読点・句点", 0) + n
    return t, n


def repair_source(q, ref, stat):
    """出典名の打ち直し崩れを直す（V1.05）。

    実測3問：「第111回 午前1」「第111回 午前2」「第111回 午前3」。
    「問」が落ちている。入力バッチに実在する形に直せるときだけ直す。
    **勝手に作らない**——直した結果が入力バッチに無ければ、元のまま戻す。
    """
    s0 = q.get('source') or ''
    key = lambda x: re.sub(r'\s+', '', x)
    if key(s0) in ref:
        return
    m = re.match(r'^(第\d+回\s*(?:午前|午後))\s*(\d+)$', s0.strip())
    if not m:
        return
    cand = '%s問%s' % (m.group(1), m.group(2))
    if key(cand) in ref:
        q['source'] = cand
        stat["直した出典名"] = stat.get("直した出典名", 0) + 1


def load_std():
    """標準値表を id で引けるようにする（V1.05）。確度の正はこの表。"""
    std = {}
    for name in ('20260830_標準値表_V1.05.tsv', '20260830_標準値表_V1.04.tsv'):
        p2 = os.path.join(BASE, name)
        if not os.path.exists(p2):
            continue
        L = io.open(p2, encoding='utf-8-sig').read().split('\n')
        cols = L[0].split('\t')
        for l in L[1:]:
            if not l.strip():
                continue
            r = dict(zip(cols, l.split('\t')))
            if r.get('id'):
                std[r['id']] = r
        break
    return std


def add_kakudo_c_note(q, std, stat):
    """確度Cの行を引いていたら、evidence に注記を足す（V1.05）。

    【なぜ機械で足すか】
    §10 は「確度Cの値を使ったら evidence に注記を残す」と決めている。
    これまで作問AIに書かせていたが、**3回作り直しても毎回落ちた**。しかも
    作り直すたびに引く行が増え（第111回午前問8 は3回目で H091 が加わった）、
    追いかけても終わらない。

    確度は標準値表に書いてある。**引いた id が分かれば、注記は導出できる。**
    書かせるのをやめて、こちらで確定させる。中身は表の写しなので、
    人が判断する余地は無い（＝誇張にならない）。
    """
    ev = q.get('evidence')
    if not isinstance(ev, str) or not ev.strip():
        return
    if '確度C' in ev:
        return
    ids = [i for i in dict.fromkeys(re.findall(r'\b([QH]\d{3})\b', ev))
           if std.get(i, {}).get('確度') == 'C']
    if not ids:
        return
    lines = []
    for i in ids:
        r = std[i]
        lines.append('20260830_標準値表_V1.05.txt：%s は確度C（%s／出典：%s）'
                     % (i, r.get('項目', ''), r.get('出典', '') or '原典未特定'))
    q['evidence'] = ev.rstrip('\n') + '\n' + '\n'.join(lines)
    stat["足した確度Cの注記"] = stat.get("足した確度Cの注記", 0) + len(ids)


def load_candidates():
    """候補タグは入力バッチの hints にある（検証ツールと同じ出どころ）。"""
    cand = {}
    for f in sorted(glob.glob(os.path.join(BASE, "batches_finish_v2", "F*.txt"))):
        txt = io.open(f, encoding="utf-8-sig").read()
        j = json.loads(txt[txt.index("\n{\n"):])
        for h in j.get("hints", []):
            cand[re.sub(r"\s+", "", h.get("source") or "")] = set(h.get("tag_candidates") or [])
    return cand


def main():
    if "--selftest" in sys.argv:
        return selftest()
    os.makedirs(DST, exist_ok=True)
    cand = load_candidates()
    ref = load_reference()
    std = load_std()
    restored = []
    stat, watch, unknown = {}, {}, {}
    n_files = n_q = 0
    broken = []
    for f in sorted(glob.glob(os.path.join(SRC, "*.json"))):
        try:
            d = json.loads(io.open(f, encoding="utf-8-sig").read())
        except Exception as e:
            broken.append((os.path.basename(f), str(e)[:50]))
            continue
        n_files += 1
        for q in (d.get("questions") or []):
            clean_question(q, stat, watch, unknown)
            # V1.05：分類を写し直す前に出典名を直す（直さないと引けない）
            repair_source(q, ref, stat)
            restore_class(q, ref, stat, restored)
            # V1.05：半角に化けた読点・句点を戻す
            for fld in ("stem", "overall_explanation", "lead"):
                if isinstance(q.get(fld), str):
                    q[fld], _ = fix_halfwidth_punct(q[fld], stat)
            for a in (q.get("atoms") or []):
                for fld in ("text", "statement", "explanation"):
                    if isinstance(a.get(fld), str):
                        a[fld], _ = fix_halfwidth_punct(a[fld], stat)
            # V1.05：確度Cの注記を標準値表から足す
            add_kakudo_c_note(q, std, stat)
            n_q += 1
            # 掃除しても候補外に残るタグを数える（落とさない・報告だけ）
            pool = cand.get(re.sub(r"\s+", "", q.get("source") or ""), set())
            for a in q.get("atoms") or []:
                for t in (a.get("tags") or []):
                    if pool and t not in pool:
                        unknown.setdefault(t, set()).add(q.get("source"))
        # BOMを付けずに書き出す（検証がBOMを毎回報告しないように）
        io.open(os.path.join(DST, os.path.basename(f)), "w", encoding="utf-8").write(
            json.dumps(d, ensure_ascii=False, indent=1))

    print("読んだ %d本 / %d問 → %s" % (n_files, n_q, os.path.basename(DST)))
    for k in sorted(stat):
        print("  %-20s %4d件" % (k, stat[k]))
    if broken:
        print("  読めなかったファイル:", broken)
    if restored:
        print("\n入力バッチから写し直した分類（%d件・黙って直さない）:" % len(restored))
        seen = set()
        for src, f, was, now in restored:
            key = (f, was, now)
            if key in seen:
                continue
            seen.add(key)
            print("  %-18s %-7s %r" % (src, f, was))
            print("  %-18s %-7s → %r" % ("", "", now))
    if unknown:
        print("\n掃除しても候補外に残るタグ（落としていない・人が決める）:")
        for t in sorted(unknown, key=lambda x: -len(unknown[x])):
            qs = sorted(unknown[t])
            print("  %-34s %2d問  例: %s" % (t, len(qs), " / ".join(qs[:2])))
    else:
        print("\n掃除しても候補外に残るタグ: なし")
    if watch:
        print("\n直さず見張っている語:")
        for w in sorted(watch, key=lambda x: -len(watch[x]))[:10]:
            print("  %-12s %2d問" % (w, len(watch[w])))


def selftest():
    st, wt, un = {}, {}, {}
    q = {"source": "t", "stem": "発達段階 of の組合せ", "sub_item": "筋収縮 of 機構",
         "major": "社会保険制度 of 基本",
         "atoms": [{"text": "脾静脈 is 門脈系", "tags": ["#in_progress", "#小児 of の生活",
                                                    "#正しいタグ", "#正しいタグ"]}]}
    clean_question(q, st, wt, un)
    a = q["atoms"][0]
    ok = []
    ok.append(("of＋の を潰す", q["stem"], "発達段階の組合せ"))
    ok.append(("小項目も直す", q["sub_item"], "筋収縮の機構"))
    ok.append(("分類名も直す", q["major"], "社会保険制度の基本"))
    ok.append(("肢も直す", a["text"], "脾静脈は門脈系"))
    ok.append(("作業中の印を落とす", "#in_progress" in a["tags"], False))
    ok.append(("タグの化けも直す", a["tags"][0], "#小児の生活"))
    ok.append(("同じタグを重ねない", a["tags"].count("#正しいタグ"), 1))
    ok.append(("落とした数を数える", st.get("落とした作業中の印"), 1))

    # --- V1.04 で足したぶん ---
    st2, wt2, un2 = {}, {}, {}
    q2 = {"source": "t2",
          "sub_item": "安全管理体制整備、医療安全文化 of the 醸成",
          "major": "看護管理·医療提供の仕組み",
          "atoms": [{"text": "本文の中黒·は触らない",
                     "tags": ["#医療安全·アクシデント防止",
                              "#看護管理·医療提供 of the 仕組み",
                              "#投薬・注射・点滴管理",
                              "#ハロペリドールなどの油性注射剤（該当なし、標準値表より）",
                              "#与薬・注射・点滴管理"]}]}
    clean_question(q2, st2, wt2, un2)
    t2 = q2["atoms"][0]["tags"]
    ok.append(("of the（2語つづき）も直す", q2["sub_item"], "安全管理体制整備、医療安全文化の醸成"))
    ok.append(("分類の中黒を直す", q2["major"], "看護管理・医療提供の仕組み"))
    ok.append(("タグの中黒を直す", "#医療安全・アクシデント防止" in t2, True))
    ok.append(("タグの of the も直す", "#看護管理・医療提供の仕組み" in t2, True))
    ok.append(("対応表で寄せる（投薬→与薬）", "#投薬・注射・点滴管理" in t2, False))
    ok.append(("寄せた先が重ならない", t2.count("#与薬・注射・点滴管理"), 1))
    ok.append(("説明文タグを落とす", any("該当なし" in x for x in t2), False))
    ok.append(("本文の中黒は触らない",
               q2["atoms"][0]["text"], "本文の中黒·は触らない"))
    ok.append(("マスタを読めている（103個）", len(TAG_MASTER) >= 100, True))

    st4, wt4, un4 = {}, {}, {}
    q4 = {"source": "t4", "atoms": [{"text": "x", "tags": ["#回家療養支援・訪問看護"]}]}
    clean_question(q4, st4, wt4, un4)
    ok.append(("回家→在宅", q4["atoms"][0]["tags"], ["#在宅療養支援・訪問看護"]))

    st5, wt5, un5 = {}, {}, {}
    q5 = {"source": "t5", "atoms": [{"text": "x", "tags": ["#グン剤・注射・点滴管理"]}]}
    clean_question(q5, st5, wt5, un5)
    ok.append(("グン剤→与薬", q5["atoms"][0]["tags"], ["#与薬・注射・点滴管理"]))

    # 壊してはいけないもの
    st3, wt3, un3 = {}, {}, {}
    q3 = {"source": "t3", "stem": "Quality of Life の向上",
          "major": "9. エンド・オブ・ライフ＜end-of-life＞にある子どもと家族への看護",
          "atoms": [{"text": "AED と CPAP", "tags": ["#感染予防・標準予防策"]}]}
    clean_question(q3, st3, wt3, un3)
    ok.append(("Quality of Life を壊さない", q3["stem"], "Quality of Life の向上"))
    ok.append(("エンド・オブ・ライフを壊さない", q3["major"],
               "9. エンド・オブ・ライフ＜end-of-life＞にある子どもと家族への看護"))
    ok.append(("正しいタグはそのまま", q3["atoms"][0]["tags"], ["#感染予防・標準予防策"]))

    bad = 0
    for name, got, want in ok:
        good = (got == want)
        print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << 得:%r 期:%r" % (got, want)))
        bad += (0 if good else 1)
    print("\n%d/%d  後始末" % (len(ok) - bad, len(ok)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
