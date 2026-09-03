#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V2.10 検証：Android で「復習の数字」も「ポモドーロの通知」も出ていなかった

何が起きていたか（実機 ColorOS・WebAPK で確認）：
 1. Android Chrome には App Badging API（setAppBadge）が無い。アプリは無ければ何もしない
    作りだったので、アイコンに数字が一度も出なかった（Android では数字は仕組み上出せない。
    出るのは「未読通知がある」ときの点だけ）
 2. ページからの new Notification() は Android で常に失敗（Illegal constructor）。
    try/catch で握りつぶしていたので、ポモドーロ・ノック終了の通知も出ていなかった
 3. 通知バッジをOFFにしても、ONのときに出した数字がアイコンに残っていた（消す経路が
    早期returnの後ろにあった）

固定すること：
 - 通知は SW の showNotification 経由で出る（swNotify）
 - Badging API が無い端末では、離れるときに「今日の分」を無音・tag置換で1件置き、
   戻ってきたら消す
 - OFF なら clearAppBadge が呼ばれる
 - 設定画面に「この端末は数字を出せない」の注記が出る（Badging API が無いときだけ）
 - sw.js に notificationclick（タップでアプリへ戻る）がある
ブラウザ側の条件（setAppBadge 無し・通知許可あり・SW の通知API）はモックで再現する。
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    import io
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


p1 = read(sorted([f for f in os.listdir(APP) if "main_part1_V" in f])[-1])
p2 = read(sorted([f for f in os.listdir(APP) if "main_part2_V" in f])[-1])
sw = read("sw.js")
ok("sw.js に notificationclick（タップでアプリへ戻る）がある", "notificationclick" in sw and "openWindow" in sw)
ok("ポモドーロの notify() はページの new Notification() を直接呼ばない",
   "M.swNotify(title" in p2 and "new global.Notification(title, { body: body, tag: 'nurse-srs-timer' })" not in p2)
ok("離れるときの通知（omoidasu-due）が visibilitychange と pagehide の両方に掛かる",
   p1.count("dueNotifyOnHide();") >= 2)

