# -*- coding: utf-8 -*-
"""v5仕上げバッチ → v6 再生成（裁定(b)・2026-09-06）。V1.01。

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
    tsvs = sorted(glob.glob(os.path.join(base, 'out', '検証結果_*.tsv')))
    for t in tsvs:   # 全tsvのNGを集める（古いNGでも、合格記録が無い限り安全側に倒す）
        for line in io.open(t, encoding='utf-8'):
            c = line.rstrip('\n').split('\t')
            if len(c) >= 3 and c[2] == 'NG':
                ng.add(c[0])
    for s in harvested:
        if s not in ng:
            res.add(s)
    if skipped_new:
        print('検証結果tsvより新しい未検証res %d件は収穫済み扱いにしない（次の検証後に再実行を）' % skipped_new)
    return res, len(harvested), len(ng)

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

def emit(base, tmap, skip):
    files = sorted(glob.glob(os.path.join(base, 'batches_finish_v5', 'G*.txt')))
    outdir = os.path.join(base, 'batches_finish_v6')
    os.makedirs(outdir, exist_ok=True)
    groups = []   # (unit, [ (hint, question) ... ]) v5のファイル単位を保つ
    miss = collections.Counter()
    kept = dropped = 0
    for f in files:
        s = io.open(f, encoding='utf-8-sig').read()
        i = s.find('{')
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
            pairs.append((h, q))
            kept += 1
        if pairs:
            groups.append((unit, pairs))
    # 詰め直し（v5のグループを基本単位に、超過時は半割）
    n = 0
    def write(unit, pairs):
        nonlocal n
        body = json.dumps({'hints': [p[0] for p in pairs],
                           'questions': [p[1] for p in pairs]}, ensure_ascii=False)
        text = HEAD_TMPL.format(unit=unit) + body
        if len(text) > LIMIT and len(pairs) > 1:
            mid = len(pairs) // 2
            write(unit, pairs[:mid]); write(unit, pairs[mid:])
            return
        n += 1
        io.open(os.path.join(outdir, 'H%04d.txt' % n), 'w', encoding='utf-8').write(text)
    for unit, pairs in groups:
        write(unit, pairs)
    return n, kept, dropped, miss

def selftest():
    import tempfile, shutil
    tmp = tempfile.mkdtemp()
    try:
        for d in ('batches_finish_v5', 'res_finish', 'out'):
            os.makedirs(os.path.join(tmp, d))
        q = lambda src, unit='在宅看護論／地域・在宅看護論': {
            'unit': unit, 'major': '6. 症状・疾患・治療に応じた地域・在宅看護',
            'medium': 'B. 主な疾患等に応じた在宅', 'source': src, 'stem': 'x' * 50,
            'atoms': [{'original_num': 1, 'is_correct': True, 'text': 'a', 'statement': '',
                       'explanation': '', 'tags': []}]}
        h = lambda src: {'source': src, 'sub_candidates': ['s'], 'tag_candidates': ['#在宅療養支援・訪問看護']}
        io.open(os.path.join(tmp, 'batches_finish_v5', 'G0001.txt'), 'w', encoding='utf-8').write(
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
        skip, nh, nn = passed_sources(tmp)
        assert skip == {'S1'}, skip
        n, kept, dropped, miss = emit(tmp, tmap, skip)
        assert kept == 2 and dropped == 1, (kept, dropped)
        out = io.open(os.path.join(tmp, 'batches_finish_v6', 'H0001.txt'), encoding='utf-8').read()
        assert '#慢性呼吸不全・COPD' in out, 'タグ差し替え'
        assert '自作タグ' in out, 'ヘッダ強化'
        assert 'S1' not in out and 'S2' in out and 'S3' in out
        # 超過分割：長文で2ファイルに割れる
        io.open(os.path.join(tmp, 'batches_finish_v5', 'G0002.txt'), 'w', encoding='utf-8').write(
            '（単元：在宅看護論／地域・在宅看護論）\n' +
            json.dumps({'hints': [h('L1'), h('L2')],
                        'questions': [dict(q('L1'), stem='y' * 2000), dict(q('L2'), stem='z' * 2000)]},
                       ensure_ascii=False))
        n, kept, dropped, miss = emit(tmp, tmap, skip)
        big = glob.glob(os.path.join(tmp, 'batches_finish_v6', 'H*.txt'))
        assert all(len(io.open(f, encoding='utf-8').read()) <= LIMIT for f in big), '3400字超過'
        print('selftest OK (7観点)')
    finally:
        shutil.rmtree(tmp)

if __name__ == '__main__':
    if '--selftest' in sys.argv:
        selftest(); sys.exit(0)
    base = sys.argv[sys.argv.index('--base') + 1] if '--base' in sys.argv else '.'
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tmap = load_map(repo)
    skip, nh, nn = passed_sources(base)
    n, kept, dropped, miss = emit(base, tmap, skip)
    print('v6生成: %dファイル／問題 %d問（合格除外 %d問）' % (n, kept, dropped))
    print('収穫済み %d source／NG記録 %d source／合格除外 %d source' % (nh, nn, len(skip)))
    if miss:
        print('注意:', dict(miss))
