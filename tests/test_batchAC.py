#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.44 検証：受験する年（日付ではなく年）／選択肢ごとの解説の3段階"""
import json, os, sys, subprocess, glob, re
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))

P1 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
P2 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
for f in ["storage.js", "scheduler.js", "drive.js", "questions.js", P1, P2, "sw.js"]:
    p = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True)
    ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

idx = open(os.path.join(APP, "index.html"), encoding="utf-8").read()
sw = open(os.path.join(APP, "sw.js"), encoding="utf-8").read()

_c = re.search(r"CACHE_NAME = 'v(\d+)\.(\d+)\.(\d+)'", sw)
ok("sw CACHE_NAME が v1.42.0 以降",
   bool(_c) and tuple(int(x) for x in _c.groups()) >= (1, 42, 0),
   _c.group(0) if _c else "not found")
ok("日付入力は残っていない", 'id="set-exam-date"' not in idx)
ok("年のプルダウンがある", 'id="set-exam-year"' in idx)
ok("解説の3段階がある", 'id="set-explain-mode"' in idx
   and idx.count('data-explain=') == 3)
ok("設定の版表示が最新（古い刻印が残っていない）",
   "NurseExamApp_V1.38" not in idx and 'id="build-stamp-settings"' in idx)
ok("版の刻印が2箇所とも V1.53", idx.count("Omoidasu_V1.53") >= 2)

# 資産の版が index と sw で一致（V1.42で入れた決まり）
_idxq = dict(re.findall(r'"\./([^"?]+)\?v=([^"]+)"', idx))
_swq = dict(re.findall(r"'\./([^'?]+)\?v=([^']+)'", sw))
for f in ["styles.css", "questions.js", "storage.js", "scheduler.js", "drive.js", "license.js"]:
    ok("%s の版が index と sw で一致" % f, _idxq.get(f) == _swq.get(f) and _idxq.get(f) == "1.53",
       "idx=%s sw=%s" % (_idxq.get(f), _swq.get(f)))


def _external(t):
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t)


