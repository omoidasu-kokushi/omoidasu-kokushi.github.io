# -*- coding: utf-8 -*-
"""test_hard_interval.py — 「難しい」の再出題までの時間を選べるようにした（V2.94）

【利用者の要望（原文に近い形で残す）】
  「難しい押したときの再出題時間はカスタムできるようにしない？
   その人の学習ペースに合わせて、その日のうちに（その回の勉強で）復習したいだろうから
   もっと短くないと集中続かないって人もいるだろうし」

【なぜ人によって変えるのか】
  V2.20 で 10分→20分にしたのは「4択では、さっき見た答えの表面記憶で
  正解してしまう」から。逆に「その回の勉強のうちにもう一度やりたい」人には
  20分は長い。**どちらが正しいかは人による**ので選べるようにする。

【触ってはいけないもの】
  変えるのは**梯子のいちばん下の長さだけ**。
  ・段の数（STEPS は7段のまま）
  ・コード（'20m' のまま。保存済みの atoms / logs / 同期台帳を書き換えない）
  ・緊急度の並び（URGENCY_ORDER）
  ・早期復習の割り込み判定（interval_code で見ている）
  これらが動くと、保存済みのデータの意味が変わる。V2.20 と同じ決まりごと。

【ここで固定すること】
  ・3/5/10/20/30 を選べて、選んだぶんだけ期日が近づく
  ・変な値を入れても20分に落ちる
  ・interval_code は '20m' のまま（データの意味を変えない）
  ・「普通」「簡単」「マスター」の期日は変わらない
  ・設定画面に選ぶところがある
"""
import io
import json
import os
import sys

from playwright.sync_api import sync_playwright

R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))


APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sch = io.open(os.path.join(APP, "scheduler.js"), encoding="utf-8").read()
html = io.open(os.path.join(APP, "index.html"), encoding="utf-8").read()
p2 = io.open(os.path.join(APP, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()
st = io.open(os.path.join(APP, "storage.js"), encoding="utf-8").read()

ok("なぜ人によって変えるのかが書いてある", "どちらが正しいかは人による" in sch)
ok("変えるのは最短段の長さだけ、と書いてある", "梯子のいちばん下の長さだけ" in sch)
ok("設定に選ぶところがある", 'id="set-hard-min"' in html)
ok("5段階（3/5/10/20/30）", all(('value="%d"' % v) in html for v in (3, 5, 10, 20, 30)))
ok("既定は20分だと画面に書いてある", "20分後（既定）" in html)
ok("保存する口がある", "hard_interval_min" in p2 and "setHardMin" in p2)
ok("既定値が meta にある", "hard_interval_min" in st)
ok("次に解いた肢から変わる、と断ってある", "次に解いた肢から" in p2)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    pg.set_default_timeout(120000)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true")
    pg.wait_for_timeout(700)

    plan = pg.evaluate("""() => {
        const K = window.Scheduler;
        const atom = { atom_id: 'x', srs_step: 0, interval_code: null };
        const now = Date.now();   /* 未来の時刻を渡すと computeDueDate が「いま」へ引き戻す（V1.61）ので、実時刻を使う */
        const out = {};
        [3, 5, 10, 20, 30, 999, null].forEach(m => {
            const p = K.planSchedule(atom, 'hard', { now: now, meta: { hard_interval_min: m } });
            out[String(m)] = { min: Math.round((p.due_date - now) / 60000),
                               code: p.interval_code, label: p.interval_label,
                               step: p.srs_step };
        });
        /* 難しい以外は動かないこと */
        const easy = K.planSchedule(atom, 'easy', { now: now, meta: { hard_interval_min: 3 } });
        const norm = K.planSchedule(atom, 'normal', { now: now, meta: { hard_interval_min: 3 } });
        out.easy = { code: easy.interval_code, days: Math.round((easy.due_date - now) / 86400000) };
        out.normal = { code: norm.interval_code, min: Math.round((norm.due_date - now) / 60000) };
        return out;
    }""")
    for m in ("3", "5", "10", "20", "30"):
        ok("%s分を選ぶと%s分後になる" % (m, m), plan[m]["min"] == int(m),
           json.dumps(plan[m], ensure_ascii=False))
    ok("変な値は20分に落ちる", plan["999"]["min"] == 20, json.dumps(plan["999"]))
    ok("未設定は20分（既定）", plan["null"]["min"] == 20, json.dumps(plan["null"]))
    ok("コードは '20m' のまま（保存済みデータの意味を変えない）",
       all(plan[m]["code"] == "20m" for m in ("3", "5", "10", "20", "30")),
       json.dumps({m: plan[m]["code"] for m in ("3", "5", "10", "20", "30")}))
    ok("段の番号も変わらない（どれも1段目）",
       all(plan[m]["step"] == 1 for m in ("3", "5", "10", "20", "30")),
       json.dumps({m: plan[m]["step"] for m in ("3", "5", "10", "20", "30")}))
    ok("表示は選んだ分に合わせる", plan["3"]["label"] == "3分後", plan["3"]["label"])
    # 30日後は日界（朝4時）へ寄せるので、時刻によって29日と出る（仕様どおり）。
    ok("「簡単」は30日後のまま", plan["easy"]["code"] == "30d" and plan["easy"]["days"] in (29, 30),
       json.dumps(plan["easy"], ensure_ascii=False))
    ok("「普通」は1時間後のまま", plan["normal"]["code"] == "1h" and plan["normal"]["min"] == 60,
       json.dumps(plan["normal"], ensure_ascii=False))

    # 設定画面のselectが今の値を選べているか
    sel = pg.evaluate("""async () => {
        await window.Storage.setMeta('hard_interval_min', 5);
        const M = window.Main;
        if (window.Half2 && window.Half2.openSettings) { await window.Half2.openSettings(); }
        await new Promise(r => setTimeout(r, 600));
        const s = document.getElementById('set-hard-min');
        return { exists: !!s, value: s ? s.value : null, n: s ? s.options.length : 0 };
    }""")
    ok("設定の選択肢が5つある", sel["n"] == 5, json.dumps(sel))
    ok("いまの設定が選ばれている", sel["value"] == "5" or sel["value"] is None,
       json.dumps(sel))

    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  hard_interval" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
