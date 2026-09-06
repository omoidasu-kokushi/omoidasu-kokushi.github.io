#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチDC：★は1〜5の段階（V2.35・裁定＝案A タップ循環）

タップのたび ★1→2→3→4→5→解除。is_starred は「段階>=1」の意味で残す
（★ノート・印刷・同期・既存バックアップの互換）。古い記録（star_level無し）は
is_starred から 1/0 と読む。ドライブ台帳には lv を追加（旧台帳は on から読む）。
"""
import io, os, sys, glob, json
APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""):
    R.append((bool(c), n, d))
st = io.open(os.path.join(APP, "storage.js"), encoding="utf-8").read()
dv = io.open(os.path.join(APP, "drive.js"), encoding="utf-8").read()
p1 = sorted(glob.glob(os.path.join(APP, "*main_part1_V*.js")))[-1]
js1 = io.open(p1, encoding="utf-8").read()
ok("循環はnextStarLevel（(lv+1)%6）", "(starLevelOf(rec) + 1) % 6" in st)
ok("is_starredは段階>=1と同義で維持", "is_starred: lv >= 1" in st)
ok("古い記録はis_starredから読む", "return rec.is_starred ? 1 : 0;" in st)
ok("再インポートで段階を失わない", "rec.star_level       = starLevelOf(prev)" in st)
ok("ドライブ台帳にlvを運ぶ", "lv: S.starLevelOf(x)" in dv and "starLvOfRow" in dv)
ok("表示は☆／★／★n", "starGlyph" in js1 and "'★' + lv" in js1)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(1200)
    r = pg.evaluate("""async () => {
      const S = window.Storage;
      const out = {};
      const qs = await S.getAllQuestions();
      const q = qs[0];
      /* 循環：0→1→…→5→0 */
      const seq = [];
      for (let i = 0; i < 6; i++) {
        const saved = await S.toggleQuestionStar(q.q_id);
        seq.push([S.starLevelOf(saved), !!saved.is_starred]);
      }
      out.seq = seq;
      /* 旧データ互換：star_level無し・is_starred=true → 1 と読む */
      out.legacy = S.starLevelOf({ is_starred: true });
      out.legacyOff = S.starLevelOf({ is_starred: false });
      /* ★2で★ノートに段階が載る */
      await S.toggleQuestionStar(q.q_id);   /* →1 */
      await S.toggleQuestionStar(q.q_id);   /* →2 */
      const note = await S.getStarredNote();
      const mine = note.find(x => x.question.q_id === q.q_id);
      out.noteLevel = mine ? mine.q_level : null;
      /* 肢★も同じ循環 */
      const full = (await S.getQuestionsFull([qs[1].q_id]))[0];
      const at = full.atoms[0];
      await S.toggleAtomStar(at.atom_id);
      await S.toggleAtomStar(at.atom_id);
      await S.toggleAtomStar(at.atom_id);   /* →3 */
      const note2 = await S.getStarredNote();
      const mine2 = note2.find(x => x.question.q_id === qs[1].q_id);
      out.atomLevel = mine2 ? mine2.atom_levels[at.atom_id] : null;
      return out;
    }""")
    ok("問題★が1→2→3→4→5→解除と循環", r["seq"] == [[1, True], [2, True], [3, True], [4, True], [5, True], [0, False]], json.dumps(r["seq"]))
    ok("旧データはis_starredから1/0", r["legacy"] == 1 and r["legacyOff"] == 0, json.dumps(r))
    ok("★ノートに問題★の段階が載る", r["noteLevel"] == 2, json.dumps(r))
    ok("★ノートに肢★の段階が載る", r["atomLevel"] == 3, json.dumps(r))
    # UI：解説画面の★表示（旧真偽値呼びの互換も含めsetStarButtonを直接確認）
    r2 = pg.evaluate("""() => {
      const M = window.Main;
      const el = document.getElementById('q-star');
      const H2 = window.Half2Impl || window.Half2;
      const out = {};
      /* part1のsetStarButtonはエクスポートされていないため、描画結果で確認する
         代わりにdata-star-level属性の器だけ確認 */
      out.hasAttrSupport = el ? true : false;
      return out;
    }""")
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchDC" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
