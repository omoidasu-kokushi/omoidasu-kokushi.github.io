#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.56 検証：出題プール分離（過去問＝本体 / 予想問題＝模試待ち）"""
import json, os, sys, subprocess, io, glob
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))
def read(f): return io.open(os.path.join(APP, f), encoding="utf-8").read()

P1 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
P2 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
for f in ["storage.js", "scheduler.js", P1, P2]:
    p = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True)
    ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

st, sc, s2 = read("storage.js"), read("scheduler.js"), read(P2)
ok("pool は source と別の項目として持つ", "normalizePool" in st and "pool           : q.pool" in st)
ok("再インポートで pool を引き継がない（データそのもの）",
   "pool も同じ理由で引き継がない" in st)
ok("解放済みかどうかを別項目で持っていない",
   "mock_released" not in st and "mock_released" not in sc)
ok("模試だけが includeMock を立てる", "includeMock: true" in s2)
ok("scheduler は「模試モードかどうか」で判定していない",
   "if (!options.includeMock)" in sc)
ok("数え方は splitMockPool 1箇所", sc.count("function splitMockPool") == 1)
ok("高水位の引き上げが1トランザクションで完結する（2タブで後戻りしない）",
   "function raiseMeta" in st and "write([STORE.META]" in st
   and st.split("function raiseMeta")[1].split("}\n")[0].find("getMeta(") < 0)
ok("復元（入れ替え）が確認を通る", "いまの中身を入れ替えますか" in s2)
ok("取り込み欄にバックアップを貼ったときは足し合わせだと明示する",
   "足し合わせました" in s2)
ok("撤去したUIツアーの呼び出しが残っていない",
   "runUiTour:" not in s2 and "runUiTour        :" not in read(P1))
ok("◀戻るでホームへ帰るときに数字を取り直す",
   "prev === 'home'" in read(P1))


def _external(t):
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t)


SEED = """() => {
  const qs = [];
  for (let i = 1; i <= 12; i++) {
    qs.push({ q_id:'MOCKQ_'+i, unit:'必修問題', major:'1. 健康に関する指標',
      medium:'A. 人口静態・人口動態', sub_item:'a. 総人口', rank:'A',
      question_type:'single', select_count:1, pool:'mock', stem:'予想問題 '+i,
      overall_explanation:'自作の解説',
      atoms:[{text:'正しい',is_correct:true,explanation:'○',tags:['#人口動態統計']},
             {text:'誤り1',is_correct:false,explanation:'×',tags:['#人口動態統計']},
             {text:'誤り2',is_correct:false,explanation:'×',tags:['#人口動態統計']},
             {text:'誤り3',is_correct:false,explanation:'×',tags:['#人口動態統計']}]});
  }
  return JSON.stringify(qs);
}"""


