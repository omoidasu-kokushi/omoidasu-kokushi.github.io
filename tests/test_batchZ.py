#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.42 検証：資産の版付け／ノックの時計の後始末／アラーム音の名前／
             設定の並び／一言欄の文字階層／同期ボタンの文言／シードの中身"""
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
sw  = open(os.path.join(APP, "sw.js"), encoding="utf-8").read()
css = open(os.path.join(APP, "styles.css"), encoding="utf-8").read()
p1s = open(os.path.join(APP, P1), encoding="utf-8").read()
p2s = open(os.path.join(APP, P2), encoding="utf-8").read()

# ---------- 資産の版付け（スプラッシュが崩れた原因） ----------
SHARED = ["styles.css", "questions.js", "storage.js", "scheduler.js", "drive.js"]
_idxq = dict(re.findall(r'"\./([^"?]+)\?v=([^"]+)"', idx))
_swq = dict(re.findall(r"'\./([^'?]+)\?v=([^']+)'", sw))
for f in SHARED:
    ok("%s に版が付いている" % f, f in _idxq and f in _swq,
       "idx=%s sw=%s" % (_idxq.get(f), _swq.get(f)))
    ok("%s の版が index と sw で一致" % f, _idxq.get(f) == _swq.get(f),
       "idx=%s sw=%s" % (_idxq.get(f), _swq.get(f)))
ok("版無しの参照が残っていない",
   '"./styles.css"' not in idx and "'./styles.css'," not in sw)
ok("CSSが読めなくても覆いとして成立する保険がある",
   "#splash{" in idx and "position:fixed" in idx.split("#splash{")[1][:120])
ok("保険は styles.css より前にある",
   0 < idx.find("#splash{") < idx.find('href="./styles.css'))

_c = re.search(r"CACHE_NAME = 'v(\d+)\.(\d+)\.(\d+)'", sw)
ok("sw CACHE_NAME が v1.32.0 以降",
   bool(_c) and tuple(int(x) for x in _c.groups()) >= (1, 32, 0),
   _c.group(0) if _c else "not found")

# ---------- 中断フック ----------
ok("セッションを畳んだことを伝えるフックがある", "onAbort" in p1s and "onAbort" in p2s)
ok("ノックの後片付けがある", "function abortKnock" in p2s)
ok("中断では endSession を呼び返さない",
   "M.endSession();" not in p2s.split("function abortKnock")[1].split("function finishKnock")[0])

# ---------- 設定の並び ----------
_h = re.findall(r'class="set-head">(\d)\.\s*([^\n<]+)', idx)
ok("設定は9節ある", len(_h) == 9, json.dumps(_h, ensure_ascii=False))
ok("7 は 出題と表示のカスタマイズ", any(n == "7" and "出題と表示" in t for n, t in _h),
   json.dumps(_h, ensure_ascii=False))
ok("8 は データ", any(n == "8" and "データ" in t for n, t in _h),
   json.dumps(_h, ensure_ascii=False))
ok("節番号が1..9で重複していない",
   sorted(n for n, _ in _h) == [str(i) for i in range(1, 10)],
   json.dumps([n for n, _ in _h]))

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
    pg.wait_for_function("window.__APP_READY === true", timeout=30000)
    try:
        pg.wait_for_function(
            "document.getElementById('splash').classList.contains('is-gone')", timeout=20000)
    except Exception:
        pass
    pg.wait_for_timeout(1200)
    try: pg.click("#welcome-start", timeout=3000)
    except Exception: pass
    pg.wait_for_timeout(700)
    pg.evaluate("window.Main.go('home')")
    pg.wait_for_timeout(500)

    # ---------- シードの中身 ----------
    r = pg.evaluate("""async () => {
      const S = window.Storage;
      const qs = await S.getAllQuestions(), at = await S.getAllAtoms();
      const tree = await S.buildTree();
      const bad = qs.filter(q => !q.stem || !q.unit || !q.major).length;
      const noAtoms = [];
      const byQ = {};
      at.forEach(a => { byQ[a.q_id] = (byQ[a.q_id] || 0) + 1; });
      qs.forEach(q => { if (!byQ[q.q_id]) { noAtoms.push(q.q_id); } });
      const noTag = at.filter(a => !a.tags || !a.tags.length).length;
      const badUnit = tree.filter(u => /[【】]/.test(u.key)).map(u => u.key);
      return { q: qs.length, a: at.length, bad, noAtoms: noAtoms.length,
               noTag, units: tree.map(u => u.key), badUnit,
               ranks: qs.reduce((m, q) => (m[q.rank] = (m[q.rank]||0)+1, m), {}) };
    }""")
    ok("シードが100問以上入っている", r["q"] >= 100, json.dumps(r["q"]))
    ok("すべての問題に選択肢がある", r["noAtoms"] == 0, json.dumps(r["noAtoms"]))
    ok("単元・大項目・問題文が欠けている問題が無い", r["bad"] == 0, json.dumps(r["bad"]))
    ok("すべての肢にテーマタグが付いている", r["noTag"] == 0, json.dumps(r["noTag"]))
    ok("単元名に【】が残っていない", r["badUnit"] == [], json.dumps(r["badUnit"], ensure_ascii=False))
    ok("ランクが S/A/B/C のみ",
       set(r["ranks"].keys()) <= {"S", "A", "B", "C"}, json.dumps(r["ranks"]))

    # 正解番号が選択肢の範囲に収まっている（0始まり）
    r = pg.evaluate("""async () => {
      const S = window.Storage;
      const qs = await S.getAllQuestions();
      let noCorrect = 0, allCorrect = 0;
      for (const q of qs.slice(0, 200)) {
        const at = await S.getAtomsByQuestion(q.q_id);
        const c = at.filter(a => a.is_correct).length;
        if (c === 0) { noCorrect++; }
        if (c === at.length && at.length > 1) { allCorrect++; }
      }
      return { noCorrect, allCorrect };
    }""")
    ok("正解が1つも無い問題が無い", r["noCorrect"] == 0, json.dumps(r))
    ok("全肢が正解になっている問題が無い", r["allCorrect"] == 0, json.dumps(r))

    # ---------- 一言欄の文字階層 ----------
    r = pg.evaluate("""() => {
      const el = document.getElementById('home-tip'); el.hidden = false;
      const px = id => parseFloat(getComputedStyle(document.getElementById(id)).fontSize);
      return { label: px('home-tip-label'), title: px('home-tip-title'),
               body: px('home-tip-body'),
               name: parseFloat(getComputedStyle(document.querySelector('.home-tip-name')).fontSize) };
    }""")
    ok("題 ＞ 見出し ＞ 本文 の順に小さくなる",
       r["label"] > r["title"] > r["body"], json.dumps(r))
    ok("題がいちばん大きい",
       r["label"] == max(r.values()), json.dumps(r))
    ok("「ひとことメモ」は控えめのまま", r["name"] < r["body"], json.dumps(r))

    # ---------- アラーム音の名前 ----------
    r = pg.evaluate("""async () => {
      const H = window.Half2Impl;
      await H.openSettings();
      await new Promise(r=>setTimeout(r,500));
      const opt = () => [...document.getElementById('set-alarm').options]
        .filter(o=>o.value==='custom')[0].textContent;
      const before = opt();
      const blob = new Blob([new Uint8Array([1,2,3,4])], {type:'audio/mpeg'});
      const f = new File([blob], 'ぴよぴよ.mp3', {type:'audio/mpeg'});
      await window.Storage.putUserAudio(f);
      await H.refreshAlarmFileNote();
      const after = opt();
      const note = document.getElementById('alarm-file-note').textContent;
      await window.Storage.deleteUserAudio();
      await H.refreshAlarmFileNote();
      return { before, after, note, cleared: opt() };
    }""")
    ok("音が無いときは <<Free>>", r["before"] == "<<Free>>", json.dumps(r["before"]))
    ok("入れたらファイル名になる（拡張子は落とす）", r["after"] == "ぴよぴよ", json.dumps(r["after"]))
    ok("説明にもファイル名が出る", "ぴよぴよ" in r["note"], json.dumps(r["note"]))
    ok("消したら <<Free>> に戻る", r["cleared"] == "<<Free>>", json.dumps(r["cleared"]))
    ok("画面から「自分の音」の語が消えている", "自分の音" not in idx)

    # ---------- 同期ボタンの文言 ----------
    # V1.44：ヘッダーの同期ボタンは撤去し、設定 6. に一本化した。
    # 文言は【押したら何が起きるか】で決める決まりなので、
    # 未ログインなら「ログインして同期」＝押した1回でログインまで済む、と読める。
    r = pg.evaluate("""async () => {
      const D = window.Drive, H = window.Half2Impl;
      D.__state.token = null;
      await window.Storage.setMeta('drive_token', null);
      await H.openSettings();
      await H.refreshDrive();
      const out = D.tokenValid();
      const outText = document.getElementById('drive-sync-label').textContent;
      D.__state.token = { access_token: 'x', expires_at: Date.now() + 3600000 };
      await H.refreshDrive();
      const inText = document.getElementById('drive-sync-label').textContent;
      const logoutShown = !document.getElementById('btn-drive-logout').hidden;
      D.__state.token = null;
      await H.refreshDrive();
      return { out, outText, inText, logoutShown,
               hdrBtn: !!document.getElementById('btn-hdr-sync') };
    }""")
    ok("同期ボタンはヘッダーに無い（設定に一本化）", r["hdrBtn"] is False, json.dumps(r))
    ok("未ログインは「ログインして同期」", r["outText"] == "ログインして同期",
       json.dumps(r["outText"], ensure_ascii=False))
    ok("ログイン済は「今すぐ同期」", r["inText"] == "今すぐ同期",
       json.dumps(r["inText"], ensure_ascii=False))
    ok("ログイン済のときだけログアウトが出る", r["logoutShown"] is True, json.dumps(r))

    # ---------- ノックの時計：途中で抜けても止まる ----------
    r = pg.evaluate("""async () => {
      const H = window.Half2Impl, M = window.Main, S = window.Storage;
      const cs = await S.getConceptStats();
      const tag = (cs[0] && cs[0].tag) || (window.CONCEPT_TAGS_MASTER||[])[0];
      await H.startKnock(tag, 5);
      await new Promise(r=>setTimeout(r,600));
      const during = { screen: M.state.screen, mode: M.state.session.mode,
                       shown: !document.getElementById('knock-timer').hidden,
                       body: document.body.classList.contains('is-knock'),
                       ticking: !!H.st.knock.tick,
                       t: document.getElementById('knock-time').textContent };
      document.getElementById('btn-home').click();
      await new Promise(r=>setTimeout(r,700));
      const t1 = document.getElementById('knock-time').textContent;
      await new Promise(r=>setTimeout(r,1400));
      const after = { screen: M.state.screen,
                      shown: !document.getElementById('knock-timer').hidden,
                      body: document.body.classList.contains('is-knock'),
                      ticking: !!H.st.knock.tick,
                      t1: t1, t2: document.getElementById('knock-time').textContent,
                      summary: !document.getElementById('modal-knock-summary').hidden };
      return { during, after };
    }""")
    d, a = r["during"], r["after"]
    ok("ノックが始まると時計が出て動く",
       d["shown"] and d["body"] and d["ticking"] and d["mode"] == "knock",
       json.dumps(d, ensure_ascii=False))
    ok("ホームを押すとホームへ戻る", a["screen"] == "home", json.dumps(a, ensure_ascii=False))
    ok("戻ったら時計の表示が消える", a["shown"] is False and a["body"] is False,
       json.dumps(a, ensure_ascii=False))
    ok("戻ったら時計が止まる（V1.42で直した不具合）",
       a["ticking"] is False, json.dumps(a, ensure_ascii=False))
    ok("戻ったあと残り時間が減り続けない", a["t1"] == a["t2"],
       "%s -> %s" % (a["t1"], a["t2"]))
    ok("中断ではまとめの画面を出さない", a["summary"] is False, json.dumps(a["summary"]))

    ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  batchZ" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
