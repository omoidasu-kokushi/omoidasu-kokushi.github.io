# -*- coding: utf-8 -*-
"""test_oneq_verdict.py — 一問一答の「この選択肢は正しい」表示と、裏回答ボタンの塗り（V2.93）

【利用者の要望（原文に近い形で残す）】
  「問われている選択肢が正しかった場合、取り消し線はつかずに赤い太字になるけど、
   『○ 正しい』とか分かりやすくて大きい表示を、選択肢と元の問題を見るの間に
   設置してほしい」
  「言えた／言えなかった は淡い赤ぬりつぶしと淡い緑塗りつぶしにしよう。
   白塗りつぶしださいかも」

【なぜ要るか】
  誤りの肢は「取り消し線＋正解は【…】」で一目で分かる。
  正しい肢は赤の太字になるだけで、**強調なのか誤りなのかが判別しにくい**。
  赤は誤りの色でもあるので、なおさら紛れる。色に意味を持たせず、文字で書く。

【ここで固定すること】
  ・正しい肢のときだけ「この選択肢は正しい」が出る（誤りの肢には出さない）
  ・置き場所は【肢】と「元の問題を見る」の間＝#choice-list の先頭
  ・取り消し線は今までどおり誤りの肢にだけ
  ・裏回答の2枚が塗りつぶしになっていて、赤と緑で別の色である
  ・地の色に混ぜているので、テーマを変えても淡いまま
"""
import io
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))


APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p1 = io.open(os.path.join(APP, "20260815_main_part1_V1.38.js"), encoding="utf-8").read()
cs = io.open(os.path.join(APP, "styles.css"), encoding="utf-8").read()

ok("なぜ文字で書くのかが残っている", "赤は誤りの色でもある" in p1)
ok("正しい肢のときだけ出す、と書いてある", "誤りの肢には出さない" in p1)
ok("先頭に差し込んでいる（＝肢と元の問題の間）", "list.insertBefore(li, list.firstChild)" in p1)
ok("塗りは地の色に混ぜている（テーマに追従）", "color-mix(in srgb, var(--c-easy" in cs)
ok("赤と緑で別の色を使っている",
   "color-mix(in srgb, var(--c-hard" in cs and "color-mix(in srgb, var(--c-easy" in cs)
ok("color-mix が使えない環境の説明がある", "color-mix が使えない環境" in cs)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")

PAYLOAD = {
    "questions": [
        {
            "source": "検査用 正しい肢", "pool": "main", "unit": "必修",
            "target": "検査用", "rank": "S",
            "major": "1. 健康の定義と理解", "medium": "A. 健康の定義",
            "question_type": "single", "stem": "検査用の問題。正しいのはどれか。",
            "overall_explanation": "検査用の全体解説である。",
            "is_splittable": True,
            "atoms": [
                {"original_num": 1, "is_correct": True, "text": "正しい言葉",
                 "statement": "正しい言葉である。", "explanation": "正しいので正解である。",
                 "tags": []},
                {"original_num": 2, "is_correct": False, "text": "誤った言葉",
                 "statement": "誤った言葉である。", "explanation": "誤りである。",
                 "tags": []},
            ],
        }
    ]
}


sys.path.insert(0, os.path.join(APP, "tools"))
import journey_lib as J          # noqa: E402  時計を進めるため


def prepare(pg, want_correct_atom):
    """1問だけの状態に作り直してから、一問一答を出す。

    2問目以降は**必ず作り直す**こと。1回採点すると期日が動くので、
    同じ手順をもう一度やっても期日が来ず、前の画面が残ったままになる
    （実測：2ケース目から前の表示を見て誤判定していた）。"""
    pg.evaluate("""async (txt) => {
        await window.Storage.resetAll();
        await window.Storage.setMeta('seed_imported', true);
        await window.Storage.importText(txt, {});
        await window.Scheduler.refreshAll({ recomputeWeakness: true });
    }""", json.dumps(PAYLOAD, ensure_ascii=False))
    return start_one_q(pg, want_correct_atom)


def start_one_q(pg, want_correct_atom):
    """一問一答を1問だけ出す。

    一問一答になるのは「本日の復習」で、期日を迎えた肢が1〜2個のときだけ
    （decideFormat / SPLIT_MODES）。そこで
      ・見せたい肢だけ「普通」＝初見1時間後
      ・もう片方は「簡単」＝30日後
    にしてから2時間進める。期日が来ているのは狙った1肢だけになる。
    """
    pg.evaluate("""async (arg) => {
        const S = window.Storage, K = window.Scheduler;
        const qs = await S.getAllQuestions();
        const q = qs.find(x => x.source === '検査用 正しい肢');
        const atoms = await S.getAtomsByQuestion(q.q_id);
        await K.applyQuestionEvaluations(q.q_id, atoms.map(a => ({
            atom_id: a.atom_id,
            eval: (!!a.is_correct === arg.wantCorrect) ? 'normal' : 'easy',
            is_correct: true
        })), { mode: 'random', sessionId: 'v', thinkMs: 1000 });
    }""", {"wantCorrect": want_correct_atom})
    pg.evaluate("(ms) => window.__advance(ms)", 2 * 3600 * 1000)
    pg.evaluate("""async () => {
        await window.Scheduler.refreshAll({ recomputeWeakness: true });
        await window.Main.startSession({ mode: 'review', count: 1 });
    }""")
    pg.wait_for_timeout(500)
    pg.evaluate("() => { const p = document.querySelector('#verdict-pop');"
                " if (p) { p.hidden = true; } }")
    return pg.evaluate("""() => {
        const st = document.querySelector('#oq-in-stem');
        return { single: !!st,
                 word: st ? (st.querySelector('.oq-word') || {}).textContent : null };
    }""")


