#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBM：74テーマに無いタグを、取り込みのときに言う（V1.88）

分類（単元＞大項目＞中項目）は V1.71 から「出題基準に無い分類◯問」と
報告していた。**タグは何を書いても黙って通っていた。**

74マスタから外れたタグが付くと、
  ・74概念理解率（§12-2）の対象にならない
  ・概念別弱点ノック（§7）に球が出ない
  ・最優先克服概念TOP3（§12-3）に出てこない
これらは全部「出ない」だけなので、**画面のどこにもエラーが出ない。**
気づけるのは「ノックを押しても問題が来ない」と思ったときで、
そのときにはもう原因の見当がつかない。

実測（同梱453問）：肢に付いたタグ 1,365個のうち **1,344個（98.5%）がマスタ外**。
74テーマのうち球があるのは **14テーマ・最大4肢**。
つまり買った直後の利用者は、74概念アナライザーも概念別弱点ノックも実質使えない。
同梱データを直すのは別の判断
（claude/20260826_同梱シードのタグが74マスタと合わない_判断待ち_V1.00.md）。
ここでは **これから取り込むぶんについて、必ず気づけるようにする。**
"""
import io, json, os, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


st = read("storage.js")
p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
js = read(p2)

ok("タグの照合がある", "function tagKnown(" in st and "function tagCheckInto(" in st)
ok("マスター不在なら検査しない（分類と同じ扱い）",
   "マスター不在なら検査しない" in st.split("function tagKnown(")[1][:400])
ok("TSVの取り込みでも数える", "tagCheckInto(report, built.atoms" in st)
ok("JSONの取り込みでも数える", "tagCheckInto(report, atoms" in st)
ok("レポートの初期値にある", "tag_bad: 0, tag_bad_rows: 0, tag_examples: []" in st)
ok("画面に出す", "103テーマに無いタグ" in js)
ok("何が起きるかを画面にも書く",
   "概念別弱点ノックにも" in js and "最優先克服概念" in js)
ok("何が起きていたかがコードに書いてある", "静かに死ぬ" in st or "静かに死ぬ" in js)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(1200)

    got = pg.evaluate("""async () => {
      const master = window.CONCEPT_TAGS_MASTER.map(x => x.tag);
      const mk = (tag, tags) => ({
        unit: '必修', rank: 'B', major: '11. 徴候と疾患',
        medium: 'A. 主要な症状と徴候', sub_item: 'a. 意識障害',
        question_type: 'single', select_count: 1, pool: 'main',
        stem: 'タグ照合の検証 ' + tag,
        atoms: [
          { original_num:1, is_correct:true,  text:'正 ' + tag, statement:'正 ' + tag, tags: tags },
          { original_num:2, is_correct:false, text:'誤 ' + tag, statement:'誤 ' + tag, tags: tags }
        ]
      });
      const payload = { questions: [
        mk('ok',   [master[0]]),
        mk('bad1', ['#でたらめなタグ']),
        mk('bad2', ['#もうひとつでたらめ', master[1]])
      ]};
      const r = await window.Storage.importText(JSON.stringify(payload));
      return { imported: r.imported, tag_bad: r.tag_bad || 0,
               tag_bad_rows: r.tag_bad_rows || 0,
               tag_examples: r.tag_examples || [], tax_bad: r.tax_bad || 0 };
    }""")
    ok("3問とも取り込める（タグが違っても弾かない）", got["imported"] == 3,
       json.dumps(got, ensure_ascii=False))
    ok("マスタ外のタグを数える（肢ごと）", got["tag_bad"] == 4, json.dumps(got, ensure_ascii=False))
    ok("マスタ外のタグを含む問題数も数える", got["tag_bad_rows"] == 2,
       json.dumps(got, ensure_ascii=False))
    ok("どのタグが外れたかを例に出す",
       "#でたらめなタグ" in got["tag_examples"] and "#もうひとつでたらめ" in got["tag_examples"],
       json.dumps(got, ensure_ascii=False))
    ok("マスタ内のタグは数えない（誤検知しない）", got["tag_bad"] == 4 and got["tax_bad"] == 0,
       json.dumps(got, ensure_ascii=False))

    clean = pg.evaluate("""async () => {
      const master = window.CONCEPT_TAGS_MASTER.map(x => x.tag);
      const payload = { questions: [{
        unit: '必修', rank: 'B', major: '11. 徴候と疾患',
        medium: 'A. 主要な症状と徴候', sub_item: 'a. 意識障害',
        question_type: 'single', select_count: 1, pool: 'main',
        stem: 'タグ照合の検証 きれいな行',
        atoms: [
          { original_num:1, is_correct:true,  text:'正', statement:'正', tags:[master[2]] },
          { original_num:2, is_correct:false, text:'誤', statement:'誤', tags:[master[3]] }
        ]
      }]};
      const r = await window.Storage.importText(JSON.stringify(payload));
      return { imported: r.imported, tag_bad: r.tag_bad || 0 };
    }""")
    ok("全部マスタ内なら警告が出ない", clean["imported"] == 1 and clean["tag_bad"] == 0,
       json.dumps(clean, ensure_ascii=False))

    # 同梱シードの実情を、思い込みではなく数えて残す
    seed = pg.evaluate("""async () => {
      const master = new Set(window.CONCEPT_TAGS_MASTER.map(x => x.tag));
      const atoms = await window.Storage.getAllAtoms();
      const seedAtoms = atoms.filter(a => String(a.q_id || '').indexOf('TAGCHK') < 0
                                        && String(a.stem || '').indexOf('タグ照合の検証') < 0);
      let total = 0, inMaster = 0;
      const hit = new Set();
      seedAtoms.forEach(a => (a.tags || []).forEach(t => {
        total++; if (master.has(t)) { inMaster++; hit.add(t); }
      }));
      return { total: total, inMaster: inMaster, themes: hit.size, masterSize: master.size };
    }""")
    ok("同梱シードのタグを数えられた", seed["total"] > 0, json.dumps(seed, ensure_ascii=False))
    ok("**同梱シードのタグはほとんどが74マスタ外**（この事実を固定して忘れない）",
       seed["inMaster"] * 20 < seed["total"], json.dumps(seed, ensure_ascii=False))
    ok("74テーマのうち球があるのは一部だけ", seed["themes"] < 40,
       json.dumps(seed, ensure_ascii=False))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBM" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
