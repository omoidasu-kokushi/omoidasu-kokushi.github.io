#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチA+B 検証スイート（headless Chromium / http://）"""
import json, re, io, os, sys, subprocess
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []

def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()

# ---------------------------------------------------------------- 静的検査
def static_checks():
    import glob as _g
    p1 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
    p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
    for f in ["questions.js", "storage.js", "scheduler.js", p1, p2, "sw.js"]:
        p = subprocess.run(["node", "--check", os.path.join(APP, f)],
                           capture_output=True, text=True)
        ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

    idx, sw = read("index.html"), read("sw.js")
    ok("index：実ファイル名と2箇所（script/REQUIRED）が一致",
       idx.count(p1) == 2 and idx.count(p2) == 2, "%s / %s" % (p1, p2))
    ok("sw：CORE_ASSETS が実ファイル名と一致", p1 in sw and p2 in sw)
    ok("index/sw に他版の part1 が残っていない",
       len(set(re.findall(r"main_part1_V\d+\.\d+\.js", idx + sw))) == 1,
       str(set(re.findall(r"main_part1_V\d+\.\d+\.js", idx + sw))))
    ok("index/sw に他版の part2 が残っていない",
       len(set(re.findall(r"main_part2_V\d+\.\d+\.js", idx + sw))) == 1,
       str(set(re.findall(r"main_part2_V\d+\.\d+\.js", idx + sw))))
    ok("sw CACHE_NAME が上がっている",
       bool(re.search(r"const CACHE_NAME = 'v1\.[1-9]", sw)),
       re.search(r"const CACHE_NAME = '[^']+'", sw).group(0))
    ok("styles.css から cx-tags-inline 全消", "cx-tags-inline" not in read("styles.css"))
    ok("part1 から tagPills/tagSignature 全消",
       "tagPills" not in read(p1) and "tagSignature" not in read(p1))
    ok("part2 から prompt( 全消", "global.prompt" not in read(p2))
    # 実ファイルが CORE_ASSETS に全部あるか
    for a in re.findall(r"'\./([^']+)'", sw.split("CORE_ASSETS")[1].split("]")[0]):
        _p = a.split("?")[0]
        ok("CORE_ASSETS 実在: %s" % a, os.path.exists(os.path.join(APP, _p)))
    # V1.42：共有ファイルは ?v=<版> 付き。index.html と1文字でも違うと
    # キャッシュに当たらず、オフラインで起動できなくなる。
    _swq = dict(re.findall(r"'\./([^'?]+)\?v=([^']+)'", sw))
    _idxq = dict(re.findall(r'"\./([^"?]+)\?v=([^"]+)"', idx))
    for f in ["styles.css", "questions.js", "storage.js", "scheduler.js", "drive.js"]:
        ok("%s に版が付いている" % f, f in _swq and f in _idxq,
           "sw=%s idx=%s" % (_swq.get(f), _idxq.get(f)))
        ok("%s の版が index と sw で一致" % f, _swq.get(f) == _idxq.get(f),
           "sw=%s idx=%s" % (_swq.get(f), _idxq.get(f)))

# ---------------------------------------------------------------- 実行時検査
def _external(t):
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t)


