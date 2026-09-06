# -*- coding: utf-8 -*-
"""test_qty_mode.py — 区切り方はスライダー2本。触ったほうが効く（V2.70）

利用者の指摘は2段ある。両方を守れているかをここで固定する。

  V2.69「ポモドーロと出題数設定は共存させないで。時間指定or出題数指定の2択で、
        どちらもスライダーでざっくり調整できる。25分を大々的に推奨する形に」
  V2.70「ランダムのポモドーロ分かりにくい。時間と問題数は同じようなUIの
        スライダーに。時間が上で問題数が下、問題数は一回り小さく。
        時間は 5分 10分 25分(推奨) 45分 60分 ／ ○ ○ ◎ ○ ○」

V2.69 では二択のセグメントを置き、選ばれていないほうのスライダーを消していた。
終了条件は1つに定まったが、**押す場所が2段階**になり、
消えたほうに何があるかも見えなかった。

V2.70 は、2本とも常に見せて **触ったほうがそのまま終了条件になる**。
「共存させない」は破っていない：**効いているのは常に1つだけ**。

ここで固定するのは6つ。
  ① スライダー2本が常に出ている（片方を hidden にしない）
  ② 効いているのは常に片方だけ（is-on が1つ）
  ③ スライダーを触ると、そちらが終了条件になる（1操作で決まる）
  ④ 時間の段は 5/10/25/45/60 で、25分の目盛りだけ ◎推奨
  ⑤ 25分のときだけポモドーロの案内が出る
  ⑥ 時間で区切るときも水増ししない（V2.57と同じ考え）
"""
import json, os, re, sys
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p2 = open(os.path.join(base, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()
cs = open(os.path.join(base, "styles.css"), encoding="utf-8").read()
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()
ix = open(os.path.join(base, "index.html"), encoding="utf-8").read()

# --- 形（V2.70） ---
ok("スライダーが2本ある", 'id="time-range"' in ix and 'id="qty-range"' in ix)
ok("2本とも同じ .qty-pick の様式になっている",
   ix.count('class="qty-pick') == 2 and 'data-qmode="time"' in ix and 'data-qmode="count"' in ix)
ok("時間が上・問題数が下", ix.index('id="qty-time-row"') < ix.index('id="qty-count-row"'))
ok("問題数は一回り小さい（is-sub）", 'class="qty-pick is-sub"' in ix and ".qty-pick.is-sub" in cs)
ok("V2.69のセグメントは無くなった", 'id="qty-mode"' not in ix)
ok("ポモドーロのON/OFFトグルは無いまま", 'id="qty-pomo"' not in ix)
ok("ポモドーロの案内が置いてある", 'id="qty-pomo-reco"' in ix and "25分やって5分休む" in ix)
ok("時間の段は5/10/25/45/60（利用者指定）", "TIME_STOPS = [5, 10, 25, 45, 60]" in p2)
ok("時間スライダーの max が段数に合っている", 'id="time-range" min="0" max="4"' in ix)
ok("目盛りが ○ ○ ◎ ○ ○ になっている",
   ix.count("<i>○</i>") == 4 and ix.count("<i>◎</i>") == 1)
ok("25分だけ推奨と書いてある", '<em>25分</em><i>◎</i><u>推奨</u>' in ix)
ok("既定は25分（ポモドーロ）", "TIME_DEFAULT = 25" in p2)
ok("旧値（15分・40分）は一番近い段へ寄る仕掛けが残っている", "function timeIndexOf" in p2)
ok("時間で区切るときも水増ししない（見込みの数だけ積む）", "Q_PER_MIN" in p2)
ok("なぜ2本見せるかがコードに書いてある", "見えないと選べない" in p2)
ok("同時に生かさない方針が残っている", "同時に効くことは無い" in p2)
ok("CSSがある", ".qty-pick{" in cs and ".qty-scale-time" in cs)
# 目盛りとthumbがずれない。問題数側を transform:scale(.92) で縮めたら
# track だけ短くなり、実測で12pxずれた（V2.70で外した）。
ok("スライダーを transform で縮めていない（目盛りとずれる）",
   ".qty-pick.is-sub input[type=range]{ width:100%; }" in cs
   and not [ln for ln in re.sub(r"/\*.*?\*/", "", cs, flags=re.S).split("\n")
             if ".qty-pick" in ln and "transform:scale" in ln])

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)

    def snap():
        return pg.evaluate("""() => {
          const H = window.Half2Impl;
          H.refreshQtyMode();
          const t = document.getElementById('qty-time-row');
          const c = document.getElementById('qty-count-row');
          const r = document.getElementById('qty-pomo-reco');
          return { tShown: !t.hidden, cShown: !c.hidden,
                   tOn: t.classList.contains('is-on'),
                   cOn: c.classList.contains('is-on'),
                   reco: !r.hidden,
                   limit: H.st.random.limit,
                   tv: (document.getElementById('time-range-val')||{}).textContent,
                   cv: (document.getElementById('qty-range-val')||{}).textContent };
        }""")

    pg.evaluate("() => { const s=window.Half2Impl.st.random; s.limit='time'; s.minutes=25; s.count=10; }")
    a = snap()
    ok("2本とも見えている（どちらも消さない）",
       a["tShown"] and a["cShown"], json.dumps(a, ensure_ascii=False))
    ok("効いているのは時間だけ", a["tOn"] and not a["cOn"], json.dumps(a, ensure_ascii=False))
    ok("25分ならポモドーロの案内が出る", a["reco"], json.dumps(a, ensure_ascii=False))
    ok("時間の表示が25分", a["tv"] == "25分", str(a["tv"]))
    ok("問題数の表示も見えている（消えていない）", a["cv"] == "10問", str(a["cv"]))

    # ③ 問題数のスライダーを触ると、そちらが終了条件になる
    pg.evaluate("""() => {
      const el = document.getElementById('qty-range');
      el.value = 3;
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }""")
    b = snap()
    ok("問題数を触るとそちらが終了条件になる", b["limit"] == "count", json.dumps(b, ensure_ascii=False))
    ok("効いているのは問題数だけ", b["cOn"] and not b["tOn"], json.dumps(b, ensure_ascii=False))
    ok("問題数を触るとポモドーロの案内は引っ込む", b["reco"] is False, json.dumps(b, ensure_ascii=False))
    ok("値が段どおり30問", b["cv"] == "30問", str(b["cv"]))
    ok("2本とも見えたまま", b["tShown"] and b["cShown"], json.dumps(b, ensure_ascii=False))

    # 時間のスライダーを触ると戻る
    pg.evaluate("""() => {
      const el = document.getElementById('time-range');
      el.value = 2;
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }""")
    c = snap()
    ok("時間を触ると時間へ戻る", c["limit"] == "time" and c["tOn"], json.dumps(c, ensure_ascii=False))
    ok("段の3番目は25分（◎の位置）", c["tv"] == "25分", str(c["tv"]))
    ok("25分に戻るとポモドーロの案内も戻る", c["reco"], json.dumps(c, ensure_ascii=False))

    pg.evaluate("""() => {
      const el = document.getElementById('time-range');
      el.value = 4;
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }""")
    d = snap()
    ok("段の5番目は60分", d["tv"] == "60分", str(d["tv"]))
    ok("25分から外すとポモドーロの案内は引っ込む", d["reco"] is False, json.dumps(d, ensure_ascii=False))

    # 枠を押すだけでも切り替わる
    pg.evaluate("() => document.getElementById('qty-count-row').click()")
    e = pg.evaluate("() => window.Half2Impl.st.random.limit")
    ok("枠を押すだけでも切り替わる（スライダーをずらさずに済む）", e == "count", str(e))

    ok("JSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
    br.close()

def _vers(txt, pat):
    return sorted(set(re.findall(pat, txt)))
sw_cache = _vers(sw, r"CACHE_NAME = 'v([0-9.]+)'")
sw_q = _vers(sw, r"\?v=([0-9.]+)")
ix_q = _vers(ix, r"\?v=([0-9.]+)")
ix_stamp = _vers(ix, r"Omoidasu_V([0-9.]+)")
ok("index.htmlの?v=が1種類に揃っている", len(ix_q) == 1, str(ix_q))
ok("indexとswの?v=が一致している", ix_q == sw_q, str(ix_q) + " vs " + str(sw_q))
ok("build-stampの版が?v=と一致している",
   len(ix_stamp) == 1 and ix_stamp[0] == ix_q[0], str(ix_stamp))
ok("CACHE_NAMEが?v=と同じ系列", len(sw_cache) == 1 and sw_cache[0] == ix_q[0] + ".0", str(sw_cache))

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  qty_mode" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
