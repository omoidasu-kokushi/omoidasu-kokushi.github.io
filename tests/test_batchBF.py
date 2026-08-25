#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBF：全初期化しても同梱の見本問題が戻ってこない（V1.81）

`init()` は「問題数0 かつ seed_imported が未設定」で見本問題を入れる。
ところが `resetAll()` は meta ストアごと消すので **seed_imported も一緒に消える**。
その結果、全初期化したあと読み込み直すと**見本問題が戻ってきていた**（実測で再現）。

旧来の回避策は「初期化したら、再読込せずにそのまま取り込む」。手順を1つ外すと
戻ってくる作りで、しかも戻ったことに気づきにくい（問題数が453に見えるだけで
エラーは何も出ない）。過去問1,173問への入れ替えは、まさにこの手順を通る。

消したのは利用者の意思なので**消えたままにする**。いったん消したあとで
見本が要るようになったら、設定から明示的に入れ直す。
"""
import io, json, os, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []

def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()

# ---------------------------------------------------------------- 静的検査
idx = read("index.html")
p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
js = read(p2)

ok("初期化のあとに印を立て直す", "markSeedConsumed()" in js and "function markSeedConsumed(" in js)
ok("入れ直す経路がある", "function restoreSeedQuestions(" in js)
ok("設定に入口がある", 'id="btn-seed-restore"' in idx and "同梱の見本問題を入れ直す" in idx)
ok("入れ直しは確認を通す（§4-15）", "M.confirmAction" in js.split("function restoreSeedQuestions(")[1][:900])
ok("なぜ戻ってきていたかが書いてある", "meta ストアごと消すので" in js)
ok("学習の記録は消えないと明記している", "学習の記録は消えません" in js)
ok("見本が同梱されていない配布物でも落ちない", "この配布物には見本問題が入っていません" in js)

# ---------------------------------------------------------------- 実行時検査
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=30000)
    pg.wait_for_timeout(1800)
    try:
        pg.click("#welcome-start", timeout=4000)
    except Exception:
        pass
    pg.wait_for_timeout(700)

    n0 = pg.evaluate("window.Storage.countQuestions()")
    ok("初回起動で見本問題が入っている", n0 > 0, str(n0))

    r = pg.evaluate("""async () => {
      const H = window.Half2Impl, S = window.Storage;
      await H.runResetAll();
      const m = await S.loadMeta();
      return { after: await S.countQuestions(),
               seedFlag: m.seed_imported === undefined ? null : m.seed_imported };
    }""")
    ok("全初期化で問題が0になる", r["after"] == 0, json.dumps(r))
    ok("初期化の直後に印が立っている（ここが修正の核心）", r["seedFlag"] is True, json.dumps(r))

    # ページを読み込み直しても戻ってこない
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=30000)
    pg.wait_for_timeout(3500)
    n1 = pg.evaluate("window.Storage.countQuestions()")
    ok("読み込み直しても見本問題が戻ってこない（旧版はここで453に戻る）", n1 == 0, str(n1))

    # 明示的に入れ直せる
    pg.evaluate("window.Main.go('settings')")
    pg.wait_for_timeout(700)
    pg.click("#btn-seed-restore")
    pg.wait_for_timeout(700)
    body = pg.text_content("#modal-confirm .modal-body") or ""
    ok("入れ直しの確認に「記録は消えない」と出る", "消えません" in body, body[:120])
    pg.click("#confirm-go")
    pg.wait_for_timeout(4500)
    n2 = pg.evaluate("window.Storage.countQuestions()")
    ok("設定から見本問題を入れ直せる", n2 == n0, "%s / %s" % (n2, n0))

    # やめれば入らない
    r3 = pg.evaluate("""async () => {
      const S = window.Storage;
      await S.resetAll();
      return await S.countQuestions();
    }""")
    pg.evaluate("window.Main.go('settings')")
    pg.wait_for_timeout(600)
    pg.click("#btn-seed-restore")
    pg.wait_for_timeout(600)
    pg.click("#modal-confirm [data-close]")
    pg.wait_for_timeout(1200)
    n3 = pg.evaluate("window.Storage.countQuestions()")
    ok("［やめる］を押せば入らない", r3 == 0 and n3 == 0, "%s / %s" % (r3, n3))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBF" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
