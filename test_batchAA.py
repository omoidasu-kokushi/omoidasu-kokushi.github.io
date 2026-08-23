#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.43 検証：階層の並び順／「Nつ選べ」の検算／正誤の見え方／
             レベル欄・一言欄の面／ランダムの文字ボタン"""
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
p2s = open(os.path.join(APP, P2), encoding="utf-8").read()

_c = re.search(r"CACHE_NAME = 'v(\d+)\.(\d+)\.(\d+)'", sw)
ok("sw CACHE_NAME が v1.33.0 以降",
   bool(_c) and tuple(int(x) for x in _c.groups()) >= (1, 33, 0),
   _c.group(0) if _c else "not found")
ok("テーマのボタンがヘッダーから消えている", 'id="btn-theme"' not in idx)
ok("設定のテーマ行に指し先がある", 'id="set-theme"' in idx)
ok("サイコロの絵文字を使っていない", "🎲</button>" not in p2s)
ok("ランダムの文字ボタンになっている", ">ランダム</button>" in p2s)


def _external(t):
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t)


def lum(c):
    """rgb(...) と color(srgb r g b) の両方を受ける。
    color-mix() を使うと Chromium は color(srgb …) 形式（0〜1）で返すので、
    \d+ で数字を拾う実装だと桁が壊れて比較が無意味になる。"""
    c = str(c)
    if c.startswith("color("):
        v = [float(x) for x in re.findall(r"[0-9]*\.?[0-9]+", c)[:3]]
    else:
        v = [float(x) / 255 for x in re.findall(r"[0-9]*\.?[0-9]+", c)[:3]]
    v = [(u / 12.92) if u <= 0.03928 else (((u + 0.055) / 1.055) ** 2.4) for u in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def ratio(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text)
          if m.type == "error" and not _external(m.text) else None)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=40000)
    try:
        pg.wait_for_function(
            "document.getElementById('splash').classList.contains('is-gone')", timeout=20000)
    except Exception:
        pass
    pg.wait_for_timeout(2500)

    # ---------- 階層の並び順 ----------
    r = pg.evaluate("""async () => {
      const tree = await window.Storage.buildTree();
      const num = s => { const m = /^\\s*(\\d+)\\s*[.．、]/.exec(s || ''); return m ? +m[1] : null; };
      const out = [];
      tree.forEach(u => {
        const ns = u.children.map(c => num(c.label)).filter(n => n !== null);
        out.push({ unit: u.key, majors: u.children.map(c => c.label).slice(0, 6),
                   sorted: ns.every((v, i) => i === 0 || ns[i-1] <= v),
                   meds: u.children[0] ? u.children[0].children.map(c => c.label).slice(0, 4) : [] });
      });
      return out;
    }""")
    ok("大項目が番号の昇順に並ぶ", all(u["sorted"] for u in r),
       json.dumps([u["majors"] for u in r], ensure_ascii=False)[:300])
    ok("10 が 9 より後ろに来る（文字比較になっていない）",
       all(u["sorted"] for u in r),
       json.dumps(r[0]["majors"], ensure_ascii=False))

    # ---------- 「Nつ選べ」の検算 ----------
    r = pg.evaluate("""async () => {
      const S = window.Storage;
      const qs = await S.getAllQuestions();
      const PICK = {'1':1,'2':2,'3':3,'4':4,'5':5,'１':1,'２':2,'３':3,'４':4,'５':5,
                    '一':1,'二':2,'三':3,'四':4,'五':5};
      const bad = [];
      for (const q of qs) {
        const m = /([0-9０-９一二三四五])\\s*つ選/.exec(q.stem || '');
        if (!m) { continue; }
        const want = PICK[m[1]];
        const at = await S.getAtomsByQuestion(q.q_id);
        const got = at.filter(a => a.is_correct).length;
        if (want && got !== want) { bad.push({ q: q.q_id, want, got, sc: q.select_count }); }
      }
      return { bad, total: qs.length };
    }""")
    ok("「Nつ選べ」と正解数が食い違う問題がシードに無い",
       len(r["bad"]) == 0, json.dumps(r["bad"], ensure_ascii=False)[:400])

    r = pg.evaluate("""async () => {
      // 取り込み時に弾かれることを直接確かめる
      const row = ['必修問題','目標','S','1. テスト','A. テスト','a. テスト','multiple',
        '次のうち正しいものを2つ選べ。',
        JSON.stringify(['① あ','② い','③ う','④ え']),
        JSON.stringify([1]),
        '【解説】②正しい。',
        JSON.stringify([['#テスト'],['#テスト'],['#テスト'],['#テスト']]),
        ''].join('\\t');
      const rep = await window.Storage.importText(row);
      return { imported: rep.imported, errors: (rep.errors||[]).map(e=>e.message) };
    }""")
    ok("「2つ選べ」なのに正解1つの行は取り込まない", r["imported"] == 0, json.dumps(r))
    ok("弾いた理由が作問者に伝わる文面",
       any("2つ選べ" in m and "正解が 1" in m for m in r["errors"]),
       json.dumps(r["errors"], ensure_ascii=False))

    # ---------- レベル欄・一言欄・進捗バー ----------
    pg.evaluate("window.Main.go('home')")
    pg.wait_for_timeout(600)
    r = pg.evaluate("""() => {
      const g = s => getComputedStyle(document.querySelector(s));
      const page = getComputedStyle(document.body).backgroundColor;
      const lv = g('.level-strip'), tip = (document.getElementById('home-tip').hidden = false,
                                           g('.home-tip'));
      const bar = g('.level-bar'), fill = g('.level-bar-fill');
      return { page, lv: lv.backgroundColor, lvShadow: lv.boxShadow,
               tip: tip.backgroundColor, tipShadow: tip.boxShadow,
               barBg: bar.backgroundColor, barH: bar.height,
               fill: fill.backgroundImage.slice(0, 40),
               note: document.getElementById('level-note').textContent,
               noteAlign: getComputedStyle(document.getElementById('level-note')).textAlign };
    }""")
    ok("レベル欄が白い面", r["lv"] == "rgb(255, 255, 255)", json.dumps(r["lv"]))
    ok("一言欄が白い面", r["tip"] == "rgb(255, 255, 255)", json.dumps(r["tip"]))
    ok("どちらも影は付けない（押せないものはフラット）",
       r["lvShadow"] in ("none", "") and r["tipShadow"] in ("none", ""),
       json.dumps([r["lvShadow"], r["tipShadow"]]))
    ok("レベル欄が背景と見分けられる", r["lv"] != r["page"], json.dumps([r["lv"], r["page"]]))
    ok("進捗バーの溝が面と見分けられる（明度差1.15以上）",
       ratio(r["barBg"], r["lv"]) >= 1.15,
       "%.3f  bar=%s lv=%s" % (ratio(r["barBg"], r["lv"]), r["barBg"], r["lv"]))
    ok("進捗バーが細すぎない（8px以上）",
       float(r["barH"].replace("px", "")) >= 8, r["barH"])
    ok("レベルの残数に「次のレベルまで」と書いてある",
       "次のレベルまで" in r["note"] or "達成" in r["note"], json.dumps(r["note"]))
    ok("残数は右端に寄せる（レベル名と左右で対になる）",
       r["noteAlign"] == "right", json.dumps(r["noteAlign"]))

    # ---------- 正誤の見え方 ----------
    pg.evaluate("""async () => {
      const S = window.Storage;
      for (const k of ['onboarding_done','tutorial_finished','ui_tour_done','random_qty_unlocked'])
        { await S.setMeta(k, true); }
      await S.setMeta('pomodoro_enabled', false);
    }""")
    r = pg.evaluate("""async () => {
      window.Half2Impl.tip = () => Promise.resolve(false);
      document.querySelectorAll('.modal-scrim,.modal-card').forEach(e => { e.hidden = true; });
      await window.Main.startSession({mode:'random', count:3, newOnly:true, shuffle:true});
      await new Promise(r => setTimeout(r, 1500));
      const s = window.Main.state.session, q = s.questions[s.index];
      const w = q.atoms.findIndex(a => !a.is_correct);
      [...document.querySelectorAll('#choice-list .choice-card')][w].click();
      await new Promise(r => setTimeout(r, 800));
      document.getElementById('btn-confirm').click();
      await new Promise(r => setTimeout(r, 2400));
      const rows = [...document.querySelectorAll('#rv-choices .cx')].map(c => {
        const cs = getComputedStyle(c);
        return { correct: c.classList.contains('is-correct'),
                 bg: cs.backgroundColor, edge: cs.borderLeftColor,
                 edgeW: cs.borderLeftWidth };
      });
      const active = [...document.querySelectorAll('#rv-choices .eval-btn.is-active')].map(b => {
        const cs = getComputedStyle(b);
        return { cls: b.className, bg: cs.backgroundColor, color: cs.color,
                 border: cs.borderLeftColor };
      });
      return { rows, active, n: rows.length };
    }""")
    rows, active = r["rows"], r["active"]
    corr = [x for x in rows if x["correct"]]
    wrong = [x for x in rows if not x["correct"]]
    ok("正解の肢がちょうど1つ色分けされている", len(corr) == 1, json.dumps(rows, ensure_ascii=False))
    ok("正解の面と誤答の面が違う",
       bool(corr) and bool(wrong) and corr[0]["bg"] != wrong[0]["bg"],
       json.dumps([corr[0]["bg"] if corr else None, wrong[0]["bg"] if wrong else None]))
    # V1.44：誤答の面はやめた。3肢ぶん並ぶので、薄くても赤が画面を占める。
    # 強い色は「正解の緑だけ」にして、探す対象を1つに絞る。
    ok("誤答の肢に面（背景）を付けない",
       bool(wrong) and wrong[0]["bg"] in ("rgba(0, 0, 0, 0)", "transparent"),
       json.dumps(wrong[0]["bg"] if wrong else None))
    ok("正解の肢だけが面を持つ",
       bool(corr) and corr[0]["bg"] not in ("rgba(0, 0, 0, 0)", "transparent"),
       json.dumps(corr[0]["bg"] if corr else None))
    ok("正解の左端の帯が誤答より太い",
       bool(corr) and bool(wrong)
       and float(corr[0]["edgeW"].replace("px", "")) > float(wrong[0]["edgeW"].replace("px", "")),
       json.dumps([corr[0]["edgeW"] if corr else None, wrong[0]["edgeW"] if wrong else None]))

    ok("初見で外すと全肢が「難しい」に点灯する（仕様どおり）",
       len(active) == r["n"] and all("eval-hard" in a["cls"] for a in active),
       json.dumps([a["cls"] for a in active], ensure_ascii=False))
    ok("その評価ボタンは塗りつぶされていない（画面が赤く染まらない）",
       all(a["bg"] == "rgb(255, 255, 255)" for a in active),
       json.dumps([a["bg"] for a in active]))
    ok("選択中は枠と文字色で分かる",
       all(ratio(a["color"], a["bg"]) >= 4.5 for a in active),
       json.dumps(["%.2f" % ratio(a["color"], a["bg"]) for a in active]))
    if corr and active:
        # 正解の面は白より暗い＝色が乗っている。評価ボタンは白のまま。
        ok("正解の面のほうが、評価ボタンより目立つ",
           lum(corr[0]["bg"]) < lum(active[0]["bg"]),
           "corr=%.4f btn=%.4f" % (lum(corr[0]["bg"]), lum(active[0]["bg"])))

    ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  batchAA" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
