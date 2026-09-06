# -*- coding: utf-8 -*-
"""test_exp_button_size.py — V2.53 「解説を見る」を評価ボタンと押し間違えない

直す前の実測（390px 幅）：
  解説を見る  x=60 w=77 h=24
  評価ボタン  y=250 h=34   → 隙間は 4px
指で押すと「難しい」に当たる。評価は忘却スケジュールを直接動かすので、
誤タップの代償が大きい。幅いっぱい・44px・上下に余白を置く。
"""
import json, os, re, subprocess, sys, time
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
css = open(os.path.join(base, "styles.css"), encoding="utf-8").read()
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()
ix = open(os.path.join(base, "index.html"), encoding="utf-8").read()

ok("解説ボタンの寸法指定がある", "min-height:44px" in css)
ok("評価ボタンとの余白を確保している", ".cx .cx-exp{ margin:8px 0 12px; }" in css)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    r = pg.evaluate("""() => {
      const host = document.createElement('div');
      host.className = 'cx';
      host.style.cssText = 'width:340px;position:fixed;left:0;top:0;z-index:99999';
      host.innerHTML =
        '<details class="cx-exp"><summary>解説を見る</summary>' +
        '<div class="explanation-body">本文</div></details>' +
        '<div class="cx-eval"><button class="eval-btn eval-hard"><b>難しい</b></button></div>';
      document.body.appendChild(host);
      const sm = host.querySelector('summary');
      const cs = getComputedStyle(sm);
      const ce = getComputedStyle(host.querySelector('.cx-exp'));
      const rs = sm.getBoundingClientRect();
      const rb = host.querySelector('.eval-btn').getBoundingClientRect();
      const out = { h: Math.round(rs.height), w: Math.round(rs.width),
                    hostW: Math.round(host.getBoundingClientRect().width),
                    mt: ce.marginTop, mb: ce.marginBottom,
                    gap: Math.round(rb.top - rs.bottom), display: cs.display };
      host.remove();
      return out;
    }""")
    ok("高さが44px以上（指のタップ目標）", r["h"] >= 44, json.dumps(r))
    ok("幅が親の8割以上（横いっぱいに広がる）",
       r["w"] >= r["hostW"] * 0.8, json.dumps(r))
    ok("評価ボタンとの隙間が10px以上", r["gap"] >= 10, json.dumps(r))
    ok("上にも余白がある（上のボタンとくっつかない）",
       r["mt"] not in ("0px", "1px", "2px"), json.dumps(r))
    ok("インラインではなく帯として並ぶ", r["display"] == "flex", json.dumps(r))
    br.close()

# --- 版は決め打ちしない（版は毎回上がる）。互いに一致しているかだけ見る ---
def _vers(txt, pat):
    return sorted(set(re.findall(pat, txt)))
sw_cache = _vers(sw, r"CACHE_NAME = 'v([0-9.]+)'")
sw_q     = _vers(sw, r"\?v=([0-9.]+)")
ix_q     = _vers(ix, r"\?v=([0-9.]+)")
ix_stamp = _vers(ix, r"Omoidasu_V([0-9.]+)")
ok("index.htmlの?v=が1種類に揃っている", len(ix_q) == 1, str(ix_q))
ok("indexとswの?v=が一致している", ix_q == sw_q, str(ix_q) + " vs " + str(sw_q))
ok("build-stampの版が?v=と一致している",
   len(ix_stamp) == 1 and ix_stamp[0] == ix_q[0], str(ix_stamp) + " vs " + str(ix_q))
ok("CACHE_NAMEが?v=と同じ系列（v<版>.0）",
   len(sw_cache) == 1 and sw_cache[0] == ix_q[0] + ".0", str(sw_cache))

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  exp_button_size" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
