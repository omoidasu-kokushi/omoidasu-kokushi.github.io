#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.58 検証：規模（2,500問・11,800肢）での速度と正しさ"""
import json, os, sys, io, time
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))
def read(f): return io.open(os.path.join(APP, f), encoding="utf-8").read()

st, sc = read("storage.js"), read("scheduler.js")


def code(src):
    """注釈を落として、コードだけを残す。
    注釈に書いた「以前は seq = seq.then(...) だった」という説明文を
    コードだと誤読して、直したはずのものを NG と報告した（実際にやった）。"""
    import re as _re
    src = _re.sub(r"/\*.*?\*/", "", src, flags=_re.S)
    return _re.sub(r"(?m)^\s*//.*$", "", src)


def body(src, name):
    """関数の本体だけを波括弧の対応で切り出す。
    "function " で split する雑なやり方だと、入れ子の無名関数で切れてしまい、
    見ているつもりの範囲を見ていない（実際にそれで誤検知した）。"""
    i = src.index("function " + name + "(")
    i = src.index("{", i)
    depth, j = 0, i
    while j < len(src):
        if src[j] == "{": depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0: return src[i:j + 1]
        j += 1
    raise AssertionError("body not closed: " + name)


ok("全アトムの読みを配れる小道具がある", "function useAtoms" in sc)

_home = code(body(sc, "getHomeState"))
ok("ホーム描画は全アトムを1回だけ読む", _home.count("getAllAtoms()") == 1, str(_home.count("getAllAtoms()")))
ok("読んだ配列を集計側へ配っている",
   "computeLevel(allAtoms)" in _home and "refreshUnlocks(allAtoms)" in _home)
ok("未学習の数とリストを配列から作っている（索引をもう一度引かない）",
   "S.countUnlearned()" not in _home and "S.getUnlearnedAtoms()" not in _home)

_all = code(body(sc, "refreshAll"))
ok("全体再集計も全アトムを1回だけ読む", _all.count("getAllAtoms()") == 1, str(_all.count("getAllAtoms()")))

for fn in ("updateAtomsBulk", "updateQuestionsBulk"):
    b = code(body(st, fn))
    ok("一括更新を直列にしていない（%s）" % fn,
       "seq = seq.then" not in b and "Promise.all(ids.map(" in b)

_save = code(body(st, "saveConceptScores"))
ok("概念スコアはタグごとに get していない", "STORE.CONCEPT].get(" not in _save)
ok("概念スコアは変わっていない行を書かない", "writes.push(rec)" in _save)

_weak = code(body(sc, "recomputeWeakness"))
ok("弱点の書き戻しを1本にまとめている", "updateAtomsBulk(patches)" in _weak)

# 取り込みのチャンクは【わざと】直列。まとめて1本にすると巨大な
# トランザクションを抱えることになる。ここが並列化されていたら誤り。
ok("取り込みのチャンクは直列のまま（巨大トランザクションを避ける）",
   "seq = seq.then" in code(body(st, "persistImportPayload")))

# 規模の目安（この環境での実測値。極端に遅くなったら気づくための線）
BUDGET_MS = { "getHomeState": 900, "buildQueue random": 700, "buildQueue exam120": 900,
              "buildDashboard": 900, "refreshAll": 2500, "boot": 12000 }

GEN = """(n) => {
  const units = ['必修問題','人体の構造と機能','疾病の成り立ち','健康支援と社会保障','基礎看護学',
                 '成人看護学','老年看護学','小児看護学','母性看護学','精神看護学','在宅看護論','看護の統合と実践'];
  const qs = [];
  for (let i = 0; i < n; i++) {
    qs.push({ q_id:'SCALE_'+i, unit:units[i%units.length], major:'M'+(i%120), medium:'D'+(i%450),
      sub_item:'S'+(i%1800), rank:'SABC'[i%4], question_type:'single', select_count:1,
      pool:(i%5===0)?'mock':'main',
      source:(i%5===0)?null:('第11'+(i%5)+'回 午前問'+(i%90)),
      stem:'規模検証用の問題 '+i+'。'+'あ'.repeat(60),
      overall_explanation:'解説'.repeat(80),
      atoms:[0,1,2,3].map(k=>({ text:'選択肢'+k+'あ'.repeat(20), is_correct:k===0,
        explanation:'肢の解説'.repeat(20), tags:['#タグ'+((i+k)%74)] })) });
  }
  return JSON.stringify(qs);
}"""


def _external(t):
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t)


