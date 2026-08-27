#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBX：試験日を1回だけ聞く（V1.99）

【なぜ要るか】
試験日を書き込む場所は設定のセレクト1箇所しか無かった。
ところが試験日が無いと、次の**5つがまとめて無効**になる。

  逆算プランナー（V1.50）／解禁の見通し（V1.94）／直前期の緩和（V1.95）／
  忘却の間隔上限（examCapMs）／直前モード（examPhase・残10日）

買ったばかりの人が設定を開く確率は高くないので、
**5機能が「たまたま設定を開いて年を選んだ人」にしか届いていなかった。**

【いつ聞くか】
チュートリアルを終えた直後。V1.60 の `requestPersist` と同じ作法で、
**この人にとって記録が価値を持ち始めた瞬間**に頼む。
起動直後に聞くと、まだ何も積み上がっていないので断られて終わる。

【1回だけ】
断られたら二度と聞かない（`exam_ask_done`）。
代わりに力試し画面へ静かな入口を残す。緩和中とは同時に出ない
（試験日が無ければ緩和も起きないので、同じ1行を使い回す）。
"""
import io, json, os, re, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


st = read("storage.js")
html = read("index.html")
css = read("styles.css")
p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
j2 = read(p2)

ok("聞いた印を持っている", "exam_ask_done           : false," in st)
ok("ダイアログがある", 'id="modal-exam-ask"' in html and 'id="exam-ask-year"' in html)
ok("あとで、が押せる", 'id="exam-ask-later"' in html)
ok("聞く関数がある", "function maybeAskExamDate(" in j2)
ok("**チュートリアル完了直後に聞く**", "return maybeAskExamDate().then(function (asked) {" in j2)
ok("なぜその瞬間かが書いてある", "requestPersist と同じ作法" in j2)
ok("**5機能が無効になることが書いてある**", "5つがまとめて無効" in j2)
ok("覆いを重ねない", "重ねると両方読まれない" in j2)
ok("力試し画面に静かな入口がある", 'id="exam-set-date"' in j2 and ".exam-ease-btn{" in css)
ok("緩和中とは同時に出ないと書いてある", "同時には出ない" in j2)
ok("版番号・CACHE_NAME・?v= の3箇所が揃っている",
   (lambda i, w: i and w and i == w)(
       (re.search(r"\?v=([0-9.]+)", html) or [None, None])[1],
       (re.search(r"\?v=([0-9.]+)", read("sw.js")) or [None, None])[1]))

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(1400)

    # --- 聞く／聞かない ---
    r = pg.evaluate("""async () => {
      const S = window.Storage, H = window.Half2Impl, M = window.Main;
      const snapAsk = await S.getMeta('exam_ask_done', false);
      const snapDate = await S.getMeta('exam_date', null);

      await S.setMeta('exam_ask_done', false);
      await S.setMeta('exam_date', null);
      const first = await H.maybeAskExamDate();
      const opened = !document.getElementById('modal-exam-ask').hidden;
      const opts = document.querySelectorAll('#exam-ask-year option').length;
      M.closeModals();
      /* 2回目は出ない（印が立っている） */
      const second = await H.maybeAskExamDate();

      /* すでに試験日がある人には出ない */
      await S.setMeta('exam_ask_done', false);
      await S.setMeta('exam_date', '2027-02-14');
      const hasDate = await H.maybeAskExamDate();

      await S.setMeta('exam_ask_done', snapAsk);
      await S.setMeta('exam_date', snapDate);
      M.closeModals();
      return { first:first, opened:opened, opts:opts, second:second, hasDate:hasDate,
               flag: await S.getMeta('exam_ask_done', false) };
    }""")
    ok("**まだ聞いていない人には聞く**", r["first"] is True and r["opened"] is True,
       json.dumps(r, ensure_ascii=False))
    ok("年の選択肢が並ぶ", r["opts"] >= 6, json.dumps(r))
    ok("**一度聞いたら二度と聞かない**", r["second"] is False, json.dumps(r))
    ok("**すでに試験日を入れている人には聞かない**", r["hasDate"] is False, json.dumps(r))

    # --- 答えると保存される／あとでなら保存しない ---
    a = pg.evaluate("""async () => {
      const S = window.Storage, H = window.Half2Impl;
      const snapDate = await S.getMeta('exam_date', null);
      await S.setMeta('exam_date', null);
      await S.setMeta('exam_ask_done', false);
      await H.maybeAskExamDate();
      const sel = document.getElementById('exam-ask-year');
      const y = sel.options[1].value;               /* 最初の実年 */
      sel.value = y;
      await H.answerExamAsk(true);
      const saved = await S.getMeta('exam_date', null);

      await S.setMeta('exam_date', null);
      await S.setMeta('exam_ask_done', false);
      await H.maybeAskExamDate();
      await H.answerExamAsk(false);                 /* あとで */
      const later = await S.getMeta('exam_date', null);

      await S.setMeta('exam_date', snapDate);
      return { y:y, saved:saved, later:later,
               closed: document.getElementById('modal-exam-ask').hidden };
    }""")
    ok("**決定すると試験日が入る**",
       a["saved"] and a["saved"].startswith(a["y"]), json.dumps(a, ensure_ascii=False))
    ok("**［あとで］では入らない**", a["later"] is None, json.dumps(a, ensure_ascii=False))
    ok("答えたら覆いが片付く", a["closed"] is True, json.dumps(a, ensure_ascii=False))

    # --- 力試し画面の静かな入口 ---
    v = pg.evaluate("""async () => {
      const S = window.Storage, H = window.Half2Impl;
      const snap = await S.getMeta('exam_date', null);
      await S.setMeta('exam_date', null);
      await H.openExamList();
      const none = { hidden: document.getElementById('exam-ease').hidden,
                     html: document.getElementById('exam-ease').innerHTML,
                     ask: document.getElementById('exam-ease').classList.contains('is-ask') };
      const d = new Date(Date.now() + 86400000 * 20);
      await S.setMeta('exam_date', d.getFullYear() + '-'
        + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0'));
      await H.openExamList();
      const near = { hidden: document.getElementById('exam-ease').hidden,
                     text: document.getElementById('exam-ease').textContent,
                     ask: document.getElementById('exam-ease').classList.contains('is-ask') };
      const far = new Date(Date.now() + 86400000 * 300);
      await S.setMeta('exam_date', far.getFullYear() + '-'
        + String(far.getMonth()+1).padStart(2,'0') + '-' + String(far.getDate()).padStart(2,'0'));
      await H.openExamList();
      const away = { hidden: document.getElementById('exam-ease').hidden };
      await S.setMeta('exam_date', snap);
      return { none:none, near:near, away:away };
    }""")
    ok("**試験日が無いときは入口が出る**",
       v["none"]["hidden"] is False and "試験日を入れる" in v["none"]["html"]
       and v["none"]["ask"] is True, json.dumps(v["none"], ensure_ascii=False))
    ok("**直前期は緩和の説明に切り替わる（入口とは同時に出ない）**",
       v["near"]["hidden"] is False and "解禁に必要な割合" in v["near"]["text"]
       and v["near"]["ask"] is False, json.dumps(v["near"], ensure_ascii=False))
    ok("試験日があって遠いときは何も出ない", v["away"]["hidden"] is True,
       json.dumps(v["away"], ensure_ascii=False))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBX" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
