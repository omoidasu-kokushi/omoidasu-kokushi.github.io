#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチD 検証スイート"""
import json, re, io, os, sys, subprocess
from playwright.sync_api import sync_playwright


# 「2つ選べ」の問題が先頭に来ると、1枚押しただけでは確定が押せない。
# 必要な枚数まで押す（V1.98：ランク当てでキューの中身が変わり、実際に踏んだ）。
def fill_choices(pg):
    pg.evaluate("""() => {
      for (const c of document.querySelectorAll('#choice-list .choice-card')) {
        const b = document.getElementById('btn-confirm');
        if (b && !b.disabled) { break; }
        const body = c.querySelector('.choice-body') || c;
        body.click();
      }
    }""")
    pg.wait_for_selector("#btn-confirm:not([disabled])", timeout=10000)


APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))
def read(f): return io.open(os.path.join(APP, f), encoding="utf-8").read()

# ------------------------------------------------------------------ 静的
import glob as _g
P1 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
P2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
for f in ["questions.js", "storage.js", "scheduler.js", P1, P2, "sw.js"]:
    p = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True)
    ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

idx, sw = read("index.html"), read("sw.js")
ok("index：実ファイル名と2箇所が一致", idx.count(P1) == 2 and idx.count(P2) == 2, "%s / %s" % (P1, P2))
ok("sw：CORE_ASSETS が実ファイル名と一致", P1 in sw and P2 in sw)
ok("index/sw に他版のモジュールが残っていない",
   len(set(re.findall(r"main_part1_V\d+\.\d+\.js", idx + sw))) == 1 and
   len(set(re.findall(r"main_part2_V\d+\.\d+\.js", idx + sw))) == 1)
# 2桁マイナー（v1.10.0）が来るので、文字クラスではなく数値で比べる。
_cn = re.search(r"const CACHE_NAME = 'v(\d+)\.(\d+)\.(\d+)'", sw)
ok("sw CACHE_NAME が上がっている",
   bool(_cn) and tuple(int(x) for x in _cn.groups()) >= (1, 2, 0),
   _cn.group(0) if _cn else "not found")
for a in re.findall(r"'\./([^']+)'", sw.split("CORE_ASSETS")[1].split("]")[0]):
    ok("CORE_ASSETS 実在: %s" % a, os.path.exists(os.path.join(APP, a.split("?")[0])))
ok("level-name を撤去", 'id="level-name"' not in idx)
ok("level-facts を追加", 'id="level-facts"' in idx)

