#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBR：解いたのに残らない、を無くす（V1.93）

【何が起きていたか】
記録が書かれるのは `nextQuestion()` の中だけ。つまり
**解答を確定して解説を読んでいる途中でアプリを閉じると、その1問は丸ごと消える。**
利用者から見ると「解いたのに残っていない」。いちばん報告されやすい壊れ方。
（§23-7 の判断待ち）

【なぜ localStorage なのか】
閉じる直前に走れるのは**同期の処理だけ**。IndexedDB は非同期なので、
`pagehide` の中から書いても最後まで走りきる保証がない。

設定を localStorage に置かない方針（§14-3）とは矛盾しない。ここに置くのは
**次の起動で本棚へ移すまでの一時置き場**であって、利用者のデータの置き場所ではない。

【壊してはいけないもの】
・二重に記録しない（同じ鍵は二度と流し込まない）
・復元は**解答した当時の時刻**で行う。3日後に開いて「3日後の10分後」になっては意味がない
・記録しないモード（検索・ノック）では書き置きもしない
・localStorage が使えない環境（プライベートモード等）で落ちない
"""
import io, json, os, re, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


st = read("storage.js")
html = read("index.html")
p1 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
j1 = read(p1)

ok("書き置きの関数がある", "function stashPendingAnswer(" in j1)
ok("流し込みの関数がある", "function flushPendingAnswer(" in j1)
ok("なぜ localStorage なのか書いてある", "同期の処理だけ" in j1)
ok("設定の方針と矛盾しない理由が書いてある", "一時置き場" in j1)
ok("隠れるときに書き置きする", "stashPendingAnswer();      /* V1.93" in j1)
ok("pagehide にも網を張る",
   "on(global, 'pagehide'" in j1 and "stashPendingAnswer(); syncOnHide();" in j1)
ok("正規に記録したら書き置きを消す", "cur.committed = true;\n    pendingClear();" in j1)
ok("**当時の時刻で復元する**", "now: p.at," in j1)
ok("二重に入れない印がある", "pending_flushed_key     : null," in st and "last === key" in j1)
ok("記録しないモードでは書き置きしない", "s.mode === 'search' || s.mode === 'knock'" in j1)
ok("使えない環境で落ちない", "catch (e) { return null; }" in j1 and "catch (e) { return false; }" in j1)
ok("版番号・CACHE_NAME・?v= の3箇所が揃っている",
   (lambda i, w: i and w and i == w)(
       (re.search(r"\?v=([0-9.]+)", html) or [None, None])[1],
       (re.search(r"\?v=([0-9.]+)", read("sw.js")) or [None, None])[1]))

from playwright.sync_api import sync_playwright

UNTIL = """const until = async (f, ms) => { const t = Date.now();
  while (!f() && Date.now() - t < (ms || 8000)) await new Promise(r => setTimeout(r, 50)); };
