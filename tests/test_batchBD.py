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
ok("模試の記録は反応時間を空にする（V3.10・利用者裁定）", "think_ms: null," in js
   and "think_ms: (typeof M.thinkMsForCurrent === 'function')" not in js)
ok("採点で控えた値を渡す（V3.05：保留 → 記録のときに渡す）", "thinkMs: it.think_ms" in js and "think_ms: a.think_ms" in js)
ok("なぜ模試だけ空欄だったかが書いてある", "模試だけが空欄" in kjs)
ok("模試の評価の既定は 4-3（V3.05：第11章③の昇格・降格は利用者裁定で廃止）",
   "K.recommendEvaluations(atoms, picked).recommendations" in js and "K.applyExamResult(" not in js)

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
    pg.wait_for_selector("#paper-list .pq", timeout=30000)
    pg.wait_for_timeout(500)
    ok("模試が始まり、全問が1枚に並ぶ（V3.10）",
       pg.evaluate("() => document.querySelectorAll('#paper-list .pq').length") >= 30,
       str(pg.evaluate("() => document.querySelectorAll('#paper-list .pq').length")))

    # V3.10：模試は1枚の問題用紙。肢をタップして塗り、☐で印を付け、最下部の［提出する］で出す。
    #        「途中で止まらないか」は、全問ぶんの .pq が並び、全部塗れることで見る。
    res0 = pg.evaluate("""() => {
      const ex = window.Half2Impl.state.exam;
      let answered = 0, ground = 0;
      ex.questions.forEach((qq, i) => {
        const li = document.querySelector('#paper-list .pq[data-index="' + i + '"]');
        if (!li) { return; }
        const inp = li.querySelector('.pq-num-input');
        if (inp) { inp.value = '1'; answered++; return; }
        const cards = [...li.querySelectorAll('.choice-card')];
        if (!cards.length) { return; }
        const atoms = (qq.atoms || []).slice().sort((a, b) => a.original_num - b.original_num);
        const need = Math.max(1, atoms.filter(a => a.is_correct).length);
        const nums = (i % 3 === 0)
          ? atoms.filter(a => a.is_correct).map(a => a.original_num)
          : atoms.filter(a => !a.is_correct).map(a => a.original_num).slice(0, need);
        (nums.length ? nums : [atoms[0].original_num]).forEach(n => {
          const c = li.querySelector('.choice-card[data-num="' + n + '"] .choice-body'); if (c) { c.click(); } });
        answered++;
        if (i % 2 === 0) { cards.forEach(c => c.querySelector('.choice-mark').click()); ground++; }
      });
      return { answered, ground, rows: document.querySelectorAll('#paper-list .pq').length };
    }""")
    answered, ground = res0["answered"], res0["ground"]

    ok("30問を最後まで解ける（途中で止まらない）", answered >= 30 and res0["rows"] >= 30, json.dumps(res0))
    ok("根拠ONにした問題がある（自動昇格の経路を通す）", ground >= 5, "ground=%d" % ground)

    # V3.10：提出は最下部だけ。押すと確認（文言だけ）→［これで提出］で採点
    pg.click("#paper-submit")
    pg.wait_for_selector("#modal-exam-submit:not([hidden])", timeout=8000)
    ok("提出の前に1度だけ確認する（自動採点しない）", True)
    pg.click("#exam-submit-go")
    pg.wait_for_timeout(2500)
    res = pg.evaluate("""() => {
      const m = document.querySelector('#modal-exam-result');
      return { shown: !!(m && !m.hidden),
               title: (document.querySelector('#exam-result-title')||{}).textContent || '',
               score: (document.querySelector('#exam-score')||{}).textContent || '' };
    }""")
    ok("採点結果のモーダルが出る", res["shown"], json.dumps(res)[:200])
    ok("総合の点が出ている", "/ 30" in res["score"], res["score"][:120])
    ok("評価の既定の内訳が出ている（V3.05）",
       "評価の既定" in res["score"] and "難しい" in res["score"], res["score"][:160])

    # V3.05：提出時は保留。結果を閉じると既定のまま記録される
    pg.click('#modal-exam-result [data-close]')
    pg.wait_for_timeout(2500)
    srs = pg.evaluate("""async () => {
      const S = window.Storage;
      const logs = await S.getAllLogs();
      const exam = logs.filter(l => l.mode === 'exam');
      const atoms = await S.getAllAtoms();
      const c = { h1: 0, m10: 0 };
      atoms.forEach(a => { if (a.interval_code === '1h') c.h1++;
                           else if (a.interval_code === '20m') c.m10++; });
      return { exam: exam.length,
               withThink: exam.filter(l => typeof l.think_ms === 'number').length,
               hasField: exam.every(l => 'think_ms' in l),
               patterns: exam.reduce((m,l) => { m[l.eval] = (m[l.eval]||0)+1; return m; }, {}),
               ground: exam.filter(l => typeof l.ground_on === 'boolean').length,
               steps: c };
    }""")
    ok("模試の記録が台帳に積まれる", srs["exam"] >= 30, json.dumps(srs))
    ok("正解の問題は「普通」で記録される（4-3・初見）", (srs["patterns"].get("normal") or 0) > 0, json.dumps(srs["patterns"]))
    ok("不正解の問題は「難しい」で記録される（4-3）", (srs["patterns"].get("hard") or 0) > 0, json.dumps(srs["patterns"]))
    ok("普通は1時間後の段に入る（初見）", srs["steps"]["h1"] > 0, json.dumps(srs["steps"]))
    ok("難は20分後の段に入る（V2.20）", srs["steps"]["m10"] > 0, json.dumps(srs["steps"]))
    ok("☐は ground_on として記録に残る（評価には使わない）", srs["ground"] >= 30, json.dumps(srs))
    ok("模試の記録に think_ms の欄がある（V1.78の抜けを塞いだ）", srs["hasField"], json.dumps(srs))
    # V3.10（利用者裁定「反応時間は模試は気にしないでいい」）：問題用紙には
    # 「押せるようになった瞬間」が無いので、模試の記録は null。欄そのものは残す（上の観点）。
    ok("模試の反応時間は空（V3.10・利用者裁定）", srs["withThink"] == 0, json.dumps(srs))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBD" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
