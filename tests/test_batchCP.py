#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCP：★ノートは何百件たまっても画面を凍らせない（V2.21）

何が起きていたか：
疑似1年データ（★697件）で★ノートを開くと、一覧のHTML自体は0.3秒で
入るのに、その直後に全項目（問題文＋全選択肢＋拡張解説＋比較表）の
一括レイアウトがメインスレッドを約20秒塞いだ。★ノートを開いた直後は
どのボタンも20秒効かず、最初は「検索が20秒かかる」ように見えた
（検索処理そのものは0.2秒だった。遅いのは前の画面の後始末だった）。
直し方：.star-item に content-visibility:auto を付け、画面外の項目の
レイアウトを後回しにする。DOMも見た目も変わらない。スクロールすれば
その場で必要なぶんだけレイアウトされる。
"""
import io, json, os, sys, time

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


css = read("styles.css")
i = css.find(".star-item{")
blk = css[i:css.find("}", i)] if i >= 0 else ""
ok("★項目に content-visibility:auto がある", "content-visibility:auto" in blk, blk[:200])
ok("飛びスクロール用の寸法ヒントがある", "contain-intrinsic-size" in blk, blk[:200])

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
    pg.evaluate("""() => { const b = document.getElementById('welcome-start'); if (b) b.click(); }""")
    pg.wait_for_timeout(400)

    # 同梱シード全問に問題★を付ける（数百件規模を再現する）
    r1 = pg.evaluate("""async () => {
      const S = window.Storage;
      const qs = await S.getAllQuestions();
      for (const q of qs) { await S.toggleQuestionStar(q.q_id); }
      return { starred: qs.length };
    }""")
    ok("シード全問に★が付いた（450問以上）", r1["starred"] >= 450, json.dumps(r1))

    # ★ノートを開く → 開き終わった直後にメインスレッドがすぐ空くこと
    r2 = pg.evaluate("""async () => {
      const t0 = performance.now();
      await window.Half2.openStarredNote();
      const opened = performance.now() - t0;
      const items = document.querySelectorAll('#star-list .star-item').length;
      return { openedMs: Math.round(opened), items };
    }""")
    t0 = time.time()
    tick = pg.evaluate("() => 1")   # レイアウト詰まりがあると、この呼び出しが数十秒待たされる
    stall = int((time.time() - t0) * 1000)
    ok("★ノートが全件描画される", r2["items"] == r1["starred"], json.dumps(r2))
    # 修正前は453件で約13秒詰まった。余裕を見て5秒を上限とする
    ok("描画直後にメインスレッドが空く（5秒未満）", stall < 5000, "stall=%dms" % stall)

    # 末尾までスクロールしても凍らない（content-visibilityの副作用が無い）
    r3 = pg.evaluate("""async () => {
      const sc = document.scrollingElement;
      const t0 = performance.now();
      sc.scrollTop = sc.scrollHeight;
      await new Promise(r => setTimeout(r, 400));
      return { ms: Math.round(performance.now() - t0),
               bottomVisible: sc.scrollTop > 0 };
    }""")
    ok("末尾へのスクロールが2秒以内", r3["ms"] < 2000, json.dumps(r3))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchCP" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
