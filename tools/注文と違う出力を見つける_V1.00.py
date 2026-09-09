# -*- coding: utf-8 -*-
"""頼んだ問題と違うものが返ってきていないか調べる V1.00（2026-09-09）

【なぜ要るか】
PADの実行で、**1本目に前回の最後の回答が保存される**ことが分かった。

  実測（2026-09-09）
    27本のバッチ … 最後は I9630.txt「第114回 午後問116」
    → 次の2本のバッチ I10631.txt は「第112回 午前問64」を頼んだのに、
      返ってきた I10631.json の中身は「第114回 午後問116」だった。

    その2本のバッチ … 最後は I11231.txt「第113回 午後問117」
    → 次の1本のバッチ I12232.txt は「第112回 午前問64」を頼んだのに、
      返ってきた I12232.json の中身は「第113回 午後問117」だった。

**1本ずれている。** 生成が終わる前に画面をコピーしているので、
前の回答をそのまま保存してしまう。2本目以降は正しく返ってきている。

その結果、第112回 午前問64 は3回頼んで3回とも作られていない。
しかも画面には何も出ないので、**回したつもりで終わる**。

【この道具がやること】
バッチ（batches_finish_v7/I*.txt）が頼んだ source と、
返ってきた res_finish/I*.json の source を突き合わせ、違うものを一覧に出す。
**ファイルは動かさない。消さない。** 何が起きたかを見せるだけ。

なお、返ってきた中身そのものは（別の問題の答えとして）正しいので、
取り込みで害にはならない。困るのは **頼んだ問題が永久に作られないこと**。

【使い方】
  python3 注文と違う出力を見つける_V1.00.py
  python3 注文と違う出力を見つける_V1.00.py --base <分類フォルダ>
  python3 注文と違う出力を見つける_V1.00.py --lane free   # 体験用の模試だけ見る
  python3 注文と違う出力を見つける_V1.00.py --selftest
"""
import glob
import io
import json
import os
import re
import sys


def nkey(s):
    """突き合わせ用に空白を詰める（検証・結合・v7再生成と同じ規則）。"""
    return re.sub(r'\s+', '', str(s or ''))


def asked(path):
    """バッチ1本が頼んでいるものを集める。

    V1.01：レーンによって「頼んだもの」の呼び名が違う。
      過去問の仕上げ … source（第111回 午前問8）で名指しする
      体験用の作問   … まだ存在しない問題なので source が無い。
                       単元｜大項目｜中項目 で名指しする
    どちらでも突き合わせられるように、source が無ければ分類を鍵にする。
    """
    try:
        t = io.open(path, encoding='utf-8-sig').read()
    except Exception:
        return set()
    src = {nkey(m) for m in re.findall(r'"source"\s*:\s*"([^"]+)"', t)}
    if src:
        return src
    out = set()
    for m in re.finditer(
            r'"unit"\s*:\s*"([^"]+)"\s*,\s*"major"\s*:\s*"([^"]+)"\s*,'
            r'\s*"medium"\s*:\s*"([^"]+)"', t):
        out.add(nkey('|'.join(m.groups())))
    return out


def returned(path):
    """返ってきた1本に入っている source を集める。"""
    try:
        d = json.loads(io.open(path, encoding='utf-8-sig').read())
    except Exception:
        return set()
    qs = d.get('questions') if isinstance(d, dict) else d
    out = set()
    for q in (qs or []):
        if not isinstance(q, dict):
            continue
        if q.get('source'):
            out.add(nkey(q['source']))
        # V1.01：source が無い（体験用の作問）ときは分類を鍵にする
        if q.get('unit') and q.get('medium'):
            out.add(nkey('|'.join([q.get('unit') or '', q.get('major') or '',
                                   q.get('medium') or ''])))
    return out


def check(base, bdir='batches_finish_v7', rdir='res_finish', pat='I*.txt'):
    bdir = os.path.join(base, bdir)
    rdir = os.path.join(base, rdir)
    rows = []
    for b in sorted(glob.glob(os.path.join(bdir, pat))):
        name = os.path.basename(b)[:-4]
        r = os.path.join(rdir, name + '.json')
        want = asked(b)
        if not os.path.exists(r):
            rows.append((name, sorted(want), None, '未処理'))
            continue
        got = returned(r)
        if want and got and not (want & got):
            rows.append((name, sorted(want), sorted(got), '頼んだ問題と違う'))
        elif want - got:
            rows.append((name, sorted(want), sorted(got), '一部が返っていない'))
        else:
            rows.append((name, sorted(want), sorted(got), 'OK'))
    return rows


