# -*- coding: utf-8 -*-
"""仕上げバッチの再生成（v7）。V1.04 — 2026-09-09

【V1.02：作り直したバッチが、PADに1本も流れていなかった】

  PADは「res_finish に同名の .json があればスキップ」する仕組み。
  ところが再生成のたびに I0001.txt から番号を振り直していたので、
  2回目以降は**全部が「もう処理済み」とみなされて飛ばされていた**。

  実測（2026-09-09）：res_finish に I0001〜I5114.json が157本あり、
  作り直した55本は1本も送られなかった。
  利用者からは「PAD実行してもコピペされない」＝「作問が終わった」ように見えていた。

  しかも中身が違うのに同じ名前になる。I0001.txt は
  前回「第115回 午後問105」で、今回は別の問題。取り違えの元になる。

  V1.02 は **res_finish にある番号の続きから振る**。
  すでに I5114.json があるなら、次は I5115.txt から。名前が重複しない。
  種類ごとの区切り（出力なし／必修／その他）は、その中で3つの帯に分ける。

【V1.01（v6版）からの変更：読む場所と書く場所だけ】
  読む   batches_finish_v5/G*.txt  →  **batches_finish_v2/F*.txt**（元のバッチ）
  書く   batches_finish_v6/H*.txt  →  **batches_finish_v7/I*.txt**
  中身の作り方（対応表での引き直し・合格分の除外・3,400字の詰め直し・
  厳守3点のヘッダ）は V1.01 のまま1つも変えていません。

【なぜ v7 が要るか（実測・2026-09-08）】
  v6（H0001〜H0726）は流し切りました。res_finish も H0726.json まであります。
  それでも残っているものが2種類あります。

    ① 出力が1度も返ってこなかった   29問
       送ったのに返らなかったもの。検証にも載らないので、
       検証ツールが作る再投入バッチからは漏れます。
       5肢が48%（全体は15%）、2つ選べが24%（全体は6.7%）と
       **出力が長くなる型に偏っています**。27問が「疾病の成り立ちと回復の促進」。
    ② 検証でNGだった              95問

  v7 はこの両方を集めます。PADは名前順に処理するので、番号で優先順位を付けます。

    I0001〜   出力が1度も返ってこなかった問題
    I1001〜   **必修**のNG（無料版に全部入れるので、ここを先に完璧にする）
    I5001〜   必修以外のNG

  必修を分けたのは、無料版に必修を全部入れると決まったため（2026-09-08）。
  実測：必修250問のうち配布できるのは232問（92.8%）。残り18問。
  そのうち10問は「確度Cの注記漏れ」だけなので、再投入で直る見込み。

【PADでの使い方】
  PADデザイナーの行1「フォルダー内のファイルを取得」を2箇所だけ変えて ▷。
    フォルダー   …\分類_令和5年版\batches_finish_v7
    ファイル フィルター   I*.txt
  res_finish に同名の .json があればスキップされるので、
  途中で止まっても再実行すれば続きから進みます。

--- 以下は V1.01（v6版）の説明 ---

何をするか
  1. batches_finish_v5/G*.txt を読み、各問題の (unit,major,medium) を
     対応表 V1.01 で引き直して tag_candidates を差し替える
  2. すでに収穫済みで検証合格した source を除外する
     （合格＝res_finishに存在 かつ 最新の検証結果tsvにNG行が無い。
       警告のみは合格扱い。収穫済みでもNGなら v6 に入れて再挑戦）
  3. 厳守3点の(2)に「自作タグ禁止・候補1個なら全肢その1個」を明記した
     ヘッダで、≦3,400字に詰め直して batches_finish_v6/H####.txt へ書く

使い方
  python3 仕上げバッチをv6へ再生成する_V1.00.py --base <分類_令和5年版のパス>
  ※ 何度でも実行してよい（実行時点の res_finish／検証結果で除外を計算し直す）
  python3 仕上げバッチをv6へ再生成する_V1.00.py --selftest
"""
import io, json, os, re, sys, glob, collections

LIMIT = 3400

def load_map(repo_dir):
    p = os.path.join(repo_dir, '20260906_中項目→概念タグ_対応表_V1.01.json')
    rows = json.load(io.open(p, encoding='utf-8'))
    return {(r['unit'], r['major'], r['medium']): ['#' + c for c in r['candidates']] for r in rows}

