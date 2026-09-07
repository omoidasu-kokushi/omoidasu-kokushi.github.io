# -*- coding: utf-8 -*-
"""test_atom_layout.py — 1肢のレイアウト（V2.77）

【利用者の指摘】
  「『自分の言葉で書く』がこのままの文字のボタンとお気に入り横と2か所ある。
    文字だけにして、それをお気に入りの隣に置くのはどう？ そのかわり
        ⇒誤り [解説を見る]
    というレイアウトに。スッキリするはず。」
  「解説を見るボタンだけど、押した後の存在感の消し方が足りない。
    これこそ若干灰色にしたほうがいいのでは」

【V2.76 まで】1肢が4行だった
    ⑤Purkinje〈プルキンエ〉線維              ✏  ☆
    ⇒誤り ✎ 自分の言葉で書く
                          [解説を見る]
  ✏ と「✎ 自分の言葉で書く」は**同じ機能**（どちらも cx-memo-btn）。

【V2.77】3行に減らす
    ⑤Purkinje〈プルキンエ〉線維   ✎ 自分の言葉で書く ☆
    ⇒誤り                        ▸ 解説を見る
  開くと
    ⇒誤り：Purkinje線維は、His束から分岐した…
                                        ▾ 閉じる

ここで固定するのは9つ。
  ① 「自分の言葉で書く」は1肢に1つだけ（見出し行）
  ② ✏ だけのボタンはもう無い
  ③ 見出し行のボタンは文字（枠と面を持たない）
  ④ 「⇒正誤」と「解説を見る」が同じ行（summary の中）
  ⑤ 開いたら正誤チップは隠れる（本文が「⇒誤り：」を出すので二重になる）
  ⑥ 開いたら文言が「閉じる」に変わる
  ⑦ 開いたら小さく・灰色・枠なしになる（V2.76 より更に消す）
  ⑧ 開いたら summary は本文の**下**に回る（読み始めが本文の先頭になる）
  ⑨ 「あなたの答え」バッジが付いても、選択肢の本文が潰れない
"""
import os, re, sys
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
js = open(os.path.join(base, "20260815_main_part1_V1.38.js"), encoding="utf-8").read()
cs = open(os.path.join(base, "styles.css"), encoding="utf-8").read()

ok("見出し行のボタンは writeBtnInline（文字）", "function writeBtnInline()" in js)
ok("✏ だけのボタンをもう作らない",
   '">✏</button>' not in js, "✏ の直書きが残っている")
ok("解説行から『自分の言葉で書く』を外した",
   "return verdictChipOnly(a) + writePrompt();" not in js)
ok("summary の中に正誤チップを入れている",
   "'<details class=\"cx-exp\"><summary>' +\n           verdictChipOnly(a) +" in js)
