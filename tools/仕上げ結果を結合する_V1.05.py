#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仕上げ結果を結合する_V1.05.py

【V1.05 で足したこと】出来上がりに**同じ出典が2つ以上あれば止める**。

  実測（2026-09-09）：出典名の空白が1つと2つ（「第113回 午後問117」と
  「第113回  午後問117」）で別の問題として扱われ、**16問が二重に配布されていた**。
  利用者の画面には同じ問題が2回出る。数だけ見ると 1,212問 に増えて見えるので、
  **多い方へ間違える**という、いちばん気づきにくい壊れ方だった。

  根は掃除 V1.07 で絶った（出典名を入力バッチの表記へそろえる）。
  ここは最後の関門として、空白を詰めた形で数え、1つでも重なっていたら止める。
  黙って通さない。



【V1.04 で足したこと】「作り直しのうち新しい方」の判定を、ファイルの更新時刻から
  **ファイル名の番号**に変えました。掃除が1,157本を20秒で書き直すので更新時刻が
  同じ秒に固まり、環境によって勝つファイルが変わっていました（実測 2026-09-09：
  仕上げ検証が Linux で NG 33問、Windows で NG 98問。差はチェック2だけ）。
  仕上げ検証 V1.25 と同じ規則です。V1.03 の動きはほかに1つも変えていません。


【V1.03 で足したこと】--patches を渡すと、**人が判断して直した問題**は
  検証NGでも配布に残します（V1.02 までの働きは1つも変えていません）。

  いまのパイプラインは 掃除 → 検証 → 結合 → 照合パッチ の順です。
  照合パッチは結合の**後**に当たるので、パッチで直した問題も
  検証NGのままで、結合の段階で落ちます。**直しても永久に配布されません。**

  実測：第111回午後問25（照度）は解説の「読書時300ルクス」だけが問題で、
  パッチを書いて直したのに、配布物に1問も入りませんでした。

  そこで、パッチファイルに **verdict（人がどう判断したか）** が書かれている
  問題は、NGでも残します。verdict の無いパッチ（表や図解を足すだけのもの）は
  対象外です。**「パッチを置けば何でも通る」にしない**ための線引きです。

  残した問題は必ず件数と source を出します。黙って通しません。

