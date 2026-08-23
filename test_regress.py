#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回帰：再インポートでユーザーデータが消えないこと（DESIGN_DECISIONS 1-3）
   ＋ バックアップ往復。storage.js は未変更だが、必ず通す。"""
import sys
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=15000)
    pg.wait_for_timeout(2000)

    base = pg.evaluate("""async () => ({
        q: await window.Storage.countQuestions(),
        a: await window.Storage.countAtoms() })""")
    # V1.42：シードを実データ457問に差し替えた。件数は questions.js の
    # SEED_QUESTIONS_TSV の行数で決まるので、ここでは固定値にしない。
    SEED_Q = base["q"]
    ok("シードが入っている（100問以上）", base["q"] >= 100 and base["a"] >= base["q"] * 2, str(base))

    # ユーザーデータを仕込む：★・メモ・進捗
    seeded = pg.evaluate("""async () => {
        const qs = await window.Storage.getAllQuestions();
        const atoms = await window.Storage.getAtomsByQuestion(qs[0].q_id);
        await window.Storage.toggleQuestionStar(qs[0].q_id);
        await window.Storage.toggleAtomStar(atoms[0].atom_id);
        await window.Storage.setMemo('atom', atoms[0].atom_id, '**自分の言葉**の解説');
        await window.Storage.setMemo('question', qs[0].q_id, '全体解説の書き換え');
        await window.Scheduler.applyQuestionEvaluations(qs[0].q_id,
          atoms.map(a => ({ atom_id: a.atom_id, eval: 'hard', is_correct: false })),
          { mode: 'random', sessionId: 'RG1', boundaryHour: 4 });
        const a0 = await window.Storage.getAtom(atoms[0].atom_id);
        return { qid: qs[0].q_id, aid: atoms[0].atom_id,
                 memo: a0.user_memo, star: a0.is_starred,
                 due: a0.due_date, cnt: a0.answer_count }; }""")
    ok("進捗・★・メモを書き込めた",
       seeded["memo"] and seeded["star"] and seeded["cnt"] == 1 and seeded["due"], str(seeded))

    # 同じシードTSVを再インポート
    reimp = pg.evaluate("""async () => {
        const rep = await window.Storage.importText(window.SEED_QUESTIONS_TSV);
        return { imported: rep.imported, updated: rep.updated, skipped: rep.skipped,
                 mismatch: rep.mismatch, atoms: rep.atoms }; }""")
    ok("再インポートは『更新』であって『追加』ではない",
       reimp["updated"] == SEED_Q and reimp["imported"] == 0, str(reimp))
    ok("正解検算でスキップされた行が無い", reimp["skipped"] == 0 and reimp["mismatch"] == 0, str(reimp))

    after = pg.evaluate("""async (s) => {
        const a = await window.Storage.getAtom(s.aid);
        const q = await window.Storage.getQuestion(s.qid);
        return { qc: await window.Storage.countQuestions(),
                 memo: a.user_memo, qmemo: q.user_memo, star: a.is_starred, qstar: q.is_starred,
                 due: a.due_date, cnt: a.answer_count, ev: a.last_eval }; }""",
        seeded)
    ok("問題数が増えていない", after["qc"] == SEED_Q, str(after["qc"]))
    ok("選択肢メモが消えていない", after["memo"] == "**自分の言葉**の解説", str(after["memo"]))
    ok("全体解説メモが消えていない", after["qmemo"] == "全体解説の書き換え", str(after["qmemo"]))
    ok("★（問題／選択肢）が消えていない", after["star"] and after["qstar"])
    ok("復習期日・評価・解答回数が消えていない",
       after["due"] == seeded["due"] and after["cnt"] == 1 and after["ev"] == "hard", str(after))

    # バックアップ往復
    rt = pg.evaluate("""async () => {
        const bk = await window.Storage.exportBackup();
        const json = JSON.stringify(bk);
        await window.Storage.resetProgressAll();
        const mid = (await window.Storage.getAllAtoms()).filter(a => a.answer_count > 0).length;
        const rep = await window.Storage.restoreBackup(JSON.parse(json), 'replace');
        const back = (await window.Storage.getAllAtoms()).filter(a => a.answer_count > 0).length;
        return { bytes: json.length, mid: mid, back: back,
                 q: rep.questions, a: rep.atoms }; }""")
    ok("進捗リセットで学習済みが0になる", rt["mid"] == 0, str(rt))
    ok("バックアップ復元で学習済みが戻る", rt["back"] > 0, str(rt))
    ok("復元件数がシードと一致", rt["q"] == SEED_Q and rt["a"] == base["a"], str(rt))
    # 問題データを丸ごと含むので、シードの量に比例する。
    # 1問あたり8KBを超えたら、どこかで不要なものを抱え込んでいる。
    ok("バックアップJSONの1問あたりが8KB未満（%d KB / %d問）"
       % (rt["bytes"] // 1024, SEED_Q), rt["bytes"] < SEED_Q * 8192, str(rt["bytes"]))

    # 弱点pt・スケジュールの基本
    sch = pg.evaluate("""() => {
        const a = { srs_step:0, interval_code:null, last_eval:null, answer_count:0 };
        return { hard: window.Scheduler.previewAllIntervals(a).hard.label,
                 normal: window.Scheduler.previewAllIntervals(a).normal.label,
                 easy: window.Scheduler.previewAllIntervals(a).easy.label,
                 masterLocked: !window.Scheduler.isMasterUnlocked(a) }; }""")
    ok("忘却間隔：初見 難=10分 / 普=1時間 / 易=30日",
       "10" in sch["hard"] and ("1" in sch["normal"]) and "30" in sch["easy"], str(sch))
    ok("マスターは初期グレーアウト", sch["masterLocked"])

    ok("ページ例外なし", not errs, " | ".join(errs[:3]))
    br.close()

fails = [r for r in R if not r[0]]
print("\n".join(("  ok  " if c else "  NG  ") + n + (("   << " + d) if (d and not c) else "")
                for c, n, d in R))
print("\n%d 項目中 %d 通過 / %d 失敗" % (len(R), len(R) - len(fails), len(fails)))
sys.exit(1 if fails else 0)
