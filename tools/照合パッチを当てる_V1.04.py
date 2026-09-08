# -*- coding: utf-8 -*-
"""看護ルー照合パッチの適用 V1.01（2026-09-06）。

V1.03：image_url_set を追加（別冊の線画を問題に結びつける）。
出典の明記が要るので、image_url_set を使うときは evidence_add も一緒に書くこと。
V1.00の全機能（表・図解は空のときだけ埋める／evidence_add追記／既存尊重）を
そのまま保ち、裁定に基づく【本文修正フィールド】を追加した。
V1.00は削除せず残す（本文修正が不要な運用ではV1.00で足りる）。

V1.01で追加したフィールド（すべて任意）
  replace_all            : [[旧,新],...] を stem/overall_explanation/各atomの
                           text・statement・explanation に全置換（文字化け修正用）
  stem_fix               : stem を置き換える（複数正答問題の「2つ選べ。」化など）
  select_count_fix       : select_count を置き換える。
                           V1.02：question_type も自動で揃える（2以上→multiple／
                           1→single）。アプリの取り込みは question_type と正解数の
                           一致を検査するため、片方だけ直すと問題ごと弾かれる。
  question_type_fix      : question_type を明示指定（自動判定より優先・V1.02）
  atom_fixes             : [{"no":1始まりの肢番号, "explanation":..., "is_correct":...,
                            "text":..., "statement":...}] 指定キーだけ置き換える
  overall_explanation_add: overall_explanation の末尾へ追記（重複追記はしない）
  evidence_drop          : [行の一部,...] を含む evidence の**行を落とす**（V1.04）
                           確度Xや適用範囲外の行を引いてしまったときに、
                           その1行だけを外すため。行ごと落とすので、
                           残りの行（正しく引けているもの）はそのまま残る。

背景（2026-09-06 裁定）
  ・第111回午前問34: 本試験は複数正答（1または3）→「2つ選べ」に改め両方正解
  ・第111回午前問39: 誤答肢の解説を「点滴側（右）から乗り降り」前提へ書き直し
  ・第111回午前問11: stem等の文字化け「大W骨」→「大腿骨」

使い方
  python3 照合パッチを当てる_V1.02.py --in 結合.json --patches 照合/patches --out 出力.json
  python3 照合パッチを当てる_V1.02.py --selftest
"""
import json, io, os, sys, glob


def _rep(s, pairs):
    if not isinstance(s, str):
        return s
    for old, new in pairs:
        s = s.replace(old, new)
    return s


def apply_patches(data, patch_dir):
    patches = {}
    for f in glob.glob(os.path.join(patch_dir, '*.json')):
        p = json.loads(io.open(f, encoding='utf-8-sig').read())
        if p.get('source'):
            patches[p['source']] = p
    stat = {'table': 0, 'mermaid': 0, 'evidence': 0, 'skipped_existing': 0, 'no_patch': 0,
            'replace': 0, 'stem': 0, 'select': 0, 'atom_fix': 0, 'overall_add': 0,
            'evidence_drop': 0}
    for q in data.get('questions', []):
        p = patches.get(q.get('source'))
        if not p:
            stat['no_patch'] += 1
            continue
        # --- V1.00と同じ：表・図解は空のときだけ、出典は追記 ---
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
        # V1.03：別冊の線画を結びつける。既に入っていれば触らない（既存尊重）。
        if p.get('image_url_set') and not q.get('image_url'):
            q['image_url'] = p['image_url_set']
            stat['image'] = stat.get('image', 0) + 1

        if p.get('evidence_add'):
            ev = q.get('evidence') or ''
            if p['evidence_add'] not in ev:
                q['evidence'] = (ev + ('\n' if ev else '') + p['evidence_add'])
                stat['evidence'] += 1
        # --- V1.01追加：本文修正 ---
        # V1.04：evidence から行単位で落とす。
        # 実測：第111回午後問25 は H070（病室100lx）と H072（手術室1,000lx）は
        # 正しく引けていて、Q033（読書時300lx）だけが
        # 「第113回午前問37 専用の行」だった。全部消すのではなく1行だけ外す。
        drops = p.get('evidence_drop') or []
        if drops and isinstance(q.get('evidence'), str):
            lines = q['evidence'].split('\n')
            kept = [ln for ln in lines if not any(d in ln for d in drops)]
            if len(kept) != len(lines):
                q['evidence'] = '\n'.join(kept)
                stat['evidence_drop'] = stat.get('evidence_drop', 0) + 1

        pairs = p.get('replace_all') or []
        if pairs:
            q['stem'] = _rep(q.get('stem'), pairs)
            q['overall_explanation'] = _rep(q.get('overall_explanation'), pairs)
            for a in q.get('atoms', []):
                for k in ('text', 'statement', 'explanation'):
                    a[k] = _rep(a.get(k), pairs)
            stat['replace'] += 1
        if p.get('stem_fix'):
            q['stem'] = p['stem_fix']
            stat['stem'] += 1
        if p.get('select_count_fix') is not None:
            q['select_count'] = p['select_count_fix']
            stat['select'] += 1
            # question_type を置いていかない（V1.02）。
            # 取り込み側は question_type と正解数の一致を見るので、
            # select_count だけ2にすると single のまま残り、その問題は
            # 「正解判定の不一致」で丸ごとスキップされる（実測1問消えた）。
            try:
                n = int(p['select_count_fix'])
            except Exception:
                n = None
            if n is not None and 'question_type' in q:
                q['question_type'] = 'multiple' if n >= 2 else 'single'
        if p.get('question_type_fix'):
            q['question_type'] = p['question_type_fix']
        for fx in (p.get('atom_fixes') or []):
            i = fx.get('no', 0) - 1
            atoms = q.get('atoms', [])
            if 0 <= i < len(atoms):
                for k in ('explanation', 'is_correct', 'text', 'statement'):
                    if k in fx:
                        atoms[i][k] = fx[k]
                stat['atom_fix'] += 1
        if p.get('overall_explanation_add'):
            oe = q.get('overall_explanation') or ''
            if p['overall_explanation_add'] not in oe:
                q['overall_explanation'] = (oe + ('\n' if oe else '') + p['overall_explanation_add'])
                stat['overall_add'] += 1
    return stat


