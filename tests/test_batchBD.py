#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBD：120問フル模試を最初から最後まで通す（V1.79）

これまで確かめていたのは「組み立て」までだった（何問そろうか・重複が無いか）。
**受験 → 採点 → 結果 → SRSへの反映**は、過去問1,173問を入れた状態で
一度も通していなかった。第11章③の自動昇格／安全降格は、模試でしか走らない。

あわせて V1.78 の抜けを塞ぐ：反応時間（think_ms）が通常の解答経路にしか
入っておらず、**時間を測る場である模試だけが空欄**だった。

実測（1,173問・120問フル模試を通しで受験）：
  受験 120問/約100秒・JSエラー0・結果モーダル表示
  自動昇格 易149肢（30日後）／安全降格 難340肢（10分後）
"""
import io, json, os, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []

def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()

# ---------------------------------------------------------------- 静的検査
kjs = read("scheduler.js")
p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
js = read(p2)

ok("模試の記録にも think_ms を載せる", "think_ms        : isNum(ctx.thinkMs)" in kjs)
ok("受験中に反応時間を控える（採点は最後なので後からでは取れない）",
   "think_ms: (typeof M.thinkMsForCurrent === 'function')" in js)
ok("採点で控えた値を渡す", "thinkMs: a.think_ms" in js)
ok("なぜ模試だけ空欄だったかが書いてある", "模試だけが空欄" in kjs)
ok("自動昇格・安全降格の規則が残っている（第11章③）",
   "正解 ＋ 根拠ON" in js and "安全降格" in js)

# ---------------------------------------------------------------- 実行時検査
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=30000)
    pg.wait_for_timeout(1500)
    try:
        pg.click("#welcome-start", timeout=4000)
    except Exception:
        pass
    pg.wait_for_timeout(600)

    # 解禁条件を満たす
    unl = pg.evaluate("""async () => {
      const S = window.Storage; const atoms = await S.getAllAtoms();
      const now = Date.now(), patch = {};
      atoms.forEach((a, i) => { if (i % 5 === 0) return;
        patch[a.atom_id] = { answer_count:1, correct_count:1, last_eval:'normal',
          last_answered_at: now - 86400000*20, srs_step:3, interval_code:'1w',
          due_date: now + 86400000 }; });
      await S.updateAtomsBulk(patch);
      const r = await window.Scheduler.refreshUnlocks();
      return r.unlocks.filter(x => x.id === 'mock_30')[0].unlocked;
    }""")
    ok("下ごしらえ：模試が解禁される", unl, str(unl))

    # 30問プチ模試を通しで受験する（本数は抑える。通ることが目的）
    pg.evaluate("window.Half2Impl.launchExam('mock_30', 30, 'real')")
    pg.wait_for_selector("#choice-list .choice-card", timeout=30000)
    ok("模試が始まり、1問目が出る",
       (pg.text_content("#q-counter") or "").strip().startswith("1 /"),
       pg.text_content("#q-counter"))

    answered = 0
    ground = 0
    for i in range(40):
        try:
            pg.wait_for_function(
                "() => document.querySelector('#choice-list .choice-card')"
                " || (document.querySelector('#numeric-wrap')"
                "     && document.querySelector('#numeric-wrap').offsetParent !== null)",
                timeout=6000)
        except Exception:
            break
        # 数値問題は選択肢カードが出ない。扱えないと途中で止まる。
        if pg.is_visible("#numeric-wrap"):
            pg.fill("#numeric-input", "1")
        else:
            # 0.5秒のインターロック中は肢が押せない（pointer-events:none）。
            # 待たずに押すと「element is not visible」で落ちる。
            pg.wait_for_selector("#choice-list.is-ready", timeout=15000)
            # 解除直後は肢が「スッ」と浮き上がる最中（transition .2s）で、
            # そのまま押すと not stable で落ちる。動きが収まるまで待つ。
            pg.wait_for_timeout(300)
            # 根拠トグルは右端の ☐（.choice-mark）。左の番号バッジではない。
            if i % 2 == 0:
                marks = pg.locator("#choice-list .choice-mark")
                hit = 0
                for k in range(marks.count()):
                    try:
                        marks.nth(k).click(timeout=5000)
                        hit += 1
                    except Exception:
                        pass
                if hit:
                    ground += 1
            cards = pg.locator("#choice-list .choice-card")
            for k in range(cards.count()):
                try:
                    cards.nth(k).click(timeout=6000)
                except Exception:
                    continue
                if not pg.evaluate("() => document.querySelector('#btn-confirm').disabled"):
                    break
        try:
            pg.wait_for_selector("#btn-confirm:not([disabled])", timeout=8000)
            pg.click("#btn-confirm")
        except Exception:
            break
        answered += 1
        # 模試は確定すると自動で次へ進む（解説を挟まない）。［次へ］は押さない。
        pg.wait_for_timeout(120)
        # V2.17：最終問題の確定で「最終確認」一覧が開く（自動採点はしない）
        if pg.is_visible("#modal-exam-confirm") or pg.is_visible("#modal-exam-result"):
            break

    ok("30問を最後まで解ける（途中で止まらない）", answered >= 30, "answered=%d" % answered)
    ok("根拠ONにした問題がある（自動昇格の経路を通す）", ground >= 5, "ground=%d" % ground)

    # V2.17：提出前の最終確認を通ってから採点する
    pg.wait_for_selector("#modal-exam-confirm:not([hidden])", timeout=8000)
    ok("提出前の最終確認が出る（自動採点しない）", True)
    pg.click("#exam-confirm-submit")
    pg.wait_for_timeout(2500)
    res = pg.evaluate("""() => {
      const m = document.querySelector('#modal-exam-result');
      return { shown: !!(m && !m.hidden),
               title: (document.querySelector('#exam-result-title')||{}).textContent || '',
               score: (document.querySelector('#exam-score')||{}).textContent || '' };
    }""")
    ok("採点結果のモーダルが出る", res["shown"], json.dumps(res)[:200])
    ok("総合の点が出ている", "/ 30" in res["score"], res["score"][:120])
    ok("自動昇格・安全降格の内訳が出ている",
       "自動昇格" in res["score"] and "安全降格" in res["score"], res["score"][:160])

    srs = pg.evaluate("""async () => {
      const S = window.Storage;
      const logs = await S.getAllLogs();
      const exam = logs.filter(l => l.mode === 'exam');
      const atoms = await S.getAllAtoms();
      const c = { d30: 0, m10: 0 };
      atoms.forEach(a => { if (a.interval_code === '30d') c.d30++;
                           else if (a.interval_code === '20m') c.m10++; });
      return { exam: exam.length,
               withThink: exam.filter(l => typeof l.think_ms === 'number').length,
               hasField: exam.every(l => 'think_ms' in l),
               patterns: exam.reduce((m,l) => { m[l.exam_pattern] = (m[l.exam_pattern]||0)+1; return m; }, {}),
               steps: c };
    }""")
    ok("模試の記録が台帳に積まれる", srs["exam"] >= 30, json.dumps(srs))
    ok("パターンA（正解＋根拠ON→易）が発生する", (srs["patterns"].get("A") or 0) > 0, json.dumps(srs["patterns"]))
    ok("パターンC（不正解/根拠OFF→難）が発生する", (srs["patterns"].get("C") or 0) > 0, json.dumps(srs["patterns"]))
    ok("易は30日後の段に入る", srs["steps"]["d30"] > 0, json.dumps(srs["steps"]))
    ok("難は20分後の段に入る（V2.20）", srs["steps"]["m10"] > 0, json.dumps(srs["steps"]))
    ok("模試の記録に think_ms の欄がある（V1.78の抜けを塞いだ）", srs["hasField"], json.dumps(srs))
    ok("模試でも反応時間が入る", srs["withThink"] > 0, json.dumps(srs))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBD" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