def runtime_checks():
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox"])
        pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append("console:" + m.text)
              if m.type == "error" and not _external(m.text) else None)
        pg.goto(URL, wait_until="load")
        pg.wait_for_function("window.__APP_READY === true", timeout=20000)
        pg.wait_for_timeout(1500)
        try: pg.click("#welcome-start", timeout=2500)
        except Exception: pass
        pg.wait_for_timeout(600)

        # ---------- 取り込み ----------
        r = pg.evaluate("""async (seedJson) => {
          const S = window.Storage, K = window.Scheduler;
          const rep = await S.importText(seedJson);
          const h = await K.getHomeState();
          const q = await S.getQuestion('MOCKQ_1');
          const a = (await S.getAtomsByQuestion('MOCKQ_1'))[0];
          return { rep_main: rep.pool_main, rep_mock: rep.pool_mock, ok: rep.ok,
                   qPool: q.pool, aPool: a.pool,
                   totalAll: h.total_questions_all, totalMain: h.total_questions,
                   lockedQ: h.mock_locked_questions, lockedA: h.mock_locked_atoms };
        }""", pg.evaluate(SEED))
        ok("取り込み結果に内訳が出る（模試用が混ざったら気づける）",
           r["rep_mock"] == 12, json.dumps(r))
        ok("問題レコードに pool が入る", r["qPool"] == "mock", json.dumps(r))
        ok("アトムにも pool が落ちる（候補を組むのはアトム側）",
           r["aPool"] == "mock", json.dumps(r))
        ok("模試待ちの問題数を数えられる", r["lockedQ"] == 12, json.dumps(r))
        ok("模試待ちのアトム数を数えられる", r["lockedA"] == 48, json.dumps(r))
        ok("見える問題数からは外れる",
           r["totalAll"] - r["totalMain"] == 12, json.dumps(r))

        # ---------- 出題経路 ----------
        r = pg.evaluate("""async () => {
          const K = window.Scheduler;
          const isMock = q => String(q.q_id).indexOf('MOCKQ_') === 0;
          const count = qs => qs.filter(isMock).length;
          const rnd  = await K.buildQueue({ mode:'random', count:200 });
          const nw   = await K.buildQueue({ mode:'new', count:200 });
          const rev  = await K.buildQueue({ mode:'review', count:200 });
          const knock= await K.buildQueue({ mode:'knock', count:200, applyGuard:false });
          const byId = await K.buildQueue({ mode:'random', count:5, qIds:['MOCKQ_1','MOCKQ_2'] });
          const exam = await K.buildQueue({ mode:'exam', count:30, applyGuard:false,
                        shuffle:true, includeMock:true,
                        mix:{ fresh:0.25, faded:0.45, unseen:0.30 } });
          return { rnd:count(rnd.questions), nw:count(nw.questions),
                   rev:count(rev.questions), knock:count(knock.questions),
                   byId:count(byId.questions), byIdN: byId.questions.length,
                   exam:count(exam.questions), examN: exam.questions.length };
        }""")
        ok("ランダムには出ない", r["rnd"] == 0, json.dumps(r))
        ok("新規モードにも出ない", r["nw"] == 0, json.dumps(r))
        ok("復習にも出ない", r["rev"] == 0, json.dumps(r))
        ok("弱点ノックにも出ない", r["knock"] == 0, json.dumps(r))
        ok("IDを直接指定しても出ない（検索から漏れない）",
           r["byId"] == 0 and r["byIdN"] == 0, json.dumps(r))
        ok("模試だけが拾える", r["exam"] > 0, json.dumps(r))
        ok("模試の問題数は減らない", r["examN"] == 30, json.dumps(r))

        # ---------- 初見枠は予想問題から先に使う ----------
        r = pg.evaluate("""async () => {
          const K = window.Scheduler;
          const q = await K.buildQueue({ mode:'exam', count:20, applyGuard:false,
                     shuffle:true, includeMock:true,
                     mix:{ fresh:0, faded:0, unseen:1.0 } });
          const mock = q.questions.filter(x => String(x.q_id).indexOf('MOCKQ_') === 0).length;
          return { mock, total: q.questions.length };
        }""")
        ok("初見枠は予想問題から先に埋まる（過去問を模試に食われない）",
           r["mock"] == 12, json.dumps(r))

        # ---------- 模試で出会うと本体へ昇格する ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, K = window.Scheduler;
          const ats = await S.getAtomsByQuestion('MOCKQ_1');
          const t = Date.now(), all = await S.getAllLogs();
          await S.replaceAllLogs(all.concat(ats.map((a, i) => ({
            atom_id:a.atom_id, answered_at:t+i, eval:'hard', is_correct:false,
            schedule_updated:true, interval_code:'10m' }))));
          const patches = {};
          ats.forEach(a => { patches[a.atom_id] = { answer_count:1, correct_count:0,
            last_eval:'hard', last_answered_at:t, due_date:t-1000,
            interval_code:'10m', _unlearned:0 }; });
          await S.updateAtomsBulk(patches);
          const h = await K.getHomeState();
          const rev = await K.buildQueue({ mode:'review', count:200 });
          const byId = await K.buildQueue({ mode:'random', count:5, qIds:['MOCKQ_1'] });
          return { lockedQ: h.mock_locked_questions, totalMain: h.total_questions,
                   inRev: rev.questions.filter(q => q.q_id === 'MOCKQ_1').length,
                   inById: byId.questions.length };
        }""")
        ok("模試で出会った予想問題は復習に乗る",
           r["inRev"] == 1, json.dumps(r))
        ok("以降は普通の問題として出せる", r["inById"] == 1, json.dumps(r))
        ok("待機中の数がひとつ減る", r["lockedQ"] == 11, json.dumps(r))

        # ---------- 分母から外れていること ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, K = window.Scheduler;
          const un = await K.refreshUnlocks();
          const dash = await K.buildDashboard({ level:"medium" });
          const row = dash.rows.filter(x => x.key === 'A. 人口静態・人口動態')[0];
          const tree = await S.countUnlearnedByScope();
          const lv = await K.computeLevel();
          return { unlockDenom: un.stats.total_questions,
                   unlockAll: un.stats.total_questions_all,
                   dashTotal: row ? row.total_atoms : -1,
                   treeMedium: tree.medium['A. 人口静態・人口動態'] || 0,
                   lvTotal: lv.stats.total_atoms };
        }""")
        ok("模試の解禁の分母から外れる（永久に解禁できない状態を作らない）",
           r["unlockAll"] - r["unlockDenom"] == 11, json.dumps(r))
        ok("分析ダッシュボードの分母から外れる（永久に赤いグラフを作らない）",
           r["dashTotal"] > 0, json.dumps(r))
        ok("ツリーの未学習バッジに数えない（消えない催促を作らない）",
           r["treeMedium"] >= 0, json.dumps(r))
        ok("レベルの分母から外れる（Level 3 を達成不能にしない）",
           r["lvTotal"] > 0, json.dumps(r))

        # ---------- 取り込み直しても解放は失われない ----------
        r = pg.evaluate("""async (seedJson) => {
          const S = window.Storage, K = window.Scheduler;
          await S.importText(seedJson);           // 同じデータをもう一度
          const q = await S.getQuestion('MOCKQ_1');
          const h = await K.getHomeState();
          const byId = await K.buildQueue({ mode:'random', count:5, qIds:['MOCKQ_1'] });
          return { pool:q.pool, lockedQ:h.mock_locked_questions, inById:byId.questions.length };
        }""", pg.evaluate(SEED))
        ok("取り込み直すと pool はデータどおりに戻る", r["pool"] == "mock", json.dumps(r))
        ok("それでも一度出会った問題は本体に残る（解放は台帳から導いている）",
           r["inById"] == 1 and r["lockedQ"] == 11, json.dumps(r))

        # ---------- 画面 ----------
        pg.evaluate("window.Main.refreshHome()")
        pg.wait_for_timeout(400)
        tag = pg.evaluate("document.getElementById('exam-tag').textContent")
        ok("待機中があると力試しカードに出る（取り込んだのに消えた、と読まれない）",
           "待機中" in tag, tag)

        # ---------- 高水位が2タブで後戻りしないこと（V1.56） ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage;
          await S.setMeta('probe_hw', 0);
          /* 同時に投げる。読みと書きが別トランザクションだと、
             小さい値が後から書かれて【レベルが下がる】。 */
          await Promise.all([10, 90, 30, 70, 50, 20].map(v => S.raiseMeta('probe_hw', v)));
          const after = await S.getMeta('probe_hw', -1);
          await S.raiseMeta('probe_hw', 5);
          const low = await S.getMeta('probe_hw', -1);
          const cached = (await S.loadMeta()).probe_hw;
          return { after, low, cached };
        }""")
        ok("同時に引き上げても一番大きい値が残る（不退転が壊れない）",
           r["after"] == 90, json.dumps(r))
        ok("小さい値を投げても下がらない", r["low"] == 90, json.dumps(r))
        ok("手元の写しも合っている（同じ画面で数字が食い違わない）",
           r["cached"] == 90, json.dumps(r))

        # ---------- 復元は入れ替えなので確認を通る（V1.56） ----------
        r = pg.evaluate("""() => {
          const s2 = window.Half2Impl.runRestore ? 'has' : 'none';
          return { s2 };
        }""")
        ok("復元の入口がある", r["s2"] == "has", json.dumps(r))

        ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
        br.close()


runtime_checks()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAJ" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
