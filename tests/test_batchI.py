#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチI 検証：ポモドーロの持ち越し ／ 一言欄の[前へ]と高さ固定 ／ 文言の自己編集"""
import json, os, sys, subprocess, glob
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

# 版はこの先も上がる。バッチIの内容が入っている下限だけを見る。
def _ver(name): return tuple(int(x) for x in name.split("_V")[-1].replace(".js", "").split("."))
ok("part1 は V1.16 以降", _ver(P1) >= (1, 16), P1)
ok("part2 は V1.13 以降", _ver(P2) >= (1, 13), P2)
sw = open(os.path.join(APP, "sw.js"), encoding="utf-8").read()
idx = open(os.path.join(APP, "index.html"), encoding="utf-8").read()
import re as _re
_c = _re.search(r"CACHE_NAME = 'v(\d+)\.(\d+)\.(\d+)'", sw)
ok("sw CACHE_NAME が v1.7.0 以降",
   bool(_c) and tuple(int(x) for x in _c.groups()) >= (1, 7, 0),
   _c.group(0) if _c else "not found")
ok("sw CORE_ASSETS が両方追随", P1 in sw and P2 in sw)
ok("index の script/REQUIRED が両方追随", idx.count(P1) == 2 and idx.count(P2) == 2)
ok("旧ファイル名が残っていない",
   len(set(_re.findall(r"main_part1_V\d+\.\d+\.js", idx + sw))) == 1 and
   len(set(_re.findall(r"main_part2_V\d+\.\d+\.js", idx + sw))) == 1)

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
    pg.wait_for_timeout(600)
    pg.evaluate("window.Main.go('home')")
    pg.wait_for_timeout(500)

    # ---------- 1. 一言欄：高さ固定 ----------
    hs = pg.evaluate("""async () => {
      const H=window.Half2Impl, S=window.Storage, el=document.getElementById('home-tip');
      const out=[];
      for (let i=0;i<H.HOME_TIPS.length;i++){
        await S.setMeta('home_tip_index', i); await H.renderHomeTips();
        out.push(Math.round(el.getBoundingClientRect().height)); }
      return out; }""")
    ok("34件すべて同じ高さ（画面が跳ねない）", len(set(hs)) == 1,
       "min=%s max=%s spread=%s" % (min(hs), max(hs), max(hs) - min(hs)))
    ok("高さは0ではない（実測値が入っている）", min(hs) > 100, str(min(hs)))
    ok("高さは min-height で指定されている",
       pg.evaluate("!!document.getElementById('home-tip').style.minHeight"),
       pg.evaluate("document.getElementById('home-tip').style.minHeight"))

    # 幅が変わったら測り直す
    pg.set_viewport_size({"width": 320, "height": 844})
    pg.wait_for_timeout(300)
    h320 = pg.evaluate("""async () => {
      const H=window.Half2Impl, S=window.Storage, el=document.getElementById('home-tip');
      H.fixHomeTipHeight(true);
      const out=[];
      for (let i=0;i<H.HOME_TIPS.length;i++){
        await S.setMeta('home_tip_index', i); await H.renderHomeTips();
        out.push(Math.round(el.getBoundingClientRect().height)); }
      return out; }""")
    ok("320px幅でも34件すべて同じ高さ", len(set(h320)) == 1,
       "min=%s max=%s" % (min(h320), max(h320)))
    ok("狭い画面のほうが高い（測り直しが効いている）", min(h320) >= min(hs),
       "320px=%s / 390px=%s" % (min(h320), min(hs)))
    pg.set_viewport_size({"width": 390, "height": 844})
    pg.wait_for_timeout(300)
    pg.evaluate("window.Half2Impl.fixHomeTipHeight(true)")

    # ---------- 2. 一言欄：前へ ----------
    ok("[前へ]ボタンが画面にある", pg.evaluate("!!document.getElementById('home-tip-prev')"))
    seq = pg.evaluate("""async () => {
      const H=window.Half2Impl, S=window.Storage, c=()=>document.getElementById('home-tip-count').textContent;
      await S.setMeta('home_tip_index', 0); await H.renderHomeTips();
      const a=c(); await H.retreatHomeTip();
      const b=c(); await H.advanceHomeTip();
      const d=c(); await H.advanceHomeTip();
      const e=c(); await H.retreatHomeTip();
      return [a,b,d,e,c()]; }""")
    ok("1件目で[前へ]を押すと末尾（34）へ回る", seq[1] == "34 / 34", json.dumps(seq))
    ok("そこから[次の話]で1件目へ戻る", seq[2] == "1 / 34", json.dumps(seq))
    ok("[次の話]は2件目へ進む", seq[3] == "2 / 34", json.dumps(seq))
    ok("[前へ]は1件目へ戻る", seq[4] == "1 / 34", json.dumps(seq))
    pg.click("#home-tip-prev")
    pg.wait_for_timeout(400)
    ok("実際にタップしても戻る",
       pg.evaluate("document.getElementById('home-tip-count').textContent") == "34 / 34",
       pg.evaluate("document.getElementById('home-tip-count').textContent"))

    # ---------- 3. 文言の編集 ----------
    cat = pg.evaluate("""async () => {
      const H=window.Half2Impl; await H.loadTextOverrides();
      const c = H.textCatalog();
      const ids = c.map(r=>r.id);
      return { n: c.length, uniq: new Set(ids).size,
               tips: c.filter(r=>r.group==='一言欄').length,
               guides: c.filter(r=>r.group==='ガイド').length,
               hasT01: ids.indexOf('t01.body')>=0,
               hasGuide: ids.indexOf('g.next.text')>=0,
               emptyDef: c.filter(r=>r.def==='').length }; }""")
    ok("編集できる文の一覧が作れる", cat["n"] > 100, json.dumps(cat, ensure_ascii=False))
    ok("idに重複が無い（別の項目に化けない）", cat["n"] == cat["uniq"], json.dumps(cat))
    ok("一言欄は34件×3項目＝102件", cat["tips"] == 102, str(cat["tips"]))
    ok("ガイドも一覧に入っている", cat["guides"] > 0 and cat["hasGuide"], json.dumps(cat))
    ok("一言欄のidが安定キーになっている", cat["hasT01"])

    ovr = pg.evaluate("""async () => {
      const H=window.Half2Impl, S=window.Storage;
      const def = H.textCatalog().find(r=>r.id==='t01.body').def;
      await H.setOverride('t01.body', 'テスト用に書き換えた本文', def);
      await S.setMeta('home_tip_index', 0);
      await H.renderHomeTips();
      const shown = document.getElementById('home-tip-body').textContent;
      const saved = await S.getMeta('text_overrides', {});
      return { shown, savedText: saved['t01.body'] && saved['t01.body'].text,
               savedBase: saved['t01.body'] && saved['t01.body'].base === def,
               ovDirect: H.ov('t01.body', def) }; }""")
    ok("書き換えた文が一言欄に出る", ovr["shown"] == "テスト用に書き換えた本文", json.dumps(ovr, ensure_ascii=False))
    ok("書き換えは meta の text_overrides に保存される",
       ovr["savedText"] == "テスト用に書き換えた本文", json.dumps(ovr, ensure_ascii=False))
    ok("元の文も一緒に保存される（更新検知のため）", ovr["savedBase"], json.dumps(ovr))

    stale = pg.evaluate("""() => {
      const H=window.Half2Impl;
      return { same: H.ovStale('t01.body', H.textCatalog().find(r=>r.id==='t01.body').def),
               changed: H.ovStale('t01.body', 'アプリ更新で変わった元の文') }; }""")
    ok("元の文が同じうちは「元が更新」にならない", not stale["same"], json.dumps(stale))
    ok("元の文が変わったら「元が更新」を検知する", stale["changed"], json.dumps(stale))

    ui = pg.evaluate("""async () => {
      const H=window.Half2Impl;
      await H.openTextEditor();
      const rows = document.querySelectorAll('#text-list .text-row').length;
      const edited = document.querySelectorAll('#text-list .text-row.is-edited').length;
      H.textUi.filter = 'edited'; await H.renderTextList();
      const onlyEdited = document.querySelectorAll('#text-list .text-row').length;
      H.textUi.filter = 'guide'; await H.renderTextList();
      const onlyGuide = document.querySelectorAll('#text-list .text-row').length;
      H.textUi.filter = 'all'; H.textUi.q = 'ポモドーロ'; await H.renderTextList();
      const searched = document.querySelectorAll('#text-list .text-row').length;
      H.textUi.q = ''; await H.renderTextList();
      return { screen: window.Main.state.screen, rows, edited, onlyEdited, onlyGuide, searched }; }""")
    ok("設定から編集画面へ入れる", ui["screen"] == "text", json.dumps(ui))
    ok("一覧に全項目が並ぶ", ui["rows"] == cat["n"], json.dumps(ui))
    ok("書き換えた項目に印が付く", ui["edited"] == 1, json.dumps(ui))
    ok("「直したものだけ」で絞れる", ui["onlyEdited"] == 1, json.dumps(ui))
    ok("「ガイド」で絞れる", ui["onlyGuide"] == cat["guides"], json.dumps(ui))
    ok("言葉で絞り込める", 0 < ui["searched"] < cat["n"], json.dumps(ui))

    modal = pg.evaluate("""async () => {
      const H=window.Half2Impl;
      await H.openTextItem('t01.body');
      return { open: !document.getElementById('modal-text-edit').hidden,
               value: document.getElementById('text-edit-area').value,
               def: document.getElementById('text-edit-default').textContent.slice(0,12),
               where: document.getElementById('text-edit-where').textContent }; }""")
    ok("編集モーダルが開く", modal["open"], json.dumps(modal, ensure_ascii=False))
    ok("いまの文が入力欄に入っている", modal["value"] == "テスト用に書き換えた本文", modal["value"])
    ok("元の文も読める", len(modal["def"]) > 0, modal["def"])
    ok("どの項目かがモーダルに出ている", "t01.body" in modal["where"], modal["where"])

    save = pg.evaluate("""async () => {
      const H=window.Half2Impl, S=window.Storage;
      await H.openTextItem('t01.body');
      document.getElementById('text-edit-area').value = 'モーダルから保存した本文';
      await H.saveTextItem();
      await S.setMeta('home_tip_index', 0); await H.renderHomeTips();
      return { shown: document.getElementById('home-tip-body').textContent,
               closed: document.getElementById('modal-text-edit').hidden }; }""")
    ok("モーダルから保存すると画面に反映される",
       save["shown"] == "モーダルから保存した本文", json.dumps(save, ensure_ascii=False))
    ok("保存するとモーダルが閉じる", save["closed"], json.dumps(save))

    rev = pg.evaluate("""async () => {
      const H=window.Half2Impl, S=window.Storage;
      await H.openTextItem('t01.body');
      await H.revertTextItem();
      await S.setMeta('home_tip_index', 0); await H.renderHomeTips();
      const def = H.textCatalog().find(r=>r.id==='t01.body').def;
      const saved = await S.getMeta('text_overrides', {});
      return { back: document.getElementById('home-tip-body').textContent === def,
               gone: !saved['t01.body'] }; }""")
    ok("[元に戻す]で既定文へ戻る", rev["back"], json.dumps(rev))
    ok("戻したら保存からも消える", rev["gone"], json.dumps(rev))

    same = pg.evaluate("""async () => {
      const H=window.Half2Impl, S=window.Storage;
      const def = H.textCatalog().find(r=>r.id==='t03.body').def;
      await H.setOverride('t03.body', def, def);
      const saved = await S.getMeta('text_overrides', {});
      return !saved['t03.body']; }""")
    ok("既定文と同じ内容で保存しても、書き換え扱いにしない", same)

    pack = pg.evaluate("""async () => {
      const H=window.Half2Impl;
      const def2 = H.textCatalog().find(r=>r.id==='t02.body').def;
      await H.setOverride('t02.body', '書き出し確認用', def2);
      const p = H.buildTextPack();
      const item = p.items['t02.body'];
      return { schema: p.schema, n: Object.keys(p.items).length,
               text: item.text, original: item.original === def2,
               where: item.where }; }""")
    ok("書き出しパックの形式が正しい", pack["schema"] == "nurse_text_pack_v1", json.dumps(pack, ensure_ascii=False))
    ok("書き出しに全項目が入る", pack["n"] == cat["n"], json.dumps(pack))
    ok("書き出しに「いまの文」が入る", pack["text"] == "書き出し確認用", pack["text"])
    ok("書き出しに「元の文」も並ぶ（何を変えたか分かる）", pack["original"], json.dumps(pack))
    ok("書き出しに場所の説明が入る", "／" in pack["where"], pack["where"])

    imp = pg.evaluate("""async () => {
      const H=window.Half2Impl, S=window.Storage;
      const p = H.buildTextPack();
      p.items['t04.body'].text = '取り込みで差し替えた本文';
      p.items['zzz.unknown'] = { text:'知らないID' };
      const r = await H.importTextPack(JSON.stringify(p));
      await S.setMeta('home_tip_index', 3); await H.renderHomeTips();
      const saved = await S.getMeta('text_overrides', {});
      return { r, shown: document.getElementById('home-tip-body').textContent,
               unknownSaved: !!saved['zzz.unknown'] }; }""")
    ok("JSONを取り込むと反映される",
       imp["shown"] == "取り込みで差し替えた本文", json.dumps(imp, ensure_ascii=False))
    ok("知らないIDは無視する（数だけ報告）",
       imp["r"]["unknown"] == 1 and not imp["unknownSaved"], json.dumps(imp))
    ok("元の文のままの項目は書き換え扱いにしない",
       imp["r"]["same"] > 100, json.dumps(imp["r"]))

    bad = pg.evaluate("""async () => {
      const H=window.Half2Impl;
      const a = await H.importTextPack('これはJSONではありません');
      const b = await H.importTextPack('{"schema":"x"}');
      return { a: a === null, b: b === null }; }""")
    ok("JSONでないものを取り込んでも壊れない", bad["a"], json.dumps(bad))
    ok("items が無いJSONも弾く", bad["b"], json.dumps(bad))

    resetall = pg.evaluate("""async () => {
      const H=window.Half2Impl, S=window.Storage;
      await H.resetAllText();
      const saved = await S.getMeta('text_overrides', {});
      await S.setMeta('home_tip_index', 0); await H.renderHomeTips();
      const def = H.textCatalog().find(r=>r.id==='t01.body').def;
      return { empty: Object.keys(saved).length === 0,
               back: document.getElementById('home-tip-body').textContent === def }; }""")
    ok("[すべて元に戻す]で書き換えが全部消える", resetall["empty"], json.dumps(resetall))
    ok("戻したあと画面も既定文に戻る", resetall["back"], json.dumps(resetall))

    inbk = pg.evaluate("""async () => {
      const H=window.Half2Impl, S=window.Storage;
      const def = H.textCatalog().find(r=>r.id==='t05.body').def;
      await H.setOverride('t05.body', 'バックアップ確認用', def);
      const bk = await S.exportBackup();
      const m = bk.stores.meta.filter(x => x.key === 'text_overrides')[0];
      await H.resetAllText();
      return { inBackup: !!(m && m.value && m.value['t05.body']) }; }""")
    ok("書き換えた文はバックアップに含まれる（新ストアを増やしていない）",
       inbk["inBackup"], json.dumps(inbk))

    guide = pg.evaluate("""async () => {
      const H=window.Half2Impl;
      const def = H.TIPS.next.text;
      await H.setOverride('g.next.text', 'ガイドを自分の言葉に直した', def);
      await window.Storage.setMeta('tips_seen', []);
      H.dismissTip();
      const shown = H.ov('g.next.text', def);
      await H.clearOverride('g.next.text');
      return shown; }""")
    ok("ガイド文も書き換えられる", guide == "ガイドを自分の言葉に直した", str(guide))

    # ---------- 4. ポモドーロ ----------
    pomo = pg.evaluate("""async () => {
      const M=window.Main, out={};
      const p = () => M.state.pomodoro;
      M.state.session.mode = 'random';
      p().startedAt = 0; p().running = false; p().lastActiveAt = 0;
      M.startPomodoro();
      out.startA = p().startedAt;
      await new Promise(r=>setTimeout(r,1200));
      M.markPomodoroActivity();
      M.endSession();
      out.runningAfterEnd = p().running;
      M.state.session.mode = 'review';
      M.startPomodoro();
      out.startB = p().startedAt;
      return out; }""")
    ok("モードが終わってもタイマーは止まらない", pomo["runningAfterEnd"], json.dumps(pomo))
    ok("次のモードを始めても 25:00 へ巻き戻らない（V1.18の不具合）",
       pomo["startA"] == pomo["startB"], json.dumps(pomo))

    idle = pg.evaluate("""() => {
      const M=window.Main, p=M.state.pomodoro, out={};
      const MIN=60000;
      p.startedAt = Date.now() - 3*MIN; p.running = true;
      M.state.session.mode = null;
      p.lastActiveAt = Date.now() - 4*MIN;  out.home4 = M.pomodoroIsFresh();
      p.lastActiveAt = Date.now() - 6*MIN;  out.home6 = M.pomodoroIsFresh();
      M.state.session.mode = 'review';
      p.lastActiveAt = Date.now() - 6*MIN;  out.quiz6 = M.pomodoroIsFresh();
      p.lastActiveAt = Date.now() - 26*MIN; out.quiz26 = M.pomodoroIsFresh();
      p.startedAt = 0;                      out.noStart = M.pomodoroIsFresh();
      return out; }""")
    ok("ホームで4分の無操作なら続き扱い", idle["home4"], json.dumps(idle))
    ok("ホームで6分の無操作なら切り直す", not idle["home6"], json.dumps(idle))
    ok("出題中の6分は続き扱い（1問を長く考えることがある）", idle["quiz6"], json.dumps(idle))
    ok("出題中でも26分の無操作は切り直す", not idle["quiz26"], json.dumps(idle))
    ok("開始していなければ続きではない", not idle["noStart"], json.dumps(idle))

    persist = pg.evaluate("""async () => {
      const M=window.Main, S=window.Storage;
      M.state.session.mode = 'random';
      M.state.pomodoro.startedAt = 0; M.state.pomodoro.running = false;
      M.startPomodoro();
      await M.savePomodoroState();
      const a = await S.getMeta('pomo_started_at', 0);
      const b = await S.getMeta('pomo_last_active', 0);
      return { saved: a > 0 && b > 0, matches: a === M.state.pomodoro.startedAt }; }""")
    ok("経過時刻が保存される（開き直しても続きから）", persist["saved"], json.dumps(persist))
    ok("保存された開始時刻が実際の値と一致する", persist["matches"], json.dumps(persist))

    ok("ページ例外なし", not errs, " | ".join(errs[:3]))
    br.close()

fails = [r for r in R if not r[0]]
print("\n".join(("  ok  " if c else "  NG  ") + n + (("   << " + d) if (d and not c) else "")
                for c, n, d in R))
print("\n%d 項目中 %d 通過 / %d 失敗" % (len(R), len(R) - len(fails), len(fails)))
sys.exit(1 if fails else 0)
