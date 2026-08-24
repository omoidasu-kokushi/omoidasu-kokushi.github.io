#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.40 検証：起動スプラッシュ
  ・必ず消えること（覆いが残る事故を構造的に防ぐ）
  ・聞くべきときだけ聞くこと（初回の人にログインを迫らない）
  ・期限内なら聞かずに同期すること
  ・押した先で操作が塞がれないこと
"""
import json, os, sys, subprocess, glob, re
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))

P1 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
P2 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
for f in ["storage.js", "scheduler.js", "drive.js", P1, P2, "sw.js"]:
    p = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True)
    ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

idx = open(os.path.join(APP, "index.html"), encoding="utf-8").read()
sw  = open(os.path.join(APP, "sw.js"), encoding="utf-8").read()
css = open(os.path.join(APP, "styles.css"), encoding="utf-8").read()
p1s = open(os.path.join(APP, P1), encoding="utf-8").read()
p2s = open(os.path.join(APP, P2), encoding="utf-8").read()

ok("index の script/REQUIRED が実ファイルを指す", idx.count(P1) == 2 and idx.count(P2) == 2)
ok("sw の CORE_ASSETS が実ファイルを指す", P1 in sw and P2 in sw)
ok("他版のファイル名が残っていない",
   len(set(re.findall(r"main_part1_V\d+\.\d+\.js", idx + sw))) == 1 and
   len(set(re.findall(r"main_part2_V\d+\.\d+\.js", idx + sw))) == 1)
_c = re.search(r"CACHE_NAME = 'v(\d+)\.(\d+)\.(\d+)'", sw)
ok("sw CACHE_NAME が v1.29.0 以降",
   bool(_c) and tuple(int(x) for x in _c.groups()) >= (1, 29, 0),
   _c.group(0) if _c else "not found")

ok("スプラッシュはHTMLに直接ある（JS待ちの白画面を作らない）", 'id="splash"' in idx)
ok("スプラッシュは <body> 直後にある（描画がJSを待たない）",
   0 < idx.find('id="splash"') < idx.find("<script src="),
   "splash=%d firstScript=%d" % (idx.find('id="splash"'), idx.find("<script src=")))
ok("ロゴ・名称・副題がある",
   'id="splash-logo"' in idx and "オモイダス" in idx and "想起を、早期に。" in idx)
ok("状態の表示欄がある", 'id="splash-status"' in idx)
ok("2択のボタンがある", 'id="splash-login"' in idx and 'id="splash-skip"' in idx)
ok("JSが動かなくても消える保険がある",
   "getElementById('splash')" in idx and "is-gone" in idx and "6000" in idx)
ok("消えたら操作を通さない", "pointer-events: none" in css.split(".splash.is-gone")[1][:200])
ok("起動に失敗しても覆いを外す", "try { hideSplash();" in p1s)
ok("スプラッシュから呼ぶ同期がある", "driveSyncFromSplash" in p1s and "driveSyncFromSplash" in p2s)
ok("動きを減らす設定に配慮している", "prefers-reduced-motion" in css)

def _external(t):
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t)

MOCK = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_drive.js"),
            encoding="utf-8").read()

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text)
          if m.type == "error" and not _external(m.text) else None)

    # ---------- 初回：一度も同期を使っていない人 ----------
    pg.goto(URL, wait_until="commit")
    # 「最初から」の保証は静的な位置で取る（commit の発火位置は環境で揺れる）
    pg.wait_for_selector("#splash", state="attached", timeout=5000)
    early = pg.evaluate("""() => {
      const s = document.getElementById('splash');
      if (!s) { return null; }
      return { gone: s.classList.contains('is-gone'),
               op: getComputedStyle(s).opacity };
    }""")
    ok("読み込みの早い段階で覆いが出ている",
       early and early["gone"] is False and float(early["op"]) > 0.9, json.dumps(early))

    pg.wait_for_function("window.__APP_READY === true", timeout=20000)
    r = pg.evaluate("""() => {
      const a = document.getElementById('splash-ask');
      return { askHidden: a.hidden };
    }""")
    ok("初めての人にはログインを聞かない（1問も解く前に離脱させない）",
       r["askHidden"] is True, json.dumps(r))

    pg.wait_for_function(
        "document.getElementById('splash').classList.contains('is-gone')", timeout=8000)
    r = pg.evaluate("""() => {
      const s = document.getElementById('splash');
      const cs = getComputedStyle(s);
      return { gone: s.classList.contains('is-gone'), pe: cs.pointerEvents,
               vis: cs.visibility };
    }""")
    ok("起動が終わると覆いが外れる", r["gone"] is True, json.dumps(r))
    ok("外れた覆いは操作を通さない", r["pe"] == "none", json.dumps(r))

    # 下のボタンが実際に押せる（覆いが残っていないことの実地確認）
    try: pg.click("#welcome-start", timeout=3000)
    except Exception: pass
    pg.wait_for_timeout(400)
    r = pg.evaluate("""() => {
      const el = document.elementFromPoint(195, 700);
      return { tag: el ? el.tagName : null,
               inSplash: !!(el && el.closest && el.closest('#splash')) };
    }""")
    ok("画面の下側が覆いに取られていない", r["inSplash"] is False, json.dumps(r))

    # ---------- 2回目：同期を使ったことがあり、期限が切れている ----------
    pg.evaluate("""async () => {
      await window.Storage.setMeta('drive_consent_at', Date.now() - 86400000);
      await window.Storage.setMeta('drive_token', null);
    }""")
    pg.reload(wait_until="commit")
    pg.wait_for_function("window.__APP_READY === true", timeout=20000)
    pg.wait_for_timeout(600)
    r = pg.evaluate("""() => {
      const a = document.getElementById('splash-ask');
      const s = document.getElementById('splash');
      const lg = document.getElementById('splash-login');
      const sk = document.getElementById('splash-skip');
      return { askShown: !a.hidden, stillUp: !s.classList.contains('is-gone'),
               login: lg.innerText.trim(), skip: sk.innerText.replace(/\\n/g, ' ').trim() };
    }""")
    ok("前に使っていて期限が切れたときだけ聞く", r["askShown"] is True, json.dumps(r))
    ok("聞いている間は覆いを外さない", r["stillUp"] is True, json.dumps(r))
    ok("ログインのボタン文言", r["login"] == "ログインして同期", json.dumps(r["login"]))
    ok("続行のボタンに結果が書いてある",
       "ログインせずに続ける" in r["skip"] and "この端末だけ" in r["skip"],
       json.dumps(r["skip"]))

    # 文字と背景の明度差
    r = pg.evaluate("""() => {
      const g = id => { const e = document.getElementById(id); const c = getComputedStyle(e);
        return { fg: c.color, bg: c.backgroundColor }; };
      const sp = getComputedStyle(document.getElementById('splash'));
      return { tag: g('splash-status'), lead: g('splash-ask-lead'), bg: sp.backgroundColor };
    }""")
    def lum(c):
        v = [int(x) / 255 for x in re.findall(r"\d+", c)[:3]]
        v = [(u / 12.92) if u <= 0.03928 else (((u + 0.055) / 1.055) ** 2.4) for u in v]
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
    def ratio(fg, bg):
        a, b = lum(fg), lum(bg)
        return (max(a, b) + 0.05) / (min(a, b) + 0.05)
    rr = ratio(r["lead"]["fg"], r["bg"])
    ok("説明文と背景の明度差が4.5以上", rr >= 4.5,
       "%.2f fg=%s bg=%s" % (rr, r["lead"]["fg"], r["bg"]))

    # 「ログインせずに続ける」で必ず抜けられる
    pg.click("#splash-skip")
    pg.wait_for_function(
        "document.getElementById('splash').classList.contains('is-gone')", timeout=6000)
    ok("［ログインせずに続ける］で抜けられる", True)

    # ---------- 3回目：期限内のトークンがある ----------
    pg.add_script_tag(content=MOCK)
    pg.evaluate("""async () => {
      window.Drive.__setTransport(window.makeDriveMock());
      await window.Drive.signIn();          // 控えが meta に残る
    }""")
    pg.reload(wait_until="commit")
    pg.wait_for_function("window.__APP_READY === true", timeout=20000)
    # 固定の待ちにしない（V1.62）。機械が混んでいると 400ms では
    # まだ最初の文言のままで、**関係ない変更のたびに赤くなる**。
    pg.wait_for_function(
        "() => (document.getElementById('splash-status').textContent || '').length > 0",
        timeout=10000)
    r = pg.evaluate("""() => {
      const a = document.getElementById('splash-ask');
      return { askHidden: a.hidden,
               status: document.getElementById('splash-status').textContent };
    }""")
    ok("期限内なら何も聞かない", r["askHidden"] is True, json.dumps(r))
    # 見たいのは「いま何をしているかが言葉で出ている」こと。
    # 段階ごとに文言が変わるので、どの段階でも通る語で見る。
    ok("いま何をしているかを言葉で見せる",
       any(w in r["status"] for w in ("同期", "準備", "ドライブ", "読み込")),
       json.dumps(r["status"], ensure_ascii=False))
    pg.wait_for_function(
        "document.getElementById('splash').classList.contains('is-gone')", timeout=10000)
    ok("同期のあと覆いが外れる", True)

    ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  batchX" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
