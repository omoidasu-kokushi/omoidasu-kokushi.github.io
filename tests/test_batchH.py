#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチH 検証：期日前の肢は評価しない（コミット門番）

  1. commitDecision の判定表（未学習／期日／期日前／期日前誤答／ノック）
  2. 実際に「次へ」を押したときに、期日前の肢が書き換わらないこと
     （V1.17 では 30日 → 90日 → 180日 へ 20分で駆け上がっていた）
  3. 期日前でも「間違えた」なら降格すること
  4. 期日前に「簡単」を手で押しても昇格しないこと（門番が難しいで上書き）
  5. 画面：評価ボタンが出ない／次回日付が出る／サマリーの丸がロック表示
  6. 「忘れていた」ボタンで復習へ戻せること
  7. 初見（未学習）は今までどおり全肢評価されること（回帰）
"""
import json, os, sys, subprocess, glob
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))

P1 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
for f in ["storage.js", "scheduler.js", P1, "sw.js"]:
    p = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True)
    ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

# 版はこの先も上がる。バッチHの内容が入っている下限だけを見る。
_v = tuple(int(x) for x in P1.split("_V")[-1].replace(".js", "").split("."))
ok("part1 は V1.15 以降", _v >= (1, 15), P1)
src_sw = open(os.path.join(APP, "sw.js"), encoding="utf-8").read()
import re as _re
_c = _re.search(r"CACHE_NAME = 'v(\d+)\.(\d+)\.(\d+)'", src_sw)
ok("sw.js の CACHE_NAME が v1.6.0 以降",
   bool(_c) and tuple(int(x) for x in _c.groups()) >= (1, 6, 0),
   _c.group(0) if _c else "not found")
ok("sw.js の CORE_ASSETS が実ファイルを指す", P1 in src_sw)
src_idx = open(os.path.join(APP, "index.html"), encoding="utf-8").read()
ok("index.html の script が実ファイルを指す", ('src="./%s"' % P1) in src_idx)
ok("index.html の診断 REQUIRED が実ファイルを指す", ('"./%s"' % P1) in src_idx)
ok("旧ファイル名がどこにも残っていない",
   "main_part1_V1.14" not in src_idx and "main_part1_V1.14" not in src_sw)

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=20000)
    pg.wait_for_timeout(2200)
    try:
        pg.click("#welcome-start", timeout=2500)
    except Exception:
        pass
    pg.wait_for_timeout(600)

    # ---------- 1. 判定表 ----------
    dec = pg.evaluate("""() => {
      const K = window.Scheduler, now = Date.now(), DAY = 86400000;
      const learned = c => ({ answer_count:3, due_date: now + c, srs_step:5, interval_code:'30d' });
      return {
        unlearned : K.commitDecision({answer_count:0, due_date:null}, true, 'review', now),
        noDue     : K.commitDecision({answer_count:3, due_date:null}, true, 'review', now),
        dueNow    : K.commitDecision(learned(-1000), true, 'review', now),
        dueExact  : K.commitDecision(learned(0), true, 'review', now),
        notDue    : K.commitDecision(learned(29*DAY), true, 'review', now),
        notDueMiss: K.commitDecision(learned(29*DAY), false, 'review', now),
        knock     : K.commitDecision(learned(29*DAY), true, 'knock', now),
        random    : K.commitDecision(learned(29*DAY), true, 'random', now),
        tree      : K.commitDecision(learned(29*DAY), true, 'tree', now),
        newMode   : K.commitDecision(learned(29*DAY), true, 'new', now)
      }; }""")
    ok("未学習は必ず評価する", dec["unlearned"]["commit"] and not dec["unlearned"]["demote"],
       json.dumps(dec["unlearned"]))
    ok("期日を持たない肢は従来どおり評価する", dec["noDue"]["commit"], json.dumps(dec["noDue"]))
    ok("期日を過ぎた肢は評価する", dec["dueNow"]["commit"], json.dumps(dec["dueNow"]))
    ok("期日ちょうど（due <= now）も評価する", dec["dueExact"]["commit"], json.dumps(dec["dueExact"]))
    ok("期日前で正しく扱えた肢は記録しない", not dec["notDue"]["commit"], json.dumps(dec["notDue"]))
    ok("期日前でも間違えたら記録する（降格）",
       dec["notDueMiss"]["commit"] and dec["notDueMiss"]["demote"], json.dumps(dec["notDueMiss"]))
    ok("概念ノックは門番の対象外（解釈D を壊さない）", dec["knock"]["commit"], json.dumps(dec["knock"]))
    ok("ランダムモードにも門番が効く", not dec["random"]["commit"], json.dumps(dec["random"]))
    ok("単元別学習にも門番が効く", not dec["tree"]["commit"], json.dumps(dec["tree"]))
    ok("新規モードにも門番が効く（既習肢が混ざるため）", not dec["newMode"]["commit"],
       json.dumps(dec["newMode"]))

    # ---------- 2〜4. 実際のコミット ----------
    SETUP = """async (cfg) => {
      const S=window.Storage, K=window.Scheduler, DAY=86400000, now=Date.now();
      const qs = await S.getAllQuestions();
      const q  = qs.find(x => x.question_type === 'single');
      const at = await S.getAtomsByQuestion(q.q_id);
      await S.updateAtom(at[0].atom_id, {srs_step:1, interval_code:'10m', last_eval:'hard',
        answer_count:3, correct_count:1, due_date: now-60000, last_answered_at: now-600000});
      for (let i=1;i<at.length;i++){
        await S.updateAtom(at[i].atom_id, {srs_step:5, interval_code:'30d', last_eval:'easy',
          answer_count:3, correct_count:3, due_date: now + 29*DAY, last_answered_at: now-DAY});
      }
      const snap = async () => (await S.getAtomsByQuestion(q.q_id)).map(x=>({
        n:x.original_num, ev:x.last_eval, ic:x.interval_code, cnt:x.answer_count,
        days: Math.round((x.due_date-Date.now())/DAY*10)/10 }));
      const before = await snap();
      const round = async (opt) => {
        const a = await S.getAtomsByQuestion(q.q_id);
        const cn = a.filter(x=>x.is_correct).map(x=>x.original_num);
        /* wrongAll: 誤答肢を1つ選ぶ（＝その肢と正解肢が「間違えた扱い」になる）。
           空選択にすると、選ばなかった誤答肢は「正しく扱えた」になるので、
           降格しないのが正しい挙動。ここを空にしていたのはテスト側の誤り。 */
        const wrong = a.filter(x=>!x.is_correct).map(x=>x.original_num);
        const picked = (opt && opt.wrongAll) ? [wrong[0]] : cn;
        const rec = K.recommendEvaluations(a, picked);
        const evals = a.map(x=>({
          atom_id: x.atom_id,
          eval: (opt && opt.forceEasy) ? 'easy' : rec.recommendations[x.atom_id].eval,
          is_correct: (picked.indexOf(x.original_num) >= 0) === !!x.is_correct }));
        return K.applyQuestionEvaluations(q.q_id, evals, {mode:'review', boundaryHour:4});
      };
      let r1 = await round(cfg && cfg.round1);
      const after1 = await snap();
      let r2 = await round(cfg && cfg.round2);
      const after2 = await snap();
      const a0 = await S.getAtomsByQuestion(q.q_id);
      const wrong0 = before.filter(x=>{
        const at2 = a0.find(y=>y.original_num===x.n); return !at2.is_correct; }).map(x=>x.n);
      const correct0 = a0.filter(x=>x.is_correct).map(x=>x.original_num);
      return { qid:q.q_id, before, after1, after2, wrong0, correct0,
               skipped1: r1.results.filter(x=>x.skipped).length,
               committed1: r1.results.filter(x=>!x.skipped).length }; }"""

    a = pg.evaluate(SETUP, {})
    ok("期日の肢だけが記録される（4肢中1肢）",
       a["committed1"] == 1 and a["skipped1"] == 3,
       "committed=%s skipped=%s" % (a["committed1"], a["skipped1"]))
    ok("期日前の3肢は 30日 のまま動かない（1回目）",
       all(x["ic"] == "30d" for x in a["after1"][1:]),
       json.dumps(a["after1"], ensure_ascii=False))
    ok("期日前の3肢は 30日 のまま動かない（2回目）",
       all(x["ic"] == "30d" for x in a["after2"][1:]),
       json.dumps(a["after2"], ensure_ascii=False))
    ok("V1.17 の 90日→180日 への駆け上がりが再現しない",
       not any(x["ic"] in ("90d", "180d") for x in a["after2"][1:]),
       json.dumps(a["after2"], ensure_ascii=False))
    ok("期日前の肢は answer_count も増えない",
       all(x["cnt"] == 3 for x in a["after2"][1:]),
       json.dumps([x["cnt"] for x in a["after2"]]))
    ok("期日の肢は今までどおり記録される（10分後・回数+2）",
       a["after2"][0]["ic"] == "10m" and a["after2"][0]["cnt"] == 5,
       json.dumps(a["after2"][0], ensure_ascii=False))
    ok("10分の段は期日前でも記録される（早期復習割り込みを殺さない）",
       pg.evaluate("""() => {
         const K=window.Scheduler, now=Date.now();
         const at = {answer_count:3, due_date: now + 9*60000, interval_code:'10m', srs_step:1};
         const d = K.commitDecision(at, true, 'random', now);
         return d.commit && d.reason === 'short-step'; }"""))
    ok("1時間の段も期日前で記録される",
       pg.evaluate("""() => {
         const K=window.Scheduler, now=Date.now();
         const at = {answer_count:3, due_date: now + 50*60000, interval_code:'1h', srs_step:2};
         return K.commitDecision(at, true, 'random', now).commit; }"""))
    ok("1日の段からは門番が効く",
       pg.evaluate("""() => {
         const K=window.Scheduler, now=Date.now();
         const at = {answer_count:3, due_date: now + 3600000, interval_code:'1d', srs_step:3};
         return !K.commitDecision(at, true, 'random', now).commit; }"""))
    ok("1週間の段からも門番が効く",
       pg.evaluate("""() => {
         const K=window.Scheduler, now=Date.now();
         const at = {answer_count:3, due_date: now + 6*86400000, interval_code:'1w', srs_step:4};
         return !K.commitDecision(at, true, 'random', now).commit; }"""))

    b = pg.evaluate(SETUP, {"round1": {"wrongAll": True}})
    # 誤答肢を1つ選んだので、「間違えた扱い」になるのは その肢 と 正解肢 の2本。
    # 選ばなかった残りの誤答肢は正しく扱えているので、動かないのが正しい。
    bad = set([b["wrong0"][0]] + b["correct0"])
    demoted = [x for x in b["after1"] if x["n"] in bad and x["n"] != 1]
    intact = [x for x in b["after1"] if x["n"] not in bad and x["n"] != 1]
    ok("期日前でも間違えた肢は「難しい」へ降格する",
       bool(demoted) and all(x["ic"] == "10m" and x["ev"] == "hard" for x in demoted),
       json.dumps(b["after1"], ensure_ascii=False))
    ok("降格した肢は answer_count が増える",
       all(x["cnt"] == 4 for x in demoted), json.dumps(demoted, ensure_ascii=False))
    ok("選ばなかった誤答肢は「正しく扱えた」ので動かない",
       bool(intact) and all(x["ic"] == "30d" and x["cnt"] == 3 for x in intact),
       json.dumps(intact, ensure_ascii=False))

    c = pg.evaluate(SETUP, {"round1": {"forceEasy": True}})
    ok("期日前に「簡単」を手で押しても昇格しない",
       all(x["ic"] == "30d" for x in c["after1"][1:]),
       json.dumps(c["after1"], ensure_ascii=False))

    d = pg.evaluate(SETUP, {"round1": {"wrongAll": True, "forceEasy": True}})
    dbad = set([d["wrong0"][0]] + d["correct0"])
    ddem = [x for x in d["after1"] if x["n"] in dbad and x["n"] != 1]
    ok("期日前の誤答に「簡単」を押しても、門番が難しいで上書きする",
       bool(ddem) and all(x["ic"] == "10m" and x["ev"] == "hard" for x in ddem),
       json.dumps(d["after1"], ensure_ascii=False))

    # ---------- 5〜6. 画面 ----------
    qid = pg.evaluate("""async () => {
      const S=window.Storage, M=window.Main, DAY=86400000, now=Date.now();
      const qs = await S.getAllQuestions();
      const q  = qs.find(x => x.question_type === 'single');
      const at = await S.getAtomsByQuestion(q.q_id);
      await S.updateAtom(at[0].atom_id, {srs_step:1, interval_code:'10m', last_eval:'hard',
        answer_count:3, correct_count:1, due_date: now-60000});
      for (let i=1;i<at.length;i++){
        await S.updateAtom(at[i].atom_id, {srs_step:5, interval_code:'30d', last_eval:'easy',
          answer_count:3, correct_count:3, due_date: now + 24*DAY});
      }
      await M.startSession({ mode:'tree', qIds:[q.q_id], count:1 });
      return q.q_id; }""")
    pg.wait_for_timeout(1200)

    ok("解答画面に選択肢が出ている",
       len(pg.query_selector_all("#choice-list .choice-card")) > 0)

    nums = pg.evaluate("""async (qid) => {
      const at = await window.Storage.getAtomsByQuestion(qid);
      return at.filter(a=>a.is_correct).map(a=>a.original_num); }""", qid)
    for n in nums:
        pg.click('#choice-list .choice-card[data-num="%d"]' % n)
    pg.click("#btn-confirm")
    pg.wait_for_timeout(900)

    ui = pg.evaluate("""() => Array.from(document.querySelectorAll('#rv-choices .cx')).map(el => ({
        num: el.getAttribute('data-num'),
        locked: el.getAttribute('data-locked'),
        evalBtns: el.querySelectorAll('.eval-btn').length,
        lockedPanel: el.querySelectorAll('.eval-locked').length,
        forgotBtn: el.querySelectorAll('.btn-forgot').length,
        text: (el.querySelector('.eval-locked') || {}).textContent || ''
      }))""")
    locked = [x for x in ui if x["locked"] == "1"]
    free = [x for x in ui if x["locked"] == "0"]
    ok("期日前の肢がロック表示になっている（3肢）", len(locked) == 3, json.dumps(ui, ensure_ascii=False))
    ok("期日の肢だけ評価ボタンが出ている（4個）",
       len(free) == 1 and free[0]["evalBtns"] == 4, json.dumps(free, ensure_ascii=False))
    ok("ロックされた肢に評価ボタンは1つも無い",
       bool(locked) and all(x["evalBtns"] == 0 for x in locked), json.dumps(locked, ensure_ascii=False))
    ok("ロックされた肢に説明パネルが出ている",
       bool(locked) and all(x["lockedPanel"] == 1 for x in locked), json.dumps(locked, ensure_ascii=False))
    ok("説明に「仕上がっています」と書いてある",
       bool(locked) and all("仕上がっています" in x["text"] for x in locked))
    ok("説明に次回の日付と残り日数が出ている",
       bool(locked) and all("次回" in x["text"] and "あと" in x["text"] and "日）" in x["text"] for x in locked),
       json.dumps([x["text"] for x in locked], ensure_ascii=False))
    ok("説明に「この回は記録しません」と書いてある",
       bool(locked) and all("この回は記録しません" in x["text"] for x in locked))
    ok("ロックされた肢に「忘れていた」ボタンがある",
       bool(locked) and all(x["forgotBtn"] == 1 for x in locked), json.dumps(locked, ensure_ascii=False))

    dots = pg.evaluate("""() => Array.from(document.querySelectorAll('#tz-summary .sum-dot'))
      .map(d => ({ n:d.getAttribute('data-num'),
                   locked:d.classList.contains('is-locked'),
                   label:d.getAttribute('aria-label') }))""")
    ok("サマリーの丸もロック表示になっている（3個）",
       len([x for x in dots if x["locked"]]) == 3, json.dumps(dots, ensure_ascii=False))
    ok("ロックされた丸の読み上げが理由を説明している",
       bool(dots) and all("期日前" in x["label"] for x in dots if x["locked"]),
       json.dumps(dots, ensure_ascii=False))

    fmt = pg.evaluate("""() => {
      const M=window.Main, DAY=86400000, now=Date.now();
      return { d24: M.fmtDueShort(now + 24*DAY),
               d1 : M.fmtDueShort(now + 25*3600000),
               h5 : M.fmtDueShort(now + 5*3600000),
               nil: M.fmtDueShort(null) }; }""")
    ok("24日先は「（あと24日）」と出る", "（あと24日）" in fmt["d24"], json.dumps(fmt, ensure_ascii=False))
    ok("24時間以内は日ではなく時間で出る", "時間）" in fmt["h5"], json.dumps(fmt, ensure_ascii=False))
    ok("25時間先は日で出る", "日）" in fmt["d1"], json.dumps(fmt, ensure_ascii=False))
    ok("期日が無いときは「未定」", fmt["nil"] == "未定", fmt["nil"])

    guard = pg.evaluate("""() => {
      const M=window.Main;
      const el = document.querySelector('#rv-choices .cx[data-locked="1"]');
      const id = el.getAttribute('data-atom-id');
      M.setEval(id, 'easy');
      const cx = document.querySelector('#rv-choices .cx[data-atom-id="'+id+'"]');
      return { stillLocked: cx.getAttribute('data-locked') === '1',
               noBtn: cx.querySelectorAll('.eval-btn').length === 0 }; }""")
    ok("ロック中の肢は setEval を直接呼んでも変わらない",
       guard["stillLocked"] and guard["noBtn"], json.dumps(guard))

    # 解説エリアはスクロールコンテナなので、headless の click は
    # 「スクロール → 座標決定 → 再スクロール」の競合で隣の要素を叩くことがある。
    # ボタンが実際に押せる位置にあることは別途 assert し、発火は DOM の
    # click イベントで確かめる（アプリ側の委譲ハンドラは同じ経路を通る）。
    reach = pg.evaluate("""() => {
      const b = document.querySelector('#rv-choices .cx[data-locked="1"] .btn-forgot');
      const r = b.getBoundingClientRect();
      const sc = document.querySelector('.rv-scroll').getBoundingClientRect();
      const t = document.elementFromPoint(r.left + r.width/2, r.top + r.height/2);
      return { w: Math.round(r.width), h: Math.round(r.height),
               inView: r.top >= sc.top && r.bottom <= sc.bottom,
               hit: t ? (t.className || t.tagName) : null }; }""")
    ok("「忘れていた」ボタンが実際に押せる大きさで、他の要素に覆われていない",
       reach["hit"] == "btn-forgot" and reach["h"] >= 28 and reach["w"] >= 100,
       json.dumps(reach, ensure_ascii=False))
    pg.eval_on_selector('#rv-choices .cx[data-locked="1"] .btn-forgot',
                        "b => b.dispatchEvent(new MouseEvent('click', {bubbles:true}))")
    pg.wait_for_timeout(500)
    after = pg.evaluate("""() => {
      const dem = document.querySelectorAll('#rv-choices .eval-locked.is-demote');
      return { demoteCount: dem.length, demoteText: dem.length ? dem[0].textContent : '' }; }""")
    ok("「忘れていた」を押すと降格表示に変わる", after["demoteCount"] == 1,
       json.dumps(after, ensure_ascii=False))
    ok("降格表示に「難しい」と10分後が書いてある",
       "難しい" in after["demoteText"] and "10分後" in after["demoteText"], after["demoteText"])

    res = pg.evaluate("""async (qid) => {
      await window.Main.nextQuestion();
      const at = await window.Storage.getAtomsByQuestion(qid);
      return at.map(x=>({n:x.original_num, ic:x.interval_code, ev:x.last_eval, cnt:x.answer_count})); }""",
      qid)
    pg.wait_for_timeout(500)
    ok("「忘れていた」を押した肢と期日の肢の2肢だけが10分後へ",
       len([x for x in res if x["ic"] == "10m"]) == 2, json.dumps(res, ensure_ascii=False))
    ok("押していない2肢は 30日 のまま",
       len([x for x in res if x["ic"] == "30d"]) == 2, json.dumps(res, ensure_ascii=False))

    # ---------- 7. 初見は従来どおり（回帰） ----------
    fresh = pg.evaluate("""async () => {
      const S=window.Storage, K=window.Scheduler;
      const qs = await S.getAllQuestions();
      const q = qs.filter(x=>x.question_type==='single')[1] || qs[1];
      const at = await S.getAtomsByQuestion(q.q_id);
      for (const a of at) {
        await S.updateAtom(a.atom_id, {srs_step:0, interval_code:null, last_eval:null,
          answer_count:0, correct_count:0, due_date:null, last_answered_at:null});
      }
      const a2 = await S.getAtomsByQuestion(q.q_id);
      const cn = a2.filter(x=>x.is_correct).map(x=>x.original_num);
      const rec = K.recommendEvaluations(a2, cn);
      const r = await K.applyQuestionEvaluations(q.q_id,
        a2.map(x=>({atom_id:x.atom_id, eval:rec.recommendations[x.atom_id].eval, is_correct:true})),
        {mode:'new', boundaryHour:4});
      const a3 = await S.getAtomsByQuestion(q.q_id);
      return { skipped: r.results.filter(x=>x.skipped).length,
               ics: a3.map(x=>x.interval_code), cnt: a3.map(x=>x.answer_count) }; }""")
    ok("初見の問題は全肢が記録される（門番が邪魔しない）",
       fresh["skipped"] == 0, json.dumps(fresh, ensure_ascii=False))
    ok("初見・正解なら全肢が1時間後になる",
       all(x == "1h" for x in fresh["ics"]), json.dumps(fresh["ics"]))
    ok("初見の全肢で answer_count が1になる",
       all(x == 1 for x in fresh["cnt"]), json.dumps(fresh["cnt"]))

    # ---------- 8. ガイド文が実装と一致していること ----------
    tips = pg.evaluate("""() => {
      const T = window.Half2Impl.TIPS || null;
      return T ? { next: T.next.text, locked: T.locked ? T.locked.text : null,
                   lockedSel: T.locked ? T.locked.sel : null,
                   order: window.Half2Impl.REVIEW_EXTRA } : null; }""")
    if tips:
        ok("「次へ」の案内が「期日が来ている選択肢だけ」と言っている",
           "期日が来ている選択肢だけ" in tips["next"], tips["next"])
        ok("古い文「触らなかった選択肢は、そのままの評価で保存されます」が消えている",
           "触らなかった選択肢は、そのままの評価で保存されます" not in tips["next"], tips["next"])
        ok("ロック表示を説明するガイドがある", bool(tips["locked"]), str(tips["locked"]))
        ok("そのガイドがロックパネルを指している",
           tips["lockedSel"] == "#rv-choices .eval-locked", str(tips["lockedSel"]))
        ok("ガイドの順番にも組み込まれている",
           tips["order"] and "locked" in tips["order"], json.dumps(tips["order"]))

    ok("ページ例外なし", not errs, " | ".join(errs[:3]))
    br.close()

fails = [r for r in R if not r[0]]
print("\n".join(("  ok  " if c else "  NG  ") + n + (("   << " + d) if (d and not c) else "")
                for c, n, d in R))
print("\n%d 項目中 %d 通過 / %d 失敗" % (len(R), len(R) - len(fails), len(fails)))
sys.exit(1 if fails else 0)
