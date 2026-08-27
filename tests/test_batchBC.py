#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBC：反応時間の記録（V1.78・§2-5の約束）

§2-5 で「思考インターロックを1.5秒・5秒へ延ばす」案を退けたとき、
代わりに約束したのがこれ——**待たせずに測る**。
「表示から最初のタップまでの時間を記録すれば、即答できた／迷ったは
事後に判定できる」と書いておきながら、V1.77 まで実装が無かった（§8）。

いま入れる理由は timing にある。**これから解く分のデータは、
いま器を作っておかないと永久に取れない。**

固定するのは3つ：起点が「押せるようになった瞬間」であること（待ちの0.5秒を
含めない）／最初のタップだけを見ること（選び直しで起点が動かない）／
取れないときは推測せず null にすること。
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
kjs = read("scheduler.js")
p1 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
js = read(p1)

ok("台帳に think_ms を積む", "think_ms       : isNum(ctx.thinkMs)" in kjs)
ok("1問ぶんの評価に thinkMs を素通しする", "thinkMs: ctx.thinkMs" in kjs)
ok("起点は「押せるようになった瞬間」", "state.current.readyAt = Date.now()" in js)
ok("0.5秒の待ちを含めない理由が書いてある", "同じ0.5秒が乗るだけ" in js)
ok("最初のタップだけを見る", "if (!state.current.firstTapAt)" in js)
ok("選び直しで起点を動かさない理由が書いてある", "選び直しは「迷い」の一部" in js)
ok("取れないときは null（推測で埋めない）", "推測で埋めない" in js)
ok("放置の1件で平均が壊れないよう上限を切る", "THINK_MAX_MS = 600000" in js)
ok("§2-5 の約束だと明記してある", "§2-5の約束" in js and "§2-5" in kjs)

# ---------------------------------------------------------------- 実行時検査
from playwright.sync_api import sync_playwright


# 「2つ選べ」の問題が先頭に来ると、1枚押しただけでは確定が押せない。
# 必要な枚数まで押す（V1.98：ランク当てでキューの中身が変わり、実際に踏んだ）。
def fill_choices(pg):
    pg.evaluate("""() => {
      for (const c of document.querySelectorAll('#choice-list .choice-card')) {
        const b = document.getElementById('btn-confirm');
        if (b && !b.disabled) { break; }
        const body = c.querySelector('.choice-body') || c;
        body.click();
      }
    }""")
    pg.wait_for_selector("#btn-confirm:not([disabled])", timeout=10000)


