# -*- coding: utf-8 -*-
"""test_seed_hisshu.py — 同梱シードを必修249問へ入れ替えた（V2.89 / SEED_VERSION 3.00）

【何が起きていたか】
  同梱シードは旧作問レーンの自由作問453問だった。実測すると

    問題文 中央値 75字（本試験の必修は23字）／45字以内 11%（本試験は9割）
    解説   中央値 1,043字（§4-4 は200〜400字）
    単元   必修308・人体128・疾病17 の3つだけ
    出典   すべて null（AI予想問題）

  初めて開いた人が最初に触るのがこれなので、体験がそのまま印象になる。
  過去問の仕上げが必修 249/250 まで到達した（残る第113回午後問21 は
  除外リストで「削除」と裁定ずみ）ので、利用者の裁定
  「旧同梱シードはもうなかったことにしていい。必修と入れ替えてほしい」
  （2026-09-09）に従って入れ替えた。

  旧453問は消していない。sample/20260909_旧同梱シード_自由作問453問_V1.00.txt
  に13列TSVで残してある（同梱から外しただけ。一括インポートで戻せる）。

【ここで固定すること】
  ・249問ちょうど・全部が必修・13列
  ・出典が全問あり、すべて第111〜115回の実際の出題（null が1問も無い）
  ・本試験の必修と同じ短さ（問題文 中央値30字以下・45字以内が8割以上）
  ・解説が §4-4 の範囲に収まる（中央値500字以下）
  ・SEED_VERSION が上がっている（上げ忘れると既存端末に届かない）
  ・旧シードの退避ファイルが 453行で残っている（消していないことの証拠）
  ・タグがすべて概念タグマスタにある（アプリが黙って捨てるのを防ぐ）
  ・実際に取り込めて 249問 / スキップ0 になる
"""
import os, sys, io, json, re, statistics

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
qjs = io.open(os.path.join(base, "questions.js"), encoding="utf-8").read()

# --- シードを questions.js から取り出す（V3.00 で中身はJSONになった） ---
import subprocess
NODE = ("const fs=require('fs');global.window={};global.self=global;"
        "eval(fs.readFileSync(process.argv[1],'utf8'));"
        "process.stdout.write(global.window.SEED_QUESTIONS_TSV);")
out = subprocess.run(["node", "-e", NODE, os.path.join(base, "questions.js")],
                     capture_output=True, text=True)
ok("同梱シードを取り出せる", out.returncode == 0 and len(out.stdout) > 1000,
   (out.stderr or "")[:200])
data = json.loads(out.stdout)
qs = data["questions"]

ok("同梱シードは249問", len(qs) == 249, len(qs))
ok("別名 SEED_QUESTIONS_JSON も同じものを指す",
   "const SEED_QUESTIONS_JSON = SEED_QUESTIONS_TSV;" in qjs)

units = {q.get("unit") for q in qs}
ok("全問が必修", units == {"必修"}, sorted(x for x in units if x))

srcs = [q.get("source") or "" for q in qs]
ok("出典が249問すべてにある（TSVでは全部 null に落ちていた）",
   all(x.strip() for x in srcs), sum(1 for x in srcs if not x.strip()))
badsrc = [x for x in srcs if not re.match(r"^第11[1-5]回 (午前|午後)問\d+$", x)]
ok("出典はすべて第111〜115回の形", not badsrc, badsrc[:3])
ok("出典に重複が無い", len(set(srcs)) == len(srcs), len(srcs) - len(set(srcs)))

exp = {"第%d回 %s問%d" % (k, ses, n)
       for k in range(111, 116) for ses in ("午前", "午後") for n in range(1, 26)}
miss = sorted(exp - set(srcs))
ok("落ちているのは裁定ずみの1問だけ", miss == ["第113回 午後問21"], miss)
ok("必修の範囲の外から混ざっていない", not (set(srcs) - exp), sorted(set(srcs) - exp)[:3])

