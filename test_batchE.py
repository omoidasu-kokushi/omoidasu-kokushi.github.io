#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチE 検証スイート"""
import json, re, io, os, sys, subprocess, glob
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))
def read(f): return io.open(os.path.join(APP, f), encoding="utf-8").read()

P1 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
P2 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])

# ------------------------------------------------------------------ 静的
for f in ["storage.js", "scheduler.js", P1, P2, "sw.js"]:
    p = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True)
    ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

idx, st = read("index.html"), read("storage.js")
ok("storage：importText から trim() を撤去",
   ".replace(/^\\uFEFF/, '').trim()" not in st and "if (!/\\S/.test(raw))" in st)
ok("設定3の見出しが「ポモドーロ勉強法」", "3. ポモドーロ勉強法" in idx and "3. ポモドーロタイマー" not in idx)
ok("スイッチ文言が指定どおり", "ポモドーロ機能(タイマー)を使う(25分)" in idx)
ok("短い休憩は5分固定と明記", "5分（固定）" in idx)
ok("ヘッダーに専用トグルがある", 'id="pomodoro-toggle"' in idx)
# 記号を「使わない」ことの検証。コメント内の言及は許すが、
# 画面に出る文字列（HTMLの初期値と textContent の代入）に混ざっていないことを見る。
# V1.44：ラベル（⏲タイマー）を消さないよう、状態の span だけを書き換える。
# textContent を丸ごと入れ替えると、HTMLに置いた文字も一緒に消える。
ok("トグルは ⏸/▶ の絵文字グリフを使わない（環境差を避ける）",
   "⏸" not in idx and "OFF</button>" not in idx
   and "setText('#pomodoro-toggle .pomo-toggle-state', p.enabled ? 'ON' : 'OFF');" in read(P1))
# V1.39：13列TSVに合わせて col13 が増えたので10個（アプリ側が正）
ok("列ごとの[？]は10個", idx.count('class="help-btn help-col"') == 10, str(idx.count('class="help-btn help-col"')))
for c in [1, 2, 3, 4, 5, 6, 7, 9, 12, 13]:
    ok("col%d の[？]がある" % c, 'data-help="col%d"' % c in idx)
for c in [8, 10, 11]:
    ok("col%d には[？]を置かない" % c, 'data-help="col%d"' % c not in idx)
ok("8/10/11は説明を省く旨を明記", "8・10・11（問題文／正解／解説）は説明を省いています" in idx)
ok("実シートのモック表がある", 'class="sheet-mock"' in idx and "<th>1</th>" in idx)
ok("テンプレートの案内がある", "20260816_TSV_Template_V1.00.xlsx" in idx)
ok("テンプレート xlsx が同梱されている",
   os.path.exists(os.path.join(APP, "sample", "20260816_TSV_Template_V1.00.xlsx")))
ok("テンプレート txt が同梱されている",
   os.path.exists(os.path.join(APP, "sample", "20260816_TSV_Template_V1.00.txt")))

# ------------------------------------------------------------------ 実行時
TPL = io.open(os.path.join(APP, "sample", "20260816_TSV_Template_V1.00.txt"), encoding="utf-8").read()

