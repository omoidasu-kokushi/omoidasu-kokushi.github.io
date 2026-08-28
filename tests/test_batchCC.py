#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCC：出題基準を令和5年版へ差し替えた（V2.05）

**何が起きていたか。**

分類の元にしていた `看護師国家試験出題基準範囲.pdf` は、PDFの作成日が
**2013年5月30日＝平成26年版**だった。平成30年版・令和5年版の2版ぶん古い。
転記そのものは正確で、元のPDFが古かった。

そのため、次のずれが商品に入ったまま動いていた。

  ・必修の大項目が「10. 生命活動 / 11. 病態と看護 / 12. 薬物治療に伴う反応」。
    令和5年版は「10. 人体の構造と機能 / 11. 徴候と疾患 / 12. 薬物の作用とその管理」
  ・精神看護学の大項目3が「生物学的側面に注目した援助」。令和5年版には存在しない
  ・**電気けいれん療法の置き場所が無かった**。令和5年版では
    `精神看護学｜4. 精神疾患・障害がある者とその家族への看護｜C. B以外の治療法`
  ・単元名「在宅看護論」は令和5年版で「在宅看護論／地域・在宅看護論」

差し替えの規模（実測）：現行458キーのうち令和5年版と完全一致は **39キー（8.5%）**。
過去問1,200問では **966問（80.5%）が機械では移せなかった**。

**この差し替えで踏んだ罠。**

  ・`RANK_BY_MEDIUM` の中項目名と `TAXONOMY_MASTER` の中項目名が
    **16件ずれていた**。別々の時点のキー一覧から作ったため。
    ずれていても JS は落ちず、**該当の中項目が静かに B に落ちるだけ**だった。
    → ここで「ランク表のキーは全部マスタにあるか」を固定する
  ・同梱453問の分類は旧458キーで書かれており、**401行が新キーに存在しなかった**。
    3階層ツリーと分析ダッシュボードに出題基準に無い枝が生える。
    → 旧キー→新キーの写像を当てて全行を通した
"""
import io, json, os, re, sys

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

qs = io.open(os.path.join(APP, "questions.js"), encoding="utf-8").read()

def block(name):
    i = qs.index("const " + name)
    return qs[i:qs.index("if (typeof window", i)]

# --- 出題基準マスタ（465キー・令和5年版） ---
tax = re.findall(r'\["([^"]+)","([^"]+)","([^"]+)"\]', block("TAXONOMY_MASTER"))
KEYS = set("|".join(k) for k in tax)
ok("出題基準マスタが465キー", len(tax) == 465, str(len(tax)))
ok("キーに重複が無い", len(KEYS) == 465, str(len(KEYS)))
units = sorted(set(k[0] for k in tax))
ok("単元は12", len(units) == 12, json.dumps(units, ensure_ascii=False))
ok("大項目は133", len(set((k[0], k[1]) for k in tax)) == 133,
   str(len(set((k[0], k[1]) for k in tax))))

# --- 令和5年版であることの印（旧版の名前が消えていること） ---
ok("必修の大項目が『11. 徴候と疾患』", ("必修", "11. 徴候と疾患", "A. 主要な症状と徴候") in tax)
ok("必修の大項目が『10. 人体の構造と機能』",
   any(k[0] == "必修" and k[1] == "10. 人体の構造と機能" for k in tax))
ok("必修の大項目が『12. 薬物の作用とその管理』",
   any(k[0] == "必修" and k[1] == "12. 薬物の作用とその管理" for k in tax))
ok("旧版の『11. 病態と看護』は無い", not any(k[1] == "11. 病態と看護" for k in tax))
ok("旧版の『10. 生命活動』は無い", not any(k[1] == "10. 生命活動" for k in tax))
ok("旧版の『生物学的側面に注目した援助』は無い",
   not any("生物学的側面に注目した援助" in k[1] for k in tax))
ok("単元名が『在宅看護論／地域・在宅看護論』", "在宅看護論／地域・在宅看護論" in units)
ok("旧単元名『在宅看護論』単独は無い", "在宅看護論" not in units)
ok("**電気けいれん療法の置き場所がある**",
   ("精神看護学", "4. 精神疾患・障害がある者とその家族への看護", "C. B以外の治療法") in tax)

# --- 概念タグマスタ（103個） ---
tb = block("CONCEPT_TAGS_MASTER")
TAGS = re.findall(r'tag:\s*"([^"]+)"', tb)
ok("概念タグは103個", len(TAGS) == 103, str(len(TAGS)))
ok("タグに重複が無い", len(set(TAGS)) == 103, str(len(set(TAGS))))
ok("全部 # で始まる", all(t.startswith("#") for t in TAGS))
labels = re.findall(r'label:\s*"([^"]+)"', tb)
ok("tag と label が対応している", len(labels) == 103 and
   all(t[1:] == l for t, l in zip(TAGS, labels)))
cats = set(re.findall(r'category:\s*"([^"]+)"', tb))
ok("カテゴリが空でない", all(c.strip() for c in cats), json.dumps(sorted(cats), ensure_ascii=False))
for t in ["#精神科治療・行動制限", "#清潔・整容ケア", "#看護過程・アセスメント",
          "#公衆衛生・地域保健活動", "#臨床判断・統合的アセスメント"]:
    ok("新設タグ " + t + " がある", t in TAGS)
for t in ["#人口動態統計", "#看護倫理・法的責任", "#在宅療養支援・訪問看護"]:
    ok("旧74のタグ " + t + " を消していない", t in TAGS)

# --- ランク表（ここが今回ずれていた） ---
rb = block("RANK_BY_MEDIUM")
RK = {}
for letter in ("S", "A", "C"):
    seg = rb.split('m[k] = "%s"' % letter)[0]
    seg = seg[seg.rindex("  ["):]
    for k in re.findall(r'"([^"]+\|[^"]+\|[^"]+)"', seg):
        RK[k] = letter
ok("ランク表に218件ある", len(RK) == 218, str(len(RK)))
missing = sorted(k for k in RK if k not in KEYS)
ok("**ランク表のキーは全部マスタにある**", not missing,
   json.dumps(missing[:5], ensure_ascii=False))
c = {"S": 0, "A": 0, "C": 0}
for v in RK.values():
    c[v] += 1
ok("S31 / A71 / C116", c == {"S": 31, "A": 71, "C": 116}, json.dumps(c))
ok("B は載せていない（既定なので）", '"B"' not in rb)

# --- 同梱の見本問題（旧キーのままだと全部ツリーから外れる） ---
sstart = qs.index("const SEED_QUESTIONS_TSV")
sbody = qs[sstart:qs.index("if (typeof window", sstart)]
rows = re.findall(r'^\s*"(.*)",?\s*$', sbody, re.M)
seed_keys = []
for r in rows:
    c2 = r.split("\\t")
    if len(c2) >= 5:
        seed_keys.append("|".join([c2[0], c2[3], c2[4]]))
ok("見本問題を読めた（453行）", len(seed_keys) == 453, str(len(seed_keys)))
bad = sorted(set(k for k in seed_keys if k not in KEYS))
ok("**見本問題の分類が全行マスタにある**", not bad,
   json.dumps(bad[:5], ensure_ascii=False))

# --- 何が起きていたかが残っていること ---
me = io.open(os.path.abspath(__file__), encoding="utf-8").read()
ok("何が起きていたかが書いてある",
   "2013年5月30日" in me and "16件ずれていた" in me and "401行" in me)

bad_ = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchCC" % (len(R) - len(bad_), len(R)))
sys.exit(1 if bad_ else 0)
