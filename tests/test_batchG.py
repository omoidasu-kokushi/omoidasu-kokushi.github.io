#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチG 検証：評価4カードの文言 ／ 一言欄34件の並び順

  V1.20 で利用者が t06/t08 を書き換えたので、SPEC はその文へ更新済み。
  ここは「実装（nextStepIndex）と文言が一致しているか」を毎回突き合わせる場所なので、
  文が変わったら SPEC も一緒に動かし、突き合わせ自体は残す。
"""
import json, io, os, sys, subprocess, glob
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))

P2 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
for f in ["storage.js", "scheduler.js", P2, "sw.js"]:
    p = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True)
    ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

# 指定文（1文字も変えていないことを全文比較で確かめる）
SPEC = {
 "評価ボタン：難しい": ("20分後に再出題",
  "いつ押しても必ず20分後に再出題されます。何度押しても20分後のままで、間隔が伸びることはありません。"
  "根拠が言えないなら、正解していても迷わずこれ。"),
 "評価ボタン：普通": ("1時間後 →翌日 →1週間に再出題",
  "初見なら1時間後。20分後か1時間後の段階なら翌日出題。そこから先は"
  "「普通」だけを押し続けても1週間より先へは進みません。1週間の壁を越えるには「簡単」を押す必要があります。"),
 "評価ボタン：簡単": ("初見で押すと30日後に再出題",
  "一度つまずいてから簡単を押した場合は、翌日 →1週間 →30日 →90日 →180日と1段ずつ昇ります。上限は180日です。"),
 "評価ボタン：マスター": ("「二度と見なくていい選択肢」を評価する時",
  "30日以上の段階に到達するまで押せません（それまではグレーのまま）。押すと次は半年後。"
  "弱点の集計からも外れます。覚悟して押しましょう。"),
}

# 期待する並び順（34件・ラベル）
ORDER = [
 "本日の復習", "このアプリの考え方", "このアプリの考え方", "使い方",
 "評価ボタン：難しい", "評価ボタン：普通", "評価ボタン：簡単", "評価ボタン：マスター",
 "エビングハウスの忘却曲線 ①", "エビングハウスの忘却曲線 ②",
 "エビングハウスの忘却曲線 ③", "エビングハウスの忘却曲線 ④",
 "ランダムモード", "テーマ別 弱点ノック", "力試しモード", "弱点分析",
 "弱点分析", "キーワード検索", "マイ★お気に入りノート",
 "使い方", "使い方", "このアプリの考え方",
 "ポモドーロ勉強法 ①", "ポモドーロ勉強法 ②", "ポモドーロ勉強法 ③", "ポモドーロ勉強法 ④",
 "設定 ①", "設定 ②", "設定 ③", "使い方",
 "製作者から ①", "製作者から ②", "製作者から ③", "製作者から",
]

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=20000)
    pg.wait_for_timeout(2400)
    pg.click("#welcome-start"); pg.wait_for_timeout(700)

    tips = pg.evaluate("window.Half2Impl.HOME_TIPS")
    ok("一言欄は34件", len(tips) == 34, str(len(tips)))

    # ---- 評価4カードの文言（全文一致）
    for lab, (t, b) in SPEC.items():
        hit = [x for x in tips if x["label"] == lab]
        ok("%s：タイトルが指定どおり" % lab, len(hit) == 1 and hit[0]["title"] == t,
           (hit[0]["title"] if hit else "not found"))
        ok("%s：本文が指定どおり（全文一致）" % lab, len(hit) == 1 and hit[0]["body"] == b,
           (hit[0]["body"] if hit else "not found"))
    ok("誤字「つまずいたてから」が残っていない",
       "つまずいたてから" not in "".join(x["body"] for x in tips))

    # ---- 並び順
    got = [x["label"] for x in tips]
    ok("並び順が動線どおり（34件・完全一致）", got == ORDER,
       "\n     got=%s\n     exp=%s" % (got, ORDER))
    ok("1件目は使い方（本日の復習）から始まる", got[0] == "本日の復習", got[0])
    ok("最後の4件は製作者から",
       all(x.startswith("製作者から") for x in got[-4:]), str(got[-4:]))
    ok("製作者からは末尾にしか無い",
       [i for i, x in enumerate(got) if x.startswith("製作者から")] == [30, 31, 32, 33],
       str([i for i, x in enumerate(got) if x.startswith("製作者から")]))
    ok("評価4ボタンは連続して5〜8件目",
       got[4:8] == ["評価ボタン：難しい", "評価ボタン：普通", "評価ボタン：簡単", "評価ボタン：マスター"],
       str(got[4:8]))
    ok("忘却曲線①〜④が連続している", got[8:12] == ["エビングハウスの忘却曲線 ①",
       "エビングハウスの忘却曲線 ②", "エビングハウスの忘却曲線 ③", "エビングハウスの忘却曲線 ④"], str(got[8:12]))
    ok("ポモドーロ①〜④が連続している",
       all(got[22 + i] == "ポモドーロ勉強法 " + c for i, c in enumerate("①②③④")), str(got[22:26]))
    ok("モード紹介はホームの並び順（ランダム→ノック→力試し）",
       got[12:15] == ["ランダムモード", "テーマ別 弱点ノック", "力試しモード"], str(got[12:15]))

    # ---- 期間が実装と一致していること（毎回突き合わせる）
    real = pg.evaluate("""() => {
        const K = window.Scheduler, P = a => K.previewAllIntervals(a);
        const fresh = { srs_step:0, interval_code:null, last_eval:null, answer_count:0 };
        const at10m = { srs_step:1, interval_code:'10m', last_eval:'hard', answer_count:1 };
        const at1d  = { srs_step:3, interval_code:'1d',  last_eval:'normal', answer_count:2 };
        const at1w  = { srs_step:4, interval_code:'1w',  last_eval:'normal', answer_count:3 };
        const at30d = { srs_step:5, interval_code:'30d', last_eval:'easy', answer_count:4 };
        const at90d = { srs_step:6, interval_code:'90d', last_eval:'easy', answer_count:5 };
        return { h1:P(fresh).hard.label, h2:P(at30d).hard.label,
                 n0:P(fresh).normal.label, n1:P(at10m).normal.label,
                 n2:P(at1d).normal.label, n3:P(at1w).normal.label,
                 e0:P(fresh).easy.label, e1:P(at10m).easy.label, e2:P(at1d).easy.label,
                 e3:P(at1w).easy.label, e4:P(at30d).easy.label, e5:P(at90d).easy.label,
                 mLock:!K.isMasterUnlocked(at1w), mOk:K.isMasterUnlocked(at30d),
                 mVal:P(at30d).master.label }; }""")
    ok("実装と一致：難しい＝常に20分後（V2.20）", real["h1"] == "20分後" and real["h2"] == "20分後", json.dumps(real, ensure_ascii=False))
    ok("実装と一致：普通＝1時間→翌日→1週間で停止",
       real["n0"] == "1時間後" and real["n1"] == "1日後" and real["n2"] == "1週間後" and real["n3"] == "1週間後",
       json.dumps(real, ensure_ascii=False))
    ok("実装と一致：簡単＝初見30日／つまずき後は翌日→1週間→30日→90日→180日",
       real["e0"] == "30日後" and real["e1"] == "1日後" and real["e2"] == "1週間後"
       and real["e3"] == "30日後" and real["e4"] == "90日後" and real["e5"] == "180日後",
       json.dumps(real, ensure_ascii=False))
    ok("実装と一致：マスターは30日以上で解禁・180日",
       real["mLock"] and real["mOk"] and real["mVal"] == "180日後", json.dumps(real, ensure_ascii=False))

    # ---- 実際に1件目から順に送られるか
    seq = pg.evaluate("""async () => {
        await window.Storage.setMeta('home_tip_index', 0);
        const out = [];
        for (let i = 0; i < 5; i++) {
          await window.Half2Impl.renderHomeTips();
          out.push([document.getElementById('home-tip-label').textContent,
                    document.getElementById('home-tip-count').textContent]);
          await window.Half2Impl.advanceHomeTip();
        }
        return out; }""")
    ok("画面上も1件目から順に出る", seq[0][0] == "本日の復習" and seq[0][1] == "1 / 34",
       json.dumps(seq, ensure_ascii=False))
    ok("5件目は「評価ボタン：難しい」", seq[4][0] == "評価ボタン：難しい" and seq[4][1] == "5 / 34",
       json.dumps(seq[4], ensure_ascii=False))

    ok("ページ例外なし", not errs, " | ".join(errs[:3]))
    br.close()

fails = [r for r in R if not r[0]]
print("\n".join(("  ok  " if c else "  NG  ") + n + (("   << " + d) if (d and not c) else "")
                for c, n, d in R))
print("\n%d 項目中 %d 通過 / %d 失敗" % (len(R), len(R) - len(fails), len(fails)))
sys.exit(1 if fails else 0)