with sync_playwright() as pw:
    br = pw.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(APP_URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(1500)
    try:
        pg.click("#welcome-start", timeout=3000)
    except Exception:
        pass
    pg.wait_for_function("navigator.serviceWorker && navigator.serviceWorker.controller !== undefined", timeout=30000)

    # ---- 3. OFF なら消す（Badging API がある端末の話。先にこちらを検査） ----
    r = pg.evaluate("""async () => {
      const calls = { set: [], clear: 0 };
      Object.defineProperty(navigator, 'setAppBadge',   { value: n => { calls.set.push(n); return Promise.resolve(); }, configurable: true });
      Object.defineProperty(navigator, 'clearAppBadge', { value: () => { calls.clear++; return Promise.resolve(); }, configurable: true });
      const M = window.Main;
      M.state.meta = Object.assign({}, M.state.meta || {}, { badge_enabled: false });
      M.updateAppBadge(7);
      const off = { set: calls.set.slice(), clear: calls.clear };
      M.state.meta = Object.assign({}, M.state.meta, { badge_enabled: true });
      M.updateAppBadge(7);
      return { off: off, on: { set: calls.set.slice(), clear: calls.clear } };
    }""")
    ok("OFFのときは setAppBadge を呼ばず clearAppBadge で消す（数字が残らない）",
       r["off"]["set"] == [] and r["off"]["clear"] == 1, json.dumps(r))
    ok("ONのときは今までどおり数字を渡す", r["on"]["set"] == [7], json.dumps(r["on"]))

    # ---- Android の条件を再現：setAppBadge 無し・通知許可あり・SW の通知APIをモック ----
    setup = pg.evaluate("""async () => {
      Object.defineProperty(navigator, 'setAppBadge',   { value: undefined, configurable: true });
      Object.defineProperty(navigator, 'clearAppBadge', { value: undefined, configurable: true });
      Object.defineProperty(window.Notification, 'permission', { get: () => 'granted', configurable: true });
      const reg = await navigator.serviceWorker.getRegistration();
      if (!reg) { return { reg: false }; }
      window.__cap = { shown: [], closed: 0 };
      reg.showNotification = (t, o) => { window.__cap.shown.push({ t: t, o: o }); return Promise.resolve(); };
      reg.getNotifications = () => Promise.resolve([{ close: () => { window.__cap.closed++; } }]);
      const reg2 = await navigator.serviceWorker.getRegistration();
      return { reg: true, same: reg2 === reg, supported: window.Main.badgingSupported() };
    }""")
    ok("SW の登録が同一オブジェクトとして取り直せる（モックが効く前提）", setup.get("reg") and setup.get("same"), json.dumps(setup))
    ok("setAppBadge が無い端末と判定される", setup.get("supported") is False, json.dumps(setup))

    r = pg.evaluate("""async () => {
      const M = window.Main;
      await M.swNotify('検査', { body: 'b', tag: 'x' });
      const s1 = window.__cap.shown.slice();
      M.state.dueToday = 5; M.state.dueQuestions = 12;
      M.state.meta = Object.assign({}, M.state.meta || {}, { badge_enabled: true });
      await M.dueNotifyOnHide();
      const s2 = window.__cap.shown.slice();
      M.state.meta = Object.assign({}, M.state.meta, { badge_enabled: false });
      await M.dueNotifyOnHide();
      const s3 = window.__cap.shown.slice();
      await M.dueNotifyClear();
      return { s1: s1, s2: s2, s3: s3, closed: window.__cap.closed };
    }""")
    ok("通知は SW の showNotification 経由で出る（アイコン付き）",
       len(r["s1"]) == 1 and r["s1"][0]["t"] == "検査" and r["s1"][0]["o"].get("icon"), json.dumps(r["s1"], ensure_ascii=False))
    due = [x for x in r["s2"] if x["o"].get("tag") == "omoidasu-due"]
    ok("離れるとき「今日の分 5問（期日 12問）」を無音・tag置換で1件置く",
       len(due) == 1 and due[0]["o"].get("silent") is True and "5問" in due[0]["o"]["body"] and "12問" in due[0]["o"]["body"],
       json.dumps(r["s2"], ensure_ascii=False))
    ok("バッジ設定がOFFなら置かない", len(r["s3"]) == len(r["s2"]), json.dumps({"s2": len(r["s2"]), "s3": len(r["s3"])}))
    ok("戻ってきたら消す（getNotifications → close）", r["closed"] >= 1, r["closed"])

    # ---- 動線：visibilitychange(hidden) で本当に置かれるか ----
    r = pg.evaluate("""async () => {
      const M = window.Main;
      M.state.meta = Object.assign({}, M.state.meta || {}, { badge_enabled: true });
      M.state.dueToday = 3; M.state.dueQuestions = 3;
      const before = window.__cap.shown.length;
      Object.defineProperty(document, 'visibilityState', { get: () => 'hidden', configurable: true });
      document.dispatchEvent(new Event('visibilitychange'));
      await new Promise(r => setTimeout(r, 600));
      Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true });
      const added = window.__cap.shown.slice(before).filter(x => x.o && x.o.tag === 'omoidasu-due');
      return { added: added.length, body: added.length ? added[0].o.body : null };
    }""")
    ok("画面が隠れた瞬間に「復習が待っています」が置かれる（実動線）", r["added"] == 1 and "3問" in (r["body"] or ""), json.dumps(r, ensure_ascii=False))

    # ---- 設定画面の注記 ----
    pg.evaluate("() => { const M = window.Main; if (M.closeModals) { M.closeModals(); } }")
    pg.wait_for_timeout(300)
    pg.click("#btn-settings")
    pg.wait_for_timeout(800)
    note = pg.evaluate("() => { const n = document.getElementById('set-badge-note'); return n ? { hidden: n.hidden, text: n.textContent.slice(0, 24) } : null; }")
    ok("Badging API が無い端末では、設定に「数字を出せない」注記が出る",
       note and note["hidden"] is False and "数字" in note["text"], json.dumps(note, ensure_ascii=False))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + str(detail)) if (detail and not good_) else ""))
print("\n%d/%d  batchCH" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
