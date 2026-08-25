#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBI：取り込んだ解説HTMLを無害化する（V1.84）

解説は**HTMLのまま**描画している（<b> <u> 表 色つきspan が中身の一部）。
つまり取り込んだ文字列が、そのまま innerHTML に入る。
敵対的な取り込みデータで実測したところ：

  ・`<img src=x onerror="...">` が**実行された**
  ・`<iframe src="https://…">` `<img src="https://…">`
    `style="background:url(https://…)"` で**外部へ通信が出た**

`<script>` は innerHTML では走らないが、onerror は走る。これは2つの約束を破る。

  ① 「記録はこの端末の中だけです。ログインも通信も要りません」（初回の説明）
  ② 買い切りで配ったあと、利用者どうしが問題データを配り合うことは自然に起きる。
     悪意ある1行で、その端末のIndexedDB全部とドライブのトークンが読める。

直し方は「全部エスケープ」ではない（表も強調も消える）。
**実データに出てくるタグだけ通す**許可制にした。
同梱453問（解説1,018件）で通しても**本文の文字数は1文字も変わらない**ことを実測。
"""
import io, json, os, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []

def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()

p1 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
js1 = read(p1)
p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
js2 = read(p2)

ok("無害化の関数がある", "function sanitizeExplanationHtml(" in js1)
ok("描画の入口で必ず通る", "var s = sanitizeExplanationHtml(html);" in js1)
ok("許可制（禁止リストではない）", "SAFE_TAGS" in js1 and "SAFE_ATTRS" in js1)
ok("img は許可しない", "img:1" in js1.split("DROP_WHOLE")[1][:400])
ok("style から外部取得だけ落とす", "STYLE_BAD" in js1 and "url" in js1.split("STYLE_BAD")[1][:120])
ok("判定は動かない文書（DOM）で行う", "createHTMLDocument" in js1)
ok("なぜ全部エスケープにしないかが書いてある", "表も強調も消えてしまう" in js1)
ok("実測した数字が残っている", "6496" in js1 and "2980" in js1)
ok("印刷のメモもエスケープする", "esc(q.user_memo)" in js2)

from playwright.sync_api import sync_playwright

PAYLOADS = {
    "img_onerror": '<img src=x onerror="window.__X1=1">',
    "script_tag": '<script>window.__X2=1<\\/script>',
    "svg_onload": '<svg onload="window.__X3=1"></svg>',
    "iframe": '<iframe src="https://example.com/beacon"></iframe>',
    "img_remote": '<img src="https://example.com/b.png">',
    "style_url": '<div style="background:url(https://example.com/bg.png);color:#c00">背景</div>',
    "a_js": '<a href="javascript:window.__X4=1">押して</a>',
    "onclick": '<span onclick="window.__X5=1">ここ</span>',
    "object": '<object data="https://example.com/x"></object>',
}

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    # 外部へ出ようとしたら記録して止める
    hits = []
    ctx.route("**/*", lambda route: (hits.append(route.request.url), route.abort())
              if "127.0.0.1" not in route.request.url else route.continue_())
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=30000)
    pg.wait_for_timeout(1800)
    try:
        pg.click("#welcome-start", timeout=4000)
    except Exception:
        pass
    pg.wait_for_timeout(700)

    # --- 実際に画面へ入れて、動くかどうかを見る
    res = pg.evaluate("""(payloads) => {
      const M = window.Main;
      const host = document.createElement('div');
      host.id = '__advhost';
      document.body.appendChild(host);
      const out = {};
      Object.keys(payloads).forEach(k => {
        host.innerHTML = M.prepareExplanationHtml('本文' + payloads[k] + '本文');
        out[k] = { html: host.innerHTML.slice(0, 160),
                   text: (host.textContent || '').indexOf('本文本文') >= 0 || (host.textContent||'').indexOf('本文') >= 0 };
      });
      out.__handlers = document.querySelectorAll('#__advhost [onclick],#__advhost [onerror],#__advhost [onload]').length;
      out.__imgs = document.querySelectorAll('#__advhost img').length;
      out.__iframes = document.querySelectorAll('#__advhost iframe').length;
      return out;
    }""", PAYLOADS)
    pg.wait_for_timeout(1500)
    flags = pg.evaluate("() => ['__X1','__X2','__X3','__X4','__X5'].filter(k => window[k])")

    ok("onerror が実行されない", "__X1" not in flags, json.dumps(flags))
    ok("インラインのイベント属性が残らない", res["__handlers"] == 0, str(res["__handlers"]))
    ok("img が残らない", res["__imgs"] == 0, str(res["__imgs"]))
    ok("iframe が残らない", res["__iframes"] == 0, str(res["__iframes"]))
    ok("どの仕掛けも動かない", not flags, json.dumps(flags))
    ok("style の url() が消える", "url(" not in res["style_url"]["html"], res["style_url"]["html"][:120])
    ok("style の色は残る", "color" in res["style_url"]["html"], res["style_url"]["html"][:120])
    ok("外部への通信が出ない", not [h for h in hits if "example.com" in h],
       json.dumps(hits[:4], ensure_ascii=False))

    # --- 本物の解説が削られていないこと（ここが緩むと中身が壊れる）
    keep = pg.evaluate("""async () => {
      const S = window.Storage, M = window.Main;
      const qs = await S.getAllQuestions(), atoms = await S.getAllAtoms();
      const srcs = [];
      qs.forEach(q => { if (q.overall_explanation) srcs.push(q.overall_explanation);
                        if (q.comparison_table) srcs.push(q.comparison_table); });
      atoms.forEach(a => { if (a.explanation) srcs.push(a.explanation); });
      const strip = x => x.replace(/<[^>]*>/g, '').replace(/\\s+/g, '');
      const before = srcs.join('\\n');
      const after = srcs.map(x => M.sanitizeExplanationHtml(x)).join('\\n');
      const c = (t, re) => (t.match(re) || []).length;
      const t0 = performance.now();
      srcs.forEach(x => M.sanitizeExplanationHtml(x));
      return { n: srcs.length, ms: Math.round(performance.now() - t0),
               text_before: strip(before).length, text_after: strip(after).length,
               b_b: c(before, /<b[ >]/g), b_a: c(after, /<b[ >]/g),
               u_b: c(before, /<u[ >]/g), u_a: c(after, /<u[ >]/g),
               td_b: c(before, /<td[ >]/g), td_a: c(after, /<td[ >]/g),
               span_b: c(before, /<span[ >]/g), span_a: c(after, /<span[ >]/g),
               cls_b: c(before, /class=/g), cls_a: c(after, /class=/g) };
    }""")
    ok("本文の文字が1文字も減らない", keep["text_before"] == keep["text_after"],
       json.dumps(keep))
    ok("強調（b・u）が残る", keep["b_b"] == keep["b_a"] and keep["u_b"] == keep["u_a"], json.dumps(keep))
    ok("表のセルが残る", keep["td_b"] == keep["td_a"], json.dumps(keep))
    ok("色つきspanとclassが残る", keep["span_b"] == keep["span_a"] and keep["cls_b"] == keep["cls_a"],
       json.dumps(keep))
    ok("重くない（解説1,000件で300ms未満）", keep["ms"] < 300, "%dms / %d件" % (keep["ms"], keep["n"]))

    # --- 表の描画がこれまでどおりであること
    tbl = pg.evaluate("""async () => {
      const S = window.Storage, M = window.Main;
      const qs = (await S.getAllQuestions()).filter(q => q.comparison_table);
      if (!qs.length) return { tables: 0 };
      const out = qs.map(q => M.prepareExplanationHtml(q.comparison_table)).join('\\n');
      const c = (t, re) => (t.match(re) || []).length;
      return { tables: qs.length, scroll: c(out, /tbl-scroll/g),
               th: c(out, /<th[ >]/g), colspan: c(out, /colspan/g) };
    }""")
    ok("表は今までどおり横スクロールで包まれる", tbl["tables"] == 0 or tbl["scroll"] == tbl["tables"],
       json.dumps(tbl))
    ok("colspan/rowspan が残る", tbl["tables"] == 0 or tbl["colspan"] > 0, json.dumps(tbl))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBI" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
