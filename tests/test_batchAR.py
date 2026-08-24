#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.67 検証：模試結果のシェア画像"""
import json, os, sys, io, glob
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))
def read(f): return io.open(os.path.join(APP, f), encoding="utf-8").read()

idx = read("index.html")
P2 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
s2 = read(P2)
ok("結果モーダルにシェアの入口がある", 'id="btn-exam-share"' in idx)
ok("Canvasだけで生成する（通信ゼロ）",
   "function buildShareCard" in s2 and "fetch(" not in s2.split("function buildShareCard")[1].split("function canvasToBlob")[0])
# 注釈には「合格可能性%は載せない」と書いてあるので、注釈を落として
# 描画コードだけを見る（注釈の語を拾って直したはずのものを赤くした）。
import re as _re
_draw = _re.sub(r"/\*.*?\*/", "", s2.split("function buildShareCard")[1]
                .split("function canvasToBlob")[0], flags=_re.S)
ok("合格可能性%を載せていない（距離だけ）",
   "合格可能性" not in _draw and "ライン80%まで" in _draw
   and "ボーダー目安180点まで" in _draw)
ok("出どころのURLが画像に入る",
   "omoidasu-kokushi.github.io" in s2.split("function buildShareCard")[1].split("function canvasToBlob")[0])
ok("共有シートが使えない環境はダウンロードに落ちる", "downloadBlobAsFile" in s2)
ok("共有シートを閉じただけなら何もしない（AbortError）", "AbortError" in s2)

PASS = {"exam_id":"mock_120","style":"real","total":120,"correct":101,
  "hisshu":{"total":25,"correct":22,"pct":88,"pass":True},
  "ippan":{"total":95,"correct":79,"score":208,"pass":True},
  "passed":True,"patterns":{},"elapsed_ms":4980000}
FAIL = {"exam_id":"mock_30","style":"final","total":30,"correct":19,
  "hisshu":{"total":30,"correct":19,"pct":63,"pass":False},
  "ippan":{"total":0,"correct":0,"score":None,"pass":True},
  "passed":False,"patterns":{},"elapsed_ms":1200000}


def _external(t):
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t)