--- 以下 V1.02 まで ---
仕上げ結果（res_finish/*.json）を、アプリ取り込み用の1本のJSONへ結合する道具（V1.02）。

V1.02（2026-09-07）：タグの後始末を足す。V1.01 の動きは1つも消していない。

  【なぜ】検証の「タグが候補外」203件を数え直したら、内訳はこうだった。
      #in_progress / #In_progress  122件（89.7%）← 作業中の印が残っている
      英単語化け（#小児 of の生活…）  10件      ← 化け直しで消える
      1対1で寄せられる誤記            2件
      寄せられない                    2件
    つまり **機械で134/136が片づく**。プロンプトを直して投げ直すまでもない。

  【#in_progress を落とす理由（実測）】
    残したまま配ると、アプリの概念ランキングに **「#in_progress」がそのまま載る**。
    「最優先で埋めたいテーマ TOP 3」に出うる。利用者には意味が分からない。
    これは作業中の印であってデータではないので、出す前に落とす。

  【寄せられる誤記は寄せない】
    「#投薬・注射・点滴管理 → #与薬・注射・点滴管理」は意味が変わりうる
    （投薬と与薬は別の語）。2件しかないので **報告に留め、人が決める**。
    直すつもりで壊すほうが害が大きい。

  【化け直しの対象に tags と sub_item を足した】
    V1.01 は本文と分類名だけを見ていた。タグと小項目も化けていた（実測）。

V1.01（2026-09-07）：**結合する前に英単語化けを直す**。

V1.01（2026-09-07）：**結合する前に英単語化けを直す**。
  実測：res_finish 499本に 95件／78問の化けが残っていた。
    「学校感染症」→「school 感染症」
    「体温のセットポイント」→「体温 of のセットポイント」
    「脾静脈は門脈系の血管である」→「脾静脈 is 門脈系の血管である」
    「社会保険制度の基本」→「社会保険制度 of 基本」（分類名まで化けている）
  利用者の目に直接触れる。分類名が化けると出題基準の照合も外れる。

  直すのは **of と is が日本語に挟まれているとき**だけ（tools/助詞の英単語化けを
  直す_V1.00.py と同じ判断）。Quality of Life のような本物の英語は壊さない。
  the / and / to / in / for / by / or / school は置き換え先が文脈で変わるので
  **直さず数えて報告する**。人が見て決める。

  V1.00 の門番（未検証を混ぜない／NGを出さない／pool検査）は1つも外していない。

【元の V1.00 の説明】

契約（§18/§19・claude_20260906_引き継ぎV1.27のマージ方針）
  ・source（例「第111回 午前問26」）単位で1問。同じsourceが複数ファイルにあれば
    **ファイルの更新時刻が新しい方**を採る（解き直し・再投入の結果を優先）
  ・**検証合格分のみ**を出す：最新の out/検証結果_*.tsv でNGだったsourceは除外
  ・門番：検証結果より新しい res ファイルがあれば**結合を拒否**する
    （未検証の結果を黙って混ぜない。先に 20260830_仕上げ検証_V1.05.py を回すこと）
  ・出力は {"questions":[...]}。answers（読み違え検出用）は取り込み時に捨てる契約なので落とす
  ・pool は "main" 以外が混ざっていたら警告して除外（仕上げレーンは過去問=本体のみ）

使い方
  python3 tools/仕上げ結果を結合する_V1.00.py --selftest
  python3 tools/仕上げ結果を結合する_V1.00.py \
      --src "<分類_令和5年版>/res_finish" --tsv-dir "<分類_令和5年版>/out" \
      --out "<分類_令和5年版>/out/20260906_取り込み用_過去問_V1.00.json"
"""
import argparse, csv, glob, io, json, os, re, sys, tempfile, time


def gen_key(path):
    """世代の順番（大きいほど新しい）。V1.04（2026-09-09）。

    【なぜ更新時刻をやめたか】
    掃除（tools_出力の後始末）が res_finish_clean の1,157本を20秒のあいだに
    全部書き直すので、更新時刻がほぼ同じ値に固まる。秒に丸めると20種類しかなく、
    1秒あたり最大61本が同着になる。同着のときどちらが勝つかは OS・
    ファイルシステム・Pythonの版で変わるため、**同じフォルダに同じコマンドを
    打っても環境が違うと結果が変わっていた**（実測 2026-09-09：
    仕上げ検証が Linux で NG 33問、Windows で NG 98問。差はチェック2だけ）。

    ファイル名は F0003.json / G0190.json / H0149.json / I8004.json の形で、
    英字1文字が世代、数字4桁がその世代の連番。生成した順に増える。
    掃除で書き直しても、別のPCへコピーしても変わらない。
    形が違うファイルは必ず番号付きより古い扱いにする。

    仕上げ検証 V1.25 と同じ規則。片方だけ直すと、検証が通した問題を
    結合が別の版で出すことになるので、必ず両方そろえること。
    """
    b = os.path.basename(path)
    m = re.match(r'^([A-Za-z])(\d+)', b)
    if not m:
        return (0, '', 0, b)
    return (1, m.group(1).upper(), int(m.group(2)), b)

# ---------------------------------------------------------------- 英単語化け
# 直し方は **既にある道具をそのまま使う**（tools/助詞の英単語化けを直す_V1.00.py）。
# ここで書き直したら規則が2つになり、必ずずれる（§24「データ契約は二重に持たない」
# と同じ考え）。実際、いったん自前で書いたら
#   「発達段階 of の組合せ」→「発達段階のの組合せ」（の が2つ）
# と壊した。元の道具は「of の」をまとめて1つの「の」に潰す規則を持っている。
import importlib.util as _ilu

_GARBLE_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "助詞の英単語化けを直す_V1.00.py")
_spec = _ilu.spec_from_file_location("_garble", _GARBLE_PY)
_garble = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_garble)

_FIELDS = ["stem", "overall_explanation", "unit", "major", "medium", "target",
           "evidence", "sub_item"]   # V1.02：小項目も化けていた（実測） 
_ATOM_FIELDS = ["text", "statement", "explanation"]


# 元の道具が見張るのは助詞になりうる語（the/and/or/to/in/for/…）だけ。
# 実データには **名詞の化け**（「学校感染症」→「school 感染症」）もあり、
# それは網に掛からなかった。語を1つずつ足していくと必ず取りこぼすので、
# **日本語に挟まれた英単語すべて**を網にする。直さない・数えるだけ。
# **すべて小文字**の英単語だけを網にする。
# 実測：大文字を含む語はほぼ医学略語（AED・ALS・CPAP・HBV・PPE・NSAIDs・pVT…）で、
# 日本語に挟まれて出るのが正常だった。全部を網にしたら21語が偽陽性で埋まり、
# 本物（of・is・school・false・as）が埋もれた。
# 小文字だけに絞ると、日本語の中に素の英単語が出る＝化けを疑う形だけが残る。
_ANY_EN = re.compile(_garble.J + r"\s?\b([a-z][a-z-]{1,20})\b\s?" + _garble.J)
# 小文字でも本文に出てよいもの
_OK_EN = {"of", "dopa", "mmHg", "kcal", "mg", "kg", "cm", "mm", "mL", "dL"}


def _degarble_text(s, stat, watch, src):
    """1つの文字列を直す。直した数を stat に、直さず見張る語を watch に積む。"""
    if not isinstance(s, str) or not s:
        return s
    out, n = _garble.fix_text(s)
    if n:
        stat["fixed"] = stat.get("fixed", 0) + n
    for w in _garble.watch_text(out):
        watch.setdefault(w, []).append(src)
    for m in _ANY_EN.finditer(out):
        w = m.group(1)
        if w in _OK_EN or w in watch:
            continue
        watch.setdefault(w, []).append(src)
    return out


# V1.02：作業中の印。データではないので出す前に落とす。
# 残すと概念ランキングに「#in_progress」がそのまま載る（実測）。
_WORK_TAGS = {"#in_progress", "#inprogress", "#作業中", "#todo", "#wip"}


def clean_tags(q, stat, watch):
    """タグの後始末。落とした数と、残った見慣れないタグを積む。"""
    src = q.get("source") or "?"
    for a in q.get("atoms") or []:
        tags = a.get("tags")
        if not isinstance(tags, list):
            continue
        out = []
        for t in tags:
            if not isinstance(t, str):
                continue
            if t.strip().lower().replace("＿", "_") in _WORK_TAGS:
                stat["work_tag"] = stat.get("work_tag", 0) + 1
                continue
            fixed = _degarble_text(t, stat, watch, src)
            if fixed != t:
                stat["tag_fixed"] = stat.get("tag_fixed", 0) + 1
            if fixed not in out:
                out.append(fixed)
        a["tags"] = out
    return q


def degarble(q, stat, watch):
    """1問ぶん直す。

    元の道具は stem と overall_explanation と肢だけを見るが、ここでは
    **分類名（unit / major / medium / target）と evidence も見る**。
    実測で「社会保険制度 of 基本」「人体の基本的な構造 and 正常な機能」のように
    分類名まで化けており、化けたまま出すと出題基準の照合が外れる。
    """
    src = q.get("source") or "?"
    for f in _FIELDS:
        if f in q:
            q[f] = _degarble_text(q[f], stat, watch, src)
    for a in q.get("atoms") or []:
        for f in _ATOM_FIELDS:
            if f in a:
                a[f] = _degarble_text(a[f], stat, watch, src)
    return q


def latest_tsv(tsv_dir):
    files = sorted(glob.glob(os.path.join(tsv_dir, '検証結果_*.tsv')))
    return files[-1] if files else None


def load_ng(tsv_path):
    ng = set()
    for row in csv.reader(io.open(tsv_path, encoding='utf-8'), delimiter='\t'):
        if row and row[0] != 'source' and len(row) >= 3 and row[2] == 'NG':
            ng.add(row[0])
    return ng


def load_deleted(src_dir):
    """除外リストで「削除」と決まっている問題を読む。

    V1.01：結合が見ていたのは検証結果の NG だけで、**除外リストを見ていなかった**。
    そのため「正解が存在しない（採点除外）」と決めた問題が結合に混ざり、
    取り込みで1問だけ弾かれていた（実測：第112回 午後問35）。
    アプリが黙って落とさず報告する作りなので気づけたが、
    決まっているものは**手前で外す**のが筋。
    """
    base = os.path.dirname(os.path.dirname(os.path.abspath(src_dir)))
    for cand in (os.path.join(os.path.dirname(src_dir), "照合", "除外リスト_V1.00.tsv"),
                 os.path.join(base, "照合", "除外リスト_V1.00.tsv")):
        if os.path.exists(cand):
            out = set()
            for row in csv.reader(io.open(cand, encoding="utf-8"), delimiter="\t"):
                if len(row) >= 2 and row[1] == "削除":
                    out.add(row[0])
            return out, cand
    return set(), None


def load_judged(patch_dir):
    """V1.03：verdict が書かれたパッチの source を集める。

    verdict は「人がこの問題をどう扱うと決めたか」を書く欄。
    ここに文が入っているものだけを「判断済み」とみなす。"""
    out = {}
    if not patch_dir or not os.path.isdir(patch_dir):
        return out
    for f in sorted(glob.glob(os.path.join(patch_dir, '*.json'))):
        try:
            p = json.loads(io.open(f, encoding='utf-8-sig').read())
        except Exception:
            continue
        v = (p.get('verdict') or '').strip()
        s = (p.get('source') or '').strip()
        if v and s:
            out[s] = v
    return out


def merge(src_dir, tsv_dir, out_path, force=False, patch_dir=None):
    tsv = latest_tsv(tsv_dir)
    if not tsv:
        raise SystemExit('検証結果_*.tsv が見つかりません。先に仕上げ検証を回してください: ' + tsv_dir)
    tsv_mtime = os.path.getmtime(tsv)
    ng = load_ng(tsv)

    files = sorted(glob.glob(os.path.join(src_dir, '*.json')))
    if not files:
        raise SystemExit('res の .json がありません: ' + src_dir)
    newer = [f for f in files if os.path.getmtime(f) > tsv_mtime]
    if newer and not force:
        raise SystemExit('検証よりも新しい結果が %d 件あります（例: %s）。\n'
                         '先に仕上げ検証を回し直してから結合してください（--force で強行可）。'
                         % (len(newer), os.path.basename(newer[0])))

    best = {}          # source -> (mtime, question)
    broken, not_main, replaced = [], [], 0
    for f in files:
        try:
            d = json.loads(io.open(f, encoding='utf-8-sig').read())
        except Exception as e:
            broken.append((os.path.basename(f), str(e)[:60]))
            continue
        mt = gen_key(f)
        for q in (d.get('questions') or []):
            src = q.get('source')
            if not src:
                broken.append((os.path.basename(f), 'sourceの無い問題'))
                continue
            if q.get('pool') != 'main':
                not_main.append(src)
                continue
            if src in best:
                if mt > best[src][0]:
                    best[src] = (mt, q); replaced += 1
            else:
                best[src] = (mt, q)

    deleted, del_path = load_deleted(src_dir)
    judged = load_judged(patch_dir)
    # V1.03：NGだが人が判断済み（パッチに verdict がある）ものは残す。
    # ただし **atoms が無いものは残さない**。
    # 実測：選択肢が図の問題（第112回午前問57ほか）は、パッチで図を結びつけても
    # 選択肢のテキストが無いままなので、取り込みが
    # 「stem または atoms がありません」で弾く（4件）。
    # 結合に入れても取り込めないなら、入れる意味がない。
    def _has_atoms(src):
        q = best[src][1]
        return bool(q.get('stem')) and bool(q.get('atoms'))
    rescued = sorted(s for s in best
                     if s in ng and s not in deleted and s in judged and _has_atoms(s))
    skipped_noatom = sorted(s for s in best
                            if s in ng and s not in deleted and s in judged and not _has_atoms(s))
    kept = {s: q for s, (m, q) in best.items()
            if (s not in ng or s in rescued) and s not in deleted}
    excluded = sorted(set(best.keys()) & ng)
    excluded_deleted = sorted(set(best.keys()) & deleted)

    # V1.01：出す直前に英単語化けを直す。
    # 直すのは日本語に挟まれた of / is だけ（助詞に戻すのが一意に決まる）。
    # 残りは数えて報告するだけにする（置き換え先が文脈で変わるため）。
    fixed = {'fixed': 0}
    watch = {}
    for q in kept.values():
        degarble(q, fixed, watch)
        clean_tags(q, fixed, watch)

    units = {}
    for q in kept.values():
        u = q.get('unit') or '（単元なし）'
        units[u] = units.get(u, 0) + 1

    # V1.05：出典の重複を最後に必ず数える。1つでもあれば止める。
    _seen = {}
    for _s in kept:
        _seen.setdefault(re.sub(r'\s+', '', _s), []).append(_s)
    _dup = {k: v for k, v in _seen.items() if len(v) > 1}
    if _dup:
        lines = ['同じ出典の問題が %d件 重なっています。配布すると同じ問題が2回出ます。' % len(_dup)]
        for k, v in list(_dup.items())[:10]:
            lines.append('    %s  ← %s' % (k, ' / '.join(repr(x) for x in v)))
        lines.append('掃除（tools_出力の後始末 V1.07以降）を通してから結合してください。')
        raise SystemExit('\n'.join(lines))

    payload = {'questions': [kept[s] for s in sorted(kept.keys())]}
    if out_path:
        io.open(out_path, 'w', encoding='utf-8').write(
            json.dumps(payload, ensure_ascii=False, separators=(',', ':')))

    report = {
        'files': len(files), 'sources': len(best), 'kept': len(kept),
        'excluded_ng': len(excluded), 'replaced_by_newer': replaced,
        'rescued': rescued, 'rescued_why': {s: judged[s] for s in rescued},
        'rescue_skipped_noatom': skipped_noatom,
        'broken_files': broken, 'not_main': sorted(set(not_main)),
        'units': units, 'tsv': os.path.basename(tsv), 'out': out_path,
        'excluded_deleted': excluded_deleted,
        'deleted_list': os.path.basename(del_path) if del_path else None,
        'degarbled': fixed,
        'watch': {w: sorted(set(v)) for w, v in watch.items()},
    }
    return payload, report


def selftest():
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, 'res'); outd = os.path.join(td, 'out')
        os.makedirs(src); os.makedirs(outd)
        # V1.03：救済の条件に「stem と atoms がある」を足したので、
        # テストの問題にも atoms を持たせる（実データは必ず持っている）。
        q = lambda s, stem: {'source': s, 'pool': 'main', 'unit': 'テスト', 'stem': stem,
                             'atoms': [{'original_num': 1, 'is_correct': True, 'text': 'a'}]}
        # 旧い方（BOM付き）と新しい方：新しい方が勝つこと
        io.open(os.path.join(src, 'A.json'), 'w', encoding='utf-8-sig').write(
            json.dumps({'questions': [q('S1', '旧'), q('S2', 'x')],
                        'answers': [{'source': 'S1'}]}, ensure_ascii=False))
        time.sleep(0.05)
        io.open(os.path.join(src, 'B.json'), 'w', encoding='utf-8').write(
            json.dumps({'questions': [q('S1', '新'), q('S3', 'y'),
                                      {'source': 'S4', 'pool': 'mock', 'unit': 'テスト', 'stem': 'm'}]},
                       ensure_ascii=False))
        time.sleep(0.05)
        io.open(os.path.join(outd, '検証結果_20260906.tsv'), 'w', encoding='utf-8').write(
            'source\tチェック\t重大度\t内容\nS3\t6\tNG\tダミー\nS2\t9\t警告\tダミー\n')
        payload, rep = merge(src, outd, None)
        srcs = {x['source']: x for x in payload['questions']}
        assert set(srcs) == {'S1', 'S2'}, srcs            # S3=NG除外 / S4=mock除外 / S2の警告は残す
        assert srcs['S1']['stem'] == '新', srcs            # 新しいmtimeが勝つ
        assert 'answers' not in payload
        assert rep['excluded_ng'] == 1 and rep['not_main'] == ['S4'] and rep['replaced_by_newer'] == 1
        # 門番：検証より新しい res があれば拒否
        time.sleep(0.05)
        io.open(os.path.join(src, 'C.json'), 'w', encoding='utf-8').write(
            json.dumps({'questions': [q('S9', 'z')]}, ensure_ascii=False))
        try:
            merge(src, outd, None); assert False, '門番が働いていない'
        except SystemExit as e:
            assert '新しい結果' in str(e)
        payload2, _ = merge(src, outd, None, force=True)
        assert 'S9' in {x['source'] for x in payload2['questions']}
        # V1.03：verdict のあるパッチがある問題は、NGでも残す。
        #        verdict の無いパッチ（表を足すだけ等）では残さない。
        pd2 = os.path.join(td, 'patches'); os.makedirs(pd2)
        io.open(os.path.join(pd2, 'a.json'), 'w', encoding='utf-8').write(
            json.dumps({'source': 'S3', 'verdict': '人が見て通すと決めた'}, ensure_ascii=False))
        io.open(os.path.join(pd2, 'b.json'), 'w', encoding='utf-8').write(
            json.dumps({'source': 'S9', 'comparison_table': '<table>表だけ</table>'},
                       ensure_ascii=False))
        j = load_judged(pd2)
        assert j == {'S3': '人が見て通すと決めた'}, ('verdictのあるものだけ拾う', j)
        payload3, rep3 = merge(src, outd, None, force=True, patch_dir=pd2)
        srcs3 = {x['source'] for x in payload3['questions']}
        assert 'S3' in srcs3, 'verdictがあればNGでも残す'
        assert rep3['rescued'] == ['S3'], rep3['rescued']
        assert rep3['rescued_why']['S3'] == '人が見て通すと決めた'
        payload4, _ = merge(src, outd, None, force=True)   # --patches 無しなら従来どおり
        assert 'S3' not in {x['source'] for x in payload4['questions']}, 'パッチ無しならNGは落ちる'

        # 選択肢が無い問題は、verdict があっても残さない（取り込みが弾くため）
        io.open(os.path.join(src, 'Z.json'), 'w', encoding='utf-8').write(
            json.dumps({'questions': [{'source': 'S3', 'pool': 'main', 'unit': 'テスト',
                                       'stem': '図だけの問題', 'atoms': []}]},
                       ensure_ascii=False))
        payload5, rep5 = merge(src, outd, None, force=True, patch_dir=pd2)
        assert 'S3' not in {x['source'] for x in payload5['questions']}, '選択肢が無ければ残さない'
        assert rep5['rescue_skipped_noatom'] == ['S3'], rep5['rescue_skipped_noatom']

    # --- V1.04：更新時刻が同じでも、番号の大きい方が勝つ ---
    #
    # これが直したかった不具合そのもの。掃除が全ファイルを同じ秒に書き直すので、
    # 更新時刻では順番が決まらない。ここでは **わざと逆順に書いて**、
    # 更新時刻だけを見ていたら古い方（H0002）が勝ってしまう状況を作る。
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, 'res'); outd = os.path.join(td, 'out')
        os.makedirs(src); os.makedirs(outd)
        q = lambda s, stem: {'source': s, 'pool': 'main', 'unit': 'テスト', 'stem': stem,
                             'atoms': [{'original_num': 1, 'is_correct': True, 'text': 'a'}]}
        io.open(os.path.join(src, 'H0010.json'), 'w', encoding='utf-8').write(
            json.dumps({'questions': [q('S1', '新しい方')]}, ensure_ascii=False))
        time.sleep(0.05)
        io.open(os.path.join(src, 'H0002.json'), 'w', encoding='utf-8').write(
            json.dumps({'questions': [q('S1', '古い方')]}, ensure_ascii=False))
        # 念のため更新時刻を完全に揃える（掃除の実態に近い）
        t0 = os.path.getmtime(os.path.join(src, 'H0002.json'))
        os.utime(os.path.join(src, 'H0010.json'), (t0, t0))
        time.sleep(0.05)
        io.open(os.path.join(outd, '検証結果_20260909.tsv'), 'w', encoding='utf-8').write(
            'source\tチェック\t重大度\t内容\n')
        payload6, _ = merge(src, outd, None, force=True)
        got = {x['source']: x['stem'] for x in payload6['questions']}
        assert got['S1'] == '新しい方', ('番号の大きい方が勝つこと', got)
        # 世代（英字）は数字より先に効く：I0001 は H9999 より新しい
        assert gen_key('/x/I0001.json') > gen_key('/x/H9999.json')
        assert gen_key('/x/H0010.json') > gen_key('/x/H0002.json')
        assert gen_key('/x/へんな名前.json') < gen_key('/x/F0001.json')

    print('selftest OK（新旧優先・NG除外・mock除外・BOM・answers落とし・未検証門番・force'
          '・V1.03の判断済み救済6観点・V1.04の番号順4観点）')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--src'); ap.add_argument('--tsv-dir'); ap.add_argument('--out')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--patches', help='照合パッチのフォルダ。verdict のあるものはNGでも残す（V1.03）')
    a = ap.parse_args()
    if a.selftest:
        selftest(); return
    if not (a.src and a.tsv_dir):
        ap.print_help(); sys.exit(1)
    payload, rep = merge(a.src, a.tsv_dir, a.out, force=a.force, patch_dir=a.patches)
    print('結合: %d問（NG除外 %d ／ 新しい方で置き換え %d ／ mock混入 %d ／ 破損 %d）'
          % (rep['kept'], rep['excluded_ng'], rep['replaced_by_newer'],
             len(rep['not_main']), len(rep['broken_files'])))
    if rep.get('rescue_skipped_noatom'):
        print('パッチはあるが選択肢が無いので残さなかった %d問（取り込みが弾くため）: %s'
              % (len(rep['rescue_skipped_noatom']),
                 ' / '.join(rep['rescue_skipped_noatom'])))
    if rep.get('rescued'):
        print('人が判断済みなのでNGでも残した %d問（パッチの verdict を根拠に）:' % len(rep['rescued']))
        for s in rep['rescued']:
            print('   %-18s %s' % (s, rep['rescued_why'][s][:60]))
    for u in sorted(rep['units']):
        print('  %s: %d問' % (u, rep['units'][u]))
    if rep['broken_files']:
        print('破損ファイル:', rep['broken_files'][:5])
    # V1.01：化けを何件直したか／直さず見張っている語を必ず出す。黙って直さない。
    if rep['excluded_deleted']:
        print('除外リストで「削除」と決まっている %d問を外しました（%s）:'
              % (len(rep['excluded_deleted']), rep['deleted_list']))
        for s in rep['excluded_deleted']:
            print('  ', s)
    print('英単語化け：直した %d件（うちタグ %d件）'
          % (rep['degarbled'].get('fixed', 0), rep['degarbled'].get('tag_fixed', 0)))
    print('作業中の印（#in_progress など）を落とした: %d件'
          % rep['degarbled'].get('work_tag', 0))
    if rep['watch']:
        print('直さず見張っている語（人が見て決める）:')
        for w in sorted(rep['watch'], key=lambda x: -len(rep['watch'][x])):
            qs = rep['watch'][w]
            print('  %-12s %2d問  例: %s' % (w, len(qs), ' / '.join(qs[:3])))
    else:
        print('直さず見張っている語: なし')
    if a.out:
        print('出力:', a.out)


if __name__ == '__main__':
    main()