def _external(t):
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t)

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" and not _external(m.text) else None)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=15000)
    pg.wait_for_timeout(2200)
    pg.click("#welcome-start"); pg.wait_for_timeout(700)

    # ---- 取り込み不具合の本命
    ROW = ["必修問題","目標Ⅰ","S","1. 健康に関する指標","A. 人口静態・人口動態","a. 総人口","single",
           "確認用の問題文A",'["あ","い","う","え"]',"[1]",
           '<span class="bg-yellow-200">① 誤り</span>：x。<span class="bg-yellow-200">② 正解</span>：y。'
           '<span class="bg-yellow-200">③ 誤り</span>：z。<span class="bg-yellow-200">④ 誤り</span>：w。',
           '[["#人口動態統計"],["#人口動態統計"],["#人口動態統計"],["#人口動態統計"]]']
    def row(mod):
        c = list(ROW)
        for k, v in mod.items(): c[k] = v
        return "\t".join(c)

    r1 = pg.evaluate("""async (t) => { const rep = await window.Storage.importText(t);
        return { got: rep.imported + rep.updated, skipped: rep.skipped,
                 err: (rep.errors[0]||{}).message || null }; }""",
        row({11: "", 7: "タグ空・単独行"}))
    ok("最後の行のタグ列が空でも取り込める（旧：必ずスキップ）",
       r1["got"] == 1 and r1["skipped"] == 0, json.dumps(r1, ensure_ascii=False))

    r2 = pg.evaluate("""async (t) => { const rep = await window.Storage.importText(t);
        return { got: rep.imported + rep.updated, skipped: rep.skipped }; }""",
        row({11: "", 7: "タグ空・2行目"}) + "\n" + row({11: "", 7: "タグ空・3行目"}))
    ok("複数行すべてタグ空でも全部取り込める", r2["got"] == 2 and r2["skipped"] == 0, json.dumps(r2))

    r3 = pg.evaluate("""async (t) => { const rep = await window.Storage.importText(t);
        return { skipped: rep.skipped, err: (rep.errors[0]||{}).message || null }; }""",
        row({0: "", 7: "単元空"}))
    ok("1列目が空なら「列数」ではなく「単元が空」と言う",
       r3["skipped"] == 1 and r3["err"] and "単元" in r3["err"], json.dumps(r3, ensure_ascii=False))

    r4 = pg.evaluate("""async (t) => { const rep = await window.Storage.importText(t);
        return { got: rep.imported + rep.updated }; }""",
        "\n\n" + row({7: "前後に改行"}) + "\n\n")
    ok("前後に空行があっても取り込める", r4["got"] == 1, json.dumps(r4))

    rj = pg.evaluate("""async () => {
        const bk = await window.Storage.exportBackup();
        const rep = await window.Storage.importText('\\n  ' + JSON.stringify(bk) + '\\n');
        return { ok: !!rep && (rep.questions > 0 || rep.mode === 'merge'), mode: rep.mode || null }; }""")
    ok("先頭に空白・改行があるJSONも復元として認識する", rj["ok"], json.dumps(rj, ensure_ascii=False))

    rt = pg.evaluate("""async (t) => { const rep = await window.Storage.importText(t);
        return { got: rep.imported + rep.updated, skipped: rep.skipped,
                 err: (rep.errors[0]||{}).message || null, msg: rep.messages }; }""", TPL)
    ok("同梱テンプレートがそのまま取り込める（見出し行を含めて）",
       rt["got"] == 2 and rt["skipped"] == 0, json.dumps(rt, ensure_ascii=False))
    ok("テンプレートの見出し行は自動で読み飛ばされる",
       any("ヘッダー行" in m for m in rt["msg"]), json.dumps(rt["msg"], ensure_ascii=False))

    # ---- 列ごとの[？]
    pg.evaluate("window.Half2Impl.openSettings()"); pg.wait_for_timeout(700)
    ok("HELP_COLS は10件", pg.evaluate("Object.keys(window.Half2Impl.HELP_COLS).length") == 10)
    c3 = pg.evaluate("""async () => { await window.Half2Impl.openHelp('col3');
        return { t: document.getElementById('help-title').textContent,
                 b: document.getElementById('help-body').textContent }; }""")
    ok("col3 はランクの説明", "ランク" in c3["t"], c3["t"])
    ok("col3 に S/A/B/C と重みが書いてある",
       "×2.5" in c3["b"] and "×0.3" in c3["b"], c3["b"][:120])
    ok("col3 に「分からなければ空でOK」がある", "空でOK" in c3["b"])
    c7 = pg.evaluate("""async () => { await window.Half2Impl.openHelp('col7');
        return document.getElementById('help-body').textContent; }""")
    ok("col7（形式）も空でOKと書いてある", "空でOK" in c7 and "single" in c7)
    c10 = pg.evaluate("!!window.Half2Impl.HELP_COLS.col10 || !!window.Half2Impl.HELP.col10")
    ok("col10（正解）の説明は用意していない", not c10)
    pg.evaluate("window.Main.closeModals()")

    # ---- Level欄の数字
    pg.evaluate("window.Main.go('home',{replace:true})"); pg.wait_for_timeout(500)
    pg.evaluate("window.Main.refreshHome()"); pg.wait_for_timeout(600)
    lv = pg.evaluate("""() => {
        const q = s => document.querySelector(s);
        const cs = e => { const c = getComputedStyle(e); return [parseFloat(c.fontSize), c.fontWeight]; };
        const chip = q('.level-chip'), facts = q('.level-facts'), pct = q('.level-pct');
        const cn = q('.level-chip .lv-n'), fn = q('.level-facts .lv-n'), pn = q('.level-pct .lv-n');
        return { chipHtml: chip.innerHTML, factsHtml: facts.innerHTML,
                 chip: cs(chip), chipN: cn ? cs(cn) : null,
                 facts: cs(facts), factsN: fn ? cs(fn) : null,
                 pct: cs(pct), pctN: pn ? cs(pn) : null,
                 nCount: document.querySelectorAll('.level-strip .lv-n').length }; }""")
    ok("Level欄の数字が <b class=\"lv-n\"> で包まれている", lv["nCount"] >= 3, str(lv["nCount"]))
    ok("Level の数字が地の文より1px大きい",
       lv["chipN"] and abs((lv["chipN"][0] - lv["chip"][0]) - 1.0) < 0.05,
       "%s vs %s" % (lv["chipN"], lv["chip"]))
    ok("%の数字が1px大きい（14 → 15px）",
       lv["pctN"] and abs((lv["pctN"][0] - lv["pct"][0]) - 1.0) < 0.05,
       "%s vs %s" % (lv["pctN"], lv["pct"]))
    ok("1行目の数字が1px大きい（10.88 → 11.88px）",
       lv["factsN"] and abs((lv["factsN"][0] - lv["facts"][0]) - 1.0) < 0.05,
       "%s vs %s" % (lv["factsN"], lv["facts"]))
    ok("数字はすべて太字800",
       all(x and x[1] == "800" for x in [lv["chipN"], lv["factsN"], lv["pctN"]]),
       str([lv["chipN"], lv["factsN"], lv["pctN"]]))
    ok("HTMLを入れる経路でもエスケープされている（< が生で出ない）",
       "<script" not in lv["factsHtml"] and "&lt;" not in lv["chipHtml"])

    # ---- 使い方カード：タイトル重複の解消
    tips = pg.evaluate("window.Half2Impl.HOME_TIPS")
    numbered = [t for t in tips if t["label"][-1] in "①②③④"]
    ok("番号をラベル側に持つカードが14件（F で設定④を削除）", len(numbered) == 14, str(len(numbered)))
    # V1.20：利用者が忘却曲線①〜④にタイトルを付けた。空であることは不変条件ではない。
    # 守るべきは「ラベルと同じ文字列を太字でもう一度出さない」ほう。
    ok("番号付きカードのタイトルがラベルの焼き直しになっていない",
       not [t for t in numbered if t["title"] and t["title"] in t["label"]],
       str([t["title"] for t in numbered if t["title"] and t["title"] in t["label"]]))
    ok("ラベルとタイトルが重複するカードは0件",
       not [t for t in tips if t["title"] and t["title"] in t["label"]],
       str([t["title"] for t in tips if t["title"] and t["title"] in t["label"]]))
    ok("番号を持たないカードは全件タイトルを持つ",
       all(t["title"] for t in tips if t["label"][-1] not in "①②③④"),
       str([t["label"] for t in tips if t["label"][-1] not in "①②③④" and not t["title"]]))
    shown = pg.evaluate("""async () => {
        const i = window.Half2Impl.HOME_TIPS.findIndex(t => !t.title);
        await window.Storage.setMeta('home_tip_index', i);
        await window.Half2Impl.renderHomeTips();
        return { label: document.getElementById('home-tip-label').textContent,
                 titleHidden: document.getElementById('home-tip-title').hidden,
                 body: document.getElementById('home-tip-body').textContent.slice(0, 20) }; }""")
    ok("タイトルが空のカードは大きい太字の行を出さない", shown["titleHidden"], json.dumps(shown, ensure_ascii=False))
    ok("ラベルに番号が入っている", shown["label"][-1] in "①②③④", shown["label"])
    shown2 = pg.evaluate("""async () => {
        const i = window.Half2Impl.HOME_TIPS.findIndex(t => !!t.title);
        await window.Storage.setMeta('home_tip_index', i);
        await window.Half2Impl.renderHomeTips();
        return document.getElementById('home-tip-title').hidden; }""")
    ok("タイトルがあるカードでは出す", shown2 is False, str(shown2))

    # ---- ヘッダーのポモドーロトグル
    pg.evaluate("""async () => {
        await window.Storage.setMeta('pomodoro_enabled', true);
        window.Main.state.pomodoro.enabled = true;
        await window.Main.startSession({ mode:'random', count:3, applyGuard:false, newOnly:false }); }""")
    pg.wait_for_timeout(1600)
    ok("出題中はトグルが見える", pg.evaluate("!document.getElementById('pomodoro-toggle').hidden"))
    # V1.44：ONの横に「⏲タイマー」の文字が並ぶので、状態は span で見る。
    ok("ON中は ON と出る",
       pg.evaluate("document.querySelector('#pomodoro-toggle .pomo-toggle-state').textContent") == "ON")
    ok("ONの横に「タイマー」の文字がある",
       "タイマー" in pg.evaluate("document.querySelector('#pomodoro-toggle .pomo-toggle-text').textContent"))
    pg.evaluate("document.getElementById('pomodoro-toggle').click()")
    pg.wait_for_timeout(700)
    offst = pg.evaluate("""() => ({
        state: document.querySelector('#pomodoro-toggle .pomo-toggle-state').textContent,
        label: document.getElementById('pomodoro-toggle').textContent,
        pressed: document.getElementById('pomodoro-toggle').getAttribute('aria-pressed'),
        chipShown: !document.getElementById('pomodoro-chip').hidden,
        chipOff: document.getElementById('pomodoro-chip').classList.contains('is-off'),
        time: document.getElementById('pomodoro-time').textContent,
        running: window.Main.state.pomodoro.running,
        enabled: window.Main.state.pomodoro.enabled })""")
    ok("1タップでOFFになる", offst["enabled"] is False and offst["running"] is False, json.dumps(offst))
    ok("OFF中は OFF になる", offst["state"] == "OFF" and offst["pressed"] == "false", json.dumps(offst))
    ok("OFFにしてもラベルは消えない", "タイマー" in offst["label"], json.dumps(offst["label"]))
    ok("OFF中もチップは薄く残る（ONに戻す入口が消えない）",
       offst["chipShown"] and offst["chipOff"], json.dumps(offst))
    ok("OFF中の時間は --:--（0:00と誤読させない）", offst["time"] == "--:--", offst["time"])
    ok("OFFはmetaにも保存される",
       pg.evaluate("async () => await window.Storage.getMeta('pomodoro_enabled')") is False)
    pg.evaluate("document.getElementById('pomodoro-toggle').click()")
    pg.wait_for_timeout(700)
    onst = pg.evaluate("""() => ({
        label: document.querySelector('#pomodoro-toggle .pomo-toggle-state').textContent,
        running: window.Main.state.pomodoro.running,
        time: document.getElementById('pomodoro-time').textContent })""")
    ok("もう1タップでONに戻り、計測が再開する",
       onst["label"] == "ON" and onst["running"] is True and onst["time"] != "--:--", json.dumps(onst))
    pg.evaluate("window.Half2Impl.openSettings()"); pg.wait_for_timeout(700)
    ok("設定のスイッチもONに同期している", pg.evaluate("document.getElementById('set-pomodoro').checked"))
    pg.evaluate("document.getElementById('set-pomodoro').click()"); pg.wait_for_timeout(800)
    ok("設定側でOFFにすると state も落ちる（3入口が1本）",
       pg.evaluate("window.Main.state.pomodoro.enabled") is False)
    pg.evaluate("window.Main.go('home',{replace:true})"); pg.wait_for_timeout(400)
    ok("ホームではトグルを出さない", pg.evaluate("document.getElementById('pomodoro-toggle').hidden"))

    ok("ページ例外なし", not errs, " | ".join(errs[:3]))
    pg.screenshot(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "shot_E.png"), full_page=True)
    br.close()

fails = [r for r in R if not r[0]]
print("\n".join(("  ok  " if c else "  NG  ") + n + (("   << " + d) if (d and not c) else "")
                for c, n, d in R))
print("\n%d 項目中 %d 通過 / %d 失敗" % (len(R), len(R) - len(fails), len(fails)))
sys.exit(1 if fails else 0)
