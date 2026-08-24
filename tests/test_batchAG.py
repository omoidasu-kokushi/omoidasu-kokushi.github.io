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

        # ---------- 模試の3分類（V1.54：最後に見てからの距離） ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, K = window.Scheduler;
          const qs = await S.getAllQuestions();
          const day = 86400000, now = Date.now();
          /* fresh（昨日解いた）と faded（60日前に解いた）を作り分ける。
             V1.52 までは「中項目が学習済みか」で分けていたが、
             学習が進むと必ず消える分類だったので作り直した。 */
          const fresh = qs.slice(0, 30), faded = qs.slice(30, 70);
          const patches = {}, logs = [];
          const put = async (list, at, code) => {
            for (const q of list) {
              const ats = await S.getAtomsByQuestion(q.q_id);
              ats.forEach((a, i) => {
                patches[a.atom_id] = {
                  answer_count: 2, correct_count: 2, last_eval: 'normal',
                  interval_code: code, last_answered_at: at, _unlearned: 0 };
                logs.push({ atom_id: a.atom_id, answered_at: at + i,
                            eval: 'normal', is_correct: true,
                            schedule_updated: true, interval_code: code });
              });
            }
          };
          await put(fresh, now - day, '1d');
          await put(faded, now - 60 * day, '1d');
          await S.replaceAllLogs(logs);
          await S.updateAtomsBulk(patches);
          const F = new Set(fresh.map(q => q.q_id));
          const D = new Set(faded.map(q => q.q_id));
          const pick = async (mix) => {
            const q = await K.buildQueue({ mode:'exam', count:20, applyGuard:false,
                                           shuffle:true, mix });
            let f = 0, d = 0, u = 0;
            for (const x of q.questions) {
              if (F.has(x.q_id)) { f++; } else if (D.has(x.q_id)) { d++; } else { u++; }
            }
            return { total: q.questions.length, fresh: f, faded: d, unseen: u };
          };
          return {
            real:  await pick({ fresh:0.25, faded:0.45, unseen:0.30 }),
            final: await pick({ fresh:0.55, faded:0.45, unseen:0.00 }),
            allNew: await pick({ fresh:0, faded:0, unseen:1.00 })
          };
        }""")
        ok("本番モードは「最近解いた問題」を出しすぎない（測定を汚さない）",
           r["real"]["fresh"] <= r["real"]["total"] * 0.4, json.dumps(r["real"]))
        ok("直前モードのほうが「最近解いた問題」が多い",
           r["final"]["fresh"] >= r["real"]["fresh"], json.dumps(r))
        ok("直前モードは初見をぶつけない",
           r["final"]["unseen"] <= r["final"]["total"] * 0.2, json.dumps(r["final"]))
        ok("初見だけを指定すれば初見が中心になる",
           r["allNew"]["unseen"] >= r["allNew"]["total"] * 0.5, json.dumps(r["allNew"]))
        ok("どの比率でも問題数は減らない",
           r["real"]["total"] == 20 and r["final"]["total"] == 20, json.dumps(r))
        ok("本番モードには「文面を忘れた既習」が入る",
           r["real"]["faded"] > 0, json.dumps(r["real"]))

        # ---------- 分類が学習の進行で死なないこと（V1.54の主目的） ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, K = window.Scheduler;
          /* 全ての中項目に手を付けた状態を作る。V1.52 の novel（中項目が未学習）は
             ここで必ず0になり、分類として働かなくなっていた。 */
          const qs = await S.getAllQuestions();
          const byMed = {};
          qs.forEach(q => { (byMed[q.medium || ''] = byMed[q.medium || ''] || []).push(q); });
          const day = 86400000, now = Date.now();
          const patches = {}, logs = [];
          for (const m of Object.keys(byMed)) {
            const ats = await S.getAtomsByQuestion(byMed[m][0].q_id);
            ats.forEach((a, i) => {
              patches[a.atom_id] = { answer_count:2, correct_count:2, last_eval:'normal',
                interval_code:'1d', last_answered_at: now - 60 * day, _unlearned:0 };
              logs.push({ atom_id:a.atom_id, answered_at: now - 60 * day + i,
                          eval:'normal', is_correct:true,
                          schedule_updated:true, interval_code:'1d' });
            });
          }
          await S.replaceAllLogs(logs);
          await S.updateAtomsBulk(patches);
          const q = await K.buildQueue({ mode:'exam', count:20, applyGuard:false,
                    shuffle:true, mix:{ fresh:0.25, faded:0.45, unseen:0.30 } });
          return { mediums: Object.keys(byMed).length, total: q.questions.length };
        }""")
        ok("全ての中項目に手を付けても模試は成立する（V1.52の分類はここで死んだ）",
           r["total"] == 20, json.dumps(r))

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
        # V1.66：出典表記。紙で回覧されたとき、アプリへたどり着く経路になる。
        r2 = pg.evaluate("""() => {
          const c = document.querySelector('#print-sheet .pn-credit');
          return { has: !!c, text: c ? c.textContent : '',
                   last: c ? c === document.querySelector('#print-sheet').lastElementChild : false };
        }""")
        ok("紙面の末尾に出典表記が入る",
           r2["has"] and "オモイダス" in r2["text"] and "omoidasu-kokushi.github.io" in r2["text"],
           json.dumps(r2, ensure_ascii=False))
        ok("出典表記は最後の要素（問題より前に出ない）", r2["last"] is True, json.dumps(r2, ensure_ascii=False))
        ok("画面には出さない（印刷のときだけ）", r["visible"] == "none", json.dumps(r))

        ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
        br.close()


runtime_checks()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAG" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
