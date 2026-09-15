# -*- coding: utf-8 -*-
"""test_tree_mock_badge.py — 模試待ち（pool mock）を未学習バッジに数えない（V3.19）

【何が起きていたか】
  DESIGN_DECISIONS 7-0（V1.56）は「全アトムを数える場所5つ（模試の解禁・レベル・分析・
  ツリーの未学習バッジ・プランナー）から模試待ちを引く。外し忘れた画面だけが永久に埋まらない」と
  決めていた。ところが **ツリーとランダム画面のバッジの元（storage.countBadgesByScope）だけ引いていなかった**。

  V2.99 で体験用の予想問題90問（pool mock）が全端末に同梱されてから、
  単元別学習のツリーに **消えない未学習 378肢（90問）** が出ていた。
  通し検証（tools/journey_all.py ⑦）で 2026-09-15 に発見：本体1,197問を解き切っても
  「未学習バッジの合計 1134（＝378肢 × 単元・大項目・中項目の3階層）」。
  模試待ちは単元別学習・ランダムには出ない（V1.56）ので、その催促は押しても減らない。

【直し方】
  countBadgesByScope で「pool が mock で、まだ1肢も答えていない問題」の肢を数えない。
  規則は scheduler.splitMockPool と同じ（問題単位・1肢でも答えていれば普通の問題）。
  模試で出会った（answer_count > 0 の肢がある）問題は、以後は普通に数える。

【ここで固定すること】
  ・初回起動（本体249＋体験用90）で、ツリーの未学習は本体249問ぶんだけ（各階層の合計が本体の未学習肢数と一致）
  ・体験用90問（pool mock）の肢は、単元・大項目・中項目のどの階層にも数えられていない
  ・模試待ちの1問に触れる（1肢だけ answer_count を立てる）と、その問題の**残りの肢**だけが未学習に数えられる
  ・storage.js と scheduler.js が同じ規則（pool==='mock' と answer_count>0 で問題単位）を持っている
    （片方だけ直したら落ちる）
  ・版番号・CACHE_NAME・?v= の3か所が**互いに**揃っている（版そのものは test_seed_hisshu が固定する）
"""
import os, sys, io, re, time
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = io.open(os.path.join(base, "storage.js"), encoding="utf-8").read()
sc = io.open(os.path.join(base, "scheduler.js"), encoding="utf-8").read()
sw = io.open(os.path.join(base, "sw.js"), encoding="utf-8").read()
ih = io.open(os.path.join(base, "index.html"), encoding="utf-8").read()

# --- 静的：規則が2か所で同じ形か ---
seg = st[st.index("function countBadgesByScope"):st.index("function headNo")]
ok("countBadgesByScope が模試待ちを読み飛ばす", "mockLocked(a)" in seg and "return;" in seg)
ok("規則は問題単位（q_id）で持つ", "mockQ[a.q_id]" in seg and "touchedQ[a.q_id]" in seg)
ok("storage 側：pool==='mock' で見る", "=== 'mock'" in seg)
ok("storage 側：1肢でも答えていれば普通の問題（answer_count > 0）", "a.answer_count > 0" in seg)
spl = sc[sc.index("function splitMockPool"):sc.index("function splitMockPool") + 900]
ok("scheduler.splitMockPool も同じ2条件（pool==='mock'／answer_count > 0）",
   "=== 'mock'" in spl and "answer_count > 0" in spl)
ok("片方だけ直さない、と両方に書いてある", "splitMockPool" in seg and "7-0" in seg)
# 版そのものは test_seed_hisshu.py が固定する。ここは「3か所が互いに揃っているか」だけを見る
# （literal を2つのファイルに書くと、毎回2か所直すことになり、片方を忘れる）
mv = re.search(r"CACHE_NAME = 'v([0-9.]+)'", sw)
ver = mv.group(1) if mv else ""            # 例 3.21.0
short = ".".join(ver.split(".")[:2])       # 例 3.21
ok("CACHE_NAME が読める", bool(mv), ver)
ok("?v= が CACHE_NAME と揃っている（index.html・sw.js とも1種類だけ）",
   bool(short) and set(re.findall(r"\?v=([0-9.]+)", ih)) == {short}
   and set(re.findall(r"\?v=([0-9.]+)", sw)) == {short},
   (short, sorted(set(re.findall(r"\?v=([0-9.]+)", ih))), sorted(set(re.findall(r"\?v=([0-9.]+)", sw)))))