def runtime_checks():
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox"])
        ctx = br.new_context(viewport={"width": 390, "height": 844})
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" and not _external(m.text) else None)
        pg.goto(URL, wait_until="load")
        pg.wait_for_function("window.__APP_READY === true", timeout=15000)
        pg.wait_for_timeout(1800)

        ok("依存モジュール5本すべてOK", pg.evaluate("""() =>
            !!(window.CONCEPT_TAGS_MASTER||[]).length && !!(window.Storage&&window.Storage.APP_BUILD)
            && !!(window.Scheduler&&window.Scheduler.APP_BUILD) && !!(window.Main&&window.Main.APP_BUILD)
            && !!(window.Half2Impl&&window.Half2Impl.openSettings)"""))
        ok("起動診断パネルが出ていない", not pg.evaluate("!!document.getElementById('boot-diagnostics')"))

        # --- 依頼12：初回に概要モーダル
        # V1.42：シードが457問になり、起動直後はスプラッシュが覆っている。
        # 覆いが外れてから見る（見た目の順序を守る）。
        try:
            pg.wait_for_function(
                "document.getElementById('splash').classList.contains('is-gone')",
                timeout=15000)
        except Exception:
            pass
        # シードの取り込みが終わってから出るので、時間ではなく状態で待つ。
        try:
            pg.wait_for_function(
                "!document.getElementById('modal-welcome').hidden", timeout=20000)
        except Exception:
            pass
        ok("初回：概要モーダルが出る",
           pg.evaluate("!document.getElementById('modal-welcome').hidden"))
        ok("概要は3行ちょうど",
           pg.evaluate("document.querySelectorAll('#modal-welcome .welcome-list li').length") == 3)
        pg.click("#welcome-start")
        pg.wait_for_timeout(900)
        ok("[はじめる]で問1へ直行", pg.evaluate("window.Main.state.screen") == "quiz")
        ok("概要モーダルは閉じている",
           pg.evaluate("document.getElementById('modal-welcome').hidden"))

        # --- unionTags 単体
        u = pg.evaluate("""() => window.Main.unionTags([
            {tags:['#A','#B']}, {tags:['#B']}, {tags:['#C','#A']}, {tags:[]}, {} ])""")
        ok("unionTags 重複除去＋順序保持", u == ["#A", "#B", "#C"], str(u))
        ok("unionTags 空入力", pg.evaluate("window.Main.unionTags([]).length") == 0)

        # --- 1問解いて解説画面へ
        pg.wait_for_timeout(700)
        pg.click("#choice-list .choice-card:nth-child(2) .choice-body")
        pg.wait_for_timeout(200)
        pg.click("#btn-confirm")
        pg.wait_for_timeout(900)
        ok("解説フェーズへ遷移",
           pg.get_attribute("#screen-quiz", "data-phase") == "review")

        # --- 依頼11：タグ上部統合
        ok("タグは上部に1行だけ",
           pg.evaluate("document.querySelectorAll('#rv-choices .cx-shared-tags').length") == 1)
        ok("肢別インラインタグは存在しない",
           pg.evaluate("document.querySelectorAll('#rv-choices .cx-tags-inline').length") == 0)
        ok("タグは .cx の外側にある（クリック判定の前提）",
           pg.evaluate("""() => { var t=document.querySelector('#rv-choices .tag-pill');
                                  return !!t && !t.closest('.cx'); }"""))
        # 肢の数はシードの問題によって変わる。肢数×4（難/普/易/マ）で見る。
        _nc = pg.evaluate("document.querySelectorAll('#rv-choices .cx').length")
        ok("評価ボタンは 肢数×4個",
           pg.evaluate("document.querySelectorAll('#rv-choices .eval-btn').length") == _nc * 4,
           "肢=%d ボタン=%d" % (_nc, pg.evaluate("document.querySelectorAll('#rv-choices .eval-btn').length")))

        # --- 依頼8：ガイドがタグ無しでも止まらない
        stall = pg.evaluate("""async () => {
            await window.Storage.setMeta('tips_seen', ['answer','confirm','eval','next']);
            window.Half2Impl.dismissTip();
            // タグを全部消して「対象が画面に無い」状態を作る
            document.querySelectorAll('#rv-choices .tag-pill').forEach(e => e.remove());
            // tipState のキャッシュを捨てさせるため resetTips 相当を経由せず直接呼ぶ
            window.Half2Impl.state.__x = 1;
            return true; }""")
        pg.evaluate("window.Half2Impl.resetTips()")
        pg.wait_for_timeout(300)
        seen_order = pg.evaluate("""async () => {
            await window.Storage.setMeta('tips_seen', ['answer','confirm','eval','next']);
            return true; }""")
        # tipState 内部キャッシュを無効化してから
        pg.evaluate("window.Half2Impl.dismissTip()")
        got = pg.evaluate("""async () => {
            document.querySelectorAll('#rv-choices .tag-pill').forEach(e => e.remove());
            await window.Half2Impl.tipReviewExtra();
            var s = document.getElementById('onb-step');
            return { visible: !document.getElementById('onb-layer').hidden,
                     step: s ? s.textContent : null }; }""")
        ok("タグ0個でもガイドが止まらない（次を出す）",
           got["visible"] and got["step"] and "/6" in got["step"], json.dumps(got, ensure_ascii=False))
        # V1.18（バッチH）で locked を1件追加。画面の上から下への順序は維持。
        ok("REVIEW_EXTRA は7件・上から順",
           pg.evaluate("JSON.stringify(window.Half2Impl.REVIEW_EXTRA)") ==
           '["qstar","tagpill","star","locked","memo","detail","summary"]')
        ok("問題文★のガイドが定義されている",
           pg.evaluate("!!window.Half2Impl.TIPS.qstar && window.Half2Impl.TIPS.qstar.sel === '#rv-star'"))

        # 評価を確定させる（answer_count を増やさないとリセット対象が生まれない）
        pg.evaluate("window.Half2Impl.dismissTip()")
        pg.evaluate("window.Main.nextQuestion()")
        pg.wait_for_timeout(1500)
        learned0 = pg.evaluate("async () => (await window.Storage.getAllAtoms()).filter(a=>a.answer_count>0).length")
        ok("評価コミットで学習済み肢が増える", learned0 > 0, "learned=%s" % learned0)

        # --- 依頼1：日界 0〜23時
        pg.evaluate("window.Half2Impl.dismissTip()")
        pg.evaluate("window.Half2Impl.openSettings()")
        pg.wait_for_timeout(800)
        ok("日界の選択肢が24個", pg.evaluate("document.querySelectorAll('#set-dayline option').length") == 24)
        res = pg.evaluate("""async () => {
            const out = [];
            for (const v of [0, 23, '', 'abc', -1, 24, 4]) {
              await window.Half2Impl.setDayBoundary(v);
              out.push(await window.Storage.getMeta('day_boundary_hour'));
            }
            return out; }""")
        ok("setDayBoundary の境界値（0が4に化けない）",
           res == [0, 23, 4, 4, 4, 4, 4], str(res))

        # --- 依頼2/4：[？]ヘルプ
        # V1.39：設定は9節構成になり、見出しの[？]も増えた（アプリ側が正）
        _nh = pg.evaluate("document.querySelectorAll('#screen-settings .set-head .help-btn').length")
        ok("見出しの[？]が3個以上ある（列ごとの[？]は別枠）", _nh >= 3, str(_nh))
        pg.click('#screen-settings .help-btn[data-help="pomodoro"]')
        pg.wait_for_timeout(400)
        ok("ポモドーロの説明が開く",
           pg.evaluate("!document.getElementById('modal-help').hidden") and
           "25分" in pg.inner_text("#help-body"))
        pg.click("#modal-help [data-close]")
        pg.wait_for_timeout(300)

        ok("取り込み手順の折りたたみがある",
           pg.evaluate("!!document.querySelector('.import-guide')"))
        ok("手順は6ステップ",
           pg.evaluate("document.querySelectorAll('.import-steps > li').length") == 6)
        # V1.39：13列に拡張されたので見出し行＋13行＝14（アプリ側が正）
        _nr = pg.evaluate("document.querySelectorAll('.import-steps table tr').length")
        ok("13列の対応表がある", _nr == 14, str(_nr))
        pg.evaluate("document.querySelector('.import-guide').open = true")
        pg.wait_for_timeout(200)
        ok("0始まりの警告が書いてある", "0 から数えます" in pg.inner_text(".import-guide"))

        # --- 依頼5：中項目リセット2段階
        pg.click("#btn-reset-medium")
        pg.wait_for_timeout(700)
        ok("中項目の一覧が出る", pg.evaluate("!document.getElementById('modal-reset-medium').hidden"))
        rows = pg.evaluate("document.querySelectorAll('#reset-medium-list .medium-row').length")
        ok("中項目が一覧に出ている（%d件）" % rows, rows >= 1)
        ok("学習記録の無い中項目は押せない",
           pg.evaluate("""() => Array.from(document.querySelectorAll('#reset-medium-list .medium-row'))
                          .filter(r => r.classList.contains('is-empty'))
                          .every(r => r.disabled)"""))
        before = pg.evaluate("async () => (await window.Storage.getAllAtoms()).filter(a=>a.answer_count>0).length")
        target = pg.evaluate("""() => { var r = document.querySelector('#reset-medium-list .medium-row:not([disabled])');
                                        return r ? r.getAttribute('data-medium') : null; }""")
        if target:
            pg.click("#reset-medium-list .medium-row:not([disabled])")
            pg.wait_for_timeout(600)
            after1 = pg.evaluate("async () => (await window.Storage.getAllAtoms()).filter(a=>a.answer_count>0).length")
            ok("1タップでは消えない（確認が挟まる）", after1 == before and before > 0,
               "before=%s after=%s" % (before, after1))
            ok("確認に対象名が出る",
               target in pg.inner_text("#reset-medium-confirm-body"))
            pg.click("#reset-medium-go")
            pg.wait_for_timeout(1200)
            after2 = pg.evaluate("async () => (await window.Storage.getAllAtoms()).filter(a=>a.answer_count>0).length")
            ok("[消す]で実際に消える", after2 < before, "before=%s after=%s" % (before, after2))
        else:
            ok("押せる中項目がある", False, "学習済み中項目が見つからない")

        # --- 依頼6：ホーム最下部のカード
        stuck = pg.evaluate("""() => { var l=document.getElementById('modal-layer');
            if (l.hidden) { return null; }
            var m=document.querySelector('#modal-layer > .modal-card:not([hidden])');
            return m ? m.id : '(層だけ開いている)'; }""")
        ok("リセット後にモーダルが残らない", stuck is None, "残存: %s" % stuck)
        pg.evaluate("window.Main.closeModals()")
        pg.evaluate("window.Main.go('home', {replace:true})")
        pg.evaluate("window.Half2Impl.renderHomeTips()")
        pg.wait_for_timeout(400)
        ok("使い方カードが出る", pg.evaluate("!document.getElementById('home-tip').hidden"))
        ok("カードは主動線より下（DOM順）",
           pg.evaluate("""() => { var a=document.getElementById('card-review'),
                                      b=document.getElementById('home-tip');
                       return !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING); }"""))
        ok("カードはツール一覧より下（DOM順）",
           pg.evaluate("""() => { var a=document.querySelector('.tool-list'),
                                      b=document.getElementById('home-tip');
                       return !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING); }"""))
        t1 = pg.inner_text("#home-tip-body")
        pg.click("#home-tip-next")
        pg.wait_for_timeout(500)
        t2 = pg.inner_text("#home-tip-body")
        ok("[次の話]で内容が変わる", t1 != t2 and t2, "%s… -> %s…" % (t1[:14], t2[:14]))
        ok("使い方カードが十分な件数ある", pg.evaluate("window.Half2Impl.HOME_TIPS.length") >= 12)

        # --- 依頼7：Level 2 の文言（getHomeState を差し替えて検証）
        note = pg.evaluate("""async () => {
            const orig = window.Scheduler.getHomeState;
            const base = await orig();
            window.Scheduler.getHomeState = async () => {
              const h = await orig();
              h.level = { level:2, level_name:'数量マイルストーン', display_pct:8, badge:null,
                          stats: Object.assign({}, h.level.stats, { total_answered_questions: 8 }) };
              return h;
            };
            await window.Main.refreshHome();
            const txt = document.getElementById('level-note').textContent;
            window.Scheduler.getHomeState = orig;
            return txt; }""")
        ok("Level2：途方もない数字の羅列が消えた", "300" not in note and "1000" not in note, note)
        ok("Level2：次の1段と残り問数が出る", "92" in note and "100" in note, note)
        # 「学習◯日目」は V1.12 で #level-facts へ分離した（検証は test_batchD.py 側）

        pg.screenshot(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "shot_home_patched.png"), full_page=True)
        ok("ページ例外なし", not errs, " | ".join(errs[:3]))
        br.close()

static_checks()
runtime_checks()

fails = [r for r in R if not r[0]]
print("\n".join(("  ok  " if c else "  NG  ") + n + (("   << " + d) if (d and not c) else "")
                for c, n, d in R))
print("\n%d 項目中 %d 通過 / %d 失敗" % (len(R), len(R) - len(fails), len(fails)))
sys.exit(1 if fails else 0)
