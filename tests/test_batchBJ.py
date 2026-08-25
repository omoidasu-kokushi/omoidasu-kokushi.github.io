#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBJ：模試を途中でやめたあと、通常学習が壊れないこと（V1.85）
   ＋ イレギュラーの網羅検証で通った箇所の固定

`endSession()` は **hooks を消さない**。消すのは各モードの役目で、
概念ノックは `onAbort` で片付けている（`abortKnock`）。
**模試だけ `onAbort` を張っていなかった。**

実測（画面から再現）：模試を1問解いて［ホーム］→ ランダムを開始 → 1問解くと
  ・解説が出ない（`data-phase` が `answer` のまま）
  ・［次へ］が押せない
  ・**記録が1件も増えない**（解答は死んだ模試の answers へ吸い込まれる）
  ・JSエラーは出ない

「模試を始めたけどやめる」はごく普通の操作で、そのあと
**解いても解いても増えない**状態が延々続く。気づく手がかりが無い。
"""
import io, json, os, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []

def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()

p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
js = read(p2)

ok("模試に onAbort がある", "M.hooks.onAbort = function (mode) {" in js and "abortExam();" in js)
ok("後片付けの関数がある", "function abortExam(" in js)
ok("3つのフックを全部外す",
   all(x in js.split("function abortExam(")[1][:400]
       for x in ["afterGrade = null", "onFinish = null", "onAbort = null"]))
ok("正常終了でも onAbort を外す", "onAbort = null;" in js.split("function showExamResult(")[1][:400])
ok("endSession を呼び返さないと書いてある", "呼び返すと入れ子" in js)
ok("何が起きていたかが書いてある", "吸い込まれ" in js and "解いても解いても" in js)

from playwright.sync_api import sync_playwright

CLOCK = """
(() => {
  const RealDate = Date; let offset = 0;
  class FakeDate extends RealDate {
    constructor(...a) { if (a.length === 0) { super(RealDate.now() + offset); } else { super(...a); } }
    static now() { return RealDate.now() + offset; }
    static parse(...a) { return RealDate.parse(...a); }
    static UTC(...a) { return RealDate.UTC(...a); }
  }
  window.Date = FakeDate;
  window.__advance = (ms) => { offset += ms; return offset; };
})();
"""

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    ctx.add_init_script(CLOCK)
    pg = ctx.new_page()
    pg.set_default_timeout(120000)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=30000)
    pg.wait_for_timeout(1800)
    try:
        pg.click("#welcome-start", timeout=4000)
    except Exception:
        pass
    pg.wait_for_timeout(700)
    # その場ガイドの吹き出しは前面に出てクリックを吸う。
    # 全部「見た」ことにして黙らせる（ガイド自体は batchAS 等で見ている）。
    pg.evaluate("""async () => {
      const S = window.Storage;
      const ids = Object.keys(window.Half2Impl.TIPS || {});
      await S.setMetaBulk({ onboarding_done:true, tutorial_finished:true,
        tips_seen: ids.length ? ids : ['answer','ground','settings','home','review','random'] });
    }""")
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(2200)
    pg.evaluate("() => window.Main.closeModals && window.Main.closeModals()")

    # 模試を解禁する
    pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler;
      const atoms = await S.getAllAtoms(); const now = Date.now(), patch = {};
      atoms.forEach((a, i) => { if (i % 5) patch[a.atom_id] = { answer_count:1, correct_count:1,
        last_eval:'normal', last_answered_at: now - 86400000, srs_step:3, interval_code:'1w',
        due_date: now + 86400000 }; });
      await S.updateAtomsBulk(patch);
      await K.refreshUnlocks();
    }""")

    def clear_overlays():
        """その場ガイドの吹き出しは前面にいてクリックを吸う。先に畳む。"""
        for _ in range(6):
            if not pg.is_visible("#onb-layer"):
                break
            try:
                pg.click("#onb-skip", timeout=2000)
                pg.wait_for_timeout(350)
            except Exception:
                break
        try:
            pg.evaluate("() => window.Main.closeModals && window.Main.closeModals()")
        except Exception:
            pass

    def press_next():
        """［次へ］を押す。ガイドの吹き出しが被っていたらそれだけ畳む。
           closeModals は呼ばない（解説フェーズのUIごと畳んでしまう）。"""
        for _ in range(6):
            if not pg.is_visible("#onb-layer"):
                break
            try:
                pg.click("#onb-skip", timeout=2000); pg.wait_for_timeout(300)
            except Exception:
                break
        state = pg.evaluate("""() => {
          const b = document.querySelector('#btn-next');
          if (!b) return { exists:false };
          const r = b.getBoundingClientRect();
          const cs = getComputedStyle(b);
          return { exists:true, hidden:b.hidden, w:Math.round(r.width), h:Math.round(r.height),
                   disp:cs.display, vis:cs.visibility, op:cs.opacity };
        }""")
        if not state.get("exists") or state.get("hidden") or state.get("w", 0) < 2:
            print("    ［次へ］の状態:", json.dumps(state, ensure_ascii=False))
            return False
        try:
            pg.click("#btn-next", timeout=8000)
            return True
        except Exception as ex:
            print("    ［次へ］を押せない:", str(ex)[:120])
            return False

    def answer_one(right=True, ground=False):
        pg.wait_for_selector("#choice-list.is-ready", timeout=20000)
        clear_overlays()
        pg.wait_for_timeout(280)
        plan = pg.evaluate("""(right) => {
          const cur = window.Main.state.current; if (!cur) return null;
          const atoms = cur.atoms || [];
          const rn = atoms.filter(a => a.is_correct).map(a => a.original_num);
          const wn = atoms.filter(a => !a.is_correct).map(a => a.original_num);
          return right ? rn : (wn.length ? wn.slice(0, Math.max(1, rn.length)) : rn.slice(0,1));
        }""", right)
        if ground:
            marks = pg.locator("#choice-list .choice-mark")
            for k in range(marks.count()):
                try: marks.nth(k).click(timeout=2500)
                except Exception: pass
        for num in (plan or []):
            try: pg.click("#choice-list .choice-card[data-num='%s'] .choice-body" % num, timeout=5000)
            except Exception: pass
        pg.wait_for_selector("#btn-confirm:not([disabled])", timeout=8000)
        pg.click("#btn-confirm")

    # --- 模試を始めて1問解き、［ホーム］で抜ける
    pg.evaluate("() => window.Half2Impl.launchExam('mock_30', 30, 'real')")
    pg.wait_for_selector("#choice-list .choice-card", timeout=40000)
    pg.wait_for_timeout(600)
    answer_one(True, ground=True)
    pg.wait_for_timeout(800)
    clear_overlays()
    pg.click("#btn-home")
    pg.wait_for_timeout(1500)

    hooks = pg.evaluate("""() => ({
      afterGrade: typeof window.Main.hooks.afterGrade,
      onFinish: typeof window.Main.hooks.onFinish,
      onAbort: typeof window.Main.hooks.onAbort,
      answers: window.Half2Impl.state.exam ? (window.Half2Impl.state.exam.answers||[]).length : null,
      aborted: window.Half2Impl.state.exam ? !!window.Half2Impl.state.exam.aborted : null })""")
    ok("［ホーム］で抜けると模試のフックが外れる",
       hooks["afterGrade"] != "function" and hooks["onFinish"] != "function",
       json.dumps(hooks, ensure_ascii=False))
    ok("途中の解答は捨てられる（採点に混ざらない）",
       hooks["answers"] == 0 and hooks["aborted"] is True, json.dumps(hooks, ensure_ascii=False))
    ok("画面はホームへ戻る",
       pg.evaluate("() => (document.querySelector('.screen.is-active')||{}).id") == "screen-home")

    # --- そのあと通常学習が正しく動くか（ここが核心）
    n0 = pg.evaluate("async () => await window.Storage.countLogs()")
    pg.evaluate("""async () => {
      const K = window.Scheduler;
      const q = await K.buildQueue({mode:'random', count:3, applyGuard:false});
      window.Main.state.session = { mode:'random', sessionId:'AFTEREXAM', questions:q.questions,
        index:0, answeredCount:0, startedAt:Date.now(), hostQueue:null, hostIndex:0 };
      await window.Main.go('quiz'); window.Main.renderQuestion();
    }""")
    pg.wait_for_timeout(1000)
    answer_one(True)
    pg.wait_for_timeout(1200)
    st = pg.evaluate("""() => ({
      phase: document.querySelector('#screen-quiz').dataset.phase,
      examAnswers: window.Half2Impl.state.exam ? (window.Half2Impl.state.exam.answers||[]).length : null,
      mode: window.Main.state.session.mode })""")
    ok("模試を抜けたあとも解説が出る（旧版はここで answer のまま）",
       st["phase"] == "review", json.dumps(st, ensure_ascii=False))
    ok("解答が死んだ模試へ吸い込まれない", st["examAnswers"] == 0, json.dumps(st, ensure_ascii=False))
    pressed = press_next()
    pg.wait_for_timeout(2500)
    n1 = pg.evaluate("async () => await window.Storage.countLogs()")
    ok("模試を抜けたあと［次へ］が押せる（旧版は押せない）", pressed, str(pressed))
    ok("模試を抜けたあとの学習が記録される（旧版は0件のまま）", n1 > n0, "%d → %d" % (n0, n1))

    # ============================ イレギュラーの固定
    # 時計を1年進める／戻す
    base = pg.evaluate("""async () => {
      const S = window.Storage;
      return { logs: await S.countLogs(),
               learned: (await S.getAllAtoms()).filter(a => a.answer_count > 0).length };
    }""")
    for label, ms in (("1年進める", 365*86400000), ("2年戻す", -730*86400000)):
        pg.evaluate("(ms) => window.__advance(ms)", ms)
        cur = pg.evaluate("""async () => {
          const S = window.Storage, K = window.Scheduler;
          await K.refreshAll({recomputeWeakness:false});
          const all = await S.getAllAtoms(); const now = Date.now();
          return { logs: await S.countLogs(),
                   learned: all.filter(a => a.answer_count > 0).length,
                   far: all.filter(a => a.due_date && a.due_date > now + 200*86400000).length,
                   due: (await K.getHomeState()).due_count };
        }""")
        ok("端末の時計を%sても記録が消えない" % label,
           cur["logs"] == base["logs"] and cur["learned"] == base["learned"],
           json.dumps(cur))
        ok("端末の時計を%sても200日超の期日が残らない" % label, cur["far"] == 0, json.dumps(cur))
        ok("端末の時計を%sても復習数が異常にならない" % label,
           0 <= cur["due"] <= cur["learned"] + 5, json.dumps(cur))
    pg.evaluate("(ms) => window.__advance(ms)", 365*86400000)

    # 確定・次への連打で二重記録しない
    dbl = pg.evaluate("""async () => {
      const K = window.Scheduler, S = window.Storage;
      const q = await K.buildQueue({mode:'random', count:1, applyGuard:false});
      const item = q.questions[0];
      const evals = item.atoms.map(a => ({ atom_id: a.atom_id, eval:'normal', is_correct:true }));
      const before = (await S.getAtomsByQuestion(item.q_id)).map(a => a.answer_count || 0);
      await Promise.all([1,2,3].map(() => K.applyQuestionEvaluations(item.q_id, evals,
        { mode:'random', sessionId:'DBL' })));
      const after = (await S.getAtomsByQuestion(item.q_id)).map(a => a.answer_count || 0);
      return { before, after, diff: after.map((v,i) => v - before[i]) };
    }""")
    ok("同じ問題の評価を同時に3回投げても、記録は3回ぶんを超えない",
       max(dbl["diff"]) <= 3, json.dumps(dbl))

    # 問題0件でも集計が落ちない
    zero = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler;
      await S.resetAll(); await S.setMeta('seed_imported', true);
      const out = {};
      const t = async (k, f) => { try { out[k] = await f(); } catch (e) { out[k] = 'ERR:' + e.message; } };
      await t('home', async () => (await K.getHomeState()).due_count);
      await t('level', async () => (await K.computeLevel()).display_pct);
      await t('dash', async () => (await K.buildDashboard({level:'sub_item'})).rows.length);
      await t('concept', async () => (await K.getConceptRanking()).length);
      await t('review', async () => (await K.getReviewQueue(10)).questions.length);
      await t('random', async () => (await K.buildQueue({mode:'random',count:10})).questions.length);
      await t('scan', async () => (await K.getScanAccuracy()).pct);
      await t('unlocks', async () => (await K.refreshUnlocks()).unlocks.filter(x=>x.unlocked).length);
      await t('backup', async () => (await S.estimateBackupBytes()).bytes);
      return out;
    }""")
    ok("問題が0件でもどの集計も例外にならない",
       not [k for k, v in zero.items() if isinstance(v, str) and v.startswith("ERR")],
       json.dumps(zero, ensure_ascii=False))
    ok("0件では模試が解禁されない", zero["unlocks"] == 0, json.dumps(zero))
    ok("0件では分析精度が0で止まる", zero["scan"] == 0, json.dumps(zero))

    # 変わった文字を取り込んでも化けない
    txt = pg.evaluate("""async () => {
      const S = window.Storage;
      const vals = { emoji: '🩺👩‍⚕️ 看護', surrogate: '𩸽と𠮷野家',
                     zenkaku: '＜ｂ＞全角＜／ｂ＞　“引用”', longword: 'あ'.repeat(2000) };
      const out = {};
      for (const k of Object.keys(vals)) {
        const v = vals[k];
        const row = ['必修問題','目標Ⅰ.','S','1. 健康に関する指標','A. 人口静態・人口動態','a. 総人口',
          'single','文字' + k + '：' + v, JSON.stringify(['① ' + v,'② い','③ う','④ え']), '[0]',
          '【正解】①<br>①正しい。', '[["#総人口"],["#総人口"],["#総人口"],["#総人口"]]',''].join('\\t');
        const r = await S.importText(row);
        const qs = (await S.getAllQuestions()).filter(q => q.stem.indexOf('文字' + k) >= 0);
        const at = qs.length ? await S.getAtomsByQuestion(qs[0].q_id) : [];
        out[k] = { imported: r.imported,
                   kept: qs.length ? qs[0].stem.indexOf(v.slice(0, 6)) >= 0 : false,
                   atom: at.length ? at[0].text.indexOf(v.slice(0, 6)) >= 0 : false };
      }
      return out;
    }""")
    bad_txt = [k for k, v in txt.items() if not (v["imported"] and v["kept"] and v["atom"])]
    ok("絵文字・サロゲート・全角・長い1語が化けない", not bad_txt,
       json.dumps(txt, ensure_ascii=False))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBJ" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
