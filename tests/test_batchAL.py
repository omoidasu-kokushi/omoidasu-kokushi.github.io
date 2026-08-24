#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.59 検証：同期の圧縮 ＆ 変わっていないときの省略"""
import json, os, sys, io
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))
def read(f): return io.open(os.path.join(APP, f), encoding="utf-8").read()


def code(src):
    import re as _re
    src = _re.sub(r"/\*.*?\*/", "", src, flags=_re.S)
    return _re.sub(r"(?m)^\s*//.*$", "", src)


dv = read("drive.js")
ok("圧縮の入口がある", "function gzipText" in dv)
ok("展開は先頭2バイトで見分ける（版のフラグを持たない）",
   "0x1f" in dv and "0x8b" in dv)
ok("圧縮できない端末では生のまま上げる", "gz || new Blob([text]" in code(dv))
ok("向こうが変わったかだけを見る問い合わせがある", "function fileStamp" in dv)
ok("省いたことは報告に残る",
   "download_skipped" in dv and "upload_skipped" in dv)
ok("版タグは端末ごとの値（同期しない）",
   "'drive_progress_stamp'" in dv
   and "drive_progress_stamp" not in dv.split("META_MAX_KEYS")[1].split("];")[0])


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
        pg.wait_for_timeout(1200)
        try: pg.click("#welcome-start", timeout=2500)
        except Exception: pass
        pg.wait_for_timeout(500)

        # ---------- 圧縮の往復 ----------
        r = pg.evaluate("""async () => {
          const D = window.Drive;
          const logs = [];
          for (let i = 0; i < 3000; i++) {
            logs.push({ atom_id:'ORIG_1_1_'+String(i).padStart(4,'0')+'_1',
              answered_at: 1756000000000 + i, eval:'normal', is_correct:true,
              schedule_updated:true, interval_code:'1d' });
          }
          const text = JSON.stringify({ schema:'x', logs: logs });
          const gz = await D.gzipText(text);
          const back = await D.blobToText(gz);
          const plain = await D.blobToText(new Blob([text]));
          return { rawKB: Math.round(text.length/1024),
                   gzKB: Math.round(gz.size/1024),
                   roundTrip: back === text,
                   plainWorks: plain === text };
        }""")
        ok("3,000件が10分の1以下になる（実測 %dKB → %dKB）" % (r["rawKB"], r["gzKB"]),
           r["gzKB"] * 10 < r["rawKB"], json.dumps(r))
        ok("圧縮して戻すと元に戻る", r["roundTrip"] is True, json.dumps(r))
        ok("圧縮していないファイルも同じ入口で読める（古いファイルが読める）",
           r["plainWorks"] is True, json.dumps(r))

        # ---------- 壊れた入力で落ちないこと ----------
        r = pg.evaluate("""async () => {
          const D = window.Drive;
          const out = {};
          try { out.empty = await D.blobToText(new Blob([])); } catch (e) { out.empty = 'THREW'; }
          try { out.one = await D.blobToText(new Blob([new Uint8Array([0x1f])])); }
          catch (e) { out.one = 'THREW'; }
          try { await D.blobToText(new Blob([new Uint8Array([0x1f,0x8b,0x00,0x01])])); out.bad = 'OK'; }
          catch (e) { out.bad = 'THREW'; }
          return out;
        }""")
        ok("空のファイルでも例外にならない", r["empty"] == "", json.dumps(r))
        ok("1バイトだけのファイルでも例外にならない", r["one"] != "THREW", json.dumps(r))
        ok("gzipを名乗る壊れたファイルは、黙って空にせず失敗させる",
           r["bad"] == "THREW", json.dumps(r))

        # ---------- 省略の条件 ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage;
          const before = await S.getDirty();
          // 解答すると必ず「変わった」と数える
          const atoms = await S.getAllAtoms();
          const a = atoms[0];
          await S.commitAnswer(a.atom_id,
            { last_eval:'normal', answer_count:(a.answer_count||0)+1 },
            { eval:'normal', is_correct:true, answered_at: Date.now(),
              schedule_updated:true, interval_code:'1d' });
          const after = await S.getDirty();
          await S.clearDirty();
          const cleared = await S.getDirty();
          return { before: Number(before||0), after: Number(after||0), cleared: Number(cleared||0) };
        }""")
        ok("解答すると「変わった」と数える（＝上げるのを省かない）",
           r["after"] > r["before"], json.dumps(r))
        ok("同期のあとは0に戻る", r["cleared"] == 0, json.dumps(r))

        ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
        br.close()


runtime_checks()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAL" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
