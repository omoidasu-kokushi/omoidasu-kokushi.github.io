#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBZ：時間で区切って始める「5分だけ」（V2.01）

【なぜ要るか】
1日の問数を決めるのは「続ける時間」ではなく **「始められるかどうか」**。
始めた人は、たいてい予定より多くやる。
V1.92 の「今日の分」（上限）は**多すぎて始められない**人のため、
こちらは**そもそも取りかかれない**人のための入口。

【ノックとの決定的な違い】
テーマ別ノック（§7）は忘却スケジュールを更新しない独立モードだが、
こちらは**本日の復習そのもの**なので、**通常どおり記録も期日も更新する。**
時間は「いつ聞くか」を決めるだけで、学習の扱いは1ミリも変えない。

【強制終了しない】
時間が来たら、**解説画面へ切り替わったタイミングで一度だけ**聞く
（ポモドーロと同じ作法。問題の途中で割り込まない）。
［続ける］なら以後は聞かない。

【カードは触らない】
V1.17 の「カードに出すのはタイトルと件数だけ」を壊さない。ボタンはカードの外。
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
p1 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
j1 = read(p1)

ok("入口がある", 'id="btn-review-5"' in html and 'id="btn-review-10"' in html)
ok("**カードの外に置いてある**",
   html.index('id="review-quick"') > html.index('id="card-review"')
   and 'id="review-quick"' not in html[html.index('id="card-review"'):html.index('</button>', html.index('id="card-review"'))])
ok("区切りのダイアログがある", 'id="modal-time-up"' in html and 'id="time-up-go"' in html)
ok("見るのは解説へ切り替わったタイミング", "checkTimeBox();" in j1)
ok("判定の関数がある", "function checkTimeBox(" in j1)
ok("**ノックと違って記録も期日も更新すると書いてある**", "通常どおり記録も期日も更新する" in j1)
ok("強制終了しないと書いてある", "強制終了はしない" in j1 or "強制終了しない" in j1)
ok("スタイルがある", ".review-quick{" in css and ".quick-btn{" in css)
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

    # --- 復習が無ければ出さない／あれば出す ---
    v = pg.evaluate("""async () => {
      const S = window.Storage, M = window.Main;
      await M.refreshHome();
      const none = document.getElementById('review-quick').hidden;
      const at = await S.getAllAtoms();
      for (const a of at.slice(0, 12)) {
        await S.updateAtom(a.atom_id, { srs_step:1, interval_code:'10m',
          last_eval:'hard', answer_count:1, due_date: Date.now() - 60000 });
      }
      await M.refreshHome();
      const some = document.getElementById('review-quick').hidden;
      const card = document.getElementById('card-review').innerText.replace(/\\n/g,'|');
      return { none:none, some:some, card:card };
    }""")
    ok("**復習が0件なら出さない**", v["none"] is True, json.dumps(v, ensure_ascii=False))
    ok("**復習があれば出る**", v["some"] is False, json.dumps(v, ensure_ascii=False))
    ok("**カードそのものは変えていない（タイトルと件数だけ）**",
       len(set(v["card"].replace("|", " ").split()) - {"本日の復習"}) <= 1,
       json.dumps(v["card"], ensure_ascii=False))

    # --- 時間制で始まるか。学習の扱いは変わらないか ---
    s = pg.evaluate("""async () => {
      const M = window.Main;
      await M.startSession({ mode:'review', timeLimitMs: 5 * 60 * 1000 });
      const s = M.state.session;
      return { mode:s.mode, limit:s.timeLimitMs, asked:s.timeAsked,
               n:s.questions.length };
    }""")
    ok("**mode は review のまま（学習の扱いを変えない）**",
       s["mode"] == "review", json.dumps(s))
    ok("時間が入る", s["limit"] == 300000 and s["asked"] is False, json.dumps(s))
    ok("問題が出る", s["n"] > 0, json.dumps(s))

    # --- 時間前は聞かない／時間が来たら一度だけ聞く ---
    t = pg.evaluate("""async () => {
      const M = window.Main;
      const before = M.checkTimeBox();
      /* 時計を触らず、開始時刻を過去へずらす */
      M.state.session.timeStartedAt = Date.now() - 6 * 60 * 1000;
      const fired = M.checkTimeBox();
      const shown = !document.getElementById('modal-time-up').hidden;
      const title = document.getElementById('time-up-title').textContent;
      const again = M.checkTimeBox();          /* 二度は聞かない */
      M.closeModals();
      return { before:before, fired:fired, shown:shown, title:title, again:again };
    }""")
    ok("**時間前は聞かない**", t["before"] is False, json.dumps(t, ensure_ascii=False))
    ok("**時間が来たら聞く**", t["fired"] is True and t["shown"] is True,
       json.dumps(t, ensure_ascii=False))
    ok("何分だったかを出す", "5分" in t["title"], json.dumps(t, ensure_ascii=False))
    ok("**二度は聞かない（続けたい人の邪魔をしない）**", t["again"] is False,
       json.dumps(t, ensure_ascii=False))

    # --- 時間制で始めても、期日と記録は通常どおり動く ---
    keep = pg.evaluate("""async () => {
      const M = window.Main, S = window.Storage, K = window.Scheduler;
      const until = async (f, ms) => { const t = Date.now();
        while (!f() && Date.now() - t < (ms || 8000)) await new Promise(r => setTimeout(r, 50)); };
      const before = (await S.getAllLogs()).length;
      await M.startSession({ mode:'review', timeLimitMs: 5 * 60 * 1000 });
      await until(() => { const c = document.querySelector('#choice-list .choice-card');
        return c && getComputedStyle(c).pointerEvents !== 'none'; });
      for (const c of document.querySelectorAll('#choice-list .choice-card')) {
        const b = document.getElementById('btn-confirm');
        if (b && !b.disabled) { break; }
        (c.querySelector('.choice-body') || c).click();
      }
      await until(() => { const b = document.getElementById('btn-confirm'); return b && !b.disabled; });
      document.getElementById('btn-confirm').click();
      await until(() => document.getElementById('screen-quiz')
                          .getAttribute('data-phase') === 'review');
      const atomId = M.state.current.atoms[0].atom_id;
      const dueBefore = (await S.getAtom(atomId)).due_date;
      document.getElementById('btn-next').click();
      /* until の述語に async 関数を渡してはいけない。Promise は必ず truthy なので
         1回目で必ず抜ける（実際に抜けて、書き込み前の数を読んでいた）。 */
      let after = before;
      for (let i = 0; i < 80 && after <= before; i++) {
        await new Promise(r => setTimeout(r, 100));
        after = (await S.getAllLogs()).length;
      }
      const dueAfter = (await S.getAtom(atomId)).due_date;
      return { before:before, after:after,
               dueChanged: dueBefore !== dueAfter };
    }""")
    ok("**時間制でも記録は残る（ノックと違う）**",
       keep["after"] > keep["before"], json.dumps(keep))
    ok("**時間制でも期日は動く（忘却スケジュールを更新する）**",
       keep["dueChanged"] is True, json.dumps(keep))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBZ" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
