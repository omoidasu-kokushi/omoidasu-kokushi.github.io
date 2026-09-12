#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチDK：一問一答の分割印を自動適用（V2.43・裁定）
シード453問すべて印なし＝一問一答が一度も出ない状態だった。起動時に1回
（meta.auto_split_done）＋取り込み成功時に自動判定を適用。
「常に4択で出す」「全部外す」で従来どおり戻せる。
"""
import io, os, sys, glob, json
APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""):
    R.append((bool(c), n, d))
p2 = sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1]
js = io.open(p2, encoding="utf-8").read()
ok("起動時の自動適用がある", "auto_split_done" in js and js.count("S.autoMarkSplittable()") >= 2)
ok("取り込み後も追いかける", "新しく入った問題にも一問一答の分割印" in js)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    # V2.99：同梱データ（見本249＋体験用90）の取り込みが終わった合図を待つ。
    # 途中で再読込すると、2回目の起動が「続きの取り込み」になり、印づけはそのあとに回る。
    pg.wait_for_function("window.__INIT_DONE === true", timeout=180000)
    pg.wait_for_timeout(500)
    # 初回起動＝シード取り込み直後は totalQ=0 分岐なので、リロードで2回目起動を再現
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_function("window.__INIT_DONE === true", timeout=180000)
    pg.wait_for_timeout(1500)
    r = pg.evaluate("""async () => {
      const S = window.Storage;
      const qs = await S.getAllQuestions();
      const marked = qs.filter(q => q.is_splittable).length;
      const singles = qs.filter(q => q.question_type === 'single').length;
      const meta = await S.loadMeta();
      return { total: qs.length, marked, singles, done: !!meta.auto_split_done };
    }""")
    ok("2回目起動で自動適用済み", r["done"], json.dumps(r))
    # 自動判定は否定形の設問（「誤っているのは」等）を除外するため全問には付かない。
    # シード453問での実測は113問。三桁付けば一問一答は日常的に出る。
    ok("分割印が三桁つく", r["marked"] >= 100, json.dumps(r))
    # 一問一答が実際に選ばれる（期日1本の状況を作る）
    r2 = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler;
      const qs = (await S.getAllQuestions()).filter(q => q.is_splittable);
      const full = (await S.getQuestionsFull([qs[0].q_id]))[0];
      const fmt = K.pickFormat(full, [full.atoms[0].atom_id], {});
      return { format: fmt.format, reason: fmt.reason };
    }""")
    ok("期日1本ならsingle形式が選ばれる", r2["format"] == "single", json.dumps(r2))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchDK" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
