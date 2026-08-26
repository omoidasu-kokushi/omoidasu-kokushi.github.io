#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.63 検証：ヘッダーのタイマーが崩れないこと ＆ 片手で押せる当たり判定"""
import json, os, sys, io
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))
def read(f): return io.open(os.path.join(APP, f), encoding="utf-8").read()

css = read("styles.css")
ok("タイマーのON/OFFに幅を焼いていない",
   "width:auto; min-width:34px; height:24px;" in css)
ok("タイマーの文字を折り返さない", ".pomo-toggle-text{" in css and "white-space:nowrap" in css)
ok("当たり判定は透明（見た目を変えない）",
   "background:transparent;      /* 見えない。押せるだけ */" in css)

UNTIL = """const until = async (f, ms) => { const t = Date.now();
  while (!f() && Date.now() - t < (ms || 8000)) await new Promise(r => setTimeout(r, 50)); };
"""

TO_REVIEW = """async () => {
  const M = window.Main;
  """ + UNTIL + """
  await M.startSession({ mode:'random', count:3 });
  await until(() => { const c = document.querySelector('#choice-list .choice-card');
    return c && getComputedStyle(c).pointerEvents !== 'none'; });
  /* 「2つ選べ」の問題が先頭に来ることがある。1枚だけ押すと
     確定が押せないまま止まる。必要な枚数まで押す（V1.89）。 */
  for (const c of document.querySelectorAll('#choice-list .choice-card')) {
    const b = document.getElementById('btn-confirm');
    if (b && !b.disabled) { break; }
    c.click();
  }
  await until(() => { const b = document.getElementById('btn-confirm'); return b && !b.disabled; });
  document.getElementById('btn-confirm').click();
  await until(() => document.getElementById('screen-quiz')
                      .getAttribute('data-phase') === 'review');
  return true;
}"""


def _external(t):
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t)


HIT = """() => {
  const sels = ['#q-star','#rv-star','#rv-stem-expand','.sum-dot','.cx-write',
                '.tag-pill','.help-btn','#pomodoro-toggle'];
  const boxes = [], areas = [], overlaps = [];
  document.querySelectorAll(sels.join(',')).forEach(el => {
    if (getComputedStyle(el).display === 'none') { return; }
    const b = el.getBoundingClientRect();
    if (!b.width || !b.height) { return; }
    const a = getComputedStyle(el, '::after');
    const px = v => parseFloat(v) || 0;
    const t = px(a.top), bo = px(a.bottom), l = px(a.left), r = px(a.right);
    /* 固定パネルと、その下を流れる本文は別の層。本文は隠れていて
       押せないので、重なりとして数えない。 */
    const fixed = !!(el.closest('.tz-summary') || el.closest('#tz-fixed')
                     || el.closest('.thumb-zone') || el.closest('.app-header'));
    const id = el.id || String(el.className).split(' ')[0];
    boxes.push({ id, layer: fixed ? 'fixed' : 'flow',
                 x: b.left + l, y: b.top + t, w: b.width - l - r, h: b.height - t - bo });
    areas.push({ id, visH: Math.round(b.height), hitH: Math.round(b.height - t - bo),
                 hitW: Math.round(b.width - l - r) });
  });
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], b = boxes[j];
      if (a.layer !== b.layer) { continue; }
      const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
      const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
      if (ox > 1 && oy > 1) { overlaps.push({ a: a.id, b: b.id,
        ox: Math.round(ox), oy: Math.round(oy) }); }
    }
  }
  return { areas, overlaps };
}"""


