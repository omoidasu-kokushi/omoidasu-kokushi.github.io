#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBN：必修の出題比率を、充足率から自動で決める（V1.89）

【なぜランク重みでやらなかったか】
`priorityScore` は preferFrequent が false のとき `rankWeight` を通らない。
つまり「頻出問題を優先する」をOFFにしている人には**1ミリも届かない**。
さらにランダムモードは shuffle 経路なので `sortCandidates` を通らず、
**そもそもランク重みが効いていない**。必修の強化をランクに載せると、
効く人と効かない人が出る。だから確率的な重みではなく、**枠**で確保する。

【なぜ枠を入れる場所を限るか】
必修は絶対基準80%（50問中40問）で、1問も吸収されない。
一般・状況は相対基準（実測ボーダー142〜167点）で、取りこぼしをボーダーが吸収する。
この非対称があるので必修は前倒しが正しい。ただし、

  **本日の復習には一切入れない。** 期日は測定の結果であって、優先度で歪めるものではない。
  **範囲を選んでいるとき（scope/tag/qIds）も入れない。** 利用者が範囲を明示している。

【なぜ段で向きが変わるか】
同梱シードは必修が68%（1,232/1,816肢）、過去問を入れても34%ある。
①②（boost 40% / mid 25%）を**上限**にすると、始めたばかりの人の必修が減ってしまう。
逆に③（normal 17%）を**下限**にすると、必修が80%そろったあとも必修が出続けて
一般に時間が回らない。だから ①② は floor、③ は cap。

