# -*- coding: utf-8 -*-
"""test_free_units_gate.py — 無料版の門を「解いた数」から「単元」へ（V3.00・案B・利用者裁定 2026-09-11）

【何が矛盾していたか】
  V1.53 の門は FREE_LIMIT＝解いた問題200問で新規の出題を止めていた。無料版の設計（2026-09-08）は
  「過去問の必修は全部無料。必修を人質に取らない」。このままだと無料の利用者は必修249問を解き切れず、
  画面の文言（「200問を解き終えました」）が設計と食い違う。

【直したこと（案B）】
  鍵が無いとき、新しい問題として出すのは
    ・単元が FREE_UNITS（['必修']）の問題（出典を問わない）
    ・印つきの予想問題（pool mock かつ variant＝体験用の模試の球）
    ・一度でも触った問題（復習は止めない・V1.53 の原則）
  だけ。判定は scheduler.buildQueue の options.freeUnits。ライセンスを見て渡すのは main（§7-B）。
  FREE_LIMIT は門に使わない（定数だけ残す）。「あと◯問」「200問を解き終えました」は消えた。
  文言は「必修は全部使える」「他の単元と模試の続きは有料版」の2つ。

【ここで固定すること】
  ・鍵なし：必修の新規は全部出る／他の単元の新規は出ず、買い切りの案内が開く（門で止まったとき）
  ・鍵なし：一度触った問題は他の単元でも出る（復習を止めない）／印つきの予想問題は模試で出る
  ・鍵あり：門は無い
  ・復習（mode review）はそもそも門を通らない
  ・gate() は数で locked にしない。ホーム・設定・購入案内に「あと◯問」「200問」が出ない
  ・模試の従来の組み方（印の球が無い端末）にも門が効く
"""
import os, sys, io, json, time
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lic = io.open(os.path.join(base, "license.js"), encoding="utf-8").read()
sc  = io.open(os.path.join(base, "scheduler.js"), encoding="utf-8").read()
p1  = io.open(os.path.join(base, "20260815_main_part1_V1.38.js"), encoding="utf-8").read()
p2  = io.open(os.path.join(base, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()
ih  = io.open(os.path.join(base, "index.html"), encoding="utf-8").read()

ok("無料の範囲は単元で持つ（FREE_UNITS）", "var FREE_UNITS = ['必修'];" in lic)
ok("gate() は数で止めない（locked は常に false）", "locked: false,\n      used: used,\n      limit: null," in lic)
ok("FREE_LIMIT は門に使わない（撤廃・定数は残す）", "V3.00 からは門に使わない" in lic and "var FREE_LIMIT = 200;" in lic)
ok("scheduler に options.freeUnits", "options.freeUnits" in sc and "free_gated" in sc)
ok("一度触った問題は止めない", "if (c.unlearned < c.atoms.length) { return true; }" in sc)
ok("印つきの予想問題は止めない", "if (c.pool === 'mock' && c.variant) { return true; }" in sc)
ok("scheduler はライセンスを知らない", "NurseLicense" not in sc)
ok("渡すのは main（startSession）", "opts.freeUnits = global.NurseLicense.FREE_UNITS;" in p1)
ok("模試の組み方にも渡す（launchExam）", "opts.freeUnits = Lx.FREE_UNITS;" in p2 and "freeUnits: opts.freeUnits" in p2)
ok("ホームの1行は「必修は全部・他は有料版」", "過去問の必修は全部使えます" in p1 and "あと ' + g.left" not in p1)
ok("購入案内の見出しは範囲の言い方（V3.02：製品版）", "この範囲の新しい問題は製品版に入っています" in ih and "buy-units" in ih)
ok("購入案内で「復習は続く」を先に言う（V1.53 の原則を残す）", "復習は、シリアルが無くてもこのまま続けられます" in ih)
ok("「200問を解き終えました」は消えた", "200問を解き終えました" not in ih and "問を解き終えました" not in p1)
ok("設定のライセンス欄も数を出さない", "'無料版'" in p2 and "g.left + '問（'" not in p2)

# ---------------- 合成データ：必修以外の本体（過去問扱い）を入れる ----------------
TAX = {
  "成人看護学": ("12. 消化・吸収機能障害のある患者への看護", "C. 治療を受ける患者への看", "人工肛門造設術", "S", "#肝硬変・消化器慢性疾患"),
  "老年看護学": ("6. さまざまな健康状態や受療状況に応じた高齢者の看護", "I. 手術療法を受ける高齢者の看護", "高齢者に起こりやすい周手術期の反応と合併症", "S", "#周術期看護・麻酔管理"),
}
def make_q(unit, n):
    major, medium, sub, rank, tag = TAX[unit]
    label = "gate-" + str(n)
    return {"unit": unit, "major": major, "medium": medium, "sub_item": sub, "rank": rank,
            "source": "第115回 午後問" + str(200 + n), "pool": "main", "variant": None,
            "question_type": "single", "select_count": 1, "image_url": None, "numeric_answer": None,
            "stem": "門の検査用の問題 " + label + "（" + sub + "）で正しいのはどれか。",
            "overall_explanation": "門の検査用。", "comparison_table": None, "mermaid_code": None, "evidence": None,
            "is_splittable": False, "origin_key": None,
            "atoms": [
              {"original_num": 1, "is_correct": True,  "text": "正しい " + label, "statement": label + " は正しい。", "explanation": "正答。", "tags": [tag]},
              {"original_num": 2, "is_correct": False, "text": "誤り " + label + " 一", "statement": label + " 一は誤り。", "explanation": "誤り。", "tags": [tag]},
              {"original_num": 3, "is_correct": False, "text": "誤り " + label + " 二", "statement": label + " 二は誤り。", "explanation": "誤り。", "tags": [tag]},
              {"original_num": 4, "is_correct": False, "text": "誤り " + label + " 三", "statement": label + " 三は誤り。", "explanation": "誤り。", "tags": [tag]},
            ]}
qs = [make_q("成人看護学", i) for i in range(1, 9)] + [make_q("老年看護学", i) for i in range(9, 13)]
PAYLOAD = json.dumps({"questions": qs}, ensure_ascii=False)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
MODAL = "(sel) => { const m = document.querySelector(sel); return !!(m && !m.hidden); }"

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_function("window.__INIT_DONE === true", timeout=60000)
    pg.evaluate("""async () => { await window.Storage.setMetaBulk({ onboarding_done: true,
      tips_seen: ['unit_hero','qty','next','scan','level','settings_btn','theme','back','home_tip',
                  'qstar','tagpill','star','locked','memo','detail','summary',
                  'q_star','img_toggle','numeric_input','pomodoro','stem_expand','ground','exam'] }); }""")
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_function("window.__INIT_DONE === true", timeout=60000)
    pg.wait_for_timeout(600)
    pg.evaluate("() => { window.Main.closeModals(); }")

    # --- gate() ---
    g = pg.evaluate("() => { const L = window.NurseLicense; return { a: L.gate(0), b: L.gate(999), units: L.FREE_UNITS, hissu: L.unitIsFree('必修'), seijin: L.unitIsFree('成人看護学') }; }")
    ok("鍵なし：gate は数で locked にしない（0問でも999問でも）", g["a"]["locked"] is False and g["b"]["locked"] is False and g["b"]["used"] == 999, g)
    ok("無料の単元は必修だけ", g["units"] == ["必修"] and g["hissu"] is True and g["seijin"] is False, g)

    # --- 必修以外の本体を入れる ---
    rep = pg.evaluate("async (t) => window.Storage.importText(t)", PAYLOAD)
    ok("必修以外の本体12問が入る（成人8・老年4）", rep.get("imported") == 12 and rep.get("pool_main") == 12, {k: rep.get(k) for k in ("imported", "pool_main", "skipped")})
    pg.evaluate("async () => { await window.Scheduler.refreshAll({recomputeWeakness:true}); }")

    r = pg.evaluate("""async () => {
      const K = window.Scheduler;
      const units = qs => { const by = {}; qs.forEach(q => { by[q.unit] = (by[q.unit]||0) + 1; }); return by; };
      const all  = await K.buildQueue({ mode:'random', count:400, applyGuard:false, newOnly:true, shuffle:true, freeUnits:['必修'] });
      const sei  = await K.buildQueue({ mode:'random', count:20, applyGuard:false, newOnly:true, shuffle:true,
                                        scope:{ field:'unit', value:'成人看護学' }, freeUnits:['必修'] });
      const seiPaid = await K.buildQueue({ mode:'random', count:20, applyGuard:false, newOnly:true, shuffle:true,
                                           scope:{ field:'unit', value:'成人看護学' } });
      const none = await K.buildQueue({ mode:'random', count:20, applyGuard:false, newOnly:true, shuffle:true,
                                        scope:{ field:'unit', value:'存在しない単元' }, freeUnits:['必修'] });
      return { allUnits: units(all.questions), allN: all.questions.length,
               sei: { n: sei.questions.length, locked: !!sei.locked, gated: !!sei.free_gated, reason: sei.reason || null },
               seiPaid: seiPaid.questions.length,
               none: { n: none.questions.length, locked: !!none.locked, gated: !!none.free_gated } };
    }""")
    ok("鍵なし：新規に出るのは必修だけ（249問すべて）", r["allUnits"] == {"必修": 249}, r["allUnits"])
    ok("鍵なし：成人看護学の新規は出ない。門で止まったと分かる（locked・free_gated）",
       r["sei"]["n"] == 0 and r["sei"]["locked"] and r["sei"]["gated"] and "製品版" in (r["sei"]["reason"] or ""), r["sei"])
    ok("鍵あり（freeUnits を渡さない）：成人看護学の新規が出る", r["seiPaid"] == 8, r["seiPaid"])
    ok("もとから問題が無い範囲は「門で止まった」にしない（案内を取り違えない）",
       r["none"]["n"] == 0 and not r["none"]["locked"] and not r["none"]["gated"], r["none"])

    # --- 画面の道：ランダムで成人看護学を選ぶ → 買い切りの案内 ---
    s1 = pg.evaluate("""async () => { const M = window.Main;
      const sess = await M.startSession({ mode:'random', count:10, newOnly:true, shuffle:true, scope:{ field:'unit', value:'成人看護学' } });
      return { started: !!sess, buy: !document.querySelector('#modal-buy').hidden,
               title: document.querySelector('#modal-buy .modal-title').textContent,
               body: document.querySelector('#modal-buy .modal-body').textContent }; }""")
    ok("鍵なし：成人看護学を選ぶと始まらず、買い切りの案内が開く", not s1["started"] and s1["buy"], s1["title"])
    ok("案内の見出しは範囲の言い方（200問ではない）", "製品版に入っています" in s1["title"] and "200問" not in s1["body"], s1["title"])
    ok("案内に「必修は全部」「復習は続く」がある", "必修（全部）" in s1["body"] and "復習は、シリアルが無くてもこのまま続けられます" in s1["body"], s1["body"][:160])
    pg.evaluate("() => { window.Main.closeModals(); }")

    s2 = pg.evaluate("""async () => { const M = window.Main;
      const sess = await M.startSession({ mode:'random', count:5, newOnly:true, shuffle:true, scope:{ field:'unit', value:'必修' } });
      const out = { started: !!sess, units: sess ? [...new Set(sess.questions.map(q => q.unit))] : [] };
      M.endSession(); M.closeModals(); M.go('home'); return out; }""")
    ok("鍵なし：必修は普通に始まる", s2["started"] and s2["units"] == ["必修"], s2)

    # --- 一度触った問題は他の単元でも出る（復習を止めない） ---
    s3 = pg.evaluate("""async () => { const S = window.Storage, K = window.Scheduler;
      const qs = (await S.getAllQuestions()).filter(q => q.unit === '老年看護学');
      const ats = await S.getAtomsByQuestion(qs[0].q_id);
      /* 「触った」は台帳（ログ）から導かれる（buildQueue は weakMap の unlearned を見る）。
         肢の answer_count だけ書いても触ったことにならないので、記録を1件積む。 */
      const now = Date.now();
      await S.appendLogs([{ atom_id: ats[0].atom_id, q_id: qs[0].q_id, eval: 'hard', is_correct: false,
                            answered_at: now - 60000, schedule_updated: true, interval_code: '20m', think_ms: 3000 }]);
      await S.updateAtom(ats[0].atom_id, { answer_count: 1, last_eval: 'hard', last_answered_at: now - 60000 });
      await K.refreshAll({ recomputeWeakness: true });
      const q = await K.buildQueue({ mode:'random', count:20, applyGuard:false, shuffle:true,
                                    scope:{ field:'unit', value:'老年看護学' }, freeUnits:['必修'] });
      return { n: q.questions.length, ids: q.questions.map(x => x.q_id), touched: qs[0].q_id }; }""")
    ok("鍵なし：一度触った問題（1肢だけでも）は他の単元でも出る", s3["n"] == 1 and s3["ids"] == [s3["touched"]], s3)

    # --- 復習は門を通らない ---
    s4 = pg.evaluate("""async () => { const S = window.Storage, K = window.Scheduler;
      const qs = (await S.getAllQuestions()).filter(q => q.unit === '成人看護学');
      const ats = await S.getAtomsByQuestion(qs[0].q_id);
      const now = Date.now();
      for (const a of ats) { await S.updateAtom(a.atom_id, { answer_count:1, last_eval:'normal', last_answered_at: now - 86400000, due_date: now - 1000, interval_code:'1d', _unlearned:0 }); }
      const rev = await K.buildQueue({ mode:'review', count:50 });
      return { inRev: rev.questions.filter(q => q.q_id === qs[0].q_id).length }; }""")
    ok("復習は門を通らない（成人看護学の期日の問題が復習に出る）", s4["inRev"] == 1, s4)

    # --- 模試の従来の組み方（印の球が無い端末）にも門が効く ---
    s5 = pg.evaluate("""async () => { const S = window.Storage, K = window.Scheduler, H = window.Half2Impl, M = window.Main;
      /* 体験用の球を外して、従来の組み方に落ちる端末を作る（印は立てたまま） */
      const mock = (await S.getAllQuestions()).filter(q => q.pool === 'mock').map(q => q.q_id);
      await S.deleteQuestions ? S.deleteQuestions(mock) : null;
      const left = await S.countQuestionsByVariant('free_a');
      return { left, hasDelete: typeof S.deleteQuestions === 'function' }; }""")
    if s5["hasDelete"] and s5["left"] == 0:
        s6 = pg.evaluate("""async () => { const H = window.Half2Impl, M = window.Main;
          await H.launchExam('mock_30', 30, 'real'); await new Promise(r => setTimeout(r, 300));
          const ex = H.state.exam; const units = [...new Set(ex.questions.map(q => q.unit))];
          if (typeof M.hooks.onAbort === 'function') { M.hooks.onAbort('exam'); } M.endSession(); M.closeModals(); M.go('home');
          return { n: ex.questions.length, units }; }""")
        ok("球が無い端末の模試：鍵なしは必修（＋触った問題）だけで組む", s6["n"] == 30 and all(u == "必修" or u in ("成人看護学", "老年看護学") for u in s6["units"]), s6)
    else:
        # 削除の API が無ければ、buildQueue に直接 freeUnits を渡して同じことを見る
        s6 = pg.evaluate("""async () => { const K = window.Scheduler;
          const q = await K.buildQueue({ mode:'exam', count:30, applyGuard:false, shuffle:true, includeMock:false, freeUnits:['必修'],
                                        mix:{ fresh:0.1, faded:0.45, unseen:0.45 } });
          return { n: q.questions.length, units: [...new Set(q.questions.map(x => x.unit))] }; }""")
        ok("模試の従来の組み方に freeUnits を渡すと、必修（＋触った問題）だけで組む",
           s6["n"] == 30 and all(u == "必修" or u in ("成人看護学", "老年看護学") for u in s6["units"]), s6)

    # --- 画面の文言 ---
    txt = pg.evaluate("""() => { window.Main.refreshFreeGate(); return { home: document.querySelector('#free-gate-text').textContent,
      hidden: document.querySelector('#free-gate').hidden, tone: document.querySelector('#free-gate').getAttribute('data-tone') }; }""")
    ok("ホームの1行：必修は全部・他は有料版（数は出さない・警告色にしない）",
       not txt["hidden"] and "必修は全部使えます" in txt["home"] and "あと" not in txt["home"] and txt["tone"] == "ok", txt)
    pg.evaluate("() => { window.Half2Impl.refreshLicense(); }")
    lic_txt = pg.evaluate("() => ({ state: document.querySelector('#lic-state').textContent, note: document.querySelector('#lic-note').textContent, bar: document.querySelector('#lic-bar').hidden })")
    ok("設定：無料版・必修は全部・進み具合の帯は出さない", lic_txt["state"] == "無料版" and "必修は全部" in lic_txt["note"] and lic_txt["bar"] is True, lic_txt)

    # --- 鍵あり（本物の鍵で登録する。gate() は内部の isPaid を見るので、export の差し替えでは効かない） ---
    GOOD = ("OMOI1.eyJuIjoiQk9PVEgtVEVTVCIsInQiOjE3NTYwMDAwMDAwMDB9."
            "-2H0zVWaIJ_x2TS5kzEUDkxLSn0TJ23d7-rDjp1gmkc0cRZ7iWREfqGc69hU5D29FFNGwjjaFN7Q_mDQxQnhOQ")
    act = pg.evaluate("async (k) => { const r = await window.NurseLicense.activate(k); await window.Main.refreshHome(); return r.ok; }", GOOD)
    ok("下ごしらえ：本物の鍵が通る", act is True, act)
    s7 = pg.evaluate("""async () => { const M = window.Main;
      const sess = await M.startSession({ mode:'random', count:5, newOnly:true, shuffle:true, scope:{ field:'unit', value:'成人看護学' } });
      const out = { started: !!sess, n: sess ? sess.questions.length : 0, buy: !document.querySelector('#modal-buy').hidden,
                    gateHidden: document.querySelector('#free-gate').hidden };
      M.endSession(); M.closeModals(); M.go('home'); return out; }""")
    pg.evaluate("async () => { await window.NurseLicense.deactivate(); }")
    ok("鍵あり：ホームの無料版の1行は消える", s7["gateHidden"] is True, s7)
    ok("鍵あり：成人看護学の新規が普通に始まる（門は無い）", s7["started"] and s7["n"] == 5 and not s7["buy"], s7)

    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  free_units_gate" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
