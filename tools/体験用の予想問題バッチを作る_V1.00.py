# -*- coding: utf-8 -*-
"""体験用の予想問題（無料版の模試）のPADバッチを作る V1.00（2026-09-10）

【これは何か】
  無料版でプチ模試（30問）とハーフ模試（60問）を1回ずつ受けてもらう。
  その中身になる予想問題を、PADで無人生成するためのバッチを作る。

    free_a … プチ模試用   30問
    free_b … ハーフ模試用 60問

  規則の正は 20260909_体験用の予想問題_作問指示_V1.00.txt と
  20260828_作問_共通仕様ソース_V2.13.txt。この道具はそこに書かれた条件を
  **機械で割り当てて、注文書の形にする**だけ。

【なぜ割り当てをこちらでやるか】
  今日いちばん高くついた失敗が「AIに数えさせる」ことだった。
  確度Cの注記は3回作り直しても毎回落ちたし、単元の配分や中項目の重複を
  AIに数えさせると、そのつど揺れる。

  **導出できるものは導出する。** 単元ごとの問題数・中項目の割り当て・
  ランクの配分・出題形式の配分は、全部こちらで決められる。
  AIに残すのは「その中項目で、指定された形の問題を1問書く」だけにする。

【ランクは中項目から決まる】
  アプリは `RANK_BY_MEDIUM`（218件）で中項目からランクを引く（storage.js の
  rankFor）。だから**ランクを指定するのではなく、狙ったランクになる中項目を選ぶ**。
  表に無い中項目は B。指示書の目安（S3割・A5割・B2割）は、この選び方で満たす。

【出力】
  batches_free/M0001.txt …  1本につき最大3問（共通仕様ソース §12）
  out/体験用の割り当て_<日付>.tsv  何をどこに割り当てたかの一覧（人が見る用）

  PADのフローは**入口と出口のフォルダを変えるだけ**で流せる形にしてある。
  過去問の仕上げと同じ「1ファイル投入 → 返答を同名.jsonで保存」。

【使い方】
  python3 体験用の予想問題バッチを作る_V1.00.py --base <分類フォルダ>
  python3 体験用の予想問題バッチを作る_V1.00.py --selftest
"""
import datetime
import glob
import io
import json
import os
import random
import re
import shutil
import sys

# 指示書の単元別問題数（実測を按分したもの）
QUOTA = {
    'free_a': {'必修': 6, '成人看護学': 4, '老年看護学': 3, '小児看護学': 2,
               '基礎看護学': 2, '母性看護学': 2, '疾病の成り立ちと回復の促進': 2,
               '精神看護学': 2, '在宅看護論／地域・在宅看護論': 2,
               '人体の構造と機能': 2, '健康支援と社会保障制度': 2,
               '看護の統合と実践': 1},
    'free_b': {'必修': 14, '成人看護学': 8, '老年看護学': 5, '小児看護学': 5,
               '基礎看護学': 4, '母性看護学': 4, '疾病の成り立ちと回復の促進': 4,
               '精神看護学': 4, '在宅看護論／地域・在宅看護論': 3,
               '人体の構造と機能': 3, '健康支援と社会保障制度': 3,
               '看護の統合と実践': 3},
}

# 出題形式の配分（指示書 §13 の実測配分）
#   4肢1つ選べ 8割 ／ 5肢1つ選べ 1割 ／ 5肢2つ選べ 1割（必修では作らない）
FORMS = {'free_a': {'four': 24, 'five': 3, 'multi': 3},
         'free_b': {'four': 48, 'five': 6, 'multi': 6}}

# ランクの目安（指示書）。中項目の選び方でこの比率に寄せる。
RANK_MIX = [('S', 0.3), ('A', 0.5), ('B', 0.2)]

PER_FILE = 3          # 1本の出力は最大3問（共通仕様ソース §12）


def load_master(base):
    """questions.js から中項目465件とランク表を読む。

    正はアプリ側（§24：データ契約を二重に持たない）。ここでは読むだけ。
    ランク表は `[ "鍵", ... ].forEach(function (k) { m[k] = "S"; });` の形で
    S/A/C の3ブロックに分かれている（B は既定なので書かれていない）。
    1行1鍵ではないので、**ブロックごとに鍵を拾ってから**ランクを付ける。
    """
    cands = [os.path.expanduser('~/omo/questions.js'),
             os.path.join(base, '..', '..', 'omo', 'questions.js'),
             os.path.join(base, 'questions.js')]
    src = None
    for p in cands:
        if os.path.exists(p):
            src = io.open(p, encoding='utf-8').read()
            break
    if src is None:
        raise SystemExit('questions.js が見つかりません。探した場所：\n  ' +
                         '\n  '.join(cands))

    i = src.index('TAXONOMY_MASTER')
    j = src.find(']];', i)
    tax = []
    for m in re.finditer(r'\[\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\]',
                         src[i:j + 3]):
        tax.append((m.group(1), m.group(2), m.group(3)))

    rank = {}
    rb_start = src.index('RANK_BY_MEDIUM')
    rb = src[rb_start:src.index('\n})();', rb_start) if '\n})();' in src[rb_start:rb_start + 200000]
                                                   else rb_start + 200000]
    for m in re.finditer(r'\[([^\[\]]*?)\]\.forEach\(function \(k\) \{ m\[k\] = "([SAC])"; \}\);',
                         rb, re.S):
        r = m.group(2)
        for k in re.findall(r'"([^"]+\|[^"]+\|[^"]+)"', m.group(1)):
            rank[k] = r
    return tax, rank


