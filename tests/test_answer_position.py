# -*- coding: utf-8 -*-
"""test_answer_position.py — AI予想問題の肢の並びを均す（正解が肢1に寄っていた）（V3.14）

【何が起きていたか（利用者の実測 2026-09-12）】
  利用者「ほとんど選択肢１を選んだけど45点/60点もとれてしまった。偏りがエグい」

  同梱データを数えた（1つ選べの問だけ）：
    同梱シード249問（過去問 pool main）  肢1 16.9% ／ 肢2 25.7% ／ 肢3 34.5% ／ 肢4 22.5%
    体験用 free_a 30問（AI作問 pool mock） **肢1 81.5%**
    体験用 free_b 60問（AI作問 pool mock） **肢1 94.4%**
  ハーフ模試（free_b・1つ選べが54問）で①だけ塗ると51問正解する。実測の45/60と合う。
  作問側に「正解をどこに置くか」を指示していなかったので、AIは素直に先頭へ置いた。

【ここで固定すること】
  ・取り込みのときに pool:'mock' の問だけ肢を並べ替え、original_num を振り直す
  ・**過去問（pool main）は並べ替えない**（出典「第111回 午前問1」の①は本物の①）
  ・**atom_id は動かさない**（記録と同期の鍵。動かすと学習記録が迷子になる）
  ・並びは q_id から決まる（乱数ではない）。同じデータを何度取り込んでも同じ並び
  ・解説の中の丸数字は書き換えない（実測：肢の解説に丸数字0件、全体解説の2問は箇条書きの印）
  ・取り込みレポートに「並べ替えました◯問」と、並べ替えたあとの正解位置の内訳を出す
  ・同梱の体験用90問は版を上げて（FREE_MOCK_VERSION 1.01）既存端末でも並びが直る
"""
import os, sys, io, json
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(n): return io.open(os.path.join(base, n), encoding="utf-8").read()
st, p2, fm = rd("storage.js"), rd("20260815_main_part2_V1.45.js"), rd("questions_free_mock.js")

ok("並べ替えは取り込みの1か所（書き込む前）", "function reorderMockAtoms" in st and "function seededOrder" in st
   and "reorderMockAtoms(payload, report);" in st
   and st.index("reorderMockAtoms(payload, report);") < st.index("var CHUNK = 200;"))
ok("並べ替えるのは pool mock だけ", "if (item.question.pool !== 'mock') { return; }" in st)
ok("atom_id は触らない（記録の鍵）", "atom_id" not in st[st.index("function reorderMockAtoms"):st.index("function countAnswerPositions")])
ok("並びは q_id から決まる（乱数ではない）", "seededOrder(item.question.q_id, atoms.length)" in st
   and "Math.random" not in st[st.index("function seededOrder"):st.index("function reorderMockAtoms")])
ok("解説の丸数字は書き換えない", "overall_explanation" not in st[st.index("function reorderMockAtoms"):st.index("function countAnswerPositions")])
ok("レポートに並べ替えた数と偏りを出す", "report.reordered" in st and "report.answer_pos" in st
   and "予想問題の選択肢を並べ替えました" in p2 and "正解の位置が偏っています" in p2)
