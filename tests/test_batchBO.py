#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBO：ランクを効かせた抽選（V1.90）

【なぜ「並べ替え」ではなく「抽選」なのか】
直近5年（第111〜115回）1,200問で、4回分からランクを付けて残り1回を本番として
採点する検証をした（in-sample で測ると効果が3倍に水増しされるため）。

  一般+状況（プール950問・ボーダー62%）
    450問時点  均等 63.7点 → 重み 66.8点（+3.1）／ 完全ソート 65.3点（+1.6）
    600問時点  均等 76.5点 → 重み 78.1点（+1.6）／ 完全ソート 74.1点（**-2.4**）

完全ソートは600問時点で5回中4回が均等より悪い。本試験の配点の35.8%はB中項目から
出るので、S・Aを先に固めるやり方は後半で必ず折り返してくる。

【なぜ必修には掛けないのか】
同じ検証を必修だけでやると、重みは全帯域で**悪化**させた。
    120問時点  均等 68.7点 → 重み 67.2点（5回中4回で悪化）
    180問時点  均等 90.6点 → 重み 89.1点（5回中5回で悪化）
必修は50問を54中項目へほぼ1問ずつ配るので、的を絞るほど取りこぼす。
**必修は「順番」ではなく「量」で守る。それが §16 の枠（V1.89）。**