def passed_sources(base):
    """収穫済みかつ検証合格の source 集合。

    V1.00(v7)：4つ目の戻り値として**収穫済みの source 集合**も返す。
    「出力が1度も返ってこなかった問題」と「出力はあったがNGだった問題」を
    分けて番号を振るため（前者を先に流したい）。

    V1.01: 最新の検証結果tsvより新しい res ファイルは「収穫済み」に数えない。
    V1.00は検証後にPADが落とした未検証ファイルを「NG記録なし＝合格」と
    誤除外していた（結合道具と同じ門番の考え方に揃えた）。"""
    res = set()
    harvested = {}
    tsvs = sorted(glob.glob(os.path.join(base, 'out', '検証結果_*.tsv')),
                  key=os.path.getmtime)
    gate = os.path.getmtime(tsvs[-1]) if tsvs else 0
    skipped_new = 0
    for f in glob.glob(os.path.join(base, 'res_finish', '*.json')):
        if os.path.getmtime(f) > gate:
            skipped_new += 1
            continue
        try:
            d = json.loads(io.open(f, encoding='utf-8-sig').read())
        except Exception:
            continue
        qs = d.get('questions', d if isinstance(d, list) else [d])
        for q in (qs if isinstance(qs, list) else [qs]):
            if isinstance(q, dict) and q.get('source'):
                harvested[q['source']] = True
    ng = set()
    # V1.01：**最新の検証結果だけ**を見る。
    #
    # V1.00 は全tsvのNGを合算していた（「古いNGでも安全側に倒す」）。
    # これは v6 の頃、検証が出力ファイルを1本ずつ見ていた時代の作法。
    # いまの検証は source ごとに**新しい方だけ**を見る（V1.15）ので、
    # 最新のtsvが、そのまま「いまの状態」になっている。
    #
    # 合算したままだと、**もう直っている問題まで再投入する**。
    # 実測（2026-09-09）：最新のtsvでは必修のNGは6問。
    # 合算すると22問になり、16問ぶんPADの実行回数が無駄になっていた。
    latest = max(glob.glob(os.path.join(base, 'out', '検証結果_*.tsv')),
                 key=os.path.getmtime, default=None)
    if latest:
        for line in io.open(latest, encoding='utf-8'):
            c = line.rstrip('\n').split('\t')
            if len(c) >= 3 and c[2] == 'NG':
                ng.add(c[0])

    # V1.04（2026-09-09）：**除外リストに載っている問題は再投入しない**。
    # 仕上げ検証（V1.08）はもともとそうしていたが、この道具は tsv の NG 行だけを
    # 見ていたので、裁定ずみの問題を毎回バッチに入れ続けていた。
    #
    # 実測：第111回午前問8 と 第112回午後問7 は3回作り直しても
    # 「確度Cの注記」だけが毎回落ちる。しかも作り直すたびに引く標準値表の行が
    # 増える（3回目で H091 が加わった）ので、待っても終わらない。
    # 照合パッチで注記を足し、結合が verdict を根拠に救う形で決着している。
    # 決着したものを回し続けると、PADの実行回数がそのぶん無駄になる。
    exc = {}
    xp = os.path.join(base, '照合', '除外リスト_V1.00.tsv')
    if os.path.exists(xp):
        for ln in io.open(xp, encoding='utf-8').read().split('\n')[1:]:
            c = ln.split('\t')
            if len(c) >= 3 and c[0].strip():
                exc[c[0].strip()] = (c[1].strip(), c[2].strip())
    dropped = sorted(s for s in ng if s in exc)
    if dropped:
        import collections as _c
        cc = _c.Counter(exc[s][1] for s in dropped)
        print('除外リストで再投入から外した %d問（%s）'
              % (len(dropped), '／'.join('%s %d' % (k, v) for k, v in cc.most_common())))
        for s in dropped:
            print('    %-18s %s（%s）' % (s, exc[s][0], exc[s][1]))
        ng -= set(dropped)
    for s in harvested:
        if s not in ng:
            res.add(s)
    if skipped_new:
        print('検証結果tsvより新しい未検証res %d件は収穫済み扱いにしない（次の検証後に再実行を）' % skipped_new)
    return res, len(harvested), len(ng), set(harvested)

