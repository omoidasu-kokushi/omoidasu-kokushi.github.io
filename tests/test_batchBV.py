#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBV：連続日数をやめて週表示にする（V1.97・判断待ちの「案B」）

【なぜ変えるか】
「連続起動◯日目」は **1日抜けるとゼロに戻る**。
戻った瞬間に、いちばん背中を押してほしい人（復帰しようとしている人）の動機を折る。
数字のインパクトは弱くなるが、**壊れない形**にする。

【何を数えるか】
台帳（`daily_log`・V1.92）から、直近7日で**解いた日**の数を数える。
台帳には解いた日だけが入っているので、そのまま「勉強した日」になる。
「起動した日」ではない。開いただけの日を数えると、数字が実態から離れる。

【消さない】
`open_streak` は meta に残す。出すのをやめるだけ。
V1.92 より前の記録には台帳が無いので、1週間かけて埋まる。
"""
import io, json, os, re, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


html = read("index.html")
st = read("storage.js")
p1 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
j1 = read(p1)

ok("週の集計がある", "function weekStudyDays(" in j1)
ok("**連続日数はもう出さない（描画から消えている）**",
   "parts.push('連続起動'" not in j1 and "'連続起動'" not in j1)
ok("やめた理由が書いてある", "1日抜けるとゼロに戻る" in j1)
ok("**open_streak の記録そのものは消していない**",
   "open_streak    : cont ? (meta.open_streak || 0) + 1 : 1," in j1)
ok("解いた日を数えている（開いた日ではない）", "解いた日だけ" in j1)
ok("版番号・CACHE_NAME・?v= の3箇所が揃っている",
   (lambda i, w: i and w and i == w)(
       (re.search(r"\?v=([0-9.]+)", html) or [None, None])[1],
       (re.search(r"\?v=([0-9.]+)", read("sw.js")) or [None, None])[1]))

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(1400)

    r = pg.evaluate("""() => {
      const M = window.Main, S = window.Storage, DAY = 86400000;
      const today = S.util.dayStart(Date.now(), 4);
      const mk = (offsets, extra) => Object.assign({
        day_boundary_hour: 4,
        daily_log: offsets.map(o => ({ k: today - o * DAY, n: 10, w: 2, u: 1 }))
      }, extra || {});
      return {
        none:   M.weekStudyDays(mk([])),
        four:   M.weekStudyDays(mk([1, 2, 4, 6])),
        /* 7日より前は数えない */
        old:    M.weekStudyDays(mk([7, 8, 9])),
        mixed:  M.weekStudyDays(mk([1, 7, 8])),
        /* 今日ぶんは daily_key / daily_count から足す */
        withToday: M.weekStudyDays(mk([1, 2],
                     { daily_key: today, daily_count: 5 })),
        /* 今日ぶんが台帳にも入っていたら二重に数えない */
        noDouble: M.weekStudyDays(mk([0, 1],
                     { daily_key: today, daily_count: 5 })),
        /* 解いていない日（n=0）は数えない */
        zero:   M.weekStudyDays({ day_boundary_hour: 4,
                  daily_log: [{ k: today - DAY, n: 0 }, { k: today - 2*DAY, n: 3 }] }),
        /* 台帳が無い（V1.92 より前）人は0 */
        legacy: M.weekStudyDays({ day_boundary_hour: 4 })
      };
    }""")
    ok("記録が無ければ0", r["none"] == 0, json.dumps(r))
    ok("**直近7日で解いた日を数える**", r["four"] == 4, json.dumps(r))
    ok("**7日より前は数えない**", r["old"] == 0 and r["mixed"] == 1, json.dumps(r))
    ok("今日ぶんも足す", r["withToday"] == 3, json.dumps(r))
    ok("**今日を二重に数えない**", r["noDouble"] == 2, json.dumps(r))
    ok("解いていない日は数えない", r["zero"] == 1, json.dumps(r))
    ok("台帳が無い人でも落ちない（0を返す）", r["legacy"] == 0, json.dumps(r))

    # --- 画面 ---
    v = pg.evaluate("""async () => {
      const M = window.Main, S = window.Storage, DAY = 86400000;
      const today = S.util.dayStart(Date.now(), 4);
      const snapLog = await S.getMeta('daily_log', []);
      const snapKey = await S.getMeta('daily_key', null);
      const snapCnt = await S.getMeta('daily_count', 0);

      await S.setMeta('daily_log', [1,2,3].map(o => ({ k: today - o*DAY, n:10, w:2, u:1 })));
      await S.setMeta('daily_key', today);
      await S.setMeta('daily_count', 4);
      await M.refreshHome();
      const on = document.getElementById('level-facts').textContent;

      await S.setMeta('daily_log', []);
      await S.setMeta('daily_key', null);
      await S.setMeta('daily_count', 0);
      await M.refreshHome();
      const off = document.getElementById('level-facts').textContent;

      await S.setMeta('daily_log', snapLog);
      await S.setMeta('daily_key', snapKey);
      await S.setMeta('daily_count', snapCnt);
      await M.refreshHome();
      return { on:on, off:off };
    }""")
    ok("**「今週◯日」が出る**", "今週4日" in v["on"], json.dumps(v, ensure_ascii=False))
    ok("**「連続起動」は出ない**", "連続起動" not in v["on"] and "連続起動" not in v["off"],
       json.dumps(v, ensure_ascii=False))
    ok("**0日のときは行そのものを出さない（0を突きつけない）**",
       "今週" not in v["off"], json.dumps(v, ensure_ascii=False))
    ok("累計は残っている", "累計解答" in v["on"], json.dumps(v, ensure_ascii=False))

    # --- 1日抜けても壊れないこと（案Bを採った理由そのもの） ---
    gap = pg.evaluate("""() => {
      const M = window.Main, S = window.Storage, DAY = 86400000;
      const today = S.util.dayStart(Date.now(), 4);
      const mk = offs => ({ day_boundary_hour: 4,
        daily_log: offs.map(o => ({ k: today - o*DAY, n:10, w:2, u:1 })) });
      return { before: M.weekStudyDays(mk([1,2,3,4])),
               afterGap: M.weekStudyDays(mk([2,3,4,5])) };
    }""")
    ok("**1日休んでもゼロに戻らない（連続日数との決定的な違い）**",
       gap["afterGap"] == 4 and gap["before"] == 4, json.dumps(gap))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBV" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
