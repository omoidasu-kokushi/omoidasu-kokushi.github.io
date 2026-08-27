#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチAT：OS文字サイズ拡大への耐性（V1.69）

Android/ブラウザの文字サイズ設定はルートフォント（標準16px）を底上げする。
本文（問題文・解説・カード）は rem なので素直に拡大され、下部固定パネル
（サムゾーン）は人間工学上の固定高を守る——その代わり固定高コントロール
内部のフォントは min() で約130%を上限にキャップする、という設計。

V1.69 で実測した崩れ（200%で評価ボタンの「マスター」が2行に折れて縦切れ、
ポモドーロチップも縦切れ）が再発しないことを、CDP Page.setFontSizes で
100% / 150% / 200% を再現して確認する。
"""
import io, json, os, re, sys

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []

def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()

# ---------------------------------------------------------------- 静的検査
css = read("styles.css")

ok("html に -webkit-text-size-adjust:100% がある（勝手なインフレ抑止）",
   "-webkit-text-size-adjust:100%" in css)
ok("評価ボタンの頭文字フォントは min() でキャップされている",
   bool(re.search(r"\.eval-btn b\{ font-size:min\(\.95rem, 20px\)", css)))
ok("評価ボタンの語尾フォントは min() でキャップされている",
   bool(re.search(r"\.eval-btn small\{ font-size:min\(\.72rem, 15px\)", css)))
ok("ポモドーロチップのフォントは min() でキャップされている",
   "font-size:min(var(--fs-xs), 14px)" in css)
# 固定高（サムゾーン設計の根幹）が min-height に化けていない
ok("評価ボタンの固定高34pxが維持されている", ".eval-btn{ height:34px; }" in css)
ok("チップの固定高28pxが維持されている",
   bool(re.search(r"\.pomo-chip\{[^}]*height:28px", css, re.S)))
# ルート/本文が px 固定になっていない（remでOS設定に追従するのが前提）
ok("html に px のフォント固定が無い（OS設定追従の前提）",
   not re.search(r"html\{[^}]*font-size:\s*\d+px", css))

# ---------------------------------------------------------------- 実行時検査
from playwright.sync_api import sync_playwright


# 「2つ選べ」の問題が先頭に来ると、1枚押しただけでは確定が押せない。
# 必要な枚数まで押す（V1.98：ランク当てでキューの中身が変わり、実際に踏んだ）。
def fill_choices(pg):
    pg.evaluate("""() => {
      for (const c of document.querySelectorAll('#choice-list .choice-card')) {
        const b = document.getElementById('btn-confirm');
        if (b && !b.disabled) { break; }
        const body = c.querySelector('.choice-body') || c;
        body.click();
      }
    }""")
    pg.wait_for_selector("#btn-confirm:not([disabled])", timeout=10000)


MEASURE = """() => {
  const clip = [];
  document.querySelectorAll('.eval-btn, #pomodoro-chip, #btn-next, .atom-chip').forEach(el => {
    const rc = el.getBoundingClientRect(); if (!rc.width) return;
    if (el.scrollHeight > el.clientHeight + 2 || el.scrollWidth > el.clientWidth + 2)
      clip.push({ c: (el.id || el.className.toString()).slice(0, 30),
                  sh: el.scrollHeight, ch: el.clientHeight,
                  sw: el.scrollWidth, cw: el.clientWidth });
  });
  const ev = document.querySelector('.eval-btn');
  return { clip: clip.slice(0, 6),
           evalH: ev ? Math.round(ev.getBoundingClientRect().height) : null,
           evalFs: ev ? parseFloat(getComputedStyle(ev.querySelector('b')).fontSize) : null,
           hOver: document.documentElement.scrollWidth - innerWidth };
}"""


def probe(p, scale):
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 375, "height": 667})
    pg = ctx.new_page()
    cdp = ctx.new_cdp_session(pg)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": scale, "fixed": scale}})
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=30000)
    pg.wait_for_timeout(1500)
    try:
        pg.click("#welcome-start", timeout=4000)
    except Exception:
        pass
    pg.wait_for_timeout(1600)
    pg.click("#choice-list .choice-card:nth-child(2) .choice-body")
    fill_choices(pg)
    pg.wait_for_timeout(200)
    pg.click("#btn-confirm")
    pg.wait_for_timeout(900)
    rv = pg.evaluate(MEASURE)
    pg.evaluate("window.Main.go('home')")
    pg.wait_for_timeout(600)
    hm = pg.evaluate("() => document.documentElement.scrollWidth - innerWidth")
    br.close()
    rv["homeHOver"] = hm
    return rv


with sync_playwright() as p:
    base = probe(p, 16)
    ok("100%：固定高コントロールに文字切れが無い", base["clip"] == [],
       json.dumps(base["clip"], ensure_ascii=False))
    ok("100%：評価ボタンは設計どおり34px", base["evalH"] == 34, str(base["evalH"]))
    ok("100%：頭文字は .95rem＝15.2px（キャップが平常時に効いていない）",
       abs((base["evalFs"] or 0) - 15.2) < 0.5, str(base["evalFs"]))
    ok("100%：横スクロールが発生していない",
       base["hOver"] <= 0 and base["homeHOver"] <= 0,
       "rv=%s home=%s" % (base["hOver"], base["homeHOver"]))

    mid = probe(p, 24)
    ok("150%：固定高コントロールに文字切れが無い", mid["clip"] == [],
       json.dumps(mid["clip"], ensure_ascii=False))
    ok("150%：頭文字はキャップ上限20pxで止まる", mid["evalFs"] == 20, str(mid["evalFs"]))
    ok("150%：本文remは拡大している（rootが実際に効いている）",
       mid["evalH"] == 34, str(mid["evalH"]))
    ok("150%：横スクロールが発生していない",
       mid["hOver"] <= 0 and mid["homeHOver"] <= 0,
       "rv=%s home=%s" % (mid["hOver"], mid["homeHOver"]))

    big = probe(p, 32)
    ok("200%：固定高コントロールに文字切れが無い（V1.69で実測した崩れ）",
       big["clip"] == [], json.dumps(big["clip"], ensure_ascii=False))
    ok("200%：評価ボタンの高さは34pxのまま（サムゾーン座標不変）",
       big["evalH"] == 34, str(big["evalH"]))
    ok("200%：横スクロールが発生していない",
       big["hOver"] <= 0 and big["homeHOver"] <= 0,
       "rv=%s home=%s" % (big["hOver"], big["homeHOver"]))

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAT" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