with sync_playwright() as p:
    br, ctx, pg = J.new_page(p)
    pg.set_default_timeout(120000)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true")
    pg.wait_for_timeout(800)

    got = prepare(pg, True)
    ok("一問一答の形で出せた", got["single"], json.dumps(got, ensure_ascii=False))
    if got["single"]:
        # --- 正しい肢に×を押す（＝外す）。肢は正しいので表示が出るはず ---
        st = pg.evaluate("""async () => {
            const x = document.querySelector('.oq-x');
            if (x) { x.click(); }
            await new Promise(r => setTimeout(r, 500));
            const v = document.getElementById('oq-verdict');
            const list = document.getElementById('choice-list');
            const exp = document.getElementById('oq-atom-exp');
            const row = document.getElementById('oq-in-stem');
            return {
                shown: !!v,
                text: v ? v.textContent.replace(/\\s+/g, '') : '',
                first: !!(v && list && list.firstElementChild === v),
                beforeExtras: !!(v && exp &&
                    (v.compareDocumentPosition(exp) & Node.DOCUMENT_POSITION_FOLLOWING)),
                strike: !!(row && row.classList.contains('is-false')),
                h: v ? Math.round(v.getBoundingClientRect().height) : 0,
                fs: v ? getComputedStyle(v.querySelector('.oq-verdict-text')).fontSize : '',
            };
        }""")
        ok("正しい肢のときに表示が出る", st["shown"], json.dumps(st, ensure_ascii=False))
        # V2.95：文言を「正しい」だけに短くした（利用者の指定「いかに情報量を減らすかが重要」）
        ok("文言は「正しい」だけ", st["text"].replace("○", "") == "正しい", st["text"])
        ok("○の印が付いている", "○" in st["text"], st["text"])
        ok("選択肢のすぐ下（一覧の先頭）にある", st["first"], json.dumps(st))
        ok("「元の問題を見る」より前にある", st["beforeExtras"] or not st["shown"],
           json.dumps(st))
        ok("正しい肢に取り消し線は付かない", not st["strike"], json.dumps(st))
        ok("大きい（高さ50px以上）", st["h"] >= 50, st["h"])

        # --- 誤りの肢に○を押す。こちらには出さない ---
        pg.evaluate("() => window.Main.endSession && window.Main.endSession()")
        g2 = prepare(pg, False)
        ok("2ケース目も一問一答で出せた", g2["single"], json.dumps(g2, ensure_ascii=False))
        st2 = pg.evaluate("""async () => {
            const o = document.querySelector('.oq-o');
            if (o) { o.click(); }
            await new Promise(r => setTimeout(r, 500));
            const row = document.getElementById('oq-in-stem');
            return { shown: !!document.getElementById('oq-verdict'),
                     strike: !!(row && row.classList.contains('is-false')),
                     fix: !!document.querySelector('.oq-fix') };
        }""")
        ok("誤りの肢には出さない", not st2["shown"], json.dumps(st2))
        ok("誤りの肢には取り消し線が付く", st2["strike"], json.dumps(st2))
        ok("誤りの肢には正解が出る", st2["fix"], json.dumps(st2))

        # --- 裏回答の2枚が塗りつぶしで、別の色 ---
        pg.evaluate("() => window.Main.endSession && window.Main.endSession()")
        prepare(pg, False)
        col = pg.evaluate("""async () => {
            const x = document.querySelector('.oq-x');
            if (x) { x.click(); }
            await new Promise(r => setTimeout(r, 500));
            const no = document.querySelector('.oq-g-no');
            const yes = document.querySelector('.oq-g-yes');
            if (!no || !yes) { return { ready: false }; }
            const cn = getComputedStyle(no), cy = getComputedStyle(yes);
            const surface = getComputedStyle(document.body).backgroundColor;
            return { ready: true, no: cn.backgroundColor, yes: cy.backgroundColor,
                     surface: surface };
        }""")
        ok("裏回答の2枚が出ている", col.get("ready"), json.dumps(col, ensure_ascii=False))
        if col.get("ready"):
            def rgb(v):
                m = re.findall(r"[\d.]+", v or "")
                return [float(x) for x in m[:3]] or [0, 0, 0]
            no, yes = rgb(col["no"]), rgb(col["yes"])
            ok("塗りつぶしてある（透明ではない）",
               "rgba(0, 0, 0, 0)" not in (col["no"], col["yes"]),
               json.dumps(col, ensure_ascii=False))
            ok("赤と緑で別の色", no != yes, json.dumps(col, ensure_ascii=False))
            ok("「言えなかった」は赤寄り（R が G より大きい）", no[0] > no[1],
               json.dumps(col, ensure_ascii=False))
            ok("「言えた」は緑寄り（G が R より大きい）", yes[1] > yes[0],
               json.dumps(col, ensure_ascii=False))

    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  oneq_verdict" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
