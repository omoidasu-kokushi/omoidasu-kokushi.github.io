# -*- coding: utf-8 -*-
"""test_verdict_coach.py — 正誤ポップアップの中身（V2.59 → V2.94 で裁定が変わった）

【V2.94（2026-09-10・利用者裁定）で方針が変わりました】
  利用者の言葉：「不正解！なんたらかんたら、って解説が出てくるけどこれはやめて。
  一問一答でもその仕様はいらない」「正解！ 残念…は残す」

  ポップアップに出すのは **見出しだけ**（○「正解！」／×「残念…」）。
  下の2行——「正解は ④ ○○」と、V2.59 で足した肢ごとの評価の案内——は出さない。

  **V2.59 の要望を消したのではなく、上書きの裁定が出た**ということ。
  V2.59 が解こうとした「肢ごとの評価を忘れる」は、初期点灯（推奨評価を
  全肢に点けておく）で空欄にはならないので、文言で補うより
  画面を覆わないほうを採った、という判断です。
  以下の検査は「もう出さないこと」を固定する形に書き換えてあります。
  何を決めたかの記録として、V2.59 の説明もそのまま残します。

--- 以下 V2.59 のときの説明（記録） ---
V2.59 正誤ポップアップで肢ごとの評価を促す

利用者の指摘：「選択肢ごとに評価するのを忘れがち」。
次へを塞ぐ案（未確認があるうちは進めない／全肢押すまで進めない）は
利用者が採らなかった。§4-③の初期点灯（推奨評価を全肢に点けておく＝
全部押さなくてよい）と正面からぶつかるため。

採った案：正誤ポップアップに一行だけ足す。
  正解   → 説明できなかった選択肢は［難しい］を押して、もう一度
  不正解 → 説明できた選択肢は［普通］か［易しい］を押しておこう

評価軸は「その選択肢の裏回答が言えたか」であって正誤ではない。
正解／不正解を見た直後が、いちばんその区別を取り違える瞬間なので、
そこに置いている。ここで固定するのは「出る場所」と「出ない場所」。
"""
import json, os, re, sys
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p1 = open(os.path.join(base, "20260815_main_part1_V1.38.js"), encoding="utf-8").read()
cs = open(os.path.join(base, "styles.css"), encoding="utf-8").read()
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()
ix = open(os.path.join(base, "index.html"), encoding="utf-8").read()

ok("案内の器がある", 'id="vp-coach"' in ix)
ok("CSSがある", ".vp-coach{" in cs)
ok("模試では出さない（もともとポップアップ自体を出さない）",
   "if (isExamMode()) { return; }" in p1)
# V2.61：pointer-events:none で一度も動いていなかったクリックハンドラを外した。
# 開ける道もあるが、開けるとポップアップの下の選択肢を押せなくなる＝
# 「非ブロッキング」という意図された性質のほうを壊す。
ok("動かないクリックハンドラを残していない（V2.61）",
   "$('#verdict-pop'), 'click'" not in p1)
