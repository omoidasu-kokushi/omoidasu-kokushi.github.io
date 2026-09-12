# -*- coding: utf-8 -*-
"""test_free_exam_variant.py — 無料版の模試を印（variant）で固定する（V2.96）

【何が起きていたか】
  無料版はプチ模試（30問）とハーフ模試（60問）を1回ずつ受けられ、中身は体験用の
  予想問題（プチ用30問＝variant "free_a"／ハーフ用60問＝"free_b"・pool "mock"）。
  作問側は印を書いて出していたが、アプリは variant を1か所も見ていなかった
  （grep で0件）。模試は V2.80 の単元枠と mix で全体から組むので、
  必修249問＋体験用90問を入れて V2.95 の buildQueue で組むと実測でこうなった。

    プチ30問  … main 5／free_a 12／free_b 13
    ハーフ60問 … main 13／free_a 15／free_b 32

  ・プチで出た問題がハーフにも出る（「さっきと同じ問題が出た」＝体験として失敗）
  ・必修の過去問（毎日の学習で計画的に消化するもの）を模試が横から食う

【直したこと（無料版の設計 V1.00 §1-2 案A）】
  ・storage.js  toAtomRecord が variant をアトムへ非正規化する（pool と同じ理由）。
                取り込みレポートに印の内訳を出す（綴り違いは「その模試が0問」になる）
  ・scheduler.js buildQueue に options.variant。「pool が mock かつ印が一致」だけにする。
                variant を渡したら includeMock 無しでも模試待ちを外さない
                （渡したのに静かに0問、を防ぐ。getKnockQueue の tag/label と同じ罠）
  ・part2       launchExam：ライセンスが無い（無料）とき、プチ→free_a・ハーフ→free_b を渡す。
                印の球が size に足りなければ、これまでどおりの組み方に落ちる
                （いまの公開版は印つきを1問も持っていないので、ここで止めると
                  無料の利用者の模試が全部「出題できる問題がありません」になる）。
                直前モードの ranks（S/A 絞り）は印で組むときは外す。

【ここで固定すること】
  ・印を渡せば全部その印（pool mock）。free_a と free_b は重ならない
  ・印を渡さない組み方（有料版）は変えていない：main が混ざる
  ・ライセンスの判断は main（part2）にあり、scheduler は NurseLicense を知らない
  ・無料状態の launchExam は mock_30→free_a／mock_60→free_b、直前モードでも同じ
  ・購入済みなら印で絞らない
  ・印つきが無い／足りないときは従来の組み方に落ちる（size を守る）
  ・取り込みレポートに variants の内訳が出る
"""
import os, sys, io, json
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p2 = io.open(os.path.join(base, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()
sc = io.open(os.path.join(base, "scheduler.js"), encoding="utf-8").read()
sj = io.open(os.path.join(base, "storage.js"), encoding="utf-8").read()

# ---------------- 静的 ----------------
ok("アトムに variant を非正規化している（storage.js toAtomRecord）",
   "variant        :" in sj and "印の無い問題は null" in sj)
ok("取り込みレポートに印の内訳（report.variants）", "report.variants" in sj)
ok("候補に variant を持つ（scheduler.js foldAtomsToCandidates）", "variant: a.variant || null" in sc)
ok("buildQueue に options.variant", "options.variant" in sc and "c.pool === 'mock' && c.variant === wantVariant" in sc)
ok("variant を渡したら includeMock 無しでも模試待ちを外さない",
   "印で選ぶときだけは外さない" in sc and "if (!wantVariant) {" in sc)
ok("なぜ印で絞るかが実測つきで書いてある", "main 5／free_a 12／free_b 13" in sc)
ok("scheduler はライセンスを知らない（売り方を混ぜない）", "NurseLicense" not in sc)
ok("プチ→free_a／ハーフ→free_b の対応表", "mock_30: 'free_a', mock_60: 'free_b'" in p2)
ok("ライセンスを見るのは main（freeExamVariant）", "function freeExamVariant" in p2 and "L.isPaid()" in p2)
ok("印で組むときは ranks を外す", "k !== 'ranks'" in p2)
ok("印で組めるかは buildQueue の前に問題レコードの数で見る（全アトムの読みは1回だけ・§6-7）",
   "S.countQuestionsByVariant(freeVariant)" in p2 and "function countQuestionsByVariant" in sj
   and "countQuestionsByVariant: countQuestionsByVariant" in sj)
ok("足りないときは従来の組み方に落ちる（size を守る）",
   "if (n >= size) { return K.buildQueue(withFreeVariant(opts, freeVariant)); }" in p2
   and "return K.buildQueue(opts);" in p2)
ok("scheduler の模試待ちの門は options.includeMock のまま（batchAJ の見張りを壊していない）",
   "if (!options.includeMock)" in sc)
ok("印で固定できたら直前モードの再抽選に回さない",
   "if (q.variant) {" in p2 and "if (q.questions.length >= size) { return finishLaunch(examId, q, style); }" in p2)
ok("画面のレポートにも印の内訳を出す", "うち印つき" in p2)

# ---------------- 合成データ（本物の出題基準の分類名・タグを使う） ----------------
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
# EXAM_UNIT_SHARE を 30問／60問に按分した枠と同じ配分（体験用の球はこの配分で作ってある）
SHARE_A = {"必修": 6, "成人看護学": 4, "老年看護学": 3, "小児看護学": 2, "基礎看護学": 2, "母性看護学": 2,
           "疾病の成り立ちと回復の促進": 2, "精神看護学": 2, "在宅看護論／地域・在宅看護論": 2,
           "人体の構造と機能": 2, "健康支援と社会保障制度": 2, "看護の統合と実践": 1}
SHARE_B = {"必修": 14, "成人看護学": 8, "老年看護学": 5, "小児看護学": 5, "基礎看護学": 4, "母性看護学": 4,
           "疾病の成り立ちと回復の促進": 4, "精神看護学": 4, "在宅看護論／地域・在宅看護論": 3,
           "人体の構造と機能": 3, "健康支援と社会保障制度": 3, "看護の統合と実践": 3}
assert sum(SHARE_A.values()) == 30 and sum(SHARE_B.values()) == 60

def make_q(unit, pool, variant, n):
    major, medium, sub, rank, tag = TAX[unit]
    label = (variant or pool) + "-" + str(n)
    return {
      "unit": unit, "major": major, "medium": medium, "sub_item": sub, "rank": rank,
      "source": None, "pool": pool, "variant": variant,
      "question_type": "single", "select_count": 1, "image_url": None, "numeric_answer": None,
      "stem": "検査用の問題 " + label + "（" + sub + "）で正しいのはどれか。",
      "overall_explanation": "検査用の全体解説 " + label + "。印で球を分ける確認に使う。",
      "comparison_table": None, "mermaid_code": None, "evidence": None,
      "is_splittable": False, "origin_key": None,
      "atoms": [
        {"original_num": 1, "is_correct": True,  "text": "正しい記述 " + label,
         "statement": "検査用 " + label + " は正しい記述である。", "explanation": "正答。検査用。", "tags": [tag]},
        {"original_num": 2, "is_correct": False, "text": "誤りの記述 " + label + " その一",
         "statement": "検査用 " + label + " その一は誤りである。", "explanation": "誤り。検査用。", "tags": [tag]},
        {"original_num": 3, "is_correct": False, "text": "誤りの記述 " + label + " その二",
         "statement": "検査用 " + label + " その二は誤りである。", "explanation": "誤り。検査用。", "tags": [tag]},
        {"original_num": 4, "is_correct": False, "text": "誤りの記述 " + label + " その三",
         "statement": "検査用 " + label + " その三は誤りである。", "explanation": "誤り。検査用。", "tags": [tag]},
      ]
    }

qs = []
n = 0
for unit, cnt in SHARE_A.items():
    for _ in range(cnt): n += 1; qs.append(make_q(unit, "mock", "free_a", n))
for unit, cnt in SHARE_B.items():
    for _ in range(cnt): n += 1; qs.append(make_q(unit, "mock", "free_b", n))
for unit in TAX:                       # 本体（過去問扱い）を各単元1問。印は無し
    n += 1; qs.append(make_q(unit, "main", None, n))
for i in range(5):                     # 印が5問しか無い球（足りないときの落ち方を見る）
    n += 1; qs.append(make_q("必修", "mock", "free_c", n))
PAYLOAD = json.dumps({"questions": qs}, ensure_ascii=False)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")

LAUNCH = """async (args) => {
  const M = window.Main, H = window.Half2Impl;
  await H.launchExam(args.id, args.size, args.style);
  await new Promise(r => setTimeout(r, 300));
  const ex = H.state.exam || {};
  const qs = ex.questions || [];
  const by = {};
  qs.forEach(q => { const k = (q.pool||'main') + ':' + (q.variant||'-'); by[k] = (by[k]||0) + 1; });
  const out = { n: qs.length, variant: ex.variant === undefined ? 'undef' : ex.variant, by: by,
                ids: qs.map(q => q.q_id), mode: (M.state.session||{}).mode,
                toast: (document.querySelector('#toast') && !document.querySelector('#toast').hidden)
                        ? document.querySelector('#toast-text').textContent : '' };
  if (typeof M.hooks.onAbort === 'function') { M.hooks.onAbort('exam'); }
  M.endSession(); M.closeModals(); M.go('home');
  return out;
}"""

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    # 同梱シードの取り込みは __APP_READY のあとも走っている（200件ずつの書き込み）。
    # 途中で reload すると 200問で止まったまま二度と続きが入らない（実測：countQuestions 200・
    # last_import_report は updated 200／skipped_missing 49）。ここではテストの都合として待つ。
    # アプリ側の扱いは判断待ち（引き継ぎ §7）。
    # 待ち方は Python 側のループ。wait_for_function に async の述語を渡すと、値が 0（偽）でも
    # 通ってしまうことがあった（実測：述語の戻りが 0 なのに wait が返った）。
    import time as _time
    _t0 = _time.time()
    while _time.time() - _t0 < 60:
        if pg.evaluate("async () => window.Storage.countQuestions()") >= 249: break
        pg.wait_for_timeout(100)
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

    paid0 = pg.evaluate("() => window.NurseLicense.isPaid()")
    ok("鍵が無い＝無料の状態から始める", paid0 is False, paid0)
    ok("対応表がそのまま見える（テストからも）",
       pg.evaluate("() => JSON.stringify(window.Half2Impl.FREE_EXAM_VARIANT)") == '{"mock_30":"free_a","mock_60":"free_b"}')

    # --- ① 印つきの問題が1問も無い（＝いまの公開版）。無料でも従来どおり組める ---
    n0 = pg.evaluate("async () => window.Storage.countQuestions()")
    ok("同梱シードが入っている（249問以上）", n0 >= 249, n0)
    r0 = pg.evaluate(LAUNCH, {"id": "mock_30", "size": 30, "style": "real"})
    ok("印つきが無ければ、無料でもプチ模試は30問組める（従来どおり）",
       r0["n"] == 30 and r0["variant"] is None, json.dumps(r0, ensure_ascii=False)[:300])
    ok("そのとき「足りない」の断りは出さない（0問なら事故ではなく、いまの公開版そのもの）",
       "しか無い" not in (r0["toast"] or "") and "しか組めない" not in (r0["toast"] or ""), r0["toast"])

    # --- ② 合成データを取り込む：free_a 30／free_b 60／main 12／free_c 5 ---
    pg.evaluate("t => { window.__T = t; }", PAYLOAD)
    rep = pg.evaluate("async () => { const r = await window.Storage.importText(window.__T); return r; }")
    ok("取り込めた（skipped 0）", rep.get("ok") and rep.get("skipped", 0) == 0 and rep.get("imported") == 107,
       {k: rep.get(k) for k in ("imported", "skipped", "pool_main", "pool_mock", "tax_bad", "tag_bad")})
    ok("プールの内訳：本体12／模試用95", rep.get("pool_main") == 12 and rep.get("pool_mock") == 95,
       (rep.get("pool_main"), rep.get("pool_mock")))
    ok("印の内訳がレポートに出る", rep.get("variants") == {"free_a": 30, "free_b": 60, "free_c": 5}, rep.get("variants"))
    ok("分類名・タグは出題基準どおり（tax_bad 0／tag_bad 0）",
       not rep.get("tax_bad") and not rep.get("tag_bad"), (rep.get("tax_bad"), rep.get("tag_bad"), rep.get("tax_examples")))
    pg.evaluate("async () => { await window.Scheduler.refreshAll({recomputeWeakness:true}); }")

    cnt = pg.evaluate("""async () => { const S = window.Storage;
      return [await S.countQuestionsByVariant('free_a'), await S.countQuestionsByVariant('free_b'),
              await S.countQuestionsByVariant('free_c'), await S.countQuestionsByVariant('free_zzz'),
              await S.countQuestionsByVariant(null)]; }""")
    ok("印つきの問題数を数えられる（free_a 30／free_b 60／free_c 5／無い印 0／印なし 0）",
       cnt == [30, 60, 5, 0, 0], cnt)

    at = pg.evaluate("""async () => {
      const S = window.Storage;
      const qs = (await S.getAllQuestions()).filter(q => q.variant);
      const a = await S.getAtomsByQuestion(qs[0].q_id);
      return { q: qs[0].variant, atoms: a.map(x => x.variant) };
    }""")
    ok("アトムにも印が落ちている（buildQueue はアトムから候補を組む）",
       at["q"] and all(v == at["q"] for v in at["atoms"]) and len(at["atoms"]) == 4, at)

    # --- ③ buildQueue：印で絞る ---
    b = pg.evaluate("""async () => {
      const K = window.Scheduler, H = window.Half2Impl;
      const run = async (o) => {
        const q = await K.buildQueue(o);
        const by = {}; q.questions.forEach(x => { const k = (x.pool||'main') + ':' + (x.variant||'-'); by[k]=(by[k]||0)+1; });
        const byU = {}; q.questions.forEach(x => { byU[x.unit]=(byU[x.unit]||0)+1; });
        return { n: q.questions.length, by, byU, ids: q.questions.map(x=>x.q_id), variant: q.variant, reason: q.reason||null };
      };
      const mix = { fresh: 0.10, faded: 0.45, unseen: 0.45 };
      return {
        a:   await run({ mode:'exam', count:30, applyGuard:false, shuffle:true, includeMock:true, variant:'free_a', mix, unitQuota:H.examUnitQuota(30) }),
        b:   await run({ mode:'exam', count:60, applyGuard:false, shuffle:true, includeMock:true, variant:'free_b', mix, unitQuota:H.examUnitQuota(60) }),
        noInc: await run({ mode:'exam', count:30, applyGuard:false, shuffle:true, variant:'free_a' }),
        zzz: await run({ mode:'exam', count:30, applyGuard:false, shuffle:true, includeMock:true, variant:'free_zzz' }),
        plain: await run({ mode:'exam', count:60, applyGuard:false, shuffle:true, includeMock:true, mix, unitQuota:H.examUnitQuota(60) }),
        quotaA: H.examUnitQuota(30), quotaB: H.examUnitQuota(60)
      };
    }""")
    ok("free_a を渡すと30問すべて mock:free_a", b["a"]["n"] == 30 and b["a"]["by"] == {"mock:free_a": 30}, b["a"]["by"])
    ok("free_b を渡すと60問すべて mock:free_b", b["b"]["n"] == 60 and b["b"]["by"] == {"mock:free_b": 60}, b["b"]["by"])
    ok("プチとハーフの中身は1問も重ならない", not (set(b["a"]["ids"]) & set(b["b"]["ids"])))
    ok("印で絞っても単元の枠はそのまま満たす（プチ）", b["a"]["byU"] == b["quotaA"], (b["a"]["byU"], b["quotaA"]))
    ok("印で絞っても単元の枠はそのまま満たす（ハーフ）", b["b"]["byU"] == b["quotaB"], (b["b"]["byU"], b["quotaB"]))
    ok("戻り値に variant が入る", b["a"]["variant"] == "free_a" and b["plain"]["variant"] is None)
    ok("includeMock を渡し忘れても、印を渡せば拾う（静かに0問にならない）",
       b["noInc"]["n"] == 30 and b["noInc"]["by"] == {"mock:free_a": 30}, b["noInc"]["by"])
    ok("無い印を渡すと0問で、理由に印の名前が入る",
       b["zzz"]["n"] == 0 and "free_zzz" in (b["zzz"]["reason"] or ""), b["zzz"]["reason"])
    ok("印を渡さない組み方（有料版）は変えていない：本体の問題が混ざる",
       b["plain"]["n"] == 60 and b["plain"]["by"].get("main:-", 0) > 0, b["plain"]["by"])

    # --- ④ launchExam：無料状態ならプチ→free_a・ハーフ→free_b ---
    ra = pg.evaluate(LAUNCH, {"id": "mock_30", "size": 30, "style": "real"})
    ok("無料のプチ模試（本番モード）は free_a 30問", ra["n"] == 30 and ra["by"] == {"mock:free_a": 30} and ra["variant"] == "free_a",
       json.dumps({k: ra[k] for k in ("n", "by", "variant", "mode")}, ensure_ascii=False))
    ok("模試として始まっている（mode exam）", ra["mode"] == "exam", ra["mode"])
    rb = pg.evaluate(LAUNCH, {"id": "mock_60", "size": 60, "style": "final"})
    ok("無料のハーフ模試（直前モードでも）は free_b 60問（ranks で削れない）",
       rb["n"] == 60 and rb["by"] == {"mock:free_b": 60} and rb["variant"] == "free_b",
       json.dumps({k: rb[k] for k in ("n", "by", "variant")}, ensure_ascii=False))
    ok("プチとハーフで同じ問題が出ない", not (set(ra["ids"]) & set(rb["ids"])))
    ok("印で組んだときは「足りない」の断りを出さない",
       "しか無い" not in (ra["toast"] or "") + (rb["toast"] or "") and "しか組めない" not in (ra["toast"] or "") + (rb["toast"] or ""),
       (ra["toast"], rb["toast"]))
    rw = pg.evaluate(LAUNCH, {"id": "mock_weak", "size": 30, "style": "real"})
    ok("いじわる模試は印で絞らない（対応表に無い）", rw["variant"] is None and rw["n"] > 0, (rw["variant"], rw["n"]))

    # --- ⑤ 印の球が足りない（free_c は5問）：断ってから従来の組み方に落ちる ---
    pg.evaluate("() => { window.Half2Impl.FREE_EXAM_VARIANT.mock_120 = 'free_c'; }")
    rc = pg.evaluate(LAUNCH, {"id": "mock_120", "size": 120, "style": "real"})
    pg.evaluate("() => { delete window.Half2Impl.FREE_EXAM_VARIANT.mock_120; }")
    ok("球が5問しか無ければ、120問を従来どおり組む（問題数は絶対に減らさない）",
       rc["n"] == 120 and rc["variant"] is None, (rc["n"], rc["variant"]))
    ok("そのときは黙らずに断る（一部だけあるのはデータの事故）",
       "体験用の予想問題（free_c）が 5問しか無い" in (rc["toast"] or ""), rc["toast"])

    # --- ⑥ 購入済みなら印で絞らない ---
    pg.evaluate("() => { window.__isPaid0 = window.NurseLicense.isPaid; window.NurseLicense.isPaid = () => true; }")
    fv = pg.evaluate("() => [window.Half2Impl.freeExamVariant('mock_30'), window.Half2Impl.freeExamVariant('mock_60')]")
    rp = pg.evaluate(LAUNCH, {"id": "mock_30", "size": 30, "style": "real"})
    pg.evaluate("() => { window.NurseLicense.isPaid = window.__isPaid0; }")
    ok("購入済みは印を渡さない", fv == [None, None], fv)
    ok("購入済みのプチ模試は印で絞らない（全体から組む）", rp["n"] == 30 and rp["variant"] is None, (rp["n"], rp["variant"], rp["by"]))
    fv2 = pg.evaluate("() => window.Half2Impl.freeExamVariant('mock_30')")
    ok("戻すと無料の判定に戻る", fv2 == "free_a", fv2)

    # --- ⑦ 中断のあと hooks が残っていない（V1.85 の不変条件を踏んでいない） ---
    hooks = pg.evaluate("() => Object.keys(window.Main.hooks||{}).filter(k => typeof window.Main.hooks[k] === 'function')")
    ok("模試を畳んだあと hooks が残っていない", not hooks, hooks)
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  free_exam_variant" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
