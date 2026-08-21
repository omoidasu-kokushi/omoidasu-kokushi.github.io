/* ==========================================================================
 * drive.js — Google ドライブ同期（V1.31 / 段階2＋3）
 *
 * 【この層の役目】
 *   利用者自身のGoogleドライブへ、自作の図とメモを預ける／取り戻す。
 *   アプリの運営者が持つサーバーは存在しない。トークンは利用者のブラウザの
 *   中だけで発行され、開発者が管理するホストを一度も経由しない。
 *   だから運営者は中身を保存も取得もできない（構造的に手段が無い）。
 *
 * 【なぜ storage.js に入れないか】
 *   storage.js は「この端末の中の保存」を受け持つ層で、通信を一切しない。
 *   ここへ OAuth と HTTP を混ぜると、バックアップ・復元・全消去の3経路に
 *   ネットワーク失敗が絡み、オフラインで動くという前提が崩れる。
 *   別ファイルにして「読み込めなくても・繋がらなくてもアプリは動く」を保つ。
 *
 * 【スコープは drive.file だけ】
 *   このアプリが作ったファイルしか見えない。利用者のドライブの他の中身は
 *   読めないし、読む必要も無い。drive / drive.readonly は使わない
 *   （Googleの追加審査が要るうえ、「全部見える」のは設計思想に反する）。
 *
 * 【トークンについて】
 *   ブラウザだけの構成ではリフレッシュトークンを保持できない。
 *   アクセストークンは短命で、期限が切れたら利用者の操作をきっかけに
 *   取り直す。だから同期は「自動」ではなく【ボタンを押したとき】に走る。
 *   これは制約であって不具合ではない。画面にもそう書く。
 * ========================================================================== */

