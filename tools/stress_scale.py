#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上限規模での実測（テスト一式には入れない／手で回す）

なぜ要るか
  日々のテストは同梱の見本問題（453問）で回している。実運用の上限は
  **過去問10年分＋作問 ≒ 5,000問／1年ぶんの学習記録 ≒ 11万件**で、
  そこは一度も通していなかった。問題数だけ、記録だけを大きくした計測は
  あるが、**両方いっぺんに大きい状態**が抜けていた。
  ここで壊れると、利用者が何日もかけて作った中身が入ったあとに分かる。

使い方
    cd <repo>
    python3 -m http.server 8900 &
    python3 tools/stress_scale.py --copies 11      # 453×11＋見本＝5,436問
    python3 tools/stress_scale.py --measure-only   # 作った状態のまま測り直す

  プロファイルは /tmp/omoidasu_stress_profile に残るので、
  --measure-only なら取り込みをやり直さずに何度でも測れる。
"""
import argparse, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
APP  = os.path.dirname(HERE)
PROF = "/tmp/omoidasu_stress_profile"
TSV  = os.path.join(APP, "tmp_stress.tsv")
URL  = "http://127.0.0.1:8900/index.html"


def build_tsv(copies):
    """同梱の見本TSVを、問題文だけ変えて copies 倍にする。
       q_id は unit/major/medium/sub_item/stem のハッシュなので、
       問題文を変えれば別問題として入る。分類は増やさない
       （出題基準は固定なので、問題を足しても階層は増えないのが実態）。"""
    js = r"""
    const fs=require('fs'); global.window={}; global.self=global;
    eval(fs.readFileSync(process.argv[1],'utf8'));
    const rows=global.window.SEED_QUESTIONS_TSV.split(/\r\n|\r|\n/).filter(s=>s.trim());
    const n=parseInt(process.argv[3],10); const out=[];
    for(let c=1;c<=n;c++) for(const r of rows){
      const cells=r.split('\t'); cells[7]='【第'+(105+c)+'回】'+cells[7]; out.push(cells.join('\t'));
    }
    fs.writeFileSync(process.argv[2], out.join('\n'),'utf8');
    console.log(JSON.stringify({rows:out.length, bytes:Buffer.byteLength(out.join('\n'))}));
    """
    r = subprocess.run(["node", "-e", js, os.path.join(APP, "questions.js"), TSV, str(copies)],
                       capture_output=True, text=True)
    if r.returncode:
        print(r.stderr); sys.exit(1)
    return json.loads(r.stdout.strip())


PREP = r"""
async (want) => {
  const out = {};
  out.before_q = await window.Storage.countQuestions();
  if (out.before_q < want) {
    const t = await (await fetch('/tmp_stress.tsv')).text();
    out.estimate_rows = window.Storage.estimateImportRows(t);
    out.room = await window.Storage.checkRoomFor(out.estimate_rows);
    // 取り込み中に画面が固まらないかを rAF の間隔で見る
    const gaps=[]; let last=performance.now(); let raf;
    (function tick(){ const n=performance.now(); gaps.push(n-last); last=n; raf=requestAnimationFrame(tick); })();
    const t0=performance.now();
    const r = await window.Storage.importText(t);
    out.import_ms = Math.round(performance.now()-t0);
    cancelAnimationFrame(raf);
    gaps.shift(); gaps.sort((a,b)=>b-a);
    out.worst_frame_ms = Math.round(gaps[0]||0);
    out.imported = r.imported; out.skipped = r.skipped; out.mismatch = r.mismatch;
  }
  out.q = await window.Storage.countQuestions();
  return out;
}
"""

INJECT = r"""
async (rounds) => {
  const atoms = await window.Storage.getAllAtoms();
  const EV=['hard','normal','easy','master']; const day=86400000, now=Date.now();
  let total=0; const t0=performance.now();
  for (let round=0; round<rounds; round++){
    let chunk=[];
    for (let i=0;i<atoms.length;i++){
      const a=atoms[i], ev=EV[(i+round)%4];
      chunk.push({atom_id:a.atom_id, q_id:a.q_id, eval:ev, is_correct:ev!=='hard',
        mode: round%2?'random':'review', session_id:'stress-'+round,
        answered_at: now-(rounds-round)*30*day-(i%1000)*1000,
        interval_code: ev==='hard'?'10m':'1d', srs_step_after:round,
        schedule_updated:true, think_ms:1200+(i%40)*700});
      if (chunk.length>=5000){ total+=await window.Storage.appendLogs(chunk); chunk=[]; }
    }
    if (chunk.length){ total+=await window.Storage.appendLogs(chunk); }
  }
  return {written: total, ms: Math.round(performance.now()-t0), atoms: atoms.length};
}
"""

MEASURE = r"""
async () => {
  const T = async (n,f)=>{ const t0=performance.now(); let v; try{ v=await f(); }catch(e){ v='ERR:'+e.message; }
                           return [n, Math.round(performance.now()-t0), v]; };
  const out=[];
  out.push(await T('問題数',        async()=>await window.Storage.countQuestions()));
  out.push(await T('記録件数',      async()=>await window.Storage.countLogs()));
  out.push(await T('保存領域',      async()=>await window.Storage.storageInfo()));
  out.push(await T('全アトム読み',  async()=>(await window.Storage.getAllAtoms()).length));
  out.push(await T('全記録読み',    async()=>(await window.Storage.getAllLogs()).length));
  out.push(await T('起動時の再計算', async()=>{ await window.Scheduler.refreshAll({recomputeWeakness:false}); return 1; }));
  out.push(await T('ホーム',        async()=>{ const h=await window.Scheduler.getHomeState(); return {due:h.due_count}; }));
  out.push(await T('取り込み後の再計算', async()=>{ await window.Scheduler.refreshAll({recomputeWeakness:true}); return 1; }));
  out.push(await T('同（2回目）',   async()=>{ await window.Scheduler.refreshAll({recomputeWeakness:true}); return 1; }));
  out.push(await T('分析（小項目）', async()=>(await window.Scheduler.buildDashboard({level:'sub_item'})).rows.length));
  out.push(await T('分析（中項目）', async()=>(await window.Scheduler.buildDashboard({level:'medium'})).rows.length));
  out.push(await T('ランダム出題',  async()=>(await window.Scheduler.buildQueue({mode:'random',count:20})).questions.length));
  /* getKnockQueue(tag, options) … tag は第1引数（§7-A-2）。
     options で {tag:...} を渡すと IDBKeyRange に object が入って DataError で落ちる。 */
  out.push(await T('概念ノック',    async()=>{ const q=await window.Scheduler.getKnockQueue('#人口動態統計',{minutes:5}); return {n:q.questions.length}; }));
  out.push(await T('同期の収集',    async()=>{ const c=await window.Drive.collectProgress(); window.__C=c; return {logs:c.logs.length}; }));
  out.push(await T('同期の圧縮後',  async()=>{
      const s=JSON.stringify(window.__C); window.__C=null;
      if (typeof CompressionStream==='undefined') return {raw_MB: +(new Blob([s]).size/1048576).toFixed(1)};
      const cs=new CompressionStream('gzip'); const w=cs.writable.getWriter();
      w.write(new TextEncoder().encode(s)); w.close();
      const buf=await new Response(cs.readable).arrayBuffer();
      return {raw_MB:+(new Blob([s]).size/1048576).toFixed(1), gzip_MB:+(buf.byteLength/1048576).toFixed(1)};
  }));
  out.push(await T('バックアップ書き出し', async()=>{
      const b=await window.Storage.exportBackup(); const s=JSON.stringify(b);
      const mb=+(new Blob([s]).size/1048576).toFixed(1); return {MB:mb};
  }));
  return out;
}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--copies", type=int, default=11, help="見本453問を何倍にするか（既定11＝約5,000問）")
    ap.add_argument("--rounds", type=int, default=5, help="全アトムを何周ぶん解いた記録を入れるか（既定5）")
    ap.add_argument("--measure-only", action="store_true", help="作った状態のまま測るだけ")
    ap.add_argument("--url", default=URL)
    a = ap.parse_args()

    from playwright.sync_api import sync_playwright

    want = 453 * a.copies
    if not a.measure_only:
        print("見本を%d倍にしたTSVを作る…" % a.copies)
        print(" ", json.dumps(build_tsv(a.copies)))

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROF, args=["--no-sandbox"],
                                                   viewport={"width": 390, "height": 844})
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.set_default_timeout(900000)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(a.url, wait_until="load")
        pg.wait_for_function("window.__APP_READY === true", timeout=300000)
        pg.wait_for_timeout(2000)
        try: pg.click("#welcome-start", timeout=4000)
        except Exception: pass
        pg.wait_for_timeout(600)

        if not a.measure_only:
            print("取り込み…")
            print(" ", json.dumps(pg.evaluate(PREP, want), ensure_ascii=False))
            n = pg.evaluate("async()=>await window.Storage.countLogs()")
            if n < 1000:
                print("学習の記録を%d周ぶん入れる…" % a.rounds)
                print(" ", json.dumps(pg.evaluate(INJECT, a.rounds), ensure_ascii=False))
            pg.reload(wait_until="load")
            pg.wait_for_function("window.__APP_READY === true", timeout=300000)
            pg.wait_for_timeout(2500)

        print("--- 実測")
        for name, ms, v in pg.evaluate(MEASURE):
            print("  %-20s %7d ms  %s" % (name, ms, json.dumps(v, ensure_ascii=False)[:150]))
        print("JSエラー:", errs[:8] if errs else "なし")
        ctx.close()

    if os.path.exists(TSV) and not a.measure_only:
        os.remove(TSV)
        print("(tmp_stress.tsv は消しました)")


main()