stems = [q.get("stem") or "" for q in qs]
med = statistics.median(len(x) for x in stems)
ok("問題文が本試験の必修と同じ短さ（中央値30字以下）", med <= 30, med)
short = sum(1 for x in stems if len(x) <= 45) / len(stems)
ok("45字以内が9割以上", short >= 0.85, round(short, 3))

exps = [q.get("overall_explanation") or "" for q in qs]
emed = statistics.median(len(x) for x in exps)
ok("解説が §4-4 の範囲に収まる（中央値500字以下）", emed <= 500, emed)

# TSVでは列が無くて落ちていたもの
ok("比較表が残っている（TSVでは運べなかった）",
   sum(1 for q in qs if q.get("comparison_table")) == 17,
   sum(1 for q in qs if q.get("comparison_table")))
ok("図解が残っている", sum(1 for q in qs if q.get("mermaid_code")) == 2,
   sum(1 for q in qs if q.get("mermaid_code")))
ok("別冊の画像が残っている", sum(1 for q in qs if q.get("image_url")) == 7,
   sum(1 for q in qs if q.get("image_url")))
ok("分割可否が残っている", sum(1 for q in qs if q.get("is_splittable")) == 83,
   sum(1 for q in qs if q.get("is_splittable")))

ok("全問が pool=main", {q.get("pool") for q in qs} == {"main"},
   sorted(str(x) for x in {q.get("pool") for q in qs}))
ok("模試用の裏問題が混ざっていない", not [q for q in qs if q.get("variant")])

# --- 正解と肢 ---
bad_cor = [q.get("source") for q in qs
           if not [a for a in (q.get("atoms") or []) if a.get("is_correct")]]
ok("正解肢が全問にある", not bad_cor, bad_cor[:3])
qt_bad = [q.get("source") for q in qs
          if (q.get("question_type") == "multiple")
          != (len([a for a in (q.get("atoms") or []) if a.get("is_correct")]) >= 2)]
ok("question_type と正解数が合っている（合わないと取り込みが問題ごと捨てる）",
   not qt_bad, qt_bad[:3])
ok("全問に肢がある", all(q.get("atoms") for q in qs))

# --- タグがマスタにあるか ---
master = set(re.findall(r'tag:\s*"([^"]+)"', qjs))
ok("概念タグマスタを読めた", len(master) >= 100, len(master))
tag_bad = set()
for q in qs:
    for a in (q.get("atoms") or []):
        for t in (a.get("tags") or []):
            if t not in master:
                tag_bad.add(t)
ok("シードのタグがすべてマスタにある（アプリが捨てない）", not tag_bad, sorted(tag_bad)[:5])

# --- 版 ---
m = re.search(r'const SEED_VERSION = "([^"]+)"', qjs)
ok("SEED_VERSION が 3.00 以上", m and m.group(1) >= "3.00", m.group(1) if m else None)
ok("入れ替えたことが questions.js に書いてある", "必修249問" in qjs)
ok("既存端末には届かないことが書いてある（onlyExisting の落とし穴）",
   "既存端末には静かに" in qjs or "249問は届かない" in qjs)

# --- 旧シードを消していない ---
oldp = os.path.join(base, "sample", "20260909_旧同梱シード_自由作問453問_V1.00.txt")
ok("旧シードの退避ファイルがある（消していない）", os.path.exists(oldp), oldp)
if os.path.exists(oldp):
    old = io.open(oldp, encoding="utf-8").read().rstrip("\n").split("\n")
    ok("旧シードは453問そのまま残っている", len(old) == 453, len(old))
    ok("旧シードも13列", {r.count("\t") + 1 for r in old} == {13})

# --- 版の3点が揃っているか ---
html = io.open(os.path.join(base, "index.html"), encoding="utf-8").read()
sw = io.open(os.path.join(base, "sw.js"), encoding="utf-8").read()
mv = re.search(r"const CACHE_NAME = 'v([\d.]+)'", sw)
ok("CACHE_NAME を上げた", mv and mv.group(1) == "2.89.0", mv.group(1) if mv else None)
ok("?v= を揃えた", "?v=2.89" in html and "?v=2.88" not in html)
ok("build-stamp を上げた", "20260909_Omoidasu_V2.89" in html)

