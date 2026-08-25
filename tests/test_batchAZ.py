#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチAZ：印刷物のQRコード（V1.75）

紙のURLは打ち込まれない。実習室や図書館で回る間違いノートから
アプリへ来る経路として、文字列は事実上機能しない（V1.66の出典表記の狙い）。
そこで出典表記をQR主体にした。

外部APIも符号化器も積まない：URLは固定なので**行列を定数で持つ**。
このバッチは外部依存なしで「行列の形」と「組版」を固定する。
実際に読めるかの検証は tools/verify_qr.py（cv2＋segnoが要る・変更時のみ手動）。
"""
import io, json, os, re, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []

def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()

# ---------------------------------------------------------------- 静的検査
css = read("styles.css")
p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
js = read(p2)

ok("再生成できる（生成スクリプトが同梱されている）",
   os.path.exists(os.path.join(APP, "tools", "make_qr.py")))
ok("読み取り検証のスクリプトも同梱されている",
   os.path.exists(os.path.join(APP, "tools", "verify_qr.py")))

m = re.search(r"var QR_MATRIX = \[(.*?)\];", js, re.S)
ok("QR_MATRIX がある", bool(m))
rows = re.findall(r"'([01]+)'", m.group(1)) if m else []
ok("29行ある（版3）", len(rows) == 29, str(len(rows)))
ok("全行が29桁", all(len(r) == 29 for r in rows), str(sorted({len(r) for r in rows})))
ok("0と1だけでできている", all(set(r) <= {"0", "1"} for r in rows))

# 位置検出パターン（3隅の7×7）。ここが崩れていたらQRとして成立しない
def finder_ok(rs, oy, ox):
    pat = ["1111111", "1000001", "1011101", "1011101", "1011101", "1000001", "1111111"]
    return all(rs[oy + i][ox:ox + 7] == pat[i] for i in range(7))
ok("左上に位置検出パターンがある", len(rows) == 29 and finder_ok(rows, 0, 0))
ok("右上に位置検出パターンがある", len(rows) == 29 and finder_ok(rows, 0, 22))
ok("左下に位置検出パターンがある", len(rows) == 29 and finder_ok(rows, 22, 0))
# タイミングパターン（6行目・6列目が交互）
ok("横のタイミングパターンが交互", len(rows) == 29 and
   all(rows[6][x] == ("1" if x % 2 == 0 else "0") for x in range(8, 21)))
ok("縦のタイミングパターンが交互", len(rows) == 29 and
   all(rows[y][6] == ("1" if y % 2 == 0 else "0") for y in range(8, 21)))

ok("URLの定数がアプリのURLと一致", "var QR_URL = 'https://omoidasu-kokushi.github.io/';" in js)
ok("クワイエットゾーンを4モジュール取る（規格上必須）", "quiet = 4" in js)
ok("色は黒白で焼く（テーマ色を使わない）",
   "fill=\"#fff\"" in js and "fill=\"#000\"" in js and "var(--" not in js.split("function qrSvg")[1][:900])
ok("なぜ画像でもAPIでもないかが書いてある", "オフライン要件に反する" in js)
ok("印刷の寸法が実測に基づく", "15mm" in js or "15mm" in css)
ok("QRのCSSがある（22mm角）", ".pn-qr{" in css and "22mm" in css)
ok("出典が改ページで割れない", "break-inside:avoid" in css.split(".pn-credit{")[1][:400])
ok("URLの文字も控えとして残す（QRが読めない紙のため）", "pn-credit-text" in js)
ok("間違いノートとレポートの両方で同じ出典を使う", js.count("printCredit()") >= 2)

# ---------------------------------------------------------------- 実行時検査
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=30000)
    pg.wait_for_timeout(1200)
    try:
        pg.click("#welcome-start", timeout=4000)
    except Exception:
        pass
    pg.wait_for_timeout(600)

    r = pg.evaluate("""() => {
      const svg = window.Half2Impl.qrSvg();
      const host = document.createElement('div');
      host.innerHTML = svg;
      const el = host.querySelector('svg');
      const path = el.querySelector('path').getAttribute('d');
      return { viewBox: el.getAttribute('viewBox'),
               cls: el.getAttribute('class'),
               role: el.getAttribute('role'),
               label: el.getAttribute('aria-label'),
               rect: !!el.querySelector('rect'),
               modules: (path.match(/M/g) || []).length,
               crisp: el.getAttribute('shape-rendering') };
    }""")
    dark = sum(row.count("1") for row in rows)
    ok("viewBox は 37×37（29＋クワイエット4×2）", r["viewBox"] == "0 0 37 37", r["viewBox"])
    ok("黒モジュールの数が行列と一致", r["modules"] == dark, "%s / %s" % (r["modules"], dark))
    ok("白い下地を敷く（透過にしない）", r["rect"])
    ok("にじませない（crispEdges）", r["crisp"] == "crispEdges", str(r["crisp"]))
    ok("読み上げ用のラベルがある", r["role"] == "img" and "omoidasu" in (r["label"] or ""), json.dumps(r))

    # 1問解いてノートを組み、印刷メディアでQRの実寸を測る
    made = pg.evaluate("""async () => {
      const S = window.Storage;
      const atoms = await S.getAllAtoms();
      const a = atoms[0];
      const patch = {}; patch[a.atom_id] = { last_eval:'hard', answer_count:1, last_answered_at: Date.now() };
      await S.updateAtomsBulk(patch);
      const res = await window.Half2Impl.buildPrintSheet({ kind:'hard', paper:'A4', cols:'1', explain:'all', limit:0 });
      const s = document.getElementById('print-sheet');
      return { count: res.count, qr: s.querySelectorAll('.pn-qr').length,
               urlText: s.innerHTML.includes('omoidasu-kokushi.github.io'),
               parent: s.parentElement.tagName };
    }""")
    ok("間違いノートにQRが1つ入る", made["qr"] == 1, json.dumps(made))
    ok("URLの文字も残っている", made["urlText"], json.dumps(made))
    ok("紙面は body 直下のまま（V1.70）", made["parent"] == "BODY", made["parent"])

    pg.emulate_media(media="print")
    pg.wait_for_timeout(300)
    box = pg.evaluate("""() => { const q = document.querySelector('#print-sheet .pn-qr');
        if (!q) return null; const b = q.getBoundingClientRect();
        return { w: Math.round(b.width), h: Math.round(b.height) }; }""")
    pg.emulate_media(media="screen")
    ok("印刷メディアでQRに実寸がある", bool(box) and box["w"] > 40, json.dumps(box))
    ok("QRが正方形", bool(box) and abs(box["w"] - box["h"]) <= 1, json.dumps(box))
    ok("22mm相当の大きさ（15mmの読み取り下限を上回る）",
       bool(box) and 70 <= box["w"] <= 95, json.dumps(box))

    # 学習レポート側にも入る
    rep = pg.evaluate("""async () => {
      const res = await window.Half2Impl.buildReportSheet();
      const s = document.getElementById('print-sheet');
      return { count: res.count, qr: s.querySelectorAll('.pn-qr').length };
    }""")
    ok("学習レポートにもQRが入る", rep["qr"] == 1, json.dumps(rep))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAZ" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
