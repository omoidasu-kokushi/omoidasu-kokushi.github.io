#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチDA：設定の再配置（V2.32・利用者裁定「なぜその設定がそこに？を正す」）

- 新設「2. 試験と出題」＝受験する年・必修の出題比率・復習の1日上限・一問一答の出しかた
- 「3. 生活リズム設定」は日界だけ
- 「8. 表示のカスタマイズ」＝選択肢ごとの解説・画像の表示位置（テーマ切替から移動）・文言直し
- 一言メモの実態ずれ修正：取り込み「12列TSV」→「TSV／JSON」、
  ドライブ同期の説明に「学習の記録」を明記（§20の実態に合わせた）
"""
import io, os, sys, glob, json, re
APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""):
    R.append((bool(c), n, d))
html = io.open(os.path.join(APP, "index.html"), encoding="utf-8").read()
p2 = sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1]
js = io.open(p2, encoding="utf-8").read()

def sec(name, nxt):
    a = html.find(name); b = html.find(nxt)
    assert a > 0 and b > a, (name, nxt)
    return html[a:b]

s2 = sec("2. 試験と出題", "3. 生活リズム設定")
ok("試験と出題＝年・必修・上限・一問一答", all(x in s2 for x in
   ('id="set-exam-year"', 'id="set-hissu"', 'id="set-cap"', 'id="btn-oneq"')))
s3 = sec("3. 生活リズム設定", "4. ポモドーロ")
ok("生活リズムは日界だけ", 'id="set-dayline"' in s3 and "set-exam-year" not in s3 and "set-hissu" not in s3)
s5 = sec("5. テーマ切替", "6. 通知")
ok("テーマ切替に画像位置は無い", "userimgpos" not in s5)
s8 = sec("8. 表示のカスタマイズ", "9. データ")
ok("表示のカスタマイズ＝解説・画像位置・文言直し", all(x in s8 for x in
   ('id="set-explain-mode"', 'name="userimgpos"', 'id="btn-text-edit"')))
nums = re.findall(r'class="set-head">(\d+)\.', html)
ok("節番号が1〜10で連番", nums == [str(i) for i in range(1, 11)], str(nums))
ok("取り込みメモがTSV／JSON", "自作問題データ（TSV／JSON）の取り込み" in html and "（12列TSV）の取り込み" not in html)
ok("ドライブ説明に学習の記録", "学習の記録</b>・自分で貼った" in js)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(800)
    r = pg.evaluate("""async () => {
      await window.Half2.openSettings();
      await new Promise(r2 => setTimeout(r2, 600));
      /* 移した部品のバインディングが生きているか：必修比率を押して値が変わる */
      const btn = document.querySelector('#set-hissu .seg-btn[data-hissu="strong"]');
      btn.click();
      await new Promise(r2 => setTimeout(r2, 400));
      const meta = await window.Storage.loadMeta();
      const active = document.querySelector('#set-hissu .seg-btn.is-active');
      return { mode: meta.hissu_mode, activeBtn: active ? active.dataset.hissu : null,
               yearOpts: document.getElementById('set-exam-year').options.length };
    }""")
    ok("移設後も必修比率の切替が効く", r["mode"] == "strong" and r["activeBtn"] == "strong", json.dumps(r))
    ok("受験する年の選択肢が生成される", r["yearOpts"] > 1, json.dumps(r))
    ok("実行時エラーなし", not errs, str(errs[:2]))
    br.close()
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchDA" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
