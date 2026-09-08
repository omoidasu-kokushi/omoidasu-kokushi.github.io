# -*- coding: utf-8 -*-
"""test_oneq_fast.py — 一問一答をタップだけで回す形にする（V2.84）

【利用者の要望（原文に近い形で残す）】
    胎児循環で胎児から胎盤に血液を送るのは【 総頸動脈 】である。
    [ ○ ] [ × ]
  これくらい超シンプルな形。解答の確定もいらない。
  ○×をタップするだけの、とにかくスピード勝負。
    ① ○か×をタップするだけで「正解!」「残念!」のポップアップ
    ② 正しい場合は【】内を強調。**【】自体には決して干渉させない**
    ②' 誤りの場合は【】内に二重取り消し線。正しい解答を直上か直下に。
        **【】自体には決して干渉させない。**固定の位置ではない。
        問題文と被ってもよい。正解の単語を常に最上部（立体の話）に。
    ③ デカい次へボタンをタップで次へ

【V2.83 まで】1問あたり画面を3か所読ませ、2タップ必要だった
    問題文カード「胎児循環で胎児から胎盤に血液を送るのはどれか。」
    見出し      「この選択肢は正しいですか？」
    肢          「① 総頸動脈」
    [○ 正しい] [× 誤り]（縦積み）
    [解答を確定する]
  さらに採点すると解説フェーズへ飛び、評価4つ・全体解説・図が一度に出た。

【V2.84】
  ・問題文カードに statement をそのまま出す（1か所だけ読む）
  ・○と×だけを横に2枚。文字は付けない
  ・押した瞬間に採点する（確定を挟まない＝40問で40タップ減る）
  ・解説フェーズへ飛ばさず、その場で答え合わせ＋大きい「次へ」
  ・解説は小さい導線から開ける

ここで固定するのは30個ほど。**【】に干渉しないこと**を特に強く見る。
"""
import os, sys, io, json
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p1 = open(os.path.join(base, "20260815_main_part1_V1.38.js"), encoding="utf-8").read()
cs = open(os.path.join(base, "styles.css"), encoding="utf-8").read()

ok("【】は記号として置き、線は中の言葉だけに掛ける",
   "oq-word" in p1 and "括弧に線が乗ると" in p1)
