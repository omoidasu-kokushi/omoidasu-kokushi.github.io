# -*- coding: utf-8 -*-
"""助詞の英単語化けを直す_V1.00.py

作問パイプライン（NotebookLM）の出力に、助詞が英単語へ化けたものが混ざる。

    肝臓 is、体内の有害物質を…      →  肝臓は、体内の有害物質を…
    発達段階 of の組合せ            →  発達段階の組合せ
    括約筋 of 収縮                  →  括約筋の収縮

実測（配布176問）：is 7件・of 16件。利用者の目に直接触れる。
同梱シードでは同じ化けを V1.86 までに84箇所直しており（batchBL）、
今回は過去問仕上げレーンの出力に同じ癖が出た。

【壊してはいけないもの】
  Quality of Life / Sanctity of Life / Insufficiency of Respiration は
  本物の英語。**日本語文字に挟まれているときだけ**直す。
  ここを守らないと、直すつもりで壊す。

【勝手に直さないもの】
  the / and / to / in / for / with / by なども化けうるが、
  置き換え先が文脈で変わる（に・と・で…）。誤変換のほうが害が大きいので、
  **検出して報告するだけ**にする。人が見て決める。

使い方
  python3 助詞の英単語化けを直す_V1.00.py --in 入力.json --out 出力.json
  python3 助詞の英単語化けを直す_V1.00.py --selftest
"""
import io, json, re, sys

# 日本語とみなす文字（英数字は入れない：本物の英語を守るため）
J = r'[぀-ヿ一-鿿ー々、。：；・（）「」]'

# 直すもの（順序が意味を持つ：of＋の の重複を先に潰す）
FIX = [
    (re.compile(r'(' + J + r')\s?\bof\b\s?の'), r'\1の'),
    (re.compile(r'(' + J + r')\s?\bof\b\s?(' + J + r')'), r'\1の\2'),
    (re.compile(r'(' + J + r')\s?\bis\b\s?(' + J + r')'), r'\1は\2'),
]
# 報告だけするもの
WATCH = re.compile(r'(' + J + r')\s?\b(the|and|or|to|in|for|with|by|at|on|an|a)\b\s?(' + J + r')')

FIELDS_Q = ('stem', 'overall_explanation')
FIELDS_A = ('text', 'statement', 'explanation')


def fix_text(s):
    """1つの文字列を直す。直した件数も返す。"""
    if not s:
        return s, 0
    n = 0
    for rx, rep in FIX:
        s, k = rx.subn(rep, s)
        n += k
        # 「AofBofC」のように連続すると1回では拾いきれない
        while k:
            s, k = rx.subn(rep, s)
            n += k
    return s, n


def watch_text(s):
    return [m.group(2) for m in WATCH.finditer(s or '')]


def fix_data(data):
    stat = {'fixed': 0, 'questions': 0, 'watch': {}}
    for q in data.get('questions', []):
        hit = 0
        for k in FIELDS_Q:
            if q.get(k):
                q[k], n = fix_text(q[k])
                hit += n
                for w in watch_text(q[k]):
                    stat['watch'][w] = stat['watch'].get(w, 0) + 1
        for a in q.get('atoms', []) or []:
            for k in FIELDS_A:
                if a.get(k):
                    a[k], n = fix_text(a[k])
                    hit += n
                    for w in watch_text(a[k]):
                        stat['watch'][w] = stat['watch'].get(w, 0) + 1
        if hit:
            stat['fixed'] += hit
            stat['questions'] += 1
    return stat


def selftest():
    s, n = fix_text('肝臓 is、体内の有害物質を無毒化する。')
    assert s == '肝臓は、体内の有害物質を無毒化する。' and n == 1, s
    s, n = fix_text('入院中の小児のストレス因子と発達段階 of の組合せ')
    assert s == '入院中の小児のストレス因子と発達段階の組合せ', s
    s, n = fix_text('排尿筋の弛緩と括約筋 of 収縮')
    assert s == '排尿筋の弛緩と括約筋の収縮', s
    s, n = fix_text('脾静脈 is 門脈系の血管である。')
    assert s == '脾静脈は門脈系の血管である。', s
    # 本物の英語は壊さない
    for eng in ['Quality of Life を保つ', 'Sanctity of Life の考え方',
                'Insufficiency of Respiration とよぶ', 'this is a pen']:
        s2, n2 = fix_text(eng)
        assert s2 == eng and n2 == 0, eng + ' -> ' + s2
    # 英数字に挟まれた of も触らない
    s3, n3 = fix_text('ADL of IADL')
    assert s3 == 'ADL of IADL' and n3 == 0, s3
    # 報告だけの語は直さない
    s4, n4 = fix_text('食事 to 水分')
    assert s4 == '食事 to 水分' and n4 == 0, s4
    assert watch_text('食事 to 水分') == ['to']
    # データ丸ごと
    d = {'questions': [{'stem': '肝臓 is 何か。', 'overall_explanation': None,
                        'atoms': [{'text': '解毒 of 臓器', 'statement': None,
                                   'explanation': 'Quality of Life は変えない'}]}]}
    st = fix_data(d)
    assert d['questions'][0]['stem'] == '肝臓は何か。'
    assert d['questions'][0]['atoms'][0]['text'] == '解毒の臓器'
    assert d['questions'][0]['atoms'][0]['explanation'] == 'Quality of Life は変えない'
    assert st['fixed'] == 2 and st['questions'] == 1, st
    print('selftest OK（is/of の修正4観点＋本物の英語5観点＋報告のみ＋データ適用）')


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        selftest(); sys.exit(0)
    src = sys.argv[sys.argv.index('--in') + 1]
    out = sys.argv[sys.argv.index('--out') + 1]
    data = json.loads(io.open(src, encoding='utf-8-sig').read())
    st = fix_data(data)
    io.open(out, 'w', encoding='utf-8').write(json.dumps(data, ensure_ascii=False, indent=1))
    print('助詞の化けを直した: %d箇所 / %d問' % (st['fixed'], st['questions']))
    if st['watch']:
        print('※ 人が見て決めるもの（直していない）:', st['watch'])
    print('出力:', out)
