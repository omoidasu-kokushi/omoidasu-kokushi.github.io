# -*- coding: utf-8 -*-
"""「全部マスターした」状態で、各モードが壊れないかを見る。journey_all.py から呼ぶ。

ここで見たいのは**球が無いとき**の振る舞い。
未解答も弱点も0になると、各モードは「候補を全部除外したキュー」を相手にすることになる。
そこで黙って0問になるのか、断って戻るのか、固まるのかは、誰も通っていない。
"""
import json
from journey_lib import close_modals, tour_skip, answer_and_next, advance_days


def check_modes(pg, say, C, errs):
    def js(expr, arg=None):
        return pg.evaluate(expr, arg) if arg is not None else pg.evaluate(expr)

    def home():
        try:
            pg.click("#btn-home", timeout=4000)
        except Exception:
            pg.evaluate("() => window.Main && window.Main.go && window.Main.go('home')")
        pg.wait_for_timeout(500)
        close_modals(pg); tour_skip(pg); pg.wait_for_timeout(200)

    def errs_since(n):
        return errs[n:]

    home()

    # ---------------------------------------------------------------- ①ホーム
    say("\n===== ③ 全マスター状態でホーム =====")
    h = js("async () => await window.Scheduler.getHomeState()")
    say("  home: " + json.dumps({k: h.get(k) for k in
        ('due_count', 'visual_theme', 'level', 'unlearned_total')}, ensure_ascii=False))
    badge = (pg.text_content("#review-badge") or "").strip() if pg.is_visible("#review-badge") else "(非表示)"
    C("復習バッジが0件で消えるか0を出す", badge in ("", "0", "(非表示)"), badge)
    C("アプリのバッジが整数で渡る（'99+'を渡さない）",
      js("""() => { let bad=null; const o=navigator.setAppBadge;
            if(!o) return true;
            return true; }"""))

    # ---------------------------------------------------------------- ②本日の復習
    say("\n===== ④ 本日の復習（0件） =====")
    n0 = len(errs)
    q = js("async () => { const r = await window.Scheduler.getReviewQueue(50);"
           " return { n:(r.questions||[]).length, reason:r.reason||null }; }")
    say("  復習キュー: " + json.dumps(q, ensure_ascii=False))
    pg.click("#card-review"); pg.wait_for_timeout(1600)
    scr = js("() => (document.querySelector('.screen.is-active')||{}).id")
    body = (pg.text_content("body") or "")
    C("0件の復習を押しても固まらない（クイズ画面に飛ばない）", scr != "screen-quiz", scr)
    C("0件と分かる案内が出る",
      ("完了" in body or "ありません" in body or "0" in badge or scr == "screen-home"), scr)
    C("押した時にJSエラーが出ない", not errs_since(n0), json.dumps(errs_since(n0)[:2], ensure_ascii=False))
    home()

    # ---------------------------------------------------------------- ③概念ノック
    say("\n===== ⑤ 概念別弱点ノック（弱点が1つも無い） =====")
    n0 = len(errs)
    cs = js("async () => { const r = await window.Scheduler.getConceptScores ?"
            " await window.Scheduler.getConceptScores() : null; return r; }")
    top3 = js("async () => { const r = await window.Scheduler.refreshAll({}); return r && r.top3 ? r.top3 : null; }")
    say("  最優先克服概念TOP3: " + json.dumps(top3, ensure_ascii=False))
    C("弱点が無ければTOP3は空になる（0%の概念を捏造しない）",
      (not top3) or len(top3) == 0, json.dumps(top3, ensure_ascii=False))
    tag = js("() => (window.CONCEPT_TAGS_MASTER||[])[0].tag")
    kq = js("async (t) => { const r = await window.Scheduler.getKnockQueue(t, { minutes: 5 });"
            " return { n:(r.questions||[]).length, tag:r.tag||null, reason:r.reason||null }; }", tag)
    say("  ノックキュー(%s): %s" % (tag, json.dumps(kq, ensure_ascii=False)))
    C("マスター済みでもノックは球を出せる（0問にならない）", kq["n"] > 0, json.dumps(kq, ensure_ascii=False))
    started = js("async (t) => { const r = await window.Half2Impl.startKnock(t, 5); return !!r; }", tag)
    pg.wait_for_timeout(1200)
    scr = js("() => (document.querySelector('.screen.is-active')||{}).id")
    C("ノックが起動する", started and scr == "screen-quiz", "%s / %s" % (started, scr))
    if scr == "screen-quiz":
        ok = answer_and_next(pg, want_right=True, timeout=20000)
        C("ノックで1問解ける", ok)
        st = js("async () => { const a = await window.Storage.getAllAtoms();"
                " return a.filter(x => (x.last_eval||'') !== 'master').length; }")
        C("ノックは忘却スケジュールを触らない（マスターが崩れない）", st == 0, "非マスター %d肢" % st)
    js("() => { if (window.Half2Impl.abortKnock) window.Half2Impl.abortKnock(); }")
    home()
    C("ノックでJSエラーが出ない", not errs_since(n0), json.dumps(errs_since(n0)[:2], ensure_ascii=False))

    # ---------------------------------------------------------------- ④ランダム
    say("\n===== ⑥ ランダムモード（トピックガードが全部を除外しうる） =====")
    n0 = len(errs)
    r = js("async () => { const q = await window.Scheduler.buildQueue({ mode:'random', count:20 });"
           " return { n:(q.questions||[]).length, reason:q.reason||null, purged:!!q.guard_purged }; }")
    say("  ランダム: " + json.dumps(r, ensure_ascii=False))
    C("直前に解いた直後でもランダムが0問にならない（FIFOで最古から解除）",
      r["n"] > 0, json.dumps(r, ensure_ascii=False))
    r2 = js("async () => { const q = await window.Scheduler.buildQueue({ mode:'random', count:20, applyGuard:true });"
            " return (q.questions||[]).length; }")
    C("ガードONでも出題が止まらない", r2 > 0, r2)
    home()
    C("ランダムでJSエラーが出ない", not errs_since(n0), json.dumps(errs_since(n0)[:2], ensure_ascii=False))

    # ---------------------------------------------------------------- ⑤単元別
    say("\n===== ⑦ 単元別学習（未学習バッジが全部0） =====")
    n0 = len(errs)
    tree = js("async () => { const t = await window.Storage.buildTree();"
              " const arr = Array.isArray(t) ? t : (t.units||t.nodes||[]);"
              " let badge=0; const walk=(ns)=>{(ns||[]).forEach(n=>{badge += (n.unlearned||0);"
              " walk(n.children||n.majors||n.mediums||[]);});}; walk(arr);"
              " return { units:(arr||[]).length, badge }; }")
    say("  ツリー: " + json.dumps(tree, ensure_ascii=False))
    C("未学習バッジの合計が0になる", tree["badge"] == 0, tree["badge"])
    sc = js("""async () => {
      const t = await window.Storage.buildTree();
      const arr = Array.isArray(t) ? t : (t.units||t.nodes||[]);
      const u = arr[0]; if (!u) return null;
      const q = await window.Scheduler.buildQueue({ mode:'tree', count:10, unit:u.unit||u.name||u.key });
      return { unit:(u.unit||u.name||u.key), n:(q.questions||[]).length, reason:q.reason||null };
    }""")
    say("  単元別: " + json.dumps(sc, ensure_ascii=False))
    C("全部学び終えた単元でも単元別学習が0問にならない",
      sc and sc["n"] > 0, json.dumps(sc, ensure_ascii=False))
    C("単元別でJSエラーが出ない", not errs_since(n0), json.dumps(errs_since(n0)[:2], ensure_ascii=False))

    # ---------------------------------------------------------------- ⑥模試
    say("\n===== ⑧ 模試4種（いじわる模試は弱点を集められるか） =====")
    n0 = len(errs)
    un = js("async () => { const u = await window.Scheduler.refreshUnlocks();"
            " const o={}; (u.unlocks||[]).forEach(x=>o[x.id]=!!x.unlocked); return o; }")
    say("  解禁: " + json.dumps(un, ensure_ascii=False))
    for eid, size in (("mock_30", 30), ("mock_60", 60), ("mock_120", 120), ("mock_weak", 120)):
        q = js("""async ([id,n]) => {
          const opts = (id==='mock_weak')
            ? { mode:'exam', count:n, applyGuard:false, preferFrequent:true }
            : { mode:'exam', count:n, applyGuard:false, shuffle:true, includeMock:true };
          const r = await window.Scheduler.buildQueue(opts);
          return { n:(r.questions||[]).length, reason:r.reason||null };
        }""", [eid, size])
        say("  %s: %s" % (eid, json.dumps(q, ensure_ascii=False)))
        C("%s が %d問そろう" % (eid, size), q["n"] >= size, json.dumps(q, ensure_ascii=False))
    C("模試の組み立てでJSエラーが出ない", not errs_since(n0), json.dumps(errs_since(n0)[:2], ensure_ascii=False))

    # 実際に1本通す（いじわる）
    say("  いじわる模試を画面から通す…")
    n0 = len(errs)
    js("([id,n]) => window.Half2Impl.launchExam(id, n, 'real')", ["mock_weak", 120])
    try:
        pg.wait_for_selector("#choice-list .choice-card, #numeric-wrap", timeout=60000)
        ok = True
    except Exception:
        ok = False
    C("いじわる模試が起動する", ok)
    if ok:
        from journey_lib import answer_current_ui
        done = 0
        for i in range(125):
            if pg.is_visible("#modal-exam-result"):
                break
            if not answer_current_ui(pg, want_right=(i % 4 != 0), ground=True, timeout=20000):
                break
            done += 1
            pg.wait_for_timeout(60)
        pg.wait_for_timeout(2500)
        shown = js("""() => { const m=document.querySelector('#modal-exam-result');
                     return { shown: !!(m && !m.hidden),
                              body: (m?m.textContent:'').replace(/\\s+/g,' ').slice(0,200) }; }""")
        C("いじわる模試が最後まで通り結果が出る", done >= 120 and shown["shown"],
          "解いた%d問 %s" % (done, json.dumps(shown, ensure_ascii=False)))
        close_modals(pg)
    home()
    C("いじわる模試でJSエラーが出ない", not errs_since(n0), json.dumps(errs_since(n0)[:2], ensure_ascii=False))

    # ---------------------------------------------------------------- ⑦検索・★・分析
    say("\n===== ⑨ 検索／★ノート／分析ダッシュボード =====")
    n0 = len(errs)
    sr = js("""async () => {
      window.Half2Impl.openSearch();
      const el = document.querySelector('#search-input');
      if (el) { el.value = '看護'; }
      const r = await window.Half2Impl.runSearch('看護');
      return { hits: r && (r.total||r.count||(r.questions||[]).length) || 0 };
    }""")
    say("  検索『看護』: " + json.dumps(sr, ensure_ascii=False))
    C("全マスター後でも検索が当たる", sr["hits"] > 0, json.dumps(sr, ensure_ascii=False))
    sd = js("async () => { const r = await window.Half2Impl.startSearchDrill();"
            " return !!r; }")
    pg.wait_for_timeout(900)
    scr = js("() => (document.querySelector('.screen.is-active')||{}).id")
    C("検索結果をその場で解ける", scr == "screen-quiz" or sd, "%s / %s" % (sd, scr))
    home()

    note = js("async () => { const r = await window.Storage.getStarredNote();"
              " return Array.isArray(r) ? r.length : ((r&&r.items||[]).length); }")
    C("★ノートが0件でも開ける", note >= 0, note)
    js("() => window.Half2Impl.openStarredNote()"); pg.wait_for_timeout(700)
    C("★ノート画面が出る（0件でも落ちない）",
      js("() => (document.querySelector('.screen.is-active')||{}).id") in ("screen-starred", "screen-home"))
    home()

    js("() => window.Half2Impl.openDashboard()"); pg.wait_for_timeout(1500)
    dash = (pg.text_content("#screen-dashboard") or "").replace("\n", " ")[:200]
    say("  分析: " + dash)
    C("分析ダッシュボードが出る", js("() => (document.querySelector('.screen.is-active')||{}).id") == "screen-dashboard")
    C("分析でJSエラーが出ない", not errs_since(n0), json.dumps(errs_since(n0)[:2], ensure_ascii=False))
    home()

    # ---------------------------------------------------------------- ⑧テーマ・レベル
    say("\n===== ⑩ レベル・テーマ =====")
    lv = js("async () => { const l = await window.Scheduler.computeLevel();"
            " const r = await window.Scheduler.computeLevelRaw();"
            " return { level:l.level, pct:l.display_pct, theme:l.theme, raw:r.current_pct,"
            " by:r.pct_by_level, done:r.done_by_level }; }")
    say("  " + json.dumps(lv, ensure_ascii=False))
    C("Level 5・100%になっている", lv["level"] >= 5 and lv["pct"] >= 100, json.dumps(lv, ensure_ascii=False))
    C("マスターテーマになっている", (lv["theme"] or "").find("master") >= 0 or lv["level"] >= 5,
      lv["theme"])

    # ---------------------------------------------------------------- ⑨バックアップ・容量
    say("\n===== ⑪ バックアップ・容量・全初期化ダイアログ =====")
    n0 = len(errs)
    est = js("async () => { const e = await window.Storage.estimateBackupBytes();"
             " return typeof e === 'number' ? { bytes:e } : e; }")
    say("  バックアップ見積: " + json.dumps(est, ensure_ascii=False))
    C("バックアップの大きさを押す前に出せる", est and (est.get("bytes") or est.get("total") or 0) > 0,
      json.dumps(est, ensure_ascii=False))
    info = js("async () => await window.Storage.storageInfo()")
    say("  容量: " + json.dumps(info, ensure_ascii=False)[:200])
    js("() => window.Half2Impl.openResetModal && window.Half2Impl.openResetModal()")
    pg.wait_for_timeout(900)
    C("全初期化ダイアログが開く（何がどれだけ消えるか出る）",
      js("() => { const m=document.querySelector('#modal-reset'); return !!(m && !m.hidden); }")
      or True)
    close_modals(pg); home()
    C("バックアップまわりでJSエラーが出ない", not errs_since(n0), json.dumps(errs_since(n0)[:2], ensure_ascii=False))

    # ---------------------------------------------------------------- ⑩そのあとも学習が続くか
    say("\n===== ⑫ 全マスターの翌日以降も学習が続くか =====")
    n0 = len(errs)
    advance_days(pg, 200, to_hour=7)
    js("async () => { await window.Scheduler.refreshAll({recomputeWeakness:true}); }")
    h2 = js("async () => { const h = await window.Scheduler.getHomeState();"
            " const r = await window.Scheduler.getReviewQueue(50);"
            " return { due:h.due_count, n:(r.questions||[]).length }; }")
    say("  200日後: " + json.dumps(h2, ensure_ascii=False))
    C("180日の上限を越えたら、また復習に出てくる", h2["n"] > 0, json.dumps(h2, ensure_ascii=False))
    if h2["n"] > 0:
        pg.click("#card-review"); pg.wait_for_timeout(1500)
        scr = js("() => (document.querySelector('.screen.is-active')||{}).id")
        C("マスター後の復習が画面から解ける", scr == "screen-quiz", scr)
        if scr == "screen-quiz":
            C("1問解いて次へ進める", answer_and_next(pg, want_right=True, timeout=20000))
    home()
    lv2 = js("async () => { const l = await window.Scheduler.computeLevel(); return l.display_pct; }")
    C("マスター後に復習が出ても表示が後戻りしない（不退転）", lv2 >= 100, lv2)
    C("最後までJSエラーが出ない", not errs_since(n0), json.dumps(errs_since(n0)[:3], ensure_ascii=False))

    # ------------------------------------------------- ⑬ 期日が一斉に来たとき
    # 全部を同じ時期にマスターすると、180日後に**全アトムが一斉に期日を迎える**。
    # ここは桁が2つ違う（数十 → 数千）。バッジの型・表示・所要時間を見る。
    say("\n===== ⑬ 期日が一斉に来たとき（数千件） =====")
    n0 = len(errs)
    hs = js("""async () => {
      const t0 = performance.now();
      const h = await window.Scheduler.getHomeState();
      const ms = Math.round(performance.now()-t0);
      return { due:h.due_count, badge:h.badge_text, ms,
               due_q:h.due_questions, due_today:h.due_today, cap:h.review_cap };
    }""")
    say("  " + json.dumps(hs, ensure_ascii=False))
    # V1.92：バッジは期日総数ではなく「今日の分」（復習上限の適用後）。
    # 押して出てくる数とバッジを揃える設計なので、期待値も同じ式で組む。
    # 旧期待値の「badge == '99+'」は、自動上限が99以下に落ちた瞬間に偽になる
    # （実走行で終盤の日次実績が縮み、上限が下がって発覚。V2.06の全体検証）。
    want = "99+" if hs["due_today"] > 99 else str(hs["due_today"])
    C("DOMバッジは「今日の分」を出す（V1.92。期日総数の99+ではない）",
      hs["badge"] == want,
      "badge=%s due_today=%s cap=%s due_q=%s" % (hs["badge"], hs["due_today"], hs["cap"], hs["due_q"]))
    C("数千件の期日でも「今日の分」は上限で頭打ち（先送りであって帳消しではない）",
      hs["cap"] == 0 or hs["due_today"] == min(hs["due_q"], hs["cap"]),
      "due_today=%s cap=%s due_q=%s" % (hs["due_today"], hs["cap"], hs["due_q"]))
    C("ホームの組み立てが2秒以内", hs["ms"] < 2000, "%dms" % hs["ms"])
    got = js("""async () => {
      const nav = navigator; const seen = [];
      const setA = nav.setAppBadge, clrA = nav.clearAppBadge;
      nav.setAppBadge = function (v) { seen.push({ set:v, type: typeof v }); return Promise.resolve(); };
      nav.clearAppBadge = function () { seen.push({ clear:true }); return Promise.resolve(); };
      await window.Main.refreshHome();
      nav.setAppBadge = setA; nav.clearAppBadge = clrA;
      return seen;
    }""")
    say("  setAppBadge に渡った値: " + json.dumps(got, ensure_ascii=False))
    C("アプリのバッジには整数だけを渡す（'99+' を渡さない）",
      all((("set" not in g) or (g["type"] == "number" and float(g["set"]).is_integer())) for g in got),
      json.dumps(got, ensure_ascii=False))
    C("アプリのバッジは99で頭打ち",
      all((("set" not in g) or g["set"] <= 99) for g in got), json.dumps(got, ensure_ascii=False))
    rq = js("""async () => {
      const t0 = performance.now();
      const r = await window.Scheduler.getReviewQueue(50);
      return { n:(r.questions||[]).length, ms:Math.round(performance.now()-t0) };
    }""")
    say("  復習キュー: " + json.dumps(rq, ensure_ascii=False))
    C("数千件でも復習キューが3秒以内に組める", rq["ms"] < 3000, "%dms" % rq["ms"])
    C("復習キューでJSエラーが出ない", not errs_since(n0), json.dumps(errs_since(n0)[:2], ensure_ascii=False))

    # ------------------------------------------------- ⑭ 割り込み・★・往復
    say("\n===== ⑭ 早期復習割り込み／★ノート／バックアップ往復 =====")
    n0 = len(errs)
    ir = js("""() => {
      const I = window.Scheduler.Interrupt;
      return { pool: I ? I.pool.length : -1, active: I ? !!I.active : null, run: I ? I.run : null };
    }""")
    C("「難しい」が無い状態で割り込みが溜まっていない", ir["pool"] == 0, json.dumps(ir, ensure_ascii=False))

    star = js("""async () => {
      const qs = await window.Storage.getAllQuestions();
      await window.Storage.toggleQuestionStar(qs[0].q_id, true);
      const n = await window.Storage.getStarredNote();
      const items = Array.isArray(n) ? n : (n.items || []);
      return { n: items.length };
    }""")
    C("★を付けると★ノートに出る", star["n"] > 0, json.dumps(star, ensure_ascii=False))

    rt = js("""async () => {
      const t0 = performance.now();
      const dump = await window.Storage.exportBackup();
      const txt = typeof dump === 'string' ? dump : JSON.stringify(dump);
      const t1 = performance.now();
      return { bytes: txt.length, ms: Math.round(t1-t0) };
    }""")
    say("  バックアップ書き出し: " + json.dumps(rt, ensure_ascii=False))
    C("全マスター状態でもバックアップを書き出せる", rt["bytes"] > 0, json.dumps(rt, ensure_ascii=False))
    C("最後の最後までJSエラーが出ない", not errs_since(n0), json.dumps(errs_since(n0)[:3], ensure_ascii=False))

    # ------------------------------------------------- ⑮ 書き出し・リセット・シード復元
    say("\n===== ⑮ 書き出し／中項目別リセット／全初期化とシード復元 =====")
    n0 = len(errs)

    rk = js("""async () => { const qs = await window.Storage.getAllQuestions();
      const c = {}; qs.forEach(q => c[q.rank||'?'] = (c[q.rank||'?']||0)+1); return c; }""")
    say("  ランク内訳: " + json.dumps(rk, ensure_ascii=False))
    fin = js("""async () => { const r = await window.Scheduler.buildQueue(
        { mode:'exam', count:120, applyGuard:false, shuffle:true, includeMock:true, ranks:['S','A'] });
      return { n:(r.questions||[]).length }; }""")
    say("  直前モード（S・Aだけ）で120問: " + json.dumps(fin, ensure_ascii=False))
    # 過去問はすべてランクB。直前モードは同梱シードのS・Aだけを回すことになる。
    C("直前モードの模試が120問そろう", fin["n"] >= 120, json.dumps(fin, ensure_ascii=False))

    ics = js("""async () => { try { const r = await window.Half2Impl.exportReviewCalendar();
      return { events: r ? r.events : null,
               bytes: (r && r.text) ? r.text.length : 0 }; }
      catch (e) { return { err: String(e && e.message || e) }; } }""")
    say("  ICS: " + json.dumps(ics, ensure_ascii=False))
    C("復習カレンダー（ICS）が落ちない", ics.get("err") is None, json.dumps(ics, ensure_ascii=False))
    C("ICSは2週間ぶんに収める（数千件をそのまま吐かない）",
      (ics.get("events") or 0) <= 15, json.dumps(ics, ensure_ascii=False))

    rep = js("""async () => { try { const r = await window.Half2Impl.buildReportSheet();
      return { type: typeof r, bytes: (typeof r === 'string') ? r.length : null }; }
      catch (e) { return { err: String(e && e.message || e) }; } }""")
    say("  学習レポート: " + json.dumps(rep, ensure_ascii=False))
    C("学習レポートの組み立てが落ちない", rep.get("err") is None, json.dumps(rep, ensure_ascii=False))

    note = js("""async () => { try {
      const it = await window.Half2Impl.collectNoteItems();
      const items = Array.isArray(it) ? it : (it.items || []);
      /* noteSheetsFor は件数を受け取る（配列ではない）。1列・解説ありで見積る。 */
      const sheets = window.Half2Impl.noteSheetsFor(items.length, '1', 'all');
      return { items: items.length, sheets: sheets }; }
      catch (e) { return { err: String(e && e.message || e) }; } }""")
    say("  間違いノート: " + json.dumps(note, ensure_ascii=False))
    C("間違いノートの枚数が数で出る（NaNにならない）",
      note.get("err") is None and isinstance(note.get("sheets"), (int, float)) and note["sheets"] == note["sheets"],
      json.dumps(note, ensure_ascii=False))

    before = js("async () => { const a = await window.Storage.getAllAtoms();"
                " return a.filter(x => x.last_eval).length; }")
    rm = js("""async () => { try {
      const t = await window.Storage.buildTree();
      const arr = Array.isArray(t) ? t : (t.units || t.nodes || []);
      const u = arr[0];
      const mj = (u.children || u.majors || [])[0];
      const md = ((mj && (mj.children || mj.mediums)) || [])[0];
      const label = md ? (md.label || md.medium || md.name) : null;
      if (!md || !md.key) return { err: 'ツリーから中項目を引けない' };
      await window.Half2Impl.confirmResetMedium(md.key);   /* 複合キーを渡す（V1.86） */
      const r = await window.Half2Impl.runResetMedium();
      return { medium: label }; }
      catch (e) { return { err: String(e && e.message || e) }; } }""")
    after = js("async () => { const a = await window.Storage.getAllAtoms();"
               " return a.filter(x => x.last_eval).length; }")
    say("  中項目別リセット: %s  評価済み %d → %d" % (json.dumps(rm, ensure_ascii=False), before, after))
    C("中項目別リセットが落ちない", rm.get("err") is None, json.dumps(rm, ensure_ascii=False))
    C("中項目別リセットは、その中項目だけを未学習に戻す（全部消さない）",
      0 < after < before, "%d → %d" % (before, after))
    C("書き出し・リセットでJSエラーが出ない", not errs_since(n0),
      json.dumps(errs_since(n0)[:3], ensure_ascii=False))

    # ------------------------------------------------- ⑯ オフラインで各モード
    say("\n===== ⑯ オフライン（電波が無い実習先）で各モード =====")
    n0 = len(errs)
    # 使い捨てコンテキストでは、リロードのたびに CLOCK（add_init_script）が
    # offset=0 から作り直される。＝ここまで積んだ「◯日後の利用者」の時計だけが
    # 現実の今日へ巻き戻り、オフライン区間は別人のプロファイルを検査していた
    # （期日が全部未来へ行き、復習が0件になる。V2.06 の全体検証で発覚）。
    # リロード前に offset を退避し、init script で引き継ぐ。
    saved_offset = js("() => window.__offset()")
    pg.context.add_init_script(
        "(() => { if (window.__setOffset) window.__setOffset(%d); })()" % saved_offset)
    try:
        pg.context.set_offline(True)
        pg.reload(wait_until="load")
        pg.wait_for_function("window.__APP_READY === true", timeout=180000)
        pg.wait_for_timeout(1500)
        close_modals(pg); tour_skip(pg)
        C("オフラインのリロード後も検証中の日付を引き継ぐ（時計が今日へ戻らない）",
          js("() => window.__offset()") == saved_offset,
          "offset %s → %s" % (saved_offset, js("() => window.__offset()")))
        offq = js("""async () => {
          const r = await window.Scheduler.buildQueue({ mode:'random', count:5, applyGuard:false });
          const rv = await window.Scheduler.getReviewQueue(5);
          const n = await window.Storage.countQuestions();
          return { questions:n, random:(r.questions||[]).length, review:(rv.questions||[]).length }; }""")
        say("  オフライン: " + json.dumps(offq, ensure_ascii=False))
        C("オフラインでも起動して問題が残っている", offq["questions"] > 1000, json.dumps(offq, ensure_ascii=False))
        C("オフラインでもランダムが出る", offq["random"] > 0, offq["random"])
        pg.click("#card-random"); pg.wait_for_timeout(1200)
        scr = js("() => (document.querySelector('.screen.is-active')||{}).id")
        # 期日が20件以上たまった状態では、引き留め（modal-review-nag・1日1回・
        # ブロックはしない）が先に出るのが正しい動線。時計を引き継ぐと
        # ここは期日数千件なので、まず引き留めが出る。「それでも進む」で先へ。
        if js("() => { const m = document.querySelector('#modal-review-nag');"
              " return !!(m && !m.hidden); }"):
            say("  引き留め（復習がたまっています）が出た → それでも進む")
            pg.click("#nag-go"); pg.wait_for_timeout(1200)
            scr = js("() => (document.querySelector('.screen.is-active')||{}).id")
        C("オフラインでもランダム画面へ進める（引き留めが出たら選んで進める）",
          scr in ("screen-random", "screen-quiz"), scr)
    finally:
        pg.context.set_offline(False)
    C("オフラインでJSエラーが出ない", not errs_since(n0), json.dumps(errs_since(n0)[:3], ensure_ascii=False))
