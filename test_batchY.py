#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.41 検証：階層バッジ／克服モード／ヘッダーの左右分け／一言欄"""
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

ok("index の script/REQUIRED が実ファイルを指す", idx.count(P1) == 2 and idx.count(P2) == 2)
ok("sw の CORE_ASSETS が実ファイルを指す", P1 in sw and P2 in sw)
ok("他版のファイル名が残っていない",
   len(set(re.findall(r"main_part1_V\d+\.\d+\.js", idx + sw))) == 1 and
   len(set(re.findall(r"main_part2_V\d+\.\d+\.js", idx + sw))) == 1)
_c = re.search(r"CACHE_NAME = 'v(\d+)\.(\d+)\.(\d+)'", sw)
ok("sw CACHE_NAME が v1.30.0 以降",
   bool(_c) and tuple(int(x) for x in _c.groups()) >= (1, 30, 0),
   _c.group(0) if _c else "not found")
ok("版の刻印が更新されている", "V1.41" in idx)

def _external(t):
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t)

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text)
          if m.type == "error" and not _external(m.text) else None)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=20000)
    pg.wait_for_timeout(1500)
    try: pg.click("#welcome-start", timeout=2500)
    except Exception: pass
    pg.wait_for_timeout(600)
    pg.evaluate("window.Main.go('home')")
    pg.wait_for_timeout(500)

    # ---------- ヘッダー：左＝移動 ／ 右＝道具 ----------
    r = pg.evaluate("""() => {
      const g = id => { const e = document.getElementById(id);
        if (!e || e.hidden) { return null; }
        const b = e.getBoundingClientRect(); return { l: Math.round(b.left), r: Math.round(b.right) }; };
      return { home: g('btn-home'), sync: g('btn-hdr-sync'),
               theme: g('btn-theme'), set: g('btn-settings'),
               badge: !!document.querySelector('#btn-settings #hdr-sync-badge'),
               w: window.innerWidth };
    }""")
    ok("ヘッダーにホームがある", bool(r["home"]), json.dumps(r))
    # V1.44：同期もヘッダーから外した（ボタンが多すぎて溢れた）。
    # 未同期の件数だけは設定ボタンのバッジに残す（どこにも出ないと溜まる）。
    ok("同期はヘッダーに出さない", r["sync"] is None, json.dumps(r))
    ok("未同期の件数は設定ボタンに出る", r["badge"] is True, json.dumps(r))
    # V1.43：テーマはヘッダーから外し、設定 4. に一本化した
    # （狭い画面でボタンが溢れたため。同じ入口を2つ置かない決まりにも合う）。
    ok("テーマはヘッダーに出さない", r["theme"] is None, json.dumps(r))
    ok("ホームは左半分にある", r["home"]["l"] < r["w"] / 2, json.dumps(r))
    ok("設定は右端に寄っている", r["set"]["r"] >= r["w"] - 16, json.dumps(r))
    ok("ホームと設定が重なっていない", r["home"]["r"] < r["set"]["l"], json.dumps(r))
    ok("390px 幅でヘッダーが溢れない", r["set"]["r"] <= r["w"], json.dumps(r))

    r = pg.evaluate("""async () => {
      await window.Storage.clearDirty(); await window.Storage.bumpDirty(4);
      await window.Half2Impl.refreshHdrSync();
      const b = document.getElementById('hdr-sync-badge');
      return { hidden: b.hidden, text: b.textContent };
    }""")
    ok("未同期があるとヘッダーにバッジが出る",
       r["hidden"] is False and r["text"] == "4", json.dumps(r))
    r = pg.evaluate("""async () => {
      await window.Storage.clearDirty();
      await window.Half2Impl.refreshHdrSync();
      return document.getElementById('hdr-sync-badge').hidden;
    }""")
    ok("未同期0ならバッジは出ない", r is True)

    # ---------- ホームへ1タップで戻れる ----------
    r = pg.evaluate("""async () => {
      await window.Half2Impl.openRandomSelect();
      await new Promise(r=>setTimeout(r,400));
      const before = window.Main.state.screen;
      document.getElementById('btn-home').click();
      await new Promise(r=>setTimeout(r,400));
      return { before, after: window.Main.state.screen };
    }""")
    ok("どの画面からでも1タップでホームへ戻れる",
       r["before"] == "random" and r["after"] == "home", json.dumps(r))

    # ---------- 一言欄：枠なし・小さな見出し ----------
    r = pg.evaluate("""() => {
      const el = document.getElementById('home-tip');
      el.hidden = false;
      const cs = getComputedStyle(el);
      const nm = document.querySelector('.home-tip-name');
      const nx = document.getElementById('home-tip-next');
      const ns = nx ? getComputedStyle(nx) : null;
      return { bw: cs.borderTopWidth + '/' + cs.borderLeftWidth,
               shadow: cs.boxShadow, bg: cs.backgroundColor,
               name: nm ? nm.textContent : null,
               nameSize: nm ? parseFloat(getComputedStyle(nm).fontSize) : null,
               btnBg: ns ? ns.backgroundColor : null };
    }""")
    ok("一言欄に枠が無い", r["bw"] == "0px/0px", json.dumps(r["bw"]))
    ok("一言欄に影が無い", r["shadow"] in ("none", ""), json.dumps(r["shadow"]))
    # V1.43：背景と同色だと塊の境目が読めなかったので、白い面に戻した。
    # 押せないことは「影が無い」で示す（決まり4-13）。
    ok("一言欄は白い面（背景と見分けられる）",
       r["bg"] == "rgb(255, 255, 255)", json.dumps(r["bg"]))
    ok("「ひとことメモ」の見出しがある", r["name"] == "ひとことメモ", json.dumps(r["name"]))
    ok("見出しは目立たない大きさ（12px以下）",
       r["nameSize"] is not None and r["nameSize"] <= 12, str(r["nameSize"]))
    ok("ボタンは面を保っている（押せることが分かる）",
       r["btnBg"] not in ("rgba(0, 0, 0, 0)", "transparent", None), json.dumps(r["btnBg"]))

    # ---------- 階層バッジ：難しい（赤）が主、未学習（灰）が従 ----------
    r = pg.evaluate("""() => {
      const H = window.Half2Impl;
      return { hard: H.pickBadge({ hard: 3, unlearned: 9 }),
               un  : H.pickBadge({ hard: 0, unlearned: 9 }),
               none: H.pickBadge({ hard: 0, unlearned: 0 }),
               cap : H.pickBadge({ hard: 120, unlearned: 0 }) };
    }""")
    ok("難しいがあるときは赤バッジだけ",
       "badge-line" in r["hard"] and "badge-soft" not in r["hard"], json.dumps(r["hard"]))
    ok("難しいが0なら未学習を控えめに出す",
       "badge-soft" in r["un"] and "badge-line" not in r["un"], json.dumps(r["un"]))
    ok("どちらも0なら何も出さない", r["none"] == "", json.dumps(r["none"]))
    ok("3桁は 99+ に丸める", "99+" in r["cap"], json.dumps(r["cap"]))

    r = pg.evaluate("""async () => {
      const b = await window.Storage.countBadgesByScope();
      return { hasHard: !!b.hard, hasUn: !!b.unlearned,
               unTotal: b.unlearned.total, hardTotal: b.hard.total };
    }""")
    ok("階層ごとの集計に難しいと未学習の両方がある",
       r["hasHard"] and r["hasUn"], json.dumps(r))
    ok("初期状態は全部が未学習（難しいは0）",
       r["hardTotal"] == 0 and r["unTotal"] > 0, json.dumps(r))

    # 「難しい」を1件つくると赤バッジ側へ移る
    r = pg.evaluate("""async () => {
      const S = window.Storage;
      const atoms = await S.getAllAtoms();
      const a = atoms[0];
      await S.commitAnswer(a.atom_id,
        { answer_count: 1, last_eval: 'hard' },
        { eval: 'hard', correct: false, answered_at: Date.now(), schedule_updated: true });
      const b = await S.countBadgesByScope();
      const tree = await S.buildTree();
      return { hardTotal: b.hard.total, unitHard: tree[0].hard, unitUn: tree[0].unlearned };
    }""")
    ok("「難しい」を付けると集計に乗る", r["hardTotal"] == 1, json.dumps(r))
    ok("階層ツリーにも難しい件数が載る", r["unitHard"] == 1, json.dumps(r))
    ok("同じ肢は未学習から外れる", r["unitUn"] >= 0, json.dumps(r))

    # ---------- 克服モード：上位帯からの重み付き抽出 ----------
    r = pg.evaluate("""() => {
      const K = window.Scheduler;
      const mk = (id, pt) => ({ q_id: id, max_priority: pt });
      const sorted = [];
      for (let i = 0; i < 30; i++) { sorted.push(mk('q' + i, 30 - i)); }
      const picked = K.weightedPick(sorted, 5, 3);
      const ids = picked.map(x => x.q_id);
      return { n: picked.length, uniq: new Set(ids).size,
               inBand: ids.every(id => parseInt(id.slice(1), 10) < 15),
               band: K.CONQUER_BAND };
    }""")
    ok("指定した件数だけ選ぶ", r["n"] == 5, json.dumps(r))
    ok("同じものを2回選ばない", r["uniq"] == 5, json.dumps(r))
    ok("上位帯（出題数×3）の外からは選ばない", r["inBand"], json.dumps(r))
    ok("帯の広さは3倍", r["band"] == 3, json.dumps(r))

    r = pg.evaluate("""() => {
      const K = window.Scheduler;
      const sorted = [];
      for (let i = 0; i < 30; i++) { sorted.push({ q_id: 'q' + i, max_priority: 30 - i }); }
      const seen = new Set();
      for (let t = 0; t < 40; t++) {
        K.weightedPick(sorted, 5, 3).forEach(x => seen.add(x.q_id));
      }
      return { variety: seen.size };
    }""")
    ok("毎回まったく同じ顔ぶれにはならない（2番手以降も出る）",
       r["variety"] > 5, json.dumps(r))

    r = pg.evaluate("""() => {
      const K = window.Scheduler;
      const sorted = [{ q_id: 'a', max_priority: 5 }, { q_id: 'b', max_priority: 3 }];
      return { n: K.weightedPick(sorted, 5, 3).length };
    }""")
    ok("候補が出題数より少なくても落ちない", r["n"] == 2, json.dumps(r))

    r = pg.evaluate("""() => {
      const K = window.Scheduler;
      // 点数0だけの帯でも、無限ループにならず件数ぶん返る
      const sorted = [];
      for (let i = 0; i < 10; i++) { sorted.push({ q_id: 'z' + i, max_priority: 0 }); }
      return { n: K.weightedPick(sorted, 4, 3).length };
    }""")
    ok("点数0だけでも選べる（永久に出ない帯を作らない）", r["n"] == 4, json.dumps(r))

    ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  batchY" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