def selftest():
    data = {'questions': [
        {'source': 'S1', 'comparison_table': None, 'mermaid_code': None, 'evidence': None},
        {'source': 'S2', 'comparison_table': '<table>既存</table>', 'mermaid_code': None, 'evidence': '既存ev'},
        {'source': 'S3', 'comparison_table': None, 'mermaid_code': None, 'evidence': None},
        {'source': 'S4', 'stem': '大W骨の問題。', 'select_count': 1, 'question_type': 'single', 'overall_explanation': '説明に大W骨。',
         'atoms': [{'text': '大W骨A', 'statement': '大W骨S', 'explanation': '大W骨E', 'is_correct': False},
                   {'text': 'B', 'statement': 'BS', 'explanation': '旧解説', 'is_correct': False}]},
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
        io.open(os.path.join(tmp, 'p4.json'), 'w', encoding='utf-8').write(json.dumps(
            {'source': 'S4', 'replace_all': [['大W骨', '大腿骨']],
             'stem_fix': '大腿骨の問題。2つ選べ。', 'select_count_fix': 2,
             'atom_fixes': [{'no': 2, 'explanation': '新解説', 'is_correct': True}],
             'overall_explanation_add': '※本試験は複数正答。'}, ensure_ascii=False))
        stat = apply_patches(data, tmp)
        q1, q2, q3, q4 = data['questions']
        # V1.00互換の6観点
        assert q1['comparison_table'] == '<table>新</table>' and q1['mermaid_code'].startswith('flowchart')
        assert q1['evidence'] == '出典X'
        assert q2['comparison_table'] == '<table>既存</table>', '既存を消さない'
        assert q2['evidence'] == '既存ev\n出典Y'
        assert q3['comparison_table'] is None, 'パッチ無しは触らない'
        # V1.01の6観点
        assert q4['stem'] == '大腿骨の問題。2つ選べ。', 'stem_fixはreplace_allの後に勝つ'
        assert q4['select_count'] == 2
        assert q4['question_type'] == 'multiple', 'V1.02：select_count_fixでquestion_typeも揃える'
        assert q4['atoms'][0]['text'] == '大腿骨A' and q4['atoms'][0]['statement'] == '大腿骨S' \
            and q4['atoms'][0]['explanation'] == '大腿骨E', '全置換'
        assert q4['atoms'][1]['explanation'] == '新解説' and q4['atoms'][1]['is_correct'] is True
        assert q4['atoms'][1]['text'] == 'B', 'atom_fixesは指定キーだけ'
        assert q4['overall_explanation'] == '説明に大腿骨。\n※本試験は複数正答。'
        # 冪等性：もう一度当てても追記が重複しない
        stat2 = apply_patches(data, tmp)
        assert q4['overall_explanation'].count('複数正答') == 1 and q2['evidence'].count('出典Y') == 1
        # V1.04：evidence を行単位で落とす。落とす行だけが消え、他は残る。
        q5 = {'source': 'S5',
              'evidence': '標準値表 H070（確度C）：病室=100\n標準値表 Q033：読書=300\n標準値表 H072（確度C）：手術室=1,000',
              'atoms': []}
        d5 = {'questions': [q5]}
        p5 = {'source': 'S5', 'evidence_drop': ['Q033']}
        io.open(os.path.join(tmp, 'S5.json'), 'w', encoding='utf-8').write(
            json.dumps(p5, ensure_ascii=False))
        apply_patches(d5, tmp)
        assert 'Q033' not in q5['evidence'], 'evidence_drop：その行が消える'
        assert 'H070' in q5['evidence'] and 'H072' in q5['evidence'], \
            'evidence_drop：他の行は残る'
        assert q5['evidence'].count('\n') == 1, 'evidence_drop：行数が1つ減る'

        assert stat['replace'] == 1 and stat['stem'] == 1 and stat['select'] == 1 \
            and stat['atom_fix'] == 1 and stat['overall_add'] == 1, stat
        # V1.02：明示指定が自動判定より優先される
        d2 = {'questions': [{'source': 'T1', 'select_count': 1, 'question_type': 'single', 'atoms': []}]}
        tmp2 = tempfile.mkdtemp()
        try:
            io.open(os.path.join(tmp2, 'q.json'), 'w', encoding='utf-8').write(json.dumps(
                {'source': 'T1', 'select_count_fix': 2, 'question_type_fix': 'single'}, ensure_ascii=False))
            apply_patches(d2, tmp2)
            assert d2['questions'][0]['question_type'] == 'single', 'question_type_fixが優先'
        finally:
            shutil.rmtree(tmp2)
        print('selftest OK (V1.00互換6観点＋V1.01 6観点＋V1.02 2観点＋V1.04 3観点＋冪等性)')
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
    print('適用: 表%d・図解%d・出典%d・置換%d・stem%d・選択数%d・肢修正%d・総評追記%d'
          '・evidence行削除%d'
          '（既存尊重スキップ%d／パッチ無し%d問）'
          % (stat['table'], stat['mermaid'], stat['evidence'], stat['replace'], stat['stem'],
             stat['select'], stat['atom_fix'], stat['overall_add'],
             stat.get('evidence_drop', 0),
             stat['skipped_existing'], stat['no_patch']))
    print('出力:', out)
