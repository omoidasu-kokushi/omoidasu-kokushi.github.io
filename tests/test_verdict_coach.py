# -*- coding: utf-8 -*-
"""test_verdict_coach.py — V2.59 正誤ポップアップで肢ごとの評価を促す

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

    a = shot(True, 4)
    ok("正解でも案内が出る", a["hidden"] is False, json.dumps(a, ensure_ascii=False))
    ok("正解の案内は［難しい］を押させる方向",
       "説明できなかった" in a["text"] and "難しい" in a["text"], a["text"])
    ok("正解の案内で［普通］［易しい］を勧めない",
       "易しい" not in a["text"], a["text"])

    b = shot(False, 4)
    ok("不正解でも案内が出る", b["hidden"] is False, json.dumps(b, ensure_ascii=False))
    ok("不正解の案内は［普通］か［易しい］を押させる方向",
       "説明できた" in b["text"] and "普通" in b["text"] and "易しい" in b["text"], b["text"])
    ok("不正解の案内で［難しい］を勧めない", "難しい" not in b["text"], b["text"])

    c = shot(True, 1)
    ok("一問一答（肢が1本）では案内を出さない", c["hidden"] is True,
       json.dumps(c, ensure_ascii=False))
    ok("そのときもポップアップ自体は出る", c["popShown"], json.dumps(c, ensure_ascii=False))

    # 4択→一問一答→4択と続けても、前の文面が残らない
    shot(False, 4); c2 = shot(True, 1); d = shot(True, 4)
    ok("一問一答をはさんでも案内が残らない", c2["hidden"] is True, json.dumps(c2, ensure_ascii=False))
    ok("戻れば正解の案内が出る",
       d["hidden"] is False and "説明できなかった" in d["text"], json.dumps(d, ensure_ascii=False))

    # 案内を出したときの正解は1.8秒。0.6秒のままだと30字は読めない。
    # 中間（1.2秒）でまだ出ていて、時間が過ぎれば消えることを実測する。
    shot(True, 4)
    pg.wait_for_timeout(1200)
    still = pg.evaluate("() => !document.getElementById('verdict-pop').hidden")
    ok("正解でも1.2秒後にはまだ出ている（0.6秒で消えていない）", still, str(still))
    pg.wait_for_timeout(1400)
    gone = pg.evaluate("() => document.getElementById('verdict-pop').hidden")
    ok("時間が過ぎれば消える（出しっぱなしにしない）", gone, str(gone))

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
ok("案内を出すときの正解の表示時間を延ばしてある（0.6秒では読めない）",
   "right ? (multi ? 1800 : 600)" in p1)

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
