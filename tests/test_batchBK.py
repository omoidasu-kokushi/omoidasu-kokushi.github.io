#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBK：中項目の名前は単元をまたいで重複する（V1.86）

出題基準の中項目名は一意ではない。実測で **465キー中 同名の中項目が多数**。
成人看護学の「A. 機能障害のアセスメント」「B. 症状とその看護」
「C. 検査を受ける患者の看護」「D. 治療を受ける患者の看護」
「E. 機能障害をもちながら生活する人の看護」は、それぞれ **12の大項目**に出てくる。
「A. コミュニケーション」「C. 看護過程」「D. 看護管理」「A. 保健師助産師看護師法」は
必修問題と基礎看護学／健康支援の両方に出てくる。

V1.85 までは範囲指定を **中項目の名前だけ** で行っていた。実測で起きること：

  ・**中項目別リセットが、消すつもりのない11個の中項目まで一緒に消す。**
    「呼吸機能障害の検査だけ戻したい」と押すと、循環・消化・栄養代謝・内分泌・
    身体防御・感覚・脳神経・運動・排泄・性生殖の検査の記録も全部消える。
    しかも一覧では12件が1行に潰れ、パンくずは最初に当たった1件しか出ない。
    **表示と実害が食い違う。**
  ・中項目からのランダム出題に、別の大項目の問題が混ざる
  ・未学習バッジが同名ぶん合算されて水増しされる
  ・分析ダッシュボードの中項目行が12件ぶんの平均になる

