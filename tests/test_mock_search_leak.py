# -*- coding: utf-8 -*-
"""test_mock_search_leak.py — 模試待ちを検索と概念タグの肢数からも引く（V3.20）

【何が起きていたか（2026-09-15・V3.19 の直後に同じ形で2件見つかった）】
  DESIGN_DECISIONS 7-0 は「模試待ち（pool mock・まだ模試で出会っていない問題）は
  **模試以外のどこにも出ない**」と決めている。V3.19 でツリーの未学習バッジを直したあと、
  「全アトムを数えている場所」を洗い直したら、さらに2か所が漏れていた。

  ① キーワード検索（storage.searchAll）
     実測：「看護」で64件中43件、「の」で90件全部が模試待ちだった。
     問題文と抜粋が見え、［この結果を今すぐ解く］でそのまま解けた。
     無料版では体験用90問がプチ模試30＋ハーフ模試60の中身そのものなので、
     **検索で先に解けると模試が成立しない**（中身が全部既視になる）。

  ② 103概念タグの肢数（storage.refreshConceptCatalog の atom_count）
     実測：103行中57行が模試待ちを含み、**29タグは中身が模試待ちだけ**。
     アナライザーに「#がん化学療法・放射線看護 4肢」と出るのに、
     押して始まる概念ノックは0問（ノック側は正しく除いていた）。
     V3.19 で直した「押しても減らない未学習バッジ」と同じ形の催促。

【直し方】
  どちらも「pool が mock で、まだ1肢も答えていない問題」を数えない・返さない。
  規則は scheduler.splitMockPool と同じ（問題単位・1肢でも答えていれば普通の問題）。
  模試で出会った問題は、以後は検索にも出るし肢数にも入る。

【ここで固定すること】
  ・検索が模試待ちを1件も返さない（同梱の全問に当たる語で引いても本体249問ぶんだけ）
  ・模試で1肢に答えた問題は、その瞬間から検索に出る
  ・概念タグの肢数に模試待ちが入らない（中身が模試待ちだけのタグは0肢になる）
  ・肢数が0のタグは概念ノックでも0問（表示と中身が食い違わない）
  ・storage.js の2か所が splitMockPool と同じ2条件を持っている（片方だけ直したら落ちる）
"""
import os, sys, io, time
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = io.open(os.path.join(base, "storage.js"), encoding="utf-8").read()

# --- 静的：2か所とも同じ2条件で書かれているか ---
seg_s = st[st.index("function searchAll"):st.index("function searchAll") + 2600]
ok("searchAll が模試待ちを読み飛ばす", "mockLockedQ(q.q_id)" in seg_s)
ok("searchAll：pool==='mock' と answer_count > 0 の2条件",
   "=== 'mock'" in seg_s and "a.answer_count > 0" in seg_s)
ok("searchAll：片方だけ直さない、と書いてある", "splitMockPool" in seg_s)
seg_c = st[st.index("function refreshConceptCatalog"):st.index("function getConceptStats")]
ok("refreshConceptCatalog が模試待ちを数えない", "touchedQ[a.q_id]" in seg_c)
ok("概念カタログ：pool==='mock' と answer_count > 0 の2条件",
   "=== 'mock'" in seg_c and "a.answer_count > 0" in seg_c)
ok("概念カタログ：7-0 を引いている", "7-0" in seg_c)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")

PROBE = """async () => {
  const S = window.Storage, K = window.Scheduler;
  const qs = await S.getAllQuestions(), atoms = await S.getAllAtoms();
  const mockQ = {}; qs.forEach(q => { if (q.pool === 'mock') mockQ[q.q_id] = 1; });
  const touched = {}; atoms.forEach(a => { if (a.answer_count > 0) touched[a.q_id] = 1; });
  const locked = id => !!mockQ[id] && !touched[id];
  const out = { total: qs.length, mock: Object.keys(mockQ).length };

  /* 同梱の全問に当たる語で引く。「の」は339問すべてに出る */
  out.search = [];
  for (const w of ['の', '看護', '患者']) {
    const r = await S.searchAll(w);
    const ids = (r.hits || []).map(h => h.q_id);
    out.search.push({ word: w, hits: ids.length, mock_locked: ids.filter(locked).length });
  }

  /* 概念タグの肢数 */
  await S.refreshConceptCatalog();
  const rows = await S.getConceptStats();
  const tagMain = {};
  atoms.forEach(a => { if (!locked(a.q_id)) (a.tags || []).forEach(t => { tagMain[t] = (tagMain[t] || 0) + 1; }); });
  out.catalog = {
    rows: rows.length,
    mismatch: rows.filter(r => (r.atom_count || 0) !== (tagMain[r.tag] || 0)).length,
    /* 中身が模試待ちだけのタグは0肢になっているはず */
    zero_but_counted: rows.filter(r => (r.atom_count || 0) > 0 && !(tagMain[r.tag] > 0)).length
  };
  /* 0肢のタグは概念ノックでも0問（表示と中身が食い違わない） */
  const zero = rows.filter(r => (r.atom_count || 0) === 0);
  out.knock_zero = zero.length ? (await K.getKnockQueue(zero[0].tag, {}) || []).length : null;
  return out;
}"""

TOUCH = """async () => {
  const S = window.Storage;
  const qs = await S.getAllQuestions();
  const q = qs.find(x => x.pool === 'mock');
  const as = (await S.getAllAtoms()).filter(a => a.q_id === q.q_id);
  const patches = {}; patches[as[0].atom_id] = { answer_count: 1 };
  await S.updateAtomsBulk(patches);
  const r = await S.searchAll('の');
  return { q_id: q.q_id, found: (r.hits || []).some(h => h.q_id === q.q_id) };
}"""

def wait_init(pg, limit=60):
    t0 = time.time()
    while time.time() - t0 < limit:
        if pg.evaluate("() => window.__INIT_DONE === true"):
            return True
        pg.wait_for_timeout(200)
    return False

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    ok("同梱2本の取り込みが終わる（__INIT_DONE）", wait_init(pg))
    r = pg.evaluate(PROBE)
    ok("初回起動は 本体249＋体験用90＝339問", r["total"] == 339 and r["mock"] == 90, (r["total"], r["mock"]))
    hit_all = [x for x in r["search"] if x["word"] == "の"][0]
    ok("全問に当たる語で引いても模試待ちは0件", hit_all["mock_locked"] == 0, hit_all)
    ok("そのとき出るのは本体249問ぶんだけ", hit_all["hits"] == r["total"] - r["mock"], hit_all)
    ok("ほかの語でも模試待ちは出ない",
       all(x["mock_locked"] == 0 for x in r["search"]), r["search"])
    ok("概念タグの肢数が本体だけの数と一致する", r["catalog"]["mismatch"] == 0, r["catalog"])
    ok("中身が模試待ちだけのタグは0肢になる", r["catalog"]["zero_but_counted"] == 0, r["catalog"])
    ok("0肢のタグは概念ノックでも0問（表示と中身が合う）",
       r["knock_zero"] in (0, None), r["knock_zero"])

    t = pg.evaluate(TOUCH)
    ok("模試で1肢に答えた問題は、その瞬間から検索に出る", t["found"], t)
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  mock_search_leak" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
