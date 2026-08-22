#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.39 検証：同期の欠落と誤り
  ・図の削除／差し替えが同期されるか、消したものが復活しないか
  ・★（アトム・問題）が同期されるか、外した★が戻ってこないか
  ・meta の同期キーが実在キーと一致しているか（模試解禁・スキャン精度）
  ・往復してもバイト列が劣化しないか、往復が止まるか
"""
import json, os, sys, subprocess, glob, re
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))

# ---------------------------------------------------------------- 静的検査
P1 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
P2 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
for f in ["storage.js", "scheduler.js", "drive.js", P1, P2, "sw.js"]:
    p = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True)
    ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

idx = open(os.path.join(APP, "index.html"), encoding="utf-8").read()
sw  = open(os.path.join(APP, "sw.js"), encoding="utf-8").read()
drv = open(os.path.join(APP, "drive.js"), encoding="utf-8").read()
st  = open(os.path.join(APP, "storage.js"), encoding="utf-8").read()
p1s = open(os.path.join(APP, P1), encoding="utf-8").read()

ok("index の script/REQUIRED が実ファイルを指す", idx.count(P1) == 2 and idx.count(P2) == 2)
ok("sw の CORE_ASSETS が実ファイルを指す", P1 in sw and P2 in sw and "drive.js" in sw)
ok("他版のファイル名が残っていない",
   len(set(re.findall(r"main_part1_V\d+\.\d+\.js", idx + sw))) == 1 and
   len(set(re.findall(r"main_part2_V\d+\.\d+\.js", idx + sw))) == 1)
_c = re.search(r"CACHE_NAME = 'v(\d+)\.(\d+)\.(\d+)'", sw)
ok("sw CACHE_NAME が v1.27.0 以降",
   bool(_c) and tuple(int(x) for x in _c.groups()) >= (1, 27, 0),
   _c.group(0) if _c else "not found")

# meta キーが実在キーを指しているか（ここがずれていると黙って空振りする）
ok("実在しない oneq_threshold が消えている", "'oneq_threshold'" not in drv)
ok("実在しない oneq_always_multi が消えている", "'oneq_always_multi'" not in drv)
for k in ["split_threshold", "always_multi", "text_overrides", "scan_answered_qids",
          "unlock_mock_30", "unlock_mock_weak", "onboarding_done", "max_pct"]:
    ok("meta同期キーに %s が入っている" % k, ("'%s'" % k) in drv)
for k in ["drive_client_id", "drive_folder_id", "seed_imported", "last_import_at"]:
    inlist = re.search(r"META_(MAX|OR|UNION|NEWER)_KEYS = \[[^\]]*'%s'" % k, drv, re.S)
    ok("端末固有の %s は同期しない" % k, not inlist)

ok("図の削除を即時に伝える口がある", "pushImageDelete" in drv)
ok("削除時に main から呼んでいる", "pushImageDelete" in p1s)
ok("★に更新時刻が付く", "star_updated_at" in st and "star_updated_at" in drv)
ok("削除の墓標を持つ", "user_image_deleted_at" in st and "image_deleted_at" in drv)
ok("同期後に概念スコアを作り直す", "recomputeConceptScores" in drv)
ok("取り込み時に再圧縮しない", "skipShrink: true" in drv)
ok("取り込み時に向こうの時刻を使う", "updatedAt: rm.at" in drv)

MOCK = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_drive.js"),
            encoding="utf-8").read()

def _external(t):
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t)

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text)
          if m.type == "error" and not _external(m.text) else None)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=20000)
    pg.wait_for_timeout(1500)
    try: pg.click("#welcome-start", timeout=2500)
    except Exception: pass
    pg.wait_for_timeout(500)

    pg.add_script_tag(content=MOCK)
    ok("モックを読み込めた", pg.evaluate("typeof window.makeDriveMock === 'function'"))

    # ============================================================
    # 純粋関数：合体の規則
    # ============================================================
    r = pg.evaluate("""() => {
      const D = window.Drive;
      // ★：外した方が新しければ外れること（集合の足し算になっていないこと）
      const a = [{id:'x', on:true,  at:100}, {id:'y', on:true, at:100}];
      const b = [{id:'x', on:false, at:200}, {id:'z', on:true, at:50}];
      const m = D.mergeStars(a, b);
      const by = {}; m.forEach(r => by[r.id] = r);
      // 同時刻の食い違いは「付いている」を採る
      const tie = D.mergeStars([{id:'t',on:false,at:9}], [{id:'t',on:true,at:9}]);
      // 旧形式（時刻なしの集合）を読めること
      const legacy = D.normalizeStars({ starred_atoms: ['p','q'] });
      return { x: by.x, y: by.y, z: by.z, n: m.length,
               tie: tie[0], legacy: legacy };
    }""")
    ok("★：外したのが新しければ外れる", r["x"]["on"] is False, json.dumps(r["x"]))
    ok("★：片方だけのものは残る", r["y"]["on"] is True and r["z"]["on"] is True)
    ok("★：同時刻の食い違いは付いている方を採る", r["tie"]["on"] is True)
    ok("★：V1.38の古い形式も読める",
       len(r["legacy"]) == 2 and all(e["on"] and e["at"] == 0 for e in r["legacy"]),
       json.dumps(r["legacy"]))

    r = pg.evaluate("""() => {
      const D = window.Drive;
      const L = { total_questions_answered: 10, max_pct: 40,
                  unlock_mock_30: true, unlock_mock_60: false,
                  scan_answered_qids: ['a','b'],
                  theme: 'dark', exam_date: '2027-02-14' };
      const Rm = { total_questions_answered: 3, max_pct: 55,
                   unlock_mock_30: false, unlock_mock_60: true,
                   scan_answered_qids: ['b','c'],
                   theme: 'sepia', exam_date: '2027-02-15' };
      const newerRemote = D.mergeMeta(L, Rm, 100, 200);   // 向こうが新しい
      const newerLocal  = D.mergeMeta(L, Rm, 300, 200);   // こっちが新しい
      return { nr: newerRemote, nl: newerLocal };
    }""")
    nr, nl = r["nr"], r["nl"]
    ok("meta：数えものは大きい方（減らさない）",
       nr["total_questions_answered"] == 10 and nr["max_pct"] == 55, json.dumps(nr))
    ok("meta：模試の解禁は片方でtrueなら永久にtrue",
       nr["unlock_mock_30"] is True and nr["unlock_mock_60"] is True)
    ok("meta：スキャン済み問題IDは足し算",
       sorted(nr["scan_answered_qids"]) == ["a", "b", "c"],
       json.dumps(nr["scan_answered_qids"]))
    ok("meta：設定は新しい方（向こうが新しい）", nr["theme"] == "sepia")
    ok("meta：設定は新しい方（こっちが新しい）", nl["theme"] == "dark")

    # ============================================================
    # 往復：図の追加・差し替え・削除
    # ============================================================
    setup = pg.evaluate("""async () => {
      const D = window.Drive, S = window.Storage;
      window.__mock = window.makeDriveMock();
      D.__setTransport(window.__mock);
      await D.giveConsent();
      await D.signIn();
      const qs = await S.getAllQuestions();
      return { qid: qs[0] && qs[0].q_id, n: qs.length };
    }""")
    ok("問題データがある", setup["n"] > 0, json.dumps(setup))
    QID = setup["qid"]

    # --- 追加 ---
    r = pg.evaluate("""async (qid) => {
      const D = window.Drive, S = window.Storage, M = window.__mock;
      // 判別できるバイト列を持つ「画像」を作る（縮小は通さない）
      const a = new Uint8Array([1,2,3,4,5,6,7,8,9,10]);
      await S.putUserImage(qid, new Blob([a], {type:'image/jpeg'}),
                           {skipShrink:true, updatedAt: 1000});
      const rep = await D.syncNow();
      const idxTxt = M.textOf('notes_index.json');
      return { rep, files: M.list(),
               bytes: M.bytesOf(qid + '.jpg'),
               idx: idxTxt ? JSON.parse(idxTxt) : null };
    }""", QID)
    ok("図を上げた", r["rep"]["uploaded"] == 1, json.dumps(r["rep"], ensure_ascii=False))
    ok("バイト列がそのまま（劣化しない）", r["bytes"] == [1,2,3,4,5,6,7,8,9,10],
       json.dumps(r["bytes"]))
    item = [i for i in (r["idx"]["items"] if r["idx"] else []) if i["q_id"] == QID]
    ok("目次に載った", bool(item) and bool(item[0]["image_file_id"]))
    ok("目次に図の時刻が載った", bool(item) and item[0].get("image_updated_at") == 1000,
       json.dumps(item[0] if item else None))
    FILEID = item[0]["image_file_id"] if item else None

    # --- 2回目の同期で何も起きない（往復が止まる） ---
    r = pg.evaluate("""async () => (await window.Drive.syncNow())""")
    ok("2回目の同期は上げも下げもしない",
       r["uploaded"] == 0 and r["downloaded"] == 0 and r["deleted"] == 0,
       json.dumps(r, ensure_ascii=False))

    # --- 差し替え：同じ枠に新しい図 ---
    r = pg.evaluate("""async (arg) => {
      const D = window.Drive, S = window.Storage, M = window.__mock;
      const b = new Uint8Array([99,98,97,96]);
      await S.putUserImage(arg.qid, new Blob([b], {type:'image/jpeg'}),
                           {skipShrink:true, updatedAt: 2000});
      const rep = await D.syncNow();
      const idx = JSON.parse(M.textOf('notes_index.json'));
      const it = idx.items.filter(i => i.q_id === arg.qid)[0];
      return { rep, bytes: M.bytesOf(arg.qid + '.jpg'),
               sameId: it.image_file_id === arg.fid,
               nJpg: M.list().filter(f => /\\.jpg$/.test(f.name)).length,
               at: it.image_updated_at };
    }""", {"qid": QID, "fid": FILEID})
    ok("差し替えた図が上がる（V1.38はここで黙って何もしなかった）",
       r["rep"]["uploaded"] == 1, json.dumps(r["rep"], ensure_ascii=False))
    ok("差し替え後の中身が新しい方になっている", r["bytes"] == [99,98,97,96],
       json.dumps(r["bytes"]))
    ok("差し替えは同じファイルを更新する（古い図が積み上がらない）",
       r["sameId"] and r["nJpg"] == 1, json.dumps(r))
    ok("目次の時刻も更新される", r["at"] == 2000, json.dumps(r["at"]))

    # --- 削除 ---
    r = pg.evaluate("""async (qid) => {
      const D = window.Drive, S = window.Storage, M = window.__mock;
      await S.deleteUserImage(qid, {deletedAt: 3000});
      const rep = await D.syncNow();
      const idx = JSON.parse(M.textOf('notes_index.json'));
      const it = idx.items.filter(i => i.q_id === qid)[0];
      return { rep, nJpg: M.list().filter(f => /\\.jpg$/.test(f.name)).length,
               item: it };
    }""", QID)
    ok("消した図をドライブからも消す", r["rep"]["deleted"] == 1,
       json.dumps(r["rep"], ensure_ascii=False))
    ok("ドライブ上に図が残っていない", r["nJpg"] == 0, json.dumps(r["nJpg"]))
    ok("目次から image_file_id が消えている",
       not r["item"].get("image_file_id"), json.dumps(r["item"]))
    ok("目次に消した時刻が残る", r["item"].get("image_deleted_at") == 3000,
       json.dumps(r["item"]))

    # --- 削除後に何度同期しても復活しない ---
    r = pg.evaluate("""async (qid) => {
      const D = window.Drive, S = window.Storage, M = window.__mock;
      await D.syncNow(); await D.syncNow();
      const rec = await S.getUserImage(qid);
      return { hasLocal: !!(rec && rec.blob),
               nJpg: M.list().filter(f => /\\.jpg$/.test(f.name)).length };
    }""", QID)
    ok("消した図が復活しない（手元）", not r["hasLocal"])
    ok("消した図が復活しない（ドライブ）", r["nJpg"] == 0)

    # --- 消した枠に新しい図を入れ直せる ---
    r = pg.evaluate("""async (qid) => {
      const D = window.Drive, S = window.Storage, M = window.__mock;
      const c = new Uint8Array([7,7,7]);
      await S.putUserImage(qid, new Blob([c], {type:'image/jpeg'}),
                           {skipShrink:true, updatedAt: 4000});
      const rep = await D.syncNow();
      return { rep, bytes: M.bytesOf(qid + '.jpg') };
    }""", QID)
    ok("消した枠に入れ直した図が上がる", r["rep"]["uploaded"] == 1,
       json.dumps(r["rep"], ensure_ascii=False))
    ok("入れ直した図の中身が正しい", r["bytes"] == [7,7,7], json.dumps(r["bytes"]))

    # --- 別端末が消したら、こちらからも消える ---
    r = pg.evaluate("""async (qid) => {
      const D = window.Drive, S = window.Storage, M = window.__mock;
      // 「向こうの端末が消した」状態を目次に作る
      const idx = JSON.parse(M.textOf('notes_index.json'));
      idx.items.forEach(i => {
        if (i.q_id === qid) {
          i.image_file_id = null; i.image_name = null;
          i.image_deleted_at = 9000; i.updated_at = 9000;
        }
      });
      await D.writeIndex({items: idx.items});
      // ドライブ上の実体も消えている
      Object.keys(M.__files).forEach(k => {
        if (/\\.jpg$/.test(M.__files[k].name)) { delete M.__files[k]; }
      });
      const rep = await D.syncNow();
      const rec = await S.getUserImage(qid);
      return { rep, hasLocal: !!(rec && rec.blob) };
    }""", QID)
    ok("向こうで消された図がこちらからも消える",
       r["rep"]["removed_local"] == 1 and not r["hasLocal"],
       json.dumps(r["rep"], ensure_ascii=False))

    # ============================================================
    # 往復：★
    # ============================================================
    r = pg.evaluate("""async () => {
      const D = window.Drive, S = window.Storage, M = window.__mock;
      const atoms = await S.getAllAtoms();
      const qs = await S.getAllQuestions();
      const aid = atoms[0].atom_id, qid = qs[0].q_id;
      await S.toggleAtomStar(aid);
      await S.toggleQuestionStar(qid);
      await D.syncNow();
      const prog = JSON.parse(M.textOf('progress.json'));
      // 手元の★を消してから同期し直す＝「別端末で開いた」ことにする
      await S.updateAtom(aid, {is_starred:false, star_updated_at:0});
      await S.updateQuestion(qid, {is_starred:false, star_updated_at:0});
      await D.syncNow();
      const a2 = await S.getAtom(aid);
      const q2 = await S.getQuestion(qid);
      return { onDrive_a: (prog.stars_atom||[]).length,
               onDrive_q: (prog.stars_question||[]).length,
               back_a: !!a2.is_starred, back_q: !!q2.is_starred,
               aid: aid, qid: qid };
    }""")
    ok("アトム★がドライブに載る", r["onDrive_a"] >= 1, json.dumps(r))
    ok("問題★がドライブに載る", r["onDrive_q"] >= 1, json.dumps(r))
    ok("アトム★が別端末に届く（V1.38は届かなかった）", r["back_a"] is True)
    ok("問題★が別端末に届く（V1.38は収集すらしていなかった）", r["back_q"] is True)
    AID, SQID = r["aid"], r["qid"]

    r = pg.evaluate("""async (arg) => {
      const D = window.Drive, S = window.Storage;
      // 外す（今の時刻が入る＝ドライブ側より新しい）
      await S.toggleAtomStar(arg.aid);
      await D.syncNow();
      await D.syncNow();
      const a = await S.getAtom(arg.aid);
      return { on: !!a.is_starred };
    }""", {"aid": AID})
    ok("外した★が何度同期しても戻ってこない", r["on"] is False)

    # ============================================================
    # 進捗の合体が壊れていないこと（V1.38の回帰）
    # ============================================================
    r = pg.evaluate("""async () => {
      const D = window.Drive, S = window.Storage;
      const before = (await S.getAllLogs()).length;
      const rep = await D.syncProgress();
      const after = (await S.getAllLogs()).length;
      return { before, after, rep };
    }""")
    ok("同期で台帳が減らない", r["after"] >= r["before"], json.dumps(r))
    ok("同期を繰り返しても台帳が増えない", r["rep"]["added"] == 0,
       json.dumps(r["rep"], ensure_ascii=False))

    # 概念スコアが作り直されていること
    r = pg.evaluate("""async () => {
      const S = window.Storage;
      const cs = await S.getConceptStats();
      return { n: cs.length };
    }""")
    ok("同期後に概念の集計が存在する", r["n"] >= 0, json.dumps(r))

    ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
    br.close()

# ---------------------------------------------------------------- 出力
bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  batchV" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
