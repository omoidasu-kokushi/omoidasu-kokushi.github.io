# -*- coding: utf-8 -*-
"""配布物から同梱シードの13列TSVを作る（V1.00・**実行しても questions.js は書き換えません**）

【なぜ】
  いまの同梱シード453問は、旧作問レーンの自由作問。実測すると

    問題文 中央値 75字（本試験の必修は23字）／45字以内は 11%（本試験は9割）
    解説   中央値 1,043字（仕様§4-4 は200〜400字）
    単元   必修308・人体の構造128・疾病の成り立ち17 の3つだけ
    出典   すべて null（AI予想問題）

  対して過去問仕上げの配布物は

    必修228問  問題文 中央値 23字／45字以内 92%／解説 中央値 292字
    出典       第111〜115回の実際の出題

  §14 の実測値（必修の問題文は中央値23字・9割が45字以内）と、
  配布物のほうがぴったり合う。

【この道具がやること】
  配布JSONから、指定した単元だけを13列TSVの行に組み直して**別ファイルに書き出す**。
  questions.js には触りません。差し替えるかどうかは利用者が決めること
  （過去問を同梱してよいかの判断を含みます。**私は決めません**）。

【13列の並び】既存のシードから読み取ったもの
  0 unit / 1 target / 2 rank / 3 major / 4 medium / 5 sub_item / 6 question_type
  7 stem / 8 choices(JSON配列・先頭に丸数字) / 9 correct(0起点のJSON配列)
  10 explanation / 11 tags(肢ごとのJSON配列) / 12 source

【使い方】
  python3 同梱シードを作り直す_V1.00.py --in <配布JSON> --unit 必修 --out <出力.txt>
  python3 同梱シードを作り直す_V1.00.py --in <配布JSON> --all --out <出力.txt>
  python3 同梱シードを作り直す_V1.00.py --selftest
"""
import io, json, os, re, sys

MARU = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'


def to_row(q):
    """1問を13列の1行にする。既存シードと同じ形にそろえる。"""
    atoms = q.get('atoms') or []
    ch, cor, tags = [], [], []
    for i, a in enumerate(atoms):
        n = a.get('original_num') or (i + 1)
        mark = MARU[n - 1] if 1 <= n <= len(MARU) else str(n)
        ch.append('%s %s' % (mark, a.get('text') or ''))
        if a.get('is_correct'):
            cor.append(i)          # 0起点（既存シードもそう）
        tags.append(list(a.get('tags') or []))
    cells = [
        q.get('unit') or '', q.get('target') or '', q.get('rank') or '',
        q.get('major') or '', q.get('medium') or '', q.get('sub_item') or '',
        q.get('question_type') or 'single', q.get('stem') or '',
        json.dumps(ch, ensure_ascii=False), json.dumps(cor),
        q.get('overall_explanation') or '',
        json.dumps(tags, ensure_ascii=False),
        q.get('source') or '',
    ]
    # 改行は既存シードと同じく <br> にする（13列TSVは1問1行なので、
    # 生の改行が入ると行が割れてデータが壊れる）。**直した件数は呼び出し側で数える。**
    fixed = 0
    out = []
    for c in cells:
        if '\n' in c or '\r' in c:
            c = re.sub(r'\r\n|\r|\n', '<br>', c)
            fixed += 1
        if '\t' in c:
            raise ValueError('タブが混ざっています: %r' % c[:40])
        out.append(c)
    return '\t'.join(out), fixed


def js_literal(row):
    """questions.js に貼れる形（JSの文字列リテラル1行）にする。"""
    return '  "' + row.replace('\\', '\\\\').replace('"', '\\"').replace('\t', '\\t') + '",'


def selftest():
    q = {'unit': '必修', 'target': '目標Ⅰ.', 'rank': 'S', 'major': '1. 健康',
         'medium': 'A. 指標', 'sub_item': 'a. 総人口', 'question_type': 'single',
         'stem': '日本の総人口に最も近いのはどれか。',
         'overall_explanation': '<br>2008年がピーク。',
         'source': '第111回 午前問1',
         'atoms': [{'original_num': 1, 'is_correct': False, 'text': '1億4,000万人',
                    'tags': ['#人口動態統計']},
                   {'original_num': 2, 'is_correct': True, 'text': '1億2,500万人',
                    'tags': ['#人口動態統計']}]}
    r, _ = to_row(q)
    c = r.split('\t')
    ok = []
    ok.append(('13列になる', len(c), 13))
    ok.append(('選択肢に丸数字が付く', json.loads(c[8])[0], '① 1億4,000万人'))
    ok.append(('正解は0起点', json.loads(c[9]), [1]))
    ok.append(('タグは肢ごとの配列', len(json.loads(c[11])), 2))
    ok.append(('出典が入る', c[12], '第111回 午前問1'))
    lit = js_literal(r)
    ok.append(('JSリテラルは1行', '\n' in lit, False))
    ok.append(('タブはエスケープされる', '\\t' in lit, True))
    try:
        to_row({'stem': 'あ\tい', 'atoms': []})
        ok.append(('タブ混入を弾く', 'ok', 'NG'))
    except ValueError:
        ok.append(('タブ混入を弾く', 'ok', 'ok'))
    r2, f2 = to_row({'stem': 'あ', 'overall_explanation': '1行目\n2行目', 'atoms': []})
    ok.append(('改行は <br> にする', '1行目<br>2行目' in r2, True))
    ok.append(('直した件数を返す', f2, 1))
    bad = 0
    for name, got, want in ok:
        good = (got == want)
        print(('  ok  ' if good else '  NG  ') + name +
              ('' if good else '   << 得%r 期%r' % (got, want)))
        bad += (0 if good else 1)
    print('\n%d/%d  シード作り直し' % (len(ok) - bad, len(ok)))
    return 1 if bad else 0


def main():
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    def arg(k, d=None):
        return sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
    src = arg('--in'); out = arg('--out')
    if not (src and out):
        print(__doc__); sys.exit(1)
    d = json.loads(io.open(src, encoding='utf-8-sig').read())
    qs = d['questions'] if isinstance(d, dict) else d
    unit = arg('--unit')
    if unit:
        qs = [q for q in qs if (q.get('unit') or '').startswith(unit)]
    rows, skipped, nl = [], [], 0
    for q in qs:
        try:
            r, f = to_row(q)
            rows.append(r); nl += f
        except ValueError as e:
            skipped.append((q.get('source'), str(e)))
    body = '\n'.join(js_literal(r) for r in rows)
    io.open(out, 'w', encoding='utf-8').write(body + '\n')
    n = len(body.encode('utf-8'))
    print('%d問 → %s（%.2f MB）' % (len(rows), out, n / 1e6))
    if nl:
        print('  解説などにあった改行を <br> に直した欄: %d箇所（黙って直しません）' % nl)
    if skipped:
        print('入れられなかった %d問（黙って捨てません）:' % len(skipped))
        for s, why in skipped[:10]:
            print('   ', s, why)
    st = sorted(len(q.get('stem') or '') for q in qs)
    ex = sorted(len(re.sub(r'<[^>]+>', '', q.get('overall_explanation') or '')) for q in qs)
    if st:
        print('  問題文 中央値%d字／45字以内 %d%%' %
              (st[len(st) // 2], 100 * sum(1 for x in st if x <= 45) // len(st)))
        print('  解説   中央値%d字' % ex[len(ex) // 2])
    print('\n※ questions.js は書き換えていません。差し替えるかは利用者が決めること。')


if __name__ == '__main__':
    main()
