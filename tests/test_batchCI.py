#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V2.12 検証：出題画面のヘッダーが窮屈で、カードと同じ文字が二重に出ていた

何が起きていたか（利用者のスクリーンショット・390px）：
 - ヘッダーに「S [2-6-B-d] 人体の構造と機能 ＞ 6. 循環系 ＞ B. 血管系 ＞ d. 冠循環」が出て、
   その直下のカードにも「S [2-6-B-d]」が出ていた（同じ属性が二重）
 - 右端に「● 24:40」と「ON ⏲タイマー」が別々に並び、幅を食っていた

直し方：
 - ヘッダーは単元名だけ。ランク・階層コード・大項目以下はカードの q-meta に集約
 - 時間チップとON/OFFトグルは「見た目は1つのピル」。当たり判定は2つのまま
   （残り時間を見るタップでOFFになる事故を防ぐ＝V1.44の判断を守る）

固定すること：
 - 出題中、ヘッダーにランク・階層コードの要素が無く、#hdr-path は単元名と一致する
 - カードの #q-path に 単元＞大項目＞中項目＞小項目 が出る（重複はカードだけに）
 - ピルの2つは隙間なく隣接し、重ならない。トグルの文字は「⏲」＋ON/OFF
 - チップを押してもON/OFFは変わらず、トグルを押すと変わる
 - 375px・390px でヘッダーの右端が画面内に収まる
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    import io
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


idx = read("index.html")
p1 = read(sorted([f for f in os.listdir(APP) if "main_part1_V" in f])[-1])
ok("ヘッダーにランク・階層コードの要素が無い（カードへ集約）",
   'id="hdr-rank"' not in idx and 'id="hdr-code"' not in idx and 'id="hdr-path"' in idx)
ok("カードに #q-path がある", 'id="q-path"' in idx)
ok("時間チップとトグルが .pomo-pill の中に並ぶ", '<div class="pomo-pill"' in idx and idx.count('class="pomo-pill"') == 1)
ok("ヘッダーに書くのは単元名だけ（part1）", "path.textContent = question.unit || '';" in p1)

with sync_playwright() as pw:
    br = pw.chromium.launch(args=["--no-sandbox"])
    for w in (375, 390):
        ctx = br.new_context(viewport={"width": w, "height": 844})
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(APP_URL, wait_until="load")
        pg.wait_for_function("window.__APP_READY === true", timeout=60000)
        pg.wait_for_timeout(1200)
        # チュートリアルと、その場ガイドを黙らせてからランダムを1問開く
        pg.evaluate("""async () => {
          const S = window.Storage;
          await S.setMeta('onboarding_done', true);
          try { await S.setMeta('tips_seen', ['qstar','tagpill','star','locked','pomodoro','eval','next','home','knock','random']); } catch (e) {}
          const M = window.Main; if (M.closeModals) { M.closeModals(); }
          await M.startSession({ mode: 'random', count: 1 });
        }""")
        pg.wait_for_function("(document.querySelector('.screen.is-active')||{}).id === 'screen-quiz'", timeout=15000)
        pg.wait_for_timeout(700)
        r = pg.evaluate("""() => {
          const t = s => (document.querySelector(s) || {}).textContent || '';
          const rc = s => { const e = document.querySelector(s); if (!e || e.hidden) { return null; }
            const b = e.getBoundingClientRect(); return { l: b.left, r: b.right, t: b.top, b: b.bottom, w: b.width, h: b.height }; };
          const q = (window.Main.state.session && window.Main.state.session.current) || null;
          const M = window.Main;
          const chip = rc('#pomodoro-chip'), tog = rc('#pomodoro-toggle'), set = rc('#btn-settings');
          const before = !!M.state.pomodoro.enabled;
          document.getElementById('pomodoro-chip').click();
          const afterChip = !!M.state.pomodoro.enabled;
          document.getElementById('pomodoro-toggle').click();
          const afterTog = !!M.state.pomodoro.enabled;
          document.getElementById('pomodoro-toggle').click();   /* 戻す */
          return { hdr: t('#hdr-path').trim(), unit: q ? q.unit : null,
                   qpath: t('#q-path').trim(), qcode: t('#q-code').trim(),
                   chip: chip, tog: tog, setRight: set ? set.r : null, vw: window.innerWidth,
                   togText: t('.pomo-toggle-text').trim(), togState: t('.pomo-toggle-state').trim(),
                   before: before, afterChip: afterChip, afterTog: afterTog,
                   hdrHasRank: !!document.querySelector('#app-header .rank-badge') };
        }""")
        unit = r["qpath"].split(" ＞ ")[0].strip() if r["qpath"] else ""
        ok("%dpx：ヘッダーは単元名だけ（ランク無し・#hdr-path == カードの単元）" % w,
           unit and r["hdr"] == unit and " ＞ " not in r["hdr"] and not r["hdrHasRank"],
           json.dumps({"hdr": r["hdr"], "unit": unit, "rank": r["hdrHasRank"]}, ensure_ascii=False))
        ok("%dpx：カードに 単元＞大項目＞中項目＞小項目 が出る（4階層・コードと同じ行）" % w,
           r["qpath"].count(" ＞ ") == 3 and r["qcode"].startswith("["), r["qpath"])
        adj = r["chip"] and r["tog"] and abs(r["chip"]["r"] - r["tog"]["l"]) <= 1.5
        ok("%dpx：時間チップとトグルが隙間なく隣接し、重ならない（1つのピルに見える）" % w,
           adj and r["chip"]["r"] <= r["tog"]["l"] + 1.5, json.dumps({"chip": r["chip"], "tog": r["tog"]}))
        ok("%dpx：トグルの文字は ⏲ ＋ ON/OFF" % w, r["togText"] == "⏲" and r["togState"] in ("ON", "OFF"),
           json.dumps({"t": r["togText"], "s": r["togState"]}, ensure_ascii=False))
        ok("%dpx：チップを押してもON/OFFは変わらず、トグルで変わる（当たり判定は2つのまま）" % w,
           r["afterChip"] == r["before"] and r["afterTog"] != r["before"], json.dumps(r, ensure_ascii=False)[:160])
        ok("%dpx：ヘッダーの右端が画面内に収まる" % w, r["setRight"] is not None and r["setRight"] <= r["vw"],
           json.dumps({"right": r["setRight"], "vw": r["vw"]}))
        # 解説（評価）画面でも同じ
        pg.evaluate("() => { const M = window.Main; if (M.closeModals) { M.closeModals(); } }")
        ok("%dpx：実行時エラーなし" % w, not errs, json.dumps(errs[:3], ensure_ascii=False))
        ctx.close()
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + str(detail)) if (detail and not good_) else ""))
print("\n%d/%d  batchCI" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