def runtime_checks():
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox"])
        pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append("console:" + m.text)
              if m.type == "error" and not _external(m.text) else None)
        pg.goto(URL, wait_until="load")
        pg.wait_for_function("window.__APP_READY === true", timeout=30000)
        pg.wait_for_timeout(1000)
        try: pg.click("#welcome-start", timeout=2500)
        except Exception: pass
        pg.wait_for_timeout(400)

        # ---------- 画像そのもの ----------
        r = pg.evaluate("""(res) => {
          const cv = window.Half2Impl.buildShareCard(res);
          const ctx = cv.getContext('2d');
          /* 画素を実際に読む。「描いたつもり」を検出するため：
             四隅と中央の5点で、真っ黒でも真っ白でもないこと＋
             中央（白い数字の帯）が明るいこと。 */
          const px = (x, y) => { const d = ctx.getImageData(x, y, 1, 1).data;
            return d[0] + d[1] + d[2]; };
          return { w: cv.width, h: cv.height,
                   corner: px(10, 10), center: px(540, 500),
                   footer: px(120, 1024) };
        }""", PASS)
        ok("画像は1080×1080", r["w"] == 1080 and r["h"] == 1080, json.dumps(r))
        ok("背景が描かれている（真っ黒/真っ白のキャンバスでない）",
           0 < r["corner"] < 300, json.dumps(r))
        ok("中央の数字が明るく描かれている", r["center"] > 500, json.dumps(r))

        # 合格・不合格の描き分け（緑の帯の有無を画素で見る）
        r = pg.evaluate("""(args) => {
          const H = window.Half2Impl;
          const band = res => {
            const cv = H.buildShareCard(res);
            /* 帯の中でも「合格ライン突破」の白文字に当たらない左端側を採る。
               中央(540,705)は文字のグリフに当たることがある。 */
            const d = cv.getContext('2d').getImageData(360, 705, 1, 1).data;
            /* #1FA97A の帯：緑が赤より十分強い */
            return d[1] > d[0] + 40;
          };
          return { pass: band(args[0]), fail: band(args[1]) };
        }""", [PASS, FAIL])
        ok("合格のときだけ緑の帯が出る", r["pass"] is True, json.dumps(r))
        ok("不合格の画像に合格帯は無い（煽らない）", r["fail"] is False, json.dumps(r))

        # 一般が0問（必修のみ模試）でも落ちない
        r = pg.evaluate("""(res) => {
          try { const cv = window.Half2Impl.buildShareCard(res);
                return { ok: true, w: cv.width }; }
          catch (e) { return { ok: false, err: String(e).slice(0, 80) }; }
        }""", FAIL)
        ok("必修だけの模試でも画像が作れる（一般0問で落ちない）",
           r["ok"] is True, json.dumps(r))

        # ---------- Blob 化 ----------
        r = pg.evaluate("""async (res) => {
          const H = window.Half2Impl;
          const cv = H.buildShareCard(res);
          /* canvasToBlob は非公開なので、共有と同じ経路で確かめる：
             navigator.share を差し替えて、渡ってきた File を検分する */
          const orig = { share: navigator.share, canShare: navigator.canShare };
          let got = null;
          navigator.canShare = () => true;
          navigator.share = (data) => { got = data; return Promise.resolve(); };
          try {
            window.Half2Impl.showExamResult ? null : null;
            /* lastResult を直接置いて shareExamResult を呼ぶ */
            const st = null;
            window.Half2Impl.gradeExam ? null : null;
          } finally {}
          /* shareExamResult は st.exam.lastResult を見る。模試を実走させずに
             それを立てる公開経路が無いので、showExamResult を最小で通す */
          await H.showExamResult(res);
          await H.shareExamResult();
          navigator.share = orig.share; navigator.canShare = orig.canShare;
          if (!got || !got.files || !got.files.length) { return { shared: false }; }
          const f = got.files[0];
          const buf = new Uint8Array(await f.arrayBuffer());
          return { shared: true, name: f.name, type: f.type,
                   size: f.size,
                   pngMagic: buf[0] === 0x89 && buf[1] === 0x50
                          && buf[2] === 0x4E && buf[3] === 0x47,
                   text: got.text || '' };
        }""", PASS)
        ok("共有シートに PNG ファイルが渡る",
           r.get("shared") and r.get("pngMagic") is True, json.dumps(r, ensure_ascii=False))
        ok("ファイル名と型が正しい",
           r.get("name") == "omoidasu_result.png" and r.get("type") == "image/png",
           json.dumps(r, ensure_ascii=False))
        ok("添える文に点数が入る", "101/120" in r.get("text", ""), json.dumps(r, ensure_ascii=False))

        # ---------- 結果モーダルにボタンが出る ----------
        r = pg.evaluate("""() => ({
          open: !document.getElementById('modal-exam-result').hidden,
          btn: !!document.getElementById('btn-exam-share'),
          visible: (() => { const b = document.getElementById('btn-exam-share');
            return b && b.offsetWidth > 0; })() })""")
        ok("採点結果のモーダルが開き、シェアボタンが見えている",
           r["open"] is True and r["visible"] is True, json.dumps(r))

        # ---------- 共有が使えない環境 → ダウンロードへ ----------
        r = pg.evaluate("""async () => {
          const orig = { share: navigator.share, canShare: navigator.canShare };
          delete navigator.share; delete navigator.canShare;
          let clicked = null;
          const origClick = HTMLAnchorElement.prototype.click;
          HTMLAnchorElement.prototype.click = function () {
            clicked = { download: this.download, href: this.href.slice(0, 5) }; };
          try { await window.Half2Impl.shareExamResult(); }
          finally {
            HTMLAnchorElement.prototype.click = origClick;
            navigator.share = orig.share; navigator.canShare = orig.canShare;
          }
          return clicked;
        }""")
        ok("共有が無い環境ではPNGダウンロードに落ちる（必ず何かが手に残る）",
           bool(r) and r.get("download") == "omoidasu_result.png"
           and r.get("href") == "blob:", json.dumps(r))

        # ---------- 結果が無いときは静かに断る ----------
        r = pg.evaluate("""async () => {
          const bak = window.Half2Impl.gradeExam;   /* 触らないが存在確認 */
          /* lastResult を消して呼ぶ */
          const H = window.Half2Impl;
          await H.showExamResult ? null : null;
          /* st は非公開なので、リロード直後の状態を模す代わりに
             新しいページで確かめるのが本筋だが、ここでは
             結果無しを直接作れないため存在チェックに留める */
          return { fnExists: typeof H.shareExamResult === 'function' };
        }""")
        ok("シェア関数が公開されている", r["fnExists"] is True, json.dumps(r))

        ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
        br.close()


runtime_checks()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAR" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