ok("build-stamp も同じ版", bool(short) and ("_Omoidasu_V" + short) in ih, short)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")

SNAP = """async () => {
  const S = window.Storage;
  const atoms = await S.getAllAtoms();
  const qs = await S.getAllQuestions();
  const mockQ = {}; qs.forEach(q => { if (q.pool === 'mock') mockQ[q.q_id] = 1; });
  let mainUn = 0, mockUn = 0;
  atoms.forEach(a => { if (!(a.answer_count > 0)) { if (mockQ[a.q_id]) mockUn++; else mainUn++; } });
  const t = await S.buildTree();
  const arr = Array.isArray(t) ? t : (t.units || t.nodes || []);
  const sum = (ns, key) => (ns || []).reduce((s, n) => s + (n[key] || 0), 0);
  const units = arr.map(u => ({ unit: u.label || u.unit || u.name, unlearned: u.unlearned || 0,
                                 majors: sum(u.children || u.majors, 'unlearned'),
                                 mediums: (u.children || u.majors || []).reduce((s, m) => s + sum(m.children || m.mediums, 'unlearned'), 0) }));
  return { total: qs.length, mock: Object.keys(mockQ).length, mainUn, mockUn,
           unitSum: sum(units, 'unlearned'), majorSum: units.reduce((s, u) => s + u.majors, 0),
           mediumSum: units.reduce((s, u) => s + u.mediums, 0),
           nonHisshuUnits: units.filter(u => !/必修/.test(u.unit)).map(u => u.unit + ':' + u.unlearned) };
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
    s0 = pg.evaluate(SNAP)
    ok("初回起動は 本体249＋体験用90＝339問", s0["total"] == 339 and s0["mock"] == 90, (s0["total"], s0["mock"]))
    ok("体験用90問の肢（378）は全部まだ未学習", s0["mockUn"] > 300, s0["mockUn"])
    ok("ツリーの単元バッジの合計＝本体の未学習肢数（模試待ちを数えない）",
       s0["unitSum"] == s0["mainUn"], "%d vs 本体%d（模試待ち%d）" % (s0["unitSum"], s0["mainUn"], s0["mockUn"]))
    ok("大項目・中項目の合計も本体だけ", s0["majorSum"] == s0["mainUn"] and s0["mediumSum"] == s0["mainUn"],
       (s0["majorSum"], s0["mediumSum"]))
    # 無料版の初回は必修しか本体に無いので、必修以外の単元に未学習が出るとしたら模試待ちの分（＝出てはいけない）
    ok("必修以外の単元に未学習が出ない（体験用の予想問題は模試で初めて出会う）",
       all(x.endswith(':0') for x in s0["nonHisshuUnits"]), s0["nonHisshuUnits"][:4])

    # --- 模試待ちの1問に触れる：1肢だけ answer_count を立てる → その問題の残りの肢だけ数えられる ---
    r = pg.evaluate("""async () => {
      const S = window.Storage;
      const qs = await S.getAllQuestions();
      const q = qs.find(x => x.pool === 'mock');
      const atoms = (await S.getAllAtoms()).filter(a => a.q_id === q.q_id);
      const first = atoms[0];
      const patches = {}; patches[first.atom_id] = { answer_count: 1 };
      const n = await S.updateAtomsBulk(patches);   /* { atom_id: {項目: 値} } の形（storage.js） */
      return { q_id: q.q_id, n: atoms.length, unit: q.unit, written: n };
    }""")
    s1 = pg.evaluate(SNAP)
    ok("模試で出会った問題（1肢に答えた）は、残りの肢が普通に数えられる",
       s1["unitSum"] == s0["unitSum"] + (r["n"] - 1), "%d → %d（肢%d本・触れた1本を除く）" % (s0["unitSum"], s1["unitSum"], r["n"]))
    ok("他の模試待ち問題は数えられないまま", s1["mockUn"] == s0["mockUn"] - 1, (s0["mockUn"], s1["mockUn"]))
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  tree_mock_badge" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
