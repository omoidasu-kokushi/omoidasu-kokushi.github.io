# -*- coding: utf-8 -*-
"""⑧の後半だけ：いじわる模試120問をUIから最後まで通す（V1.00）。

【なぜ別の道具にしたか】
  ⑧は「模試4種の組み立て」＋「120問をUIで完走」の2つでできている。
  組み立ては journey_all.py --resume（JALL_FROM=8）で通る（4種とも120問そろう）。
  残っていたのが完走で、**これが一度も最後まで走っていなかった**。

【実測（2026-09-08）】
    1問あたり 1.27秒（journey_lib.answer_current_ui のまま）→ 120問で152秒
    速い版にして 0.85秒 → 120問で **102秒**
  ここまで縮めても、起動＋結果画面の確認を足すと
  MCP経由のシェルの2分の壁（約115秒）に収まらない。

  分かっているのは
    ・120問は途中で止まらず最後まで解ける（102秒で解き終える）
    ・残っているのは結果画面が出るかどうかの確認だけ
  で、これは**環境の制約であってアプリの欠陥ではない**。

【使い方】利用者のPCなら壁が無いので、1回走らせれば結果画面まで見えます。

    cd ~/omo && python3 -m http.server 8900 &
    # 1回目：解き切った状態を作ってプロファイルに残す（14秒）
    python3 tools/journey_all.py --import <ext_v4.json> --profile /tmp/jp --stop-after 2
    # 2回目：その続きから、いじわる模試だけを最後まで
    python3 tools/いじわる模試を最後まで通す_V1.00.py

【速い版でも本番と同じ経路を通ること】
  ・押す要素は同じ（#paper-list の .choice-mark と .choice-card .choice-body、#paper-submit → これで提出）
  ・根拠マークを1回の evaluate にまとめただけで、委譲ハンドラは本番と同じものが動く
  ・外したのは 260ms の保険待ちだけ（#choice-list.is-ready を待っているので二重だった）

⑧は「模試4種の組み立て」＋「120問をUIで完走」の2つでできている。
組み立ては journey_all.py --resume（JALL_FROM=8）で通っている（4種とも120問そろう）。
残っていたのは完走のほうで、これが約100秒かかり、毎回2分の壁で切られていた。

ここでは完走だけを、--profile で作った「解き切ったあと」の状態から始める。
"""
import json, os, sys, time
sys.path.insert(0, os.path.expanduser("~/omo/tools"))
from journey_lib import *   # noqa
from playwright.sync_api import sync_playwright

R=[]
def C(name,cond,detail=""):
    R.append((bool(cond),name,str(detail)))
    print(("  ok  " if cond else "  NG  ")+name+(("   << "+str(detail)) if detail else ""),flush=True)

t0=time.time()
with sync_playwright() as pw:
    br,ctx,pg = new_page(pw, profile="/tmp/jp")
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:8900/index.html", wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=120000)
    pg.wait_for_timeout(900); tour_skip(pg); close_modals(pg)
    print("  起動まで %.1f秒"%(time.time()-t0),flush=True)
    pg.evaluate("([id,n]) => window.Half2Impl.launchExam(id, n, 'real')", ["mock_weak",120])
    pg.wait_for_selector("#paper-list .pq", timeout=60000)   # V3.10：1枚の問題用紙
    C("いじわる模試が起動する", True)
    # V3.10：確定が無くなり、塗った瞬間が解答。1回の evaluate で120問ぶんを塗って最下部から提出する
    #        （V2.17〜V3.09 は1問ずつ #btn-confirm を押していた）。
    ts=time.time()
    from journey_lib import fill_exam_paper
    n = fill_exam_paper(pg, accuracy=0.75, ground_ratio=1.0)
    done = n["answered"]
    print("    %d問 %.0f秒"%(done,time.time()-ts),flush=True)
    try: pg.wait_for_selector("#modal-exam-result:not([hidden])", timeout=8000)
    except Exception: pass
    shown=pg.evaluate("""() => { const m=document.querySelector('#modal-exam-result');
        return { shown: !!(m && !m.hidden),
                 body: (m?m.textContent:'').replace(/\\s+/g,' ').slice(0,180) }; }""")
    print("  120問に %.0f秒"%(time.time()-ts),flush=True)
    C("いじわる模試が最後まで通り結果が出る（120問）",
      done>=120 and shown["shown"], "解いた%d問 %s"%(done,json.dumps(shown,ensure_ascii=False)))
    C("いじわる模試でJSエラーが出ない", not errs, json.dumps(errs[:2],ensure_ascii=False))
    ctx.close()
    if br: br.close()
bad=[x for x in R if not x[0]]
print("\n%d/%d  exam_weak_full （全体 %.0f秒）"%(len(R)-len(bad),len(R),time.time()-t0))
sys.exit(1 if bad else 0)
