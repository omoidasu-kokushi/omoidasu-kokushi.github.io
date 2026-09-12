# -*- coding: utf-8 -*-
"""test_level5_weak_mock.py — Level 5 ＝ いじわる模試の合格（王冠）（V3.07）

【何が起きていたか（§23-⑥・利用者裁定 2026-09-12）】
  ・Level 5 は「全アトムのマスター化（👑 ALL MASTERED）」。マスターは30日以上のステップでしか押せず、
    400日＋模試2回の通し検証で 15%。実質「模試を何度も受けた人」だけの到達点だった。
    V3.05 で模試の昇格（正解＋根拠ON→易／マ）も無くなり、さらに遠のいた。
  ・利用者「いじわる模試合格で王冠とかでいいかも。模試で苦手なのばっか出されて合格点出たら十分でしょ」

【ここで固定すること】
  ・Level 5 の達成＝meta.weak_mock_passed（いじわる模試に合格した印・永久）
  ・進み具合：解禁の進み（unlock_pct_mock_weak）の半分 → 解禁で50 → 受けて不合格で75 → 合格で100
  ・いじわる模試を採点すると印が立つ（受験＝weak_mock_taken／合格＝weak_mock_passed）
  ・王冠のバッジは合格で出る。全マスター（all_mastered）は情報として残るが Level の条件ではない
  ・ホームの2行目は段階で言う（達成（いじわる模試に合格）等）
  ・同期は片方で true なら true（META_OR_KEYS）
"""
import os, sys, io, json
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(n): return io.open(os.path.join(base, n), encoding="utf-8").read()
sc, st, dr, p1, p2 = rd("scheduler.js"), rd("storage.js"), rd("drive.js"), rd("20260815_main_part1_V1.38.js"), rd("20260815_main_part2_V1.45.js")

ok("Level 5 の名前と条件がいじわる模試の合格", "name: 'いじわる模試 合格・殿堂入り'" in sc and "var l5Done = weak.done;" in sc and "function weakMockLevel" in sc)
ok("進み具合は 半分→50→75→100", "pct: 100, done: true, stage: 'passed'" in sc and "pct: 75,  done: false, stage: 'taken'" in sc
   and "pct: 50,  done: false, stage: 'unlocked'" in sc and "clamp(up, 0, 100) / 2" in sc)
ok("いじわる模試の採点で印が立つ", "function recordWeakMockResult" in st and "S.recordWeakMockResult(passed)" in p2)
ok("同期は片方で true なら true", "'weak_mock_taken', 'weak_mock_passed'" in dr)
ok("王冠のバッジは合格で。全マスターは別の印として残す", "badge: raw.weak_mock_passed ? '👑 いじわる模試 合格'" in sc and "all_mastered: allMastered" in sc)
ok("ホームの2行目は段階で言う", "function levelFiveNote" in p1 and "達成（いじわる模試に合格）" in p1)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_function("window.__INIT_DONE === true", timeout=60000)
    pg.wait_for_timeout(600)
    pg.evaluate("() => { const b = document.getElementById('welcome-start'); if (b) b.click(); }")
    pg.wait_for_timeout(400)
    r = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler, M = window.Main;
      const out = {};
      const raw0 = await K.computeLevelRaw();
      out.stage0 = raw0.stats.weak_mock_stage; out.pct0 = raw0.pct_by_level[5]; out.done0 = raw0.done_by_level[5];
      /* 解禁の進みが半分になる */
      await S.setMetaBulk({ unlock_pct_mock_weak: 60 });
      const raw1 = await K.computeLevelRaw();
      out.pctLocked = raw1.pct_by_level[5];
      /* 解禁 → 50 */
      await S.setMetaBulk({ unlock_mock_weak: true });
      const raw2 = await K.computeLevelRaw();
      out.pctUnlocked = raw2.pct_by_level[5]; out.stage2 = raw2.stats.weak_mock_stage;
      /* 受けて不合格 → 75（印は採点の関数で立つ） */
      await S.recordWeakMockResult(false);
      const raw3 = await K.computeLevelRaw();
      out.pctTaken = raw3.pct_by_level[5]; out.takenFlag = (await S.getMeta('weak_mock_taken', false)) === true;
      out.notPassedYet = !(await S.getMeta('weak_mock_passed', false)) && raw3.done_by_level[5] === false;
      /* 全マスターでも Level 5 ではない（他レベルが未達なので level は 1 のまま。5 の done だけ見る） */
      const atoms = await S.getAllAtoms(); const patch = {};
      atoms.forEach(a => { if (a.pool !== 'mock') patch[a.atom_id] = { answer_count: 3, last_eval: 'master', srs_step: 7, interval_code: '180d', due_date: Date.now() + 86400000 * 100 }; });
      await S.updateAtomsBulk(patch);
      const raw4 = await K.computeLevelRaw();
      out.allMasteredNotLevel5 = raw4.all_mastered === true && raw4.done_by_level[5] === false && raw4.pct_by_level[5] === 75;
      /* 合格 → 100・王冠 */
      await S.recordWeakMockResult(true);
      const lv = await K.computeLevel();
      out.passed = lv.done_by_level[5] === true && lv.pct_by_level[5] === 100 && /いじわる模試 合格/.test(lv.badge || '');
      out.levelName = lv.level_name;
      /* ホームの2行目 */
      await M.refreshHome();
      out.note = document.getElementById('level-note').textContent;
      return out; }""")
    ok("初期：未解禁 0%・未達成", r["stage0"] == "locked" and r["pct0"] == 0 and r["done0"] is False, r)
    ok("解禁の進み 60% → Level 5 は 30%", r["pctLocked"] == 30, r["pctLocked"])
    ok("解禁 → 50%", r["pctUnlocked"] == 50 and r["stage2"] == "unlocked")
    ok("受けて不合格 → 75%・印 weak_mock_taken・未達成", r["pctTaken"] == 75 and r["takenFlag"] and r["notPassedYet"])
    ok("全マスターでも Level 5 の達成ではない（情報として残るだけ）", r["allMasteredNotLevel5"])
    ok("合格 → 100%・達成・王冠のバッジ", r["passed"], r["levelName"])
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  level5_weak_mock" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
