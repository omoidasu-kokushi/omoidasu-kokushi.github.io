#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仕上げ結果（res_finish/*.json）を、アプリ取り込み用の1本のJSONへ結合する道具。

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
import argparse, csv, glob, io, json, os, sys, tempfile, time


def latest_tsv(tsv_dir):
    files = sorted(glob.glob(os.path.join(tsv_dir, '検証結果_*.tsv')))
    return files[-1] if files else None


def load_ng(tsv_path):
    ng = set()
    for row in csv.reader(io.open(tsv_path, encoding='utf-8'), delimiter='\t'):
        if row and row[0] != 'source' and len(row) >= 3 and row[2] == 'NG':
            ng.add(row[0])
    return ng


def merge(src_dir, tsv_dir, out_path, force=False):
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
        mt = os.path.getmtime(f)
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

    kept = {s: q for s, (m, q) in best.items() if s not in ng}
    excluded = sorted(set(best.keys()) & ng)

    units = {}
    for q in kept.values():
        u = q.get('unit') or '（単元なし）'
        units[u] = units.get(u, 0) + 1

    payload = {'questions': [kept[s] for s in sorted(kept.keys())]}
    if out_path:
        io.open(out_path, 'w', encoding='utf-8').write(
            json.dumps(payload, ensure_ascii=False, separators=(',', ':')))

    report = {
        'files': len(files), 'sources': len(best), 'kept': len(kept),
        'excluded_ng': len(excluded), 'replaced_by_newer': replaced,
        'broken_files': broken, 'not_main': sorted(set(not_main)),
        'units': units, 'tsv': os.path.basename(tsv), 'out': out_path,
    }
    return payload, report


def selftest():
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, 'res'); outd = os.path.join(td, 'out')
        os.makedirs(src); os.makedirs(outd)
        q = lambda s, stem: {'source': s, 'pool': 'main', 'unit': 'テスト', 'stem': stem}
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
    print('selftest OK（新旧優先・NG除外・mock除外・BOM・answers落とし・未検証門番・force）')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--src'); ap.add_argument('--tsv-dir'); ap.add_argument('--out')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        selftest(); return
    if not (a.src and a.tsv_dir):
        ap.print_help(); sys.exit(1)
    payload, rep = merge(a.src, a.tsv_dir, a.out, force=a.force)
    print('結合: %d問（NG除外 %d ／ 新しい方で置き換え %d ／ mock混入 %d ／ 破損 %d）'
          % (rep['kept'], rep['excluded_ng'], rep['replaced_by_newer'],
             len(rep['not_main']), len(rep['broken_files'])))
    for u in sorted(rep['units']):
        print('  %s: %d問' % (u, rep['units'][u]))
    if rep['broken_files']:
        print('破損ファイル:', rep['broken_files'][:5])
    if a.out:
        print('出力:', a.out)


if __name__ == '__main__':
    main()
