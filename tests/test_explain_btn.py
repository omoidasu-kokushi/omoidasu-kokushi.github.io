# -*- coding: utf-8 -*-
"""test_explain_btn.py — 「解説を見る」が押せると分かる（V2.76）

【利用者からの報告】
  「デカいんだけど色も立体感の無いデザインも非アクティブっぽくて、
    あ、こんなのあったんだ／あ、押せるんだこれ、という感じで存在感が無さすぎる。
    実際、学生も見落としていた。」

【実測（V2.75・390px・ライト）】
    幅 316 / 高さ 44   ← 幅いっぱいの大きな面
    背景 #ECF1F7      ← --surface-3（奥まった面）
    文字 #56657A      ← --text-sub（補助文字色）
    枠   #DAE2EC      ← --border（ほぼ見えない）
    影   none ／ 文字 12.48px
  多くのUIで「無効なボタン」に使う配色そのもの。
  大きいのに沈んでいるので、押せる場所ではなく仕切りに見えていた。

【V2.76 の直し方】
  閉じているとき＝これから押す状態なので、主役の配色にする。
    面＝accent-soft ／ 枠＝accent 2px ／ 文字＝accent 800 ／ 下に2pxの影
    先頭に ▸ ／ 文字 12.5px → 14px
  開いたあと＝もう読んでいるので、主張を下げて本文の邪魔をしない。

【絵文字を使わない】
  最初 📖 を置いたが、実測で豆腐（□）になった。
  ▸（U+25B8）は絵文字の異体字を持たない幾何学記号で、
  このアプリの「元の解説を見る」で既に使っていて化けていない。

ここで固定するのは7つ。
  ① 閉じているとき、面・枠・文字がすべてアクセント色（沈んだ灰色ではない）
  ② 枠が2px、下に影がある（立体に見える）
  ③ 先頭に ▸ が出る。絵文字を使っていない
  ④ 文字が 14px 以上・太さ800
  ⑤ 高さ44px以上（指で押せる）
  ⑥ 開いたら主張が下がる（背景が透明・記号が ▾）
  ⑦ 320px で横スクロールが出ない
"""
import os, re, sys
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cs = open(os.path.join(base, "styles.css"), encoding="utf-8").read()
# 「.cx-exp .explanation-body」は 57章より前のコメントにも出てくるので、
# index() だと手前で切れて中身が空になる。57章の中だけを切り出す。
_i = cs.index(".cx-exp > summary{")
blk = cs[_i:cs.index("/* 「まだありません」ではなく", _i)]

ok("なぜ直したかが書いてある", "無効なボタン" in cs and "学生が解説の存在に気づいていなかった" in cs)
ok("閉じているときの面はアクセント色", "background:var(--accent-soft);" in blk)
ok("枠は2pxのアクセント色", "border:2px solid var(--accent);" in blk)
ok("下に影がある", "box-shadow:0 2px 0 var(--accent);" in blk)
ok("押した瞬間に沈む", "translateY(2px)" in blk)
ok("記号は ▸（エスケープで書く）", "\\25B8" in cs)
ok("開いたら ▾ になる", "\\25BE" in cs)
ok("V2.77：記号は CTA の中（summary 直下ではない）",
   ".cx-exp > summary .cx-exp-cta::before" in cs)
# 絵文字（サロゲートペア／絵文字ブロック）が混ざっていないこと
emoji = re.findall(r"[\U0001F300-\U0001FAFF☀-➿]", blk)
ok("絵文字を使っていない（豆腐になる）", not emoji, emoji[:5])

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
INJECT = """() => {
  /* 解説が無い問題に当たると .cx-exp が出ないので、
     見た目を測るために同じ形の details を1つ足す。
     測るのは CSS であって、出し分けの条件ではない。 */
  const host = document.querySelector('.cx') || document.body;
  const d = document.createElement('details');
  d.className = 'cx-exp';
  /* V2.77：summary の中は「⇒正誤」＋「解説を見る」。記号は CTA の ::before。 */
  d.innerHTML = '<summary>'
              +   '<span class="cx-arrow">⇒</span>'
              +   '<span class="vd-chip" data-verdict="wrong">誤り</span>'
              +   '<span class="cx-exp-cta">解説を見る</span>'
              + '</summary>'
              + '<div class="explanation-body">本文</div>';
  host.appendChild(d);
  return true;
}"""
M = """() => {
  const e = document.querySelector('.cx-exp > summary');
  if (!e) return null;
  const c = getComputedStyle(e), b = e.getBoundingClientRect();
  return { w: Math.round(b.width), h: Math.round(b.height),
           bg: c.backgroundColor, fg: c.color, bd: c.borderColor,
           bw: c.borderWidth, sh: c.boxShadow,
           fs: parseFloat(c.fontSize), fw: c.fontWeight,
           /* V2.77：記号は summary ではなく CTA の ::before に移った */
           mark: getComputedStyle(e.querySelector('.cx-exp-cta') || e, '::before').content };
}"""

