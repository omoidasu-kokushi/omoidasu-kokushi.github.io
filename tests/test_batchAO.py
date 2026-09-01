#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.62 検証：新しい版への切り替えが本当に起きること

このスイートは【自分専用のコピーとサーバ】を立てる。
sw.js を書き換えて更新を起こす必要があるので、他のスイートと
同じ木を使うと壊してしまう。
"""
import json, os, sys, io, shutil, subprocess, tempfile, socket, time, glob
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))
def read(f): return io.open(os.path.join(APP, f), encoding="utf-8").read()

P1 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
s1 = read(P1)
ok("リロードは controllerchange で行う", "'controllerchange'" in s1)
ok("こちらが頼んだときだけ従う（他所からの切替で勝手に再読込しない）",
   "state.swReloading" in s1)
ok("合図が来ない環境のための時間切れがある", "UPDATE_FALLBACK_MS" in s1)
ok("起動時に待っている版があれば案内し直す",
   "reg.waiting && swc.controller" in s1)
ok("出題中には割り込まない", "state.screen === 'quiz'" in s1 and "swUpdatePending" in s1)


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); n = s.getsockname()[1]; s.close(); return n


def runtime_checks():
    tmp = tempfile.mkdtemp(prefix="omo_sw_")
    work = os.path.join(tmp, "app")
    shutil.copytree(APP, work, ignore=shutil.ignore_patterns(".git", "tests", "*.zip"))
    port = free_port()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port)],
                           cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = "http://127.0.0.1:%d/index.html" % port
    swp = os.path.join(work, "sw.js")
    try:
        time.sleep(1.5)
        with sync_playwright() as p:
            br = p.chromium.launch(args=["--no-sandbox"])
            pg = br.new_context().new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            def settle():
                """開いている覆いを片付けて、ホームに立たせる。

                更新の案内は【出題中でない・他の覆いが開いていない】ときだけ
                出るのが正しい振る舞いなので、片付けないと永久に出てこない。
                ［はじめる］を押すとチュートリアルが始まって出題画面へ入るため、
                押さずに畳む。"""
                pg.wait_for_timeout(700)
                try:
                    pg.evaluate("""() => {
                      const M = window.Main;
                      if (M.state.screen === 'quiz' && M.endSession) { M.endSession(); }
                      M.closeModals();
                      return M.go('home', { replace: true });
                    }""")
                except Exception:
                    pass
                pg.wait_for_timeout(500)

            pg.goto(url, wait_until="load")
            pg.wait_for_function("window.__APP_READY === true", timeout=40000)
            settle()
            pg.wait_for_timeout(1600)
            # 新規プロファイルの初回ナビゲーションは、SWのclaimが遅い環境だと
            # まだ controller=null のことがある（クラウド検証で実測）。
            # ここで待たないと old='NO_CONTROLLER' の置換空振り→以後が連鎖NGになる。
            pg.wait_for_function("() => !!navigator.serviceWorker.controller",
                                 timeout=30000)

            ver = """async () => {
              const c = navigator.serviceWorker.controller;
              if (!c) { return { cache: 'NO_CONTROLLER' }; }
              const ch = new MessageChannel();
              const got = new Promise(r => { ch.port1.onmessage = e => r(e.data); });
              c.postMessage({ type:'GET_VERSION' }, [ch.port2]);
              return await Promise.race([got,
                new Promise(r => setTimeout(() => r({ cache:'TIMEOUT' }), 3000))]);
            }"""
            v1 = pg.evaluate(ver)
            ok("Service Worker が主導権を持っている",
               v1["cache"] not in ("NO_CONTROLLER", "TIMEOUT"), json.dumps(v1))
            old = v1["cache"]

            # --- 新しい版を置く ---
            src = io.open(swp, encoding="utf-8").read()
            io.open(swp, "w", encoding="utf-8").write(
                src.replace("const CACHE_NAME = '" + old + "'",
                            "const CACHE_NAME = 'v9.99.0'"))

            r = pg.evaluate("""async () => {
              const reg = await navigator.serviceWorker.getRegistration();
              await reg.update();
              const t0 = Date.now();
              while (!reg.waiting && Date.now() - t0 < 40000) {
                await new Promise(r => setTimeout(r, 150));
              }
              return { waiting: !!reg.waiting,
                       shown: !document.getElementById('modal-sw-update').hidden };
            }""")
            ok("新しい版が来たことを検出する", r["waiting"] is True, json.dumps(r))
            if not r["shown"]:
                # 他の覆いが開いていれば保留するのが正しい。片付けてから確かめる。
                settle()
                pg.wait_for_function(
                    "() => !document.getElementById('modal-sw-update').hidden", timeout=40000)
            ok("新しい版が来たら案内が出る",
               pg.evaluate("!document.getElementById('modal-sw-update').hidden"), "")

            # --- ［あとで］でも、起動し直せばまた案内される ---
            pg.evaluate("document.querySelector('#modal-sw-update [data-close]').click()")
            pg.wait_for_timeout(300)
            dismissed = pg.evaluate("document.getElementById('modal-sw-update').hidden")
            pg.reload(wait_until="load")
            pg.wait_for_function("window.__APP_READY === true", timeout=40000)
            settle()
            # 起動直後はスプラッシュと起動ダイアログが順に開くので、
            # 案内はそれらが片付いてから出る。時間で決め打ちにしない。
            pg.wait_for_function(
                "() => !document.getElementById('modal-sw-update').hidden", timeout=40000)
            again = pg.evaluate("!document.getElementById('modal-sw-update').hidden")
            ok("［あとで］で閉じられる", dismissed is True)
            ok("［あとで］のあと起動し直すと、また案内される（古い版に取り残さない）",
               again is True)

            # --- ［更新する］で本当に新しい版になる ---
            pg.click("#sw-reload", timeout=4000)
            pg.wait_for_load_state("load")
            pg.wait_for_timeout(3500)
            try:
                pg.wait_for_function("window.__APP_READY === true", timeout=30000)
            except Exception:
                pass
            v2 = pg.evaluate(ver)
            ok("［更新する］で本当に新しい版へ切り替わる（V1.61まではここで古いままだった）",
               v2["cache"] == "v9.99.0", json.dumps({"before": old, "after": v2}))

            r = pg.evaluate("""async () => {
              const reg = await navigator.serviceWorker.getRegistration();
              return { waiting: !!(reg && reg.waiting),
                       shown: !document.getElementById('modal-sw-update').hidden };
            }""")
            ok("待っている版が残らない", r["waiting"] is False, json.dumps(r))
            ok("更新後に案内が出しっぱなしにならない", r["shown"] is False, json.dumps(r))

            # --- 出題中には割り込まない ---
            r = pg.evaluate("""async () => {
              const M = window.Main;
              await M.startSession({ mode:'random', count:3 });
              await new Promise(r => setTimeout(r, 700));
              M.state.swUpdatePending = false;
              /* 出題中に案内が来た状況を作る */
              const before = { screen: M.state.screen,
                               shown: !document.getElementById('modal-sw-update').hidden };
              M.offerUpdate ? M.offerUpdate() : null;
              return { before,
                       shownDuringQuiz: !document.getElementById('modal-sw-update').hidden,
                       pending: M.state.swUpdatePending };
            }""")
            if r.get("pending") is None:
                ok("出題中は案内を保留する（offerUpdate が公開されていない）", False, json.dumps(r))
            else:
                ok("出題中は覆いを出さない（解いている手を止めない）",
                   r["shownDuringQuiz"] is False, json.dumps(r))
                ok("保留したことを覚えている", r["pending"] is True, json.dumps(r))

            opened = pg.evaluate("""() =>
              [...document.querySelectorAll('#modal-layer > .modal-card')]
                .filter(c => !c.hidden).map(c => c.id)""")
            pg.evaluate("""async () => {
              const M = window.Main;
              if (M.endSession) { M.endSession(); }
              /* 覆いが開いたままだと、案内は正しく保留され続ける。
                 利用者は閉じるので、テストでも閉じてから確かめる。 */
              M.closeModals();
              await M.go('home', { replace: true });
              await M.refreshHome();
            }""")
            # 固定の待ちにしない（保留の掘り起こしは何段かの setTimeout を経る）
            shown = True
            try:
                pg.wait_for_function(
                    "() => !document.getElementById('modal-sw-update').hidden", timeout=40000)
            except Exception:
                shown = False
            r = pg.evaluate("""() => ({
              shown: !document.getElementById('modal-sw-update').hidden,
              pending: window.Main.state.swUpdatePending,
              screen: window.Main.state.screen,
              layerHidden: document.getElementById('modal-layer').hidden })""")
            ok("ホームへ戻ったら、保留していた案内を出す",
               shown and r["shown"] is True and r["pending"] is False,
               json.dumps({"state": r, "openedBefore": opened}, ensure_ascii=False))

            ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
            br.close()
    finally:
        srv.terminate()
        shutil.rmtree(tmp, ignore_errors=True)


runtime_checks()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAO" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