ok("同梱の体験用は版を上げた（既存端末も直る）", 'const FREE_MOCK_VERSION = "1.01";' in fm)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_function("window.__INIT_DONE === true", timeout=60000)
    pg.wait_for_timeout(800)
    r = pg.evaluate("""async () => {
      const S = window.Storage;
      const out = {};
      const qs = await S.getAllQuestions();
      const atoms = await S.getAllAtoms();
      const byQ = {};
      atoms.forEach(a => { (byQ[a.q_id] = byQ[a.q_id] || []).push(a); });
      const dist = (pool) => {
        const pos = {}; let n = 0;
        qs.filter(q => (q.pool || 'main') === pool).forEach(q => {
          const list = (byQ[q.q_id] || []).slice().sort((a, b) => a.original_num - b.original_num);
          const cor = list.map((a, i) => a.is_correct ? i + 1 : 0).filter(Boolean);
          if (cor.length !== 1) { return; }
          n++; pos[cor[0]] = (pos[cor[0]] || 0) + 1;
        });
        let top = 0; Object.keys(pos).forEach(k => { if (pos[k] > top) top = pos[k]; });
        return { n, pos, maxPct: n ? Math.round(top * 100 / n) : 0 };
      };
      out.mock = dist('mock');
      out.main = dist('main');
      /* 予想問題：肢の番号は 1..n が1つずつ（抜けや重複が無い） */
      let numOk = true, idOk = true;
      qs.filter(q => q.pool === 'mock').forEach(q => {
        const list = (byQ[q.q_id] || []);
        const nums = list.map(a => a.original_num).sort((a, b) => a - b);
        if (nums.join(',') !== list.map((_, i) => i + 1).join(',')) { numOk = false; }
        /* atom_id は取り込み順のまま（_1.._n）で、番号とは独立 */
        list.forEach(a => { if (!/_\\d+$/.test(a.atom_id)) { idOk = false; } });
      });
      out.numsUnique = numOk; out.idShape = idOk;
      /* 過去問は元の並びのまま：同梱シードの1問目と突き合わせる */
      const seed = JSON.parse(window.SEED_QUESTIONS_TSV).questions[0];
      const q0 = qs.filter(q => (q.pool || 'main') === 'main' && q.source === seed.source)[0];
      if (q0) {
        const list = (byQ[q0.q_id] || []).slice().sort((a, b) => a.original_num - b.original_num);
        out.mainKept = list.map(a => a.text).join('|') === seed.atoms.map(a => a.text).join('|');
      }
      /* 決定的：同じデータをもう一度取り込んでも番号が変わらない */
      const before = {};
      (byQ[qs.filter(q => q.pool === 'mock')[0].q_id] || []).forEach(a => { before[a.atom_id] = a.original_num; });
      const qidMock = qs.filter(q => q.pool === 'mock')[0].q_id;
      /* 学習記録を1件書いてから取り込み直す（進捗が生き残るか） */
      const one = (byQ[qidMock] || [])[0];
      const patch = {}; patch[one.atom_id] = { answer_count: 3, last_eval: 'normal', srs_step: 2, interval_code: '1d', due_date: Date.now() + 86400000 };
      await S.updateAtomsBulk(patch);
      const rep = await S.importText(window.FREE_MOCK_QUESTIONS_JSON, { onlyExisting: true });
      out.report = { reordered: rep.reordered || 0, pos: rep.answer_pos || null, total: rep.answer_pos_total || 0, maxPct: rep.answer_pos_max_pct || 0 };
      const atoms2 = await S.getAllAtoms();
      const after = {}; let kept = null;
      atoms2.filter(a => a.q_id === qidMock).forEach(a => { after[a.atom_id] = a.original_num; if (a.atom_id === one.atom_id) { kept = a; } });
      out.stable = JSON.stringify(before) === JSON.stringify(after);
      out.progressKept = !!kept && kept.answer_count === 3 && kept.interval_code === '1d';
      return out; }""")
    m = r["mock"]
    ok("予想問題の正解の位置がばらける（どの肢も45%以下）", m["n"] >= 60 and m["maxPct"] <= 45,
       json.dumps(m, ensure_ascii=False))
    ok("肢1に寄っていない（もとは94%）", (m["pos"].get("1", 0) * 100 // max(1, m["n"])) <= 40,
       json.dumps(m["pos"], ensure_ascii=False))
    ok("肢の番号は1..nが1つずつ（抜けも重複も無い）", r["numsUnique"])
    ok("atom_id は取り込み順のまま（番号とは独立）", r["idShape"])
    ok("過去問は元の並びのまま（出典どおり）", r.get("mainKept") is True)
    ok("過去問の分布は触っていない（本試験の性質のまま）", r["main"]["n"] >= 200 and r["main"]["maxPct"] >= 30,
       json.dumps(r["main"], ensure_ascii=False))
    ok("取り込みレポートに並べ替えた数が出る", r["report"]["reordered"] >= 60, json.dumps(r["report"], ensure_ascii=False))
    ok("レポートの偏りは並べ替えたあとの数字", r["report"]["total"] >= 60 and r["report"]["maxPct"] <= 45,
       json.dumps(r["report"], ensure_ascii=False))
    ok("取り込み直しても並びが変わらない（決定的）", r["stable"])
    ok("並べ替えても学習記録は残る", r["progressKept"])
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  answer_position" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