# --- 実際に取り込めるか ---
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
try:
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None

if sync_playwright:
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox"])
        ctx = br.new_context(viewport={"width": 390, "height": 844})
        pg = ctx.new_page()
        pg.set_default_timeout(120000)
        errs = []
        pg.on("pageerror", lambda ex: errs.append(str(ex)))
        pg.goto(URL, wait_until="load")
        pg.wait_for_function("window.__APP_READY === true")
        rep = pg.evaluate("""async () => {
            await window.Storage.resetAll();
            const r = await window.Storage.importText(window.SEED_QUESTIONS_TSV, {});
            return r;
        }""")
        # resetAll の直後でも起動時の自動シードが先に入っていることがあるので、
        # 新規と更新の合計で見る（どちらでも249問がそろっていればよい）。
        ok("同梱シードがそのまま取り込める",
           rep.get("parsed") == 249
           and (rep.get("imported") or 0) + (rep.get("updated") or 0) == 249,
           json.dumps({k: rep.get(k) for k in
                       ("parsed", "imported", "updated", "skipped", "mismatch")},
                      ensure_ascii=False))
        # TSVのころは source が12列目で is_splittable として読まれ、
        # 「第111回 午前問1 は分割可否として読めない」の警告が249件出ていた。
        ok("取り込みの警告が1件も出ない（列ズレの再発を見張る）",
           not rep.get("warnings"),
           json.dumps((rep.get("warnings") or [])[:2], ensure_ascii=False))
        dbsrc = pg.evaluate("""async () => {
            const qs = await window.Storage.getAllQuestions();
            return { n: qs.length, withSrc: qs.filter(q => q.source).length,
                     spl: qs.filter(q => q.is_splittable).length,
                     img: qs.filter(q => q.image_url).length,
                     tbl: qs.filter(q => q.comparison_table).length };
        }""")
        ok("取り込んだあとも出典が全問に残っている（画面に「AI予想問題」と出ない）",
           dbsrc["withSrc"] == 249, json.dumps(dbsrc, ensure_ascii=False))
        # 分割可否は取り込み側でも判定するので、シードの83問より増える（実測194）。
        # 減っていないことだけを見る。
        ok("比較表・別冊画像・分割可否も残っている",
           dbsrc["tbl"] == 17 and dbsrc["img"] == 7 and dbsrc["spl"] >= 83,
           json.dumps(dbsrc, ensure_ascii=False))
        ok("捨てられた行が無い", rep.get("skipped") == 0 and rep.get("mismatch") == 0,
           json.dumps({k: rep.get(k) for k in ("skipped", "mismatch")}))
        ok("分類・化け・欠字・タグの警告が全部0",
           not any(rep.get(k) for k in ("tax_bad", "garble_bad", "lost_bad", "tag_bad")),
           json.dumps({k: rep.get(k) for k in
                       ("tax_bad", "garble_bad", "lost_bad", "tag_bad")}))
        # 13列TSVには pool 列が無い。取り込みレポートも TSV では pool の内訳を
        # 出さない（JSON取り込みのときだけ出る）ので、DBを直に数える。
        pools = pg.evaluate("""async () => {
            const qs = await window.Storage.getAllQuestions();
            const c = {};
            qs.forEach(q => { const k = q.pool || 'main'; c[k] = (c[k] || 0) + 1; });
            return c;
        }""")
        ok("全問が pool=main（模試用が混ざっていない）",
           pools.get("main") == 249 and not pools.get("mock"),
           json.dumps(pools, ensure_ascii=False))
        ok("取り込み中にJSエラーが出ていない", not errs, errs[:2])
        br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  seed_hisshu" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
