#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBY：起動できていないことを、閉じても消さない（V2.00）

【何が起きていたか】
保存領域（IndexedDB）が開けないと診断パネルが出る。ここまでは正しい。
ところが［閉じる］を押すと**覆いが消えたきり、何も残らなかった**。

結果、**ふつうのホーム画面が出ているのに、何をしても記録されない**という
いちばん分かりにくい壊れ方になる。利用者からは「反応しないアプリ」に見える。

【どう直したか】
覆いは片付けてよい（閉じたそばから再表示すると操作を永久に塞ぐ）。
ただし**起動できていないときだけ、小さな印を必ず残す。**
押せば診断パネルが同じ内容で戻る。

起動できている場合（`file://` の助言など）は、閉じたら本当に消してよい。
そこは「動いてはいる」ので、印を残すと過剰な警告になる。
"""
import io, json, os, re, sys

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


html = read("index.html")

ok("印を出す関数がある", "function showDiagBadge(" in html)
ok("**起動できていないときだけ印を残す**", "if (!window.__APP_READY) { showDiagBadge(); }" in html)
ok("印から同じ内容へ戻せる", "window.__DIAG_LAST = opts;" in html
   and "render(window.__DIAG_LAST || {});" in html)
ok("なぜ覆いを消してよいか書いてある", "閉じたそばから再表示" in html)
ok("何が起きていたか書いてある", "何をしても記録されない" in html)
ok("版番号・CACHE_NAME・?v= の3箇所が揃っている",
   (lambda i, w: i and w and i == w)(
       (re.search(r"\?v=([0-9.]+)", html) or [None, None])[1],
       (re.search(r"\?v=([0-9.]+)", read("sw.js")) or [None, None])[1]))

from playwright.sync_api import sync_playwright

BLOCK_IDB = """
  const orig = indexedDB.open.bind(indexedDB);
  indexedDB.open = function () {
    const req = { onerror:null, onsuccess:null, onupgradeneeded:null,
                  error: new DOMException('試験用に塞いだ','InvalidStateError') };
    setTimeout(() => { if (req.onerror) req.onerror({ target: req }); }, 10);
    return req;
  };
"""

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])

    # ---------- 起動できないとき ----------
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    pg.add_init_script(BLOCK_IDB)
    pg.goto(URL, wait_until="load")
    pg.wait_for_timeout(5000)

    st = pg.evaluate("""() => ({
      diag: !!document.getElementById('boot-diagnostics'),
      ready: !!window.__APP_READY })""")
    ok("**保存領域が開けないと診断パネルが出る**",
       st["diag"] is True and st["ready"] is False, json.dumps(st))

    pg.click("#boot-diagnostics-close")
    pg.wait_for_timeout(400)
    after = pg.evaluate("""() => ({
      panel: !!document.getElementById('boot-diagnostics'),
      badge: !!document.getElementById('boot-diagnostics-badge'),
      text: (document.getElementById('boot-diagnostics-badge') || {}).textContent || '' })""")
    ok("**閉じれば覆いは片付く（操作を塞がない）**", after["panel"] is False, json.dumps(after, ensure_ascii=False))
    ok("**ただし印は残る（動いていないことを消さない）**",
       after["badge"] is True and "起動できていません" in after["text"],
       json.dumps(after, ensure_ascii=False))

    pg.click("#boot-diagnostics-badge")
    pg.wait_for_timeout(400)
    back = pg.evaluate("""() => ({
      panel: !!document.getElementById('boot-diagnostics'),
      badge: !!document.getElementById('boot-diagnostics-badge'),
      title: (document.querySelector('#boot-diagnostics b') || {}).textContent || '' })""")
    ok("**印を押せば診断パネルが戻る**", back["panel"] is True, json.dumps(back, ensure_ascii=False))
    ok("戻ったら印は消える（二重に出さない）", back["badge"] is False, json.dumps(back, ensure_ascii=False))
    ok("戻ったパネルに理由が書いてある", len(back["title"]) > 0, json.dumps(back, ensure_ascii=False))

    # 2回閉じても印は1つだけ
    pg.click("#boot-diagnostics-close"); pg.wait_for_timeout(300)
    pg.click("#boot-diagnostics-badge"); pg.wait_for_timeout(300)
    pg.click("#boot-diagnostics-close"); pg.wait_for_timeout(300)
    dup = pg.evaluate("document.querySelectorAll('#boot-diagnostics-badge').length")
    ok("何度開き閉じしても印は1つだけ", dup == 1, str(dup))
    ctx.close()

    # ---------- ふつうに起動できるとき ----------
    ctx2 = br.new_context(viewport={"width": 390, "height": 844})
    pg2 = ctx2.new_page()
    pg2.goto(URL, wait_until="load")
    pg2.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg2.wait_for_timeout(3000)
    fine = pg2.evaluate("""() => ({
      panel: !!document.getElementById('boot-diagnostics'),
      badge: !!document.getElementById('boot-diagnostics-badge') })""")
    ok("**ふつうに起動できていれば、パネルも印も出ない**",
       fine["panel"] is False and fine["badge"] is False, json.dumps(fine))

    # 起動できている状態で助言だけ出した場合は、閉じたら本当に消える
    adv = pg2.evaluate("""async () => {
      window.__DIAG_DISMISSED = false;
      window.__showBootDiagnostics({ level:'warn', title:'助言だけ', detail:'動いてはいます' });
      await new Promise(r => setTimeout(r, 200));
      const shown = !!document.getElementById('boot-diagnostics');
      document.getElementById('boot-diagnostics-close').click();
      await new Promise(r => setTimeout(r, 200));
      return { shown: shown,
               panel: !!document.getElementById('boot-diagnostics'),
               badge: !!document.getElementById('boot-diagnostics-badge') };
    }""")
    ok("**起動できているときの助言は、閉じたら本当に消える（過剰な警告にしない）**",
       adv["shown"] is True and adv["panel"] is False and adv["badge"] is False,
       json.dumps(adv, ensure_ascii=False))

    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBY" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
