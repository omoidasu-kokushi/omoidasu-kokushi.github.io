# -*- coding: utf-8 -*-
"""test_bessatsu_image.py — V2.65 別冊の線画を同梱する

【裁定 2026-09-06】厚労省作成の線画・図表は「出典：第○回看護師国家試験 別冊」を
明記して使用してよい。X線・臨床写真など写真系は転載しない。

別冊に図がある9問を実際に見て仕分けた。
  使用可（線画・図表）4問 … 心電図2件・トリアージタッグ・病室の模式図
  転載しない（写真）5問 … 腕の写真・MRI/X線/冠動脈造影・便・胸部CT・物品

ここで固定するのは3つ。
  ① 同梱するのは4枚だけ（写真を足していない）
  ② CORE ではなく OPTIONAL に置く（取れなくてもアプリは起動する）
  ③ image_url があれば画像アコーディオンが出る
"""
import json, os, re, sys
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()
ix = open(os.path.join(base, "index.html"), encoding="utf-8").read()
p1 = open(os.path.join(base, "20260815_main_part1_V1.38.js"), encoding="utf-8").read()

IMGS = ["111_am81.png", "113_am23.png", "114_am13.png", "114_am107.png"]
d = os.path.join(base, "images", "bessatsu")
ok("画像フォルダがある", os.path.isdir(d))
have = sorted(os.listdir(d)) if os.path.isdir(d) else []
ok("同梱は4枚だけ（写真を足していない）", have == sorted(IMGS), str(have))

size = sum(os.path.getsize(os.path.join(d, f)) for f in have) if have else 0
ok("4枚あわせて400KB未満（線画なので色数を落としてある）",
   0 < size < 400 * 1024, "%dKB" % (size // 1024))

# --- V2.66：選択肢が図の問題（本体の問題PDFから切り出した線画） ---
SEN = ["112_am57.png", "112_pm95.png", "113_am110.png", "113_am46.png", "113_pm21.png",
       "113_pm37.png", "113_pm54.png", "113_pm66.png", "114_am39.png", "114_am41.png",
       "115_am16.png", "115_am22.png"]
d2 = os.path.join(base, "images", "sentakushi")
ok("選択肢画像のフォルダがある", os.path.isdir(d2))
have2 = sorted(os.listdir(d2)) if os.path.isdir(d2) else []
ok("選択肢画像は12枚", have2 == sorted(SEN), str(have2))
size2 = sum(os.path.getsize(os.path.join(d2, f)) for f in have2) if have2 else 0
ok("選択肢画像は800KB未満", 0 < size2 < 800 * 1024, "%dKB" % (size2 // 1024))
ok("画像はぜんぶで1.2MB未満（PWAの配布物に載せる）",
   (size + size2) < 1200 * 1024, "%dKB" % ((size + size2) // 1024))
for f in SEN:
    ok("sw.js が sentakushi/%s をキャッシュする" % f, ("./images/sentakushi/" + f) in sw)
ok("選択肢画像も CORE に入れない", "sentakushi" not in (sw.split("CORE_ASSETS")[1].split("]")[0]
                                                       if "CORE_ASSETS" in sw else ""))

for f in IMGS:
    ok("sw.js が %s をキャッシュする" % f, ("./images/bessatsu/" + f) in sw)

core = sw.split("CORE_ASSETS")[1].split("]")[0] if "CORE_ASSETS" in sw else ""
ok("別冊画像は CORE に入れない（1件でも取れないとインストールごと失敗するため）",
   "bessatsu" not in core)
opt = sw.split("OPTIONAL_ASSETS")[1].split("]")[0] if "OPTIONAL_ASSETS" in sw else ""
ok("別冊画像は OPTIONAL に入れる（無くても本体は動く）",
   opt.count("bessatsu") == 4, str(opt.count("bessatsu")))
ok("なぜ OPTIONAL なのかがコードに書いてある", "オフライン動作が丸ごと死ぬ" in sw)

ok("画像アコーディオンの仕組みがある", "function renderImageAccordion" in p1)
ok("image_url が無ければ出さない", "if (!q.image_url) { wrap.hidden = true; return; }" in p1)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)

    got = pg.evaluate("""async (list) => {
      const out = {};
      for (const f of list) {
        try {
          const r = await fetch('images/bessatsu/' + f);
          const b = r.ok ? await r.blob() : null;
          out[f] = { status: r.status, type: b ? b.type : null, size: b ? b.size : 0 };
        } catch (e) { out[f] = { err: String(e).slice(0, 60) }; }
      }
      return out;
    }""", IMGS)
    for f in IMGS:
        g = got.get(f, {})
        ok("%s が配信されている（PNG）" % f,
           g.get("status") == 200 and (g.get("type") or "").startswith("image/") and g.get("size", 0) > 1000,
           json.dumps(g))

    acc = pg.evaluate("""() => {
      const M = window.Main;
      M.renderImageAccordion({ image_url: 'images/bessatsu/113_am23.png' });
      const w = document.getElementById('q-image-wrap');
      const i = document.getElementById('q-image');
      const on = { hidden: !!w.hidden, src: i ? i.getAttribute('src') : null };
      M.renderImageAccordion({ image_url: null });
      return { on: on, offHidden: !!w.hidden };
    }""")
    ok("image_url があるとアコーディオンが出る",
       acc["on"]["hidden"] is False and "113_am23" in (acc["on"]["src"] or ""),
       json.dumps(acc, ensure_ascii=False))
    ok("image_url が無いと出さない", acc["offHidden"], json.dumps(acc))
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
print("\n%d/%d  bessatsu_image" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
