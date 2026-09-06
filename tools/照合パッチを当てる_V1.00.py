# -*- coding: utf-8 -*-
"""看護ルー照合パッチの適用（2026-09-06）。

照合レーン（Claudeが看護roo!の解説と突合し、事実だけを自分の言葉で
再構成したもの）が 照合/patches/*.json に落とす表・図解を、
結合済みJSON（{"questions":[...]}）へ当てる。

原則
  ・comparison_table / mermaid_code は【空のときだけ】埋める。
    LMが作った表・図解があるなら、そちらを勝手に消さない。
  ・evidence_add があれば evidence の末尾へ追記（表内の数値の出どころを残す）。
  ・conflicts が残っているパッチも当ててよい（conflictsは記録であって拒否理由ではない）。

使い方
  python3 照合パッチを当てる_V1.00.py --in 結合.json --patches 照合/patches --out 出力.json
  python3 照合パッチを当てる_V1.00.py --selftest
"""
import json, io, os, sys, glob


def apply_patches(data, patch_dir):
    patches = {}
    for f in glob.glob(os.path.join(patch_dir, '*.json')):
        p = json.loads(io.open(f, encoding='utf-8-sig').read())
        if p.get('source'):
            patches[p['source']] = p
    stat = {'table': 0, 'mermaid': 0, 'evidence': 0, 'skipped_existing': 0, 'no_patch': 0}
    for q in data.get('questions', []):
        p = patches.get(q.get('source'))
        if not p:
            stat['no_patch'] += 1
            continue
        if p.get('comparison_table'):
            if q.get('comparison_table'):
                stat['skipped_existing'] += 1
            else:
                q['comparison_table'] = p['comparison_table']
                stat['table'] += 1
        if p.get('mermaid_code'):
            if q.get('mermaid_code'):
                stat['skipped_existing'] += 1
            else:
                q['mermaid_code'] = p['mermaid_code']
                stat['mermaid'] += 1
        if p.get('evidence_add'):
            ev = q.get('evidence') or ''
            if p['evidence_add'] not in ev:
                q['evidence'] = (ev + ('\n' if ev else '') + p['evidence_add'])
                stat['evidence'] += 1
    return stat


def selftest():
    data = {'questions': [
        {'source': 'S1', 'comparison_table': None, 'mermaid_code': None, 'evidence': None},
        {'source': 'S2', 'comparison_table': '<table>既存</table>', 'mermaid_code': None, 'evidence': '既存ev'},
        {'source': 'S3', 'comparison_table': None, 'mermaid_code': None, 'evidence': None},
    ]}
    import tempfile, shutil
    tmp = tempfile.mkdtemp()
    try:
        io.open(os.path.join(tmp, 'p1.json'), 'w', encoding='utf-8').write(json.dumps(
            {'source': 'S1', 'comparison_table': '<table>新</table>',
             'mermaid_code': 'flowchart LR\n A-->B', 'evidence_add': '出典X'}, ensure_ascii=False))
        io.open(os.path.join(tmp, 'p2.json'), 'w', encoding='utf-8').write(json.dumps(
            {'source': 'S2', 'comparison_table': '<table>上書きしない</table>',
             'evidence_add': '出典Y'}, ensure_ascii=False))
        stat = apply_patches(data, tmp)
        q1, q2, q3 = data['questions']
        assert q1['comparison_table'] == '<table>新</table>' and q1['mermaid_code'].startswith('flowchart')
        assert q1['evidence'] == '出典X'
        assert q2['comparison_table'] == '<table>既存</table>', '既存を消さない'
        assert q2['evidence'] == '既存ev\n出典Y'
        assert q3['comparison_table'] is None, 'パッチ無しは触らない'
        assert stat == {'table': 1, 'mermaid': 1, 'evidence': 2, 'skipped_existing': 1, 'no_patch': 1}, stat
        print('selftest OK (6観点)')
    finally:
        shutil.rmtree(tmp)


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        selftest(); sys.exit(0)
    src = sys.argv[sys.argv.index('--in') + 1]
    pd = sys.argv[sys.argv.index('--patches') + 1]
    out = sys.argv[sys.argv.index('--out') + 1]
    data = json.loads(io.open(src, encoding='utf-8-sig').read())
    stat = apply_patches(data, pd)
    io.open(out, 'w', encoding='utf-8').write(json.dumps(data, ensure_ascii=False, indent=1))
    print('適用: 表%d・図解%d・出典%d（既存尊重スキップ%d／パッチ無し%d問）'
          % (stat['table'], stat['mermaid'], stat['evidence'],
             stat['skipped_existing'], stat['no_patch']))
    print('出力:', out)
