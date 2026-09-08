# -*- coding: utf-8 -*-
"""配布物から同梱シードを作る V1.01（**実行しても questions.js は書き換えません**）

V1.00 は消していません。13列TSVが要る場面ではそのまま使えます。

【V1.01 で変えたこと：出力をTSVからJSONにした】
  V1.00 は13列TSVを出し、12列目に source を置いていました。ところが
  storage.js の取り込みは

      cells[12] = is_splittable（分割してよいか）
      cells[13] = source（出典）
      cells[14] = image_url（別冊の画像）

  と読みます。**列の意味が1つずれていた**ので、V1.00 で作ったシードを
  取り込むと 249問すべてが

      source        → null（画面には「AI予想問題」と出る）
      is_splittable → 「第111回 午前問1」が分割可否として読めない → 警告249件

  になりました（実測）。過去問を同梱する意味がほぼ消えます。

  列を14に増やせば source と画像は乗りますが、それでも

      comparison_table（比較表）17問
      mermaid_code（図解）2問

  は列が無いので落ちます。TSVは §18 のスキーマの一部しか運べません。

  そこで V1.01 は **§18 のJSONをそのまま出します**。取り込み側は
  先頭が `[` か `{` ならJSONとして読む（storage.js の形式判定）ので、
  同梱シードの受け渡しに使っている変数へそのまま入れられます。
  列のズレという事故の種そのものが無くなります。

【この道具がやること】
  配布JSONから、指定した単元だけを取り出し、**questions.js に貼れる形**
  （1問1行のJS文字列配列。join("\\n") で1本のJSONになる）で別ファイルに
  書き出します。questions.js には触りません。差し替えるかどうかは
  利用者が決めることです（過去問を同梱してよいかの判断を含みます）。

【使い方】
  python3 同梱シードを作り直す_V1.01.py --in <配布JSON> --unit 必修 --out <出力.txt>
  python3 同梱シードを作り直す_V1.01.py --in <配布JSON> --all --out <出力.txt>
  python3 同梱シードを作り直す_V1.01.py --selftest
"""
import io, json, os, statistics, sys

# アプリの取り込みが読む鍵だけを残す（§18）。余分な内部鍵は落とす。
KEEP = [
    'source', 'unit', 'target', 'rank', 'major', 'medium', 'sub_item',
    'num_code', 'unit_no', 'question_type', 'select_count', 'stem',
    'overall_explanation', 'comparison_table', 'mermaid_code',
    'evidence', 'pool', 'variant', 'origin_key', 'is_splittable',
    'image_url', 'case_key', 'case_no', 'numeric_answer', 'atoms',
]
ATOM_KEEP = ['text', 'statement', 'explanation', 'is_correct', 'tags', 'original_num']


def slim(q):
    """取り込みが見る鍵だけにする。null と空配列は落として軽くする。"""
    out = {}
    for k in KEEP:
        if k == 'atoms':
            continue
        v = q.get(k)
        if v is None or v == '' or v == []:
            continue
        out[k] = v
    atoms = []
    for a in (q.get('atoms') or []):
        b = {}
        for k in ATOM_KEEP:
            v = a.get(k)
            if v is None or v == '' or v == []:
                continue
            b[k] = v
        atoms.append(b)
    out['atoms'] = atoms
    return out


def build(qs):
    """questions.js に貼れる行の並びを返す（先頭・末尾の器を含む）。"""
    lines = ['  \'{"questions":[\',']
    for i, q in enumerate(qs):
        body = json.dumps(slim(q), ensure_ascii=False, separators=(',', ':'))
        if i < len(qs) - 1:
            body += ','
        lines.append('  ' + json.dumps(body, ensure_ascii=False) + ',')
    lines.append('  \']}\'')
    return lines