with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text)
          if m.type == "error" and not _external(m.text) else None)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    try:
        pg.wait_for_function(
            "document.getElementById('splash').classList.contains('is-gone')", timeout=25000)
    except Exception:
        pass
    pg.wait_for_timeout(2500)

    # ---------- 受験する年 ----------
    r = pg.evaluate("""async () => {
      const H = window.Half2Impl;
      await H.openSettings();
      await new Promise(r => setTimeout(r, 700));
      const sel = document.getElementById('set-exam-year');
      const now = new Date();
      return { opts: [...sel.options].map(o => ({ v: o.value, t: o.text })),
               d2027: H.examDateForYear(2027), d2028: H.examDateForYear(2028),
               d2031: H.examDateForYear(2031), dNull: H.examDateForYear(''),
               yearOf: H.examYearOf('2029-02-15'),
               thisYear: now.getFullYear() };
    }""")
    vals = [o["v"] for o in r["opts"] if o["v"]]
    ok("2027年は 2/14", r["d2027"] == "2027-02-14", json.dumps(r["d2027"]))
    ok("2028年以降は 2/15", r["d2028"] == "2028-02-15" and r["d2031"] == "2031-02-15",
       json.dumps([r["d2028"], r["d2031"]]))
    ok("空なら null", r["dNull"] is None, json.dumps(r["dNull"]))
    ok("保存値から年を取り出せる", r["yearOf"] == "2029", json.dumps(r["yearOf"]))
    ok("「選ばない」が先頭にある", r["opts"][0]["v"] == "", json.dumps(r["opts"][0]))
    ok("選べる年が6つ並ぶ", len(vals) == 6, json.dumps(vals))
    ok("過ぎた年は出さない",
       all(int(v) >= r["thisYear"] for v in vals), json.dumps(vals))
    ok("画面には日付を出さない（年と「2月中旬」だけ）",
       all(("年" in o["t"] and "月中旬" in o["t"] and "-" not in o["t"])
           for o in r["opts"] if o["v"]),
       json.dumps([o["t"] for o in r["opts"]], ensure_ascii=False))

    r = pg.evaluate("""async () => {
      const H = window.Half2Impl, S = window.Storage, M = window.Main;
      await H.setExamYear('2027');
      await new Promise(r => setTimeout(r, 400));
      /* refreshExamNote が読み直した結果（画面が実際に見ている値）で確かめる。
         S.loadMeta() は _metaCache を返すため、書き込み直後は
         呼ぶ時点によって古い写しが返ることがある。 */
      /* 値をその場で写し取る。S.loadMeta() は _metaCache の【同じオブジェクト】を
         返し、setMeta はそれを書き換えるので、参照を持ち回すと
         あとの操作の結果を見てしまう（実際にこれで嘘の失敗が出た）。 */
      const saved = (M.state.meta || {}).exam_date || null;
      const note = document.getElementById('exam-note').textContent;
      const sel1 = document.getElementById('set-exam-year').value;
      await H.setExamYear('');
      await new Promise(r => setTimeout(r, 400));
      const cleared = (M.state.meta || {}).exam_date || null;
      return { saved: saved, note: note, sel: sel1, cleared: cleared,
               note2: document.getElementById('exam-note').textContent };
    }""")
    ok("保存の形は従来どおり YYYY-MM-DD（scheduler をそのまま使う）",
       r["saved"] == "2027-02-14", json.dumps(r["saved"]))
    ok("選んだ年がプルダウンに残る", r["sel"] == "2027", json.dumps(r["sel"]))
    ok("残り日数と間隔の上限が出る",
       "あと" in r["note"] and "最長" in r["note"], json.dumps(r["note"], ensure_ascii=False))
    ok("案内文にも日付を出さない", "2月14日" not in r["note"], json.dumps(r["note"], ensure_ascii=False))
    ok("「選ばない」で消せる", r["cleared"] is None, json.dumps(r["cleared"]))
    ok("消したら案内も戻る", "まだ入っていません" in r["note2"], json.dumps(r["note2"], ensure_ascii=False))

    # ---------- 解説の3段階 ----------
    r = pg.evaluate("""async () => {
      const M = window.Main, S = window.Storage, H = window.Half2Impl;
      const withExp = { atom_id:'T1', q_id:'Q1', original_num:1, is_correct:false,
                        text:'あ', explanation:'①× これは誤り。理由はこう。', user_memo:null };
      const withMemo = { atom_id:'T2', q_id:'Q1', original_num:2, is_correct:false,
                         text:'い', explanation:'①× これは誤り。', user_memo:'自分のメモ' };
      const noExp = { atom_id:'T3', q_id:'Q1', original_num:3, is_correct:true,
                      text:'う', explanation:'', user_memo:null };
      const out = {};
      for (const m of ['button','hidden','open']) {
        await S.setMeta('explain_mode', m);
        M.state.meta = await S.loadMeta();
        H.refreshExplainMode();
        const a = M.renderAtomBody(withExp), b = M.renderAtomBody(withMemo),
              c = M.renderAtomBody(noExp);
        out[m] = {
          mode: M.explainMode(),
          fold: /cx-exp/.test(a), write: /cx-write/.test(a),
          openBody: /理由はこう/.test(a) && !/cx-exp/.test(a),
          chip: /vd-chip/.test(a),
          memoShown: /自分のメモ/.test(b), memoOrigFold: /memo-orig-inline/.test(b),
          noExpWrite: /cx-write/.test(c), noExpFold: /cx-exp/.test(c),
          noExpChip: /vd-chip/.test(c),
          segActive: [...document.querySelectorAll('#set-explain-mode .seg-btn')]
                       .filter(x => x.classList.contains('is-active'))
                       .map(x => x.getAttribute('data-explain')),
          note: document.getElementById('explain-mode-note').textContent
        };
      }
      // 既定（未設定）は button
      await S.setMeta('explain_mode', null);
      M.state.meta = await S.loadMeta();
      out.def = M.explainMode();
      return out;
    }""")
    bt, hd, op = r["button"], r["hidden"], r["open"]
    ok("既定は「ボタンで出す」", r["def"] == "button", json.dumps(r["def"]))
    ok("button：解説は畳まれ、開くボタンが出る", bt["fold"] and not bt["openBody"], json.dumps(bt))
    ok("hidden：解説を出さない", (not hd["fold"]) and (not hd["openBody"]), json.dumps(hd))
    ok("open：最初から本文が出る", op["openBody"] and not op["fold"], json.dumps(op))
    ok("どのモードでも正誤は必ず見える",
       bt["chip"] and hd["chip"] and op["chip"], json.dumps([bt["chip"], hd["chip"], op["chip"]]))
    ok("隠しているときは「自分の言葉で書く」を出す",
       bt["write"] and hd["write"] and not op["write"],
       json.dumps([bt["write"], hd["write"], op["write"]]))
    ok("自分で書いたメモはどのモードでも必ず出す",
       bt["memoShown"] and hd["memoShown"] and op["memoShown"], json.dumps("memo"))
    ok("hidden では元の解説の折りたたみも出さない",
       bt["memoOrigFold"] and (not hd["memoOrigFold"]) and op["memoOrigFold"],
       json.dumps([bt["memoOrigFold"], hd["memoOrigFold"], op["memoOrigFold"]]))
    ok("元から解説が無い肢は、モードに関係なく「書く」だけ",
       all(x["noExpWrite"] and not x["noExpFold"] and x["noExpChip"] for x in (bt, hd, op)),
       json.dumps([[x["noExpWrite"], x["noExpFold"]] for x in (bt, hd, op)]))
    ok("設定の3択が選択中と一致する",
       bt["segActive"] == ["button"] and hd["segActive"] == ["hidden"]
       and op["segActive"] == ["open"],
       json.dumps([bt["segActive"], hd["segActive"], op["segActive"]]))
    ok("モードごとに説明文が変わる",
       len({bt["note"], hd["note"], op["note"]}) == 3,
       json.dumps([bt["note"], hd["note"], op["note"]], ensure_ascii=False)[:200])

    # ---------- ヘッダーの文字 ----------
    pg.evaluate("window.Main.go('home')")
    pg.wait_for_timeout(500)
    r = pg.evaluate("""() => {
      const vis = id => { const e = document.getElementById(id);
        return e && !e.hidden ? getComputedStyle(e).display !== 'none' : false; };
      const txt = sel => { const e = document.querySelector(sel);
        return e ? getComputedStyle(e).display !== 'none' : false; };
      const tog = document.getElementById('pomodoro-toggle');
      tog.hidden = false;
      return { homeText: txt('#btn-home .hdr-btn-text'),
               setText: txt('#btn-settings .hdr-btn-text'),
               timerText: txt('.pomo-toggle-text'),
               timerLabel: (document.querySelector('.pomo-toggle-text') || {}).textContent,
               w: window.innerWidth,
               right: Math.round(document.getElementById('btn-settings').getBoundingClientRect().right) };
    }""")
    ok("390px でも「ホーム」の文字が出る", r["homeText"] is True, json.dumps(r))
    ok("390px でも「設定」の文字が出る", r["setText"] is True, json.dumps(r))
    ok("ONの横に「タイマー」の文字が出る",
       r["timerText"] is True and "タイマー" in (r["timerLabel"] or ""), json.dumps(r))
    ok("文字を出してもヘッダーが溢れない", r["right"] <= r["w"], json.dumps(r))

    ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  batchAC" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
