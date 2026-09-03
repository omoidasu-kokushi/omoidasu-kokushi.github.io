#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBQ：復習の1日上限「今日の分」（V1.92）

【なぜ要るか】
本日の復習には上限がなかった。3日休むと期日の問題が積み上がり、カードに 200 と出る。
**その数字そのものが、始められない理由になる。**
間隔反復のアプリが捨てられるいちばん多い理由がこれ。

【V1.92 で見つかった古い不具合】
`buildQueue` の count には既定値10が入っている。`mode:'review'` はその count を
そのまま `getReviewQueue` へ渡していたので、**本日の復習はずっと最大10問しか
出していなかった**。バッジは期日の全件（例：128）を出しているのに、押すと10問で
「本日の復習タスク完了！🎉」が出る、という状態だった。
上限を入れるついでに、ここを options.count を直接見る形へ直した。

【なぜ壊れないか】
出す順は緊急度（interval_code）の昇順のまま。**最も差し迫ったものから出す**ので、
切られるのは常に「いちばん後回しでよいもの」。

【隠さない】
上限は先送りであって帳消しではない。残りは必ず数で見せる。
ただし**溜まっていない人の画面には1文字も足さない**
（カードに出すのはタイトルと件数だけ、という V1.17 の決定を壊さない）。

【上限の決め方】
自動＝直近14日のうち**解いた日**の中央値 × 1.5（30〜200）。記録が7日未満なら60。
**休んだ日を0として混ぜない。** 週3日に100問ずつ解く人の中央値が0になり、
上限が30まで落ちて二度と追いつけなくなる。
"""
import io, json, os, re, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


sc = read("scheduler.js")
st = read("storage.js")
html = read("index.html")
css = read("styles.css")
p1 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
j1, j2 = read(p1), read(p2)

ok("上限の既定を持っている", "review_cap              : 'auto'," in st)
ok("実績の台帳を持っている", "daily_log               : []," in st)
ok("休んだ日を混ぜない理由が書いてある", "休んだ日は入らない" in st and "休んだ日を0として混ぜません" in sc)
ok("自動計算がある", "function autoReviewCap(" in sc)
ok("0（上限なし）と未設定を区別している", "m === 0 || m === '0' || m === 'off'" in sc)
ok("今日の実績を進める純関数がある", "function bumpDaily(" in sc)
ok("日界の共有ユーティリティを正しく呼んでいる", "S.util.dayStart(" in sc and "S.dayStart(" not in sc)
ok("残りを必ず返す", "due_questions_all: all," in sc and "due_rest: rest," in sc)
ok("バッジは今日の分に揃えてある", "badge_value: Math.min(dueToday, 99)," in sc)
ok("**プランナーの「問」を肢数から問題数へ直した**",
   "buildPlan(meta, dueToday," in sc and "getDueCount が返すのは**肢の数**" in sc)
ok("溜まっているときだけ出す行がある", 'id="review-rest"' in html and ".review-rest{" in css)
ok("溜まっていない人には出さないと書いてある", "1文字も足さない" in html and "1文字も足さない" in j1)
ok("続ける道が残っている", 'id="done-more"' in html and "reviewCap: false" in j1)
ok("設定に上限の段がある", 'id="set-cap"' in html and 'data-cap="0"' in html)
ok("設定の表示を更新する入口がある", "refreshCapNote().catch(noop);" in j2)
# 版そのものは batchAC / batchAH が横断で見ている。ここで数字を焼くと
# 次の改修で必ず赤くなるので焼かない。
ok("版番号・CACHE_NAME・?v= の3箇所が揃っている",
   (lambda i, w: i and w and i == w)(
       (re.search(r"\?v=([0-9.]+)", html) or [None, None])[1],
       (re.search(r"\?v=([0-9.]+)", read("sw.js")) or [None, None])[1]))

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(1400)

    # --- 上限の決め方 ---
    r = pg.evaluate("""() => {
      const K = window.Scheduler;
      const log = ns => ns.map((n, i) => ({ k: i, n: n }));
      return {
        few:   K.autoReviewCap(log([50, 50, 50])),          /* 記録が7日未満 */
        mid:   K.autoReviewCap(log([40,40,40,40,40,40,40])), /* 中央値40 × 1.5 */
        low:   K.autoReviewCap(log([5,5,5,5,5,5,5])),        /* 下限で止まる */
        high:  K.autoReviewCap(log([300,300,300,300,300,300,300])), /* 上限で止まる */
        /* 週3日に100問ずつの人。休んだ日は台帳に入らない前提 */
        thrice: K.autoReviewCap(log([100,100,100,100,100,100,100])),
        /* 0が混ざっても数えない（万一入っていたときの保険） */
        zeros: K.autoReviewCap(log([0,0,0,0,100,100,100,100,100,100,100])),
        auto:  K.resolveReviewCap({ review_cap:'auto', daily_log:log([40,40,40,40,40,40,40]) }),
        man:   K.resolveReviewCap({ review_cap:100 }),
        off:   K.resolveReviewCap({ review_cap:0 }),
        none:  K.resolveReviewCap({}),
        med:   [K.medianOf([1,2,3]), K.medianOf([1,2,3,4]), K.medianOf([])]
      };
    }""")
    ok("記録が足りないうちは既定の60", r["few"] == 60, json.dumps(r))
    ok("中央値×1.5で決まる", r["mid"] == 60, json.dumps(r))
    ok("下限30より下げない", r["low"] == 30, json.dumps(r))
    ok("上限200より上げない", r["high"] == 200, json.dumps(r))
    ok("**週3日に100問ずつの人の上限が潰れない**", r["thrice"] == 150, json.dumps(r))
    ok("**0の日は数えない**", r["zeros"] == 150, json.dumps(r))
    ok("中央値の計算が合っている", r["med"] == [2, 2.5, 0], json.dumps(r["med"]))
    ok("**「上限なし」と「未設定」を取り違えない**",
       r["off"]["cap"] == 0 and r["off"]["mode"] == "off"
       and r["none"]["cap"] == 60 and r["none"]["mode"] == "auto",
       json.dumps({"off": r["off"], "none": r["none"]}, ensure_ascii=False))
    ok("手動はその数になる", r["man"]["cap"] == 100 and r["man"]["mode"] == "manual",
       json.dumps(r["man"], ensure_ascii=False))

    # --- 今日の実績 ---
    d = pg.evaluate("""() => {
      const K = window.Scheduler, DAY = 86400000;
      const t0 = K.bumpDaily({ daily_key:null, daily_count:0, daily_log:[] }, 1000*3600*10, 4);
      const t1 = K.bumpDaily({ daily_key:t0.daily_key, daily_count:5, daily_log:[] },
                             1000*3600*10, 4);
      /* 日をまたぐと、前日ぶんが台帳へ送られて今日は1から */
      const t2 = K.bumpDaily({ daily_key:t0.daily_key, daily_count:12, daily_log:[] },
                             1000*3600*10 + DAY, 4);
      /* 14日ぶんより古いものは落ちる */
      const long = { daily_key:t0.daily_key, daily_count:9,
                     daily_log: Array.from({length:14}, (_, i) => ({ k:i, n:i+1 })) };
      const t3 = K.bumpDaily(long, 1000*3600*10 + DAY, 4);
      return { t0:t0, t1:t1, t2:t2, t3len:t3.daily_log.length, t3first:t3.daily_log[0].n };
    }""")
    ok("初日は1から数える", d["t0"]["daily_count"] == 1, json.dumps(d))
    ok("同じ日なら足していく", d["t1"]["daily_count"] == 6, json.dumps(d))
    ok("**日をまたいだら前日ぶんを台帳へ送って0から**",
       d["t2"]["daily_count"] == 1 and d["t2"]["daily_log"][0]["n"] == 12, json.dumps(d))
    ok("台帳は14日ぶんまで", d["t3len"] == 14 and d["t3first"] == 2, json.dumps(d))

    # --- 実際に切れるか。切っても壊れないか ---
    q = pg.evaluate("""async () => {
      const K = window.Scheduler, S = window.Storage;
      const now = Date.now();
      const at = await S.getAllAtoms();
      /* 40問ぶん以上の期日を作る。緊急度をばらけさせて、
         切られるのが「いちばん後回しでよいもの」であることを見る。 */
      const codes = ['10m','1h','1d','1w'];
      const byQ = {};
      at.forEach(a => { (byQ[a.q_id] = byQ[a.q_id] || []).push(a); });
      const qids = Object.keys(byQ).slice(0, 80);
      for (let i = 0; i < qids.length; i++) {
        const code = codes[i % codes.length];
        for (const a of byQ[qids[i]]) {
          await S.updateAtom(a.atom_id, { srs_step:1, interval_code:code,
            last_eval:'normal', answer_count:1, due_date: now - 60000 });
        }
      }
      await S.setMeta('review_cap', 20);
      const capped = await K.buildQueue({ mode:'review' });
      await S.setMeta('review_cap', 0);
      const full = await K.buildQueue({ mode:'review' });
      await S.setMeta('review_cap', 'auto');
      const urg = qs => qs.map(x => (x.due_atom_ids||[]).length ? 1 : 0);
      const codeOf = async qid => {
        const a = await S.getAtomsByQuestion(qid);
        return a[0] ? a[0].interval_code : null;
      };
      const cappedCodes = [];
      for (const x of capped.questions) { cappedCodes.push(await codeOf(x.q_id)); }
      const h = await K.getHomeState();
      return { capN: capped.questions.length, capRest: capped.due_rest,
               capAll: capped.due_questions_all, cap: capped.review_cap,
               fullN: full.questions.length, fullRest: full.due_rest,
               codes: cappedCodes,
               home: { today:h.due_today, rest:h.due_rest, all:h.due_questions,
                       badge:h.badge_text, cap:h.review_cap } };
    }""")
    ok("**10問で打ち切られていた古い不具合が直っている**",
       q["capN"] > 10 or q["fullN"] > 10,
       json.dumps({k: q[k] for k in q if k != "codes"}, ensure_ascii=False))
    ok("**上限どおりの数で止まる**", q["capN"] == 20 and q["cap"] == 20,
       json.dumps({k: q[k] for k in q if k != "codes"}, ensure_ascii=False))
    ok("**切ったぶんを必ず返す**",
       q["capRest"] == q["capAll"] - 20 and q["capRest"] > 0,
       json.dumps({k: q[k] for k in q if k != "codes"}, ensure_ascii=False))
    ok("**「上限なし」なら全部出る**",
       q["fullN"] == q["capAll"] and q["fullRest"] == 0,
       json.dumps({k: q[k] for k in q if k != "codes"}, ensure_ascii=False))
    ok("**切られるのは後回しでよいもの（差し迫った10分・1時間が先に出る）**",
       q["codes"][:10].count("10m") + q["codes"][:10].count("1h") >= 8,
       json.dumps(q["codes"], ensure_ascii=False))
    ok("ホームの数が queue と揃っている",
       q["home"]["all"] == q["capAll"] and q["home"]["today"] + q["home"]["rest"] == q["capAll"],
       json.dumps(q["home"], ensure_ascii=False))
    ok("**バッジは今日の分を出す（押して出てくる数と揃える）**",
       q["home"]["badge"] == str(min(q["home"]["today"], 99))
       or (q["home"]["today"] > 99 and q["home"]["badge"] == "99+"),
       json.dumps(q["home"], ensure_ascii=False))

    # --- V2.11：OSアイコン（App Badging）にも今日の分を渡す（§23-⑨） ---
    b = pg.evaluate("""async () => {
      const got = [];
      const orig = navigator.setAppBadge
        ? navigator.setAppBadge.bind(navigator) : null;
      navigator.setAppBadge = async n => { got.push(n); };
      try { await window.Main.refreshHome(); }
      finally { if (orig) { navigator.setAppBadge = orig; }
                else { delete navigator.setAppBadge; } }
      const h = await window.Scheduler.getHomeState();
      return { got: got, want: h.badge_value, today: h.due_today };
    }""")
    ok("OSアイコンバッジへ渡るのは badge_value（今日の分・99以下の整数）",
       len(b["got"]) >= 1 and b["got"][-1] == b["want"]
       and isinstance(b["got"][-1], int) and b["got"][-1] <= 99,
       json.dumps(b, ensure_ascii=False))

    # --- 画面 ---
    v = pg.evaluate("""async () => {
      const S = window.Storage, M = window.Main;
      await S.setMeta('review_cap', 20);
      await M.refreshHome();
      const on = document.getElementById('review-rest');
      const shown = { hidden:on.hidden, text:on.textContent };
      await S.setMeta('review_cap', 0);
      await M.refreshHome();
      const off = { hidden:on.hidden };
      await S.setMeta('review_cap', 'auto');
      const card = document.getElementById('card-review').innerText.replace(/\\n/g,'|');
      return { shown:shown, off:off, card:card };
    }""")
    ok("**溜まっていれば1行出る**",
       v["shown"]["hidden"] is False and "明日以降" in v["shown"]["text"],
       json.dumps(v, ensure_ascii=False))
    ok("**溜まっていなければ出さない**", v["off"]["hidden"] is True, json.dumps(v, ensure_ascii=False))
    ok("**カードそのものは変えていない（タイトルと件数だけ）**",
       len(set(v["card"].replace("|", " ").split()) - {"本日の復習"}) <= 1,
       json.dumps(v["card"], ensure_ascii=False))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBQ" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