過去問1,200問を取り込むと **139問（12%）** が同名の中項目に属する。
同梱453問だけではほとんど踏まないので、**過去問を入れた瞬間に効いてくる。**
"""
import io, json, os, re, sys, glob as _g
from collections import Counter

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
SEP = ""
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


st = read("storage.js")
sc = read("scheduler.js")
p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
js = read(p2)

ok("範囲指定の複合キーがある", "function scopeKey(" in st and "function splitScope(" in st)
ok("範囲の絞り込みが入っている", "function narrowScope(" in st)
ok("アトムの範囲取得が絞り込みを通る",
   "narrowScope(list, sc)" in st.split("function getAtomsByScope(")[1][:400])
ok("問題の範囲取得も絞り込みを通る",
   "narrowScope(list, sc)" in st.split("function getQuestionsByScope(")[1][:400])
ok("バッジも複合キーで数える", "medium_key[mk]" in st and "sub_item_key[sk]" in st)
ok("ツリーの中項目キーが複合キー", "var mkey = scopeKey(q.unit, q.major, q.medium);" in st)
ok("分析ダッシュボードも複合キーで束ねる",
   "var deep = (level === 'medium' || level === 'sub_item');" in sc)
ok("リセット一覧が複合キーで並ぶ", "S.scopeKey(q.unit, q.major, q.medium)" in js)
ok("確認ダイアログにパンくずを出す", "mediumPath(medium)" in js)
ok("何が起きていたかが書いてある", "12大項目" in st or "12件" in js)

# 出題基準マスタそのものに重複があることを、コードではなくデータで確かめる
qs = read("questions.js")
mstart = qs.index("const TAXONOMY_MASTER")
body = qs[mstart:qs.index("if (typeof window", mstart)]
keys = re.findall(r'\["([^"]+)","([^"]+)","([^"]+)"\]', body)
ok("出題基準マスタを読めた", len(keys) == 465, str(len(keys)))
cnt = Counter(k[2] for k in keys)
dup = {k: v for k, v in cnt.items() if v > 1}
ok("中項目名は一意ではない（重複が実在する）", len(dup) >= 5, json.dumps(dup, ensure_ascii=False))
ok("同名が最大12件ある", bool(dup) and max(dup.values()) >= 12,
   json.dumps(sorted(dup.items(), key=lambda x: -x[1])[:3], ensure_ascii=False))
ok("大項目名は単元をまたがない（ここは名前で足りる）",
   all(len(set(k[0] for k in keys if k[1] == mj)) == 1 for mj in set(k[1] for k in keys)))

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

    # 同名の中項目を2つ、別の大項目に作って取り込む
    made = pg.evaluate("""async () => {
      const mk = (unit, major, medium, tag) => ({
        unit: unit, rank: 'B', major: major, medium: medium, sub_item: null,
        question_type: 'single', select_count: 1, pool: 'main',
        stem: '同名中項目の検証 ' + tag,
        atoms: [
          { original_num:1, is_correct:true,  text:'正 ' + tag, statement:'正 ' + tag, tags:[] },
          { original_num:2, is_correct:false, text:'誤 ' + tag, statement:'誤 ' + tag, tags:[] }
        ]
      });
      const payload = { questions: [
        mk('成人看護学', '8. 呼吸機能障害のある患者の看護', 'C. 検査を受ける患者の看護', 'A'),
        mk('成人看護学', '9. 循環機能障害のある患者の看護', 'C. 検査を受ける患者の看護', 'B')
      ]};
      const r = await window.Storage.importText(JSON.stringify(payload));
      return { imported: r.imported, skipped: r.skipped };
    }""")
    ok("同名の中項目を2件取り込めた", made["imported"] == 2, json.dumps(made, ensure_ascii=False))

    got = pg.evaluate("""async () => {
      const S = window.Storage;
      const kA = S.scopeKey('成人看護学', '8. 呼吸機能障害のある患者の看護', 'C. 検査を受ける患者の看護');
      const kB = S.scopeKey('成人看護学', '9. 循環機能障害のある患者の看護', 'C. 検査を受ける患者の看護');
      const byName = await S.getAtomsByScope('medium', 'C. 検査を受ける患者の看護');
      const onlyA  = await S.getAtomsByScope('medium', kA);
      const onlyB  = await S.getAtomsByScope('medium', kB);
      return { byName: byName.length, onlyA: onlyA.length, onlyB: onlyB.length,
               aMajors: [...new Set(onlyA.map(a => a.major))],
               split: S.splitScope(kA) };
    }""")
    ok("名前だけで引くと同名が全部まとまって返る（今までの挙動）", got["byName"] >= 4,
       json.dumps(got, ensure_ascii=False))
    ok("複合キーで引くと片方だけになる", got["onlyA"] == 2 and got["onlyB"] == 2,
       json.dumps(got, ensure_ascii=False))
    ok("複合キーの中身が大項目まで一致する",
       got["aMajors"] == ["8. 呼吸機能障害のある患者の看護"],
       json.dumps(got["aMajors"], ensure_ascii=False))
    ok("複合キーを分解できる",
       got["split"]["unit"] == "成人看護学" and got["split"]["leaf"] == "C. 検査を受ける患者の看護",
       json.dumps(got["split"], ensure_ascii=False))

    # 消す側：片方だけ消えて、もう片方が残ること
    reset = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler;
      const kA = S.scopeKey('成人看護学', '8. 呼吸機能障害のある患者の看護', 'C. 検査を受ける患者の看護');
      const kB = S.scopeKey('成人看護学', '9. 循環機能障害のある患者の看護', 'C. 検査を受ける患者の看護');
      const all = await S.getAtomsByScope('medium', 'C. 検査を受ける患者の看護');
      for (const a of all) {
        await K.applyEvaluation(a.atom_id, 'normal', { mode: 'random', isCorrect: true, sessionId: 'BK' });
      }
      const before = { A: (await S.getAtomsByScope('medium', kA)).filter(x => x.answer_count > 0).length,
                       B: (await S.getAtomsByScope('medium', kB)).filter(x => x.answer_count > 0).length };
      const r = await S.resetProgressByScope('medium', kA);
      const after  = { A: (await S.getAtomsByScope('medium', kA)).filter(x => x.answer_count > 0).length,
                       B: (await S.getAtomsByScope('medium', kB)).filter(x => x.answer_count > 0).length };
      return { before: before, after: after, reset: r.atoms };
    }""")
    ok("消す前は両方に記録がある", reset["before"]["A"] > 0 and reset["before"]["B"] > 0,
       json.dumps(reset, ensure_ascii=False))
    ok("指した中項目だけが未学習に戻る", reset["after"]["A"] == 0,
       json.dumps(reset, ensure_ascii=False))
    ok("**同名の別の中項目は消えない**", reset["after"]["B"] == reset["before"]["B"],
       json.dumps(reset, ensure_ascii=False))

    # 出す側：中項目からの出題が混ざらないこと
    q = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler;
      const kA = S.scopeKey('成人看護学', '8. 呼吸機能障害のある患者の看護', 'C. 検査を受ける患者の看護');
      const r = await K.buildQueue({ mode:'tree', count:20, applyGuard:false,
                                     scope:{ field:'medium', value:kA } });
      const qs = r.questions || [];
      return { n: qs.length, majors: [...new Set(qs.map(x => x.major))] };
    }""")
    ok("中項目からの出題が同名の別大項目を混ぜない",
       q["n"] > 0 and q["majors"] == ["8. 呼吸機能障害のある患者の看護"],
       json.dumps(q, ensure_ascii=False))

    # ツリーのバッジが合算されないこと
    tree = pg.evaluate("""async (sep) => {
      const t = await window.Storage.buildTree();
      const arr = Array.isArray(t) ? t : (t.units || t.nodes || []);
      const out = [];
      arr.forEach(u => (u.children||[]).forEach(mj => (mj.children||[]).forEach(md => {
        if (md.label === 'C. 検査を受ける患者の看護') {
          out.push({ major: mj.label, label: md.label,
                     key_has_sep: String(md.key).indexOf(sep) >= 0,
                     label_has_sep: String(md.label).indexOf(sep) >= 0,
                     count: md.count, unlearned: md.unlearned });
        }
      })));
      return out;
    }""", SEP)
    ok("ツリーで同名の中項目が別々の行になる", len(tree) >= 2, json.dumps(tree, ensure_ascii=False))
    ok("ツリーの中項目キーが複合キーになっている",
       bool(tree) and all(x["key_has_sep"] for x in tree), json.dumps(tree, ensure_ascii=False))
    ok("ツリーの表示ラベルに区切り文字が混ざらない",
       all(not x["label_has_sep"] for x in tree), json.dumps(tree, ensure_ascii=False))

    # 分析ダッシュボードの行も分かれること
    dash = pg.evaluate("""async () => {
      const d = await window.Scheduler.buildDashboard({ level: 'medium' });
      const rows = (d.rows || []).filter(r => r.label === 'C. 検査を受ける患者の看護');
      return { n: rows.length, crumbs: rows.map(r => r.crumb) };
    }""")
    ok("分析の中項目行が同名でも分かれる", dash["n"] >= 2, json.dumps(dash, ensure_ascii=False))
    ok("行のパンくずが行ごとに違う（嘘をつかない）",
       len(set(dash["crumbs"])) == dash["n"], json.dumps(dash, ensure_ascii=False))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBK" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