with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=30000)
    pg.wait_for_timeout(1500)
    try:
        pg.click("#welcome-start", timeout=4000)
    except Exception:
        pass
    pg.wait_for_timeout(900)

    # 実際に1問解いて、台帳に think_ms が載るか
    # 出題画面へ（すでに出ているはず）。押せるようになるまで待ってからタップする
    pg.wait_for_selector("#choice-list .choice-card", timeout=15000)
    pg.wait_for_selector("#choice-list.is-ready", timeout=15000)
    pg.wait_for_timeout(700)          # 「迷った」ぶんの時間
    pg.click("#choice-list .choice-card:nth-child(2) .choice-body")
    fill_choices(pg)
    pg.wait_for_timeout(150)
    pg.click("#btn-confirm")
    pg.wait_for_timeout(900)
    pg.click("#btn-next")
    pg.wait_for_timeout(1200)

    logs = pg.evaluate("""async () => {
      const S = window.Storage;
      const all = await S.getAllLogs();
      const last = all.slice(-6);
      const vals = last.map(l => l.think_ms);
      return { n: all.length, vals: vals,
               hasField: last.every(l => 'think_ms' in l),
               numeric: vals.filter(v => typeof v === 'number') };
    }""")
    ok("解答すると台帳に think_ms の欄が載る", logs["hasField"], json.dumps(logs))
    ok("値が入る（数値）", len(logs["numeric"]) >= 1, json.dumps(logs))
    ok("同じ問題の全アトムに同じ値が載る",
       len(set(logs["numeric"])) <= 1, json.dumps(logs["numeric"]))

    # --- 迷った時間の差が、そのまま値の差になるか ---
    #   固定の待ち時間そのものは環境の遅れを含むので当てにしない。
    #   2問を違う長さで解いて【差】を見る（差なら遅れが相殺される）。
    LASTLOG = 'async () => { const all = await window.Storage.getAllLogs(); const last = all[all.length - 1]; return last ? last.think_ms : null; }'

    def counter():
        return (pg.text_content("#q-counter") or "").strip()

    def goto_next():
        """次の問題へ進み、押せるようになるまで待つ。
        【この試験の罠】前の問題の .is-ready が残っていることがあるので、
        問題番号が変わるのを見てから待つ。見ないと、待った時間が画面の
        切り替わりに食われて値が逆転する（実際に逆転した）。"""
        prev = counter()
        nxt = pg.locator("#btn-next")
        if not nxt.is_visible():
            # すでに次の問題が出ている（解説画面にいない）ならそのまま待つ
            pg.wait_for_selector("#choice-list .choice-card", timeout=15000)
            pg.wait_for_selector("#choice-list.is-ready", timeout=15000)
            return
        nxt.click()
        pg.wait_for_function("(prev) => { const el = document.querySelector('#q-counter');"
                             " return el && el.textContent.trim() !== prev; }",
                             arg=prev, timeout=15000)
        pg.wait_for_selector("#choice-list .choice-card", timeout=15000)
        pg.wait_for_selector("#choice-list.is-ready", timeout=15000)

    def answer(wait_ms):
        """いま出ている問題を、指定の時間だけ迷ってから解く。値を返す。"""
        pg.wait_for_timeout(wait_ms)
        # 肢の数も、選ぶ数も問題によって違う（「2つ選べ」がある）。
        # 確定できるようになるまで押し足す。反応時間は【最初の1回】で測る。
        cards = pg.locator("#choice-list .choice-card")
        for i in range(cards.count()):
            cards.nth(i).click()
            pg.wait_for_timeout(120)
            if not pg.evaluate("() => document.querySelector('#btn-confirm').disabled"):
                break
        live = pg.evaluate("() => window.Main.thinkMsForCurrent()")
        pg.wait_for_selector("#btn-confirm:not([disabled])", timeout=8000)
        pg.click("#btn-confirm")
        pg.wait_for_timeout(600)
        return live

    # 【この試験の罠 その2】台帳へ積まれるのは［確定］ではなく［次へ］のとき。
    #   確定の直後に台帳を読むと、1問前の値を読んでしまう（実際に読んだ）。
    def commit_and_read():
        """［次へ］を押して台帳へ積ませ、積まれた値を読む。
        次の問題があるとは限らない（セッションが終わることがある）ので、
        画面ではなく【台帳の件数が増えたこと】を待つ。"""
        n0 = pg.evaluate("window.Storage.getAllLogs().then(l => l.length)")
        nxt = pg.locator("#btn-next")
        if nxt.is_visible():
            nxt.click()
        pg.wait_for_function("(n) => window.Storage.getAllLogs().then(l => l.length > n)",
                             arg=n0, timeout=15000)
        return pg.evaluate(LASTLOG)

    # 計測用に、余裕のある出題を自分で始める
    #  （オンボーディングの出題は問数が限られていて、途中で尽きる）
    pg.evaluate("window.Main.startSession({ mode: 'random', count: 8 })")
    pg.wait_for_selector("#choice-list .choice-card", timeout=15000)
    pg.wait_for_selector("#choice-list.is-ready", timeout=15000)

    quick = answer(200)
    quick_logged = commit_and_read()
    pg.wait_for_selector("#choice-list .choice-card", timeout=15000)
    pg.wait_for_selector("#choice-list.is-ready", timeout=15000)
    slow = answer(1700)
    slow_logged = commit_and_read()
    print("   [計測] quick=%s(台帳 %s) slow=%s(台帳 %s)" % (quick, quick_logged, slow, slow_logged))

    ok("台帳の値と、その場で計算した値が一致する（quick）",
       quick == quick_logged, "live=%s logged=%s" % (quick, quick_logged))
    ok("台帳の値と、その場で計算した値が一致する（slow）",
       slow == slow_logged, "live=%s logged=%s" % (slow, slow_logged))
    diff = (slow - quick) if (quick is not None and slow is not None) else None
    ok("迷った時間の差がそのまま値の差になる（1.5秒±0.6）",
       diff is not None and 900 <= diff <= 2100,
       "quick=%s slow=%s diff=%s" % (quick, slow, diff))
    ok("即答のほうが小さい値になる",
       quick is not None and slow is not None and quick < slow,
       "quick=%s slow=%s" % (quick, slow))

    ok("反応時間の計算が公開されている（検証できる）",
       pg.evaluate("() => typeof window.Main.thinkMsForCurrent === 'function'"))

    edge2 = pg.evaluate("""() => {
      // いまの出題状態を使って、境界を直に確かめる
      const M = window.Main;
      const q = document.querySelector('#choice-list .choice-card');
      return { ok: !!q };
    }""")
    ok("出題画面が生きている", edge2["ok"])

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBC" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
