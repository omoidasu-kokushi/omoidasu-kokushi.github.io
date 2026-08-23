#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.55 検証：取り消せない操作の共通確認 ＆ Escape で覆いが畳めること"""
import json, os, sys, subprocess, io, glob
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))
def read(f): return io.open(os.path.join(APP, f), encoding="utf-8").read()

P1 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
P2 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
for f in [P1, P2]:
    p = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True)
    ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

idx = read("index.html")
ok("共通の確認モーダルがある", 'id="modal-confirm"' in idx)
ok("確認モーダルに［やめる］がある", 'id="modal-confirm"' in idx and "data-close" in idx)
ok("実行ボタンが危険色", 'id="confirm-go"' in idx and 'is-danger' in idx)

s1, s2 = read(P1), read(P2)
ok("図の削除が確認を通る", "confirmAction({" in s1 and "この図を消しますか" in s1)
ok("文言の一括リセットが確認を通る", "すべて元の文に戻しますか" in s2)
ok("音の削除が確認を通る", "この音を消しますか" in s2)
ok("確認の入口は1つ（個別モーダルを増やしていない）",
   s1.count("id=\"modal-confirm\"") == 0 and "confirmAction : confirmAction" in s1)


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
        pg.wait_for_function("window.__APP_READY === true", timeout=20000)
        pg.wait_for_timeout(1500)
        try: pg.click("#welcome-start", timeout=2500)
        except Exception: pass
        pg.wait_for_timeout(600)

        # ---------- 確認の3つの終わり方 ----------
        r = pg.evaluate("""async () => {
          const M = window.Main;
          const out = {};
          // ① 実行する
          let p = M.confirmAction({ title:'T', body:'B', ok:'やる' });
          const shown = !document.getElementById('modal-confirm').hidden
                     && !document.getElementById('modal-layer').hidden;
          const label = document.getElementById('confirm-go').textContent;
          const title = document.getElementById('confirm-title').textContent;
          document.getElementById('confirm-go').click();
          out.yes = await p;
          out.shown = shown; out.label = label; out.title = title;
          out.closedAfterYes = document.getElementById('modal-layer').hidden;

          // ② やめる（背景タップ）
          p = M.confirmAction({ title:'T2', body:'B2' });
          document.getElementById('modal-layer').click();
          out.no = await p;

          // ③ 開いたまま別の確認を出したら、前のは「やめる」で解決する
          const p1 = M.confirmAction({ title:'A', body:'a' });
          const p2 = M.confirmAction({ title:'B', body:'b' });
          out.first = await p1;
          document.getElementById('confirm-go').click();
          out.second = await p2;
          return out;
        }""")
        ok("確認が覆いごと開く", r["shown"] is True, json.dumps(r))
        ok("見出しと実行ラベルを差し替えられる",
           r["title"] == "T" and r["label"] == "やる", json.dumps(r))
        ok("［実行する］は true を返す", r["yes"] is True, json.dumps(r))
        ok("押したあと覆いが畳まれる", r["closedAfterYes"] is True, json.dumps(r))
        ok("背景タップは false を返す（待ちっぱなしにならない）",
           r["no"] is False, json.dumps(r))
        ok("確認が二重に開いたら、前のは「やめる」で解決する",
           r["first"] is False and r["second"] is True, json.dumps(r))

        # ---------- Escape ----------
        r = pg.evaluate("""async () => {
          const M = window.Main;
          M.openModal('#modal-buy');
          return { before: document.getElementById('modal-layer').hidden };
        }""")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(200)
        after = pg.evaluate("document.getElementById('modal-layer').hidden")
        ok("Escape で覆いが畳める（§4-14 の二重の経路）",
           r["before"] is False and after is True, json.dumps({"before": r["before"], "after": after}))

        # 待っている確認も Escape で解決すること
        # 評価結果を Promise にしない。Playwright は Promise だと解決まで待つので、
        # 解決していない確認をそのまま返すと固まる（実際に固まった）。
        pg.evaluate("""() => {
          window.__esc = 'pending';
          window.Main.confirmAction({ title:'E', body:'e' })
            .then(function (v) { window.__esc = v; });
        }""")
        pg.wait_for_timeout(200)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)
        r = pg.evaluate("window.__esc")
        ok("Escape で閉じたときも確認は false で解決する", r is False, json.dumps(r))

        # ---------- 出題中でも覆いは畳める ----------
        r = pg.evaluate("""async () => {
          const M = window.Main;
          await M.startSession({ mode:'random', count:3 });
          M.openModal('#modal-buy');
          return { screen: M.state.screen, open: !document.getElementById('modal-layer').hidden };
        }""")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(200)
        after = pg.evaluate("document.getElementById('modal-layer').hidden")
        ok("出題中でも Escape で覆いが畳める",
           r["open"] is True and after is True,
           json.dumps({"screen": r["screen"], "after": after}))

        ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
        br.close()


runtime_checks()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAI" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