def main():
    base = sys.argv[sys.argv.index('--base') + 1] if '--base' in sys.argv else '.'
    # V1.01：レーンを選べるようにした。過去問の仕上げと体験用の模試で
    # 入口・出口のフォルダが違う（PADの切替と同じ）。
    lane = sys.argv[sys.argv.index('--lane') + 1] if '--lane' in sys.argv else 'auto'
    LANES = {
        'past': ('batches_finish_v7', 'res_finish', 'I*.txt'),
        'free': ('batches_free',      'res_free',   'M*.txt'),
    }
    if lane == 'auto':
        lanes = [k for k in ('past', 'free')
                 if glob.glob(os.path.join(base, LANES[k][0], LANES[k][2]))]
        if not lanes:
            print('バッチが1本もありません（batches_finish_v7 / batches_free）')
            return
    else:
        lanes = [lane]

    total = bad_all = 0
    shift = False
    for k in lanes:
        bdir, rdir, pat = LANES[k]
        rows = check(base, bdir, rdir, pat)
        if not rows:
            continue
        print('--- %s（%s → %s）' % (k, bdir, rdir))
        bad = [r for r in rows if r[3] != 'OK']
        for name, want, got, why in rows:
            mark = 'ok ' if why == 'OK' else 'NG '
            print('%s %-10s %-10s 頼んだ %s' % (mark, name, why, '／'.join(want) or '(なし)'))
            if why == '頼んだ問題と違う':
                print('%14s返ってきた %s' % ('', '／'.join(got) or '(なし)'))
                shift = True
        print('  %d本中 %d本が注文どおり、%d本が違う／未処理'
              % (len(rows), len(rows) - len(bad), len(bad)))
        total += len(rows)
        bad_all += len(bad)
    print()
    print('合計 %d本中 %d本が違う／未処理' % (total, bad_all))
    if shift:
        print()
        print('※ PADは各実行の1本目に、前回の最後の回答を保存します（実測）。')
        print('  1本だけのバッチは必ず失敗します。**捨て駒を1本目に置いてください。**')
        print('  そのバッチだけ、もう一度流せば取り戻せます。')


def selftest():
    import tempfile
    R = []

    def ok(n, c, d=''):
        R.append((bool(c), n, str(d)))

    with tempfile.TemporaryDirectory() as td:
        b = os.path.join(td, 'batches_finish_v7')
        r = os.path.join(td, 'res_finish')
        os.makedirs(b)
        os.makedirs(r)
        io.open(os.path.join(b, 'I0001.txt'), 'w', encoding='utf-8').write(
            'なにか説明\n{"questions":[{"source":"第112回 午前問64"}]}')
        io.open(os.path.join(b, 'I0002.txt'), 'w', encoding='utf-8').write(
            'なにか説明\n{"questions":[{"source":"第113回 午後問117"}]}')
        io.open(os.path.join(b, 'I0003.txt'), 'w', encoding='utf-8').write(
            'なにか説明\n{"questions":[{"source":"第111回 午前問1"}]}')
        # 1本目は前回の答え（ずれ）／2本目は正しい／3本目は未処理
        io.open(os.path.join(r, 'I0001.json'), 'w', encoding='utf-8').write(
            json.dumps({'questions': [{'source': '第114回 午後問116'}]}, ensure_ascii=False))
        io.open(os.path.join(r, 'I0002.json'), 'w', encoding='utf-8').write(
            json.dumps({'questions': [{'source': '第113回  午後問117'}]}, ensure_ascii=False))
        rows = {x[0]: x for x in check(td)}
        ok('ずれを見つける', rows['I0001'][3] == '頼んだ問題と違う', rows['I0001'])
        ok('空白のゆれは同じものとして扱う', rows['I0002'][3] == 'OK', rows['I0002'])
        ok('未処理を見分ける', rows['I0003'][3] == '未処理', rows['I0003'])
        ok('返ってきた中身を出す', rows['I0001'][2] == ['第114回午後問116'], rows['I0001'])

    bad = [x for x in R if not x[0]]
    for g, n, d in R:
        print(('  ok  ' if g else '  NG  ') + n + ('' if g else '   << ' + d))
    print('\n%d/%d  注文と違う出力を見つける' % (len(R) - len(bad), len(R)))
    return 1 if bad else 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    main()