# ------------------------------------------------------------------ 実行時
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=15000)
    pg.wait_for_timeout(2200)
    pg.click("#welcome-start"); pg.wait_for_timeout(700)

    # ---- 連続起動日数
    meta = pg.evaluate("async () => await window.Storage.loadMeta()")
    ok("初回起動で open_streak = 1", meta.get("open_streak") == 1, str(meta.get("open_streak")))
    ok("open_day_last が入る", bool(meta.get("open_day_last")))

    # ---- レベル表示（各レベルを差し替えて検証）
    def level_probe(lv, stats):
        return pg.evaluate("""async (arg) => {
            const orig = window.Scheduler.getHomeState;
            window.Scheduler.getHomeState = async () => {
              const h = await orig();
              h.level = { level: arg.lv, level_name:'x', display_pct: 12, badge: null,
                          stats: Object.assign({}, h.level.stats, arg.stats) };
              return h;
            };
            await window.Main.refreshHome();
            const out = { facts: document.getElementById('level-facts').textContent,
                          note : document.getElementById('level-note').textContent,
                          pct  : document.getElementById('level-pct').textContent };
            window.Scheduler.getHomeState = orig;
            return out; }""", {"lv": lv, "stats": stats})

    r2 = level_probe(2, {"total_answered_questions": 46})
    # V1.97：連続日数の表示をやめ、週表示にした（判断待ちの「案B」）。
    # 連続は1日抜けるとゼロに戻り、**復帰しようとしている人の動機を折る**。
    # open_streak は meta に残してある（上で確認済み）。出すのをやめただけ。
    ok("Lv2 1行目：学習日数・累計",
       "学習1日目" in r2["facts"] and "累計解答46問" in r2["facts"], r2["facts"])
    ok("**連続日数はもう出さない（V1.97）**",
       "連続起動" not in r2["facts"], r2["facts"])
    ok("Lv2 2行目：残り54問 / 100問",
       "残り 54問" in r2["note"] and "100問" in r2["note"], r2["note"])
    ok("Lv2：肩書きが出ない（level-name撤去）",
       pg.evaluate("!document.getElementById('level-name')"))
    ok("%表示は維持", r2["pct"] == "12%", r2["pct"])

    r1 = level_probe(1, {"unique_answered_questions": 3, "total_questions": 5})
    ok("Lv1：分母は min(全問題数,60)＝5", "残り 2問 ／ 5問" in r1["note"], r1["note"])
    r3 = level_probe(3, {"total_atoms": 20, "unlearned_atoms": 8})
    ok("Lv3：肢単位で残り8肢", "残り 8肢 ／ 20肢" in r3["note"], r3["note"])
    r5 = level_probe(5, {"total_atoms": 20, "mastered_atoms": 20})
    ok("Lv5：達成表記", "達成（20肢）" in r5["note"], r5["note"])

    # ---- 全体解説の組版（純関数）
    conv = pg.evaluate(r"""() => window.Main.prepareOverallHtml(
        '・<span class="bg-yellow-200">① 正解</span>：総人口は減少<br>・<span class="bg-yellow-200">② 誤り</span>：増加している')""")
    ok("①正解 → 1.○", "1.○" in conv, conv[:160])
    ok("②誤り → 2.×", "2.×" in conv, conv[:160])
    ok("行頭の「・」が消えている", "・<span" not in conv and not conv.startswith("・"), conv[:160])
    ok("元の「正解」「誤り」の語が残っていない", "正解" not in conv and "誤り" not in conv, conv[:200])

    # ---- 文字サイズ（全体解説 vs 選択肢の解説）
    pg.wait_for_timeout(700)
    pg.click("#choice-list .choice-card:nth-child(2) .choice-body"); pg.wait_for_timeout(200)
    fill_choices(pg)
    pg.click("#btn-confirm"); pg.wait_for_timeout(900)
    pg.evaluate("window.Half2Impl.dismissTip()")
    pg.evaluate("document.getElementById('btn-detail').click()")
    pg.wait_for_timeout(500)
    sizes = pg.evaluate("""() => {
        const o = document.getElementById('rv-overall');
        const c = document.querySelector('#rv-choices .cx-exp');
        return { overall: parseFloat(getComputedStyle(o).fontSize),
                 choice : c ? parseFloat(getComputedStyle(c).fontSize) : null }; }""")
    ok("全体解説は13〜14px（旧15.2pxから縮小）",
       13.0 <= sizes["overall"] <= 14.0, str(sizes))
    ok("全体解説は選択肢の解説と同等かわずかに大きい",
       sizes["choice"] and sizes["choice"] <= sizes["overall"] <= sizes["choice"] + 1.0, str(sizes))
    ok("12px下限を割っていない", sizes["overall"] >= 12.0, str(sizes))

    # ---- ポモドーロ
    pomo = pg.evaluate("""() => {
        window.Main.state.pomodoro.enabled = true;
        window.Main.state.pomodoro.running = true;
        window.Main.state.pomodoro.startedAt = Date.now() - 5 * 60 * 1000;
        window.Main.state.pomodoro.limitMs = 25 * 60 * 1000;
        window.Main.openPomodoroSheet();
        return { title: document.getElementById('pomo-title').textContent,
                 open : !document.getElementById('modal-pomodoro').hidden }; }""")
    ok("残り20分でタップ → 嘘の見出しを出さない",
       pomo["open"] and "25分が経過" not in pomo["title"] and "残り" in pomo["title"], str(pomo))
    pomo2 = pg.evaluate("""() => {
        window.Main.state.pomodoro.startedAt = Date.now() - 26 * 60 * 1000;
        window.Main.openPomodoroSheet();
        return document.getElementById('pomo-title').textContent; }""")
    ok("25分経過後は経過の見出しになる", "25分が経過" in pomo2, pomo2)
    pomo3 = pg.evaluate("""() => {
        window.Main.state.pomodoro.running = false;
        window.Main.openPomodoroSheet();
        return document.getElementById('pomo-title').textContent; }""")
    ok("待機中は待機と出る", "待機中" in pomo3, pomo3)
    ok("OFFボタンが同じシートにある",
       pg.evaluate("!!document.getElementById('pomo-off')"))
    pg.evaluate("window.Main.closeModals()")

    # ---- ランダム＝初見のみ
    newonly = pg.evaluate("""async () => {
        const all = await window.Scheduler.buildQueue({ mode:'random', count:50, applyGuard:false });
        const only = await window.Scheduler.buildQueue({ mode:'random', count:50, applyGuard:false, newOnly:true });
        return { all: all.questions.length, only: only.questions.length }; }""")
    ok("newOnly で候補が絞られる（%s → %s）" % (newonly["all"], newonly["only"]),
       newonly["only"] <= newonly["all"], str(newonly))

    # 全問を学習済みにして枯渇させる
    exhausted = pg.evaluate("""async () => {
        const qs = await window.Storage.getAllQuestions();
        for (const q of qs) {
          const atoms = await window.Storage.getAtomsByQuestion(q.q_id);
          await window.Scheduler.applyQuestionEvaluations(q.q_id,
            atoms.map(a => ({ atom_id:a.atom_id, eval:'hard', is_correct:false })),
            { mode:'random', sessionId:'EX', boundaryHour:4 });
        }
        const only = await window.Scheduler.buildQueue({ mode:'random', count:50, applyGuard:false, newOnly:true });
        return only.questions.length; }""")
    ok("全問一周後、初見は0件になる", exhausted == 0, str(exhausted))
    pg.evaluate("window.Half2Impl.startRandom(null, 10)")
    pg.wait_for_timeout(1200)
    ok("枯渇時は行き止まりにせず案内を出す",
       pg.evaluate("!document.getElementById('modal-no-new').hidden"))
    ok("案内に復習・ノークへの導線がある",
       pg.evaluate("!!document.getElementById('nonew-review') && !!document.getElementById('nonew-knock')"))
    pg.evaluate("window.Main.closeModals()")

    # ---- 復習ソフト警告
    due = pg.evaluate("""async () => {
        const atoms = await window.Storage.getAllAtoms();
        for (const a of atoms) { await window.Storage.updateAtom(a.atom_id, { due_date: Date.now() - 60000 }); }
        await window.Storage.setMeta('review_nag_day', 0);
        return await window.Storage.getDueCount(); }""")
    ok("復習を%d件たまらせた（閾値20）" % due, due >= 20, str(due))
    pg.evaluate("window.Main.go('home', {replace:true})")
    pg.wait_for_timeout(300)
    pg.evaluate("document.getElementById('card-random').click()")
    pg.wait_for_timeout(900)
    ok("復習20件以上でランダムへ行くと引き止める",
       pg.evaluate("!document.getElementById('modal-review-nag').hidden"))
    ok("件数が出る", pg.inner_text("#nag-count").strip() == str(due), pg.inner_text("#nag-count"))
    ok("ブロックではない（それでも進むがある）", pg.evaluate("!!document.getElementById('nag-go')"))
    pg.click("#nag-go"); pg.wait_for_timeout(1200)
    ok("[それでも進む]で本来の画面へ進む",
       pg.evaluate("window.Main.state.screen") in ("random", "quiz"),
       pg.evaluate("window.Main.state.screen"))
    pg.evaluate("window.Main.go('home', {replace:true})")
    pg.wait_for_timeout(300)
    pg.evaluate("document.getElementById('card-random').click()")
    pg.wait_for_timeout(900)
    ok("同じ日に2回目は引き止めない（1日1回）",
       pg.evaluate("document.getElementById('modal-review-nag').hidden"))
    pg.evaluate("window.Main.closeModals(); window.Main.go('home', {replace:true})")

    # ---- 使い方カード
    tips = pg.evaluate("window.Half2Impl.HOME_TIPS")
    ok("使い方カードは34件（F で 3削除・4追加）", len(tips) == 34, str(len(tips)))
    body_all = "".join(t["body"] for t in tips)
    # V1.22 で利用者が「臨床検査技師」を「とある医療系の」に変えた。
    # 資格名ではなく、3枚それぞれに固有の言い回しがあることで見る。
    ok("製作者から①〜③がある",
       "国家試験に合格してます" in body_all and "何十回と目にして" in body_all
       and "余裕な問題は出題されない" in body_all)
    ok("忘却曲線①〜④がある",
       "エビングハウス" in body_all and "半年後" in body_all and "2度目3度目" in body_all)
    # V1.22 で「熟睡とスマホは×」→「ベッド・スマホは×」に変更。
    ok("ポモドーロ①〜④がある",
       "1ポモドーロ" in body_all and "スマホは×" in body_all and "邪魔くさい" in body_all)
    ok("設定①〜④がある", "ダークモードを推奨" in body_all and "過去5年より前" in body_all)
    # 事実修正の3点
    # F で文言を差し替えたので、言い回しではなく「初見＝30日」という事実で見る
    ok("修正1：初見の「簡単」は30日と書いてある（1週間ではない）",
       "初見で「簡単」を押すと、次の出題は30日後" in body_all and "1週間後です" not in body_all)
    # V1.20 で利用者が t15 を短くし、解禁条件の記述そのものを外した。
    # 「正しい要約があること」ではなく「誤った要約が無いこと」だけを見る。
    ok("修正2：「120問入ると解禁」の誤った要約が無い", "120問入ると解禁" not in body_all)
    ok("修正3：更新頻度の断定（毎週）が消えている", "毎週" not in body_all)
    ok("修正4：割り込みはランダム限定と書いてある",
       "ランダムモードで学習しているときだけ" in body_all)
    ok("修正5：復習の引き止めは実装と一致（20件・1日1回）",
       "20件以上たまったまま" in body_all)

    ok("ページ例外なし", not errs, " | ".join(errs[:3]))
    pg.screenshot(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "shot_D.png"), full_page=True)
    br.close()

fails = [r for r in R if not r[0]]
print("\n".join(("  ok  " if c else "  NG  ") + n + (("   << " + d) if (d and not c) else "")
                for c, n, d in R))
print("\n%d 項目中 %d 通過 / %d 失敗" % (len(R), len(R) - len(fails), len(fails)))
sys.exit(1 if fails else 0)
