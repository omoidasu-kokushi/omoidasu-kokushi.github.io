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
    出題基準の458キーに存在しない分類になっていた。
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
ok("出題基準マスタが458キーある", len(KEYS) == 458, str(len(KEYS)))

# --- 概念タグマスタ ---
tstart = qs.index("const CONCEPT_TAGS_MASTER")
tbody = qs[tstart:qs.index("if (typeof window", tstart)]
TAGS = set(re.findall(r'tag:\s*"([^"]+)"', tbody))
ok("概念タグマスタが74ある", len(TAGS) == 74, str(len(TAGS)))

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
rows = [r for r in out.stdout.split("\n") if r.strip()]
ok("453行ある", len(rows) == 453, str(len(rows)))
cols = set(len(r.split("\t")) for r in rows)
ok("全行が13列", cols == {13}, str(sorted(cols)))

# --- 分類が出題基準の中にあること ---
bad_key = []
for i, r in enumerate(rows):
    c = r.split("\t")
    k = "｜".join([c[0], c[3], c[4]])
    if k not in KEYS:
        bad_key.append((i, k))
ok("全行の分類が出題基準の458キーの中にある", not bad_key,
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
for phrase in ("Quality of Life", "Sanctity of Life", "Insufficiency of Respiration"):
    ok("本物の英語が残っている: " + phrase, phrase in qs)

# --- 全角・半角のゆれ ---
ok("＜＞が半角に落ちていない", "恒常性<ホメオスタシス>" not in qs)
ok("閉じ括弧が出題基準どおり", "特異的生体防御反応(免疫系)" not in qs)
ok("生成器の後始末が残っていない", "STATE_COMPLETE" not in qs)

# --- タグのセルがJSONとして読めること ---
# 中身が74マスタに収まっているかは別問題。実測では 1,365個中 1,344個（98.5%）が
# マスタ外の自由タグで、74テーマのうち球があるのは14テーマ・最大4肢しかない。
# ここを直すのは同梱データの作り直しなので、判断待ち
# （claude/20260826_同梱シードのタグが74マスタと合わない_判断待ち_V1.00.md）。
# このテストでは「読めること」だけを固定し、
# 取り込み時に気づけるかどうかは batchBM が見る。
bad_tag = []
for i, r in enumerate(rows):
    c = r.split("\t")
    try:
        groups = json.loads(c[11]) if c[11].strip() else []
        if not isinstance(groups, list):
            bad_tag.append((i, "配列ではない"))
    except Exception:
        bad_tag.append((i, "JSONとして読めない"))
ok("タグのセルが全行JSONとして読める", not bad_tag,
   json.dumps(bad_tag[:5], ensure_ascii=False))

# --- 正解番号が選択肢の数を超えないこと ---
bad_ans = []
for i, r in enumerate(rows):
    c = r.split("\t")
    if c[6].strip().lower() == "numeric":
        continue
    try:
        opts = json.loads(c[8])
        ans = json.loads(c[9])
    except Exception:
        bad_ans.append((i, "JSONとして読めない"))
        continue
    if not ans or any((not isinstance(x, int)) or x < 0 or x >= len(opts) for x in ans):
        bad_ans.append((i, {"opts": len(opts), "ans": ans}))
ok("正解番号が選択肢の範囲に収まっている", not bad_ans,
   json.dumps(bad_ans[:5], ensure_ascii=False))

# --- ランクが S/A/B/C であること ---
ranks = Counter(r.split("\t")[2] for r in rows)
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
