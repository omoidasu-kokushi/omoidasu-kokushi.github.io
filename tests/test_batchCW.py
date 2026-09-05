#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCW：カレンダー書き出しの入口を撤去（V2.28・利用者裁定）
毎日やる前提の復習を予定表に書き出す意味が無い、との裁定。入口だけ撤去し、
.icsコードは残置（バインディングはnull安全なon()なのでエラーにならない）。
"""
import io, os, sys, glob
APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
R = []
def ok(n, c, d=""):
    R.append((bool(c), n, d))
html = io.open(os.path.join(APP, "index.html"), encoding="utf-8").read()
ok("btn-ics の行が無い", 'id="btn-ics"' not in html)
ok("撤去の経緯がコメントで残る", "カレンダー書き出し（V1.51）は撤去" in html)
ok("印刷・レポートの隣接行は無事", 'id="btn-note-print"' in html and 'id="btn-report-print"' in html)
from playwright.sync_api import sync_playwright
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(800)
    ok("起動エラーなし（外したバインディングが落ちない）", not errs, str(errs[:2]))
    br.close()
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchCW" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
