#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBS：模試の解禁の見通し（V1.94・判断待ちの「案C」）

【何が起きていたか】
模試の解禁は**解答済みの割合だけ**で決まり、試験日を見ていない。
実測（tools/journey.py・1,359問）では
  1日40問 …… 90日たっても1つも解禁されない
  1日100問 … 50日目に120問フル模試まで解禁
**試験3ヶ月前に始めて1日40問の人は、本番形式の模試を一度も受けられない。**
いちばん試験に近い機能に、いちばん必要な人が届かない。

【ここで直すのは条件ではなく見通し】
解禁条件には**1ミリも触らない**。案A（直前期の緩和）は仕様第11章の数値に
手を入れるので別に判断する。ここでやるのは
**「このペースでは間に合わない」と早く知らせること**だけ。

【楽観側であることを言葉に埋める】
「普通以上◯%」の伸びは正答率次第で読めない。初見で正解すれば全肢[普通]
（§4-3の既定）と仮定して数える。実際は不正解の肢が[難しい]になるぶん遅くなる。
だから文言は必ず「早くても」。断定しない。

【試験日を入れていない人には何も出さない】
「試験日がある」「まだ解禁されていない」「間に合わない」の3つが揃ったときだけ。
"""
import io, json, os, re, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


sc = read("scheduler.js")
html = read("index.html")
css = read("styles.css")
p1 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
j1 = read(p1)

ok("見通しの計算がある", "function forecastUnlock(" in sc)
ok("ペースの見立てがある", "function pacePerDay(" in sc)
ok("進み方の実測がある", "function unlockRate(" in sc)
ok("模型で計算していないと書いてある", "模型で計算しない" in sc)
ok("**解禁条件そのものには触っていない**",
   "need_unique: 0.15" in read("storage.js")
   and "need_unique: 0.35" in read("storage.js")
   and "need_unique: 0.50" in read("storage.js"))
ok("案Aは別扱いだと書いてある", "案A＝直前期の緩和は仕様第11章の数値に" in sc)
ok("楽観側だと書いてある", "楽観側" in j1)
ok("文言は「早くても」", "早くても" in j1)
ok("出す枠がある", 'id="exam-forecast"' in html and ".exam-forecast{" in css)
ok("間に合っている人には出さないと書いてある", "1文字も足さない" in html)
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

    # --- 進み方の実測 ---
    r = pg.evaluate("""() => {
      const K = window.Scheduler, DAY = 86400000;
      const day0 = Math.floor(Date.now() / DAY) * DAY;
      const mk = pcts => ({
        daily_log: pcts.slice(0, -1).map((u, i) => ({
          k: day0 - (pcts.length - 1 - i) * DAY, n:40, w:8, u:u })),
        daily_key: day0, daily_unlock: pcts[pcts.length - 1] });
      return {
        few:  K.unlockRate(mk([0, 1, 2, 3])),              /* 5日ぶんに満たない */
        five: K.unlockRate(mk([0, 1, 2, 3, 4, 5])),        /* 1日1% */
        fast: K.unlockRate(mk([0, 3, 6, 9, 12, 15])),      /* 1日3% */
        flat: K.unlockRate(mk([7, 7, 7, 7, 7, 7])),        /* 進んでいない */
        legacy: K.unlockRate({ daily_log:[1,2,3,4,5,6].map(k=>({k:k,n:40})) })
      };
    }""")
    ok("実測が足りないうちは見立てない", r["few"] is None, json.dumps(r))
    ok("**1日あたり何ポイント進んでいるかを実測する**",
       r["five"]["per_day"] == 1 and r["fast"]["per_day"] == 3, json.dumps(r))
    ok("進んでいなければ0", r["flat"]["per_day"] == 0, json.dumps(r))
    ok("**V1.94より前の記録（uが無い）は使わない**", r["legacy"] is None, json.dumps(r))

    # --- ペースの見立て（文言に出すぶん） ---
    pc = pg.evaluate("""() => {
      const K = window.Scheduler;
      return {
        all: K.pacePerDay({ daily_log:[1,2,3,4,5].map(k=>({k:k,n:40,w:8})) }),
        nw:  K.pacePerDay({ daily_log:[1,2,3,4,5].map(k=>({k:k,n:40,w:8})) }, 'new'),
        legacy: K.pacePerDay({ daily_log:[1,2,3,4,5].map(k=>({k:k,n:40})) }, 'new'),
        few: K.pacePerDay({ daily_log:[1,2,3,4].map(k=>({k:k,n:40,w:8})) }, 'new')
      };
    }""")
    ok("解いた数と、初めて解いた数を別々に見立てられる",
       pc["all"] == 40 and pc["nw"] == 8, json.dumps(pc))
    ok("古い記録には初めて解いた数が無いので見立てない", pc["legacy"] is None, json.dumps(pc))
    ok("実績が5日に満たなければ見立てない", pc["few"] is None, json.dumps(pc))

    # --- 見通しそのもの ---
    f = pg.evaluate("""() => {
      const K = window.Scheduler, DAY = 86400000, now = Date.now();
      const day0 = Math.floor(now / DAY) * DAY;
      const stats = { total_atoms:5448, answered_atoms:0, normal_plus_atoms:0,
                      total_questions:1359 };
      const exam = d => {
        const t = new Date(now + d * DAY);
        return t.getFullYear() + '-' + String(t.getMonth()+1).padStart(2,'0')
             + '-' + String(t.getDate()).padStart(2,'0');
      };
      const mk = (pcts, extra) => Object.assign({
        daily_log: pcts.slice(0, -1).map((u, i) => ({
          k: day0 - (pcts.length - 1 - i) * DAY, n:40, w:8, u:u })),
        daily_key: day0, daily_unlock: pcts[pcts.length - 1] }, extra || {});
      const slowLog = [0,1,2,3,4,5], fastLog = [0,3,6,9,12,15];
      return {
        slow:   K.forecastUnlock(stats, mk(slowLog, { exam_date: exam(90) }), 40, now, 4),
        fast:   K.forecastUnlock(stats, mk(fastLog, { exam_date: exam(90) }), 100, now, 4),
        flat:   K.forecastUnlock(stats, mk([7,7,7,7,7,7], { exam_date: exam(90) }), 40, now, 4),
        noExam: K.forecastUnlock(stats, mk(slowLog, {}), 40, now, 4),
        done:   K.forecastUnlock(stats, mk(slowLog,
                  { exam_date: exam(90), unlock_mock_120:true }), 40, now, 4),
        past:   K.forecastUnlock(stats, mk(slowLog, { exam_date: exam(-5) }), 40, now, 4),
        noHist: K.forecastUnlock(stats, { exam_date: exam(90) }, 40, now, 4),
        few:    K.forecastUnlock({ total_atoms:200, answered_atoms:0, normal_plus_atoms:0,
                                   total_questions:50 },
                  mk(slowLog, { exam_date: exam(90) }), 40, now, 4)
      };
    }""")
    ok("**このペースでは間に合わない、と出る**",
       f["slow"]["show"] is True and f["slow"]["in_time"] is False
       and f["slow"]["over_days"] > 0,
       json.dumps(f["slow"], ensure_ascii=False))
    ok("**間に合っている人には出さない**",
       f["fast"]["show"] is False and f["fast"]["in_time"] is True,
       json.dumps(f["fast"], ensure_ascii=False))
    ok("**何倍の速さが要るかを出す（切り上げ。「1倍」にはしない）**",
       f["slow"]["need_ratio"] >= 1.1, json.dumps(f["slow"], ensure_ascii=False))
    ok("**わずかに足りないときも「1倍」とは書かない**",
       (f["slow"]["need_ratio"] is None) or f["slow"]["need_ratio"] > 1.0,
       json.dumps(f["slow"], ensure_ascii=False))
    ok("**まったく進んでいない人にも黙らない**",
       f["flat"]["show"] is True and f["flat"]["reason"] == "stalled",
       json.dumps(f["flat"], ensure_ascii=False))
    ok("**試験日を入れていない人には出さない**", f["noExam"]["show"] is False,
       json.dumps(f["noExam"], ensure_ascii=False))
    ok("**もう解禁されている人には出さない**", f["done"]["show"] is False,
       json.dumps(f["done"], ensure_ascii=False))
    ok("試験が終わっている人には出さない", f["past"]["show"] is False,
       json.dumps(f["past"], ensure_ascii=False))
    ok("実測が無いうちは出さない", f["noHist"]["show"] is False,
       json.dumps(f["noHist"], ensure_ascii=False))
    ok("問題数が足りないときは、ペースではなく取り込みを促す",
       f["few"]["show"] is True and f["few"]["reason"] == "need_questions"
       and f["few"]["need_questions"] == 70,
       json.dumps(f["few"], ensure_ascii=False))
    ok("**「間に合わなくなる30日以上前」に出る（90日前でもう出ている）**",
       f["slow"]["rest_days"] >= 30 and f["slow"]["show"] is True,
       json.dumps(f["slow"], ensure_ascii=False))

    # --- 画面 ---
    v = pg.evaluate("""async () => {
      const M = window.Main;
      const el = document.getElementById('exam-forecast');
      M.renderExamForecast({ show:true, reason:'too_slow', label:'120問フル模試',
        pace:40, per_day:1, at: Date.now() + 86400000 * 120,
        over_days:30, need_ratio:1.5 });
      const on = { hidden:el.hidden, text:el.textContent };
      M.renderExamForecast({ show:true, reason:'stalled', label:'120問フル模試' });
      const stalled = el.textContent;
      M.renderExamForecast({ show:true, reason:'need_questions',
        label:'120問フル模試', need_questions:70 });
      const few = el.textContent;
      M.renderExamForecast({ show:false });
      const off = el.hidden;
      return { on:on, stalled:stalled, few:few, off:off };
    }""")
    ok("**間に合わないときは文面が出る**",
       v["on"]["hidden"] is False and "早くても" in v["on"]["text"]
       and "1.5倍" in v["on"]["text"],
       json.dumps(v["on"], ensure_ascii=False))
    ok("**復習だけでは進まないことを伝える**",
       "新しい問題" in v["stalled"] and "復習だけでは" in v["stalled"],
       json.dumps(v["stalled"], ensure_ascii=False))
    ok("問題不足のときは取り込みを促す文面になる",
       "70問足りません" in v["few"], json.dumps(v["few"], ensure_ascii=False))
    ok("**出す条件が揃わなければ1文字も出さない**", v["off"] is True, json.dumps(v))

    # --- 通しで：既定の画面には出ない ---
    h = pg.evaluate("""async () => {
      const S = window.Storage, M = window.Main, DAY = 86400000;
      await M.refreshHome();
      const before = document.getElementById('exam-forecast').hidden;
      const y = new Date(Date.now() + DAY * 60);
      const day0 = Math.floor(Date.now() / DAY) * DAY;
      await S.setMeta('exam_date', y.getFullYear() + '-'
        + String(y.getMonth()+1).padStart(2,'0') + '-' + String(y.getDate()).padStart(2,'0'));
      await S.setMeta('daily_log', [0,1,2,3,4].map((u, i) => ({
        k: day0 - (5 - i) * DAY, n:10, w:2, u:u })));
      await S.setMeta('daily_key', day0);
      await S.setMeta('daily_unlock', 5);
      await M.refreshHome();
      const after = { hidden: document.getElementById('exam-forecast').hidden,
                      text: document.getElementById('exam-forecast').textContent };
      await S.setMeta('exam_date', null);
      await S.setMeta('daily_log', []);
      await S.setMeta('daily_unlock', 0);
      await M.refreshHome();
      return { before:before, after:after,
               back: document.getElementById('exam-forecast').hidden };
    }""")
    ok("**試験日が入っていない既定の画面には出ない**", h["before"] is True,
       json.dumps(h, ensure_ascii=False))
    ok("**試験日と遅い進み方を入れると出る**",
       h["after"]["hidden"] is False and "早くても" in h["after"]["text"],
       json.dumps(h["after"], ensure_ascii=False))
    ok("試験日を外せばまた消える", h["back"] is True, json.dumps(h, ensure_ascii=False))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBS" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
