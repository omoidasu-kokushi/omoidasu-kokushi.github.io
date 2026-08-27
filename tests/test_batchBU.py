#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBU：分析がまだ足りないことを言う（V1.96・§23-1/§23-2 の「案C」）

【何が食い違っていたか】
仕様§8-① は「チュートリアル10問 → ランダム10問（計20問）」。
実装は**3問**で終わる（コードに「まとめて20問やらせる旧構成をやめ、最初は3問だけ」
という意図が明記されている）。連動して仕様§8-② の「初回10問完了時16%」も
実際には **3問＝5%** になっていた（全60問モデル）。

【どちらに寄せたか】
**実装（3問）に寄せる。** 3問化は初回の摩擦を下げるための意図的な変更で、
戻すと最初の離脱が増える。

足りないのは「この5%が何なのか」の説明だけ。
ほぼ空のグラフを説明なしで見せると「壊れている」と読まれる。
**チュートリアルを重くする代わりに、待たせる理由を説明する。**
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
css = read("styles.css")
p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
j2 = read(p2)

ok("出す枠がある", 'id="dash-scan"' in html and ".dash-scan{" in css)
ok("更新の関数がある", "function refreshDashScan(" in j2)
ok("ダッシュボードを描くたびに更新する", "refreshDashScan();" in j2)
ok("3問のままにした理由が書いてある", "最初は3問だけ" in j2)
ok("チュートリアルを重くしない方針が書いてある",
   "チュートリアルを重くする代わりに、待たせる理由を説明する" in j2)
ok("使わない色を書いていない（--card-2 は存在しない）", "--card-2" not in css)
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

    # --- 実装は3問、精度は5%（仕様§8の10問／16%ではない）---
    m = pg.evaluate("""async () => {
      const K = window.Scheduler, S = window.Storage;
      const snap = await S.getMeta('scan_answered_qids', []);
      const qs = await S.getAllQuestions();
      const at = n => S.setMeta('scan_answered_qids', qs.slice(0, n).map(q => q.q_id));
      const read = async n => { await at(n); return await K.getScanAccuracy(); };
      const out = { three: await read(3), ten: await read(10),
                    twenty: await read(20), sixty: await read(60) };
      await S.setMeta('scan_answered_qids', snap);
      return out;
    }""")
    ok("**3問＝5%（仕様の16%ではない。実装に寄せた）**",
       m["three"]["pct"] == 5, json.dumps(m["three"], ensure_ascii=False))
    ok("10問＝17%", m["ten"]["pct"] == 17, json.dumps(m["ten"], ensure_ascii=False))
    ok("20問＝33%", m["twenty"]["pct"] == 33, json.dumps(m["twenty"], ensure_ascii=False))
    ok("60問＝100%で完了", m["sixty"]["pct"] == 100 and m["sixty"]["complete"] is True,
       json.dumps(m["sixty"], ensure_ascii=False))

    # --- 説明が出るか ---
    v = pg.evaluate("""async () => {
      const H = window.Half2Impl, S = window.Storage;
      const snap = await S.getMeta('scan_answered_qids', []);
      const qs = await S.getAllQuestions();
      const box = document.getElementById('dash-scan');

      await S.setMeta('scan_answered_qids', qs.slice(0, 3).map(q => q.q_id));
      await H.refreshDashScan();
      const few = { hidden: box.hidden, text: box.textContent };

      await S.setMeta('scan_answered_qids', qs.slice(0, 60).map(q => q.q_id));
      await H.refreshDashScan();
      const done = { hidden: box.hidden };

      await S.setMeta('scan_answered_qids', snap);
      await H.refreshDashScan();
      return { few:few, done:done };
    }""")
    ok("**足りないうちは説明が出る**", v["few"]["hidden"] is False,
       json.dumps(v["few"], ensure_ascii=False))
    ok("**「あと何問」を数で出す**",
       "あと 57問" in v["few"]["text"], json.dumps(v["few"], ensure_ascii=False))
    ok("いまの精度も一緒に出す",
       "5%" in v["few"]["text"] and "3/60問" in v["few"]["text"],
       json.dumps(v["few"], ensure_ascii=False))
    ok("**まだ解いていない範囲が上に出ないことを言う**",
       "まだ解いていない範囲が上に出ません" in v["few"]["text"],
       json.dumps(v["few"], ensure_ascii=False))
    ok("**60問そろったら出さない（用が済んだら消える）**",
       v["done"]["hidden"] is True, json.dumps(v["done"], ensure_ascii=False))

    # --- 画面を開いても壊れない ---
    d = pg.evaluate("""async () => {
      const H = window.Half2Impl;
      await H.openDashboard('sub_item');
      await new Promise(r => setTimeout(r, 400));
      const box = document.getElementById('dash-scan');
      return { screen: document.querySelector('.screen.is-active')
                 ? document.querySelector('.screen.is-active').id : null,
               present: !!box,
               overflow: document.documentElement.scrollWidth
                         > document.documentElement.clientWidth };
    }""")
    ok("ダッシュボードが開く", d["screen"] == "screen-dashboard" and d["present"] is True,
       json.dumps(d, ensure_ascii=False))
    ok("横スクロールが出ない", d["overflow"] is False, json.dumps(d, ensure_ascii=False))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBU" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
