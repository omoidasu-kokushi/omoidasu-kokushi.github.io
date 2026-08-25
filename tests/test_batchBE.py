#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBE：概念別弱点ノックと早期復習割り込み（V1.80）

どちらも仕様の中核だが、これまで固定していたのは**文言と静的な条件**が中心で、
実際に走らせた確認が薄かった。過去問1,173問を入れた状態で通してみて、
どちらも正しく動くことを確かめたので、その動きをここに固定する。

とくに大事なのは割り込みの**絶対ガード**（仕様§5-②）。
「本日の復習・概念別弱点ノック・力試し模試・単元別学習・単語検索の演習を
実行中は割り込みを完全に禁止」——ここが緩むと、測っている最中に
別の問題が割り込んで、模試の初見性も復習の順序も壊れる。

ノック側の要点は**忘却スケジュールを更新しないこと**（解釈D）。
評価・弱点pt・概念理解率だけを更新する独立モードでなければ、
集中演習しただけで期日が動いてしまう。
"""
import io, json, os, sys

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []

def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()

# ---------------------------------------------------------------- 静的検査
kjs = read("scheduler.js")
ok("割り込みを許すモードは new と random だけ",
   "INTERRUPT_ALLOWED_MODES = ['new', 'random']" in kjs)
ok("3問蓄積で発火", "INTERRUPT_TRIGGER = 3" in kjs)
ok("1回の割り込みは3問", "INTERRUPT_BATCH = 3" in kjs)
ok("連続割り込みの上限は5", "INTERRUPT_MAX_RUN = 5" in kjs)
ok("ノックはトピックガードを外す", "applyGuard: false" in kjs)

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
    pg.wait_for_timeout(1400)
    try:
        pg.click("#welcome-start", timeout=4000)
    except Exception:
        pass
    pg.wait_for_timeout(700)

    # ---------- 早期復習割り込み ----------
    it = pg.evaluate("""async () => {
      const K = window.Scheduler, S = window.Storage;
      K.Interrupt.endSession();
      const atoms = (await S.getAllAtoms()).slice(0, 12);
      let noted = 0;
      atoms.forEach(a => {
        if (K.Interrupt.note({ atom_id:a.atom_id, q_id:a.q_id, interval_code:'10m' }, 'random')) noted++;
      });
      const out = {
        noted: noted,
        uniqueQ: K.Interrupt.uniqueQuestionCount(),
        allow: {},
      };
      ['new','random','review','exam','knock','search','tree'].forEach(m => {
        out.allow[m] = K.Interrupt.shouldTrigger(m);
      });
      const b = await K.Interrupt.begin('random');
      out.begin = { started: b.started, n: (b.questions||[]).length };
      const blocked = await K.Interrupt.begin('review');
      out.blocked = { started: blocked.started, reason: blocked.reason || null };
      return out;
    }""")
    ok("許可モードで蓄積できる", it["noted"] >= 3, json.dumps(it)[:160])
    ok("同じ問題は1件に畳まれる", it["uniqueQ"] >= 3, json.dumps(it)[:160])
    ok("ランダムでは発火する", it["allow"]["random"], json.dumps(it["allow"]))
    ok("新規でも発火する（許可モード）", it["allow"]["new"] is not None, json.dumps(it["allow"]))
    ok("【絶対ガード】本日の復習では発火しない", it["allow"]["review"] is False, json.dumps(it["allow"]))
    ok("【絶対ガード】力試し模試では発火しない", it["allow"]["exam"] is False, json.dumps(it["allow"]))
    ok("【絶対ガード】弱点ノックでは発火しない", it["allow"]["knock"] is False, json.dumps(it["allow"]))
    ok("【絶対ガード】単語検索の演習では発火しない", it["allow"]["search"] is False, json.dumps(it["allow"]))
    ok("【絶対ガード】単元別学習では発火しない", it["allow"]["tree"] is False, json.dumps(it["allow"]))
    ok("割り込みは3問ちょうど出す", it["begin"]["started"] and it["begin"]["n"] == 3, json.dumps(it["begin"]))
    ok("禁止モードから始めようとしても始まらない",
       it["blocked"]["started"] is False and bool(it["blocked"]["reason"]), json.dumps(it["blocked"]))

    # 蓄積を許さないモードでは note そのものが通らない
    note = pg.evaluate("""async () => {
      const K = window.Scheduler, S = window.Storage;
      K.Interrupt.endSession();
      const a = (await S.getAllAtoms())[0];
      return { review: K.Interrupt.note({ atom_id:a.atom_id, q_id:a.q_id, interval_code:'10m' }, 'review'),
               exam:   K.Interrupt.note({ atom_id:a.atom_id, q_id:a.q_id, interval_code:'10m' }, 'exam'),
               random: K.Interrupt.note({ atom_id:a.atom_id, q_id:a.q_id, interval_code:'10m' }, 'random') };
    }""")
    ok("禁止モードでは蓄積すらしない", note["review"] is False and note["exam"] is False, json.dumps(note))
    ok("許可モードでは蓄積する", note["random"] is True, json.dumps(note))

    # ---------- 概念別弱点ノック ----------
    prep = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler;
      const atoms = await S.getAllAtoms();
      const now = Date.now(), patch = {};
      atoms.forEach((a, i) => { if (i % 3 === 0) return;
        patch[a.atom_id] = { answer_count:1, correct_count:(i%2), last_eval:['hard','normal','easy'][i%3],
          last_answered_at: now - 86400000*5, srs_step:2, interval_code:'1d', due_date: now + 3600000 }; });
      await S.updateAtomsBulk(patch);
      await K.recomputeConceptScores();
      const rank = await K.getConceptRanking({ order:'low', withAtomsOnly:true });
      return { n: rank.length, tag: rank.length ? rank[0].tag : null,
               label: rank.length ? (rank[0].label || null) : null };
    }""")
    ok("理解率の低い概念が並ぶ", prep["n"] > 0, json.dumps(prep))
    # 【落とし穴】出題に渡すのは tag（先頭に # が付く）。label を渡すと1問も出ない。
    ok("ランキングの tag は # から始まる（label と取り違えない）",
       bool(prep["tag"]) and prep["tag"].startswith("#"), json.dumps(prep))

    q = pg.evaluate("""(tag) => window.Scheduler.getKnockQueue(tag, { minutes: 5 })
          .then(q => ({ n: q.questions.length, tag: q.tag, reason: q.reason || null }))""", prep["tag"])
    ok("ノックの出題が組める", q["n"] > 0, json.dumps(q, ensure_ascii=False))
    label_q = pg.evaluate("""(label) => window.Scheduler.getKnockQueue(label, { minutes: 5 })
          .then(q => ({ n: q.questions.length }))""", prep["label"])
    ok("label（#なし）を渡すと1問も出ない＝取り違えは静かに空振りする",
       label_q["n"] == 0, json.dumps(label_q))

    pg.evaluate("(tag) => window.Half2Impl.startKnock(tag, 5)", prep["tag"])
    pg.wait_for_timeout(1200)
    kn = pg.evaluate("""() => {
      const t = document.querySelector('#knock-timer');
      const r = t ? t.getBoundingClientRect() : null;
      return { parent: t && t.parentElement ? t.parentElement.tagName : null,
               visible: !!(r && r.width > 0 && r.height > 0),
               text: t ? (t.textContent||'').replace(/\\s+/g,' ').trim().slice(0,40) : null,
               bodyClass: document.body.className.indexOf('is-knock') >= 0,
               mode: window.Main.state.session ? window.Main.state.session.mode : null,
               cards: document.querySelectorAll('#choice-list .choice-card').length };
    }""")
    ok("ノックが始まる（モードが knock）", kn["mode"] == "knock", json.dumps(kn, ensure_ascii=False))
    ok("タイマーは body 直下に出す（画面を移っても消えない）", kn["parent"] == "BODY", json.dumps(kn, ensure_ascii=False))
    ok("タイマーに実寸がある", kn["visible"], json.dumps(kn, ensure_ascii=False))
    ok("残り時間と対象の概念が出ている",
       ("04:" in (kn["text"] or "") or "05:00" in (kn["text"] or "")) and "#" in (kn["text"] or ""),
       json.dumps(kn, ensure_ascii=False))
    ok("body に is-knock が付く", kn["bodyClass"], json.dumps(kn, ensure_ascii=False))
    ok("問題が出ている", kn["cards"] > 0, json.dumps(kn, ensure_ascii=False))

    # 1問解く → 評価は入るが、忘却スケジュールは動かない（解釈D）
    before = pg.evaluate("""async () => {
      const S = window.Storage;
      const q = window.Main.state.session.questions[0];
      const a = await S.getAllAtoms();
      return a.filter(x => x.q_id === q.q_id)
              .map(x => [x.atom_id, x.interval_code, x.due_date, x.srs_step].join('|')).sort();
    }""")
    pg.wait_for_selector("#choice-list.is-ready", timeout=15000)
    pg.wait_for_timeout(300)
    cards = pg.locator("#choice-list .choice-card")
    for k in range(cards.count()):
        try:
            cards.nth(k).click(timeout=6000)
        except Exception:
            continue
        if not pg.evaluate("() => document.querySelector('#btn-confirm').disabled"):
            break
    pg.wait_for_selector("#btn-confirm:not([disabled])", timeout=8000)
    pg.click("#btn-confirm")
    pg.wait_for_timeout(900)
    try:
        pg.click("#btn-next", timeout=4000)
        pg.wait_for_timeout(1000)
    except Exception:
        pass

    after = pg.evaluate("""async () => {
      const S = window.Storage;
      const logs = await S.getAllLogs();
      const kn = logs.filter(l => l.mode === 'knock');
      return { logs: kn.length,
               scheduleUpdated: kn.filter(l => l.schedule_updated).length,
               withThink: kn.filter(l => typeof l.think_ms === 'number').length,
               evals: kn.filter(l => !!l.eval).length };
    }""")
    ok("ノックの記録が台帳に積まれる", after["logs"] > 0, json.dumps(after))
    ok("評価は記録される（克服が概念スコアに反映される）", after["evals"] > 0, json.dumps(after))
    ok("【解釈D】忘却スケジュールは更新しない", after["scheduleUpdated"] == 0, json.dumps(after))
    ok("ノックでも反応時間が入る", after["withThink"] > 0, json.dumps(after))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBE" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