HEAD_TMPL = (
    'ソース「仕上げ指示書」の規則にすべて従い、以下の questions を仕上げてください（単元：{unit}）。\n'
    '出力は ```json で開き ``` で閉じ、フェンスの外には1文字も書かないこと。\n'
    '厳守3点：\n'
    '(1) unit・target・rank・major・medium・source・stem・atoms の text／is_correct／original_num は、'
    '入力の文字列をそのままコピーして返す（言い換え・表記の正規化・誤字修正も禁止）。\n'
    '(2) sub_item と tags は、その問題の sub_candidates／tag_candidates から文字列をそのままコピーして選ぶ'
    '（自分で打ち直さない）。候補に無い文字列・自作タグ（#in_progress 等のプレースホルダを含む）は全て不合格。'
    'tag_candidates が1個しか無い場合は、その1個を該当する全ての肢に使う。\n'
    '(3) 解説に数値・年号・基準値を書いてよいのは、選択肢・問題文・標準値表にある値か、'
    'evidence に「ソース名：値」を1行書いた値だけ。\n'
)

def emit(base, tmap, skip, harvested):
    files = sorted(glob.glob(os.path.join(base, 'batches_finish_v2', 'F*.txt')))
    outdir = os.path.join(base, 'batches_finish_v7')
    os.makedirs(outdir, exist_ok=True)
    # V1.00(v7)：作り直すたびにファイル数が変わるので、前回の残りが混ざる。
    # 実測：241本 → 190本に減ったとき、古い51本がそのまま残って
    # PADが「もう要らない問題」まで流すところだった。
    # 消さずに _to_delete へ退避してから作る（このプロジェクトの決まり）。
    old = sorted(glob.glob(os.path.join(outdir, 'I*.txt')))
    if old:
        import datetime, shutil
        bak = os.path.join(base, '_to_delete',
                           'batches_finish_v7_%s' % datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
        os.makedirs(bak, exist_ok=True)
        for f in old:
            shutil.move(f, os.path.join(bak, os.path.basename(f)))
        print('前回の %d本を %s へ退避しました（消していません）' % (len(old), bak))
    groups = []   # (unit, [ (hint, question) ... ]) v5のファイル単位を保つ
    miss = collections.Counter()
    kept = dropped = 0
    for f in files:
        s = io.open(f, encoding='utf-8-sig').read()
        # V1.00(v7)：元のバッチ（F*.txt）は本文の中にも { が出る（説明文の例など）。
        # find('{') だと途中で拾って壊れるので、行頭の { から読む。
        i = s.find('\n{\n')
        if i < 0:
            i = s.find('{')
        else:
            i += 1
        d = json.loads(s[i:])
        hints = {h['source']: h for h in d['hints']}
        m = re.search(r'（単元：(.+?)）', s)
        unit = m.group(1) if m else d['questions'][0]['unit']
        pairs = []
        for q in d['questions']:
            if q['source'] in skip:
                dropped += 1
                continue
            h = hints.get(q['source'])
            if not h:
                miss['hint欠落'] += 1
                continue
            k = (q['unit'], q['major'], q['medium'])
            if k in tmap:
                h = dict(h); h['tag_candidates'] = tmap[k]
            else:
                miss['対応表に無い分類'] += 1
            if q['source'] not in harvested:
                kind = 'new'
            elif (q.get('unit') or '').startswith('必修'):
                kind = 'hisshu'          # 無料版に全部入れるので先に直す
            else:
                kind = 'ng'
            pairs.append((h, q, kind))
            kept += 1
        if pairs:
            groups.append((unit, pairs))
    # 詰め直し（元のファイル単位を基本に、超過時は半割）
    # V1.00(v7)：出力が1度も返ってこなかったものを**先に**流したいので、
    # 番号を I0001〜（未処理）と I5001〜（NG）で分ける。PADは名前順に処理する。
    # V1.02：res_finish にある I番号の続きから振る（同名スキップを避ける）。
    used = 0
    for f in glob.glob(os.path.join(base, 'res_finish', 'I*.json')):
        m = re.match(r'I(\d+)', os.path.basename(f))
        if m:
            used = max(used, int(m.group(1)))
    # V1.03：**1000本ぶん先へ飛ばす。**
    # V1.02 は「最大＋1」から振っていたが、PADが動いている最中に作り直すと
    # そのぶん追い越されて番号がぶつかる（実測：36本作った直後に14本が衝突）。
    # ぶつかった名前はPADが「処理済み」として飛ばすので、その問題は永久に流れない。
    # 1000本ぶん空ければ、PADが1000本進む前に作り直すかぎり当たらない。
    base_no = used + 1001
    # 3つの帯（出力なし／必修／その他）を、続き番号の中に作る。
    # 1本の帯は最大300本と見ておく（実測の最大は241本）。
    counters = {'new': base_no - 1,
                'hisshu': base_no + 299,
                'ng': base_no + 599}
    if used:
        print('res_finish に I%04d まであるので、I%04d から振ります'
              '（同じ名前だとPADが「処理済み」として飛ばす。'
              'PADが動いている最中の作り直しに備えて1000本ぶん空けています）'
              % (used, base_no))

    def write(unit, pairs, kind):
        body = json.dumps({'hints': [p[0] for p in pairs],
                           'questions': [p[1] for p in pairs]}, ensure_ascii=False)
        text = HEAD_TMPL.format(unit=unit) + body
        if len(text) > LIMIT and len(pairs) > 1:
            mid = len(pairs) // 2
            write(unit, pairs[:mid], kind); write(unit, pairs[mid:], kind)
            return
        counters[kind] += 1
        io.open(os.path.join(outdir, 'I%04d.txt' % counters[kind]),
                'w', encoding='utf-8').write(text)

    for unit, pairs in groups:
        for kind in ('new', 'hisshu', 'ng'):
            sub = [p for p in pairs if p[2] == kind]
            if sub:
                write(unit, sub, kind)
    n = ((counters['new'] - (base_no - 1)) +
         (counters['hisshu'] - (base_no + 299)) +
         (counters['ng'] - (base_no + 599)))
    return n, kept, dropped, miss

def selftest():
    import tempfile, shutil
    tmp = tempfile.mkdtemp()
    try:
        for d in ('batches_finish_v2', 'res_finish', 'out'):
            os.makedirs(os.path.join(tmp, d))
        q = lambda src, unit='在宅看護論／地域・在宅看護論': {
            'unit': unit, 'major': '6. 症状・疾患・治療に応じた地域・在宅看護',
            'medium': 'B. 主な疾患等に応じた在宅', 'source': src, 'stem': 'x' * 50,
            'atoms': [{'original_num': 1, 'is_correct': True, 'text': 'a', 'statement': '',
                       'explanation': '', 'tags': []}]}
        h = lambda src: {'source': src, 'sub_candidates': ['s'], 'tag_candidates': ['#在宅療養支援・訪問看護']}
        io.open(os.path.join(tmp, 'batches_finish_v2', 'F0001.txt'), 'w', encoding='utf-8').write(
            '（単元：在宅看護論／地域・在宅看護論）\n' +
            json.dumps({'hints': [h('S1'), h('S2'), h('S3')],
                        'questions': [q('S1'), q('S2'), q('S3')]}, ensure_ascii=False))
        # S1=収穫済み合格 / S2=収穫済みNG / S3=未収穫
        io.open(os.path.join(tmp, 'res_finish', 'G0001.json'), 'w', encoding='utf-8').write(
            json.dumps({'questions': [q('S1'), q('S2')]}, ensure_ascii=False))
        io.open(os.path.join(tmp, 'out', '検証結果_20260906.tsv'), 'w', encoding='utf-8').write(
            'S2\t4\tNG\tタグ候補外\n')
        tmap = {('在宅看護論／地域・在宅看護論', '6. 症状・疾患・治療に応じた地域・在宅看護',
                 'B. 主な疾患等に応じた在宅'): ['#在宅療養支援・訪問看護', '#慢性呼吸不全・COPD']}
        skip, nh, nn, harvested = passed_sources(tmp)
        assert skip == {'S1'}, skip
        n, kept, dropped, miss = emit(tmp, tmap, skip, harvested)
        assert kept == 2 and dropped == 1, (kept, dropped)
        # V1.00(v7)：番号を種類で分ける。
        #   I0001〜 出力が1度も返ってこなかったもの（S3）
        #   I5001〜 出力はあったがNGだったもの（S2）
        # S1 は合格なのでどちらにも入らない。
        # V1.02：番号は res_finish の続きから振るので、固定の名前で開かない。
        # 「若い番号＝出力なし」「その次＝必修」「いちばん大きい＝その他」の順。
        def _pick(kind):
            fs = sorted(glob.glob(os.path.join(tmp, 'batches_finish_v7', 'I*.txt')))
            texts = [io.open(f, encoding='utf-8').read() for f in fs]
            return texts
        _all = _pick('all')
        newf = [t for t in _all if 'S3' in t]
        newf = newf[0] if newf else ''
        ngf = [t for t in _all if 'S2' in t]
        ngf = ngf[0] if ngf else ''
        # V1.00：必修は I1001〜 に分ける（無料版に全部入れるため）
        io.open(os.path.join(tmp, 'batches_finish_v2', 'F0003.txt'), 'w', encoding='utf-8').write(
            '（単元：必修）\n' +
            json.dumps({'hints': [h('M1')], 'questions': [q('M1', unit='必修')]}, ensure_ascii=False))
        io.open(os.path.join(tmp, 'res_finish', 'G0002.json'), 'w', encoding='utf-8').write(
            json.dumps({'questions': [q('M1', unit='必修')]}, ensure_ascii=False))
        io.open(os.path.join(tmp, 'out', '検証結果_20260906.tsv'), 'w', encoding='utf-8').write(
            'S2\t4\tNG\tタグ候補外\nM1\t7\tNG\t確度C\n')
        skip2, _, _, harv2 = passed_sources(tmp)
        emit(tmp, tmap, skip2, harv2)
        _all2 = [io.open(f, encoding='utf-8').read() for f in
                 sorted(glob.glob(os.path.join(tmp, 'batches_finish_v7', 'I*.txt')))]
        assert any('M1' in t for t in _all2), '必修のNGも出る'
        assert '#慢性呼吸不全・COPD' in newf, 'タグ差し替え'
        assert '自作タグ' in newf, 'ヘッダ強化'
        assert 'S3' in newf and 'S2' not in newf, '未収穫は I0001〜'
        assert 'S2' in ngf and 'S3' not in ngf, 'NGは I5001〜'
        assert 'S1' not in newf and 'S1' not in ngf, '合格分は入れない'
        # V1.02：res_finish に I0009.json があれば、次は I0010 から振る
        io.open(os.path.join(tmp, 'res_finish', 'I0009.json'), 'w', encoding='utf-8').write(
            json.dumps({'questions': []}, ensure_ascii=False))
        skip3, _, _, harv3 = passed_sources(tmp)
        emit(tmp, tmap, skip3, harv3)
        names = sorted(os.path.basename(x) for x in
                       glob.glob(os.path.join(tmp, 'batches_finish_v7', 'I*.txt')))
        assert all(int(re.match(r'I(\d+)', x).group(1)) >= 10 for x in names), \
            ('res_finish の続きから振る', names)
        # 超過分割：長文で2ファイルに割れる
        io.open(os.path.join(tmp, 'batches_finish_v2', 'F0002.txt'), 'w', encoding='utf-8').write(
            '（単元：在宅看護論／地域・在宅看護論）\n' +
            json.dumps({'hints': [h('L1'), h('L2')],
                        'questions': [dict(q('L1'), stem='y' * 2000), dict(q('L2'), stem='z' * 2000)]},
                       ensure_ascii=False))
        n, kept, dropped, miss = emit(tmp, tmap, skip, harvested)
        big = glob.glob(os.path.join(tmp, 'batches_finish_v7', 'I*.txt'))
        assert all(len(io.open(f, encoding='utf-8').read()) <= LIMIT for f in big), '3400字超過'
        print('selftest OK (11観点：V1.01の7つ＋番号の振り分け3つ＋続き番号)')
    finally:
        shutil.rmtree(tmp)

if __name__ == '__main__':
    if '--selftest' in sys.argv:
        selftest(); sys.exit(0)
    base = sys.argv[sys.argv.index('--base') + 1] if '--base' in sys.argv else '.'
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tmap = load_map(repo)
    skip, nh, nn, harvested = passed_sources(base)
    n, kept, dropped, miss = emit(base, tmap, skip, harvested)
    print('v7生成: %dファイル／問題 %d問（合格除外 %d問）' % (n, kept, dropped))
    print('収穫済み %d source／NG記録 %d source／合格除外 %d source' % (nh, nn, len(skip)))
    print('  番号は res_finish の続きから振ってあります（同名スキップを避けるため）。')
    print('  若い番号から順に「出力が無い → 必修のNG → それ以外」です。')
    print('\nPADの行1「フォルダー内のファイルを取得」を2箇所だけ変えて ▷：')
    print('  フォルダー          ...\\分類_令和5年版\\batches_finish_v7')
    print('  ファイル フィルター  I*.txt')
    if miss:
        print('注意:', dict(miss))