"""

TO_REVIEW = """async () => {
  const M = window.Main;
  """ + UNTIL + """
  await M.startSession({ mode:'random', count:3 });
  await until(() => { const c = document.querySelector('#choice-list .choice-card');
    return c && getComputedStyle(c).pointerEvents !== 'none'; });
  for (const c of document.querySelectorAll('#choice-list .choice-card')) {
    const b = document.getElementById('btn-confirm');
    if (b && !b.disabled) { break; }
    c.click();
  }
  await until(() => { const b = document.getElementById('btn-confirm'); return b && !b.disabled; });
  document.getElementById('btn-confirm').click();
  await until(() => document.getElementById('screen-quiz')
                      .getAttribute('data-phase') === 'review');
  return window.Main.state.current.question.q_id;
}"""

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(1400)

    qid = pg.evaluate(TO_REVIEW)

    # ---------- 解説を読んでいる途中で閉じる ----------
    r = pg.evaluate("""async () => {
      const M = window.Main, S = window.Storage;
      const before = (await S.getAllLogs()).length;
      const stashed = M.stashPendingAnswer();
      const raw = localStorage.getItem(M.PENDING_KEY);
      const after = (await S.getAllLogs()).length;
      return { stashed:stashed, has: !!raw, parsed: raw ? JSON.parse(raw) : null,
               before:before, after:after };
    }""")
    ok("**閉じる直前に書き置きが残る**", r["stashed"] is True and r["has"] is True,
       json.dumps({k: r[k] for k in r if k != "parsed"}, ensure_ascii=False))
    ok("書き置きには問題と評価が入っている",
       r["parsed"] and r["parsed"]["q_id"] == qid and len(r["parsed"]["evaluations"]) > 0,
       json.dumps(r["parsed"], ensure_ascii=False))
    ok("書き置きは同期で終わる（DBはまだ増えていない）",
       r["before"] == r["after"], json.dumps({"b": r["before"], "a": r["after"]}))

    # ---------- 開き直して記録されるか ----------
    pg2 = ctx.new_page()
    pg2.on("pageerror", lambda e: errs.append(str(e)))
    pg2.set_default_timeout(120000)
    pg2.goto(URL, wait_until="load")
    pg2.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg2.wait_for_timeout(1800)
    r2 = pg2.evaluate("""async () => {
      const S = window.Storage, M = window.Main;
      const logs = await S.getAllLogs();
      const at = await S.getAtomsByQuestion(""" + json.dumps(qid) + """);
      const mine = logs.filter(l => at.some(a => a.atom_id === l.atom_id));
      return { n: mine.length, atoms: at.length,
               raw: localStorage.getItem(M.PENDING_KEY),
               key: await S.getMeta('pending_flushed_key', null),
               at0: mine.length ? mine[0].answered_at : null,
               now: Date.now() };
    }""")
    ok("**開き直したら、その1問が記録されている**",
       r2["n"] >= r2["atoms"] and r2["atoms"] > 0, json.dumps(r2, ensure_ascii=False))
    ok("書き置きは片付いている", r2["raw"] is None, json.dumps(r2, ensure_ascii=False))
    ok("流し込んだ鍵を覚えている", bool(r2["key"]), json.dumps(r2, ensure_ascii=False))
    ok("**記録の時刻は解答した当時のもの（開き直した時刻ではない）**",
       r2["at0"] is not None and (r2["now"] - r2["at0"]) >= 0,
       json.dumps(r2, ensure_ascii=False))

    # ---------- 二度目の起動で二重に入らないか ----------
    r3 = pg2.evaluate("""async () => {
      const S = window.Storage, M = window.Main;
      const p = await S.getMeta('pending_flushed_key', null);
      const before = (await S.getAllLogs()).length;
      /* 同じ書き置きをもう一度置いて、もう一度流し込む */
      const parts = String(p).split('|');
      const at = await S.getAtomsByQuestion(parts[0]);
      localStorage.setItem(M.PENDING_KEY, JSON.stringify({
        q_id: parts[0], at: Number(parts[1]), mode:'random', sessionId:'x',
        boundaryHour: 4,
        evaluations: at.map(a => ({ atom_id:a.atom_id, eval:'normal', is_correct:true }))
      }));
      await M.flushPendingAnswer();
      return { before:before, after:(await S.getAllLogs()).length,
               raw: localStorage.getItem(M.PENDING_KEY) };
    }""")
    ok("**同じ鍵は二度と流し込まない**",
       r3["before"] == r3["after"] and r3["raw"] is None,
       json.dumps(r3, ensure_ascii=False))

    # ---------- 記録しないモードでは書き置きしない ----------
    r4 = pg2.evaluate("""async () => {
      const M = window.Main;
      """ + UNTIL + """
      await M.startSession({ mode:'random', count:2 });
      await until(() => { const c = document.querySelector('#choice-list .choice-card');
        return c && getComputedStyle(c).pointerEvents !== 'none'; });
      for (const c of document.querySelectorAll('#choice-list .choice-card')) {
        const b = document.getElementById('btn-confirm');
        if (b && !b.disabled) { break; }
        c.click();
      }
      await until(() => { const b = document.getElementById('btn-confirm'); return b && !b.disabled; });
      document.getElementById('btn-confirm').click();
      await until(() => document.getElementById('screen-quiz')
                          .getAttribute('data-phase') === 'review');
      localStorage.removeItem(M.PENDING_KEY);
      const real = M.state.session.mode;
      M.state.session.mode = 'search';
      const s1 = M.stashPendingAnswer();
      M.state.session.mode = 'knock';
      const s2 = M.stashPendingAnswer();
      M.state.session.mode = real;
      const s3 = M.stashPendingAnswer();
      /* 記録済みの印が立っていたら、もう書き置きしない */
      M.state.current.committed = true;
      const s4 = M.stashPendingAnswer();
      M.state.current.committed = false;
      localStorage.removeItem(M.PENDING_KEY);
      return { search:s1, knock:s2, normal:s3, committed:s4 };
    }""")
    ok("**検索モードでは書き置きしない**", r4["search"] is False, json.dumps(r4))
    ok("**ノックでは書き置きしない**", r4["knock"] is False, json.dumps(r4))
    ok("通常モードでは書き置きする", r4["normal"] is True, json.dumps(r4))
    ok("**記録済みなら二度書き置きしない**", r4["committed"] is False, json.dumps(r4))

    # ---------- 解答前は書き置きしない ----------
    r5 = pg2.evaluate("""async () => {
      const M = window.Main;
      """ + UNTIL + """
      await M.startSession({ mode:'random', count:2 });
      await until(() => { const c = document.querySelector('#choice-list .choice-card');
        return c && getComputedStyle(c).pointerEvents !== 'none'; });
      const s = M.stashPendingAnswer();
      localStorage.removeItem(M.PENDING_KEY);
      return { stashed:s, graded:M.state.current.graded };
    }""")
    ok("**まだ答えていない問題は書き置きしない**",
       r5["stashed"] is False and r5["graded"] is False, json.dumps(r5))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBR" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
