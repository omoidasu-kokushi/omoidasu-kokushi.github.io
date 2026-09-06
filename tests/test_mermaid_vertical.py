# -*- coding: utf-8 -*-
"""test_mermaid_vertical.py — V2.63 図解を縦に流す

利用者の指摘：
  「図解が ○○⇒××⇒▲▲⇒■■ と横に続いていて、文字が小さすぎて見にくい。
   基本的に縦並びにして、分岐がある場合は横にも展開する形にしたい。」

実測：配布176問の図解22枚のうち18枚が flowchart LR。
横に長い図は幅390pxに収めるため縮小されるので、ノードが増えるほど文字が小さくなる。

このテストで固定するのは2つ。
  ① 倒すのは先頭の向き指定だけ（subgraph の direction / 他の図種は触らない）
  ② 縦にすると実際に文字が大きくなる（見かけのpxで測る）
"""
import json, os, re, sys
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p1 = open(os.path.join(base, "20260815_main_part1_V1.38.js"), encoding="utf-8").read()
st = open(os.path.join(base, "storage.js"), encoding="utf-8").read()
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()
ix = open(os.path.join(base, "index.html"), encoding="utf-8").read()

ok("向きを倒す関数がある", "function toVerticalFlow" in p1)
ok("描くときに通している", "mermaid.render(id, toVerticalFlow(code))" in p1)
ok("保存データは書き換えない（取り込み側にはいない）", "toVerticalFlow" not in st)

CASES = [
    ("flowchart LR\n  A-->B", "flowchart TD", "flowchart LR を倒す"),
    ("graph LR\n  A-->B", "graph TD", "graph LR を倒す"),
    ("graph RL\n  A-->B", "graph TD", "graph RL も倒す"),
    ("flowchart TD\n  A-->B", "flowchart TD", "すでに TD なら触らない"),
    ("graph TB\n  A-->B", "graph TB", "TB は TD に書き換えない"),
    ("graph BT\n  A-->B", "graph BT", "BT は触らない"),
    ("  flowchart LR\n  A-->B", "  flowchart TD", "先頭の空白を保つ"),
    ("sequenceDiagram\n  A->>B: x", "sequenceDiagram", "図種が違えば触らない"),
]

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)

    for src, head, name in CASES:
        got = pg.evaluate(
            "(s) => window.Main.toVerticalFlow(s).split(String.fromCharCode(10))[0]", src)
        ok(name, got == head, "%r -> %r（期待 %r）" % (src.split("\n")[0], got, head))

    sub = pg.evaluate("""() => {
      const s = 'flowchart LR' + String.fromCharCode(10) +
                '  subgraph S' + String.fromCharCode(10) +
                '    direction LR' + String.fromCharCode(10) +
                '    A-->B' + String.fromCharCode(10) + '  end';
      return window.Main.toVerticalFlow(s);
    }""")
    ok("subgraph 内の direction LR は触らない（意図して横に並べている場所）",
       "direction LR" in sub and sub.split("\n")[0] == "flowchart TD", json.dumps(sub))

    stt = pg.evaluate("""() => {
      const s = 'stateDiagram-v2' + String.fromCharCode(10) + '  direction LR';
      return window.Main.toVerticalFlow(s);
    }""")
    ok("stateDiagram の direction LR も触らない", "direction LR" in stt, json.dumps(stt))

    # --- 実測：縦にすると文字が大きくなる ---
    m = pg.evaluate("""async () => {
      const M = window.Main;
      await M.renderMermaid('flowchart TD');
      for (let i = 0; i < 60 && typeof window.mermaid === 'undefined'; i++) {
        await new Promise(r => setTimeout(r, 150));
      }
      if (typeof window.mermaid === 'undefined') { return { skip: true }; }
      const NL = String.fromCharCode(10);
      const code = 'flowchart LR' + NL +
        '  A[蛋白質の代謝] --> B[アンモニア発生]' + NL +
        '  B --> C[肝臓：尿素回路で無毒化]' + NL +
        '  C --> D[尿素]' + NL + '  D --> E[腎臓]' + NL + '  E --> F[尿として排泄]';
      const host = document.createElement('div');
      host.style.cssText = 'position:fixed;left:0;top:0;width:390px;z-index:9999;background:#fff';
      document.body.appendChild(host);
      window.mermaid.initialize({ startOnLoad:false, securityLevel:'strict', theme:'neutral',
        fontFamily: getComputedStyle(document.body).fontFamily,
        flowchart:{ htmlLabels:true, useMaxWidth:true, padding:12, nodeSpacing:34, rankSpacing:40 }});
      const out = {};
      let n = 0;
      for (const [key, src] of [['lr', code], ['td', M.toVerticalFlow(code)]]) {
        const r = await window.mermaid.render('t' + (++n), src);
        host.innerHTML = r.svg || '';
        await new Promise(r2 => setTimeout(r2, 300));
        const svg = host.querySelector('svg');
        const b = svg.getBoundingClientRect();
        const vb = (svg.getAttribute('viewBox') || '0 0 1 1').trim().split(/\s+/);
        const iw = parseFloat(vb[2]) || 1;
        const lab = svg.querySelector('.nodeLabel') || svg.querySelector('text');
        const fs = lab ? parseFloat(getComputedStyle(lab).fontSize) : 0;
        out[key] = { w: Math.round(iw), seen: Math.round(fs * (b.width / iw) * 10) / 10 };
      }
      host.remove();
      return out;
    }""")
    if m.get("skip"):
        ok("（図解の実測は mermaid を読み込めないため省略）", True)
    else:
        ok("横のままだと画面幅に収まらない（縮小がかかる）",
           m["lr"]["w"] > 390, json.dumps(m))
        ok("縦にすると画面幅に収まる（縮小がかからない）",
           m["td"]["w"] <= 390, json.dumps(m))
        ok("見かけの文字が実際に大きくなる（1.5倍以上）",
           m["td"]["seen"] >= m["lr"]["seen"] * 1.5,
           "%.1fpx -> %.1fpx" % (m["lr"]["seen"], m["td"]["seen"]))
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
print("\n%d/%d  mermaid_vertical" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