def rank_of(t, rank):
    """中項目のランク。表に無ければ B（アプリの rankFor と同じ規則）。"""
    return rank.get('|'.join(t), 'B')


def pick_media(tax, rank, quota, used, seed):
    """単元ごとに、狙ったランク配分になるよう中項目を選ぶ。

    used に入っている中項目は使わない（free_a と free_b で重ねないため）。
    足りなければランクの縛りを外して埋める——**問題数を減らさない**。
    体験用の球が足りないほうが、ランクが偏るより悪い。"""
    rng = random.Random(seed)
    out = []
    for unit in sorted(quota):
        need = quota[unit]
        # 重なりは **(単元, 中項目名)** でも避ける。大項目が違っても、
        # 利用者から見れば「さっきと同じ中項目」に見えるため。
        seen_names = set((u, m) for (u, _mj, m) in used)
        pool = [t for t in tax
                if t[0] == unit and t not in used and (t[0], t[2]) not in seen_names]
        by = {'S': [], 'A': [], 'B': [], 'C': []}
        for t in pool:
            by[rank_of(t, rank)].append(t)
        for k in by:
            rng.shuffle(by[k])
        want = []
        for r, share in RANK_MIX:
            want += [r] * int(round(need * share))
        while len(want) < need:
            want.append('A')
        want = want[:need]
        def take(lists):
            """まだ使っていない中項目を1つ取る。

            by[...] は単元の頭で1回だけ作るので、取ったあとに
            seen_names へ足しても、**別のランクの束に同じ名前が残っている**。
            実測：この取りこぼしで free_a と free_b に同じ中項目が4件重なった。
            取り出すたびに見張る。"""
            for lst in lists:
                while lst:
                    t = lst.pop(0)
                    if t not in used and (t[0], t[2]) not in seen_names:
                        return t
            return None

        got = []
        for r in want:
            t = take([by[r], by['A'], by['S'], by['B'], by['C']])
            if t is None:
                break
            got.append(t)
            used.add(t)
            seen_names.add((t[0], t[2]))
        # 足りない（その単元の中項目を使い切った）ときは、残りから詰める
        rest = [t for t in pool if t not in used and (t[0], t[2]) not in seen_names]
        rng.shuffle(rest)
        while len(got) < need and rest:
            t = rest.pop(0)
            got.append(t)
            used.add(t)
        out += got
    return out


def assign_forms(items, forms, seed):
    """出題形式を割り当てる。**必修には「2つ選べ」を作らない**（指示書 E）。"""
    rng = random.Random(seed + 1)
    order = list(range(len(items)))
    rng.shuffle(order)
    plan = ['four'] * len(items)
    # 先に「2つ選べ」を必修以外へ配る
    n_multi = forms['multi']
    for i in order:
        if n_multi <= 0:
            break
        if items[i][0] != '必修':
            plan[i] = 'multi'
            n_multi -= 1
    n_five = forms['five']
    for i in order:
        if n_five <= 0:
            break
        if plan[i] == 'four':
            plan[i] = 'five'
            n_five -= 1
    return plan


FORM_TEXT = {
    'four':  {'select_count': 1, 'atoms': 4, 'label': '4肢から1つ選べ'},
    'five':  {'select_count': 1, 'atoms': 5, 'label': '5肢から1つ選べ'},
    'multi': {'select_count': 2, 'atoms': 5, 'label': '5肢から2つ選べ'},
}

