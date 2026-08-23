#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.45 検証：JSON取り込みの正解数クロスチェック

  TSVには V1.43 で「Nつ選べ」の検算が入ったが、JSON経路には入っていなかった。
  同じデータでもTSVなら弾かれ、JSONなら素通りする、という差そのものが事故のもと。
  ここではJSON経路で次の4つが弾かれること、正しいデータは通ること、
  numeric は従来どおり検算されないことを確かめる。
"""
import json, os, sys, subprocess, re, io
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))
def read(f): return io.open(os.path.join(APP, f), encoding="utf-8").read()

# ---------------------------------------------------------------- 静的検査
p = subprocess.run(["node", "--check", os.path.join(APP, "storage.js")],
                   capture_output=True, text=True)
ok("syntax storage.js", p.returncode == 0, p.stderr.strip()[:200])

sto, idx, sw = read("storage.js"), read("index.html"), read("sw.js")
ok("crossCheckJsonQuestion がある", "function crossCheckJsonQuestion" in sto)
ok("crossCheckJsonQuestion を公開している", "crossCheckJsonQuestion :" in sto)
ok("importJsonPayload から呼んでいる",
   "crossCheckJsonQuestion(q, jsonQtype)" in sto)
ok("「しかありません」固定の文面が残っていない",
   "つしかありません（作問データを直してください）" not in sto)

# 共有ファイルの版が index と sw で揃っているか（§1-7）
_swq = dict(re.findall(r"'\./([^'?]+)\?v=([^']+)'", sw))
_idxq = dict(re.findall(r'"\./([^"?]+)\?v=([^"]+)"', idx))
ok("storage.js の版が index と sw で一致",
   _swq.get("storage.js") == _idxq.get("storage.js"),
   "sw=%s idx=%s" % (_swq.get("storage.js"), _idxq.get("storage.js")))
_c = re.search(r"CACHE_NAME = 'v(\d+)\.(\d+)\.(\d+)'", sw)
ok("sw CACHE_NAME が v1.36.0 以降",
   bool(_c) and tuple(int(x) for x in _c.groups()) >= (1, 36, 0),
   _c.group(0) if _c else "not found")


def _external(t):
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t)


# 検証用の1問を組み立てるヘルパ（JSに渡す）
BUILD = """
function mk(o) {
  var atoms = o.correct.map(function (c, i) {
    return { original_num: i + 1, is_correct: !!c,
             text: 'テスト肢' + (i + 1), statement: 'テスト肢' + (i + 1) + 'である。',
             explanation: '理由' + (i + 1), tags: ['#人口動態統計'] };
  });
  var q = {
    unit: 'JSON検算', target: null, rank: 'B',
    major: '1. 検算', medium: 'A. 検算', sub_item: 'a. ' + o.key,
    source: null, question_type: o.qtype, image_url: null,
    stem: o.stem, numeric_answer: o.numeric == null ? null : o.numeric,
    overall_explanation: '全体解説', comparison_table: null, mermaid_code: null,
    is_splittable: false, variant: null, origin_key: null, atoms: atoms
  };
  if (o.sc !== undefined) { q.select_count = o.sc; }
  return q;
}
"""


def runtime_checks():
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox"])
        ctx = br.new_context(viewport={"width": 390, "height": 844})
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append("console:" + m.text)
              if m.type == "error" and not _external(m.text) else None)
        pg.goto(URL, wait_until="load")
        pg.wait_for_function("window.__APP_READY === true", timeout=15000)
        pg.wait_for_timeout(1800)

        # ---------- 弾かれるべき4つ ----------
        bad = pg.evaluate("""async () => {
          %s
          const cases = [
            { key: 'pick',  label: '「2つ選べ」なのに正解1つ',
              q: mk({ key:'pick', qtype:'multiple', stem:'次のうち正しいものを2つ選べ。',
                      correct:[false,true,false,false], sc:2 }) },
            { key: 'single', label: 'single なのに正解2つ',
              q: mk({ key:'single', qtype:'single', stem:'正しいのはどれか。',
                      correct:[true,true,false,false] }) },
            { key: 'sc',    label: 'select_count と正解数が食い違う',
              q: mk({ key:'sc', qtype:'single', stem:'正しいのはどれか。',
                      correct:[true,false,false,false], sc:2 }) },
            { key: 'zero',  label: '正解が1つも無い',
              q: mk({ key:'zero', qtype:'single', stem:'正しいのはどれか。',
                      correct:[false,false,false,false] }) }
          ];
          const out = {};
          for (const c of cases) {
            const rep = await window.Storage.importText(JSON.stringify({ questions: [c.q] }));
            out[c.key] = { imported: rep.imported, skipped: rep.skipped,
                           mismatch: rep.mismatch,
                           errors: (rep.errors || []).map(e => e.message) };
          }
          return out;
        }""" % BUILD)

        for key, label, needle in [
            ("pick",   "「2つ選べ」なのに正解1つのJSONは取り込まない", "2つ選べ"),
            ("single", "single なのに正解2つのJSONは取り込まない",     "single"),
            ("sc",     "select_count と正解数が食い違うJSONは取り込まない", "select_count"),
            ("zero",   "正解が1つも無いJSONは取り込まない",            "正解の選択肢がありません"),
        ]:
            v = bad.get(key, {})
            ok(label, v.get("imported") == 0 and v.get("mismatch") == 1,
               json.dumps(v, ensure_ascii=False)[:300])
            ok("弾いた理由が作問者に伝わる（%s）" % key,
               any(needle in m for m in v.get("errors", [])),
               json.dumps(v.get("errors", []), ensure_ascii=False)[:300])

        ok("不一致は parse ではなく mismatch として報告される",
           all(any("正解判定の不一致" in m for m in bad[k]["errors"])
               for k in ["pick", "single", "sc", "zero"]),
           json.dumps(bad, ensure_ascii=False)[:400])

        # ---------- 通るべき3つ ----------
        good = pg.evaluate("""async () => {
          %s
          const cases = [
            { key: 'multi', q: mk({ key:'multi', qtype:'multiple',
                stem:'次のうち正しいものを2つ選べ。',
                correct:[true,true,false,false], sc:2 }) },
            { key: 'nosc',  q: mk({ key:'nosc', qtype:'single',
                stem:'正しいのはどれか。', correct:[false,true,false,false] }) },
            { key: 'num',   q: mk({ key:'num', qtype:'numeric',
                stem:'点滴の滴下数はどれか。', correct:[true], numeric:'50' }) }
          ];
          const out = {};
          for (const c of cases) {
            const rep = await window.Storage.importText(JSON.stringify({ questions: [c.q] }));
            const qs = await window.Storage.getAllQuestions();
            const hit = qs.filter(q => q.sub_item === 'a. ' + c.key)[0] || null;
            out[c.key] = { imported: rep.imported, mismatch: rep.mismatch,
                           errors: (rep.errors || []).map(e => e.message),
                           select_count: hit ? hit.select_count : null,
                           question_type: hit ? hit.question_type : null };
          }
          return out;
        }""" % BUILD)

        ok("正しい「2つ選べ」JSONは取り込める",
           good["multi"]["imported"] == 1 and good["multi"]["mismatch"] == 0,
           json.dumps(good["multi"], ensure_ascii=False)[:300])
        ok("select_count がそのまま保たれる", good["multi"]["select_count"] == 2,
           str(good["multi"]["select_count"]))
        ok("select_count 未指定のJSONも取り込める",
           good["nosc"]["imported"] == 1, json.dumps(good["nosc"], ensure_ascii=False)[:300])
        ok("select_count 未指定は正解数から補われる（undefined にならない）",
           good["nosc"]["select_count"] == 1, str(good["nosc"]["select_count"]))
        ok("numeric は検算せず取り込む（従来どおり）",
           good["num"]["imported"] == 1 and good["num"]["mismatch"] == 0,
           json.dumps(good["num"], ensure_ascii=False)[:300])
        ok("numeric の question_type が保たれる",
           good["num"]["question_type"] == "numeric", str(good["num"]["question_type"]))

        # ---------- TSV側は今までどおり ----------
        tsv = pg.evaluate("""async () => {
          const row = ['必修問題','目標','S','1. テスト','A. テスト','a. テスト','multiple',
            '次のうち正しいものを2つ選べ。',
            JSON.stringify(['① あ','② い','③ う','④ え']),
            JSON.stringify([1]),
            '【解説】②正しい。',
            JSON.stringify([['#人口動態統計'],['#人口動態統計'],['#人口動態統計'],['#人口動態統計']]),
            ''].join('\\t');
          const rep = await window.Storage.importText(row);
          return { imported: rep.imported, mismatch: rep.mismatch,
                   errors: (rep.errors||[]).map(e=>e.message) };
        }""")
        ok("TSV側の検算は今までどおり弾く",
           tsv["imported"] == 0 and tsv["mismatch"] == 1,
           json.dumps(tsv, ensure_ascii=False)[:300])
        ok("TSVの文面は「正解が 1」を含む（従来の期待値を維持）",
           any("2つ選べ" in m and "正解が 1" in m for m in tsv["errors"]),
           json.dumps(tsv["errors"], ensure_ascii=False)[:300])

        # ---------- 関数の単体 ----------
        unit = pg.evaluate("""() => {
          const f = window.Storage.crossCheckJsonQuestion;
          const A = n => Array.from({length:4}, (_, i) => ({ is_correct: i < n }));
          return {
            okSingle : f({ stem:'正しいのはどれか。', atoms:A(1) }, 'single'),
            ngSingle : f({ stem:'正しいのはどれか。', atoms:A(2) }, 'single'),
            okMulti  : f({ stem:'2つ選べ。', atoms:A(2), select_count:2 }, 'multiple'),
            ngMulti  : f({ stem:'2つ選べ。', atoms:A(3), select_count:3 }, 'multiple'),
            numeric  : f({ stem:'いくつか。', atoms:[] }, 'numeric')
          };
        }""")
        ok("単体：single＋正解1 は通る", unit["okSingle"] is None, str(unit["okSingle"]))
        ok("単体：single＋正解2 は止める", bool(unit["ngSingle"]), str(unit["ngSingle"]))
        ok("単体：2つ選べ＋正解2 は通る", unit["okMulti"] is None, str(unit["okMulti"]))
        ok("単体：2つ選べ＋正解3 は止める（多すぎる側も見る）",
           bool(unit["ngMulti"]), str(unit["ngMulti"]))
        ok("単体：多すぎる側の文面が「あります」になっている",
           bool(unit["ngMulti"]) and "つあります" in unit["ngMulti"], str(unit["ngMulti"]))
        ok("単体：numeric は検算しない", unit["numeric"] is None, str(unit["numeric"]))

        ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
        br.close()


runtime_checks()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAD" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
