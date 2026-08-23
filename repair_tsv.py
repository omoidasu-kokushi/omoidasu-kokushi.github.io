#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
repair_tsv.py — 受け取ったTSVを取り込める形に直す

【元データの傷】
  1. セル内に実改行が入っていて、1問が複数の物理行に割れている
  2. 10列目（正解番号）が空の行が約半分ある（正解は11列目の解説文の中にある）
  3. まったく同じ問題が何度も重複している

【直し方】
  1. 行の先頭が 【単元名】+タブ の行を「新しい問題の始まり」と見なして復元する
     （列数で判定すると、壊れた行と正常な行の境目を取り違える）
  2. 解説文から 正解：【①…】 / 【正解】① を拾い、0始まりの番号へ直す
  3. 問題文＋選択肢が同一のものは最初の1件だけ残す

【捨てたものは必ず数えて報告する】黙って減らさない。
"""
import io, re, json, sys, collections

SRC = '/tmp/qs.txt'
OUT = '/home/claude/nurse/questions_clean.tsv'

CIRC = '①②③④⑤⑥⑦⑧⑨⑩'
CIRC_IDX = {c: i for i, c in enumerate(CIRC)}
START = re.compile(r'^【[^】]+】\t')
TAGCELL = re.compile(r'^\s*\[\s*\[?\s*"#')
PATS = [
    re.compile(r'【正解】\s*[^①-⑩]{0,6}?([' + CIRC + r']+)'),
    re.compile(r'正解[：:]\s*【\s*([' + CIRC + r']+)'),
    re.compile(r'正解[はが]?\s*[：:]\s*([' + CIRC + r']+)'),
]
POSITIVE = re.compile(r'([' + CIRC + r'])\s*(?:正しい|正解|○|適切)')


def unquote(s):
    """Excel経由で付く二重引用符を戻す（DESIGN 3-4 と同じ問題）。"""
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1].replace('""', '"')
    return s


raw = io.open(SRC, encoding='utf-8-sig').read()

# ---- 1. 割れた行を復元 ----
rows, buf = [], None
for line in raw.split('\n'):
    if START.match(line):
        if buf is not None:
            rows.append(buf)
        buf = line
    else:
        if buf is None:
            continue
        buf += line          # 実改行は落とす（本文は <br> で改行済み）
if buf is not None:
    rows.append(buf)

rep = collections.Counter()
rep['復元した行'] = len(rows)

out, seen = [], {}
dropped_short, dropped_noans, dropped_dup, dropped_json = [], [], [], []

for n, r in enumerate(rows, 1):
    c = [unquote(x) for x in r.split('\t')]

    # ---- 2. 正解列が丸ごと無い行を補正 ----
    #    11列目がタグ配列に見えるなら、10列目（正解）が抜けている。
    if len(c) >= 11 and TAGCELL.match(c[10] or ''):
        c = c[:9] + [''] + c[9:]
        rep['正解列の抜けを補正'] += 1

    if len(c) < 12:
        dropped_short.append((n, len(c), c[7][:40] if len(c) > 7 else ''))
        continue
    c = c[:13] + [''] * max(0, 13 - len(c))

    try:
        choices = json.loads(c[8])
        if not isinstance(choices, list) or not choices:
            raise ValueError('選択肢が配列でない')
    except Exception as e:
        dropped_json.append((n, str(e)[:40], c[8][:60]))
        continue

    # ---- 3. 正解番号を決める ----
    idx, src = None, None
    a = c[9].strip()
    if a:
        try:
            v = json.loads(a)
            v = v if isinstance(v, list) else [v]
            if all(isinstance(i, int) for i in v):
                idx, src = v, '列'
        except Exception:
            pass
    if idx is None or any(i < 0 or i >= len(choices) for i in idx):
        got = None
        for pat in PATS:
            m = pat.search(c[10])
            if m:
                got = m.group(1); break
        if not got:
            # 「①正しい。②誤り。」形式
            hits = POSITIVE.findall(c[10])
            if hits:
                got = ''.join(sorted(set(hits), key=CIRC_IDX.get))
        if got:
            idx, src = sorted({CIRC_IDX[ch] for ch in got}), '解説'
        else:
            idx = None
    if idx is None or any(i < 0 or i >= len(choices) for i in idx):
        dropped_noans.append((n, c[7][:50]))
        continue
    c[9] = json.dumps(idx)
    rep['正解：' + src] += 1

    # 形式と正解数の食い違いを直す
    qt = c[6].strip()
    if qt == 'single' and len(idx) > 1:
        c[6] = 'multiple'; rep['形式を multiple へ直した'] += 1
    elif qt == 'multiple' and len(idx) == 1:
        c[6] = 'single'; rep['形式を single へ直した'] += 1

    # 単元名の 【】 を外す。パンくずに出る名前なので、飾りの括弧が
    # 「必修問題 ＞ 1.健康に関する指標」の可読性を下げる。
    c[0] = c[0].strip().strip('【】')

    # ---- 4. 重複を落とす ----
    key = (c[7].strip(), c[8].strip())
    if key in seen:
        dropped_dup.append((n, seen[key], c[7][:40]))
        continue
    seen[key] = n
    out.append('\t'.join(x.replace('\t', ' ') for x in c))

rep['取り込む問題'] = len(out)
rep['捨てた：行が壊れている'] = len(dropped_short)
rep['捨てた：選択肢が読めない'] = len(dropped_json)
rep['捨てた：正解が特定できない'] = len(dropped_noans)
rep['捨てた：重複'] = len(dropped_dup)

io.open(OUT, 'w', encoding='utf-8', newline='').write('\n'.join(out))

print('=== 集計 ===')
for k in ['復元した行', '正解列の抜けを補正', '正解：列', '正解：解説',
          '形式を multiple へ直した', '形式を single へ直した',
          '捨てた：行が壊れている', '捨てた：選択肢が読めない',
          '捨てた：正解が特定できない', '捨てた：重複', '取り込む問題']:
    if rep[k]:
        print('  %-24s %d' % (k, rep[k]))

print('\n=== 単元の内訳 ===')
for u, n in collections.Counter(l.split('\t')[0] for l in out).most_common():
    print('  %-24s %d問' % (u, n))
print('\n=== ランクの内訳 ===')
for r_, n in collections.Counter(l.split('\t')[2] for l in out).most_common():
    print('  %-6s %d問' % (r_, n))
print('\n=== 形式 ===')
for r_, n in collections.Counter(l.split('\t')[6] for l in out).most_common():
    print('  %-10s %d問' % (r_, n))

print('\n=== 捨てた行（先頭5件ずつ） ===')
for name, arr in [('壊れている', dropped_short), ('選択肢が読めない', dropped_json),
                  ('正解が特定できない', dropped_noans), ('重複', dropped_dup)]:
    print(' %s (%d):' % (name, len(arr)))
    for x in arr[:5]:
        print('  ', x)

print('\n出力:', OUT, len(io.open(OUT, encoding='utf-8').read()), '文字')