def stats(qs):
    stems = [len(q.get('stem') or '') for q in qs]
    exps = [len(q.get('overall_explanation') or '') for q in qs]
    return {
        'n': len(qs),
        'stem_median': statistics.median(stems) if stems else 0,
        'stem_le45': (sum(1 for x in stems if x <= 45) / len(stems)) if stems else 0,
        'exp_median': statistics.median(exps) if exps else 0,
        'with_source': sum(1 for q in qs if q.get('source')),
        'with_table': sum(1 for q in qs if q.get('comparison_table')),
        'with_mermaid': sum(1 for q in qs if q.get('mermaid_code')),
        'with_image': sum(1 for q in qs if q.get('image_url')),
        'splittable': sum(1 for q in qs if q.get('is_splittable')),
    }


def selftest():
    R = []

    def ok(name, cond, detail=''):
        R.append((bool(cond), name, str(detail)))

    q = {'source': '第111回 午前問1', 'unit': '必修', 'rank': 'S', 'stem': 'あ',
         'question_type': 'single', 'pool': 'main', 'is_splittable': True,
         'comparison_table': '<table></table>', 'mermaid_code': None,
         'image_url': None, 'variant': None, 'kr_id': 999,
         'atoms': [{'text': 'ア', 'is_correct': True, 'tags': ['#x'],
                    'explanation': 'せつめい', 'verify_status': 'json'}]}
    s = slim(q)
    ok('出典を落とさない', s.get('source') == '第111回 午前問1')
    ok('分割可否を落とさない', s.get('is_splittable') is True)
    ok('比較表を落とさない', s.get('comparison_table') == '<table></table>')
    ok('null は落とす', 'mermaid_code' not in s and 'variant' not in s)
    ok('取り込みが見ない鍵は落とす', 'kr_id' not in s)
    ok('肢の中身は残す', s['atoms'][0]['explanation'] == 'せつめい')
    ok('肢の内部鍵は落とす', 'verify_status' not in s['atoms'][0])

    lines = build([q, dict(q, source='第111回 午前問2')])
    text = '\n'.join(lines)
    ok('器で挟んである', text.startswith('  \'{"questions":['))
    # JS の join を真似て、実際にJSONとして読めるか
    parts = []
    for ln in lines:
        t = ln.strip()
        if t.endswith(','):
            t = t[:-1]
        parts.append(json.loads('"' + t[1:-1].replace('"', '\\"') + '"')
                     if t.startswith("'") else json.loads(t))
    d = json.loads('\n'.join(parts))
    ok('つなぐとJSONとして読める', len(d['questions']) == 2, json.dumps(d)[:80])
    ok('1問1行になっている', len(lines) == 4, len(lines))

    bad = [x for x in R if not x[0]]
    for good, name, detail in R:
        print(('  ok  ' if good else '  NG  ') + name + ('' if good else '   << ' + detail))
    print('\n%d/%d  シード作り直し V1.01' % (len(R) - len(bad), len(R)))
    return 1 if bad else 0


def main():
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    src = sys.argv[sys.argv.index('--in') + 1]
    out = sys.argv[sys.argv.index('--out') + 1]
    unit = None if '--all' in sys.argv else sys.argv[sys.argv.index('--unit') + 1]
    d = json.load(io.open(src, encoding='utf-8-sig'))
    qs = d['questions'] if isinstance(d, dict) else d
    if unit:
        qs = [q for q in qs if q.get('unit') == unit]
    qs.sort(key=lambda q: (q.get('source') or ''))
    lines = build(qs)
    io.open(out, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    st = stats(qs)
    mb = os.path.getsize(out) / 1024 / 1024
    print('%d問 → %s（%.2f MB）' % (st['n'], out, mb))
    print('  出典あり %d / 比較表 %d / 図解 %d / 別冊画像 %d / 分割可 %d'
          % (st['with_source'], st['with_table'], st['with_mermaid'],
             st['with_image'], st['splittable']))
    print('  問題文 中央値%d字／45字以内 %d%%' % (st['stem_median'], round(100 * st['stem_le45'])))
    print('  解説   中央値%d字' % st['exp_median'])
    print('')
    print('※ questions.js は書き換えていません。差し替えるかは利用者が決めること。')


if __name__ == '__main__':
    main()
