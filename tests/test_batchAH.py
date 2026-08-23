#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.53 検証：買い切りライセンス（無料枠200問・鍵の照合・同期での引き継ぎ）"""
import json, os, sys, subprocess, io, glob
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))
def read(f): return io.open(os.path.join(APP, f), encoding="utf-8").read()

# 本物の秘密鍵で発行した鍵。ここに秘密鍵そのものは置かない。
GOOD = ("OMOI1.eyJuIjoiQk9PVEgtVEVTVCIsInQiOjE3NTYwMDAwMDAwMDB9."
        "-2H0zVWaIJ_x2TS5kzEUDkxLSn0TJ23d7-rDjp1gmkc0cRZ7iWREfqGc69hU5D29FFNGwjjaFN7Q_mDQxQnhOQ")
# 署名の最後の1文字を変えた偽物
BAD = GOOD[:-1] + ("A" if GOOD[-1] != "A" else "B")

P1 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
P2 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
for f in ["license.js", "scheduler.js", "drive.js", P1, P2]:
    p = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True)
    ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

idx, sw, css, lic = read("index.html"), read("sw.js"), read("styles.css"), read("license.js")
ok("license.js が読み込まれている", "./license.js?v=" in idx)
ok("起動診断にも入っている（欠けたら名指しで分かる）", 'window.NurseLicense' in idx)
ok("Service Worker のキャッシュ対象にも入っている", "./license.js?v=" in sw)
ok("index.html と sw.js の版が揃っている",
   sorted(set(__import__("re").findall(r"license\.js\?v=([0-9.]+)", idx + sw))) .__len__() == 1)
ok("秘密鍵が配布物に混ざっていない（d は秘密鍵にしかない）", '"d"' not in lic and "'d'" not in lic)
ok("無料枠がホームの1行として出る", 'id="free-gate"' in idx)
ok("購入案内のモーダルがある", 'id="modal-buy"' in idx)
ok("設定にライセンス欄がある", 'id="lic-key"' in idx)
ok("無料枠の色に警告色（赤）を使っていない",
   "#c8912a" in css and ".free-gate{" in css)
ok("購入案内で「復習は続く」を先に言っている", "buy-keep" in idx and "復習は" in idx)

drv = read("drive.js")
ok("solved_ever は大きい方を採る", "'solved_ever'" in drv and "META_MAX_KEYS" in drv)
ok("license_key は消えない側が勝つ", "META_KEEP_KEYS" in drv and "'license_key'" in drv)


def _external(t):
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t)