ok("指は通したまま（非ブロッキングを壊していない）",
   "pointer-events:none" in cs.split(".verdict-pop{")[1].split("}")[0])

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)

    def shot(right, natoms):
        return pg.evaluate("""([right, n]) => {
          const M = window.Main;
          const atoms = [];
          for (let i = 1; i <= n; i++) {
            atoms.push({ atom_id: 'a' + i, original_num: i, text: '選択肢' + i,
                         is_correct: i === 1 });
          }
          M.showVerdictPopup({ atoms: atoms, answeredRight: right });
          const c = document.getElementById('vp-coach');
          const pop = document.getElementById('verdict-pop');
          return { hidden: !!c.hidden,
                   text: (c.textContent || '').replace(/\s+/g, ' ').trim(),
                   popShown: !pop.hidden,
                   title: (document.getElementById('vp-title').textContent || '') };
        }""", [right, natoms])

    def shot2(right, natoms):
        """見出し・正解文・案内の3つを見る（V2.94）。"""
        return pg.evaluate("""([right, n]) => {
          const M = window.Main;
          const atoms = [];
          for (let i = 1; i <= n; i++) {
            atoms.push({ atom_id: 'a' + i, original_num: i, text: '選択肢' + i,
                         is_correct: i === 1 });
          }
          M.showVerdictPopup({ atoms: atoms, answeredRight: right });
          const c = document.getElementById('vp-coach');
          const ans = document.getElementById('vp-answer');
          const pop = document.getElementById('verdict-pop');
          return { coachHidden: !!c.hidden,
                   coachText: (c.textContent || '').trim(),
                   ansHidden: !!ans.hidden,
                   ansText: (ans.textContent || '').trim(),
                   popShown: !pop.hidden,
                   mark: (document.getElementById('vp-mark').textContent || '').trim(),
                   title: (document.getElementById('vp-title').textContent || '').trim() };
        }""", [right, natoms])

    a = shot2(True, 4)
    ok("正解の見出しは「正解！」", a["title"] == "正解！" and a["mark"] == "○",
       json.dumps(a, ensure_ascii=False))
    ok("正解でもポップアップは出る", a["popShown"], json.dumps(a, ensure_ascii=False))
    ok("正解のときに案内を出さない（V2.94）", a["coachHidden"] and not a["coachText"],
       json.dumps(a, ensure_ascii=False))
    ok("正解のときに正解文を出さない（V2.94）", a["ansHidden"] and not a["ansText"],
       json.dumps(a, ensure_ascii=False))

    b = shot2(False, 4)
    ok("不正解の見出しは「残念…」", b["title"] == "残念…" and b["mark"] == "×",
       json.dumps(b, ensure_ascii=False))
    ok("不正解でも「正解は ○○」を出さない（V2.94の主眼）",
       b["ansHidden"] and not b["ansText"], json.dumps(b, ensure_ascii=False))
    ok("不正解でも案内を出さない（V2.94）", b["coachHidden"] and not b["coachText"],
       json.dumps(b, ensure_ascii=False))
    ok("肢の本文がポップアップに漏れていない",
       "選択肢" not in (b["ansText"] + b["coachText"]), json.dumps(b, ensure_ascii=False))

    c = shot2(True, 1)
    ok("一問一答でも見出しだけ", c["popShown"] and c["coachHidden"] and c["ansHidden"],
       json.dumps(c, ensure_ascii=False))

    # 4択→一問一答→4択と続けても、前の文面が残らない
    shot2(False, 4); c2 = shot2(True, 1); d = shot2(True, 4)
    ok("一問一答をはさんでも文面が残らない",
       c2["coachHidden"] and c2["ansHidden"], json.dumps(c2, ensure_ascii=False))
    ok("戻っても文面は出ない", d["coachHidden"] and d["ansHidden"],
       json.dumps(d, ensure_ascii=False))

    # V2.94：読ませる文が無くなったので短くした。正解0.6秒／不正解0.9秒。
    shot2(False, 4)
    pg.wait_for_timeout(400)
    still = pg.evaluate("() => !document.getElementById('verdict-pop').hidden")
    ok("不正解は0.4秒ではまだ出ている", still, str(still))
    pg.wait_for_timeout(900)
    gone = pg.evaluate("() => document.getElementById('verdict-pop').hidden")
    ok("1.3秒あれば消えている（出しっぱなしにしない）", gone, str(gone))

    ok("設定でポップアップを切っている人には出さない",
       pg.evaluate("""async () => {
         await window.Storage.setMeta('verdict_popup_enabled', false);
         window.Main.state.meta.verdict_popup_enabled = false;
         document.getElementById('verdict-pop').hidden = true;
         window.Main.showVerdictPopup({ atoms: [{atom_id:'a1',original_num:1,text:'x',is_correct:true},
                                                {atom_id:'a2',original_num:2,text:'y',is_correct:false}],
                                        answeredRight: true });
         return document.getElementById('verdict-pop').hidden;
       }"""))
    ok("JSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
    br.close()

# 表示時間はコードで固定する（実測待ちにすると赤くなったり緑になったりする）
# V2.59 は「案内を読む時間」として正解1.8秒・不正解1.6〜2.4秒を取っていた。
# V2.94 で読ませる文が無くなったので、正解0.6秒／不正解0.9秒に戻した。
ok("読ませる文が無いぶん、出している時間を短くしてある（V2.94）",
   "var ms = right ? 600 : 900;" in p1)
ok("なぜ短くしたかが書いてある",
   "2文字を読むのにその長さは要らない" in p1)

def _vers(txt, pat):
    return sorted(set(re.findall(pat, txt)))
sw_cache = _vers(sw, r"CACHE_NAME = 'v([0-9.]+)'")
sw_q = _vers(sw, r"\?v=([0-9.]+)")
ix_q = _vers(ix, r"\?v=([0-9.]+)")
ix_stamp = _vers(ix, r"Omoidasu_V([0-9.]+)")
ok("index.htmlの?v=が1種類に揃っている", len(ix_q) == 1, str(ix_q))
ok("indexとswの?v=が一致している", ix_q == sw_q, str(ix_q) + " vs " + str(sw_q))
ok("build-stampの版が?v=と一致している",
   len(ix_stamp) == 1 and ix_stamp[0] == ix_q[0], str(ix_stamp))
ok("CACHE_NAMEが?v=と同じ系列", len(sw_cache) == 1 and sw_cache[0] == ix_q[0] + ".0", str(sw_cache))

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  verdict_coach" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
