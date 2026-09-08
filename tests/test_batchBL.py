#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBL：同梱の見本問題そのものの健全性（V1.87）

同梱453問は **取り込みを経ずに** questions.js から直接入る。
つまり取り込みレポートの「出題基準に無い分類◯問」を一度も通らない。
そのため、シードが壊れていても誰も気づかない。

実測で見つかったもの（V1.86 まで入っていた）：

  ・**「の」が半角の "of" に化けている箇所が 84**。
    「他選択肢 of 誤り理由」「事故 of 背景」「腋毛 of 発生」など、
    解説本文・選択肢本文・分類セルにまたがって混入していた。
    利用者の目に直接触れる。1箇所だけ "the" もあった。
  ・そのうち **15行は分類セルに入っていた**ので、
    「9. 主な看護活動展開 of 場と看護の機能」のような、
    出題基準の465キーに存在しない分類になっていた。
  ・全角＜＞が半角<>、全角）が半角) になっている行が11。
    こちらも出題基準と一致しない。
  ・**タグのセルに生成器の後始末が残っていた**（`STATE_COMPLETE` が6個・5行）。
    そのうち3行はタグのセルがJSONとして読めなくなっていた。

分類が一致しないと、3階層ツリーと分析ダッシュボードに
**出題基準に無い枝が生える**。利用者からは「なぜかここだけ別項目」に見える。

