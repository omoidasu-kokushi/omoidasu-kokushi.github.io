#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.60 検証：保存領域が尽きたときの振る舞い ＆ 消されないための宣言"""
import json, os, sys, io, subprocess, glob
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))
def read(f): return io.open(os.path.join(APP, f), encoding="utf-8").read()

P1 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
P2 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
for f in ["storage.js", P1, P2]:
    p = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True)
    ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

st, s1, s2, idx = read("storage.js"), read(P1), read(P2), read("index.html")
ok("文言の変換は1箇所（describeError）", st.count("function describeError") == 1)
ok("保存の失敗はトーストでなく覆いで出す", 'id="modal-save-error"' in idx)
ok("覆いから書き出しへ逃がせる", 'id="save-error-backup"' in idx)
ok("設定に保存領域の欄がある", 'id="store-row"' in idx and 'id="btn-persist"' in idx)
ok("起動直後には persist を要求しない",
   "requestPersist" not in s1, "part1 で呼んでいる")
ok("投資が発生したあとに要求する（チュートリアル完了・取り込み）",
   s2.count("S.requestPersist()") >= 3)


def _external(t):
    # このスイートは【わざと保存を失敗させる】ので、アプリが出す
    # console.error は正しい振る舞い。ここで拾うと、直したはずのものが
    # 赤く出て意味が反転する。意図した失敗だけを名指しで除く。
    if "QuotaExceededError" in t or "[nextQuestion]" in t:
        return True
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t)


UNTIL = """const until = async (f, ms) => { const t = Date.now();
  while (!f() && Date.now() - t < (ms || 8000)) await new Promise(r => setTimeout(r, 50)); };
"""


