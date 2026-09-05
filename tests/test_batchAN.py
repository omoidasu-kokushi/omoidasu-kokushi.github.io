#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.61 検証：時計の狂い／壊れたデータ／不正な取り込みで壊れないこと"""
import json, os, sys, io, subprocess, glob
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))
def read(f): return io.open(os.path.join(APP, f), encoding="utf-8").read()

p = subprocess.run(["node", "--check", os.path.join(APP, "scheduler.js")],
                   capture_output=True, text=True)
ok("syntax scheduler.js", p.returncode == 0, p.stderr.strip()[:200])

sc = read("scheduler.js")
ok("期日に絶対上限がある", "MAX_HORIZON" in sc and "function capHorizon" in sc)
ok("壊れた期日を直す経路がある", "function repairFarDueDates" in sc)
ok("直した件数を黙って捨てない", "遠すぎる期日を" in sc)


def _external(t):
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t
            or "遠すぎる期日" in t)


DAY = 86400000


def runtime_checks():
    with sync_playwright() as p2:
        br = p2.chromium.launch(args=["--no-sandbox"])
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

        # ---------- 時計が進んでいたとき ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, K = window.Scheduler;
          const now = Date.now(), day = 86400000;
          const a = (await S.getAllAtoms())[7];
          const future = { atom_id:a.atom_id, answered_at: now + 400*day, eval:'easy',
            is_correct:true, schedule_updated:true, interval_code:'180d' };
          const only = K.rebuildAtomState(a, [future], { boundaryHour:4 });
          const real = { atom_id:a.atom_id, answered_at: now - 1000, eval:'hard',
            is_correct:false, schedule_updated:true, interval_code:'10m' };
          const both = K.rebuildAtomState(a, [future, real], { boundaryHour:4 });
          return {
            onlyDueDays: Math.round((only.due_date - now) / day),
            onlyEval: only.last_eval,
            bothDueMin: Math.round((both.due_date - now) / 60000),
            bothEval: both.last_eval,
            bothCount: both.answer_count,
            lastAtInFuture: both.last_answered_at > now
          };
        }""")
        ok("未来の記録があっても期日は梯子の範囲に収まる（永久に出てこない肢を作らない）",
           r["onlyDueDays"] <= 200, json.dumps(r))
        ok("時計を戻して解き直すと、そちらが最新として効く",
           r["bothEval"] == "hard" and r["bothDueMin"] <= 25, json.dumps(r))
        ok("未来の記録も解答回数には数える（解いた事実は消さない）",
           r["bothCount"] == 2, json.dumps(r))
        ok("未来の時刻をそのまま持たせない（分析や並べ替えが狂う）",
           r["lastAtInFuture"] is False, json.dumps(r))

        # ---------- すでに壊れている端末の自己修復 ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, K = window.Scheduler;
          const now = Date.now(), day = 86400000;
          const atoms = await S.getAllAtoms();
          const ids = atoms.slice(0, 3).map(a => a.atom_id);
          const patch = {};
          ids.forEach(id => { patch[id] = { due_date: now + 900*day,
            srs_step: 5, interval_code:'30d' }; });
          await S.updateAtomsBulk(patch);
          const okId = atoms[10].atom_id;
          const keep = { due_date: now + 20*day, srs_step: 4, interval_code:'1w' };
          await S.updateAtomsBulk({ [okId]: keep });
          const n = await K.repairFarDueDates(await S.getAllAtoms());
          const after = await S.getAtom(ids[0]);
          const untouched = await S.getAtom(okId);
          return { repaired: n,
                   afterDays: Math.round((after.due_date - now) / day),
                   step: after.srs_step,
                   untouchedDays: Math.round((untouched.due_date - now) / day) };
        }""")
        ok("遠すぎる期日を直す", r["repaired"] >= 3, json.dumps(r))
        ok("直した期日は梯子の範囲に入る", r["afterDays"] <= 200, json.dumps(r))
        ok("段は戻さない（積み上げた定着を失わせない）", r["step"] == 5, json.dumps(r))
        ok("普通の期日には触らない", r["untouchedDays"] == 20, json.dumps(r))

        # ---------- 壊れたレコードで落ちないこと ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, K = window.Scheduler;
          const out = {};
          const qs = await S.getAllQuestions();
          await S.updateQuestion(qs[0].q_id,
            { stem: null, rank: undefined, unit: undefined, medium: undefined });
          const atoms = await S.getAllAtoms();
          await S.updateAtom(atoms[0].atom_id, { q_id: 'NO_SUCH_QUESTION' });
          try { out.home = (await K.getHomeState()).total_questions; }
          catch (e) { out.homeErr = String(e).slice(0, 80); }
          try { out.queue = (await K.buildQueue({ mode:'random', count:20 })).questions.length; }
          catch (e) { out.queueErr = String(e).slice(0, 80); }
          try { out.dash = (await K.buildDashboard({ level:'medium' })).rows.length; }
          catch (e) { out.dashErr = String(e).slice(0, 80); }
          try { await K.refreshAll({ recomputeWeakness: true }); out.refresh = 'ok'; }
          catch (e) { out.refreshErr = String(e).slice(0, 80); }
          return out;
        }""")
        ok("必須項目が欠けた問題があってもホームが出る",
           "homeErr" not in r, json.dumps(r))
        ok("親のいない選択肢があっても出題できる",
           "queueErr" not in r and r["queue"] > 0, json.dumps(r))
        ok("分析も落ちない", "dashErr" not in r and r["dash"] > 0, json.dumps(r))
        ok("全体再集計も落ちない", r.get("refresh") == "ok", json.dumps(r))

        # ---------- 不正な行が混ざった取り込み ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage;
          const qs = [];
          for (let i = 0; i < 200; i++) {
            if (i % 4 === 0) { qs.push({ q_id:'BAD_'+i }); }
            else if (i % 4 === 1) { qs.push({ q_id:'BAD2_'+i, stem:'x', atoms:[] }); }
            else if (i % 4 === 2) { qs.push({ q_id:'BAD3_'+i, stem:'x',
              question_type:'multiple', select_count:2,
              atoms:[{text:'a',is_correct:true},{text:'b',is_correct:false}] }); }
            else { qs.push({ q_id:'OKQ_'+i, unit:'必修問題', major:'M', medium:'D',
              sub_item:'S', rank:'A', question_type:'single', select_count:1,
              stem:'問'+i, atoms:[{text:'a',is_correct:true},{text:'b',is_correct:false}] }); }
          }
          const rep = await S.importText(JSON.stringify(qs));
          return { ok: rep.ok, imported: rep.imported, skipped: rep.skipped,
                   mismatch: rep.mismatch, errors: (rep.errors||[]).length,
                   hasLine: (rep.errors||[]).every(e => typeof e.line === 'number') };
        }""")
        ok("正しい行だけが入る", r["imported"] == 50, json.dumps(r))
        ok("不正な行は落とす（黙って直さない）", r["skipped"] == 150, json.dumps(r))
        ok("「2つ選べ」なのに正解1つ、を検算で弾く", r["mismatch"] == 50, json.dumps(r))
        ok("どの行が落ちたか、行番号で分かる",
           r["hasLine"] is True and r["errors"] == 150, json.dumps(r))

        ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
        br.close()


runtime_checks()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAN" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
