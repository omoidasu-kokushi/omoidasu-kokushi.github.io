# -*- coding: utf-8 -*-
"""test_free_mock_bundle.py — 体験用の予想問題90問を2本目の同梱データとして届ける（V2.99）

【何を作ったか】
  無料版の模試の球（pool mock・variant free_a 30問／free_b 60問）を questions_free_mock.js として同梱し、
  起動時に印 free_mock_imported が無ければ1度だけ取り込む。

【なぜ同梱シード（questions.js）に足さなかったか】
  同梱シードの更新は onlyExisting（V2.08）なので、配布物のシードに問題を足しても
  **既存の端末には新しい問題が届かない**（更新0問で静かに終わる）。
  別の印で入れれば、既存の端末にも次の起動で入る（V2.97 の「印で入れる」と同じ型）。
  購入済みの人にも入る：予想問題の一部として模試の球になる（印は無視される・V2.96）。

【ここで固定すること】
  ・データファイルが JSON として読め、90問・free_a 30／free_b 60・全部 pool mock・出典なし
  ・index.html が読み、sw.js の OPTIONAL に同じ ?v= で入っている（無くても本体は動く＝起動診断の必須には入れない）
  ・初回起動で 本体249＋体験用90 が入り、印と版が立つ
  ・既存の端末（本体だけ・印なし）も次の起動で90問が入り、理由をトーストで言う
  ・ランダムには混ざらない（模試待ち＝mock_locked）。模試の門は「球あり・1回目」になる
  ・全初期化のあとは両方とも戻らない（印を両方立てる）。設定の「入れ直す」で両方戻る
"""
import os, sys, io, json, re, time, subprocess
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fpath = os.path.join(base, "questions_free_mock.js")
p2 = io.open(os.path.join(base, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()
ih = io.open(os.path.join(base, "index.html"), encoding="utf-8").read()
sw = io.open(os.path.join(base, "sw.js"), encoding="utf-8").read()

# ---------------- 静的：データファイル ----------------
ok("questions_free_mock.js がある", os.path.exists(fpath))
info = {}
if os.path.exists(fpath):
    out = subprocess.run(["node", "-e",
        "const fs=require('fs');const window={};eval(fs.readFileSync(process.argv[1],'utf8'));"
        "const d=JSON.parse(window.FREE_MOCK_QUESTIONS_JSON);"
        "const qs=d.questions;const by={};qs.forEach(q=>{const k=(q.pool||'main')+':'+(q.variant||'-');by[k]=(by[k]||0)+1;});"
        "console.log(JSON.stringify({n:qs.length,by,src:qs.filter(q=>q.source).length,ver:window.FREE_MOCK_VERSION,"
        "units:[...new Set(qs.map(q=>q.unit))].length,atoms:qs.reduce((a,q)=>a+(q.atoms||[]).length,0)}))",
        fpath], capture_output=True, text=True)
    try: info = json.loads(out.stdout.strip().splitlines()[-1])
    except Exception: info = {"err": out.stderr[:200]}
ok("JSON として読める・90問", info.get("n") == 90, info)
ok("free_a 30／free_b 60・全部 pool mock", info.get("by") == {"mock:free_a": 30, "mock:free_b": 60}, info.get("by"))
ok("出典なし（AI予想問題）", info.get("src") == 0, info.get("src"))
ok("版がある", bool(info.get("ver")), info.get("ver"))
ok("12単元にまたがる", info.get("units") == 12, info.get("units"))

# ---------------- 静的：読み込みと印 ----------------
m_ih = re.search(r'src="\./questions_free_mock\.js\?v=([\d.]+)"', ih)
m_sw = re.search(r"'\./questions_free_mock\.js\?v=([\d.]+)'", sw)
ok("index.html が読む", bool(m_ih))
ok("sw.js の OPTIONAL に同じ ?v= で入っている（1文字違うとキャッシュに当たらない）",
   m_ih and m_sw and m_ih.group(1) == m_sw.group(1)
   and sw.index("questions_free_mock.js") > sw.index("const OPTIONAL_ASSETS"), (m_ih and m_ih.group(1), m_sw and m_sw.group(1)))
ok("起動診断の必須（REQUIRED）には入れない（無くても本体は動く）",
   "questions_free_mock" not in ih[ih.index("var REQUIRED"):ih.index("function isOk")])
ok("印で1度だけ入れる（importFreeMockIfNeeded）", "function importFreeMockIfNeeded" in p2 and "!meta.free_mock_imported" in p2)
ok("印は取り込みが終わってから立てる", "S.setMeta('free_mock_imported', true)" in p2)
ok("版が上がったら既存だけ上書き（onlyExisting）", "meta.free_mock_version !== FMV" in p2)
ok("全初期化で両方の印を立てる", "setMetaBulk({ seed_imported: true, free_mock_imported: true })" in p2)
ok("設定の「入れ直す」で体験用も入れ直す", "S.importText(global.FREE_MOCK_QUESTIONS_JSON)" in p2)
ok("なぜ別ファイルかが書いてある", "既存の端末に新しい問題が届かない" in p2)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
COUNTS = """async () => { const S = window.Storage; const qs = await S.getAllQuestions(); const m = await S.loadMeta();
  return { total: qs.length, main: qs.filter(q => (q.pool||'main') !== 'mock').length,
           mock: qs.filter(q => q.pool === 'mock').length,
           fa: await S.countQuestionsByVariant('free_a'), fb: await S.countQuestionsByVariant('free_b'),
           seed_imported: !!m.seed_imported, fm_imported: !!m.free_mock_imported, fm_version: m.free_mock_version || null,
           toast: (document.querySelector('#toast') && !document.querySelector('#toast').hidden)
                    ? document.querySelector('#toast-text').textContent : '' }; }"""

def wait_total(pg, want, limit=40):
    t0 = time.time()
    while time.time() - t0 < limit:
        c = pg.evaluate(COUNTS)
        if c["total"] >= want and c["fm_imported"]: return c
        pg.wait_for_timeout(200)
    return pg.evaluate(COUNTS)

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    ver = pg.evaluate("() => window.FREE_MOCK_VERSION || null")
    ok("ページに FREE_MOCK_VERSION が載る", ver == info.get("ver"), (ver, info.get("ver")))

    # --- ① 初回起動：本体249＋体験用90 ---
    c0 = wait_total(pg, 339)
    ok("初回起動で 本体249＋体験用90＝339問 が入る", c0["total"] == 339 and c0["main"] == 249 and c0["mock"] == 90, c0)
    ok("印つき free_a 30／free_b 60", c0["fa"] == 30 and c0["fb"] == 60, (c0["fa"], c0["fb"]))
    ok("両方の印と版が立つ", c0["seed_imported"] and c0["fm_imported"] and c0["fm_version"] == ver, c0)

    # ランダムには混ざらない・模試の門は「球あり・1回目」
    r = pg.evaluate("""async () => {
      const K = window.Scheduler, S = window.Storage, H = window.Half2Impl;
      const q = await K.buildQueue({ mode: 'random', count: 60, applyGuard: false });
      const mock = q.questions.filter(x => x.pool === 'mock').length;
      const gate = await H.freeExamGate('mock_30', await S.getUnlockState());
      return { n: q.questions.length, mock, gate: { variant: gate.variant, first: gate.first, blocked: gate.blocked } };
    }""")
    ok("ランダムには予想問題が混ざらない（模試待ち）", r["n"] > 0 and r["mock"] == 0, r)
    ok("無料版の模試の門は「球あり・1回目」", r["gate"] == {"variant": "free_a", "first": True, "blocked": False}, r["gate"])

    # --- ② 既存の端末（本体だけ・印なし）：次の起動で90問が入る ---
    pg.evaluate("""async () => { const S = window.Storage;
      await S.resetAll();
      await S.importText(window.SEED_QUESTIONS_TSV);
      await S.setMetaBulk({ seed_imported: true, seed_version: window.SEED_VERSION, onboarding_done: true }); }""")
    pre = pg.evaluate(COUNTS)
    ok("再現：本体249だけ・体験用の印なし（V2.98 以前の端末）", pre["total"] == 249 and not pre["fm_imported"], pre)
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    c1 = wait_total(pg, 339)
    ok("次の起動で90問が入る（既存の端末にも届く）", c1["total"] == 339 and c1["mock"] == 90 and c1["fm_imported"], c1)
    # トーストは数秒で消える。入った直後から数秒の間に見えていればよい
    t0 = time.time(); toast = ""
    while time.time() - t0 < 8:
        t = pg.evaluate("() => (document.querySelector('#toast') && !document.querySelector('#toast').hidden) ? document.querySelector('#toast-text').textContent : ''")
        if "体験用の予想問題" in (t or ""): toast = t; break
        pg.wait_for_timeout(200)
    ok("問題数が増えた理由をトーストで言う", "体験用の予想問題 90問を入れました" in toast, toast or c1["toast"])

    # 2回目の起動では入れ直さない（印あり・版一致）
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(2500)
    c2 = pg.evaluate(COUNTS)
    ok("2回目の起動では二重に入らない", c2["total"] == 339 and c2["mock"] == 90, c2)

    # --- ③ 全初期化：両方とも戻らない。設定の「入れ直す」で両方戻る ---
    pg.evaluate("() => { window.Main.closeModals(); }")
    r3 = pg.evaluate("""async () => { const H = window.Half2Impl, S = window.Storage;
      await H.doResetAll(); const m = await S.loadMeta();
      return { n: await S.countQuestions(), seed: !!m.seed_imported, fm: !!m.free_mock_imported }; }""")
    ok("全初期化で 0問・印は両方立つ", r3["n"] == 0 and r3["seed"] and r3["fm"], r3)
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(3000)
    ok("再読込しても見本も体験用も戻らない", pg.evaluate("async () => window.Storage.countQuestions()") == 0)
    pg.evaluate("() => { window.Main.closeModals(); window.Half2Impl.restoreSeedQuestions(); }")
    pg.wait_for_timeout(600)
    pg.click("#confirm-go")
    c4 = wait_total(pg, 339)
    ok("設定の「入れ直す」で 見本249＋体験用90 が戻る", c4["total"] == 339 and c4["main"] == 249 and c4["mock"] == 90, c4)

    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  free_mock_bundle" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