def runtime_checks():
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox"])
        errs = []
        for w in (320, 375, 390, 430):
            pg = br.new_context(viewport={"width": w, "height": 844}).new_page()
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append("console:" + m.text)
                  if m.type == "error" and not _external(m.text) else None)
            pg.goto(URL, wait_until="load")
            pg.wait_for_function("window.__APP_READY === true", timeout=30000)
            pg.wait_for_timeout(900)
            try: pg.click("#welcome-start", timeout=2500)
            except Exception: pass
            pg.wait_for_timeout(400)
            pg.evaluate(TO_REVIEW)
            pg.wait_for_timeout(600)

            # ---------- ヘッダーのタイマー ----------
            r = pg.evaluate("""() => {
              const t = document.getElementById('pomodoro-toggle');
              const b = t.getBoundingClientRect();
              const txt = document.querySelector('.pomo-toggle-text');
              const st = document.querySelector('.pomo-toggle-state');
              const rect = e => { if (!e) { return null; }
                const r = e.getBoundingClientRect();
                return { w: Math.round(r.width), h: Math.round(r.height) }; };
              const de = document.documentElement;
              /* 枠そのものの scrollHeight は見ない。当たり判定の ::after が
                 わざと枠の外へ出ているので、それを「はみ出し」と数えてしまう。
                 見たいのは【中の文字が縦に折り返していないか】。 */
              const inner = [...t.children].reduce((m, e) =>
                Math.max(m, e.getBoundingClientRect().height), 0);
              return { h: Math.round(b.height), innerH: Math.round(inner),
                       textShown: txt ? getComputedStyle(txt).display !== 'none' : false,
                       text: rect(txt), state: rect(st),
                       docOverflow: de.scrollWidth > de.clientWidth };
            }""")
            ok("%dpx：タイマーの文字が枠からはみ出さない（V1.62までは縦に折り返していた）" % w,
               r["innerH"] <= r["h"], json.dumps(r))
            if r["textShown"]:
                ok("%dpx：タイマーの文字が横1行に収まる" % w,
                   r["text"]["w"] > r["text"]["h"] * 2, json.dumps(r))
            ok("%dpx：横スクロールが出ない" % w, r["docOverflow"] is False, json.dumps(r))

            # ---------- 当たり判定 ----------
            r = pg.evaluate(HIT)
            small = [a for a in r["areas"] if a["hitH"] < 36]
            ok("%dpx：押せる部品の当たり判定が36px以上ある" % w,
               not small, json.dumps(small, ensure_ascii=False))
            ok("%dpx：当たり判定どうしが重ならない（押し間違いのすり替えを作らない）" % w,
               not r["overlaps"], json.dumps(r["overlaps"], ensure_ascii=False))
            ok("%dpx：見た目の大きさは変えていない" % w,
               any(a["visH"] <= 20 for a in r["areas"]),
               json.dumps([a for a in r["areas"] if a["visH"] <= 20][:2]))
            pg.close()

        # ---------- 広げた当たり判定が実際に効くか（機能で確かめる） ----------
        pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(URL, wait_until="load")
        pg.wait_for_function("window.__APP_READY === true", timeout=30000)
        pg.wait_for_timeout(900)
        try: pg.click("#welcome-start", timeout=2500)
        except Exception: pass
        pg.wait_for_timeout(400)
        pg.evaluate(TO_REVIEW)
        pg.wait_for_timeout(700)
        # 覆いが開いたままだと elementFromPoint が覆いを返す。片付けてから測る。
        pg.evaluate("() => window.Main.closeModals()")
        pg.wait_for_timeout(400)

        # 広げた当たり判定が、下の評価ボタンを覆っていないこと。
        # **他の操作より先に測る。** あとで測ると、途中の操作で画面が
        # 滑って評価ボタンが画面外へ出てしまい、覆われているのか
        # 見えていないだけなのか区別が付かない（実際に区別が付かなかった）。
        r = pg.evaluate("""() => {
          const btns = [...document.querySelectorAll('.eval-btn')];
          if (!btns.length) { return { skip: true }; }
          /* 覆っていても設計どおりのもの。ここを除かないと、
             「自分の当たり判定が覆った」のか「元々そういう作り」なのか
             区別が付かない（実際に付かなかった）。
               .onb-layer  … ガイドの吹き出し（わざと前に出る）
               #toast      … 数秒で消える通知
               .thumb-zone … 固定パネル。本文はこの下を流れる設計 */
          const byDesign = el => !!(el.closest && (el.closest('.onb-layer')
                                 || el.closest('#toast') || el.closest('.toast')));
          const panel = document.querySelector('.thumb-zone');
          const pb = panel ? panel.getBoundingClientRect() : null;
          const out = [];
          btns.forEach(el => {
            const b = el.getBoundingClientRect();
            if (!b.width || !b.height) { return; }
            const cx = b.left + b.width / 2, cy = b.top + b.height / 2;
            if (cy < 0 || cy > window.innerHeight) { return; }
            if (pb && pb.height && !el.closest('.thumb-zone') && cy > pb.top - 2) { return; }
            const hit = document.elementFromPoint(cx, cy);
            if (hit && byDesign(hit)) { return; }
            out.push({ id: String(el.className).split(' ')[1] || 'eval',
                       y: Math.round(b.top),
                       reachable: !!(hit && (hit === el || el.contains(hit))) });
          });
          return { list: out };
        }""")
        if not r.get("skip") and r["list"]:
            ok("評価ボタンが覆われていない（押し間違えると評価が変わるので致命的）",
               all(x["reachable"] for x in r["list"]),
               json.dumps(r["list"], ensure_ascii=False))

        # ★を「見た目の外・当たり判定の内」で押す
        r = pg.evaluate("""() => {
          const el = document.getElementById('rv-star');
          const b = el.getBoundingClientRect();
          const before = el.getAttribute('aria-pressed');
          /* 見た目の上端より 6px 上＝広げた当たり判定の中 */
          const x = b.left + b.width / 2, y = b.top - 6;
          const hit = document.elementFromPoint(x, y);
          return { before, inside: !!(hit && (hit === el || el.contains(hit))),
                   hitId: hit ? (hit.id || hit.tagName) : null };
        }""")
        ok("★は見た目の外側でも押せる（当たり判定が効いている）",
           r["inside"] is True, json.dumps(r, ensure_ascii=False))

        # 肢セレクターを、広げた当たり判定の位置で【本物のクリック】で押す。
        # 委譲（#tz-summary で closest('.sum-dot')）に届くかを見る。
        # ::after は要素の一部なので、広げた場所を押しても
        # event.target はボタンそのものになる——それを確かめる。
        r = pg.evaluate("""() => {
          window.__hitTarget = null;
          document.getElementById('tz-summary').addEventListener('click', (e) => {
            const d = e.target.closest && e.target.closest('.sum-dot');
            window.__hitTarget = d ? d.getAttribute('data-num') : ('NO:' + e.target.tagName);
          }, true);
          const dots = [...document.querySelectorAll('.sum-dot')];
          if (dots.length < 2) { return { skip: true }; }
          const t = dots[1].getBoundingClientRect();
          return { x: Math.round(t.left + t.width / 2), y: Math.round(t.top - 8),
                   num: dots[1].getAttribute('data-num'), n: dots.length };
        }""")
        if not r.get("skip"):
            pg.mouse.click(r["x"], r["y"])
            pg.wait_for_timeout(400)
            got = pg.evaluate("window.__hitTarget")
            ok("肢セレクターは見た目の外側を押しても、その肢として届く",
               got == r["num"], json.dumps({"expected": r["num"], "got": got}))

        # ---------- ひとこと欄の送りは題と同じ行（V1.65） ----------
        r = pg.evaluate("""async () => {
          const M = window.Main, H = window.Half2Impl;
          M.closeModals(); await M.go('home', { replace: true });
          const tip = document.getElementById('home-tip');
          tip.hidden = false;
          if (H.renderHomeTips) { await H.renderHomeTips(); }
          await new Promise(r => setTimeout(r, 350));
          const B = s => { const e = document.querySelector(s); if (!e) return null;
            const b = e.getBoundingClientRect();
            return { x: Math.round(b.left), y: Math.round(b.top),
                     w: Math.round(b.width), h: Math.round(b.height) }; };
          const head = B('.home-tip-head'), prev = B('#home-tip-prev'),
                cnt = B('#home-tip-count'), next = B('#home-tip-next');
          const inRow = el => el && head && el.y >= head.y - 2
                          && (el.y + el.h) <= (head.y + head.h + 2);
          const before = document.getElementById('home-tip-count').textContent;
          document.getElementById('home-tip-next').click();
          await new Promise(r => setTimeout(r, 300));
          const after = document.getElementById('home-tip-count').textContent;
          return { sameRow: inRow(prev) && inRow(cnt) && inRow(next),
                   order: prev && cnt && next && prev.x < cnt.x && cnt.x < next.x,
                   prevH: prev ? prev.h : 0, nextH: next ? next.h : 0,
                   navGone: !document.querySelector('.home-tip-nav'),
                   moved: before !== after };
        }""")
        ok("ひとこと欄：前へ・数・次へが題と同じ行にある",
           r["sameRow"] is True and r["order"] is True, json.dumps(r))
        ok("ひとこと欄：送りボタンの高さが34px以上ある",
           r["prevH"] >= 34 and r["nextH"] >= 34, json.dumps(r))
        ok("ひとこと欄：下段の旧ナビは残っていない", r["navGone"] is True, json.dumps(r))
        ok("ひとこと欄：移設しても送りが機能する", r["moved"] is True, json.dumps(r))

        ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
        br.close()


runtime_checks()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAP" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
