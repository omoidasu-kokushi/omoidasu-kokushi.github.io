#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBT：直前期の解禁緩和（V1.95・判断待ちの「案A」）

【なぜ入れたか】
解禁は解答済みの割合だけで決まり、試験日を見ていなかった。
実測（tools/journey.py・1,359問）で **1日40問の人は90日たっても1つも解禁されない**。
試験3ヶ月前に始めた人は本番形式の模試を一度も受けられないまま試験を迎える。
買い切りの商品としてここがいちばん痛い。

【効くのは試験日を入れている人だけ】
試験日が無ければ係数は 1.0。**入れていない人の解禁日は1日もずれない。**（成功基準②）

【問題数の下限は緩めない】
30問模試に30問要るのは物理的な要件で、試験が近いかどうかとは関係がない。
緩めると「120問フル模試」が80問で始まってしまう。

【戻さない】
一度 true にしたフラグは戻さない（既存仕様）。試験日を後ろへずらすと
解禁済みが残るが、戻すほうが体験としてずっと悪い。

【画面が説明できること】
「なぜ今日開いたのか」が分からないと、解禁が偶然に見える。
緩和中は理由を出し、**条件の文字も実際の数に書き換える**。
書き換えないと、画面は15%と言っているのに6%で開く。
"""
import io, json, os, re, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


st = read("storage.js")
sc = read("scheduler.js")
html = read("index.html")
css = read("styles.css")
p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
j2 = read(p2)

ok("緩和の段がある", "var EXAM_EASE = [" in st and "within: 30, factor: 0.4" in st
   and "within: 60, factor: 0.6" in st)
ok("係数の関数がある", "function unlockEaseFactor(" in st)
ok("**必要割合の定義そのものは変えていない**",
   "need_unique: 0.15" in st and "need_unique: 0.35" in st and "need_unique: 0.50" in st
   and "need_normal_plus: 0.40" in st and "need_normal_plus: 0.45" in st
   and "need_normal_plus: 0.50" in st)
ok("問題数の下限は緩めないと書いてある", "問題数の下限（req_q）は緩めない" in st)
ok("試験日を渡している", "examRestDays        : restDays" in sc)
ok("緩和中は理由を出す", 'id="exam-ease"' in html and ".exam-ease{" in css)
ok("**条件の文字も書き換える**", "直前期のため緩和中" in j2)
ok("書き換えない場合の壊れ方が書いてある", "画面は15%と言っているのに6%で開く" in j2)
ok("版番号・CACHE_NAME・?v= の3箇所が揃っている",
   (lambda i, w: i and w and i == w)(
       (re.search(r"\?v=([0-9.]+)", html) or [None, None])[1],
       (re.search(r"\?v=([0-9.]+)", read("sw.js")) or [None, None])[1]))

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(1400)

    # --- 係数そのもの ---
    r = pg.evaluate("""() => { const S = window.Storage; return {
      none:  S.unlockEaseFactor(null),
      far:   S.unlockEaseFactor(120),
      edge61:S.unlockEaseFactor(61),
      at60:  S.unlockEaseFactor(60),
      at31:  S.unlockEaseFactor(31),
      at30:  S.unlockEaseFactor(30),
      at0:   S.unlockEaseFactor(0),
      past:  S.unlockEaseFactor(-3) }; }""")
    ok("**試験日が無ければ緩めない**", r["none"] == 1, json.dumps(r))
    ok("遠いうちは緩めない", r["far"] == 1 and r["edge61"] == 1, json.dumps(r))
    ok("残り60日で0.6", r["at60"] == 0.6 and r["at31"] == 0.6, json.dumps(r))
    ok("残り30日で0.4", r["at30"] == 0.4 and r["at0"] == 0.4, json.dumps(r))
    ok("試験が終わっていれば緩めない", r["past"] == 1, json.dumps(r))

    # --- 解禁判定に効くか ---
    u = pg.evaluate("""async () => {
      const S = window.Storage;
      /* 30問プチ模試：ユニーク15% ＋ 普通以上40%。
         いま 8% / 20% の人は、通常では開かないが 0.4倍（6%/16%）なら開く。 */
      const base = { totalQuestions: 500, uniqueAnsweredRatio: 0.08,
                     normalPlusRatio: 0.20, fullMockPassStreak: 0 };
      const pick = (rs, id) => rs.filter(x => x.id === id)[0];
      const snap = await S.loadMeta();
      const reset = async () => {
        await S.setMeta('unlock_mock_30', false);
        await S.setMeta('unlock_mock_60', false);
        await S.setMeta('unlock_mock_120', false);
        await S.setMeta('unlock_pct_mock_30', 0);
      };
      await reset();
      const far = pick(await S.evaluateUnlocks(Object.assign({}, base, { examRestDays: 200 })), 'mock_30');
      await reset();
      const near = pick(await S.evaluateUnlocks(Object.assign({}, base, { examRestDays: 20 })), 'mock_30');
      await reset();
      const noExam = pick(await S.evaluateUnlocks(base), 'mock_30');
      await reset();
      /* 問題数が足りなければ、緩和が効いていても開かない */
      const fewQ = pick(await S.evaluateUnlocks(Object.assign({}, base,
        { totalQuestions: 10, examRestDays: 20 })), 'mock_30');
      await reset();
      return { far:far, near:near, noExam:noExam, fewQ:fewQ,
               had: !!snap.unlock_mock_30 };
    }""")
    ok("**試験が遠ければ、いままでどおり開かない**",
       u["far"]["unlocked"] is False and u["far"]["eased"] is False,
       json.dumps(u["far"], ensure_ascii=False))
    ok("**試験日を入れていない人も、いままでどおり開かない（成功基準②）**",
       u["noExam"]["unlocked"] is False and u["noExam"]["ease"] == 1,
       json.dumps(u["noExam"], ensure_ascii=False))
    ok("**直前期なら開く（成功基準①）**",
       u["near"]["unlocked"] is True and u["near"]["eased"] is True,
       json.dumps(u["near"], ensure_ascii=False))
    ok("緩和後の必要割合を返す（画面が説明に使う）",
       abs(u["near"]["need_unique"] - 0.06) < 1e-9
       and abs(u["near"]["need_normal_plus"] - 0.16) < 1e-9,
       json.dumps(u["near"], ensure_ascii=False))
    ok("**問題数が足りなければ、緩和が効いていても開かない**",
       u["fewQ"]["unlocked"] is False and u["fewQ"]["q_gate_met"] is False,
       json.dumps(u["fewQ"], ensure_ascii=False))

    # --- 一度開いたら戻らない ---
    keep = pg.evaluate("""async () => {
      const S = window.Storage;
      const base = { totalQuestions: 500, uniqueAnsweredRatio: 0.08,
                     normalPlusRatio: 0.20, fullMockPassStreak: 0 };
      const pick = (rs, id) => rs.filter(x => x.id === id)[0];
      await S.setMeta('unlock_mock_30', false);
      await S.setMeta('unlock_pct_mock_30', 0);
      const opened = pick(await S.evaluateUnlocks(Object.assign({}, base, { examRestDays: 20 })), 'mock_30');
      /* 試験日を後ろへずらしても（＝緩和が切れても）戻さない */
      const later = pick(await S.evaluateUnlocks(Object.assign({}, base, { examRestDays: 300 })), 'mock_30');
      const none  = pick(await S.evaluateUnlocks(base), 'mock_30');
      await S.setMeta('unlock_mock_30', false);
      await S.setMeta('unlock_pct_mock_30', 0);
      return { opened:opened.unlocked, later:later.unlocked, none:none.unlocked };
    }""")
    ok("**一度開いたら、試験日をずらしても閉じない（既存仕様）**",
       keep["opened"] is True and keep["later"] is True and keep["none"] is True,
       json.dumps(keep))

    # --- 画面 ---
    v = pg.evaluate("""async () => {
      const S = window.Storage, H = window.Half2Impl;
      await S.setMeta('exam_date', null);
      await H.openExamList();
      const off = { hidden: document.getElementById('exam-ease').hidden,
                    cond: document.querySelector('#exam-list .exam-cond').textContent };
      const d = new Date(Date.now() + 86400000 * 20);
      await S.setMeta('exam_date', d.getFullYear() + '-'
        + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0'));
      await H.openExamList();
      const on = { hidden: document.getElementById('exam-ease').hidden,
                   note: document.getElementById('exam-ease').textContent,
                   cond: document.querySelector('#exam-list .exam-cond').textContent };
      await S.setMeta('exam_date', null);
      await H.openExamList();
      const back = document.getElementById('exam-ease').hidden;
      return { off:off, on:on, back:back };
    }""")
    ok("**試験日が無ければ何も出ない**", v["off"]["hidden"] is True,
       json.dumps(v["off"], ensure_ascii=False))
    ok("**直前期は理由が出る**",
       v["on"]["hidden"] is False and "解禁に必要な割合" in v["on"]["note"],
       json.dumps(v["on"], ensure_ascii=False))
    ok("**合格基準は変えていないと明記される**",
       "合格基準そのものは本番と同じ" in v["on"]["note"],
       json.dumps(v["on"], ensure_ascii=False))
    ok("**条件の文字も実際の数に書き換わる**",
       "6%" in v["on"]["cond"] and "緩和中" in v["on"]["cond"],
       json.dumps(v["on"], ensure_ascii=False))
    ok("試験日を外せば元の数字に戻る",
       v["back"] is True and "15%" in v["off"]["cond"],
       json.dumps({"off": v["off"], "back": v["back"]}, ensure_ascii=False))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBT" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