【壊してはいけないもの】
・未学習と既出の境目は動かさない（一周の完了問数が変わってはいけない）
・本日の復習の出題順は1問も変えない
・問題数を減らさない。同じ集合を返す
・「頻出問題を優先する」トグルをOFFにしたら、V1.89以前と同じ均等に戻る
"""
import io, json, os, re, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


sc = read("scheduler.js")
html = read("index.html")

ok("抽選の関数がある", "function rankShuffle(" in sc)
ok("必修は重み1.0で扱う", "c.hissu ? 1.0 : rankWeight(c.rank)" in sc)
ok("既存のランク重みをそのまま使う", "var RANK_WEIGHT = { S: 2.5, A: 1.6, B: 1.0, C: 0.3 };" in sc)
ok("トグルOFFで均等に戻ると書いてある",
   "var pick = preferFrequent ? rankShuffle : shuffle;" in sc)
ok("必修に掛けない理由が書いてある", "必修には掛けない" in sc)
ok("完全ソートを採らない理由が書いてある", "並べ替えではなく重み付き抽選が正しい" in sc)
css = read("styles.css")
# 版そのものは batchAC / batchAH が横断で見ている。ここで数字を焼くと
# 次の改修で必ず赤くなり、**関係ない場所を直させる**ので焼かない。
ok("版番号・CACHE_NAME・?v= の3箇所が揃っている",
   read("index.html").count("?v=") >= 6
   and read("sw.js").count("?v=") >= 6
   and (lambda i, w: i and w and i == w)(
       (re.search(r"\?v=([0-9.]+)", read("index.html")) or [None, None])[1],
       (re.search(r"\?v=([0-9.]+)", read("sw.js")) or [None, None])[1]))
ok("折り返したタグが重ならないよう行の隙間を取ってある",
   "row-gap:19px" in css and css.count("row-gap:19px") >= 2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(1400)

    # --- 抽選そのもの（作り物の候補で確かめる） ---
    r = pg.evaluate("""() => {
      const K = window.Scheduler;
      const mk = (rank, hissu, i) => ({ q_id:'q'+i, rank:rank, hissu:hissu, unlearned:1 });
      const list = [];
      for (let i = 0; i < 400; i++) { list.push(mk('S', false, 'S'+i)); }
      for (let i = 0; i < 400; i++) { list.push(mk('A', false, 'A'+i)); }
      for (let i = 0; i < 400; i++) { list.push(mk('B', false, 'B'+i)); }
      for (let i = 0; i < 400; i++) { list.push(mk('C', false, 'C'+i)); }
      /* 上位200件に各ランクが何件入るか。重みどおりなら S>A>B>C */
      const head = {S:0,A:0,B:0,C:0};
      for (let t = 0; t < 20; t++) {
        K.rankShuffle(list, 1000 + t * 7919).slice(0, 200)
          .forEach(c => { head[c.rank]++; });
      }
      /* 必修だけの集合では、ランクが違っても偏らないこと */
      const his = [];
      for (let i = 0; i < 400; i++) { his.push(mk('S', true, 'HS'+i)); }
      for (let i = 0; i < 400; i++) { his.push(mk('C', true, 'HC'+i)); }
      const hh = {S:0,C:0};
      for (let t = 0; t < 20; t++) {
        K.rankShuffle(his, 2000 + t * 7919).slice(0, 200)
          .forEach(c => { hh[c.rank]++; });
      }
      const a = K.rankShuffle(list, 4242).map(c => c.q_id);
      const b = K.rankShuffle(list, 4242).map(c => c.q_id);
      const c = K.rankShuffle(list, 9999).map(c => c.q_id);
      const sorted = x => x.slice().sort().join('|');
      return { head:hh && head, hissuHead:hh,
               same: a.join('|') === b.join('|'),
               differs: a.join('|') !== c.join('|'),
               keepsSet: sorted(a) === sorted(list.map(x => x.q_id)),
               len: a.length, srcLen: list.length };
    }""")
    h = r["head"]
    ok("**S が A より前に来やすい**", h["S"] > h["A"], json.dumps(h))
    ok("**A が B より前に来やすい**", h["A"] > h["B"], json.dumps(h))
    ok("**B が C より前に来やすい**", h["B"] > h["C"], json.dumps(h))
    ok("**C も0にはならない（切り捨てない）**", h["C"] > 0, json.dumps(h))
    tot = sum(h.values()) or 1
    ok("Sの取り分が実測の狙い（4割前後）に収まる",
       0.32 <= h["S"] / tot <= 0.50, json.dumps({"S%": round(100 * h["S"] / tot, 1), **h}))
    hh = r["hissuHead"]
    ok("**必修どうしはランクで偏らない（均等に扱う）**",
       abs(hh["S"] - hh["C"]) < 0.10 * (hh["S"] + hh["C"]), json.dumps(hh))
    ok("同じ seed なら同じ並びになる", r["same"] is True, json.dumps(r))
    ok("seed が違えば並びも違う", r["differs"] is True, json.dumps(r))
    ok("**同じ集合を返す（1問も落とさない・増やさない）**",
       r["keepsSet"] is True and r["len"] == r["srcLen"], json.dumps(r))

    # --- 実際のキューで効くか ---
    # 同梱453問は S121 / A225 / B103 / C4 で、**すでにS+Aが76%**を占める。
    # 押しのける相手（B）が少ないので、ここで見える差は小さい。
    # 過去問1,200問（S349 / A361 / B490＝Bが41%）を入れてから本領が出る。
    q = pg.evaluate("""async () => {
      const K = window.Scheduler;
      const cnt = qs => { const d = {S:0,A:0,B:0,C:0};
        qs.forEach(x => { const r = String(x.rank||'B').toUpperCase();
          if (d[r] !== undefined) { d[r]++; } }); return d; };
      const run = async pf => {
        const acc = {S:0,A:0,B:0,C:0}; let n = 0;
        for (let i = 0; i < 12; i++) {
          const r = await K.buildQueue({ mode:'random', count:60, applyGuard:false,
            newOnly:true, shuffle:true, seed:1000 + i * 7919,
            hissuQuota:false, preferFrequent:pf });
          const d = cnt(r.questions);
          for (const k in d) { acc[k] += d[k]; }
          n += r.questions.length;
        }
        return { acc:acc, n:n };
      };
      return { on: await run(true), off: await run(false) };
    }""")
    ok("トグルONでも問題数は変わらない",
       q["on"]["n"] == q["off"]["n"] and q["on"]["n"] == 720,
       json.dumps(q, ensure_ascii=False))
    ok("**トグルONでSの取り分が上がる**",
       q["on"]["acc"]["S"] > q["off"]["acc"]["S"], json.dumps(q, ensure_ascii=False))
    ok("**Cの取り分は増えない**",
       q["on"]["acc"]["C"] <= q["off"]["acc"]["C"], json.dumps(q, ensure_ascii=False))

    # --- 壊してはいけないもの ---
    guard = pg.evaluate("""async () => {
      const K = window.Scheduler;
      /* 本日の復習は mode:'review' で別経路。順番が1問も変わらないこと */
      const r1 = await K.buildQueue({ mode:'review', count:30, preferFrequent:true });
      const r2 = await K.buildQueue({ mode:'review', count:30, preferFrequent:false });
      const ids = x => x.questions.map(q => q.q_id).join('|');
      /* 未学習と既出の境目が動かないこと＝一周の完了問数が同じ */
      const base = { mode:'random', count:9999, applyGuard:false, newOnly:true,
                     shuffle:true, seed:13579, hissuQuota:false };
      const a = await K.buildQueue(Object.assign({}, base, { preferFrequent:true }));
      const b = await K.buildQueue(Object.assign({}, base, { preferFrequent:false }));
      const sortedIds = x => x.questions.map(q => q.q_id).sort().join('|');
      return { reviewSame: ids(r1) === ids(r2), reviewN: r1.questions.length,
               oneLapSame: a.questions.length === b.questions.length,
               setSame: sortedIds(a) === sortedIds(b),
               lapN: a.questions.length };
    }""")
    ok("**本日の復習の出題順は1問も変わらない**",
       guard["reviewSame"] is True, json.dumps(guard, ensure_ascii=False))
    ok("**一周の完了問数が同じ（境目を動かしていない）**",
       guard["oneLapSame"] is True, json.dumps(guard, ensure_ascii=False))
    ok("**一周で出る問題の顔ぶれも同じ（順番だけの話）**",
       guard["setSame"] is True, json.dumps(guard, ensure_ascii=False))

    # --- 必修の枠（V1.89）と両立するか ---
    both = pg.evaluate("""async () => {
      const K = window.Scheduler, S = window.Storage;
      await S.setMeta('hissu_mode', 'strong');       /* floor 40% */
      const r = await K.buildQueue({ mode:'random', count:40, applyGuard:false,
                                     newOnly:true, shuffle:true, seed:11111,
                                     preferFrequent:true });
      await S.setMeta('hissu_mode', 'auto');
      return { n:r.questions.length, hissu:r.hissu_count, share:r.hissu && r.hissu.share };
    }""")
    ok("**ランク抽選を入れても必修の枠は効く**",
       both["hissu"] >= round(40 * 0.40) * 0.9 and both["n"] == 40,
       json.dumps(both, ensure_ascii=False))

    # --- 折り返したタグの当たり判定が重ならないか（V1.90 で見つけた古い穴） ---
    # ランク抽選で先頭に来る問題が変わり、**タグが2行に折り返す問題**が出た。
    # .tag-pill::after は上下へ9pxずつ出ているのに、行の隙間が5pxしかなく、
    # 2行目と 13px 重なっていた（batchAP が実測で捕まえた）。
    # 重なると、タップが隣の行へ吸われて別のテーマが開く。
    wrap = pg.evaluate("""() => {
      const box = document.createElement('div');
      box.style.cssText = 'position:fixed;left:0;top:0;width:300px;z-index:1';
      box.className = 'atom-tags';
      for (let i = 0; i < 8; i++) {
        const b = document.createElement('button');
        b.type = 'button'; b.className = 'tag-pill';
        b.textContent = '#テスト用のながいタグ' + i;
        box.appendChild(b);
      }
      document.body.appendChild(box);
      const px = v => parseFloat(v) || 0;
      const rects = [...box.querySelectorAll('.tag-pill')].map(el => {
        const r = el.getBoundingClientRect();
        const a = getComputedStyle(el, '::after');
        return { x:r.left + px(a.left), y:r.top + px(a.top),
                 w:r.width - px(a.left) - px(a.right),
                 h:r.height - px(a.top) - px(a.bottom),
                 visH: Math.round(r.height), top: Math.round(r.top) };
      });
      let over = 0, minH = 999;
      for (let i = 0; i < rects.length; i++) {
        minH = Math.min(minH, Math.round(rects[i].h));
        for (let j = i + 1; j < rects.length; j++) {
          const a = rects[i], b = rects[j];
          const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
          const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
          if (ox > 1 && oy > 1) { over++; }
        }
      }
      const rows = new Set(rects.map(r => r.top)).size;
      box.remove();
      return { over: over, rows: rows, minHit: minH, n: rects.length };
    }""")
    ok("試験用のタグが実際に折り返している（試験そのものが空回りしていない）",
       wrap["rows"] >= 2, json.dumps(wrap, ensure_ascii=False))
    ok("**折り返しても当たり判定が重ならない**",
       wrap["over"] == 0, json.dumps(wrap, ensure_ascii=False))
    ok("**広げた当たり判定は36px以上のまま**",
       wrap["minHit"] >= 36, json.dumps(wrap, ensure_ascii=False))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBO" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