ok("問題文は必ず出す（statement だけにしない）", "問題文は**必ず出す**" in p1)
ok("なぜ statement だけにしないかが書いてある", "74%が肢の本文と同じ" in p1)
ok("正解はポップアップと同じ形で下に出す", "ポップアップと同じ形" in p1)
ok("降参がある", "oq-giveup" in p1 and "説明できない" in p1)
ok("○で正解なら自動で次へ", "手を止めずに次へ" in p1)
ok("×で正解なら裏回答を聞く", "showOneQGround" in p1)
ok("裏回答は×が左・○が右", "oq-g-no" in p1 and "押す回数の多い側を" in p1)
ok("解説は肢のぶんだけ", "この肢のぶんだけ" in p1)
ok("元の問題を見る導線がある", "元の問題を見る" in p1)
ok("display:flex を書いた（block では中央に寄らない）", "display:flex を書く" in cs)
ok("○×は押した瞬間に採点する", "押した瞬間に採点する" in p1)
ok("解説フェーズへ飛ばさない", "解説フェーズへ飛ばさない" in p1)
ok("flex-direction を明示した（親が column なので）", "flex-direction を必ず書く" in cs)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
BK = os.environ.get(
    "ONEQ_JSON",
    "/sessions/ecstatic-wizardly-dijkstra/mnt/owner/Desktop/国家試験対策室/"
    "過去問抽出_20260824/分類_令和5年版/out/20260908_一問一答おためし_V1.00.json")

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(1000)

    if not os.path.exists(BK):
        ok("（おためしデータが無いので実機の確認は省略）", True, BK)
    else:
        pg.evaluate("t => { window.__B = t; }", io.open(BK, encoding="utf-8-sig").read())
        pg.evaluate("async () => { await window.Storage.restoreBackup(JSON.parse(window.__B), 'merge'); }")
        pg.reload(wait_until="load")
        pg.wait_for_function("window.__APP_READY === true", timeout=60000)
        pg.wait_for_timeout(1400)
        pg.evaluate("() => { const s=document.getElementById('splash'); if(s) s.classList.add('is-gone');"
                    " if (window.Main && window.Main.closeModals) window.Main.closeModals(); }")
        pg.evaluate("() => { const b=document.querySelector('#card-review')"
                    "||document.querySelector('.main-card'); if (b) b.click(); }")
        pg.wait_for_timeout(1800)
        for _ in range(8):
            try:
                pg.locator("button:has-text('OK')").first.click(timeout=500)
                pg.wait_for_timeout(200)
            except Exception:
                break
        pg.evaluate("() => { const p=document.querySelector('#verdict-pop'); if(p) p.hidden=true; }")
        pg.wait_for_timeout(400)

        a = pg.evaluate("""() => {
          const st = document.querySelector('#choice-list .oq-word-row');
          const list = document.querySelector('#choice-list');
          const cs2 = [...document.querySelectorAll('#choice-list .choice-card')];
          const o = document.querySelector('.oq-o .ox-mark');
          const x = document.querySelector('.oq-x .ox-mark');
          const b = document.querySelector('#btn-confirm');
          const r = cs2.map(c => c.getBoundingClientRect());
          return {
            key: (st.querySelector('.oq-key')||{}).textContent || null,
            word: (st.querySelector('.oq-word')||{}).textContent || null,
            dir: getComputedStyle(list).flexDirection,
            n: cs2.length,
            sameRow: r.length === 2 && Math.abs(r[0].top - r[1].top) < 4,
            h: r.length ? Math.round(r[0].height) : 0,
            o: o ? o.textContent.trim() : null,
            x: x ? x.textContent.trim() : null,
            confirmHidden: b ? b.hidden : null,
            instruction: (document.querySelector('#q-instruction')||{}).textContent || '',
            stem: (document.querySelector('#q-stem-text')||{}).textContent || '',
            giveup: !!document.querySelector('#oq-giveup'),
            oBg: getComputedStyle(document.querySelector('.oq-o')).backgroundColor,
            xBg: getComputedStyle(document.querySelector('.oq-x')).backgroundColor
          };
        }""")
        ok("【】ごと出ている", a["key"] and a["key"].startswith("【") and a["key"].endswith("】"), a["key"])
        ok("中の言葉が別要素になっている", bool(a["word"]), a["word"])
        ok("○と×だけ（文字を付けない）", a["o"] == "○" and a["x"] == "×", (a["o"], a["x"]))
        ok("横に2枚並ぶ", a["dir"] == "row" and a["sameRow"], (a["dir"], a["sameRow"]))
        ok("押しやすい大きさ（70px以上）", a["h"] >= 70, a["h"])
        ok("確定ボタンを出さない", a["confirmHidden"] is True, a["confirmHidden"])
        ok("「この選択肢は正しいですか？」を出さない", a["instruction"].strip() == "", a["instruction"])
        ok("問題文が消えていない", len(a["stem"].strip()) >= 8, a["stem"][:30])
        ok("降参が出ている", a["giveup"], a["giveup"])
        ok("○は淡い緑・×は淡い赤で塗る",
           a["oBg"] != a["xBg"] and "rgba(0, 0, 0, 0)" not in a["oBg"], (a["oBg"], a["xBg"]))

        # わざと外す
        sel = pg.evaluate("() => window.Main.state.current.atoms[0].is_correct ? '.oq-x' : '.oq-o'")
        pg.evaluate("s => { document.querySelector(s + ' .choice-body').click(); }", sel)
        pg.wait_for_timeout(900)
        pop = pg.evaluate("""() => {
          const p = document.querySelector('#verdict-pop');
          return { shown: !!(p && !p.hidden),
                   title: (document.querySelector('#vp-title')||{}).textContent || '',
                   answer: (document.querySelector('#vp-answer')||{}).textContent || '' };
        }""")
        ok("ポップアップが出る", pop["shown"], pop)
        ok("ポップアップは○×だけ（正解は下に出すので二重にしない）",
           pop["answer"].strip() == "", pop["answer"])
        pg.evaluate("() => { const p=document.querySelector('#verdict-pop'); if(p) p.hidden=true; }")
        pg.wait_for_timeout(300)

        b = pg.evaluate("""() => {
          const st = document.querySelector('#choice-list .oq-word-row');
          const w = st.querySelector('.oq-word');
          const k = st.querySelector('.oq-key');
          const f = st.querySelector('.oq-fix');
          const cw = getComputedStyle(w), ck = getComputedStyle(k);
          const wr = w.getBoundingClientRect(), fr = f ? f.getBoundingClientRect() : null;
          const btn = document.querySelector('#btn-confirm');
          return {
            wrong: st.classList.contains('is-wrong'),
            wordLine: cw.textDecorationLine, wordStyle: cw.textDecorationStyle,
            keyLine: ck.textDecorationLine,
            fix: f ? f.textContent : null,
            below: !!(fr && fr.top >= wr.bottom - 2),
            red: f ? getComputedStyle(f.querySelector('b')).color : null,
            next: btn && !btn.hidden ? btn.textContent.trim() : null,
            big: btn ? btn.classList.contains('is-oq-next') : false,
            nextH: btn ? Math.round(btn.getBoundingClientRect().height) : 0,
            more: !!document.querySelector('#oq-open-review'),
            phase: document.querySelector('#screen-quiz').getAttribute('data-phase')
          };
        }""")
        ok("中の言葉に二重取り消し線", b["wordLine"] == "line-through" and b["wordStyle"] == "double",
           (b["wordLine"], b["wordStyle"]))
        ok("**【】には線を掛けない**", b["keyLine"] == "none", b["keyLine"])
        ok("正しい言葉が出る", bool(b["fix"]), b["fix"])
        ok("正しい言葉は線を引いた行のすぐ下", b["below"], b["below"])
        ok("答えの単語だけ赤で目立つ", (b["red"] or "").startswith("rgb(2"), b["red"])
        ok("解説フェーズへ飛ばない", b["phase"] == "answer", b["phase"])
        ok("大きい「次へ」が出る", b["big"] and b["nextH"] >= 56, (b["next"], b["nextH"]))
        ok("解説を読む導線は残す", b["more"], b["more"])

        pg.evaluate("() => { document.querySelector('#btn-confirm').click(); }")
        pg.wait_for_timeout(1400)
        nxt = pg.evaluate("""() => {
          return { noFix: !document.querySelector('.oq-fix') };
        }""")
        ok("次へで進む（前の答え合わせが残らない）", nxt["noFix"], nxt)

    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  oneq_fast" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
