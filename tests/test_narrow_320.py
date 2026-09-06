# -*- coding: utf-8 -*-
"""test_narrow_320.py — 320px で画面からはみ出さない（V2.74）

【実測で見つけた不具合】320x860（iPhone SE 相当）でランダム画面を開くと

    画面幅            320px
    ページの幅        363px   ← 横スクロールが出る
    .pick-row の幅    347px   ← 288px の枠から 59px はみ出す
    .pick-dice の右端 363px   ← 「ランダム」ボタンが画面の外

画面写真でも「ラン」で切れて、押せる面積が半分になっていた。

【原因】`.pick-row` は `.major-list`（display:grid）のグリッド項目。
グリッド項目の自動最小サイズは min-content なので、中身が入り切らないと
**枠を無視して広がる**。V2.68 で「あと◯問」バッジを足したぶん min-content が増え、
288px の枠を超えた。それまでは偶然ぎりぎり収まっていた。V2.68 の退行。

【直し方】`.pick-row{ min-width:0 }`。
min-width:0 を入れずに main / dice / name 側をいじっても**1pxも動かない**
（項目そのものが縮めないので、中をいくら縮めても意味がない）ことを実測で確かめた。

ここで固定するのは4つ。
  ① 320px で横スクロールが出ない（主要画面すべて）
  ② 「ランダム」ボタンが画面内に収まり、文字が欠けない
  ③ min-width:0 が CSS に残っている（消すと再発する）
  ④ 単元名は ellipsis で縮む（行が壊れるのではなく、名前が縮む）
"""
import json, os, sys
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cs = open(os.path.join(base, "styles.css"), encoding="utf-8").read()
ok("`.pick-row` に min-width:0 が入っている（消すと再発）",
   ".pick-row{ display:flex; align-items:stretch; gap:6px; margin-bottom:8px; min-width:0; }" in cs)
ok("なぜ要るかが書いてある", "グリッド項目の自動最小サイズは min-content" in cs)
ok("単元名は ellipsis で縮む", "text-overflow:ellipsis" in cs)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
SCREENS = [
    ("home",      "() => window.Main.go('home')"),
    ("random",    "async () => { await window.Half2Impl.openRandomSelect(); }"),
    ("dashboard", "() => window.Main.go('dashboard')"),
    ("search",    "() => window.Main.go('search')"),
    ("starred",   "() => window.Main.go('starred')"),
    ("tree",      "() => window.Main.go('tree')"),
    ("exam",      "() => window.Main.go('exam')"),
    ("settings",  "() => window.Main.go('settings')"),
]

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 320, "height": 860}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.evaluate("""async () => {
      await window.Storage.setMetaBulk({ onboarding_done: true,
        tips_seen: ['unit_hero','qty','next','scan','level','settings_btn','theme','back','home_tip'] });
    }""")
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(1500)
    pg.evaluate("() => { const s=document.getElementById('splash'); if(s) s.classList.add('is-gone'); window.Main.closeModals(); }")

    wide = []
    for name, go in SCREENS:
        try:
            pg.evaluate(go)
        except Exception as e:
            wide.append({"screen": name, "err": str(e)[:80]}); continue
        pg.wait_for_timeout(500)
        pg.evaluate("() => window.Main.closeModals && window.Main.closeModals()")
        pg.wait_for_timeout(150)
        w = pg.evaluate("() => document.documentElement.scrollWidth")
        if w > 322:
            wide.append({"screen": name, "docScrollW": w})
    ok("320pxで横スクロールが出ない（主要8画面）", not wide, json.dumps(wide, ensure_ascii=False))

    pg.evaluate("async () => { await window.Half2Impl.openRandomSelect(); }")
    pg.wait_for_timeout(600)
    pg.evaluate("() => window.Main.closeModals()")
    pg.wait_for_timeout(200)
    r = pg.evaluate("""() => {
      const rows = [...document.querySelectorAll('.pick-row')];
      if (!rows.length) { return { none: true }; }
      const vw = document.documentElement.clientWidth;
      const bad = [];
      rows.forEach(row => {
        const d = row.querySelector('.pick-dice');
        if (!d) { return; }
        const b = d.getBoundingClientRect();
        if (b.right > vw + 1) { bad.push({ right: Math.round(b.right), vw: vw }); }
      });
      const d0 = rows[0].querySelector('.pick-dice');
      const b0 = d0.getBoundingClientRect();
      const nm = rows[0].querySelector('.pick-name');
      const ncs = getComputedStyle(nm);
      return { n: rows.length, bad: bad,
               diceW: Math.round(b0.width), diceText: (d0.textContent || '').trim(),
               diceFits: d0.scrollWidth <= d0.clientWidth + 1,
               nameEllipsis: ncs.textOverflow === 'ellipsis' };
    }""")
    ok("「ランダム」ボタンが全行とも画面内に収まる", not r.get("bad"), json.dumps(r, ensure_ascii=False))
    ok("ボタンの文字が欠けていない", r.get("diceFits") and r.get("diceText") == "ランダム",
       json.dumps(r, ensure_ascii=False))
    ok("単元名は ellipsis で縮む（行を壊さない）", r.get("nameEllipsis"), json.dumps(r, ensure_ascii=False))
    ok("JSエラーが出ていない", not errs, " / ".join(errs[:3]))
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  narrow_320" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