def runtime_checks():
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox"])
        pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append("console:" + m.text)
              if m.type == "error" and not _external(m.text) else None)
        t0 = time.time()
        pg.goto(URL, wait_until="load")
        pg.wait_for_function("window.__APP_READY === true", timeout=40000)
        pg.wait_for_timeout(1000)
        try: pg.click("#welcome-start", timeout=2500)
        except Exception: pass
        pg.wait_for_timeout(400)

        rep = pg.evaluate("""async (j) => {
          const r = await window.Storage.importText(j);
          return { ok:r.ok, imported:r.imported, atoms:r.atoms, main:r.pool_main, mock:r.pool_mock };
        }""", pg.evaluate(GEN, 2500))
        ok("2,500問を取り込める", rep["imported"] == 2500, json.dumps(rep))
        ok("肢は10,000件", rep["atoms"] == 10000, json.dumps(rep))

        seeded = pg.evaluate("""async () => {
          const S = window.Storage;
          const atoms = await S.getAllAtoms();
          const now = Date.now(), day = 86400000;
          const logs = [], patches = {};
          for (let i = 0; i < 3000 && i < atoms.length; i++) {
            const a = atoms[i], at = now - (i % 60) * day;
            logs.push({ atom_id:a.atom_id, answered_at:at, eval:'normal', is_correct:true,
                        schedule_updated:true, interval_code:'1d' });
            patches[a.atom_id] = { answer_count:1, correct_count:1, last_eval:'normal',
              last_answered_at:at, due_date: now - 1000, interval_code:'1d', _unlearned:0 };
          }
          await S.replaceAllLogs(logs);
          await S.updateAtomsBulk(patches);
          return { atoms: atoms.length, logs: logs.length };
        }""")
        ok("肢が1万件を超えた状態を作れた", seeded["atoms"] > 10000, json.dumps(seeded))

        def bench(label, expr, runs=3):
            best = 1e9
            for _ in range(runs):
                t = time.time()
                pg.evaluate(expr)
                best = min(best, (time.time() - t) * 1000)
            return best

        ms = bench("h", "async () => { await window.Scheduler.getHomeState(); }")
        ok("ホーム描画が %d ms 以内（実測 %d ms）" % (BUDGET_MS["getHomeState"], ms),
           ms < BUDGET_MS["getHomeState"], "%d ms" % ms)

        ms = bench("r", "async () => { await window.Scheduler.buildQueue({mode:'random',count:20}); }")
        ok("ランダムの組み立てが %d ms 以内（実測 %d ms）" % (BUDGET_MS["buildQueue random"], ms),
           ms < BUDGET_MS["buildQueue random"], "%d ms" % ms)

        ms = bench("e", """async () => { await window.Scheduler.buildQueue({mode:'exam',count:120,
                    applyGuard:false, shuffle:true, includeMock:true,
                    mix:{fresh:0.25,faded:0.45,unseen:0.30}}); }""")
        ok("120問模試の組み立てが %d ms 以内（実測 %d ms）" % (BUDGET_MS["buildQueue exam120"], ms),
           ms < BUDGET_MS["buildQueue exam120"], "%d ms" % ms)

        ms = bench("d", "async () => { await window.Scheduler.buildDashboard({level:'sub_item'}); }")
        ok("分析ダッシュボードが %d ms 以内（実測 %d ms）" % (BUDGET_MS["buildDashboard"], ms),
           ms < BUDGET_MS["buildDashboard"], "%d ms" % ms)

        ms = bench("a", "async () => { await window.Scheduler.refreshAll({recomputeWeakness:true}); }", runs=2)
        ok("全体再集計が %d ms 以内（実測 %d ms）" % (BUDGET_MS["refreshAll"], ms),
           ms < BUDGET_MS["refreshAll"], "%d ms" % ms)

        # 速くしても答えが変わっていないこと
        r = pg.evaluate("""async () => {
          const S = window.Storage, K = window.Scheduler;
          const h = await K.getHomeState();
          const byIndex = await S.countUnlearned();
          const listLen = (await S.getUnlearnedAtoms()).length;
          const un = await K.refreshUnlocks();
          const lv = await K.computeLevel();
          const atoms = await S.getAllAtoms();
          const un2 = await K.refreshUnlocks(atoms);      // 配った場合
          const lv2 = await K.computeLevel(atoms);
          return { homeUnlearned: h.unlearned_atoms_all, byIndex, listLen,
                   a: un.stats.answered_atoms, b: un2.stats.answered_atoms,
                   c: lv.stats.total_atoms, d: lv2.stats.total_atoms };
        }""")
        ok("未学習の数が索引の集計と一致する（読みをまとめても答えが変わらない）",
           r["homeUnlearned"] == r["byIndex"] == r["listLen"], json.dumps(r))
        ok("アトムを配っても解禁の集計が変わらない", r["a"] == r["b"], json.dumps(r))
        ok("アトムを配ってもレベルの集計が変わらない", r["c"] == r["d"], json.dumps(r))

        # 概念スコアは書き直しても同じ値になる
        r = pg.evaluate("""async () => {
          const S = window.Storage, K = window.Scheduler;
          const a = await K.recomputeConceptScores();
          const rows1 = await S.getConceptStats();
          const b = await K.recomputeConceptScores();     // 2回目は書くものが無いはず
          const rows2 = await S.getConceptStats();
          const same = rows1.length === rows2.length && rows1.every((x, i) =>
            x.tag === rows2[i].tag && x.score === rows2[i].score
            && x.evaluated_count === rows2[i].evaluated_count);
          return { n1: Object.keys(a).length, n2: Object.keys(b).length,
                   rows: rows1.length, same };
        }""")
        ok("概念スコアは2回流しても同じ結果になる", r["same"] is True, json.dumps(r))

        # 起動しなおしても壊れない
        t = time.time()
        pg.reload(wait_until="load")
        pg.wait_for_function("window.__APP_READY === true", timeout=60000)
        boot = (time.time() - t) * 1000
        ok("2,500問でも %d ms 以内に起動する（実測 %d ms）" % (BUDGET_MS["boot"], boot),
           boot < BUDGET_MS["boot"], "%d ms" % boot)

        ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
        br.close()


runtime_checks()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAK" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