【なぜ不退転にしないか】
レベル表示は不退転でよいが、必修の枠は戻せなければならない。忘れたら弱いままになる。
80%を超えたあと75%を割ったら 25% へ自動で戻す（ヒステリシス）。
"""
import io, json, os, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


sc = read("scheduler.js")
st = read("storage.js")
p1 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
j1, j2 = read(p1), read(p2)
html = read("index.html")

ok("割合の定義がある", "var HISSU_SHARE = { boost: 0.40, mid: 0.25, normal: 0.17 };" in sc)
ok("段ごとの向きがある", "var HISSU_DIR   = { boost: 'floor', mid: 'floor', normal: 'cap' };" in sc)
ok("17%は本番の配点比だと書いてある", "本番の配点比" in sc)
ok("80%は必修の合格基準だと書いてある", "必修の合格基準" in sc)
ok("ヒステリシスの線がある", "HISSU_BACK  = 0.75" in sc)
ok("充足率の関数がある", "function getHissuFill(" in sc)
ok("**全アトムを読み直さない（§6-7）**",
   "Promise.resolve(fillFromAtoms(atoms))" in sc and "function fillFromAtoms(" in sc)
ok("段の判定がある", "function hissuStageOf(" in sc)
ok("枠の適用がある", "function applyHissuQuota(" in sc)
ok("本日の復習には入らないと書いてある", "本日の復習には一切入れない" in sc)
ok("範囲を選んだときは入らない",
   "!options.scope && !options.tag && !(options.qIds && options.qIds.length)" in sc)
ok("段が変わったときだけ保存する", "hissuInfo.stage !== meta.hissu_stage" in sc)
ok("既定は自動", "hissu_mode              : 'auto'," in st)
ok("案内の回数を持っている", "hissu_hint_no           : 0," in st)
ok("設定に3択がある", 'id="set-hissu"' in html and 'data-hissu="strong"' in html)
ok("案内のダイアログがある", 'id="modal-hissu-hint"' in html)
ok("設定を開いたら表示を更新する", "refreshHissuNote().catch(noop);" in j2)
ok("起動時に案内を出す入口がある", "H2b.maybeHissuHint()" in j1)
ok("更新の案内と重ねない", "2枚重ねると両方読まれない" in j1)
ok("案内は3回で止まる", "(meta.hissu_hint_no || 0) >= 3" in j2)
ok("案内は自動より先に降りる（読みを増やさない）",
   "自動のままの人には出しようがない" in j2)
ok("案内は1日1回", "hissu_hint_at" in j2 and "setHours(0, 0, 0, 0)" in j2)
ok("％ではなく距離を出す", "/50 相当" in j2 and "合格ラインまで" in j2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(1400)

    fill = pg.evaluate("async () => await window.Scheduler.getHissuFill()")
    ok("必修の肢を数えられる", fill["atoms"] > 0, json.dumps(fill, ensure_ascii=False))

    stg = pg.evaluate("""() => { const K = window.Scheduler; return {
      low:  K.hissuStageOf(0.20, null),
      mid:  K.hissuStageOf(0.60, null),
      high: K.hissuStageOf(0.85, null),
      keep: K.hissuStageOf(0.78, 'normal'),
      back: K.hissuStageOf(0.74, 'normal'),
      up:   K.hissuStageOf(0.78, 'mid') }; }""")
    ok("50%未満は boost", stg["low"] == "boost", json.dumps(stg))
    ok("50〜80%は mid", stg["mid"] == "mid", json.dumps(stg))
    ok("80%以上は normal", stg["high"] == "normal", json.dumps(stg))
    ok("**normalは75%まで粘る（ヒステリシス）**", stg["keep"] == "normal", json.dumps(stg))
    ok("**75%を割ったら mid へ戻る（不退転にしない）**", stg["back"] == "mid", json.dumps(stg))
    ok("midのままなら80%を超えるまで上がらない", stg["up"] == "mid", json.dumps(stg))

    rs = pg.evaluate("""() => { const K = window.Scheduler; return {
      auto:   K.resolveHissuShare({ hissu_mode: 'auto' },   0.20),
      weak:   K.resolveHissuShare({ hissu_mode: 'normal' }, 0.20),
      strong: K.resolveHissuShare({ hissu_mode: 'strong' }, 0.90) }; }""")
    ok("自動は段どおり", rs["auto"]["share"] == 0.4 and rs["auto"]["dir"] == "floor",
       json.dumps(rs["auto"], ensure_ascii=False))
    ok("手動が自動より弱いときだけ案内する",
       rs["weak"]["hint"] is True and rs["auto"]["hint"] is False and rs["strong"]["hint"] is False,
       json.dumps(rs, ensure_ascii=False))
    ok("手動「強め」は増やす向き", rs["strong"]["dir"] == "floor", json.dumps(rs["strong"], ensure_ascii=False))
    ok("手動「本番と同じ」は減らす向き", rs["weak"]["dir"] == "cap", json.dumps(rs["weak"], ensure_ascii=False))

    # --- 枠が実際に効くか（同じ seed で比べる） ---
    q = pg.evaluate("""async () => {
      const K = window.Scheduler, S = window.Storage;
      const base = { mode:'random', count:40, applyGuard:false, newOnly:true, shuffle:true, seed:12345 };
      const off = await K.buildQueue(Object.assign({}, base, { hissuQuota:false }));
      await S.setMeta('hissu_mode', 'normal');            /* dir=cap / 17% */
      const cap = await K.buildQueue(Object.assign({}, base));
      await S.setMeta('hissu_mode', 'strong');            /* dir=floor / 40% */
      const flo = await K.buildQueue(Object.assign({}, base));
      await S.setMeta('hissu_mode', 'auto');
      const h = qs => qs.filter(x => String(x.unit||'').indexOf('必修') >= 0).length;
      return { off:{n:off.questions.length, hissu:h(off.questions)},
               cap:{n:cap.questions.length, hissu:cap.hissu_count, share:cap.hissu.share, dir:cap.hissu.dir},
               flo:{n:flo.questions.length, hissu:flo.hissu_count, share:flo.hissu.share, dir:flo.hissu.dir} };
    }""")
    ok("枠を切ったときの必修の数を取れた", q["off"]["n"] == 40, json.dumps(q, ensure_ascii=False))
    ok("**上限（17%）が効いて必修が減る**",
       q["cap"]["hissu"] <= round(40 * 0.17) and q["cap"]["hissu"] < q["off"]["hissu"],
       json.dumps(q, ensure_ascii=False))
    ok("上限をかけても問題数が減らない", q["cap"]["n"] == 40, json.dumps(q, ensure_ascii=False))
    ok("下限（40%）は、もともと多ければ何もしない",
       q["flo"]["hissu"] >= round(40 * 0.40), json.dumps(q, ensure_ascii=False))
    ok("下限をかけても問題数が減らない", q["flo"]["n"] == 40, json.dumps(q, ensure_ascii=False))

    # --- 下限が本当に増やせるか（必修だけを外した pool を作れないので、少ない count で見る） ---
    fl = pg.evaluate("""async () => {
      const K = window.Scheduler;
      const pool = await K.buildQueue({ mode:'random', count:10, applyGuard:false,
                                        newOnly:true, shuffle:true, seed:777, hissuQuota:false });
      const picked = pool.questions.map(q => ({ q_id:q.q_id, hissu: String(q.unit||'').indexOf('必修')>=0 }));
      const others = picked.map((c,i) => ({ q_id:'X'+i, hissu:false }));
      const spares = Array.from({length:20}, (_,i) => ({ q_id:'H'+i, hissu:true }));
      const out = K.applyHissuQuota(others, others.concat(spares), 10, 0.40, 1, 'floor');
      return { n: out.length, hissu: out.filter(c => c.hissu).length };
    }""")
    ok("**下限は足りないときに必修を増やす**", fl["hissu"] == 4 and fl["n"] == 10,
       json.dumps(fl, ensure_ascii=False))

    # --- 入れ替える相手がいなければ数を削らない ---
    nz = pg.evaluate("""() => {
      const K = window.Scheduler;
      const picked = Array.from({length:10}, (_,i) => ({ q_id:'A'+i, hissu:false }));
      const out = K.applyHissuQuota(picked, picked, 10, 0.40, 1, 'floor');
      return { n: out.length, hissu: out.filter(c => c.hissu).length };
    }""")
    ok("入れ替える相手がいなければ、数を削らずそのまま", nz["n"] == 10 and nz["hissu"] == 0,
       json.dumps(nz, ensure_ascii=False))

    # --- 本日の復習には触れない ---
    rv = pg.evaluate("""async () => {
      const K = window.Scheduler;
      const a = await K.getReviewQueue(30);
      return { hissu_info: !!a.hissu, n: (a.questions||[]).length };
    }""")
    ok("**本日の復習には枠が入らない**", rv["hissu_info"] is False, json.dumps(rv, ensure_ascii=False))

    # --- 範囲を選んだときは入らない ---
    scq = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler;
      const t = await S.buildTree();
      const u = t[t.length - 1];
      const a = await K.buildQueue({ mode:'random', count:20, applyGuard:false, newOnly:true,
                                     shuffle:true, scope:{ field:'unit', value:u.key } });
      return { unit: u.key, hissu_info: !!a.hissu, n: a.questions.length };
    }""")
    ok("**単元を選んだときは枠が入らない**", scq["hissu_info"] is False,
       json.dumps(scq, ensure_ascii=False))

    # --- トグルOFFでも効く（今回の眼目） ---
    off = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler;
      await S.setMeta('prefer_frequent', false);
      await S.setMeta('hissu_mode', 'normal');
      const a = await K.buildQueue({ mode:'random', count:40, applyGuard:false,
                                     newOnly:true, shuffle:true, seed:12345 });
      await S.setMeta('prefer_frequent', true);
      await S.setMeta('hissu_mode', 'auto');
      return { n: a.questions.length, hissu: a.hissu_count, share: a.hissu.share };
    }""")
    ok("**頻出優先トグルがOFFでも枠は効く**",
       off["hissu"] <= round(40 * 0.17) and off["n"] == 40, json.dumps(off, ensure_ascii=False))

    # --- 一周の完了問数が変わらない ---
    same = pg.evaluate("""async () => {
      const K = window.Scheduler;
      const a = await K.buildQueue({ mode:'random', count:5000, applyGuard:false, newOnly:true, shuffle:true });
      const b = await K.buildQueue({ mode:'random', count:5000, applyGuard:false, newOnly:true,
                                     shuffle:true, hissuQuota:false });
      return { on: a.questions.length, off: b.questions.length };
    }""")
    ok("**一周の完了問数が枠あり／なしで同じ**", same["on"] == same["off"],
       json.dumps(same, ensure_ascii=False))

    # --- 設定の3択が実際に切り替わる ---
    ui = pg.evaluate("""async () => {
      await window.Half2Impl.openSettings();
      await window.Half2Impl.setHissuMode('strong');
      const m1 = (await window.Storage.loadMeta()).hissu_mode;
      const on1 = document.querySelector('#set-hissu .seg-btn.is-active');
      await window.Half2Impl.setHissuMode('auto');
      const m2 = (await window.Storage.loadMeta()).hissu_mode;
      return { m1: m1, active1: on1 ? on1.dataset.hissu : null, m2: m2,
               note: (document.querySelector('#hissu-note')||{}).textContent || '' };
    }""")
    ok("設定から切り替えられる", ui["m1"] == "strong" and ui["m2"] == "auto",
       json.dumps(ui, ensure_ascii=False))
    ok("押した段が反転して見える", ui["active1"] == "strong", json.dumps(ui, ensure_ascii=False))
    ok("説明に％ではなく距離が出る", "/50 相当" in ui["note"], json.dumps(ui, ensure_ascii=False))

    # --- 案内は1日1回・3回で止まる ---
    hint = pg.evaluate("""async () => {
      const S = window.Storage, H = window.Half2Impl;
      await S.setMeta('hissu_mode', 'normal');
      await S.setMeta('hissu_hint_at', 0); await S.setMeta('hissu_hint_no', 0);
      const a = await H.maybeHissuHint();
      const b = await H.maybeHissuHint();          /* 同じ日は2回目が出ない */
      await H.hissuHintAnswer(false);
      await S.setMeta('hissu_hint_at', 0);
      const c = await H.maybeHissuHint();
      await H.hissuHintAnswer(false);
      await S.setMeta('hissu_hint_at', 0);
      const d = await H.maybeHissuHint();
      await H.hissuHintAnswer(false);
      await S.setMeta('hissu_hint_at', 0);
      const e = await H.maybeHissuHint();          /* 3回断ったので出ない */
      const no = (await S.loadMeta()).hissu_hint_no;
      await S.setMeta('hissu_mode', 'auto');
      return { first:a, sameDay:b, second:c, third:d, fourth:e, no:no };
    }""")
    ok("案内が出る", hint["first"] is True, json.dumps(hint, ensure_ascii=False))
    ok("**同じ日は2回出ない**", hint["sameDay"] is False, json.dumps(hint, ensure_ascii=False))
    ok("**3回断ったら以後出ない**", hint["fourth"] is False and hint["no"] >= 3,
       json.dumps(hint, ensure_ascii=False))

    # --- 自動のままなら、そもそも案内は出ない（起動でアトムを読まない） ---
    # V1.89 の初版は meta より先に getHissuFill() を呼んでいた。既定の人まで
    # 起動直後に全アトム（同梱1,816肢）を読み、画面が滑って
    # 選択肢の押下が1回ぶん落ちた（batchAP が幅ごとに揺れた）。
    quiet = pg.evaluate("""async () => {
      const S = window.Storage, H = window.Half2Impl, K = window.Scheduler;
      await S.setMeta('hissu_mode', 'auto');
      await S.setMeta('hissu_hint_at', 0); await S.setMeta('hissu_hint_no', 0);
      let reads = 0;
      const orig = S.getAllAtoms;
      S.getAllAtoms = function () { reads++; return orig.apply(this, arguments); };
      const shown = await H.maybeHissuHint();
      S.getAllAtoms = orig;
      return { shown: shown, reads: reads,
               open: !document.getElementById('modal-hissu-hint').hidden };
    }""")
    ok("**自動のままの人には案内を出さない**",
       quiet["shown"] is False and quiet["open"] is False,
       json.dumps(quiet, ensure_ascii=False))
    ok("**そのとき全アトムを読まない（起動を重くしない）**",
       quiet["reads"] == 0, json.dumps(quiet, ensure_ascii=False))

    auto = pg.evaluate("""async () => {
      const S = window.Storage, H = window.Half2Impl;
      await S.setMeta('hissu_mode', 'normal');
      await H.hissuHintAnswer(true);
      const m = await S.loadMeta();
      return { mode: m.hissu_mode, no: m.hissu_hint_no };
    }""")
    ok("［自動に戻す］で自動になり、断った回数も戻る",
       auto["mode"] == "auto" and auto["no"] == 0, json.dumps(auto, ensure_ascii=False))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBN" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