`Quality of Life` `Sanctity of Life` `Insufficiency of Respiration` は
本物の英語なので、直してはいけない。ここも固定する。
"""
import io, json, os, re, sys
from collections import Counter

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


qs = io.open(os.path.join(APP, "questions.js"), encoding="utf-8").read()

# --- 出題基準マスタ ---
mstart = qs.index("const TAXONOMY_MASTER")
body = qs[mstart:qs.index("if (typeof window", mstart)]
KEYS = set("｜".join(k) for k in re.findall(r'\["([^"]+)","([^"]+)","([^"]+)"\]', body))
ok("出題基準マスタが465キーある", len(KEYS) == 465, str(len(KEYS)))

# --- 概念タグマスタ ---
tstart = qs.index("const CONCEPT_TAGS_MASTER")
tbody = qs[tstart:qs.index("if (typeof window", tstart)]
TAGS = set(re.findall(r'tag:\s*"([^"]+)"', tbody))
ok("概念タグマスタが103ある", len(TAGS) == 103, str(len(TAGS)))

# --- 見本問題のTSVを、アプリと同じ手順で組み立てて読む ---
import subprocess
NODE_SNIPPET = (
    "const fs=require('fs');global.window={};global.self=global;"
    "eval(fs.readFileSync(process.argv[1],'utf8'));"
    "process.stdout.write(global.window.SEED_QUESTIONS_TSV);"
)
out = subprocess.run(["node", "-e", NODE_SNIPPET, os.path.join(APP, "questions.js")],
                     capture_output=True, text=True)
ok("見本問題のTSVを取り出せる", out.returncode == 0 and len(out.stdout) > 1000,
   (out.stderr or "")[:200])
# V2.89（2026-09-09）：同梱シードを自由作問453問の13列TSV →
# 過去問の必修249問の **JSON** へ入れ替えた（利用者裁定）。
# TSVは source を12列目に置いていたが storage.js は12列目を is_splittable、
# 13列目を source として読む。1列ずれていたので、TSVのままだと249問すべてが
# source=null（画面に「AI予想問題」と出る）になっていた。JSONなら列が無い。
# 旧453問は消しておらず sample/20260909_旧同梱シード_自由作問453問_V1.00.txt に残る。
data = json.loads(out.stdout)
qrows = data["questions"]
ok("249問ある（V2.89で必修249問へ入れ替え）", len(qrows) == 249, str(len(qrows)))
ok("出典が249問すべてにある", all(q.get("source") for q in qrows),
   sum(1 for q in qrows if not q.get("source")))

# --- 分類が出題基準の中にあること ---
bad_key = []
for i, q in enumerate(qrows):
    k = "｜".join([q.get("unit") or "", q.get("major") or "", q.get("medium") or ""])
    if k not in KEYS:
        bad_key.append((i, k))
ok("全問の分類が出題基準の465キーの中にある", not bad_key,
   json.dumps(bad_key[:5], ensure_ascii=False))

# --- 機械翻訳の混入（の → of / the） ---
mojibake = re.findall(r"[ぁ-んァ-ヶ一-龥][\s][a-zA-Z]{1,6}[\s][ぁ-んァ-ヶ一-龥]", qs)
ok("日本語のあいだに英単語が挟まっていない（「の」が of に化けていない）",
   not mojibake, json.dumps(mojibake[:6], ensure_ascii=False))
ok("英数字と日本語のあいだにも化けが無い",
   not re.findall(r"[ぁ-んァ-ヶ一-龥]\s(?:of|the)\s", qs)
   and not re.findall(r"\s(?:of|the)\s[ぁ-んァ-ヶ一-龥]", qs),
   json.dumps(re.findall(r".{12}\s(?:of|the)\s.{12}", qs)[:4], ensure_ascii=False))

# --- 本物の英語まで潰していないこと ---
# V2.89：この主張は「化け直しの道具が本物の英語まで壊していないか」を見るもので、
# 元データは旧シード。同梱を必修249問へ入れ替えたので questions.js には
# もう出てこない。主張は消さず、**退避した旧シードに対して**そのまま続ける。
OLD = os.path.join(APP, "sample", "20260909_旧同梱シード_自由作問453問_V1.00.txt")
ok("旧シードを消さずに退避してある", os.path.exists(OLD), OLD)
old_txt = io.open(OLD, encoding="utf-8").read() if os.path.exists(OLD) else ""
ok("旧シードは453問のまま", len([r for r in old_txt.split("\n") if r.strip()]) == 453)
for phrase in ("Quality of Life", "Sanctity of Life", "Insufficiency of Respiration"):
    ok("本物の英語が残っている（旧シード）: " + phrase, phrase in old_txt)

# --- 全角・半角のゆれ ---
ok("＜＞が半角に落ちていない", "恒常性<ホメオスタシス>" not in qs)
ok("閉じ括弧が出題基準どおり", "特異的生体防御反応(免疫系)" not in qs)
ok("生成器の後始末が残っていない", "STATE_COMPLETE" not in qs)
# V2.89：旧シードでも同じ主張を続ける（元データはこちら）
ok("＜＞が半角に落ちていない（旧シード）", "恒常性<ホメオスタシス>" not in old_txt)
ok("閉じ括弧が出題基準どおり（旧シード）", "特異的生体防御反応(免疫系)" not in old_txt)
ok("生成器の後始末が残っていない（旧シード）", "STATE_COMPLETE" not in old_txt)

# --- タグが読めること ---
# 中身が74マスタに収まっているかは別問題。実測では 1,365個中 1,344個（98.5%）が
# マスタ外の自由タグで、74テーマのうち球があるのは14テーマ・最大4肢しかない。
# ここを直すのは同梱データの作り直しなので、判断待ち
# （claude/20260826_同梱シードのタグが74マスタと合わない_判断待ち_V1.00.md）。
# V2.89：JSONになったので「読めるか」ではなく「配列か」を見る。
# ついでに **マスタに収まっているか** も見る（過去問シードは収まっているはず）。
bad_tag = []
master = set(re.findall(r'tag:\s*"([^"]+)"', qs))
out_of_master = set()
for i, q in enumerate(qrows):
    for a_ in (q.get("atoms") or []):
        tg = a_.get("tags")
        if tg is not None and not isinstance(tg, list):
            bad_tag.append((i, "配列ではない"))
        for t in (tg or []):
            if t not in master:
                out_of_master.add(t)
ok("タグが全問で配列になっている", not bad_tag, json.dumps(bad_tag[:5], ensure_ascii=False))
ok("タグがすべて概念タグマスタにある（過去問シードでは収まる）",
   not out_of_master, json.dumps(sorted(out_of_master)[:5], ensure_ascii=False))

# --- 正解と選択肢 ---
bad_ans = []
for i, q in enumerate(qrows):
    atoms = q.get("atoms") or []
    if q.get("question_type") == "numeric":
        continue
    cor = [a_ for a_ in atoms if a_.get("is_correct")]
    if not atoms or not cor:
        bad_ans.append((i, {"atoms": len(atoms), "correct": len(cor)}))
ok("正解肢が全問にある", not bad_ans, json.dumps(bad_ans[:5], ensure_ascii=False))

# --- ランクが S/A/B/C であること ---
ranks = Counter(q.get("rank") for q in qrows)
ok("ランクが S/A/B/C だけ", set(ranks) <= {"S", "A", "B", "C"},
   json.dumps(ranks, ensure_ascii=False))

# --- 何が起きていたかが残っていること ---
bl = io.open(os.path.abspath(__file__), encoding="utf-8").read()
ok("何が起きていたかが書いてある", "他選択肢 of 誤り理由" in bl and "84" in bl)

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBL" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
