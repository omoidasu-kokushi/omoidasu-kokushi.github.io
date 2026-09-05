#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCK：模試が未解禁の間、力試しカードは見た目だけ休む（V2.14）

何が起きていたか：
問題も学習量も足りず模試が1つも解禁されていない状態でも、ホームの
力試しカードは他のカードと同じ顔で「押せる」ように見えていた。
押しても始められるものが無いのに、入口だけ元気なのは誤解を生む（利用者指摘）。
直し方：解禁ゼロの間はカードに is-locked を付け、彩度・明度を落とす。
タップは殺さない（一覧側に解禁条件と進捗が出るため、行き止まりにしない）。
"""
import io, json, os, sys

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


import glob as _g
p1 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
js = read(p1)
css = read("styles.css")
ok("ホーム描画で解禁有無を見てクラスを付け替える",
   "examCard.classList.toggle('is-locked'" in js)
ok("タップを殺さない意図がコードに書いてある", "行き止まりにしない" in js)
ok("見た目のスタイルがある", ".sub-card.is-locked" in css)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(1200)

    r1 = pg.evaluate("""() => {
      const c = document.getElementById('card-exam');
      return { locked: c ? c.classList.contains('is-locked') : null,
               clickable: c ? !c.disabled : null };
    }""")
    ok("新規状態では is-locked が付く", r1["locked"] is True, json.dumps(r1))
    ok("タップ自体は生きている（disabledにしない）", r1["clickable"] is True, json.dumps(r1))

    r2 = pg.evaluate("""async () => {
      const orig = window.Storage.getUnlockState;
      window.Storage.getUnlockState = () => Promise.resolve(
        [{ id: 'mock_30', unlocked: true }, { id: 'mock_weak', unlocked: false }]);
      try {
        await window.Main.refreshHome();
        await new Promise(res => setTimeout(res, 600));
        const c = document.getElementById('card-exam');
        return { locked: c.classList.contains('is-locked') };
      } finally {
        window.Storage.getUnlockState = orig;
      }
    }""")
    ok("1つでも解禁されたら is-locked が外れる", r2["locked"] is False, json.dumps(r2))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchCK" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
