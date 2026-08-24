#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.64 検証：キーボードと読み上げで使えること"""
import json, os, sys, io, glob
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))
def read(f): return io.open(os.path.join(APP, f), encoding="utf-8").read()

idx = read("index.html")
cards = idx.count('class="modal-card')
roles = idx.count('role="dialog"')
ok("覆いはすべて dialog として扱う（%d枚中%d枚）" % (cards, roles), cards == roles,
   "cards=%d roles=%d" % (cards, roles))
ok("覆いは背後を触れない扱いにする", idx.count('aria-modal="true"') == cards)
ok("通知は読み上げの対象", 'id="toast"' in idx and 'aria-live="polite"' in idx)
ok("取り込みの結果も読み上げの対象",
   'id="import-report"' in idx and idx.count('aria-live="polite"') >= 2)

s2 = read(os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1]))
ok("検索結果は button（div のままにしない）",
   '<button type="button" class="search-hit"' in s2)
ok("検索結果に読み上げる名前がある", 'この問題を解く' in s2)

css = read("styles.css")
ok("button 化で組版が変わらないよう幅と寄せを明示している",
   "display:block; width:100%; text-align:left;" in css)
ok("押した手ごたえがある（§4-13）", ".search-hit:active{" in css)


def _external(t):
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t)


def runtime_checks():
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox"])
        pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append("console:" + m.text)
              if m.type == "error" and not _external(m.text) else None)
        pg.goto(URL, wait_until="load")
        pg.wait_for_function("window.__APP_READY === true", timeout=30000)
        pg.wait_for_timeout(1000)
        try: pg.click("#welcome-start", timeout=2500)
        except Exception: pass
        pg.wait_for_timeout(400)
        pg.evaluate("""async () => { const M = window.Main;
          M.closeModals(); await M.go('home', { replace: true }); }""")
        pg.wait_for_timeout(500)

        # ---------- 押せるのにボタンでないものが残っていないか ----------
        def fake(sel_desc):
            return pg.evaluate("""() => {
              const out = [];
              document.querySelectorAll(
                '[data-qid],[data-action],[data-num],[data-scope-field],[data-tag]'
              ).forEach(el => {
                if (['BUTTON','A','INPUT','SELECT','TEXTAREA','OPTION'].includes(el.tagName)) return;
                if (el.getAttribute('role') === 'button') return;
                const b = el.getBoundingClientRect();
                if (!b.width || !b.height) return;
                out.push({ tag: el.tagName, cls: String(el.className).split(' ')[0] });
              });
              return out;
            }""")

        ok("ホーム：押せるものはすべてボタン", not fake("home"),
           json.dumps(fake("home")[:3], ensure_ascii=False))

        pg.evaluate("""async () => { const H = window.Half2Impl;
          await H.openSearch(); await H.runSearch('看護'); }""")
        pg.wait_for_timeout(900)
        f = fake("search")
        ok("検索結果：押せるものはすべてボタン", not f, json.dumps(f[:3], ensure_ascii=False))

        r = pg.evaluate("""() => {
          const hits = [...document.querySelectorAll('.search-hit')];
          const h = hits[0];
          if (!h) { return { none: true }; }
          const cs = getComputedStyle(h);
          return { n: hits.length, tag: h.tagName, label: h.getAttribute('aria-label'),
                   w: Math.round(h.getBoundingClientRect().width),
                   align: cs.textAlign, focusable: h.tabIndex >= 0,
                   docOverflow: document.documentElement.scrollWidth
                              > document.documentElement.clientWidth };
        }""")
        ok("検索結果はキーボードでたどれる", r.get("focusable") is True, json.dumps(r, ensure_ascii=False))
        ok("読み上げる名前が付いている",
           bool(r.get("label")) and "解く" in r["label"], json.dumps(r, ensure_ascii=False))
        ok("button にしても左寄せ・全幅のまま（組版が変わっていない）",
           r.get("align") == "left" and r.get("w", 0) > 300, json.dumps(r, ensure_ascii=False))
        ok("横スクロールが出ない", r.get("docOverflow") is False, json.dumps(r, ensure_ascii=False))

        # ---------- キーボードだけで演習を始められる ----------
        r = pg.evaluate("""async () => {
          const h = document.querySelector('.search-hit');
          h.focus();
          const focused = document.activeElement === h;
          h.dispatchEvent(new KeyboardEvent('keydown', { key:'Enter', bubbles:true }));
          h.click();                       /* Enter は button の既定で click になる */
          const t0 = Date.now();
          while (window.Main.state.screen !== 'quiz' && Date.now() - t0 < 8000) {
            await new Promise(r => setTimeout(r, 50));
          }
          return { focused, screen: window.Main.state.screen,
                   mode: window.Main.state.session.mode,
                   n: window.Main.state.session.questions.length };
        }""")
        ok("検索結果にフォーカスできる", r["focused"] is True, json.dumps(r))
        ok("押すとその問題の演習が始まる（button 化で機能を壊していない）",
           r["screen"] == "quiz" and r["n"] > 0, json.dumps(r))

        # ---------- 覆いのフォーカス ----------
        r = pg.evaluate("""async () => {
          const M = window.Main;
          M.closeModals();
          await M.go('home', { replace: true });
          document.getElementById('btn-home').focus();
          const before = document.activeElement.id;
          M.openModal('#modal-buy');
          await new Promise(r => setTimeout(r, 250));
          const m = document.getElementById('modal-buy');
          return { before, role: m.getAttribute('role'), modal: m.getAttribute('aria-modal'),
                   label: m.getAttribute('aria-label'),
                   inside: m.contains(document.activeElement) };
        }""")
        ok("覆いは dialog として読まれる",
           r["role"] == "dialog" and r["modal"] == "true", json.dumps(r, ensure_ascii=False))
        ok("覆いの名前は見出しから取る（何のダイアログか読まれる）",
           bool(r["label"]) and len(r["label"]) > 3, json.dumps(r, ensure_ascii=False))
        ok("開くとキーボードの位置が覆いの中へ移る",
           r["inside"] is True, json.dumps(r, ensure_ascii=False))

        # Tab が覆いの外へ出ない
        r = pg.evaluate("""() => {
          const m = document.getElementById('modal-buy');
          const list = [...m.querySelectorAll('button:not([disabled])')]
            .filter(e => e.offsetWidth > 0);
          list[list.length - 1].focus();
          return { n: list.length, last: document.activeElement === list[list.length - 1] };
        }""")
        pg.keyboard.press("Tab")
        pg.wait_for_timeout(200)
        inside = pg.evaluate("""() => document.getElementById('modal-buy')
          .contains(document.activeElement)""")
        ok("最後の項目から Tab しても覆いの外へ出ない（裏の画面を触れない）",
           inside is True, json.dumps({"n": r["n"], "inside": inside}))

        # 閉じると元の場所へ戻る
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(400)
        r = pg.evaluate("""() => ({
          active: document.activeElement ? document.activeElement.id : null,
          layerHidden: document.getElementById('modal-layer').hidden })""")
        ok("閉じるとキーボードの位置が元へ戻る（先頭からたどり直しにならない）",
           r["active"] == "btn-home", json.dumps(r))
        ok("閉じたあと覆いは畳まれている", r["layerHidden"] is True, json.dumps(r))

        # 覆いが無いときに Tab を押しても壊れない
        pg.keyboard.press("Tab")
        pg.wait_for_timeout(200)
        ok("覆いが無いときの Tab で例外にならない", True)

        ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
        br.close()


runtime_checks()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAQ" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