def rgb(s):
    m = re.findall(r"\d+", s or "")
    return tuple(int(x) for x in m[:3]) if len(m) >= 3 else None

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.evaluate("""async () => {
      await window.Storage.setMetaBulk({ onboarding_done: true, tips_seen: ['all'] });
    }""")
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(1200)
    pg.evaluate("() => { const s=document.getElementById('splash'); if(s) s.classList.add('is-gone');"
                " if(window.Main && window.Main.closeModals) window.Main.closeModals(); }")
    pg.evaluate(INJECT)
    pg.wait_for_timeout(250)

    m = pg.evaluate(M)
    ok("測れている", m is not None, m)
    if m:
        ok("面が沈んだ灰色ではない（旧 #ECF1F7 ではない）", rgb(m["bg"]) != (236, 241, 247), m["bg"])
        ok("文字が補助色ではない（旧 #56657A ではない）", rgb(m["fg"]) != (86, 101, 122), m["fg"])
        ok("枠が2px", m["bw"].startswith("2px"), m["bw"])
        ok("影がある", m["sh"] != "none", m["sh"])
        ok("文字が14px以上", m["fs"] >= 14, m["fs"])
        ok("太さ800", str(m["fw"]) == "800", m["fw"])
        ok("高さ44px以上", m["h"] >= 44, m["h"])
        ok("先頭に ▸ が出る", m["mark"] == '"▸"', m["mark"])
        # 枠と文字がアクセント色（=同系）で、面より濃い
        ok("枠と文字が同じアクセント色", rgb(m["bd"]) == rgb(m["fg"]), (m["bd"], m["fg"]))

    # 3テーマとも、枠がその配色のアクセント色になっている
    for th in ("light", "dark", "sepia"):
        pg.evaluate("t => { document.documentElement.dataset.theme = t; }", th)
        pg.wait_for_timeout(250)
        mm = pg.evaluate(M)
        acc = pg.evaluate("() => getComputedStyle(document.documentElement)"
                          ".getPropertyValue('--accent').trim()")
        ok("%s：枠がアクセント色" % th, rgb(mm["bd"]) is not None and mm["bw"].startswith("2px"),
           (mm["bd"], acc))
        ok("%s：面と文字の明るさが違う（読める）" % th,
           abs(sum(rgb(mm["bg"])) - sum(rgb(mm["fg"]))) > 150,
           (mm["bg"], mm["fg"]))
    pg.evaluate("() => { document.documentElement.dataset.theme = 'light'; }")

    # 開いたら静かになる
    pg.evaluate("() => { document.querySelector('.cx-exp').open = true; }")
    pg.wait_for_timeout(250)
    o = pg.evaluate(M)
    ok("開いたら面が透明になる", rgb(o["bg"]) is None or "rgba(0, 0, 0, 0)" in o["bg"], o["bg"])
    ok("開いたら影が消える", o["sh"] == "none", o["sh"])
    ok("開いたら記号が ▾ になる", o["mark"] == '"▾"', o["mark"])
    ok("開いたら小さくなる", o["h"] < 44 and o["fs"] < 14, (o["h"], o["fs"]))
    pg.evaluate("() => { document.querySelector('.cx-exp').open = false; }")

    # 320px でも枠からはみ出さない
    pg.set_viewport_size({"width": 320, "height": 720})
    pg.wait_for_timeout(350)
    ok("320px で横スクロールが出ない",
       not pg.evaluate("() => document.documentElement.scrollWidth"
                       " > document.documentElement.clientWidth"))
    n = pg.evaluate(M)
    ok("320px でも高さ44px以上", n["h"] >= 44, n["h"])
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  explain_btn" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
