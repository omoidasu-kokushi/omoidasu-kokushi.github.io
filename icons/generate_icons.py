#!/usr/bin/env python3
"""
20260815_NurseExamApp_V1.00 / icons/generate_icons.py
アイコン生成スクリプト（PWA用の全サイズを1コマンドで再生成する）

  実行: python3 icons/generate_icons.py

意匠は styles.css のデザイン方向「臨床モニタ」に合わせる。
  ・地色      : #10151D（ダークテーマの背景）
  ・ECG波形   : #2AC7D6（モニタのトレース色 ＝ アプリのアクセント）
  ・トリアージ: 赤 #FF5568 / 黄 #F0AE33 / 緑 #2ECB95（評価4軸の色）
外部素材を一切使わないため、オフライン要件を崩さない。
"""
from PIL import Image, ImageDraw, ImageChops, ImageFilter
import os

BG      = (16, 21, 29, 255)
BG2     = (26, 35, 49, 255)
TRACE   = (42, 199, 214, 255)
GLOW    = (42, 199, 214, 120)
TRIAGE  = [(255, 85, 104, 255), (240, 174, 51, 255), (46, 203, 149, 255)]
HERE    = os.path.dirname(os.path.abspath(__file__))

def ecg_points(w, h, y0, amp):
    """モニタ波形：基線 → P波 → QRS群 → T波 → 基線"""
    seq = [
        (0.00, 0.0), (0.14, 0.0),
        (0.20, -0.18), (0.26, 0.0),          # P波
        (0.32, 0.16), (0.38, -1.00),         # Q → R
        (0.44, 0.40), (0.50, 0.0),           # S
        (0.62, -0.34), (0.72, 0.0),          # T波
        (1.00, 0.0),
    ]
    return [(x * w, y0 + f * amp) for x, f in seq]

def rounded_bg(size, radius_ratio=0.22, pad=0):
    """角丸の地色 ＋ 上方向のわずかな明度差（styles.css の radial-gradient に対応）"""
    r = int(size * radius_ratio)
    box = [pad, pad, size - 1 - pad, size - 1 - pad]

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=r, fill=255)

    base = Image.new("RGBA", (size, size), BG)

    grad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    span = int(size * 0.6)
    for i in range(span):
        a = int(70 * (1 - i / span))
        gd.line([(0, i), (size, i)], fill=(BG2[0], BG2[1], BG2[2], a))
    base = Image.alpha_composite(base, grad)

    # ImageDraw は RGBA をブレンドせず上書きするため、
    # 角丸の切り抜きはアルファチャンネルの乗算で行う
    base.putalpha(ImageChops.multiply(base.split()[3], mask))

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img = Image.alpha_composite(img, base)
    return img, ImageDraw.Draw(img)

def draw_icon(size, safe=1.0, radius_ratio=0.22):
    S = 4                                  # 4倍で描いて縮小（擬似アンチエイリアス）
    big = size * S
    img, d = rounded_bg(big, radius_ratio)
    d = ImageDraw.Draw(img)

    inner = big * safe
    off = (big - inner) / 2
    w = inner * 0.78
    x0 = off + (inner - w) / 2
    y0 = off + inner * 0.47
    amp = inner * 0.235
    pts = [(x0 + px, y0 + py) for px, py in ecg_points(w, inner, 0, amp)]

    lw = max(2, int(inner * 0.062))

    # グローは別レイヤーに描いてから合成する。
    # ImageDraw は RGBA を上書きするため、同一レイヤーに重ねると
    # 発光ではなく「淡い縁取り」になってしまう。
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).line(pts, fill=GLOW, width=int(lw * 2.4), joint="curve")
    glow = glow.filter(ImageFilter.GaussianBlur(radius=lw * 0.9))
    img.alpha_composite(glow)

    d = ImageDraw.Draw(img)
    d.line(pts, fill=TRACE, width=lw, joint="curve")               # 本線
    d.ellipse([pts[-1][0] - lw * 0.85, pts[-1][1] - lw * 0.85,
               pts[-1][0] + lw * 0.85, pts[-1][1] + lw * 0.85], fill=TRACE)

    # トリアージ3点（難・普・易の色）
    dot = inner * 0.052
    gap = dot * 2.5
    cy = off + inner * 0.775
    cx = off + inner / 2 - gap
    for c in TRIAGE:
        d.ellipse([cx - dot, cy - dot, cx + dot, cy + dot], fill=c)
        cx += gap

    return img.resize((size, size), Image.LANCZOS)

SPECS = [
    ("icon-192.png",          192, 1.00, 0.22),
    ("icon-512.png",          512, 1.00, 0.22),
    ("icon-maskable-192.png", 192, 0.72, 0.50),   # セーフゾーン80%を満たす
    ("icon-maskable-512.png", 512, 0.72, 0.50),
    ("apple-touch-icon.png",  180, 1.00, 0.00),   # iOSは角丸を自前で付ける
    ("favicon-32.png",         32, 1.00, 0.22),
]

if __name__ == "__main__":
    for name, size, safe, rr in SPECS:
        p = os.path.join(HERE, name)
        draw_icon(size, safe, rr).save(p, "PNG", optimize=True)
        print(f"  generated {name:26s} {size:>4}px  {os.path.getsize(p):>7,} bytes")
    print(f"\n{len(SPECS)} icons written to {HERE}")