def runtime_checks():
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox"])
        pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append("console:" + m.text)
              if m.type == "error" and not _external(m.text) else None)
        pg.goto(URL, wait_until="load")
        pg.wait_for_function("window.__APP_READY === true", timeout=20000)
        pg.wait_for_timeout(1500)
        try: pg.click("#welcome-start", timeout=2500)
        except Exception: pass
        pg.wait_for_timeout(600)

        # ---------- 鍵の照合 ----------
        r = pg.evaluate("""async ([good, bad]) => {
          const L = window.NurseLicense;
          const g = await L.verify(good);
          const b = await L.verify(bad);
          const junk = await L.verify('これは鍵ではありません');
          // 折り返して貼られた鍵（メールから写すと必ず起きる）
          const wrapped = await L.verify(good.slice(0, 40) + '\\n  ' + good.slice(40));
          return { good: g.ok, goodName: (g.payload || {}).n,
                   bad: b.ok, badWhy: b.reason,
                   junk: junk.ok, junkWhy: junk.reason,
                   wrapped: wrapped.ok, limit: L.FREE_LIMIT };
        }""", [GOOD, BAD])
        ok("正しい鍵は通る", r["good"] is True, json.dumps(r))
        ok("鍵の中の購入者名が読める（問い合わせの照合用）",
           r["goodName"] == "BOOTH-TEST", json.dumps(r))
        ok("1文字だけ違う偽物は落ちる", r["bad"] is False, json.dumps(r))
        ok("偽物の理由が「署名」と分かる", r["badWhy"] == "signature", json.dumps(r))
        ok("でたらめな文字列は「形が違う」と分かる", r["junkWhy"] == "format", json.dumps(r))
        ok("折り返して貼っても通る（メールから写すと必ず折り返す）",
           r["wrapped"] is True, json.dumps(r))
        ok("無料枠は200問", r["limit"] == 200, json.dumps(r))

        # ---------- 無料枠の判定 ----------
        r = pg.evaluate("""async () => {
          const L = window.NurseLicense;
          await L.deactivate();
          return { at0: L.gate(0), at199: L.gate(199), at200: L.gate(200), at999: L.gate(999) };
        }""")
        ok("最初は止まらない", r["at0"]["locked"] is False, json.dumps(r["at0"]))
        ok("199問では止まらない", r["at199"]["locked"] is False, json.dumps(r["at199"]))
        ok("200問で止まる", r["at200"]["locked"] is True, json.dumps(r["at200"]))
        ok("残り数が正しい", r["at199"]["left"] == 1, json.dumps(r["at199"]))
        ok("上限を超えても残りは負にならない",
           r["at999"]["left"] == 0, json.dumps(r["at999"]))

        # ---------- 鍵を入れると全部開く ----------
        r = pg.evaluate("""async (good) => {
          const L = window.NurseLicense, S = window.Storage;
          const bad = await L.activate('OMOI1.aaa.bbb');
          const savedAfterBad = (await S.loadMeta()).license_key || null;
          const good2 = await L.activate(good);
          const saved = (await S.loadMeta()).license_key || null;
          const g = L.gate(9999);
          return { badOk: bad.ok, savedAfterBad, goodOk: good2.ok,
                   saved: !!saved, paid: g.paid, locked: g.locked, isPaid: L.isPaid() };
        }""", GOOD)
        ok("偽物は保存しない（入れたのに効かない、を作らない）",
           r["badOk"] is False and r["savedAfterBad"] is None, json.dumps(r))
        ok("正しい鍵は保存される", r["goodOk"] is True and r["saved"] is True, json.dumps(r))
        ok("鍵があれば何問解いても止まらない",
           r["paid"] is True and r["locked"] is False, json.dumps(r))

        # ---------- 出題そのものが止まるか ----------
        r = pg.evaluate("""async () => {
          const K = window.Scheduler;
          const free = await K.buildQueue({ mode:'random', count:10, solvedOnly:true });
          const paid = await K.buildQueue({ mode:'random', count:10 });
          return { freeN: free.questions.length, freeLocked: !!free.locked,
                   freeWhy: free.reason || '', paidN: paid.questions.length };
        }""")
        ok("無料枠を使い切ると初見の問題は出ない", r["freeN"] == 0, json.dumps(r))
        ok("止まった理由が「無料枠」だと分かる", r["freeLocked"] is True, json.dumps(r))
        ok("鍵があれば普通に出る", r["paidN"] > 0, json.dumps(r))

        # ---------- 復習は止めない（いちばん大事な一線） ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, K = window.Scheduler;
          const atoms = await S.getAllAtoms();
          const now = Date.now(), t0 = now - 86400000;
          const patches = {}, logs = [];
          atoms.slice(0, 6).forEach((a, i) => {
            patches[a.atom_id] = { answer_count:1, correct_count:1, last_eval:'normal',
                                   last_answered_at:t0, due_date: now - 60000, _unlearned:0 };
            logs.push({ atom_id:a.atom_id, answered_at:t0+i, eval:'normal',
                        is_correct:true, schedule_updated:true, interval_code:'1d' });
          });
          await S.replaceAllLogs(logs);
          await S.updateAtomsBulk(patches);
          // 未購入に戻す
          await window.NurseLicense.deactivate();
          const rev = await K.buildQueue({ mode:'review', count:10 });
          return { n: rev.questions.length, paid: window.NurseLicense.isPaid() };
        }""")
        ok("鍵が無くても復習は出る（記録を人質に取らない）",
           r["paid"] is False and r["n"] > 0, json.dumps(r))

        # ---------- 到達点は後戻りしない ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, K = window.Scheduler;
          await S.setMeta('solved_ever', 150);
          const h = await K.getHomeState();
          const after = (await S.loadMeta()).solved_ever;
          return { home: h.solved_ever, after, now: h.solved_questions };
        }""")
        ok("解いた数が減っても到達点は下がらない",
           r["home"] >= 150 and r["after"] >= 150, json.dumps(r))

        # ---------- 端末をまたぐ引き継ぎ ----------
        r = pg.evaluate("""async (good) => {
          const D = window.Drive;
          if (!D || !D.mergeMeta) { return { skip: true }; }
          const A = { license_key: good, solved_ever: 40 };
          const B = { solved_ever: 210, day_boundary_hour: 6 };
          // B のほうが設定は新しい。それでも鍵は消えてはいけない。
          const m1 = D.mergeMeta(A, B, 1000, 9000);
          const m2 = D.mergeMeta(B, A, 9000, 1000);
          return { k1: m1.license_key === good, k2: m2.license_key === good,
                   s1: m1.solved_ever, s2: m2.solved_ever };
        }""", GOOD)
        if r.get("skip"):
            ok("端末をまたぐ引き継ぎ（mergeMeta が公開されていない）", False, "no mergeMeta")
        else:
            ok("買った端末の鍵が、買っていない端末へ渡る", r["k1"] is True, json.dumps(r))
            ok("設定が新しい側が鍵を持っていなくても消えない", r["k2"] is True, json.dumps(r))
            ok("解いた数は大きい方を採る", r["s1"] == 210 and r["s2"] == 210, json.dumps(r))

        ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
        br.close()


runtime_checks()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAH" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