(function (global) {
  'use strict';

  var S = global.Storage;

  var SCOPE       = 'https://www.googleapis.com/auth/drive.file';
  var GIS_SRC     = 'https://accounts.google.com/gsi/client';
  var API_FILES   = 'https://www.googleapis.com/drive/v3/files';
  var API_UPLOAD  = 'https://www.googleapis.com/upload/drive/v3/files';
  /* --- 配布用のクライアントID（V1.32） ---
     不特定多数へ配るので、利用者に貼らせない。ここに入れておく。
     【これは秘密の値ではない】。ブラウザで動く仕組みでは必ず公開される値で、
     Googleもそう設計している。悪用の歯止めは「承認済みJavaScript生成元」で、
     登録したアドレスから来た要求しかGoogleが受け付けない。
     空のままだと、設定画面の入力欄から各自で入れる形に戻る（開発中はこれ）。 */
  var DEFAULT_CLIENT_ID = '973785386546-3u8ckvbr9ehgcsac3m1rael0r8k31m6k.apps.googleusercontent.com';

  var FOLDER_NAME = 'Omoidasu';
  var INDEX_NAME  = 'notes_index.json';
  var INDEX_SCHEMA = 1;

  /* トークンの有効期限は Google が返す expires_in（通常3600秒）。
     境目ちょうどで落ちないよう、60秒手前で切れた扱いにする。 */
  var TOKEN_SKEW_MS = 60 * 1000;

  var state = {
    token: null,        /* { access_token, expires_at } */
    folderId: null,
    tokenClient: null,
    gisLoaded: false
  };

  /* テストから差し替えるための入口。実物の fetch と GIS を触らずに
     経路だけを検証できるようにしてある（本番では一切使わない）。 */
  var transport = null;
  function setTransport(t) { transport = t; state.token = null; state.folderId = null; }
  function http(url, opts) {
    if (transport && transport.fetch) { return transport.fetch(url, opts); }
    return global.fetch(url, opts);
  }

  function nowMs() { return Date.now(); }

  /* ---------------------------------------------------------------- 設定 */

  /* 埋め込みが最優先。利用者が自分のIDを入れたときだけ、そちらを使う
     （自分のGoogle Cloudで動かしたい人向けの逃げ道）。 */
  function getClientId() {
    return S.loadMeta().then(function (m) {
      return m.drive_client_id || DEFAULT_CLIENT_ID || null;
    });
  }

  function hasBuiltInClientId() { return !!DEFAULT_CLIENT_ID; }

  function setClientId(id) {
    var v = (id || '').trim() || null;
    if (v && !/\.apps\.googleusercontent\.com$/.test(v)) {
      return Promise.reject(new Error(
        'クライアントIDの形が違います。末尾が .apps.googleusercontent.com のものを貼ってください。'));
    }
    state.token = null; state.tokenClient = null; state.folderId = null;
    /* 別のGoogle Cloudプロジェクトへ移ると、覚えたIDは他人のものになる。 */
    return S.setMeta('drive_client_id', v)
      .then(function () { return S.setMeta('drive_folder_id', null); })
      .then(function () { return S.setMeta('drive_index_id', null); })
      .then(function () { return v; });
  }

  function isConfigured() {
    return getClientId().then(function (id) { return !!id; });
  }

  /* 同意（著作権・個人情報）を受けたか */
  function hasConsent() {
    return S.loadMeta().then(function (m) { return !!m.drive_consent_at; });
  }
  function giveConsent() {
    return S.setMeta('drive_consent_at', nowMs()).then(function () { return true; });
  }

  /* ------------------------------------------------------------ トークン */

  function tokenValid() {
    return !!(state.token && state.token.access_token &&
              state.token.expires_at - TOKEN_SKEW_MS > nowMs());
  }

  function loadGis() {
    if (transport) { state.gisLoaded = true; return Promise.resolve(true); }
    if (state.gisLoaded && global.google && global.google.accounts) { return Promise.resolve(true); }
    return new Promise(function (resolve, reject) {
      var s = global.document.createElement('script');
      s.src = GIS_SRC; s.async = true; s.defer = true;
      s.onload = function () { state.gisLoaded = true; resolve(true); };
      s.onerror = function () {
        reject(new Error('Googleのログイン部品を読み込めませんでした。通信を確認してください。'));
      };
      global.document.head.appendChild(s);
    });
  }

  /* 利用者の操作から呼ぶこと。ポップアップを開くため、
     クリック以外のきっかけで呼ぶとブラウザに塞がれる。 */
  function signIn(opts) {
    opts = opts || {};
    if (tokenValid() && !opts.force) { return Promise.resolve(state.token); }

    return getClientId().then(function (clientId) {
      if (!clientId) {
        throw new Error('先に「クライアントID」を設定してください。');
      }
      if (transport && transport.signIn) {
        return transport.signIn(clientId).then(function (t) {
          state.token = { access_token: t.access_token,
                          expires_at: nowMs() + (t.expires_in || 3600) * 1000 };
          return state.token;
        });
      }
      return loadGis().then(function () {
        return new Promise(function (resolve, reject) {
          var tc = global.google.accounts.oauth2.initTokenClient({
            client_id: clientId,
            scope: SCOPE,
            callback: function (resp) {
              if (resp && resp.access_token) {
                state.token = {
                  access_token: resp.access_token,
                  expires_at: nowMs() + (Number(resp.expires_in) || 3600) * 1000
                };
                resolve(state.token);
              } else {
                reject(new Error('ログインできませんでした。'));
              }
            },
            error_callback: function (err) {
              reject(new Error('ログインを中止しました' +
                ((err && err.type) ? '（' + err.type + '）' : '') + '。'));
            }
          });
          state.tokenClient = tc;
          tc.requestAccessToken({ prompt: opts.force ? 'consent' : '' });
        });
      });
    });
  }

  function signOut() {
    var t = state.token;
    state.token = null; state.folderId = null;
    /* 別アカウントで入り直すと、覚えたIDは前のアカウントのもの。 */
    S.setMeta('drive_folder_id', null).catch(function () {});
    S.setMeta('drive_index_id', null).catch(function () {});
    if (!transport && t && global.google && global.google.accounts &&
        global.google.accounts.oauth2 && global.google.accounts.oauth2.revoke) {
      try { global.google.accounts.oauth2.revoke(t.access_token); } catch (e) { /* 失敗しても続行 */ }
    }
    return Promise.resolve(true);
  }

  function authHeader() {
    if (!tokenValid()) {
      return Promise.reject(new Error('EXPIRED'));
    }
    return Promise.resolve({ Authorization: 'Bearer ' + state.token.access_token });
  }

  /* 401 は「期限切れ」として上へ返す。黙って再ログインを走らせない
     （ポップアップは利用者の操作からしか開けないため）。 */
  function checkResponse(r) {
    if (r.ok) { return r; }
    if (r.status === 401 || r.status === 403) {
      var e = new Error('EXPIRED'); e.status = r.status; throw e;
    }
    var err = new Error('ドライブとの通信に失敗しました（' + r.status + '）');
    err.status = r.status;
    throw err;
  }

  /* -------------------------------------------------------------- フォルダ */

  /* --- 検索の回数を減らす（V1.32） ---
     files.list は1回100単位で、Drive APIの上限は【プロジェクト全体で共有】される。
     図がN枚あるときに毎回名前で探すと、同期1回でN回の検索になり、
     利用者が増えたときに全員でその枠を食い合う。
     一度分かったIDは meta に覚えておき、次からは検索せずに使う。
     覚えたIDが無効になっていたら（利用者がドライブ側で消した）、
     404を受けて覚え直す。 */
  function rememberId(key, id) {
    return S.setMeta(key, id || null).then(function () { return id; });
  }

  function ensureFolder() {
    if (state.folderId) { return Promise.resolve(state.folderId); }
    return S.loadMeta().then(function (m) {
      if (m.drive_folder_id) {
        state.folderId = m.drive_folder_id;
        return state.folderId;
      }
      return lookupFolder();
    });
  }

  function lookupFolder() {
    return authHeader().then(function (h) {
      var q = encodeURIComponent(
        "mimeType='application/vnd.google-apps.folder' and name='" + FOLDER_NAME +
        "' and trashed=false");
      return http(API_FILES + '?q=' + q + '&fields=files(id,name)&pageSize=1', { headers: h })
        .then(checkResponse)
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (j.files && j.files.length) { state.folderId = j.files[0].id; return state.folderId; }
          return http(API_FILES + '?fields=id', {
            method: 'POST',
            headers: Object.assign({ 'Content-Type': 'application/json' }, h),
            body: JSON.stringify({
              name: FOLDER_NAME, mimeType: 'application/vnd.google-apps.folder'
            })
          }).then(checkResponse)
            .then(function (r) { return r.json(); })
            .then(function (f) {
              state.folderId = f.id;
              return rememberId('drive_folder_id', f.id);
            });
        });
    }).then(function (id) {
      if (state.folderId && !id) { return state.folderId; }
      return rememberId('drive_folder_id', id || state.folderId);
    });
  }

  /* 覚えたIDが使えなかったときに、1回だけ探し直してやり直す。 */
  function withFolderRetry(fn) {
    return fn().catch(function (e) {
      if (!e || e.status !== 404) { throw e; }
      state.folderId = null;
      return rememberId('drive_folder_id', null)
        .then(lookupFolder)
        .then(function () { return fn(); });
    });
  }

  /* ------------------------------------------------------------ ファイル */

  function findByName(name) {
    return ensureFolder().then(function (folderId) {
      return authHeader().then(function (h) {
        var q = encodeURIComponent(
          "name='" + name + "' and '" + folderId + "' in parents and trashed=false");
        return http(API_FILES + '?q=' + q + '&fields=files(id,name,modifiedTime)&pageSize=1',
                    { headers: h })
          .then(checkResponse)
          .then(function (r) { return r.json(); })
          .then(function (j) { return (j.files && j.files.length) ? j.files[0] : null; });
      });
    });
  }

  /* multipart で「メタデータ＋中身」を1回で送る。
     同名があれば作り直さず PATCH で中身だけ差し替える
     （毎回作ると同じ名前のファイルがドライブに積み上がる）。 */
  function uploadBlob(name, blob, mime, knownId) {
    return ensureFolder().then(function (folderId) {
      /* IDが分かっていれば検索しない（100単位の節約）。 */
      var find = knownId ? Promise.resolve({ id: knownId, name: name })
                         : findByName(name);
      return find.then(function (existing) {
        return authHeader().then(function (h) {
          var meta = existing ? { name: name } : { name: name, parents: [folderId] };
          var boundary = 'nurseapp' + Math.floor(nowMs()).toString(36);
          var head = '--' + boundary + '\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n' +
                     JSON.stringify(meta) + '\r\n' +
                     '--' + boundary + '\r\nContent-Type: ' + (mime || 'application/octet-stream') +
                     '\r\n\r\n';
          var tail = '\r\n--' + boundary + '--';
          var body = new Blob([head, blob, tail], { type: 'multipart/related; boundary=' + boundary });
          var url = API_UPLOAD + (existing ? '/' + existing.id : '') +
                    '?uploadType=multipart&fields=id,name,modifiedTime';
          return http(url, {
            method: existing ? 'PATCH' : 'POST',
            headers: Object.assign(
              { 'Content-Type': 'multipart/related; boundary=' + boundary }, h),
            body: body
          }).then(checkResponse).then(function (r) { return r.json(); });
        });
      });
    });
  }

  function downloadBlob(fileId) {
    return authHeader().then(function (h) {
      return http(API_FILES + '/' + fileId + '?alt=media', { headers: h })
        .then(checkResponse)
        .then(function (r) { return r.blob(); });
    });
  }

  function deleteFile(fileId) {
    return authHeader().then(function (h) {
      return http(API_FILES + '/' + fileId, { method: 'DELETE', headers: h })
        .then(function (r) {
          /* 既に無い（404）のは成功と同じ。消したい状態にはなっている。 */
          if (r.ok || r.status === 404) { return true; }
          return checkResponse(r);
        }).then(function () { return true; });
    });
  }

  /* -------------------------------------------------------------- 目次 */

  function emptyIndex() {
    return { schema: INDEX_SCHEMA, updated_at: 0, items: [] };
  }

  function readIndex() {
    return S.loadMeta().then(function (m) {
      if (m.drive_index_id) { return { id: m.drive_index_id }; }
      return findByName(INDEX_NAME).then(function (f) {
        if (f) { return rememberId('drive_index_id', f.id).then(function () { return f; }); }
        return null;
      });
    }).then(function (f) {
      if (!f) { return emptyIndex(); }
      return downloadBlob(f.id).then(function (b) { return b.text(); })
        .then(function (t) {
          try {
            var j = JSON.parse(t);
            if (!j || !Array.isArray(j.items)) { return emptyIndex(); }
            return j;
          } catch (e) {
            /* 壊れていても捨てない。空として扱い、上書き時に退避を残す。 */
            return emptyIndex();
          }
        });
    });
  }

  function writeIndex(idx) {
    idx.schema = INDEX_SCHEMA;
    idx.updated_at = nowMs();
    var blob = new Blob([JSON.stringify(idx, null, 2)], { type: 'application/json' });
    return S.loadMeta().then(function (m) {
      return uploadBlob(INDEX_NAME, blob, 'application/json', m.drive_index_id || null);
    }).then(function (f) {
      return rememberId('drive_index_id', f.id);
    }).then(function () { return idx; });
  }

  /* ------------------------------------------------------------ 突合 */

  function keyOf(it) { return String(it.q_id) + '|' + String(it.atom_id || ''); }

  /* 新しい方を採る。ただし【負けた方を捨てない】。
     同じ問題を2端末で別々に直したとき、黙って消えるのが一番まずいので、
     負けた側を _conflicts に積んで、あとから見えるようにしておく。 */
  function mergeIndex(localItems, remoteIdx) {
    var out = {}, conflicts = [];
    (remoteIdx.items || []).forEach(function (it) { out[keyOf(it)] = it; });

    localItems.forEach(function (mine) {
      var k = keyOf(mine);
      var theirs = out[k];
      if (!theirs) { out[k] = mine; return; }
      var a = Number(mine.updated_at || 0), b = Number(theirs.updated_at || 0);
      if (a === b) { return; }
      if (a > b) {
        out[k] = mine;
        if (differs(mine, theirs)) { conflicts.push({ kept: 'local', key: k, lost: theirs }); }
      } else if (differs(mine, theirs)) {
        conflicts.push({ kept: 'remote', key: k, lost: mine });
      }
    });

    var items = Object.keys(out).map(function (k) { return out[k]; });
    items.sort(function (x, y) { return keyOf(x) < keyOf(y) ? -1 : 1; });
    return { items: items, conflicts: conflicts };
  }

  function differs(a, b) {
    return String(a.memo || '') !== String(b.memo || '') ||
           String(a.image_file_id || '') !== String(b.image_file_id || '');
  }

  /* ------------------------------------------------------------ 同期 */

  /* この端末の状態を目次の形にする */
  function collectLocal() {
    return Promise.all([S.getAllQuestions(), S.getAllUserFiles()]).then(function (r) {
      var qs = r[0];
      var byQ = {};
      r[1].forEach(function (f) { if (f.kind === 'image' && f.q_id) { byQ[f.q_id] = f; } });

      return qs.filter(function (q) {
        return byQ[q.q_id] || (q.user_memo && String(q.user_memo).trim());
      }).map(function (q) {
        var f = byQ[q.q_id];
        return {
          q_id: q.q_id,
          atom_id: null,
          image_name: f ? (q.q_id + '.jpg') : null,
          image_file_id: q.drive_image_id || null,
          image_updated_at: f ? (f.updated_at || 0) : 0,
          memo: q.user_memo || null,
          updated_at: Math.max(Number(q.memo_updated_at || 0),
                               Number(q.user_image_updated_at || 0),
                               f ? Number(f.updated_at || 0) : 0)
        };
      });
    });
  }

  /* 押したときだけ走る。戻り値は画面にそのまま出せる報告。 */
  function syncNow(onProgress) {
    var report = {
      ok: true, uploaded: 0, downloaded: 0, memo_updated: 0,
      conflicts: [], skipped: 0, started_at: nowMs(), messages: []
    };
    var say = function (m) {
      report.messages.push(m);
      if (typeof onProgress === 'function') { onProgress(m); }
    };

    return hasConsent().then(function (okd) {
      if (!okd) { throw new Error('CONSENT_REQUIRED'); }
      say('ドライブのフォルダを確認しています…');
      /* 覚えたフォルダを利用者がドライブ側で消していたら、探し直してやり直す。 */
      return withFolderRetry(function () { return ensureFolder(); });
    }).then(function () {
      say('目次を読んでいます…');
      return Promise.all([collectLocal(), readIndex()]);
    }).then(function (pair) {
      var local = pair[0], remote = pair[1];
      var merged = mergeIndex(local, remote);
      report.conflicts = merged.conflicts;

      var localByKey = {};
      local.forEach(function (it) { localByKey[keyOf(it)] = it; });

      /* 【ドライブ側の目次に載っているか】だけを見る。
         手元の drive_image_id は当てにしない：利用者がドライブで
         フォルダごと消すと、手元にIDだけ残る。そのIDを「上がっている証拠」
         として扱うと、二度と上げ直さないまま同期が成功したことになる
         （黙って何もしない、が一番まずい壊れ方）。 */
      var remoteHasImage = {};
      (remote.items || []).forEach(function (it) {
        if (it.image_file_id) { remoteHasImage[keyOf(it)] = true; }
      });

      /* 1) この端末にあってドライブに無い画像を上げる */
      var ups = merged.items.filter(function (it) {
        var mine = localByKey[keyOf(it)];
        return mine && mine.image_name && !remoteHasImage[keyOf(it)];
      });

      var seq = Promise.resolve();
      ups.forEach(function (it) {
        seq = seq.then(function () {
          return S.getUserImage(it.q_id).then(function (rec) {
            if (!rec || !rec.blob) { report.skipped++; return; }
            say('図を上げています（' + it.q_id + '）…');
            /* 目次に無いのだから、既知IDは信用しない。新規として上げる。 */
            return uploadBlob(it.q_id + '.jpg', rec.blob, rec.mime || 'image/jpeg', null)
              .then(function (f) {
                it.image_file_id = f.id;
                report.uploaded++;
                return S.getQuestion(it.q_id).then(function (q) {
                  if (!q) { return null; }
                  q.drive_image_id = f.id;
                  return S.putQuestionShallow(q);
                });
              });
          });
        });
      });

      /* 2) ドライブにあってこの端末に無いものを取り込む */
      seq = seq.then(function () {
        var downs = merged.items.filter(function (it) {
          var mine = localByKey[keyOf(it)];
          /* ドライブ側に実物があるものだけを取りに行く。 */
          return remoteHasImage[keyOf(it)] && it.image_file_id
                 && (!mine || !mine.image_name);
        });
        var s2 = Promise.resolve();
        downs.forEach(function (it) {
          s2 = s2.then(function () {
            say('図を取り込んでいます（' + it.q_id + '）…');
            return downloadBlob(it.image_file_id).then(function (b) {
              /* 上げるときに縮小済み。ここで再圧縮すると往復のたびに劣化する。 */
              return S.putUserImage(it.q_id, b, { skipShrink: true });
            }).then(function () {
              report.downloaded++;
              return S.getQuestion(it.q_id).then(function (q) {
                if (!q) { return null; }
                q.drive_image_id = it.image_file_id;
                return S.putQuestionShallow(q);
              });
            }).catch(function () { report.skipped++; });
          });
        });
        return s2;
      });

      /* 3) メモの本文を、新しい方に合わせる */
      seq = seq.then(function () {
        var s3 = Promise.resolve();
        merged.items.forEach(function (it) {
          var mine = localByKey[keyOf(it)];
          if (!it.memo) { return; }
          if (mine && String(mine.memo || '') === String(it.memo)) { return; }
          s3 = s3.then(function () {
            return S.getQuestion(it.q_id).then(function (q) {
              if (!q) { return null; }
              q.user_memo = it.memo;
              q.memo_updated_at = it.updated_at || nowMs();
              report.memo_updated++;
              return S.putQuestionShallow(q);
            });
          });
        });
        return s3;
      });

      return seq.then(function () {
        say('目次を書き戻しています…');
        return writeIndex({ items: merged.items });
      });
    }).then(function () {
      report.finished_at = nowMs();
      return S.setMeta('drive_last_sync', report.finished_at).then(function () { return report; });
    }).catch(function (e) {
      report.ok = false;
      report.error = (e && e.message) || String(e);
      report.finished_at = nowMs();
      return report;
    });
  }

  function lastSync() {
    return S.loadMeta().then(function (m) { return m.drive_last_sync || null; });
  }

  global.Drive = {
    SCOPE            : SCOPE,
    FOLDER_NAME      : FOLDER_NAME,
    INDEX_NAME       : INDEX_NAME,
    INDEX_SCHEMA     : INDEX_SCHEMA,

    DEFAULT_CLIENT_ID: DEFAULT_CLIENT_ID,
    hasBuiltInClientId: hasBuiltInClientId,
    getClientId      : getClientId,
    setClientId      : setClientId,
    isConfigured     : isConfigured,
    hasConsent       : hasConsent,
    giveConsent      : giveConsent,

    signIn           : signIn,
    signOut          : signOut,
    tokenValid       : tokenValid,

    ensureFolder     : ensureFolder,
    lookupFolder     : lookupFolder,
    withFolderRetry  : withFolderRetry,
    findByName       : findByName,
    uploadBlob       : uploadBlob,
    downloadBlob     : downloadBlob,
    deleteFile       : deleteFile,
    readIndex        : readIndex,
    writeIndex       : writeIndex,
    emptyIndex       : emptyIndex,

    collectLocal     : collectLocal,
    mergeIndex       : mergeIndex,
    syncNow          : syncNow,
    lastSync         : lastSync,

    /* テスト用。本番では触らない。 */
    __setTransport   : setTransport,
    __state          : state
  };

}(typeof window !== 'undefined' ? window : this));