ok("「書く」と★を1つの塊にした", "'<span class=\"cx-acts\">' +" in js)
ok("なぜ塊にしたかが書いてある", "1行1〜2文字まで潰れていた" in js)
ok("なぜ消し方を強めたかが書いてある", "開いたあとの消し方が足りなかった" in cs)
ok("summary を本文の下へ回している", ".cx-exp[open]{ display:flex; flex-direction:column-reverse; }" in cs)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
# 実物と同じ形の1肢を作って測る。
# （解説が無い問題に当たると .cx-exp が出ないので、出題に頼らない）
INJECT = """(long) => {
  const host = document.createElement('section');
  host.id = 'lay-probe';
  host.style.cssText = 'padding:8px';
  const text = long
    ? '国民全員がいずれかの公的医療保険に加入する国民皆保険制度であり、'
      + '職業や居住地に応じて加入先が決まる'
    : 'Purkinje〈プルキンエ〉線維';
  host.innerHTML =
    '<article class="cx is-wrong is-picked" data-strength="weak" data-num="5">'
    + '<div class="cx-line">'
    +   '<span class="cx-num">⑤</span>'
    +   '<span class="cx-text">' + text + '</span>'
    +   '<span class="cx-pick">あなたの答え</span>'
    +   '<span class="cx-acts">'
    +     '<button type="button" class="cx-write cx-write-inline cx-memo-btn">✎ 自分の言葉で書く</button>'
    +     '<button type="button" class="cx-star" data-star-level="0">☆</button>'
    +   '</span>'
    + '</div>'
    + '<div class="cx-exp explanation-body">'
    +   '<details class="cx-exp"><summary>'
    +     '<span class="cx-arrow">⇒</span><span class="vd-chip" data-verdict="wrong">誤り</span>'
    +     '<span class="cx-exp-cta">解説を見る</span>'
    +   '</summary>'
    +   '<div class="explanation-body">'
    +     '<span class="cx-arrow">⇒</span><span class="vd-chip" data-verdict="wrong">誤り：</span>'
    +     'Purkinje線維は、His束から分岐した右脚・左脚のさらに末梢に位置する。'
    +   '</div></details>'
    + '</div></article>';
  document.querySelectorAll('#lay-probe').forEach(e => e.remove());
  document.body.prepend(host);
  return true;
}"""
M = """() => {
  const s = document.querySelector('#lay-probe .cx-exp > summary');
  const c = getComputedStyle(s), b = s.getBoundingClientRect();
  const chip = s.querySelector('.vd-chip');
  const cta  = s.querySelector('.cx-exp-cta');
  const line = document.querySelector('#lay-probe .cx-line');
  const txt  = document.querySelector('#lay-probe .cx-text');
  const wr   = document.querySelector('#lay-probe .cx-write-inline');
  const st   = document.querySelector('#lay-probe .cx-star');
  const wc   = getComputedStyle(wr);
  return {
    h: Math.round(b.height), fs: parseFloat(c.fontSize),
    bg: c.backgroundColor, bw: c.borderWidth, sh: c.boxShadow,
    chip: getComputedStyle(chip).display,
    after: getComputedStyle(cta, '::after').content,
    dir: getComputedStyle(s.parentElement).flexDirection,
    sameRow: Math.abs(chip.getBoundingClientRect().top
                      - cta.getBoundingClientRect().top) < 6,
    textW: Math.round(txt.getBoundingClientRect().width),
    lineW: Math.round(line.getBoundingClientRect().width),
    writeBg: wc.backgroundColor, writeBd: wc.borderStyle,
    starRight: Math.round(st.getBoundingClientRect().right),
    writes: document.querySelectorAll('#lay-probe .cx-write').length
  };
}"""

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(900)
    pg.evaluate("() => { const s=document.getElementById('splash'); if(s) s.classList.add('is-gone');"
                " if(window.Main && window.Main.closeModals) window.Main.closeModals(); }")

    pg.evaluate(INJECT, False)
    pg.wait_for_timeout(200)
    m = pg.evaluate(M)
    ok("「自分の言葉で書く」は1肢に1つ", m["writes"] == 1, m["writes"])
    ok("そのボタンは文字だけ（面が無い）",
       "rgba(0, 0, 0, 0)" in m["writeBg"] or m["writeBg"] == "transparent", m["writeBg"])
    ok("そのボタンは枠を持たない", m["writeBd"] == "none", m["writeBd"])
    ok("⇒正誤 と 解説を見る が同じ行", m["sameRow"], m)
    ok("閉じているときは押せる面（枠2px・影あり）",
       m["bw"].startswith("2px") and m["sh"] != "none", (m["bw"], m["sh"]))

    pg.evaluate("() => { document.querySelector('#lay-probe details.cx-exp').open = true; }")   # 外側の div も class="cx-exp" を持つので details を指す
    pg.wait_for_timeout(250)
    o = pg.evaluate(M)
    ok("開いたら正誤チップは隠れる（本文と二重にしない）", o["chip"] == "none", o["chip"])
    ok("開いたら文言が「閉じる」になる", o["after"] == '"閉じる"', o["after"])
    ok("開いたら枠も影も消える", o["bw"].startswith("0px") and o["sh"] == "none",
       (o["bw"], o["sh"]))
    ok("開いたら面が透明になる", "rgba(0, 0, 0, 0)" in o["bg"], o["bg"])
    ok("開いたら小さくなる（22px以下・12px未満）", o["h"] <= 22 and o["fs"] < 12, (o["h"], o["fs"]))
    ok("開いたら summary が本文の下に回る", o["dir"] == "column-reverse", o["dir"])
    ok("V2.76 より確かに消えている（46px → 22px以下）", o["h"] <= 22, o["h"])

    # 長い選択肢＋「あなたの答え」でも本文が潰れない
    pg.evaluate(INJECT, True)
    pg.wait_for_timeout(250)
    L = pg.evaluate(M)
    ok("長い選択肢でも本文が潰れない（行幅の半分以上を使う）",
       L["textW"] >= L["lineW"] * 0.5, (L["textW"], L["lineW"]))
    ok("★が枠の外に出ない", L["starRight"] <= 390, L["starRight"])

    # 320px
    pg.set_viewport_size({"width": 320, "height": 720})
    pg.wait_for_timeout(300)
    N = pg.evaluate(M)
    ok("320px で横スクロールが出ない",
       not pg.evaluate("() => document.documentElement.scrollWidth"
                       " > document.documentElement.clientWidth"))
    ok("320px でも本文が潰れない", N["textW"] >= N["lineW"] * 0.5, (N["textW"], N["lineW"]))
    ok("320px でも★が枠の中", N["starRight"] <= 320, N["starRight"])
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  atom_layout" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
