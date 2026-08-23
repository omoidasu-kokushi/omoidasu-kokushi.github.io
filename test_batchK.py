#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.22 検証：ヘッダーの今日の問題数 ／ 復習カードの整理 ／
             ランダムの残り問題数 ／ 単元別ツリーの重複ボタン ／ 一言欄の反映"""
import json, os, sys, subprocess, glob, re
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))

P1 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
P2 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
for f in ["storage.js", "scheduler.js", P1, P2, "sw.js"]:
    p = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True)
    ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

idx = open(os.path.join(APP, "index.html"), encoding="utf-8").read()
sw = open(os.path.join(APP, "sw.js"), encoding="utf-8").read()
ok("index の script/REQUIRED が実ファイルを指す", idx.count(P1) == 2 and idx.count(P2) == 2)
ok("sw の CORE_ASSETS が実ファイルを指す", P1 in sw and P2 in sw)
ok("他版のファイル名が残っていない",
   len(set(re.findall(r"main_part1_V\d+\.\d+\.js", idx + sw))) == 1 and
   len(set(re.findall(r"main_part2_V\d+\.\d+\.js", idx + sw))) == 1)
_c = re.search(r"CACHE_NAME = 'v(\d+)\.(\d+)\.(\d+)'", sw)
ok("sw CACHE_NAME が v1.10.0 以降",
   bool(_c) and tuple(int(x) for x in _c.groups()) >= (1, 10, 0),
   _c.group(0) if _c else "not found")
ok("HTML から hero-eyebrow が消えている", "hero-eyebrow" not in idx)
ok("HTML から review-sub が消えている", "review-sub" not in idx)
ok("JS からも review-sub への書き込みが消えている",
   "setText('#review-sub'" not in open(os.path.join(APP, P1), encoding="utf-8").read())

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=20000)
    pg.wait_for_timeout(2200)
    try:
        pg.click("#welcome-start", timeout=2500)
    except Exception:
        pass
    pg.wait_for_timeout(700)
    pg.evaluate("window.Main.go('home')")
    pg.wait_for_timeout(600)

    # ---------- 本日の復習カード ----------
    hero = pg.evaluate("""() => {
      const h = document.getElementById('card-review');
      return { text: h.innerText.replace(/\\n/g,'|'),
               eyebrow: !!h.querySelector('.hero-eyebrow'),
               sub: !!document.getElementById('review-sub'),
               badge: !!h.querySelector('#review-badge'),
               h: Math.round(h.getBoundingClientRect().height) }; }""")
    ok("「主動線」の肩書きが消えている", not hero["eyebrow"], json.dumps(hero, ensure_ascii=False))
    ok("説明文が消えている", not hero["sub"], json.dumps(hero, ensure_ascii=False))
    ok("タイトルは残っている", "本日の復習" in hero["text"], hero["text"])
    ok("件数バッジの置き場所は残っている", hero["badge"], json.dumps(hero))
    ok("復習0件のときはタイトルだけになる", hero["text"].strip() == "本日の復習", hero["text"])

    due = pg.evaluate("""async () => {
      const S=window.Storage, M=window.Main;
      const at = await S.getAllAtoms();
      await S.updateAtom(at[0].atom_id, {srs_step:1, interval_code:'10m', last_eval:'hard',
        answer_count:1, due_date: Date.now()-60000});
      await M.refreshHome();
      const b = document.getElementById('review-badge');
      return { hidden: b.hidden, text: b.textContent,
               card: document.getElementById('card-review').innerText.replace(/\\n/g,'|') }; }""")
    ok("復習があるとバッジに件数が出る",
       not due["hidden"] and due["text"] == "1", json.dumps(due, ensure_ascii=False))
    ok("カードに出るのはタイトルと件数だけ",
       set(due["card"].replace("|", " ").split()) <= {"本日の復習", "1"},
       json.dumps(due, ensure_ascii=False))

    # ---------- ヘッダー ----------
    head0 = pg.evaluate("Math.round(document.querySelector('header').getBoundingClientRect().height)")
    solved = pg.evaluate("""async()=>{ const S=window.Storage,K=window.Scheduler,M=window.Main;
      const qs=await S.getAllQuestions();
      for (const q of qs){ const at=await S.getAtomsByQuestion(q.q_id);
        const cn=at.filter(a=>a.is_correct).map(a=>a.original_num);
        const rec=K.recommendEvaluations(at,cn);
        await K.applyQuestionEvaluations(q.q_id,
          at.map(a=>({atom_id:a.atom_id,eval:rec.recommendations[a.atom_id].eval,is_correct:true})),
          {mode:'new',boundaryHour:4});
        await S.bumpDailyCount(4); }
      await M.refreshHome();
      const lab=document.querySelector('.scan-label');
      return { text: lab.innerText, font: getComputedStyle(lab).fontSize,
               done: document.getElementById('scan-meter').classList.contains('is-done'),
               headerH: Math.round(document.querySelector('header').getBoundingClientRect().height) }; }""")
    ok("分析精度100%後は今日の実績表示に変わる", solved["done"], json.dumps(solved, ensure_ascii=False))
    ok("表示は「今日解いた問題数 ◯ 問」",
       solved["text"].startswith("今日解いた問題数") and solved["text"].endswith("問"),
       solved["text"])
    ok("「復習」の数は出さない", "復習" not in solved["text"], solved["text"])
    ok("文字が大きくなっている（10.88px → 12.48px）",
       solved["font"] == "12.48px", solved["font"])
    ok("ヘッダーの高さは変わらない", solved["headerH"] == head0,
       "%s -> %s" % (head0, solved["headerH"]))

    # ---------- ランダムのカウントダウン ----------
    bt = pg.evaluate("""() => {
      const f = window.Main.randomBadgeText;
      return { over: f({unlearned_questions:1001, random_qty_unlocked:false}),
               at1000: f({unlearned_questions:1000, random_qty_unlocked:false}),
               at999: f({unlearned_questions:999, random_qty_unlocked:true}),
               at1: f({unlearned_questions:1, random_qty_unlocked:true}),
               zero: f({unlearned_questions:0, random_qty_unlocked:true}),
               nul: f({unlearned_questions:null, random_qty_unlocked:false}),
               none: f(null) }; }""")
    ok("1000問を超えるうちは従来どおり出題数を出す", bt["over"] == "10問", json.dumps(bt, ensure_ascii=False))
    ok("1000問ちょうどから数えはじめる", bt["at1000"] == "1000", json.dumps(bt))
    ok("999 と数字だけを出す", bt["at999"] == "999", json.dumps(bt))
    ok("残り1問でも数字を出す", bt["at1"] == "1", json.dumps(bt))
    ok("0問（読破）では数字を出さない", bt["zero"] == "全解放", json.dumps(bt))
    ok("数が取れないときは従来表示へ倒す（動線を消さない）",
       bt["nul"] == "10問" and bt["none"] == "10問", json.dumps(bt))

    snap = pg.evaluate("""async () => {
      const h = await window.Scheduler.buildHomeSnapshot ? null : null;
      const S=window.Storage;
      const at = await S.getUnlearnedAtoms();
      const seen={}; let n=0;
      at.forEach(a=>{ if(!seen[a.q_id]){seen[a.q_id]=1;n++;} });
      return { unlearnedQ: n,
               badge: document.getElementById('random-badge').textContent,
               meta: document.getElementById('random-meta').textContent }; }""")
    ok("未学習が0なら数字は出ていない", snap["unlearnedQ"] > 0 or snap["badge"] != "0",
       json.dumps(snap, ensure_ascii=False))

    cnt = pg.evaluate("""async () => {
      const S=window.Storage, M=window.Main;
      const at = await S.getAllAtoms();
      /* 1問ぶんだけ未学習へ戻す */
      const qid = at[0].q_id;
      for (const a of at) {
        if (a.q_id !== qid) { continue; }
        await S.updateAtom(a.atom_id, {answer_count:0, last_eval:null, due_date:null,
                                       srs_step:0, interval_code:null});
      }
      await M.refreshHome();
      return { badge: document.getElementById('random-badge').textContent,
               meta: document.getElementById('random-meta').textContent,
               heights: [...document.querySelectorAll('.sub-card')]
                          .map(c=>Math.round(c.getBoundingClientRect().height)) }; }""")
    ok("残り1問なら「1」と出る", cnt["badge"] == "1", json.dumps(cnt, ensure_ascii=False))
    ok("数字の意味を説明が受けている", cnt["meta"] == "未学習の残り", cnt["meta"])
    ok("3枚のサブカードの高さは揃ったまま",
       len(set(cnt["heights"])) == 1, json.dumps(cnt["heights"]))

    wide = pg.evaluate("""() => {
      const b=document.getElementById('random-badge');
      const c=document.getElementById('card-random');
      b.textContent='1000';
      const br=b.getBoundingClientRect(), cr=c.getBoundingClientRect();
      const ico=c.querySelector('.sub-icon').getBoundingClientRect();
      return { inside: br.right <= cr.right, iconVisible: ico.width > 0,
               overlap: br.left < ico.right }; }""")
    ok("4桁でもカードからはみ出さない", wide["inside"], json.dumps(wide))
    ok("4桁でもアイコンを押し出さない",
       wide["iconVisible"] and not wide["overlap"], json.dumps(wide))

    # ---------- ランダムの階層ドリルダウン（V1.41で単元別ツリーを統合） ----------
    drill = pg.evaluate("""async () => {
      const H = window.Half2Impl;
      await H.openRandomSelect();
      await new Promise(r=>setTimeout(r,500));
      const snap = () => ({
        hero: document.getElementById('unit-hero-title').textContent,
        crumbHidden: document.getElementById('pick-crumb').hidden,
        rows: [...document.querySelectorAll('#major-list .pick-row')].map(r => ({
          name: r.querySelector('.pick-name').textContent,
          drill: r.querySelector('.pick-main').getAttribute('data-drill'),
          field: r.querySelector('.pick-main').getAttribute('data-field'),
          dice: !!r.querySelector('.pick-dice') })) });
      const l0 = snap();
      document.querySelector('#major-list .pick-main').click();
      await new Promise(r=>setTimeout(r,300));
      const l1 = snap();
      document.querySelector('#major-list .pick-main').click();
      await new Promise(r=>setTimeout(r,300));
      const l2 = snap();
      return { l0, l1, l2 }; }""")
    l0, l1, l2 = drill["l0"], drill["l1"], drill["l2"]
    ok("最上位は全単元から始まる", "全単元" in l0["hero"], json.dumps(l0["hero"]))
    ok("最上位ではパンくずを出さない（場所を取るだけ）", l0["crumbHidden"] is True)
    ok("掘るとパンくずが出る", l1["crumbHidden"] is False)
    ok("階層ごとに範囲名が変わる",
       l0["hero"] != l1["hero"] != l2["hero"], json.dumps([l0["hero"], l1["hero"], l2["hero"]]))
    ok("各階層の行に「その場で出す」サイコロがある",
       all(r["dice"] for r in l0["rows"] + l1["rows"] + l2["rows"]),
       json.dumps(drill, ensure_ascii=False)[:300])
    ok("第1階層は単元", all(r["field"] == "unit" for r in l0["rows"]),
       json.dumps(l0["rows"], ensure_ascii=False))
    ok("第2階層は大項目", all(r["field"] == "major" for r in l1["rows"]),
       json.dumps(l1["rows"], ensure_ascii=False))
    ok("第3階層は中項目で、それ以上は掘れない",
       all(r["field"] == "medium" and r["drill"] == "0" for r in l2["rows"]),
       json.dumps(l2["rows"], ensure_ascii=False))

    up = pg.evaluate("""async () => {
      document.querySelector('#pick-crumb button[data-up="0"]').click();
      await new Promise(r=>setTimeout(r,300));
      return { hero: document.getElementById('unit-hero-title').textContent,
               crumbHidden: document.getElementById('pick-crumb').hidden }; }""")
    ok("パンくずで一番上まで戻れる",
       "全単元" in up["hero"] and up["crumbHidden"] is True, json.dumps(up, ensure_ascii=False))
    _idx = open(os.path.join(APP, "index.html"), encoding="utf-8").read()
    ok("単元別学習の画面は残っていない",
       "screen-tree" not in _idx and 'data-action="go-tree"' not in _idx)

    # 範囲を指定するとその場で出題が始まる（旧「まとめて出題」の代替）
    tapped = pg.evaluate("""async () => {
      document.querySelector('#major-list .pick-dice').click();
      await new Promise(r=>setTimeout(r,1200));
      return { screen: window.Main.state.screen, mode: window.Main.state.session.mode,
               qs: window.Main.state.session.questions.length }; }""")
    ok("サイコロを押すとその場で出題が始まる",
       tapped["screen"] == "quiz" and tapped["qs"] > 0, json.dumps(tapped, ensure_ascii=False))

    # ---------- 一言欄 ----------
    tips = pg.evaluate("window.Half2Impl.HOME_TIPS")
    byid = {x["id"]: x for x in tips}
    ok("一言欄は34件のまま", len(tips) == 34, str(len(tips)))
    ok("ポモドーロ①にタイトルが付いた", byid["t23"]["title"] == "持続可能な勉強法",
       json.dumps(byid["t23"], ensure_ascii=False))
    ok("ポモドーロ②にタイトルが付いた", byid["t24"]["title"] == "こまめな休憩", byid["t24"]["title"])
    ok("ポモドーロ③にタイトルが付いた", byid["t25"]["title"] == "寝落ちしないように！", byid["t25"]["title"])
    ok("ポモドーロ③の本文が「ベッド・スマホは×」になった",
       "ベッド・スマホは×" in byid["t25"]["body"] and "熟睡" not in byid["t25"]["body"],
       byid["t25"]["body"])
    ok("ポモドーロ④にタイトルが付いた", byid["t26"]["title"] == "邪魔だと思ったら…。", byid["t26"]["title"])
    ok("t30 のタイトルが「問題は自分で足せる」", byid["t30"]["title"] == "問題は自分で足せる",
       byid["t30"]["title"])
    ok("t31 が「とある医療系の国家試験」になった",
       "とある医療系の国家試験" in byid["t31"]["body"] and "臨床検査技師" not in byid["t31"]["body"],
       byid["t31"]["body"])
    ok("t32 にタイトルが付き、本文が「製作に至りました」",
       byid["t32"]["title"] == "製作の意図" and "製作に至りました" in byid["t32"]["body"],
       json.dumps(byid["t32"], ensure_ascii=False))
    ok("t33 にタイトルが付いた", byid["t33"]["title"] == "無駄の無い設計です", byid["t33"]["title"])
    ok("マスターに「※力試しモードでは出現します」を戻していない",
       "力試しモードでは出現します" not in byid["t08"]["body"], byid["t08"]["body"])
    ok("ガイドの誤字「言葉をなどを」を戻していない",
       "言葉をなどを" not in pg.evaluate("window.Half2Impl.TIPS.search.text"),
       pg.evaluate("window.Half2Impl.TIPS.search.text"))

    ok("ページ例外なし", not errs, " | ".join(errs[:3]))
    br.close()

fails = [r for r in R if not r[0]]
print("\n".join(("  ok  " if c else "  NG  ") + n + (("   << " + d) if (d and not c) else "")
                for c, n, d in R))
print("\n%d 項目中 %d 通過 / %d 失敗" % (len(R), len(R) - len(fails), len(fails)))
sys.exit(1 if fails else 0)
