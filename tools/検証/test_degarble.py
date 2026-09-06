# -*- coding: utf-8 -*-
"""test_degarble.py — 化け直しが「直すべきものだけ」直すか（2026-09-07）

直すつもりで壊すのがいちばん怖い。実例で確かめる。
"""
import importlib.util, os, sys

p = os.path.expanduser("~/omo/tools/仕上げ結果を結合する_V1.01.py")
spec = importlib.util.spec_from_file_location("mg", p)
mg = importlib.util.module_from_spec(spec); spec.loader.exec_module(mg)

R = []
def ok(name, got, want):
    R.append((got == want, name, "得:%r 期:%r" % (got, want)))

def fix(s):
    stat = {}; watch = {}
    return mg._degarble_text(s, stat, watch, "t")

# --- 直すもの（日本語に挟まれている） ---
# 「of の」は の が2つにならないよう、まとめて1つの「の」に潰す（元の道具の規則）
ok("of＋の を の1つに潰す", fix("発達段階 of の組合せ"), "発達段階の組合せ")
ok("体温 of の", fix("体温 of のセットポイント"), "体温のセットポイント")
ok("括約筋 of 収縮", fix("括約筋 of 収縮"), "括約筋の収縮")
ok("社会保険制度 of 基本", fix("社会保険制度 of 基本"), "社会保険制度の基本")
ok("助詞のis", fix("脾静脈 is 門脈系の血管である。"), "脾静脈は門脈系の血管である。")
# 空白なしで詰まった形（肝臓is体内の）は元の道具も直さない。
# \b が効かないため。実データでは空白ありしか出ていないので、ここは仕様として固定する。
ok("空白なしは直さない（実データに無い形）", fix("肝臓is体内の"), "肝臓is体内の")

# --- 壊してはいけないもの（本物の英語） ---
ok("Quality of Life", fix("Quality of Life を保つ"), "Quality of Life を保つ")
ok("Sanctity of Life", fix("Sanctity of Life の考え方"), "Sanctity of Life の考え方")
ok("英文のまま", fix("This is a pen"), "This is a pen")
ok("英語に挟まれたof", fix("Insufficiency of Respiration"), "Insufficiency of Respiration")
ok("数字に挟まれたof", fix("3 of 5"), "3 of 5")

# --- 直さないもの（置き換え先が文脈で変わる） ---
ok("school は直さない", fix("学校保健安全法で school 感染症"), "学校保健安全法で school 感染症")
ok("and は直さない", fix("構造 and 機能"), "構造 and 機能")
ok("the は直さない", fix("社会福祉 the 基本"), "社会福祉 the 基本")

# --- 何度かけても同じ（冪等） ---
once = fix("発達段階 of の組合せ")
ok("冪等", fix(once), once)

# --- 見張り（数えるだけ）が効いているか ---
stat = {}; watch = {}
mg._degarble_text("学校保健安全法で school 感染症", stat, watch, "第112回 午前問82")
ok("school を見張りに記録する", watch.get("school"), ["第112回 午前問82"])
stat2 = {}; watch2 = {}
mg._degarble_text("発達段階 of の組合せ", stat2, watch2, "t")
ok("直した数を数える", stat2.get("fixed"), 1)

bad = [x for x in R if not x[0]]
for good, name, d in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + d) if not good else ""))
print("\n%d/%d  degarble" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
