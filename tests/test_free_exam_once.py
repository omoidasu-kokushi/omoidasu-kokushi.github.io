# -*- coding: utf-8 -*-
"""test_free_exam_once.py — 無料版の模試はプチ1回・ハーフ1回（V2.98・無料版の設計 §3・案B 裁定 2026-09-11）

【何を作ったか】
  鍵が無いとき、印（free_a／free_b）で組んだプチ模試・ハーフ模試は**それぞれ1回**。
  2回目を押すと、受けた結果を認めてから続きを示す案内（設計 §3-2）を出し、模試は始めない。

【決めごと（実装計画 §0 の裁定）】
  ・回数は exam_history から導く。数えるのは【同じ模試・同じ印】の記録だけ
      - 印の球が無い端末（いまの公開版）は従来どおり何度でも受けられる
      - 印無しの古い記録（過去問で組んだ模試）は数えない
      - 購入済み（鍵あり）は数えない
  ・「予想問題はこのほかに◯◯問」の数字は出さない（有料版の球がまだ無い。数字は事実だけ）
  ・［結果を見る］は履歴の1件を採点のときと同じ枡で見せる。「復習を始める」「画像でシェア」は隠す
    （問題と解答はもう手元に無い）
  ・受ける前の1行「この模試は1回ぶんです」を受け方のモーダルに出す（1回ぶんのときだけ）
  ・カウントダウン（「あと1回！」）は出さない。結果を見るのに購入を要求しない
  ・本文に「過去問の必修は、買わなくてもこのまま使えます」を必ず入れる

【ここで固定すること】
  ・球が無い → 止めない／印無しの記録があっても止めない
  ・球あり・1回目 → 受け方のモーダルに「1回ぶん」の1行が出る／受けると履歴に variant が残る
  ・球あり・2回目 → 模試を始めず案内。もう片方が未受験なら［◯◯を受ける］、両方受けたら「有料版に入っています」
  ・［結果を見る］で過去の結果が見える（復習・シェアのボタンは隠れる）。採点のときは戻る
  ・鍵あり → 何度でも受けられ、1行も出ない
"""
import os, sys, io, json, time
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p2 = io.open(os.path.join(base, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()
sj = io.open(os.path.join(base, "storage.js"), encoding="utf-8").read()
ih = io.open(os.path.join(base, "index.html"), encoding="utf-8").read()

# ---------------- 静的 ----------------
ok("回数の門 freeExamGate がある", "function freeExamGate" in p2)
ok("数えるのは同じ模試・同じ印の記録だけ", "x.variant === variant" in p2)
ok("球が無ければ従来どおり（止めない）", "if (n < size) { return none; }" in p2)
ok("履歴に variant を残す（storage）", "variant : (result.variant" in sj)
ok("採点の結果に variant を入れる（part2）", "variant: st.exam.variant || null" in p2)
ok("2回目の案内モーダルがある", 'id="modal-free-exam"' in ih and "function openFreeExamLimit" in p2)
ok("受ける前の1行がある", 'id="exam-style-once"' in ih and "この模試は<b>1回ぶん</b>です" in ih)
ok("必修は無料のままだと書く", "過去問の必修は、買わなくてもこのまま使えます" in p2)
ok("できないことを先に言わない（受けた結果を先に認める）", "問はもう解きました" in p2)
ok("数字は事実だけ（有料版の予想問題の数を書いていない）", "このほかに" not in p2)
ok("購入は BUY_URL 1箇所", "global.open(M.BUY_URL, '_blank', 'noopener')" in p2)
ok("過去の結果では復習とシェアを隠し、採点のときは戻す",
   "share.hidden = true" in p2 and "shareBtn.hidden = false" in p2)

# ---------------- 合成データ（test_free_exam_variant と同じ作り） ----------------
TAX = {
  "必修":                      ("13. 看護における基本技術", "C. フィジカルアセスメント", "意識レベルの評価", "S", "#バイタルサイン・生体計測"),
  "成人看護学":                ("12. 消化・吸収機能障害のある患者への看護", "C. 治療を受ける患者への看", "人工肛門造設術", "S", "#肝硬変・消化器慢性疾患"),
  "老年看護学":                ("6. さまざまな健康状態や受療状況に応じた高齢者の看護", "I. 手術療法を受ける高齢者の看護", "高齢者に起こりやすい周手術期の反応と合併症", "S", "#周術期看護・麻酔管理"),
  "小児看護学":                ("8. 慢性的な疾患・障害がある子どもと家族への看護", "A. 先天性疾患や慢性的な経過をとる疾患をもつ子どもと家族への看護", "発達に応じたセルフケア能力の獲得・自立支援", "S", "#小児の先天性・慢性疾患"),
  "基礎看護学":                ("5. 診療に伴う看護技術", "F. 生体機能のモニタリング", "経皮的動脈血酸素飽和度＜SpO2＞の測定、血糖測定", "S", "#バイタルサイン・生体計測"),
  "母性看護学":                ("4. 妊娠期の看護", "A. 正常な妊娠経過と妊娠期の異常", "常位胎盤早期剝離", "S", "#正常妊娠・胎児発育動態"),
  "疾病の成り立ちと回復の促進": ("6. 循環機能", "A. 心臓の疾患の病態と診断・治療", "虚血性心疾患（狭心症、急性冠症候群）", "A", "#急性冠症候群・心不全"),
  "精神看護学":                ("2. 主な精神疾患・障害の特徴と看護", "E. 神経症性障害、ストレス関連障害、身体表現性障害", "PTSD", "S", "#不安症・ストレス関連障害"),
  "在宅看護論／地域・在宅看護論": ("6. 症状・疾患・治療に応じた地域・在宅看護", "C. 主な治療等に応じた在宅", "酸素療法", "S", "#在宅療養支援・訪問看護"),
  "人体の構造と機能":          ("16. 生殖器系", "B. 男性の生殖器系の構造と機能", "精巣と精路", "B", "#生殖器・性分化"),
  "健康支援と社会保障制度":    ("4. 社会保険制度の基本", "C. 介護保険制度", "保険者、被保険者", "A", "#介護保険・高齢者支援"),
  "看護の統合と実践":          ("1. 看護におけるマネジメント", "E. 医療安全を維持する仕組みと対策", "医療事故・インシデントレポートの分析と活用", "A", "#医療安全・アクシデント防止"),
}
SHARE_A = {"必修": 6, "成人看護学": 4, "老年看護学": 3, "小児看護学": 2, "基礎看護学": 2, "母性看護学": 2,
           "疾病の成り立ちと回復の促進": 2, "精神看護学": 2, "在宅看護論／地域・在宅看護論": 2,
           "人体の構造と機能": 2, "健康支援と社会保障制度": 2, "看護の統合と実践": 1}
SHARE_B = {"必修": 14, "成人看護学": 8, "老年看護学": 5, "小児看護学": 5, "基礎看護学": 4, "母性看護学": 4,
           "疾病の成り立ちと回復の促進": 4, "精神看護学": 4, "在宅看護論／地域・在宅看護論": 3,
           "人体の構造と機能": 3, "健康支援と社会保障制度": 3, "看護の統合と実践": 3}

def make_q(unit, pool, variant, n):
    major, medium, sub, rank, tag = TAX[unit]
    label = (variant or pool) + "-" + str(n)
    return {
      "unit": unit, "major": major, "medium": medium, "sub_item": sub, "rank": rank,
      "source": None, "pool": pool, "variant": variant,
      "question_type": "single", "select_count": 1, "image_url": None, "numeric_answer": None,
      "stem": "検査用の問題 " + label + "（" + sub + "）で正しいのはどれか。",
      "overall_explanation": "検査用の全体解説 " + label + "。",
      "comparison_table": None, "mermaid_code": None, "evidence": None,
      "is_splittable": False, "origin_key": None,
      "atoms": [
        {"original_num": 1, "is_correct": True,  "text": "正しい記述 " + label, "statement": "検査用 " + label + " は正しい。", "explanation": "正答。", "tags": [tag]},
        {"original_num": 2, "is_correct": False, "text": "誤りの記述 " + label + " 一", "statement": "検査用 " + label + " 一は誤り。", "explanation": "誤り。", "tags": [tag]},
        {"original_num": 3, "is_correct": False, "text": "誤りの記述 " + label + " 二", "statement": "検査用 " + label + " 二は誤り。", "explanation": "誤り。", "tags": [tag]},
        {"original_num": 4, "is_correct": False, "text": "誤りの記述 " + label + " 三", "statement": "検査用 " + label + " 三は誤り。", "explanation": "誤り。", "tags": [tag]},
      ]
    }
qs = []; n = 0
for unit, cnt in SHARE_A.items():
    for _ in range(cnt): n += 1; qs.append(make_q(unit, "mock", "free_a", n))
for unit, cnt in SHARE_B.items():
    for _ in range(cnt): n += 1; qs.append(make_q(unit, "mock", "free_b", n))
PAYLOAD = json.dumps({"questions": qs}, ensure_ascii=False)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")

def wait_count(pg, want, limit=30):
    t0 = time.time()
    while time.time() - t0 < limit:
        n = pg.evaluate("async () => window.Storage.countQuestions()")
        if n >= want: return n
        pg.wait_for_timeout(150)
    return pg.evaluate("async () => window.Storage.countQuestions()")

MODAL = """(sel) => { const m = document.querySelector(sel); return !!(m && !m.hidden); }"""

def run_exam_ui(pg, size):
    """始まっている模試を最後まで解いて提出する（V3.10：1枚の問題用紙）"""
    pg.wait_for_selector("#paper-list .pq", timeout=30000)
    pg.wait_for_timeout(400)
    answered = pg.evaluate("""() => {
      const ex = window.Half2Impl.state.exam;
      let n = 0;
      ex.questions.forEach((qq, i) => {
        const li = document.querySelector('#paper-list .pq[data-index="' + i + '"]');
        if (!li) { return; }
        const inp = li.querySelector('.pq-num-input');
        if (inp) { inp.value = '1'; n++; return; }
        const c = li.querySelector('.choice-card .choice-body');
        if (c) { c.click(); n++; }
      });
      return n; }""")
    pg.click("#paper-submit")
    pg.wait_for_selector("#modal-exam-submit:not([hidden])", timeout=8000)
    pg.click("#exam-submit-go")
    pg.wait_for_timeout(2500)
    return answered

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    wait_count(pg, 249)
    pg.wait_for_function("window.__INIT_DONE === true", timeout=60000)   # 同梱データ（見本＋体験用）の取り込みまで待つ（V2.99）
    pg.evaluate("""async () => { await window.Storage.setMetaBulk({ onboarding_done: true,
      tips_seen: ['unit_hero','qty','next','scan','level','settings_btn','theme','back','home_tip',
                  'qstar','tagpill','star','locked','memo','detail','summary',
                  'q_star','img_toggle','numeric_input','pomodoro','stem_expand','ground','exam'] }); }""")
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(1200)
    pg.evaluate("() => { window.Main.closeModals(); }")

    # V2.99：体験用の予想問題90問が同梱されるようになった（起動時に自動で入る）。
    # この試験は「印つきの球が無い端末」から始めたいので、同梱ぶんを外して本体（見本249問）だけにする。
    # 印は立てたままにする（再読込で戻ってこないように）。
    pg.wait_for_function("window.__INIT_DONE === true", timeout=60000)
    pg.evaluate("""async () => { const S = window.Storage;
      await S.resetAll();
      await S.importText(window.SEED_QUESTIONS_TSV);
      await S.setMetaBulk({ seed_imported: true, seed_version: window.SEED_VERSION,
        free_mock_imported: true, free_mock_version: window.FREE_MOCK_VERSION || null, onboarding_done: true,
        tips_seen: ['unit_hero','qty','next','scan','level','settings_btn','theme','back','home_tip',
                    'qstar','tagpill','star','locked','memo','detail','summary',
                    'q_star','img_toggle','numeric_input','pomodoro','stem_expand','ground','exam'] });
      await window.Scheduler.refreshAll({ recomputeWeakness: true }); await window.Main.refreshHome(); }""")
    pg.evaluate("() => { window.Main.closeModals(); }")
    nb = pg.evaluate("async () => [await window.Storage.countQuestions(), await window.Storage.countQuestionsByVariant('free_a')]")
    ok("下ごしらえ：印つきの球が無い端末（本体249問だけ）", nb == [249, 0], nb)

    # 解禁条件を満たす（本体の肢に履歴を付ける）
    unl = pg.evaluate("""async () => {
      const S = window.Storage; const atoms = await S.getAllAtoms();
      const now = Date.now(), patch = {};
      atoms.forEach((a, i) => { if (a.pool === 'mock' || i % 5 === 0) return;
        patch[a.atom_id] = { answer_count:1, correct_count:1, last_eval:'normal',
          last_answered_at: now - 86400000*20, srs_step:3, interval_code:'1w', due_date: now + 86400000 }; });
      await S.updateAtomsBulk(patch);
      const r = await window.Scheduler.refreshUnlocks();
      return r.unlocks.filter(x => x.id === 'mock_30' || x.id === 'mock_60').map(x => [x.id, x.unlocked]);
    }""")
    ok("下ごしらえ：プチ・ハーフが解禁される", all(u[1] for u in unl), unl)
    ok("鍵が無い＝無料", pg.evaluate("() => !window.NurseLicense.isPaid()"))

    # --- ① 球が無い（いまの公開版）：止めない。印無しの記録があっても止めない ---
    g0 = pg.evaluate("""async () => { const H = window.Half2Impl, S = window.Storage;
      const states = await S.getUnlockState();
      await S.saveExamResult({ exam_id:'mock_30', at: Date.now() - 5000, total:30, correct:20, passed:false, elapsed_ms:1000 });
      return await H.freeExamGate('mock_30', states); }""")
    ok("球が無ければ門は開いたまま（印無しの記録があっても）", g0["blocked"] is False and g0["first"] is False and g0["variant"] is None, g0)
    r0 = pg.evaluate("""async () => { const H = window.Half2Impl, M = window.Main;
      await H.startExam('mock_30', 'real'); await new Promise(r => setTimeout(r, 400));
      const out = { mode: (M.state.session||{}).mode, n: (H.state.exam.questions||[]).length, variant: H.state.exam.variant,
                    freeModal: !document.querySelector('#modal-free-exam').hidden };
      if (typeof M.hooks.onAbort === 'function') { M.hooks.onAbort('exam'); } M.endSession(); M.closeModals(); M.go('home');
      return out; }""")
    ok("球が無ければ従来どおり模試が始まる（案内は出ない）", r0["mode"] == "exam" and r0["n"] == 30 and r0["variant"] is None and not r0["freeModal"], r0)

    # --- ② 球を入れる：1回目 ---
    pg.evaluate("t => { window.__T = t; }", PAYLOAD)
    rep = pg.evaluate("async () => window.Storage.importText(window.__T)")
    ok("印つき90問が入る", rep.get("imported") == 90 and rep.get("variants") == {"free_a": 30, "free_b": 60}, rep.get("variants"))
    pg.evaluate("async () => { await window.Scheduler.refreshAll({recomputeWeakness:true}); }")
    g1 = pg.evaluate("""async () => { const H = window.Half2Impl, S = window.Storage;
      return await H.freeExamGate('mock_30', await S.getUnlockState()); }""")
    ok("球あり・印つきの記録なし → 1回目（印無しの古い記録は数えない）",
       g1["variant"] == "free_a" and g1["first"] is True and g1["blocked"] is False and g1["other"]["id"] == "mock_60", g1)

    # 受け方のモーダルに「1回ぶん」の1行
    pg.evaluate("async () => { await window.Half2Impl.startExam('mock_30'); }")
    pg.wait_for_timeout(500)
    ok("1回目：受け方のモーダルが開き、「1回ぶん」の1行が見える",
       pg.evaluate(MODAL, "#modal-exam-style") and pg.evaluate("() => !document.querySelector('#exam-style-once').hidden"))
    # 本番モードで受けて、最後まで解く（履歴に印が残る道を実際に通す）
    pg.click('#modal-exam-style [data-exam-style="real"]')
    pg.wait_for_timeout(600)
    ok("印で組まれている（free_a 30問）",
       pg.evaluate("() => { const ex = window.Half2Impl.state.exam; return ex.variant === 'free_a' && ex.questions.length === 30; }"))
    answered = run_exam_ui(pg, 30)
    res_shown = pg.evaluate(MODAL, "#modal-exam-result")
    btns = pg.evaluate("() => [document.querySelector('#btn-exam-share').hidden, document.querySelector('#btn-exam-review').hidden]")
    ok("30問を解いて採点される（復習・シェアのボタンは出ている）", answered >= 30 and res_shown and btns == [False, False], (answered, res_shown, btns))
    pg.evaluate("() => { window.Main.closeModals(); window.Main.go('home'); }")
    hist = pg.evaluate("async () => (await window.Storage.getExamHistory('mock_30')).map(h => [h.variant || null, h.total])")
    ok("履歴に印つきの記録が残る（印無しの古い記録も残る）", ["free_a", 30] in hist and [None, 30] in hist, hist)

    # --- ③ 2回目：模試を始めず案内。もう片方（ハーフ）はまだ受けられる ---
    pg.evaluate("async () => { await window.Half2Impl.startExam('mock_30'); }")
    pg.wait_for_timeout(500)
    shown = pg.evaluate(MODAL, "#modal-free-exam")
    title = pg.text_content("#free-exam-title") or ""
    body = pg.text_content("#free-exam-body") or ""
    acts = pg.evaluate("() => Array.from(document.querySelectorAll('#free-exam-actions [data-fx]')).map(b => b.getAttribute('data-fx'))")
    ok("2回目：模試は始まらず案内が出る", shown and pg.evaluate("() => (window.Main.state.session||{}).mode") != "exam", (shown, title))
    ok("見出し：1回ぶんの予想問題が入っている", "プチ模試は1回ぶんの予想問題が入っています" in title, title)
    ok("本文：まず受けた結果を認める（30問はもう解きました・受けた日）", "30問はもう解きました" in body and "受けた日" in body, body[:120])
    ok("本文：ハーフ模試はまだ受けられる", "ハーフ模試（60問）はまだ受けられます" in body, body[:200])
    ok("本文：必修は無料のまま", "過去問の必修は、買わなくてもこのまま使えます" in body)
    ok("ボタン：ハーフを受ける／結果を見る／有料版", acts == ["other", "result", "buy"], acts)
    ok("受け方のモーダルは開いていない", not pg.evaluate(MODAL, "#modal-exam-style"))

    # ［結果を見る］
    pg.click('#modal-free-exam [data-fx="result"]')
    pg.wait_for_timeout(400)
    rt = pg.text_content("#exam-result-title") or ""
    btns2 = pg.evaluate("() => [document.querySelector('#btn-exam-share').hidden, document.querySelector('#btn-exam-review').hidden]")
    ok("［結果を見る］で過去の結果が見える", pg.evaluate(MODAL, "#modal-exam-result") and "プチ模試の結果" in rt, rt)
    ok("過去の結果では復習とシェアを隠す", btns2 == [True, True], btns2)
    ok("点数が出ている", "/ 30" in (pg.text_content("#exam-score") or ""))
    pg.evaluate("() => { window.Main.closeModals(); }")

    # ［ハーフ模試を受ける］→ ハーフの受け方モーダル（1回ぶんの1行つき）
    pg.evaluate("async () => { await window.Half2Impl.startExam('mock_30'); }")
    pg.wait_for_timeout(400)
    pg.click('#modal-free-exam [data-fx="other"]')
    pg.wait_for_timeout(600)
    ok("［ハーフ模試を受ける］でハーフの受け方モーダルが開く（1回ぶんの1行つき）",
       pg.evaluate(MODAL, "#modal-exam-style") and pg.evaluate("() => window.Half2Impl.state.exam.pendingStyleId") == "mock_60"
       and pg.evaluate("() => !document.querySelector('#exam-style-once').hidden"))
    pg.evaluate("() => { window.Main.closeModals(); }")

    # --- ④ 両方受け終わったら「有料版に入っています」 ---
    pg.evaluate("""async () => { await window.Storage.saveExamResult({ exam_id:'mock_60', variant:'free_b', at: Date.now(), total:60, correct:45,
      hisshu:{total:14,correct:12,pct:86,pass:true}, ippan:{total:46,correct:33,score:179,pass:false}, passed:false, elapsed_ms:120000,
      by_unit:[{unit:'必修',total:14,correct:12}] }); }""")
    pg.evaluate("async () => { await window.Half2Impl.startExam('mock_60'); }")
    pg.wait_for_timeout(500)
    title2 = pg.text_content("#free-exam-title") or ""
    body2 = pg.text_content("#free-exam-body") or ""
    acts2 = pg.evaluate("() => Array.from(document.querySelectorAll('#free-exam-actions [data-fx]')).map(b => b.getAttribute('data-fx'))")
    ok("両方受け終わり：見出しは「製品版に入っています」（V3.02：有料版と言わない）", pg.evaluate(MODAL, "#modal-free-exam") and "予想問題の続きは製品版に入っています" in title2, title2)
    ok("本文：ここまで／有料版の中身／必修は無料のまま",
       "プチ30問とハーフ60問はここまでです" in body2 and "いじわる模試" in body2 and "過去問の必修は、買わなくてもこのまま使えます" in body2, body2[:200])
    ok("ボタン：有料版を見る／結果を見る／必修の学習に戻る", acts2 == ["buy", "result", "home"], acts2)
    ok("カウントダウン（あと1回！）を出さない", "あと1回" not in title + body + title2 + body2)
    pg.click('#modal-free-exam [data-fx="result"]')
    pg.wait_for_timeout(400)
    ok("ハーフの結果に単元ごとの正答率が出る", "単元ごとの正答率" in (pg.text_content("#exam-score") or ""))
    pg.evaluate("() => { window.Main.closeModals(); }")
    pg.evaluate("async () => { await window.Half2Impl.startExam('mock_30'); }")
    pg.wait_for_timeout(400)
    ok("プチ側から押しても同じ「製品版」の案内", "予想問題の続きは製品版に入っています" in (pg.text_content("#free-exam-title") or ""))
    pg.click('#modal-free-exam [data-fx="home"]')
    pg.wait_for_timeout(300)
    ok("［必修の学習に戻る］でホームへ", pg.evaluate("() => window.Main.state.screen") == "home" and not pg.evaluate(MODAL, "#modal-free-exam"))

    # --- ⑤ いじわる模試は対象外／鍵ありは何度でも ---
    gw = pg.evaluate("async () => window.Half2Impl.freeExamGate('mock_weak', await window.Storage.getUnlockState())")
    ok("いじわる模試は回数の門の対象外", gw["variant"] is None and gw["blocked"] is False)
    pg.evaluate("() => { window.__isPaid0 = window.NurseLicense.isPaid; window.NurseLicense.isPaid = () => true; }")
    pg.evaluate("async () => { await window.Half2Impl.startExam('mock_30'); }")
    pg.wait_for_timeout(500)
    paid_ok = pg.evaluate(MODAL, "#modal-exam-style") and not pg.evaluate(MODAL, "#modal-free-exam") \
              and pg.evaluate("() => document.querySelector('#exam-style-once').hidden")
    pg.evaluate("() => { window.NurseLicense.isPaid = window.__isPaid0; window.Main.closeModals(); }")
    ok("鍵ありは2回目も受けられ、「1回ぶん」の1行も出ない", paid_ok)

    # --- ⑥ 採点のときは復習・シェアのボタンが戻る ---
    pg.evaluate("""() => { window.Half2Impl.showExamResult({ exam_id:'mock_30', style:'real', at: Date.now(), total:30, correct:22,
      hisshu:{total:6,correct:5,pct:83,pass:true}, ippan:{total:24,correct:17,score:177,pass:false}, passed:false,
      patterns:{A:3,B:0,C:10}, by_unit:null, elapsed_ms:60000 }); }""")
    pg.wait_for_timeout(800)
    btns3 = pg.evaluate("() => [document.querySelector('#btn-exam-share').hidden, document.querySelector('#btn-exam-review').hidden]")
    ok("採点のときは復習とシェアのボタンが戻る", btns3 == [False, False], btns3)
    pg.evaluate("() => { window.Main.closeModals(); }")

    hooks = pg.evaluate("() => Object.keys(window.Main.hooks||{}).filter(k => typeof window.Main.hooks[k] === 'function')")
    ok("hooks が残っていない", not hooks, hooks)
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  free_exam_once" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