HEAD = '''ソース「作問_共通仕様ソース」と「体験用の予想問題_作問指示」の規則にすべて従い、
下の orders のとおりに新しい予想問題を作ってください（{n}問）。
出力は ```json で開き ``` で閉じ、フェンスの外には1文字も書かないこと。

厳守5点：
(1) orders の unit・major・medium・rank・variant は、**そのままコピーして返す**。
    自分で選び直さない。言い換え・表記の正規化もしない。
(2) pool は全問 "mock"。source は null。origin_key も null。
    （pool を書き忘れると本体プールに混ざり、過去問と一緒に出題される）
(3) question_type と select_count と肢の数は、orders の指定どおりにする。
    select_count が 2 のときだけ question_type は "multiple"、それ以外は "single"。
(4) sub_item と tags は、その注文の sub_candidates／tag_candidates から
    文字列をそのままコピーして選ぶ。候補に無い文字列・自作タグは全て不合格。
(5) 解説に数値・年号・基準値を書いてよいのは、選択肢・問題文・標準値表にある値か、
    evidence に「ソース名：値」を1行書いた値だけ。

出力の形は共通仕様ソース §18 のスキーマに合わせ、
1問ごとに stem / atoms（text・is_correct・statement・explanation・tags）/
overall_explanation / evidence / is_splittable を埋めてください。
'''


def build_orders(items, plan, variant, tax_sub, tag_cand, rank=None):
    orders = []
    for t, form in zip(items, plan):
        f = FORM_TEXT[form]
        orders.append({
            'unit': t[0], 'major': t[1], 'medium': t[2],
            # ランクは中項目から決まる導出値（アプリの rankFor と同じ表）。
            # ここで渡しておけば、作問側が自分で決めて揺れることがない。
            'rank': rank_of(t, rank or {}),
            'variant': variant, 'pool': 'mock',
            'question_type': 'multiple' if f['select_count'] >= 2 else 'single',
            'select_count': f['select_count'],
            'atom_count': f['atoms'],
            'form_label': f['label'],
            'sub_candidates': tax_sub.get('|'.join(t), []),
            'tag_candidates': tag_cand.get('|'.join(t), []),
        })
    return orders


