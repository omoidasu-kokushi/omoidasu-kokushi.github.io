#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチF 検証スイート：一言欄の修正 ／ ランダムカードの3段階変身"""
import json, re, io, os, sys, subprocess, glob
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))
def read(f): return io.open(os.path.join(APP, f), encoding="utf-8").read()

P1 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
P2 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
for f in ["storage.js", "scheduler.js", P1, P2, "sw.js"]:
    p = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True)
    ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

idx = read("index.html")
ok("card-random に data-state がある", 'id="card-random"' in idx and 'data-state="random"' in idx)
ok("random-tag を追加", 'id="random-tag"' in idx)
ok("no-new モーダルに id を付与", 'id="nonew-title"' in idx and 'id="nonew-body"' in idx)

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=15000)
    pg.wait_for_timeout(2200)
    pg.click("#welcome-start"); pg.wait_for_timeout(800)

    # ================= 一言欄 =================
    tips = pg.evaluate("window.Half2Impl.HOME_TIPS")
    body_all = "".join(t["body"] for t in tips)
    labels = [t["label"] for t in tips]
    ok("一言欄は34件（33 − 削除3 ＋ 追加4）", len(tips) == 34, str(len(tips)))

    # --- 削除3件
    ok("削除：設定④が消えている", "設定 ④" not in labels, str([l for l in labels if l.startswith("設定")]))
    ok("削除：設定は①〜③だけ",
       sorted([l for l in labels if l.startswith("設定")]) == ["設定 ①", "設定 ②", "設定 ③"],
       str(sorted([l for l in labels if l.startswith("設定")])))
    ok("削除：バックアップで保存形式を確認…が消えている", "どんな形で問題が保存されているか" not in body_all)
    ok("削除：「数字は下がりません」が消えている",
       "数字は下がりません" not in [t["title"] for t in tips] and "二度と下がりません" not in body_all)
    ok("削除：「データはこの端末の中だけ」が消えている",
       "データはこの端末の中だけにあります" not in [t["title"] for t in tips]
       and "ログインも通信もありません" not in body_all)

    # --- 差し替え3件
    easy = [t for t in tips if t["title"] == "「簡単」を押すのは、他人に説明できるときだけ"]
    ok("差し替え：「簡単」の心構えが指定文になっている",
       len(easy) == 1 and easy[0]["body"] ==
       "初見で「簡単」を押すと、次の出題は30日後です。そこからさらに「簡単」を重ねると90日・180日と伸びます。"
       "うろ覚えのまま簡単は押さないでください。迷ったら「普通」で十分です。",
       easy[0]["body"] if easy else "not found")
    eb2 = [t for t in tips if t["label"] == "エビングハウスの忘却曲線 ②"]
    ok("差し替え：忘却曲線②が指定文になっている",
       len(eb2) == 1 and eb2[0]["body"] ==
       "「難しい」を選ぶとその日のうちに再出題。「易しい」を選ぶと最短でも翌日まで再出題されません。"
       "2度目3度目と「易しい」を選ぶと、どんどん長い期間出題されなくなっていきます。",
       eb2[0]["body"] if eb2 else "not found")
    rv = [t for t in tips if t["label"] == "本日の復習"]
    ok("差し替え：本日の復習が「メイン機能」だと言っている",
       len(rv) == 1 and "メイン機能" in rv[0]["title"], str(rv))

    # --- 追加4件（期間）
    ev = {t["label"]: t for t in tips if t["label"].startswith("評価ボタン：")}
    ok("追加：評価4ボタンの期間カードが4件", len(ev) == 4, str(sorted(ev.keys())))
    ok("難しい＝10分後", "難しい" in "".join(ev.keys()) and "10分後" in ev["評価ボタン：難しい"]["title"])
    ok("難しいは何度押しても伸びないと明記", "間隔が伸びることはありません" in ev["評価ボタン：難しい"]["body"])
    ok("普通＝1時間→翌日→1週間", "1時間後" in ev["評価ボタン：普通"]["title"]
       and "1週間" in ev["評価ボタン：普通"]["title"])
    ok("普通は1週間で止まると明記", "1週間より先へは進みません" in ev["評価ボタン：普通"]["body"])
    ok("簡単＝初見30日後", "30日後" in ev["評価ボタン：簡単"]["title"])
    ok("簡単のつまずき後の梯子（翌日→1週間→30日→90日→180日）",
       all(x in ev["評価ボタン：簡単"]["body"] for x in ["翌日", "1週間", "30日", "90日", "180日"]))
    # V1.20：タイトルは利用者の文（「二度と見なくていい選択肢」を評価する時）に変わった。
    # 期間の明記は本文側にあるので、そちらで見る。
    ok("マスター＝半年後だと本文に書いてある",
       "半年後" in ev["評価ボタン：マスター"]["body"], ev["評価ボタン：マスター"]["body"])
    ok("マスターは30日以上で解禁と明記", "30日以上" in ev["評価ボタン：マスター"]["body"])

    # --- 期間が実装と一致していること（scheduler から実測して突き合わせ）
    real = pg.evaluate("""() => {
        const K = window.Scheduler;
        const fresh = { srs_step:0, interval_code:null, last_eval:null, answer_count:0 };
        const at10m = { srs_step:1, interval_code:'10m', last_eval:'hard', answer_count:1 };
        const at1d  = { srs_step:3, interval_code:'1d',  last_eval:'normal', answer_count:2 };
        const at1w  = { srs_step:4, interval_code:'1w',  last_eval:'normal', answer_count:3 };
        const at30d = { srs_step:5, interval_code:'30d', last_eval:'easy', answer_count:4 };
        const at90d = { srs_step:6, interval_code:'90d', last_eval:'easy', answer_count:5 };
        const P = a => K.previewAllIntervals(a);
        return {
          hard_fresh : P(fresh).hard.label,  hard_at30d: P(at30d).hard.label,
          norm_fresh : P(fresh).normal.label, norm_10m : P(at10m).normal.label,
          norm_1d    : P(at1d).normal.label,  norm_1w  : P(at1w).normal.label,
          easy_fresh : P(fresh).easy.label,   easy_10m : P(at10m).easy.label,
          easy_1d    : P(at1d).easy.label,    easy_1w  : P(at1w).easy.label,
          easy_30d   : P(at30d).easy.label,   easy_90d : P(at90d).easy.label,
          master_lock: !K.isMasterUnlocked(at1w), master_ok: K.isMasterUnlocked(at30d),
          master_val : P(at30d).master.label }; }""")
    ok("実装：難しいは常に10分後（初見でも30日の段でも）",
       real["hard_fresh"] == "10分後" and real["hard_at30d"] == "10分後", json.dumps(real, ensure_ascii=False))
    ok("実装：普通は 初見1時間 → 10分後の段なら1日 → 1日の段なら1週間 → 以後1週間固定",
       real["norm_fresh"] == "1時間後" and real["norm_10m"] == "1日後"
       and real["norm_1d"] == "1週間後" and real["norm_1w"] == "1週間後", json.dumps(real, ensure_ascii=False))
    ok("実装：簡単は 初見30日／最短は翌日（10分の段から1日後）",
       real["easy_fresh"] == "30日後" and real["easy_10m"] == "1日後", json.dumps(real, ensure_ascii=False))
    ok("実装：簡単の梯子 1日→1週間→30日→90日→180日",
       real["easy_1d"] == "1週間後" and real["easy_1w"] == "30日後"
       and real["easy_30d"] == "90日後" and real["easy_90d"] == "180日後", json.dumps(real, ensure_ascii=False))
    ok("実装：マスターは1週間の段では押せず、30日の段で押せて180日",
       real["master_lock"] and real["master_ok"] and real["master_val"] == "180日後",
       json.dumps(real, ensure_ascii=False))

    # ================= ランダムカードの2状態（V1.41） =================
    # いじわる模試は力試しモードの中にあるので、ホームから独立して出さない。
    # 「全問読破」も行き止まりだったため、読破後は【克服モード】へ変わる。
    ok("状態判定：初見あり → random",
       pg.evaluate("window.Main.randomCardState(5)") == "random")
    ok("状態判定：初見0 → conquer",
       pg.evaluate("window.Main.randomCardState(0)") == "conquer")
    ok("状態判定：未学習数が取れないときは動線を消さない（random のまま）",
       pg.evaluate("window.Main.randomCardState(null)") == "random"
       and pg.evaluate("window.Main.randomCardState(undefined)") == "random")

    def card(un):
        return pg.evaluate("""(un) => {
            window.Main.renderRandomCard(un);
            const c = document.getElementById('card-random');
            const tag = document.getElementById('random-tag');
            return { state: c.dataset.state, action: c.getAttribute('data-action'),
                     title: c.querySelector('.sub-title').textContent,
                     meta : c.querySelector('.sub-meta').textContent,
                     icon : c.querySelector('.sub-icon').className,
                     badgeHidden: document.getElementById('random-badge').hidden,
                     tagHidden: tag.hidden, tag: tag.textContent }; }""", un)

    c1 = card(5)
    ok("① 初見あり：ランダムモード", c1["state"] == "random" and c1["title"] == "ランダムモード"
       and c1["action"] == "go-random" and c1["badgeHidden"] is False and c1["tagHidden"] is True,
       json.dumps(c1, ensure_ascii=False))

    c2 = card(0)
    ok("② 初見0：克服モードに変わる", c2["state"] == "conquer" and c2["title"] == "克服モード"
       and "苦手" in c2["meta"], json.dumps(c2, ensure_ascii=False))
    ok("② 押し先は同じ選択画面（入口を増やさない）", c2["action"] == "go-random")
    ok("② 出題数バッジは消える", c2["badgeHidden"] is True)
    ok("② 何が起きたかがカードに書いてある",
       c2["tagHidden"] is False and "解答ずみ" in c2["tag"], json.dumps(c2, ensure_ascii=False))
    ok("アイコンが2状態で変わる", c1["icon"] != c2["icon"],
       str([c1["icon"], c2["icon"]]))
    sib = pg.evaluate("""() => [
        document.querySelector('#card-knock .sub-icon').className,
        document.querySelector('#card-exam .sub-icon').className ]""")
    ok("克服モードのアイコンが隣のカードと被らない", c2["icon"] not in sib,
       "%s vs %s" % (c2["icon"], sib))
    ok("追加アイコンのCSSが定義されている", "ico-bolt" in read("styles.css"))

    # 位置は一切動かない（主動線の座標を守る）
    pos = pg.evaluate("""(states) => {
        const out = [];
        for (const s of states) {
          window.Main.renderRandomCard(s);
          const r = document.getElementById('card-random').getBoundingClientRect();
          const h = document.getElementById('card-review').getBoundingClientRect();
          out.push([Math.round(r.top), Math.round(r.left), Math.round(h.top)]);
        }
        return out; }""", [5, 0])
    ok("2状態を通じてカードと主動線の座標が動かない",
       len({tuple(x) for x in pos}) == 1, str(pos))

    ok("ホームからいじわる模試への独立動線が無い（力試しモードの中だけ）",
       'data-action="go-evil"' not in read("index.html"))

    pg.evaluate("window.Main.closeModals()")

    # 解禁後は同じ案内が別の文面になる
    unl = pg.evaluate("""async () => {
        await window.Storage.setMeta('unlock_mock_weak', true);
        await window.Half2Impl.openAllClearedSheet();
        return document.getElementById('nonew-body').textContent; }""")
    ok("解禁後は「このカードから挑戦できます」に変わる", "挑戦できます" in unl, unl[:160])
    pg.evaluate("window.Main.closeModals()")

    ok("ページ例外なし", not errs, " | ".join(errs[:3]))
    pg.screenshot(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "shot_F.png"), full_page=True)
    br.close()

fails = [r for r in R if not r[0]]
print("\n".join(("  ok  " if c else "  NG  ") + n + (("   << " + d) if (d and not c) else "")
                for c, n, d in R))
print("\n%d 項目中 %d 通過 / %d 失敗" % (len(R), len(R) - len(fails), len(fails)))
sys.exit(1 if fails else 0)
