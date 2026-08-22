#!/usr/bin/env python3
"""起動スモークテスト：http:// 経由で index.html を開き、
   __APP_READY / 依存モジュール / コンソールエラー / 初期画面を確認する。"""
import json, sys
from playwright.sync_api import sync_playwright

import os
URL = os.environ.get("APP_URL", "http://127.0.0.1:8899/index.html")

def run():
    out = {"console_errors": [], "page_errors": []}
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox"])
        ctx = br.new_context(viewport={"width": 390, "height": 844},
                             user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15")
        pg = ctx.new_page()
        pg.on("console", lambda m: out["console_errors"].append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: out["page_errors"].append(str(e)))
        pg.goto(URL, wait_until="load")
        try:
            pg.wait_for_function("window.__APP_READY === true", timeout=15000)
            out["app_ready"] = True
        except Exception as e:
            out["app_ready"] = False
            out["ready_error"] = str(e)

        out["modules"] = pg.evaluate("""() => ({
            questions : !!(window.CONCEPT_TAGS_MASTER && window.CONCEPT_TAGS_MASTER.length),
            storage   : !!(window.Storage && window.Storage.APP_BUILD),
            scheduler : !!(window.Scheduler && window.Scheduler.APP_BUILD),
            part1     : !!(window.Main && window.Main.APP_BUILD),
            part2     : !!(window.Half2Impl && window.Half2Impl.openSettings),
            eventsBound : !!window.__EVENTS_BOUND,
            half2Bound  : !!window.__HALF2_BOUND,
            bootError   : window.__BOOT_ERROR || null
        })""")
        out["diag_panel_shown"] = pg.evaluate("!!document.getElementById('boot-diagnostics')")
        pg.wait_for_timeout(2500)
        out["counts"] = pg.evaluate("""async () => ({
            questions: await window.Storage.countQuestions(),
            atoms    : await window.Storage.countAtoms(),
            tags     : window.CONCEPT_TAGS_MASTER.length
        })""")
        out["screen"] = pg.evaluate("window.Main.state.screen")
        out["visible_modal"] = pg.evaluate(
            """() => { var m = document.querySelector('#modal-layer > .modal-card:not([hidden])');
                       return m ? m.id : null; }""")
        pg.screenshot(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "shot_boot.png"), full_page=False)
        br.close()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("app_ready") and not out["page_errors"] else 1

sys.exit(run())