def emit(base, seed=20260910):
    tax, rank = load_master(base)
    outdir = os.path.join(base, 'batches_free')
    os.makedirs(outdir, exist_ok=True)

    # 前回の残りは消さずに退避（このプロジェクトの決まりごと）
    old = sorted(glob.glob(os.path.join(outdir, 'M*.txt')))
    if old:
        bak = os.path.join(base, '_to_delete',
                           'batches_free_%s' % datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
        os.makedirs(bak, exist_ok=True)
        for f in old:
            shutil.move(f, os.path.join(bak, os.path.basename(f)))
        print('前回の %d本を %s へ退避しました（消していません）' % (len(old), bak))

    # 中項目→小項目候補・タグ候補は、過去問の入力バッチ（F*.txt の hints）から借りる。
    # 同じ中項目の問題に渡した候補をそのまま使う＝作問の条件を過去問とそろえる。
    tax_sub, tag_cand = {}, {}
    for f in sorted(glob.glob(os.path.join(base, 'batches_finish_v2', 'F*.txt'))):
        t = io.open(f, encoding='utf-8-sig').read()
        try:
            j = json.loads(t[t.index('\n{\n'):])
        except Exception:
            continue
        hints = {h.get('source'): h for h in j.get('hints', [])}
        for q in j.get('questions', []):
            k = '|'.join([q.get('unit') or '', q.get('major') or '', q.get('medium') or ''])
            h = hints.get(q.get('source')) or {}
            if h.get('sub_candidates') and k not in tax_sub:
                tax_sub[k] = h['sub_candidates']
            if h.get('tag_candidates') and k not in tag_cand:
                tag_cand[k] = h['tag_candidates']

    used = set()
    rows, n_files, no = [], 0, 0
    for variant in ('free_a', 'free_b'):
        items = pick_media(tax, rank, QUOTA[variant], used, seed)
        plan = assign_forms(items, FORMS[variant], seed)
        orders = build_orders(items, plan, variant, tax_sub, tag_cand, rank)
        for i in range(0, len(orders), PER_FILE):
            chunk = orders[i:i + PER_FILE]
            no += 1
            name = 'M%04d.txt' % no
            body = HEAD.format(n=len(chunk)) + '\n' + json.dumps(
                {'orders': chunk}, ensure_ascii=False) + '\n'
            io.open(os.path.join(outdir, name), 'w', encoding='utf-8').write(body)
            n_files += 1
            for o in chunk:
                rows.append((name, variant, o['unit'], o['major'], o['medium'],
                             rank_of((o['unit'], o['major'], o['medium']), rank),
                             o['form_label'],
                             len(o['sub_candidates']), len(o['tag_candidates'])))

    outd = os.path.join(base, 'out')
    os.makedirs(outd, exist_ok=True)
    tsv = os.path.join(outd, '体験用の割り当て_%s.tsv'
                       % datetime.datetime.now().strftime('%Y%m%d'))
    with io.open(tsv, 'w', encoding='utf-8') as fh:
        fh.write('バッチ\tvariant\t単元\t大項目\t中項目\tランク\t形式\t小項目候補\tタグ候補\n')
        for r in rows:
            fh.write('\t'.join(str(x) for x in r) + '\n')

    # 出来ばえを数える（黙って出さない）
    import collections
    print('バッチ %d本 ／ 注文 %d問 → %s' % (n_files, len(rows), os.path.basename(outdir)))
    for v in ('free_a', 'free_b'):
        sub = [r for r in rows if r[1] == v]
        cu = collections.Counter(r[2] for r in sub)
        cr = collections.Counter(r[5] for r in sub)
        cf = collections.Counter(r[6] for r in sub)
        need = QUOTA[v]
        bad = [u for u in need if cu.get(u, 0) != need[u]]
        print('  %s %d問  単元の過不足 %s' % (v, len(sub), ('なし' if not bad else bad)))
        print('       ランク %s' % dict(cr))
        print('       形式   %s' % dict(cf))
        nz = sum(1 for r in sub if r[8] == 0)
        if nz:
            print('       ※ タグ候補が空の注文 %d問（過去問に同じ中項目が無い）' % nz)
    dup = len(rows) - len(set((r[2], r[4]) for r in rows))
    print('  中項目の重なり %d件（free_a と free_b を通して0であること）' % dup)
    print('  割り当て表 → %s' % os.path.basename(tsv))
    return n_files, rows


def selftest():
    R = []

    def ok(n, c, d=''):
        R.append((bool(c), n, str(d)))

    tax = [('必修', '1. あ', 'A. %d' % i) for i in range(20)]
    tax += [('成人看護学', '2. い', 'B. %d' % i) for i in range(20)]
    rank = {}
    for i, t in enumerate(tax):
        rank['|'.join(t)] = 'SAB'[i % 3]
    used = set()
    q = {'必修': 6, '成人看護学': 4}
    a = pick_media(tax, rank, q, used, 1)
    ok('頼んだ数だけ選ぶ', len(a) == 10, len(a))
    ok('単元ごとの数が合う',
       sum(1 for t in a if t[0] == '必修') == 6 and
       sum(1 for t in a if t[0] == '成人看護学') == 4,
       [t[0] for t in a])
    b = pick_media(tax, rank, q, used, 1)
    ok('2回目は前回と重ならない', not (set(a) & set(b)), sorted(set(a) & set(b))[:3])
    ok('使った中項目は記録される', len(used) == 20, len(used))

    plan = assign_forms(a, {'four': 4, 'five': 3, 'multi': 3}, 1)
    ok('形式の数が合う', plan.count('multi') == 3 and plan.count('five') == 3,
       {x: plan.count(x) for x in set(plan)})
    ok('必修に「2つ選べ」を作らない',
       all(not (t[0] == '必修' and p == 'multi') for t, p in zip(a, plan)),
       [t[0] for t, p in zip(a, plan) if p == 'multi'])

    ok('注文に pool=mock と variant が入る',
       all(o['pool'] == 'mock' and o['variant'] == 'free_a'
           for o in build_orders(a, plan, 'free_a', {}, {})))
    ok('select_count と question_type が矛盾しない',
       all((o['select_count'] >= 2) == (o['question_type'] == 'multiple')
           for o in build_orders(a, plan, 'free_a', {}, {})))
    ok('指示書の配分と一致（free_a 30問・free_b 60問）',
       sum(QUOTA['free_a'].values()) == 30 and sum(QUOTA['free_b'].values()) == 60,
       [sum(QUOTA['free_a'].values()), sum(QUOTA['free_b'].values())])
    ok('形式の合計が問題数と一致',
       sum(FORMS['free_a'].values()) == 30 and sum(FORMS['free_b'].values()) == 60,
       [sum(FORMS['free_a'].values()), sum(FORMS['free_b'].values())])

    bad = [x for x in R if not x[0]]
    for g, n, d in R:
        print(('  ok  ' if g else '  NG  ') + n + ('' if g else '   << ' + d))
    print('\n%d/%d  体験用バッチ' % (len(R) - len(bad), len(R)))
    return 1 if bad else 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    base = sys.argv[sys.argv.index('--base') + 1] if '--base' in sys.argv else '.'
    emit(base)
    print('')
    print('PADの変更は3か所だけです（過去問の仕上げと同じ形）:')
    print('  1行目「フォルダー内のファイルを取得」 フォルダー … \\batches_free')
    print('                                        フィルター … M*.txt')
    print('  終盤「テキストをファイルに書き込む」   フォルダー … \\res_free')
    print('  ※ 出口を res_finish のままにしないこと。過去問の検証が全部NGになります。')
