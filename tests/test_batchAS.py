#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.68 検証：配色トークンのコントラストを styles.css から直接検算する

ブラウザを立てない静的テスト。画面走査（/tmpの道具）は
「その画面に出ていた組み合わせ」しか見られず、単発だった。
ここではトークンの組み合わせ規則そのものを毎回検算する。
色を1つでも動かしたら、このテストが即座に答えを出す。
"""
import io, os, re, sys

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))

css = io.open(os.path.join(APP, "styles.css"), encoding="utf-8").read()


def block(name):
    """テーマブロックの中身。
    共通トークン（評価色など）は :root、面と文字はテーマ別の
    html[data-theme="…"] ブロックにある。ライトも "light" ブロック。"""
    if name == "root":
        m = re.search(r":root\{(.*?)\n\}", css, re.S)
        # :root は複数あるので、色トークンを含むものを探す
        for mm in re.finditer(r":root\{(.*?)\n\}", css, re.S):
            if "--c-hard:" in mm.group(1): return mm.group(1)
        return m.group(1) if m else ""
    m = re.search(r'html\[data-theme="%s"\]\{(.*?)\n\}' % name, css, re.S)
    return m.group(1) if m else ""


def tokens(name):
    t = {}
    for m in re.finditer(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})", block(name)):
        t[m.group(1)] = m.group(2)
    return t


ROOT = tokens("root")
BLOCKS = { n: tokens(n) for n in ("light", "dark", "sepia") }
def theme(name):
    t = dict(ROOT)
    t.update(BLOCKS["light"])          # ライトが既定（他テーマは上書き）
    if name != "light": t.update(BLOCKS[name])
    return t


def hx(h): h = h.lstrip("#"); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
def lum(rgb):
    def f(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
def ratio(a, b):
    l1, l2 = lum(a), lum(b)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)
def mix(fg, bg, pct):
    f, b = hx(fg), hx(bg)
    a = pct / 100.0
    return tuple(f[i] * a + b[i] * (1 - a) for i in range(3))


WHITE = (255, 255, 255)
NEED = 4.5

for name in ("light", "dark", "sepia"):
    T = theme(name)
    surfaces = [T[k] for k in ("surface", "surface-2", "surface-3", "bg") if k in T]
    ok("%s：トークンが読めている" % name, len(T) > 10 and len(surfaces) == 4,
       "tokens=%d surf=%d" % (len(T), len(surfaces)))

    # --- 地の文字（sub / mute）×全表面 ---
    for key in ("text-sub", "text-mute"):
        worst = min(ratio(hx(T[key]), hx(s)) for s in surfaces)
        ok("%s：%s が全表面で4.5以上（%.2f）" % (name, key, worst), worst >= NEED)

    # --- べた塗り × ink（点灯した評価ボタン・バッジ・atom-chip） ---
    solid_ink = [("c-hard", "c-hard-ink"), ("c-easy", "c-easy-ink"),
                 ("c-normal", "c-normal-ink"), ("c-master", "c-master-ink")]
    for bgk, inkk in solid_ink:
        if bgk not in T or inkk not in T: continue
        r = ratio(hx(T[inkk]), hx(T[bgk]))
        ok("%s：%s×%s＝%.2f（べた塗りの文字）" % (name, inkk, bgk, r), r >= NEED)

    # --- 淡い面（tint 16〜22%）× on-soft（肢セレクター・正誤マーク・チップ） ---
    tinted = [("c-hard", "c-hard-on-soft", (16, 18, 22)),
              ("c-easy", "c-easy-on-soft", (16, 22)),
              ("c-normal", "c-normal-on-soft", (18,)),
              ("c-master", "c-master-on-soft", (18,))]
    for basek, softk, pcts in tinted:
        if basek not in T or softk not in T: continue
        worst = min(ratio(hx(T[softk]), mix(T[basek], s, p))
                    for s in surfaces for p in pcts)
        ok("%s：%s が tint 地で4.5以上（%.2f）" % (name, softk, worst), worst >= NEED)

    # --- accent-soft × accent-on-soft（タグ・レベルチップ） ---
    if "accent-soft" in T and "accent-on-soft" in T:
        r = ratio(hx(T["accent-on-soft"]), hx(T["accent-soft"]))
        ok("%s：accent-on-soft×accent-soft＝%.2f" % (name, r), r >= NEED)

    # --- accent 面 × accent-ink（btn-primary・バッジ・ガイド吹き出し） ---
    if "accent" in T and "accent-ink" in T:
        r = ratio(hx(T["accent-ink"]), hx(T["accent"]))
        ok("%s：accent-ink×accent＝%.2f" % (name, r), r >= NEED)

    # --- accent を文字に使う場所（ひとこと欄の題ほか）×全表面 ---
    # ダークは明るいシアンで元から余裕。3テーマとも同じ規則で見る。
    worst = min(ratio(hx(T["accent"]), hx(s)) for s in surfaces)
    ok("%s：accent文字が全表面で4.5以上（%.2f）" % (name, worst), worst >= NEED)

# --- リテラル：is-warm の温色バッジ（トークン外なので個別に） ---
m = re.search(r"\.badge-line\.is-warm\{ background:(#[0-9A-Fa-f]{6})", css)
ok("is-warm の背景が拾える", bool(m))
if m:
    r = ratio(WHITE, hx(m.group(1)))
    ok("白×is-warm＝%.2f（V1.68までは3.21だった）" % r, r >= NEED)

# --- 退行防止：#fff 直書きでべた塗りに載せている場所が増えていない ---
hard_fff = len(re.findall(r"background:var\(--c-(?:hard|easy)\);[^}]*color:#fff", css))
ok("評価色のべた塗りに #fff 直書きが残っていない（ink を通す）",
   hard_fff == 0, "found=%d" % hard_fff)

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAS" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