def runtime_checks():
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox"])
        pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append("console:" + m.text)
              if m.type == "error" and not _external(m.text) else None)
        pg.goto(URL, wait_until="load")
        pg.wait_for_function("window.__APP_READY === true", timeout=30000)
        pg.wait_for_timeout(1200)
        try: pg.click("#welcome-start", timeout=2500)
        except Exception: pass
        pg.wait_for_timeout(500)

        # ---------- 文言 ----------
        r = pg.evaluate("""() => {
          const S = window.Storage;
          const mk = (name, msg) => { const e = new Error(msg || name); e.name = name; return e; };
          return {
            quota: S.describeError(mk('QuotaExceededError', 'quota')),
            closed: S.describeError(mk('InvalidStateError', 'db closing')),
            unknown: S.describeError(mk('WeirdError', 'なにか')),
            raw: S.describeError(new Error('quota bytes'))
          };
        }""")
        ok("満杯は「保存領域がいっぱい」と伝わる言葉になる",
           "保存領域がいっぱい" in r["quota"], r["quota"][:60])
        ok("満杯のときに次にやることが書いてある",
           "バックアップ" in r["quota"], r["quota"][:60])
        ok("名前が quota でなくても本文で拾える",
           "保存領域がいっぱい" in r["raw"], r["raw"][:60])
        ok("閉じられたときは開き直しを案内する", "開き直" in r["closed"], r["closed"][:50])
        ok("心当たりの無い失敗でも元の文言を捨てない",
           "WeirdError" in r["unknown"], r["unknown"][:80])

        # ---------- 空き容量 ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage;
          const info = await S.storageInfo();
          const small = await S.checkRoomFor(10);
          const huge  = await S.checkRoomFor(100000000);
          return { supported: info.supported, hasQuota: info.quota > 0,
                   pct: info.pct, smallOk: small.ok, hugeOk: huge.ok,
                   hugeNeed: huge.need };
        }""")
        ok("使用量と上限が取れる", r["supported"] is True and r["hasQuota"] is True, json.dumps(r))
        ok("普通の取り込みは通る", r["smallOk"] is True, json.dumps(r))
        ok("入りきらない量は始める前に断る", r["hugeOk"] is False, json.dumps(r))

        # ---------- 解答の保存が失敗したとき ----------
        r = pg.evaluate("""async () => {
          const M = window.Main;
          """ + UNTIL + """
          await M.startSession({ mode:'random', count:3 });
          await until(() => { const c = document.querySelector('#choice-list .choice-card');
            return c && getComputedStyle(c).pointerEvents !== 'none'; });
          /* 「2つ選べ」の問題が先頭に来ることがある。1枚だけ押すと
             確定が押せないまま止まる。必要な枚数まで押す（V1.89）。 */
          for (const c of document.querySelectorAll('#choice-list .choice-card')) {
            const b = document.getElementById('btn-confirm');
            if (b && !b.disabled) { break; }
            c.click();
          }
          await until(() => { const b = document.getElementById('btn-confirm');
            return b && !b.disabled; });
          document.getElementById('btn-confirm').click();
          await until(() => document.getElementById('screen-quiz')
                              .getAttribute('data-phase') === 'review');
          const idx0 = M.state.session.index;
          const logs0 = (await window.Storage.getAllLogs()).length;
          const origPut = IDBObjectStore.prototype.put;
          IDBObjectStore.prototype.put = function () {
            const e = new Error('quota'); e.name = 'QuotaExceededError'; throw e; };
          let out = {};
          try {
            document.getElementById('btn-next').click();
            await until(() => !document.getElementById('modal-save-error').hidden, 6000);
            out.modalOpen = !document.getElementById('modal-save-error').hidden;
            out.body = (document.getElementById('save-error-body') || {}).textContent || '';
            out.idxBefore = idx0; out.idxAfter = M.state.session.index;
          } finally { IDBObjectStore.prototype.put = origPut; }
          out.logsAfter = (await window.Storage.getAllLogs()).length;
          out.logsBefore = logs0;
          return out;
        }""")
        ok("保存に失敗したら覆いで止める（数秒で消えるトーストにしない）",
           r["modalOpen"] is True, json.dumps({k: r[k] for k in r if k != 'body'}))
        ok("失敗の理由が人の言葉で出る",
           "保存領域がいっぱい" in r["body"], r["body"][:60])
        ok("次の問題へ進まない（解いたつもりで記録が無い、を作らない）",
           r["idxAfter"] == r["idxBefore"], json.dumps(r))
        ok("記録も増えていない（中途半端に残らない）",
           r["logsAfter"] == r["logsBefore"], json.dumps(r))

        # 覆いを閉じて、次は普通に保存できること
        r = pg.evaluate("""async () => {
          const M = window.Main;
          """ + UNTIL + """
          M.closeModals ? M.closeModals() : document.getElementById('modal-layer').click();
          const idx0 = M.state.session.index;
          const before = (await window.Storage.getAllLogs()).length;
          document.getElementById('btn-next').click();
          await until(() => M.state.session.index !== idx0, 8000);
          return { moved: M.state.session.index !== idx0,
                   added: (await window.Storage.getAllLogs()).length - before };
        }""")
        ok("原因が消えれば、同じ問題をそのまま保存できる",
           r["moved"] is True and r["added"] > 0, json.dumps(r))

        # ---------- 設定の保存領域欄 ----------
        r = pg.evaluate("""async () => {
          await window.Half2Impl.openSettings();
          """ + UNTIL + """
          await until(() => !document.getElementById('store-row').hidden, 6000);
          const fill = document.getElementById('store-bar-fill');
          return { shown: !document.getElementById('store-row').hidden,
                   note: document.getElementById('store-note').textContent,
                   tone: fill.getAttribute('data-tone'),
                   warnShown: !document.getElementById('store-warn').hidden,
                   btnShown: !document.getElementById('btn-persist').hidden };
        }""")
        ok("保存領域の欄が出る", r["shown"] is True, json.dumps(r, ensure_ascii=False))
        ok("使用量が数字で読める", "使用" in r["note"] and "MB" in r["note"], r["note"])
        ok("空きが十分なときは警告色にしない", r["tone"] == "ok", json.dumps(r))
        ok("消えない設定になっていなければ、その旨と手段を出す",
           r["warnShown"] is True and r["btnShown"] is True, json.dumps(r))

        # ---------- 取り込み前の空き容量チェック ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, H = window.Half2Impl;
          const orig = S.checkRoomFor;
          S.checkRoomFor = () => Promise.resolve(
            { ok:false, unknown:false, need: 900*1048576, free: 3*1048576,
              usage: 1, quota: 2 });
          let out = {};
          try {
            await H.runImport('[{"q_id":"X","unit":"u","major":"m","medium":"d","sub_item":"s",'
              + '"rank":"A","question_type":"single","select_count":1,"stem":"x",'
              + '"atoms":[{"text":"a","is_correct":true},{"text":"b","is_correct":false}]}]');
            await new Promise(r => setTimeout(r, 500));
            out.report = document.getElementById('import-report').textContent;
            out.isError = document.getElementById('import-report').className.indexOf('is-error') >= 0;
          } finally { S.checkRoomFor = orig; }
          return out;
        }""")
        ok("空きが足りなければ取り込みを始めない",
           "保存領域が足りません" in r["report"], r["report"][:70])
        ok("必要量と空きを数字で出す（何をどれだけ空ければよいか分かる）",
           "MB" in r["report"] and r["isError"] is True, r["report"][:90])

        ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
        br.close()


runtime_checks()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAM" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
