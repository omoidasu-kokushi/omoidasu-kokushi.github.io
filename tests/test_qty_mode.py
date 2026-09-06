# -*- coding: utf-8 -*-
"""test_qty_mode.py — V2.69 ランダムは「時間で区切る」か「問題数で区切る」の二択

利用者の指摘：
  「ポモドーロと出題数設定は共存させないで。時間指定or出題数指定の2択で、
   どちらもスライダーでざっくり調整できる。その上でポモドーロの25分を
   大々的に推奨する形にする。」

前は「⏲25分間出題（推奨）」のON/OFFと「出題数設定」が同時に生きていて、
**どちらでセッションが終わるのかが決まっていなかった**。
実際に終了条件だったのは問題数だけで、ポモドーロは25分で休憩をすすめるだけ。
表示と実際が食い違っていた。

ここで固定するのは3つ。
  ① 二択になっていて、選んだほうのスライダーだけ出る
  ② 25分のときだけポモドーロの案内が出る
  ③ 時間で区切るときも水増ししない（V2.57と同じ考え）
"""
import json, os, re, sys
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p2 = open(os.path.join(base, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()
cs = open(os.path.join(base, "styles.css"), encoding="utf-8").read()
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()
ix = open(os.path.join(base, "index.html"), encoding="utf-8").read()

ok("二択のセグメントがある", 'id="qty-mode"' in ix and 'data-qmode="time"' in ix and 'data-qmode="count"' in ix)
ok("スライダーが2本ある", 'id="time-range"' in ix and 'id="qty-range"' in ix)
ok("ポモドーロのON/OFFトグルは無くなった", 'id="qty-pomo"' not in ix)
ok("ポモドーロの案内が置いてある", 'id="qty-pomo-reco"' in ix and "25分やって5分休む" in ix)
ok("時間の段は5〜60分", "TIME_STOPS = [5, 10, 15, 25, 40, 60]" in p2)
ok("既定は25分（ポモドーロ）", "TIME_DEFAULT = 25" in p2)
ok("時間で区切るときも水増ししない（見込みの数だけ積む）", "Q_PER_MIN" in p2)
ok("なぜ二択にしたかがコードに書いてある", "同時に生かさない" in p2)
ok("CSSがある", ".qty-pomo-reco{" in cs)
# 時間側だけ track が短く、目盛りとずれていた（実測）。同じ幅にする。
ok("2本のスライダーが同じ幅（目盛りとずれない）",
   "#qty-range, #time-range{ width:100%" in cs)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)

    def snap():
        return pg.evaluate("""() => {
          const H = window.Half2Impl;
          H.refreshQtyMode();
          const t = document.getElementById('qty-time-row');
          const c = document.getElementById('qty-count-row');
          const r = document.getElementById('qty-pomo-reco');
          const on = [...document.querySelectorAll('#qty-mode .seg-btn')]
            .filter(b => b.classList.contains('is-active'))
            .map(b => b.getAttribute('data-qmode'));
          return { time: !t.hidden, count: !c.hidden, reco: !r.hidden, on: on,
                   tv: (document.getElementById('time-range-val')||{}).textContent,
                   cv: (document.getElementById('qty-range-val')||{}).textContent };
        }""")

    pg.evaluate("() => { const s=window.Half2Impl.st.random; s.limit='time'; s.minutes=25; s.count=10; }")
    a = snap()
    ok("時間を選ぶと時間のスライダーだけ出る",
       a["time"] and not a["count"], json.dumps(a, ensure_ascii=False))
    ok("選ばれている側だけが is-active", a["on"] == ["time"], json.dumps(a))
    ok("25分ならポモドーロの案内が出る", a["reco"], json.dumps(a, ensure_ascii=False))
    ok("時間の表示が25分", a["tv"] == "25分", str(a["tv"]))

    pg.evaluate("() => { window.Half2Impl.st.random.minutes = 40; }")
    b = snap()
    ok("25分から外すとポモドーロの案内は引っ込む", b["reco"] is False, json.dumps(b, ensure_ascii=False))
    ok("時間の表示が40分", b["tv"] == "40分", str(b["tv"]))

    pg.evaluate("() => { window.Half2Impl.st.random.limit = 'count'; }")
    c = snap()
    ok("問題数を選ぶと問題数のスライダーだけ出る",
       c["count"] and not c["time"], json.dumps(c, ensure_ascii=False))
    ok("問題数を選ぶとポモドーロの案内は出ない", c["reco"] is False, json.dumps(c, ensure_ascii=False))
    ok("選ばれている側だけが is-active", c["on"] == ["count"], json.dumps(c))
    ok("問題数の表示が10問", c["cv"] == "10問", str(c["cv"]))

    pg.evaluate("() => window.Main.go('random')")
    pg.wait_for_timeout(400)
    w = pg.evaluate("""() => {
      const H = window.Half2Impl;
      H.st.random.limit = 'time'; H.refreshQtyMode();
      const t = document.getElementById('time-range');
      const s = document.querySelector('#qty-time-row .qty-scale');
      const a = t.getBoundingClientRect(), b = s.getBoundingClientRect();
      return { range: Math.round(a.width), scale: Math.round(b.width) };
    }""")
    ok("スライダーの幅と目盛りの幅が揃っている",
       w["range"] > 0 and abs(w["range"] - w["scale"]) <= 2, json.dumps(w))
    ok("JSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
    br.close()

def _vers(txt, pat):
    return sorted(set(re.findall(pat, txt)))
sw_cache = _vers(sw, r"CACHE_NAME = 'v([0-9.]+)'")
sw_q = _vers(sw, r"\?v=([0-9.]+)")
ix_q = _vers(ix, r"\?v=([0-9.]+)")
ix_stamp = _vers(ix, r"Omoidasu_V([0-9.]+)")
ok("index.htmlの?v=が1種類に揃っている", len(ix_q) == 1, str(ix_q))
ok("indexとswの?v=が一致している", ix_q == sw_q, str(ix_q) + " vs " + str(sw_q))
ok("build-stampの版が?v=と一致している",
   len(ix_stamp) == 1 and ix_stamp[0] == ix_q[0], str(ix_stamp))
ok("CACHE_NAMEが?v=と同じ系列", len(sw_cache) == 1 and sw_cache[0] == ix_q[0] + ".0", str(sw_cache))

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  qty_mode" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
