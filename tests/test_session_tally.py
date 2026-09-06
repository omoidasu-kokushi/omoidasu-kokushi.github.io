# -*- coding: utf-8 -*-
"""test_session_tally.py — V2.58 区切りに評価の内訳を出す

利用者の裁定：「区切りの実感だけもたせよう。評価の内訳で。」

正答率は出さない。このアプリが忘却スケジュールを動かしているのは
【難／普／易／マ】であって、選択の正誤ではない（§4-③）。
正答率を出すと「4択で当たった」を成果として数えることになり、
「当てられても根拠が言えないなら知らない」という前提と逆を教える。
そこがこのテストのいちばん大事な観点なので、文言そのものを固定する。

数えるのは【記録された評価】（plan.eval）。押した評価ではない。
期日前に間違えた肢は門番が「難」へ降ろすので（§V2.19）、
押した側を数えると画面の内訳と実際のスケジュールがずれる。
"""
import json, os, re, sys
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p1 = open(os.path.join(base, "20260815_main_part1_V1.38.js"), encoding="utf-8").read()
p2 = open(os.path.join(base, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()
cs = open(os.path.join(base, "styles.css"), encoding="utf-8").read()
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()
ix = open(os.path.join(base, "index.html"), encoding="utf-8").read()

ok("区切りのダイアログがある", 'id="modal-session-done"' in ix)
ok("内訳の器が3つある（区切り・復習・ノック）",
   'id="tally-session"' in ix and 'id="tally-review"' in ix and 'id="tally-knock"' in ix)
# コメントは「なぜ出さないか」を書いてあるので数えない。画面に出る文言だけを見る。
ix_visible = re.sub(r"<!--.*?-->", "", ix, flags=re.S)
ok("画面の文言に「正答率」を出していない（§4-③）",
   "正答率" not in ix_visible and "正解率" not in ix_visible)
ok("押した評価ではなく記録された評価を数える（plan.eval）",
   "one.plan && one.plan.eval" in p1)
ok("記録しないモード（単語検索）では数えない", "if (mode !== 'search') { bumpTally" in p1)
ok("内訳は state 直下に置く（endSession が session を畳んだあとに描くため）",
   "tally: null," in p1)
ok("ノックのまとめにも内訳を出す", "M.renderTally('#tally-knock')" in p2)
ok("CSSがある", ".tally-chip{" in cs and ".tally-note{" in cs)

TAG = "#内訳検証"
def q(i):
    return {"source": "内訳検証問%d" % i, "unit": "必修",
            "major": "1. 健康の定義と理解", "medium": "A. 健康の定義",
            "rank": "S", "question_type": "single", "select_count": 1, "pool": "main",
            "stem": "内訳検証の問題%d。正しいのはどれか。" % i,
            "atoms": [{"text": "誤り%d" % i, "statement": "誤り", "explanation": "誤り。",
                       "is_correct": False, "tags": [TAG]},
                      {"text": "正しい%d" % i, "statement": "正しい", "explanation": "正しい。",
                       "is_correct": True, "tags": [TAG]}]}
PAYLOAD = json.dumps({"questions": [q(i) for i in range(1, 4)]}, ensure_ascii=False)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.evaluate("""async (t) => {
      await window.Storage.setMeta('onboarding_done', true);
      await window.Storage.importText(t);
    }""", PAYLOAD)

    ids = pg.evaluate("""async () => {
      const qs = await window.Storage.getAllQuestions();
      return qs.filter(x => /^内訳検証問/.test(x.source || '')).map(x => x.q_id);
    }""")
    ok("検証用の3問が入った", len(ids) == 3, str(len(ids)))

    pg.evaluate("""async (ids) => {
      await window.Main.startSession({ mode: 'random', count: 3, shuffle: false, onlyIds: ids });
    }""", ids)
    pg.wait_for_timeout(1200)

    # 3問を「難しい」「普通」「易しい」で1問ずつ確定する
    EVAL_SEL = ["#eval-hard, .eval-btn.eval-hard",
                "#eval-normal, .eval-btn.eval-normal",
                "#eval-easy, .eval-btn.eval-easy"]
    for i in range(3):
        cards = pg.locator("#choice-list .choice-card")
        for k in range(cards.count()):
            try:
                cards.nth(k).click(timeout=5000)
            except Exception:
                continue
            if not pg.evaluate("() => { const b=document.querySelector('#btn-confirm'); return !b || b.disabled; }"):
                break
        try:
            pg.wait_for_selector("#btn-confirm:not([disabled])", timeout=6000)
            pg.click("#btn-confirm")
        except Exception:
            pass
        pg.wait_for_timeout(700)
        try:
            pg.locator(EVAL_SEL[i]).first.click(timeout=4000)
        except Exception:
            pass
        pg.wait_for_timeout(250)
        try:
            pg.click("#btn-next", timeout=5000)
        except Exception:
            pass
        pg.wait_for_timeout(900)

    r = pg.evaluate("""() => {
      const el = document.getElementById('tally-session');
      const m = document.getElementById('modal-session-done');
      const t = window.Main.state.tally;
      return { open: !!(m && !m.hidden), shown: !!(el && !el.hidden),
               html: el ? el.innerHTML : '',
               text: el ? (el.textContent || '').replace(/\s+/g, ' ').trim() : '',
               count: (document.getElementById('sess-count')||{}).textContent,
               tally: t };
    }""")
    ok("区切りのダイアログが出る", r["open"], json.dumps(r, ensure_ascii=False)[:300])
    ok("内訳が出る", r["shown"], json.dumps(r, ensure_ascii=False)[:300])
    ok("3問と出る", r["count"] == "3", str(r["count"]))
    t = r["tally"] or {}
    ok("問数を数えている", t.get("questions") == 3, json.dumps(t, ensure_ascii=False))
    ok("肢の数を数えている", t.get("atoms", 0) >= 3, json.dumps(t, ensure_ascii=False))
    ok("難しい・普通・易しいがそれぞれ1肢以上ある",
       t.get("hard", 0) >= 1 and t.get("normal", 0) >= 1 and t.get("easy", 0) >= 1,
       json.dumps(t, ensure_ascii=False))
    ok("押していない「マスター」はチップに出さない（0は並べない）",
       "マスター" not in r["text"], r["text"])
    ok("難しい肢は「20分ほどで戻ってきます」と伝える",
       ("20分" in r["text"]) if t.get("soon", 0) else True, r["text"])
    ok("正答率を出していない",
       "正答率" not in r["text"] and "%" not in r["text"], r["text"])

    # 空のセッションでは内訳を出さない（0だらけの箱を出さない）
    e = pg.evaluate("""() => {
      window.Main.state.tally = null;
      window.Main.renderTally('#tally-session');
      const el = document.getElementById('tally-session');
      return { hidden: !!el.hidden, html: el.innerHTML };
    }""")
    ok("1肢も評価していなければ内訳を出さない", e["hidden"] and e["html"] == "",
       json.dumps(e, ensure_ascii=False))

    z = pg.evaluate("""() => {
      window.Main.state.tally = { sid:'X', questions:2, atoms:4,
                                  hard:0, normal:4, easy:0, master:0, soon:0, skipped:2 };
      window.Main.renderTally('#tally-review');
      const el = document.getElementById('tally-review');
      return (el.textContent || '').replace(/\s+/g, ' ').trim();
    }""")
    ok("0の評価はチップを出さない", "難しい" not in z and "普通" in z, z)
    ok("まだ期日でない肢は「記録していません」と断る", "記録していません" in z, z)
    ok("JSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
    br.close()

def _vers(txt, pat):
    return sorted(set(re.findall(pat, txt)))
sw_cache = _vers(sw, r"CACHE_NAME = 'v([0-9.]+)'")
sw_q = _vers(sw, r"\?v=([0-9.]+)")
ix_q = _vers(ix, r"\?v=([0-9.]+)")
ix_stamp = _vers(ix, r"Omoidasu_V([0-9.]+)")
ok("index.htmlの?v=が1種類に揃っている", len(ix_q) == 1, str(ix_q))
ok("indexとswの?v=が一致している", ix_q == sw_q, str(ix_q) + " vs " + str(sw_q))
ok("build-stampの版が?v=と一致している",
   len(ix_stamp) == 1 and ix_stamp[0] == ix_q[0], str(ix_stamp))
ok("CACHE_NAMEが?v=と同じ系列", len(sw_cache) == 1 and sw_cache[0] == ix_q[0] + ".0", str(sw_cache))

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  session_tally" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
