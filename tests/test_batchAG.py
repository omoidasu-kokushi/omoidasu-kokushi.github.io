#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.51 検証：既出／初見の混合比・カレンダー書き出し・間違いノート"""
import json, os, sys, subprocess, io, glob
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))
def read(f): return io.open(os.path.join(APP, f), encoding="utf-8").read()

P2 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
for f in ["scheduler.js", P2]:
    p = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True)
    ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

idx, css = read("index.html"), read("styles.css")
ok("カレンダー書き出しの入口がある", 'id="btn-ics"' in idx)
ok("間違いノートの入口がある", 'id="btn-note-print"' in idx)
ok("用紙を4種から選べる",
   all(('value="%s"' % v) in idx for v in ["A4", "A5", "B5", "B4"]))
ok("印刷専用の紙面がある", 'id="print-sheet"' in idx)
ok("画面には出さない", "#print-sheet{ display:none; }" in css)
ok("1問が途中で切れない指定がある", "break-inside:avoid" in css)


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

        # ---------- 既出／初見の混合 ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, K = window.Scheduler;
          // 一部の問題だけ「全肢を解いた」状態にする
          const qs = await S.getAllQuestions();
          /* 中項目ごとに【1問だけ】解いた状態にする。
             まとめて先頭40問を解くと、その中項目が丸ごと解答済みになり、
             「同じ中項目の別の問題」＝familiar が構造的に作れない。 */
          const byMed = {};
          qs.forEach(q => { (byMed[q.medium || ''] = byMed[q.medium || ''] || []).push(q); });
          const target = Object.keys(byMed)
            .filter(m => byMed[m].length >= 2)
            .slice(0, 40)
            .map(m => byMed[m][0]);
          const patches = {}, logs = [];
          const t0 = Date.now() - 86400000;
          for (const q of target) {
            const at = await S.getAtomsByQuestion(q.q_id);
            at.forEach((a, i) => {
              patches[a.atom_id] = {
                answer_count: 2, correct_count: 2, last_eval: 'easy',
                last_answered_at: t0, _unlearned: 0 };
              /* 「解いた」は台帳（progress_log）が根拠。
                 アトムの数字だけ書き換えても未学習のまま扱われる。 */
              logs.push({ atom_id: a.atom_id, answered_at: t0 + i,
                          eval: 'easy', is_correct: true,
                          schedule_updated: true, interval_code: '30d' });
            });
          }
          await S.replaceAllLogs(logs);
          await S.updateAtomsBulk(patches);
          const known = new Set(target.map(q => q.q_id));
          const learnedSubs = new Set(target.map(q => q.medium).filter(Boolean));
          const pick = async (mix) => {
            const q = await K.buildQueue({ mode:'exam', count:20, applyGuard:false,
                                           shuffle:true, mix });
            let solved = 0, familiar = 0, novel = 0;
            for (const x of q.questions) {
              if (known.has(x.q_id)) { solved++; }
              else if (learnedSubs.has(x.medium)) { familiar++; }
              else { novel++; }
            }
            return { total: q.questions.length, solved, familiar, novel };
          };
          return {
            real:  await pick({ solved:0.25, familiar:0.60, novel:0.15 }),
            final: await pick({ solved:0.55, familiar:0.45, novel:0.00 }),
            zero:  await pick({ solved:0,    familiar:0,    novel:1.00 })
          };
        }""")
        ok("本番モードは「解いた問題」を出しすぎない（測定を汚さない）",
           r["real"]["solved"] <= r["real"]["total"] * 0.4, json.dumps(r["real"]))
        ok("直前モードのほうが「解いた問題」が多い",
           r["final"]["solved"] >= r["real"]["solved"], json.dumps(r))
        ok("直前モードは未習の範囲をぶつけない",
           r["final"]["novel"] <= r["final"]["total"] * 0.2, json.dumps(r["final"]))
        ok("未習だけを指定すれば未習が中心になる",
           r["zero"]["novel"] >= r["zero"]["total"] * 0.5, json.dumps(r["zero"]))
        ok("どの比率でも問題数は減らない",
           r["real"]["total"] == 20 and r["final"]["total"] == 20, json.dumps(r))
        ok("本番モードの主成分は「知識は既習・問題は初見」",
           r["real"]["familiar"] >= r["real"]["solved"], json.dumps(r["real"]))

        # ---------- カレンダー書き出し ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, H = window.Half2Impl;
          const atoms = await S.getAllAtoms();
          const day = 86400000, now = Date.now();
          const patches = {};
          patches[atoms[0].atom_id] = { due_date: now + day };
          patches[atoms[1].atom_id] = { due_date: now + day };
          patches[atoms[2].atom_id] = { due_date: now + 3 * day };
          patches[atoms[3].atom_id] = { due_date: now - 5 * day };   // 期日を過ぎたもの
          patches[atoms[4].atom_id] = { due_date: now + 90 * day };  // 遠すぎるもの
          await S.updateAtomsBulk(patches);
          const rep = await H.exportReviewCalendar();
          const t = rep.text || '';
          return { events: rep.events,
                   isCal: t.indexOf('BEGIN:VCALENDAR') === 0,
                   vevents: (t.match(/BEGIN:VEVENT/g) || []).length,
                   hasAlarm: t.indexOf('BEGIN:VALARM') >= 0,
                   hasFar: t.indexOf('オモイダス') >= 0,
                   stamped: !!(await S.loadMeta()).ics_exported_at };
        }""")
        ok("iCalendar として書き出せる", r["isCal"] is True, json.dumps(r))
        ok("同じ日の分は1件にまとまる", r["vevents"] == r["events"], json.dumps(r))
        ok("遠すぎる予定は入れない（2週間まで）", r["events"] <= 3, json.dumps(r))
        ok("通知（VALARM）が付く", r["hasAlarm"] is True, json.dumps(r))
        ok("書き出した時刻を残す（週1回の書き出しを促すため）",
           r["stamped"] is True, json.dumps(r))

        # ---------- 間違いノート ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, H = window.Half2Impl;
          const atoms = await S.getAllAtoms();
          const p = {}; p[atoms[10].atom_id] = { last_eval: 'hard' };
          await S.updateAtomsBulk(p);
          const qs = await S.getAllQuestions();
          await S.toggleQuestionStar(qs[1].q_id);
          const both = await H.collectNoteItems('both');
          const star = await H.collectNoteItems('star');
          const hard = await H.collectNoteItems('hard');
          const built = await H.buildPrintSheet({ kind:'both', paper:'A5', cols:'2', explain:'all' });
          const sheet = document.getElementById('print-sheet');
          const style = document.getElementById('print-page-style');
          return { both: both.length, star: star.length, hard: hard.length,
                   built: built.count,
                   items: sheet.querySelectorAll('.pn-item').length,
                   cols: sheet.getAttribute('data-cols'),
                   page: style ? style.textContent : '',
                   visible: getComputedStyle(sheet).display };
        }""")
        ok("★と「難しい」を集められる", r["both"] > 0, json.dumps(r))
        ok("★だけ・難だけでも絞れる", r["star"] > 0 and r["hard"] > 0, json.dumps(r))
        ok("選んだ用紙が @page に反映される", "A5" in r["page"], json.dumps(r["page"]))
        ok("段組みの指定が反映される", r["cols"] == "2", json.dumps(r))
        ok("組んだ問題数と紙面の件数が一致する", r["built"] == r["items"], json.dumps(r))
        ok("画面には出さない（印刷のときだけ）", r["visible"] == "none", json.dumps(r))

        ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
        br.close()


runtime_checks()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAG" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
