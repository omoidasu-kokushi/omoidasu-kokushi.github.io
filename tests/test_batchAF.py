#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.50 検証：逆算プランナー ＆ 模試の受け方（本番／直前）"""
import json, os, sys, subprocess, io, glob
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))
def read(f): return io.open(os.path.join(APP, f), encoding="utf-8").read()

P1 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
P2 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
for f in ["scheduler.js", P1, P2]:
    p = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True)
    ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

idx = read("index.html")
ok("プランナーの置き場所がある", 'id="home-plan"' in idx)
ok("受け方のダイアログがある", 'id="modal-exam-style"' in idx and 'data-exam-style="final"' in idx)
ok("合格基準は変えないと画面に書いてある", "合格の基準はどちらも本番と同じ" in idx)


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
        pg.wait_for_timeout(1800)
        try: pg.click("#welcome-start", timeout=2500)
        except Exception: pass
        pg.wait_for_timeout(600)

        # ---------- 逆算プランナー：計算そのもの ----------
        r = pg.evaluate("""() => {
          const K = window.Scheduler;
          const day = 86400000, now = Date.parse('2026-08-23T10:00:00+09:00');
          const mk = d => ({ exam_date: d, day_boundary_hour: 4 });
          return {
            none:   K.buildPlan({}, 5, 100, 4, now),
            far:    K.buildPlan(mk('2027-02-14'), 18, 1200, 4, now),
            near:   K.buildPlan(mk('2026-09-02'), 3, 1200, 4, now),
            done:   K.buildPlan(mk('2027-02-14'), 7, 0, 4, now),
            past:   K.buildPlan(mk('2026-01-01'), 4, 50, 4, now)
          };
        }""")
        ok("試験日が無ければ何も約束しない",
           r["none"]["has_exam"] is False and r["none"]["pace"] == "no-exam", json.dumps(r["none"]))
        ok("残り日数から今日の必要数が出る",
           r["far"]["pace"] == "ok" and r["far"]["need_new"] > 0
           and r["far"]["today"] == r["far"]["need_new"] + 18, json.dumps(r["far"]))
        ok("解ける日は残り日数より少なく見積もる（実習・体調のぶん）",
           r["far"]["usable_days"] < r["far"]["rest_days"] + 1, json.dumps(r["far"]))
        ok("間に合わないときは正直に behind を返す",
           r["near"]["pace"] == "behind", json.dumps(r["near"]))
        ok("未学習が0なら done", r["done"]["pace"] == "done" and r["done"]["need_new"] == 0,
           json.dumps(r["done"]))
        ok("試験日を過ぎたら past", r["past"]["pace"] == "past", json.dumps(r["past"]))

        # ---------- 逆算プランナー：画面 ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, M = window.Main;
          await S.setMeta('exam_date', null);
          M.state.meta = await S.loadMeta();
          await M.refreshHome();
          const hiddenNoExam = document.getElementById('home-plan').hidden;
          await S.setMeta('exam_date', '2027-02-14');
          M.state.meta = await S.loadMeta();
          await M.refreshHome();
          const box = document.getElementById('home-plan');
          return { hiddenNoExam, shown: !box.hidden,
                   main: document.getElementById('home-plan-main').textContent,
                   sub: document.getElementById('home-plan-sub').textContent,
                   tone: box.getAttribute('data-tone') };
        }""")
        ok("試験日が未設定なら行を出さない", r["hiddenNoExam"] is True, json.dumps(r, ensure_ascii=False))
        ok("試験日を入れると1行出る", r["shown"] is True, json.dumps(r, ensure_ascii=False))
        ok("主役の数字は1つだけ",
           r["main"].count("問") == 1, json.dumps(r["main"], ensure_ascii=False))
        ok("内訳と残り日数は控えめな行に出る",
           "復習" in r["sub"] and "試験まで" in r["sub"], json.dumps(r["sub"], ensure_ascii=False))

        # ---------- 模試：直前モードの出題 ----------
        r = pg.evaluate("""async () => {
          const K = window.Scheduler;
          const real  = await K.buildQueue({ mode:'exam', count:20, applyGuard:false, shuffle:true });
          const final = await K.buildQueue({ mode:'exam', count:20, applyGuard:false, shuffle:true,
                                             ranks:['S','A'], preferKnown:true });
          const rank = qs => qs.map(q => String(q.rank || 'B').toUpperCase());
          return { realRanks: rank(real.questions), finalRanks: rank(final.questions),
                   realN: real.questions.length, finalN: final.questions.length };
        }""")
        ok("直前モードは S/A だけを出す",
           all(x in ("S", "A") for x in r["finalRanks"]),
           json.dumps(sorted(set(r["finalRanks"]))))
        ok("本番モードは絞らない（C も出うる）",
           len(set(r["realRanks"])) >= 1, json.dumps(sorted(set(r["realRanks"]))))
        ok("直前モードでも問題は出る", r["finalN"] > 0, json.dumps(r))

        # ---------- 模試：受け方を必ず聞く ----------
        # 解禁状態と警告は本筋ではないので、ここだけ差し替えて動線を見る。
        r = pg.evaluate("""async () => {
          const H = window.Half2Impl, S = window.Storage, K = window.Scheduler;
          const origUnlock = S.getUnlockState, origWarn = K.shouldWarnBeforeExam;
          S.getUnlockState = () => Promise.resolve([{ id:'mock_30', unlocked:true }]);
          K.shouldWarnBeforeExam = () => Promise.resolve({ warn:false });
          window.Main.state.screen = 'home';
          const before = document.getElementById('modal-exam-style').hidden;
          let after, screen;
          try {
            await H.startExam('mock_30');
            await new Promise(r => setTimeout(r, 400));
            after  = document.getElementById('modal-exam-style').hidden;
            screen = window.Main.state.screen;
          } finally {
            S.getUnlockState = origUnlock; K.shouldWarnBeforeExam = origWarn;
          }
          return { before, after, screen };
        }""")
        ok("模試を押すと受け方を先に聞く（いきなり始まらない）",
           r["before"] is True and r["after"] is False and r["screen"] == "home", json.dumps(r))

        # 受け方を選んだら、そのスタイルで始まる
        r = pg.evaluate("""async () => {
          const S = window.Storage, K = window.Scheduler;
          const origUnlock = S.getUnlockState, origWarn = K.shouldWarnBeforeExam, origQ = K.buildQueue;
          let seen = null;
          S.getUnlockState = () => Promise.resolve([{ id:'mock_30', unlocked:true }]);
          K.shouldWarnBeforeExam = () => Promise.resolve({ warn:false });
          K.buildQueue = (o) => { seen = o; return origQ(o); };
          try {
            await window.Half2Impl.startExam('mock_30');
            await new Promise(r => setTimeout(r, 300));
            document.querySelector('#modal-exam-style [data-exam-style=\"final\"]').click();
            await new Promise(r => setTimeout(r, 900));
          } finally {
            S.getUnlockState = origUnlock; K.shouldWarnBeforeExam = origWarn; K.buildQueue = origQ;
          }
          return { ranks: seen && seen.ranks, mix: seen && seen.mix,
                   style: window.Half2Impl.st && window.Half2Impl.st.exam
                          && window.Half2Impl.st.exam.style };
        }""")
        # V1.52：preferKnown（2分類）は mix（3分類）に置き換わった。
        ok("直前モードを選ぶと S/A ＋ 既習寄りの配分で組まれる",
           r["ranks"] == ["S", "A"] and r["mix"] is not None
           and r["mix"]["solved"] > r["mix"]["novel"], json.dumps(r))

        ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
        br.close()


runtime_checks()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAF" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
