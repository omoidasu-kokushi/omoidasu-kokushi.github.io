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
  /* 学習の進捗（台帳）。図の目次とは別ファイルにする。
     図は1枚ごとに上げるが、台帳は数MBになりうるので、
     同じ頻度で送ると通信量が釣り合わない。 */
  var PROGRESS_NAME = 'progress.json';
  var PROGRESS_SCHEMA = 1;
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
  function isNum(v) { return typeof v === 'number' && !isNaN(v); }

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

  /* --- トークンを1時間だけ手元に残す（V1.39） ---
     【なぜ】
       Googleのブラウザ向けの仕組みでは、更新用トークンが発行されない。
       黙って取り直すこともできない（公式に「implicit では利用者の
       操作なしにトークンは取れない」と明記されている）。
       つまり【半永久ログインは原理的に作れない】。
       できるのは「1時間は押さずに済む」ことだけ。
       画面を閉じて開き直すたびに押させるのは、その1時間すら
       捨てていることになるので、期限まで手元に残す。
     【残す範囲】
       権限は drive.file だけ。このアプリが作ったファイルしか触れない。
       つまり漏れても届く先は、この端末に元から入っているものと同じ。
       期限が切れたものは読まずに捨てる。 */
  function saveToken() {
    if (!state.token) { return S.setMeta('drive_token', null); }
    return S.setMeta('drive_token', {
      access_token: state.token.access_token,
      expires_at: state.token.expires_at
    });
  }

  function restoreToken() {
    if (tokenValid()) { return Promise.resolve(state.token); }
    return S.loadMeta().then(function (m) {
      var t = m.drive_token;
      if (!t || !t.access_token) { return null; }
      if (Number(t.expires_at || 0) - TOKEN_SKEW_MS <= nowMs()) {
        return S.setMeta('drive_token', null).then(function () { return null; });
      }
      state.token = { access_token: t.access_token, expires_at: Number(t.expires_at) };
      return state.token;
    }).catch(function () { return null; });
  }

  /* 次に押すときアカウントの選択画面を出さないためのヒント。
     権限に email は含めていないので、ドライブ側の about から
     【取れたら取る】。取れなくても動く（選択画面が1枚増えるだけ）。 */
  function rememberHint() {
    if (!tokenValid()) { return Promise.resolve(null); }
    return authHeader().then(function (h) {
      return http('https://www.googleapis.com/drive/v3/about?fields=user(emailAddress)',
                  { headers: h });
    }).then(function (r) {
      if (!r.ok) { return null; }
      return r.json();
    }).then(function (j) {
      var mail = j && j.user && j.user.emailAddress;
      if (!mail) { return null; }
      return S.setMeta('drive_login_hint', mail).then(function () { return mail; });
    }).catch(function () { return null; });
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

  /* --- 押した瞬間にポップアップを開けるようにしておく（V1.37） ---
     【なぜ要るか】
       iOS Safari は「利用者が押した、その場で」開かれた窓しか許さない。
       押したあとに1回でも await（DBの読み書き・スクリプトの読み込み）が
       入ると、そのあとの window.open は無言で塞がれる。
       PCのChromeは緩いので気づきにくく、【スマホだけログインできない】
       という形で出る。
     【対策】
       設定画面を開いた時点で、GISの読み込みとトークンクライアントの
       用意まで済ませておく。押したときに残る仕事を
       requestAccessToken() の1回だけにする。
     ※ 起動時には読み込まない。オフライン起動を壊さないため
       （設定画面を開く＝すでにその気がある、という区切り）。 */
  function prepare() {
    if (state.tokenClient) { return Promise.resolve(true); }
    return Promise.all([getClientId(), S.loadMeta()]).then(function (rr) {
      var clientId = rr[0], hint = (rr[1] || {}).drive_login_hint || undefined;
      if (!clientId) { return false; }
      if (transport) { state.tokenClient = { __mock: true, clientId: clientId }; return true; }
      return loadGis().then(function () {
        state.tokenClient = global.google.accounts.oauth2.initTokenClient({
          client_id: clientId,
          scope: SCOPE,
          /* 前に入ったアカウントを覚えていれば、選択画面を飛ばせる。 */
          hint: hint,
          callback: function (resp) {
            var cb = state.pending; state.pending = null;
            if (!cb) { return; }
            if (resp && resp.access_token) {
              state.token = {
                access_token: resp.access_token,
                expires_at: nowMs() + (Number(resp.expires_in) || 3600) * 1000
              };
              saveToken().catch(function () {});
              rememberHint().catch(function () {});
              cb.resolve(state.token);
            } else {
              cb.reject(new Error('ログインできませんでした。'));
            }
          },
          error_callback: function (err) {
            var cb = state.pending; state.pending = null;
            if (!cb) { return; }
            cb.reject(new Error('ログインを中止しました' +
              ((err && err.type) ? '（' + err.type + '）' : '') + '。'));
          }
        });
        return true;
      }).catch(function () { return false; });
    });
  }

  /* 利用者の操作から呼ぶこと。用意が済んでいれば、ここでの await はゼロ。 */
  function signIn(opts) {
    opts = opts || {};
    if (tokenValid() && !opts.force) { return Promise.resolve(state.token); }

    /* 用意済みなら、押した勢いのまま窓を開く（await を挟まない）。 */
    if (state.tokenClient && !state.tokenClient.__mock) {
      return new Promise(function (resolve, reject) {
        state.pending = { resolve: resolve, reject: reject };
        try {
          state.tokenClient.requestAccessToken({ prompt: opts.force ? 'consent' : '' });
        } catch (e) {
          state.pending = null;
          reject(new Error('ログイン画面を開けませんでした。' +
                           'ポップアップがブロックされていないか確認してください。'));
        }
      });
    }

    return getClientId().then(function (clientId) {
      if (!clientId) {
        throw new Error('先に「クライアントID」を設定してください。');
      }
      if (transport && transport.signIn) {
        return transport.signIn(clientId).then(function (t) {
          state.token = { access_token: t.access_token,
                          expires_at: nowMs() + (t.expires_in || 3600) * 1000 };
          return saveToken().then(function () { return state.token; });
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
                saveToken().catch(function () {});
                rememberHint().catch(function () {});
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
    S.setMeta('drive_token', null).catch(function () {});
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
      /* 期限切れの控えを残すと、次の起動で「ログイン中」に見えたまま
         毎回失敗する。掴んだ時点で捨てる。 */
      state.token = null;
      S.setMeta('drive_token', null).catch(function () {});
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

  /* ======================================================================
   * gzip（V1.59）
   *
   * 学習の記録は、同じ形のオブジェクトが何千行も並ぶ。
   * 実測：3,000件で 400KB。**gzip をかけると 17KB（23分の1）**。
   * 圧縮 12ms・展開 6ms なので、通信を待つより圧倒的に速い。
   *
   * ファイル名は progress.json のまま変えない。
   * 中身が gzip かどうかは**先頭2バイト（1f 8b）で見分ける**ので、
   * 版のフラグを持たなくても、古い（生JSONの）ファイルをそのまま読める。
   * 逆に、圧縮に対応していない端末が生JSONを上げても、
   * こちらは同じ経路で読める。片方だけ新しくても壊れない。
   * ====================================================================== */

  /* 直近の書き出しで、生の大きさと実際に送った大きさ。報告に出す。 */
  var _lastUploadBytes = null;

  function canGzip() {
    return (typeof global.CompressionStream === 'function' &&
            typeof global.DecompressionStream === 'function' &&
            typeof global.Response === 'function');
  }

  function gzipText(text) {
    if (!canGzip()) { return Promise.resolve(null); }
    try {
      var stream = new Blob([text]).stream()
        .pipeThrough(new global.CompressionStream('gzip'));
      return new global.Response(stream).arrayBuffer()
        .then(function (buf) { return new Blob([buf], { type: 'application/gzip' }); })
        .catch(function () { return null; });
    } catch (e) { return Promise.resolve(null); }
  }

  /* Blob を「中身のテキスト」に戻す。gzip でも生でも同じ入口。 */
  function blobToText(blob) {
    return blob.arrayBuffer().then(function (buf) {
      var head = new Uint8Array(buf.slice(0, 2));
      var isGz = head.length === 2 && head[0] === 0x1f && head[1] === 0x8b;
      if (!isGz) { return new Blob([buf]).text(); }
      if (!canGzip()) {
        /* 相手が圧縮して上げたのに、こちらが展開できない。
           黙って空として扱うと【学習の記録が消えた】ように見えるので、
           はっきり失敗させる。 */
        return Promise.reject(new Error(
          'この端末では圧縮された同期ファイルを読めません。ブラウザを新しくしてください。'));
      }
      var stream = new Blob([buf]).stream()
        .pipeThrough(new global.DecompressionStream('gzip'));
      return new global.Response(stream).text();
    });
  }

  /* 中身を落とさずに「向こうが変わったか」だけを見る（V1.59）。
     1回の軽い問い合わせで済むので、変わっていなければ
     数百KBのダウンロードを丸ごと省ける。 */
  function fileStamp(fileId) {
    return authHeader().then(function (h) {
      return http(API_FILES + '/' + fileId + '?fields=version,modifiedTime,size',
                  { headers: h })
        .then(checkResponse)
        .then(function (r) { return r.json(); })
        .then(function (j) {
          return String(j.version || '') + '|' + String(j.modifiedTime || '');
        });
    }).catch(function () { return null; });   /* 分からなければ従来どおり落とす */
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
           String(a.image_file_id || '') !== String(b.image_file_id || '') ||
           Number(a.image_updated_at || 0) !== Number(b.image_updated_at || 0) ||
           Number(a.image_deleted_at || 0) !== Number(b.image_deleted_at || 0);
  }

  /* ------------------------------------------------------------ 同期 */

  /* この端末の状態を目次の形にする */
  function collectLocal() {
    return Promise.all([S.getAllQuestions(), S.getAllUserFiles()]).then(function (r) {
      var qs = r[0];
      var byQ = {};
      r[1].forEach(function (f) { if (f.kind === 'image' && f.q_id) { byQ[f.q_id] = f; } });

      /* 図を消した問題も目次に載せる。載せないと「手元に無い」だけの状態になり、
         向こうの目次に残った image_file_id を根拠に取りに行ってしまう
         ＝【消した図が次の同期でよみがえる】。 */
      return qs.filter(function (q) {
        /* メモを消した問題も目次に載せる（V1.49）。載せないと目次から消え、
           向こうに残った本文を根拠に書き戻してしまう
           ＝【消したメモが次の同期でよみがえる】。図と同じ壊れ方。 */
        return byQ[q.q_id] || q.user_image_deleted_at ||
               (q.user_memo && String(q.user_memo).trim()) ||
               Number(q.memo_updated_at || 0) > 0;
      }).map(function (q) {
        var f = byQ[q.q_id];
        var del = f ? 0 : Number(q.user_image_deleted_at || 0);
        return {
          q_id: q.q_id,
          atom_id: null,
          image_name: f ? (q.q_id + '.jpg') : null,
          /* 実物が無いのに ID を載せない。載せると墓標が「図あり」に見える。 */
          image_file_id: f ? (q.drive_image_id || null) : null,
          image_updated_at: f ? (f.updated_at || 0) : 0,
          image_deleted_at: del,
          memo: q.user_memo || null,
          updated_at: Math.max(Number(q.memo_updated_at || 0),
                               Number(q.user_image_updated_at || 0),
                               del,
                               f ? Number(f.updated_at || 0) : 0)
        };
      });
    });
  }

  /* 押したときだけ走る。戻り値は画面にそのまま出せる報告。 */
  function syncNow(onProgress) {
    var report = {
      ok: true, uploaded: 0, downloaded: 0, memo_updated: 0,
      deleted: 0, removed_local: 0,
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
         （黙って何もしない、が一番まずい壊れ方）。

         V1.39：真偽値ではなく【IDと時刻】で持つ。真偽値だと
         「もう有る」で終わってしまい、同じ枠に入れ直した新しい図が
         永久に上がらなかった。 */
      var remoteImg = {};
      (remote.items || []).forEach(function (it) {
        if (it.image_file_id) {
          remoteImg[keyOf(it)] = { id: it.image_file_id,
                                   at: Number(it.image_updated_at || 0) };
        }
      });

      var seq = Promise.resolve();

      /* 0) この端末で消した図を、ドライブからも消す。
            ここを飛ばすと、消したのに別端末が拾って戻してくる。 */
      merged.items.forEach(function (it) {
        var k = keyOf(it), rm = remoteImg[k];
        var mine = localByKey[k];
        if (!rm) { return; }
        if (it.image_name) { return; }                       /* 実物がある＝消していない */
        if (!(Number(it.image_deleted_at || 0) > rm.at)) { return; }
        if (!mine || Number(mine.image_deleted_at || 0) <= 0) { return; }
        seq = seq.then(function () {
          say('消した図をドライブからも消しています（' + it.q_id + '）…');
          return deleteFile(rm.id).catch(function () { /* 既に無くても続行 */ })
            .then(function () {
              it.image_file_id = null;
              it.image_name = null;
              report.deleted++;
              delete remoteImg[k];
              return S.getQuestion(it.q_id).then(function (q) {
                if (!q) { return null; }
                q.drive_image_id = null;
                return S.putQuestionShallow(q);
              });
            });
        });
      });

      /* 1) 上げる：手元に実物があり、ドライブに無い or 手元の方が新しい。
            差し替えのときは【同じファイルを更新】する（新規に上げると
            ドライブに古い図が残り続ける）。 */
      seq = seq.then(function () {
        var ups = merged.items.filter(function (it) {
          var k = keyOf(it), mine = localByKey[k], rm = remoteImg[k];
          if (!mine || !mine.image_name) { return false; }
          /* 向こうが「もっと新しく消した」のなら上げ返さない。
             ここが無いと、別端末で消した図をこちらが上げ直してしまい、
             消しても消しても戻ってくる（削除が永久に確定しない）。 */
          if (Number(it.image_deleted_at || 0) > Number(mine.image_updated_at || 0)) {
            return false;
          }
          return !rm || Number(mine.image_updated_at || 0) > rm.at;
        });
        var s1 = Promise.resolve();
        ups.forEach(function (it) {
          s1 = s1.then(function () {
            var k = keyOf(it), rm = remoteImg[k], mine = localByKey[k];
            return S.getUserImage(it.q_id).then(function (rec) {
              if (!rec || !rec.blob) { report.skipped++; return; }
              say('図を上げています（' + it.q_id + '）…');
              return uploadBlob(it.q_id + '.jpg', rec.blob,
                                rec.mime || 'image/jpeg', rm ? rm.id : null)
                .then(function (f) {
                  it.image_file_id = f.id;
                  it.image_name = it.q_id + '.jpg';
                  it.image_updated_at = Number(mine.image_updated_at || 0);
                  it.image_deleted_at = 0;
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
        return s1;
      });

      /* 2) 取り込む：ドライブに実物があり、手元に無い or 向こうの方が新しい。
            ただし手元で消したのが向こうより新しいなら取り込まない。 */
      seq = seq.then(function () {
        var downs = merged.items.filter(function (it) {
          var k = keyOf(it), rm = remoteImg[k], mine = localByKey[k];
          if (!rm) { return false; }
          if (Number(it.image_deleted_at || 0) > rm.at) { return false; }
          if (!mine || !mine.image_name) { return true; }
          return rm.at > Number(mine.image_updated_at || 0);
        });
        var s2 = Promise.resolve();
        downs.forEach(function (it) {
          s2 = s2.then(function () {
            var rm = remoteImg[keyOf(it)];
            say('図を取り込んでいます（' + it.q_id + '）…');
            return downloadBlob(rm.id).then(function (b) {
              /* 上げるときに縮小済み。ここで再圧縮すると往復のたびに劣化する。
                 時刻も向こうのものを使う。ここで今の時刻を入れると、
                 取り込んだ側が常に新しくなって上げ返し、往復が止まらない。 */
              return S.putUserImage(it.q_id, b,
                                    { skipShrink: true, updatedAt: rm.at });
            }).then(function () {
              report.downloaded++;
              return S.getQuestion(it.q_id).then(function (q) {
                if (!q) { return null; }
                q.drive_image_id = rm.id;
                return S.putQuestionShallow(q);
              });
            }).catch(function () { report.skipped++; });
          });
        });
        return s2;
      });

      /* 2b) 向こうで消された図を、この端末からも消す。 */
      seq = seq.then(function () {
        var gone = merged.items.filter(function (it) {
          var mine = localByKey[keyOf(it)];
          return mine && mine.image_name && !it.image_name &&
                 Number(it.image_deleted_at || 0) > Number(mine.image_updated_at || 0);
        });
        var s2b = Promise.resolve();
        gone.forEach(function (it) {
          s2b = s2b.then(function () {
            say('向こうで消された図を外しています（' + it.q_id + '）…');
            return S.deleteUserImage(it.q_id,
                     { deletedAt: Number(it.image_deleted_at || 0) })
              .then(function () { report.removed_local++; })
              .catch(function () { report.skipped++; });
          });
        });
        return s2b;
      });

      /* 3) メモの本文を、新しい方に合わせる */
      seq = seq.then(function () {
        var s3 = Promise.resolve();
        merged.items.forEach(function (it) {
          var mine = localByKey[keyOf(it)];
          /* V1.49：空（＝向こうで消された）も反映する。
             以前は `if (!it.memo) return;` で空を素通りさせていたため、
             消したメモが手元に残り続けた。 */
          if (String((mine && mine.memo) || '') === String(it.memo || '')) { return; }
          /* 手元のほうが新しいなら触らない。合体で負けた側だけを書き戻す。 */
          if (mine && Number(mine.updated_at || 0) >= Number(it.updated_at || 0)) { return; }
          s3 = s3.then(function () {
            return S.getQuestion(it.q_id).then(function (q) {
              if (!q) { return null; }
              q.user_memo = it.memo || null;
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
      /* 学習の記録も合わせる。図と違って「合体」する（上書きしない）。 */
      say('学習の記録を確認しています…');
      return syncProgress(say).then(function (pr) {
        report.progress = pr;
      }).catch(function (e) {
        /* 図の同期の結果（件数）は残す。ただし【成功として扱わない】。
           V1.47まで、ここで握りつぶしていたのが最悪の壊れ方だった。
           進捗が1件も上がっていないのに report.ok は true のままで、
           このあと clearDirty() が未同期バッジまで0に戻していた。
           利用者から見ると「同期できている」。実際には学習の記録が
           上がっておらず、機種変更で初めて失われていたと分かる。 */
        report.progress_error = (e && e.message) || String(e);
        report.ok = false;
        report.error = '学習の記録を同期できませんでした：' + report.progress_error;
      });
    }).then(function () {
      report.finished_at = nowMs();
      /* 失敗したときは未同期の印を消さない。
         印が残ることが、利用者にとって唯一の「まだ上がっていない」合図になる。 */
      return (report.ok ? S.clearDirty() : Promise.resolve(null))
        .then(function () { return S.setMeta('drive_last_sync', report.finished_at); })
        .then(function () { return S.setMeta('drive_last_error', report.ok ? null : report.error); })
        .then(function () { return report; });
    }).catch(function (e) {
      report.ok = false;
      report.error = (e && e.message) || String(e);
      report.finished_at = nowMs();
      return S.setMeta('drive_last_error', report.error)
        .catch(function () { return null; })
        .then(function () { return report; });
    });
  }

  /* ======================================================================
   * 学習の進捗の同期（V1.38）
   *
   * 【なぜ「新しい方を採る」ではダメか】
   *   図やメモは1人が1つの文を書くので、新しい方を採れば足りる。
   *   進捗は違う。スマホで問1〜5、PCで問6〜10を解いたなら、
   *   【どちらも残らなければならない】。片方で上書きすると勉強が消える。
   *
   * 【どうするか】
   *   progress_log は追記しかされない台帳なので、2台ぶんを合体できる。
   *   合体した台帳から各肢の状態を組み立て直す（Scheduler.rebuildAtomState）。
   *   結果として、どちらの端末で解いた記録も残る。
   *
   * 【meta の扱い】
   *   数えもの（解答数・到達率）は【大きい方】を採る。減らさないため。
   *   設定（試験日・テーマなど）は新しい方を採る。
   * ====================================================================== */

  /* 大きい方を採る（減らさない）。到達率・回数・ハイウォーターマーク。 */
  var META_MAX_KEYS = [
    'total_questions_answered',
    'max_pct', 'level_current',
    'max_pct_lv1', 'max_pct_lv2', 'max_pct_lv3', 'max_pct_lv4', 'max_pct_lv5',
    'unlock_pct_mock_30', 'unlock_pct_mock_60',
    'unlock_pct_mock_120', 'unlock_pct_mock_weak',
    'full_mock_pass_streak',
    'tutorial_answered', 'pomodoro_session_count',
    /* V1.53：解いた問題数の到達点。無料枠の物差し。大きい方を採る。 */
    'solved_ever',
    /* V1.49：進捗を全消しした時刻。新しい方（＝あとで消した方）が勝つ。
       この時刻以前の記録は合体のときに落とす。 */
    'progress_reset_at'
  ];

  /* 片方でtrueになったら永久にtrue。模試の解禁とオンボーディングの通過。
     V1.39：ここが丸ごと抜けていた。PCで解禁した模試がスマホで出ない、
     チュートリアルをやり直させられる、という形で出る。 */
  var META_OR_KEYS = [
    'unlock_mock_30', 'unlock_mock_60', 'unlock_mock_120', 'unlock_mock_weak',
    'onboarding_done', 'tutorial_finished', 'random_qty_unlocked', 'ui_tour_done'
  ];

  /* 集合の足し算。分析スキャン精度の分子。 */
  var META_UNION_KEYS = ['scan_answered_qids'];

  /* V1.54：肢ごとの時刻表。肢ごとに新しい方を採る。
     範囲リセット（中項目単位の消去）の墓標。全消しの progress_reset_at と違い、
     【どの肢を、いつ消したか】が要るので1つの時刻では持てない。 */
  var META_MAP_MAX_KEYS = ['scope_reset_at'];

  /* V1.53：ライセンスは【持っている側】が勝つ。
     設定の新旧で決めると、買っていない端末で日界を変えただけで
     鍵が消えることになる。片方にあれば残す。 */
  var META_KEEP_KEYS = ['license_key'];

  /* 新しい方を採る。設定・見た目。
     V1.39：oneq_threshold / oneq_always_multi は実在しないキーだった
     （正しくは split_threshold / always_multi）。ずっと空振りしていた。 */
  var META_NEWER_KEYS = [
    'exam_date', 'day_boundary_hour', 'theme', 'visual_theme', 'prefer_frequent',
    'user_image_pos', 'pomodoro_enabled', 'pomodoro_alarm',
    'pomodoro_longbreak_min', 'split_threshold', 'always_multi',
    'notify_enabled', 'badge_enabled', 'verdict_popup_enabled',
    'text_overrides'
  ];

  /* V1.49：設定キーの一覧は【ここが持ち主】。
     storage.js は、この一覧に入っているキーが変わったときだけ
     settings_updated_at を打つ。写しを作らず、起動時に渡す。 */
  if (S && S.setSyncedSettingKeys) { S.setSyncedSettingKeys(META_NEWER_KEYS); }

  /* 【意図的に同期しない】
       drive_*                  端末ごとのID。混ぜると別アカウントを指す。
       seed_imported / last_import_* / total_imported_rows / unit_index_map
                                問題データ由来。取り込み直せば再生成される。
       daily_key / daily_count  その端末のその日の数え。台帳から出せる。
       schema_version / app_build / created_at   端末の素性。
       home_tip_index / tips_seen / pomodoro_hint_shown / review_nag_day
                                その端末での案内の出し分け。混ぜる意味がない。 */

  /* ★を「集合」ではなく「id・状態・時刻」の並びで運ぶ。
     集合の足し算にすると、外した★が相手側から毎回戻ってきて
     二度と外せない（図の削除とまったく同じ壊れ方）。 */
  function starRows(list, idKey) {
    var out = [];
    list.forEach(function (x) {
      var at = Number(x.star_updated_at || 0);
      if (!x.is_starred && !at) { return; }   /* 触られていないものは運ばない */
      out.push({ id: x[idKey], on: !!x.is_starred, at: at });
    });
    return out;
  }

  function mergeStars(a, b) {
    var out = {};
    (a || []).concat(b || []).forEach(function (r) {
      if (!r || r.id === undefined || r.id === null) { return; }
      var prev = out[r.id];
      if (!prev) { out[r.id] = r; return; }
      var pa = Number(prev.at || 0), ra = Number(r.at || 0);
      if (ra > pa) { out[r.id] = r; }
      /* 同時刻で食い違ったら「付いている」を採る。
         消えるより余分に付く方が、利用者にとって取り返しがつく。 */
      else if (ra === pa && r.on && !prev.on) { out[r.id] = r; }
    });
    return Object.keys(out).map(function (k) { return out[k]; });
  }

  function collectProgress() {
    return Promise.all([S.getAllLogs(), S.loadMeta(), S.getAllAtoms(),
                        S.getAllQuestions()])
      .then(function (r) {
        var meta = {}, m = r[1] || {};
        META_MAX_KEYS.concat(META_OR_KEYS, META_UNION_KEYS, META_NEWER_KEYS,
                             META_KEEP_KEYS, META_MAP_MAX_KEYS)
          .forEach(function (k) { if (m[k] !== undefined) { meta[k] = m[k]; } });
        return {
          schema: PROGRESS_SCHEMA,
          updated_at: nowMs(),
          /* 設定の新旧はこちらで比べる。updated_at は同期の後始末でも
             打ち直されるので、物差しにならない（V1.49）。 */
          settings_at: Number(m.settings_updated_at || 0),
          /* V1.48：log_id は端末ごとの連番で、他の端末では意味を持たない。
             送ると、別端末の別の解答に同じ番号が付いた状態で戻ってきて、
             書き戻しのときに主キーが衝突する。端末の外へ出さない。
             （storage.js 側でも落としているので二重の守り） */
          logs: (r[0] || []).map(function (l) {
            var o = {}, k;
            for (k in l) {
              if (Object.prototype.hasOwnProperty.call(l, k) && k !== 'log_id') { o[k] = l[k]; }
            }
            return o;
          }),
          meta: meta,
          stars_atom: starRows(r[2], 'atom_id'),
          stars_question: starRows(r[3], 'q_id'),
          /* 旧版（V1.38）が読めるように、集合の形も残しておく。 */
          starred_atoms: r[2].filter(function (a) { return a.is_starred; })
                             .map(function (a) { return a.atom_id; })
        };
      });
  }

  /* V1.38 が書いた progress.json には時刻が無い。集合しか無いので
     「時刻0で付いている」として読む。以後どちらかの端末で触れば
     そちらが必ず勝つ。 */
  function normalizeStars(p) {
    if (Array.isArray(p.stars_atom)) { return p.stars_atom; }
    return (p.starred_atoms || []).map(function (id) {
      return { id: id, on: true, at: 0 };
    });
  }

  function emptyProgress() {
    return { schema: PROGRESS_SCHEMA, updated_at: 0, settings_at: 0, logs: [], meta: {},
             stars_atom: [], stars_question: [], starred_atoms: [] };
  }

  /* opts.stamp に前回の版タグを渡すと、向こうが変わっていないときは
     { skipped: true } を返して**ダウンロードそのものを省く**。

     省いてよい理由：向こうにあるのは【前回こちらが上げたもの】で、
     こちらの記録はそれ以降**足すだけ**なので、こちらが常に上位互換になる。
     合体しても結果が変わらないので、落とす意味がない。
     （範囲リセットで減ることはあるが、そのときは墓標が一緒に上がるので
       減った状態を上げるのが正しい） */
  function readProgress(opts) {
    opts = opts || {};
    return S.loadMeta().then(function (m) {
      if (m.drive_progress_id) { return { id: m.drive_progress_id }; }
      return findByName(PROGRESS_NAME).then(function (f) {
        if (f) { return rememberId('drive_progress_id', f.id).then(function () { return f; }); }
        return null;
      });
    }).then(function (f) {
      if (!f) { return emptyProgress(); }
      var pre = opts.stamp
        ? fileStamp(f.id).then(function (now) {
            return (now && now === opts.stamp) ? 'same' : now;
          })
        : Promise.resolve(null);
      return pre.then(function (st) {
        if (st === 'same') {
          var e = emptyProgress();
          e.skipped = true;
          e.stamp = opts.stamp;
          return e;
        }
        return downloadBlob(f.id).then(function (b) { return blobToText(b); })
          .then(function (t) {
            var j = null;
            try { j = JSON.parse(t); } catch (e2) { j = null; }
            if (!j || !Array.isArray(j.logs)) { return emptyProgress(); }
            j.stamp = st || null;
            j.bytes = t.length;
            return j;
          });
      });
    });
  }

  function writeProgress(payload) {
    payload.schema = PROGRESS_SCHEMA;
    payload.updated_at = nowMs();
    var text = JSON.stringify(payload);
    /* gzip が使えなければ生のまま上げる。読む側は先頭2バイトで
       見分けるので、片方だけ古い端末でも成立する（V1.59）。 */
    return gzipText(text).then(function (gz) {
      var blob = gz || new Blob([text], { type: 'application/json' });
      var mime = gz ? 'application/gzip' : 'application/json';
      _lastUploadBytes = { raw: text.length, sent: blob.size };
      return S.loadMeta().then(function (m) {
        return uploadBlob(PROGRESS_NAME, blob, mime, m.drive_progress_id || null);
      }).then(function (f) {
        return rememberId('drive_progress_id', f.id).then(function () { return f; });
      }).then(function (f) {
        /* 上げ終わった時点の版タグを控える。次の同期でこれと同じなら
           【前回こちらが上げたまま】なので、落とさずに済む。 */
        return fileStamp(f.id).then(function (st) {
          return S.setMeta('drive_progress_stamp', st || null);
        }).catch(function () { return null; });
      }).then(function () { return payload; });
    });
  }



  function mergeMeta(localMeta, remoteMeta, localAt, remoteAt) {
    var out = {}, i, k;
    for (i = 0; i < META_MAX_KEYS.length; i++) {
      k = META_MAX_KEYS[i];
      var a = Number(localMeta[k] || 0), b = Number(remoteMeta[k] || 0);
      if (localMeta[k] !== undefined || remoteMeta[k] !== undefined) {
        out[k] = Math.max(a, b);
      }
    }
    for (i = 0; i < META_OR_KEYS.length; i++) {
      k = META_OR_KEYS[i];
      if (localMeta[k] !== undefined || remoteMeta[k] !== undefined) {
        out[k] = !!(localMeta[k] || remoteMeta[k]);
      }
    }
    for (i = 0; i < META_UNION_KEYS.length; i++) {
      k = META_UNION_KEYS[i];
      var la = Array.isArray(localMeta[k]) ? localMeta[k] : null;
      var ra = Array.isArray(remoteMeta[k]) ? remoteMeta[k] : null;
      if (la || ra) {
        var seen = {}, list = [];
        (la || []).concat(ra || []).forEach(function (v) {
          var s = String(v);
          if (!seen[s]) { seen[s] = 1; list.push(v); }
        });
        out[k] = list;
      }
    }
    for (i = 0; i < META_MAP_MAX_KEYS.length; i++) {
      k = META_MAP_MAX_KEYS[i];
      var lm = (localMeta[k] && typeof localMeta[k] === 'object') ? localMeta[k] : null;
      var rm = (remoteMeta[k] && typeof remoteMeta[k] === 'object') ? remoteMeta[k] : null;
      if (lm || rm) {
        var mm = {};
        [lm, rm].forEach(function (src) {
          if (!src) { return; }
          Object.keys(src).forEach(function (id) {
            var v = Number(src[id]) || 0;
            if (!(mm[id] >= v)) { mm[id] = v; }
          });
        });
        out[k] = mm;
      }
    }
    for (i = 0; i < META_KEEP_KEYS.length; i++) {
      k = META_KEEP_KEYS[i];
      var kv = localMeta[k] || remoteMeta[k];
      if (kv) { out[k] = kv; }
    }
    var newer = (remoteAt > localAt) ? remoteMeta : localMeta;
    var older = (remoteAt > localAt) ? localMeta : remoteMeta;
    for (i = 0; i < META_NEWER_KEYS.length; i++) {
      k = META_NEWER_KEYS[i];
      if (newer[k] !== undefined) { out[k] = newer[k]; }
      else if (older[k] !== undefined) { out[k] = older[k]; }
    }
    return out;
  }

  /* 合体した台帳を手元へ書き戻し、各肢の状態を作り直す。
     opts.starsAtom / opts.starsQuestion があれば★も書き戻す。 */
  function applyProgress(merged, meta, opts) {
    var K = global.Scheduler;
    var boundary = isNum(meta.day_boundary_hour) ? meta.day_boundary_hour : 4;
    var capMs = K.examCapMs ? K.examCapMs(meta, nowMs(), boundary) : null;

    var byAtom = {};
    merged.forEach(function (l) {
      if (!byAtom[l.atom_id]) { byAtom[l.atom_id] = []; }
      byAtom[l.atom_id].push(l);
    });

    opts = opts || {};
    var starA = {};
    (opts.starsAtom || []).forEach(function (r) { starA[r.id] = r; });

    return S.replaceAllLogs(merged).then(function () {
      return S.getAllAtoms();
    }).then(function (atoms) {
      var patches = {}, touched = 0;
      atoms.forEach(function (a) {
        var patch = null;
        var logs = byAtom[a.atom_id];
        if (logs && logs.length) {
          patch = K.rebuildAtomState(a, logs, { boundaryHour: boundary, capMs: capMs });
          if (patch) { touched++; }
        }
        /* ★は台帳と無関係。解いていない肢にも付く。 */
        var st = starA[a.atom_id];
        if (st && (!!a.is_starred !== !!st.on ||
                   Number(a.star_updated_at || 0) !== Number(st.at || 0))) {
          patch = patch || {};
          patch.is_starred = !!st.on;
          patch.star_updated_at = Number(st.at || 0);
        }
        if (patch) { patches[a.atom_id] = patch; }
      });
      return S.updateAtomsBulk(patches).then(function () { return touched; });
    }).then(function (touched) {
      /* 問題★ */
      var starQ = opts.starsQuestion || [];
      if (!starQ.length) { return touched; }
      return S.getAllQuestions().then(function (qs) {
        var want = {};
        starQ.forEach(function (r) { want[r.id] = r; });
        var qp = {};
        qs.forEach(function (q) {
          var st = want[q.q_id];
          if (!st) { return; }
          if (!!q.is_starred === !!st.on &&
              Number(q.star_updated_at || 0) === Number(st.at || 0)) { return; }
          qp[q.q_id] = { is_starred: !!st.on, star_updated_at: Number(st.at || 0) };
        });
        return S.updateQuestionsBulk(qp).then(function () { return touched; });
      });
    }).then(function (touched) {
      /* 台帳を差し替えたら74概念の理解率はもう合っていない。
         ここで作り直さないと、分析画面と弱点ノックが同期前の値のまま残る。 */
      if (!K.recomputeConceptScores) { return touched; }
      return Promise.resolve(K.recomputeConceptScores())
        .catch(function () { return null; })
        .then(function () { return touched; });
    });
  }

  function syncProgress(say) {
    var report = { logs_before: 0, logs_after: 0, added: 0, atoms_rebuilt: 0 };
    var _dirty = 0;
    return S.loadMeta().then(function (m0) {
      return S.getDirty().then(function (d) {
        _dirty = Number(d || 0);
        return Promise.all([collectProgress(), readProgress({ stamp: m0.drive_progress_stamp })]);
      });
    }).then(function (pair) {
      var mine = pair[0], theirs = pair[1];
      var K = global.Scheduler;
      report.logs_before = mine.logs.length;
      /* 向こうが前回のままなら、落とすのを省いた（V1.59）。
         省いたことは必ず報告に残す。黙って省くと、
         「同期したのに相手の分が来ない」を調べる手がかりが消える。 */
      report.download_skipped = !!theirs.skipped;
      report.downloaded_bytes = theirs.bytes || 0;
      /* 進捗を全消しした時刻より前の記録は、合体のときに落とす（V1.49）。
         落とさないと、向こうの台帳から全部よみがえり、
         利用者が実行した「全部消す」が無言で取り消される。
         新しい方の墓標を採るので、どちらの端末で消しても効く。 */
      var cut = Math.max(Number((mine.meta || {}).progress_reset_at || 0),
                         Number((theirs.meta || {}).progress_reset_at || 0));
      var merged = K.mergeLogs(mine.logs, theirs.logs);
      if (cut > 0) {
        merged = merged.filter(function (l) { return Number(l.answered_at || 0) > cut; });
      }
      /* --- V1.54：範囲リセット（中項目単位）の墓標を適用する ---
         肢ごとに「この時刻までの記録は消した」を持つ。
         全消しと同じ理由で、これが無いと消した範囲だけが
         向こうの台帳からよみがえる。 */
      var scopeCut = {};
      [(mine.meta || {}).scope_reset_at, (theirs.meta || {}).scope_reset_at]
        .forEach(function (src) {
          if (!src || typeof src !== 'object') { return; }
          Object.keys(src).forEach(function (id) {
            var v = Number(src[id]) || 0;
            if (!(scopeCut[id] >= v)) { scopeCut[id] = v; }
          });
        });
      var scopeKeys = Object.keys(scopeCut);
      if (scopeKeys.length) {
        var before2 = merged.length;
        merged = merged.filter(function (l) {
          var c2 = scopeCut[l.atom_id];
          return !(c2 > 0) || Number(l.answered_at || 0) > c2;
        });
        report.dropped_by_scope_reset = before2 - merged.length;
      }

      report.logs_after = merged.length;
      report.added = merged.length - mine.logs.length;
      report.dropped_by_reset = cut > 0 ? 1 : 0;

      /* 設定の新旧は settings_at で比べる。updated_at を使うと、
         同期の後始末で打ち直されたローカルが常に勝ち、
         相手の設定が永久に届かない（V1.48まで）。 */
      var settingsAt = Math.max(Number(mine.settings_at || 0), Number(theirs.settings_at || 0));
      var meta = mergeMeta(mine.meta || {}, theirs.meta || {},
                           Number(mine.settings_at || 0), Number(theirs.settings_at || 0));
      var starsA = mergeStars(normalizeStars(mine), normalizeStars(theirs));
      var starsQ = mergeStars(mine.stars_question || [], theirs.stars_question || []);
      report.stars_atom = starsA.filter(function (r) { return r.on; }).length;
      report.stars_question = starsQ.filter(function (r) { return r.on; }).length;

      if (say) { say('学習の記録を合わせています…'); }
      return applyProgress(merged, meta,
                           { starsAtom: starsA, starsQuestion: starsQ })
      .then(function (n) {
        report.atoms_rebuilt = n;
        /* meta を書き戻す（数えものは大きい方、設定は新しい方） */
        var seq = Promise.resolve();
        Object.keys(meta).forEach(function (k) {
          seq = seq.then(function () { return S.setMeta(k, meta[k]); });
        });
        /* 合わせ終わった時点の「設定の時刻」を揃える。
           ここを揃えないと、書き戻しの setMeta が settings_updated_at を
           今の時刻に押し上げ、次の同期でまたローカルが勝ってしまう。 */
        return seq.then(function () {
          return S.setMeta('settings_updated_at', settingsAt);
        });
      }).then(function () {
        /* --- 何も起きていないなら、上げるのも省く（V1.59） ---
           条件は2つとも満たすときだけ。
             ① 向こうが前回こちらが上げたまま（＝落とすものが無かった）
             ② こちらで利用者の操作が1件も無い（sync_dirty が 0）
           ②は解答・★・メモ・図のすべてで増える。同期そのものの
           書き戻しでは増えないので、「本当に何も起きていない」を表す。

           省いたことは必ず報告に残す。黙って省くと、
           「同期したのに相手へ届かない」を調べる手がかりが消える。 */
        if (theirs.skipped && _dirty === 0) {
          report.upload_skipped = true;
          return null;
        }
        return writeProgress({
          logs: merged, meta: meta, settings_at: settingsAt,
          stars_atom: starsA, stars_question: starsQ,
          starred_atoms: starsA.filter(function (r) { return r.on; })
                               .map(function (r) { return r.id; })
        });
      }).then(function () {
        if (_lastUploadBytes) {
          report.uploaded_bytes = _lastUploadBytes.sent;
          report.uploaded_raw_bytes = _lastUploadBytes.raw;
          report.compressed = _lastUploadBytes.sent < _lastUploadBytes.raw;
        }
        return report;
      });
    });
  }

  /* --- 図を1枚入れたら、その場で上げる（V1.38） ---
     全体同期は台帳ごと送るので重い。図の追加は「その1枚＋目次」だけで済む。
     ログイン済みで期限内のときだけ走らせ、そうでなければ黙って見送る
     （ここで再ログインを促すと、図を貼るたびに邪魔になる）。 */
  function pushOneImage(qId) {
    if (!tokenValid()) { return Promise.resolve({ skipped: true, reason: 'NOT_SIGNED_IN' }); }
    return hasConsent().then(function (okd) {
      if (!okd) { return { skipped: true, reason: 'CONSENT_REQUIRED' }; }
      return S.getUserImage(qId).then(function (rec) {
        if (!rec || !rec.blob) { return { skipped: true, reason: 'NO_IMAGE' }; }
        /* 目次に載っているなら【同じファイルを更新】する。新規に上げると、
           入れ替えるたびにドライブへ古い図が積み上がる。 */
        return withFolderRetry(function () { return readIndex(); }).then(function (idx0) {
          var key0 = String(qId) + '|', prev = null;
          (idx0.items || []).forEach(function (it) {
            if (keyOf(it) === key0 && it.image_file_id) { prev = it.image_file_id; }
          });
          return uploadBlob(qId + '.jpg', rec.blob, rec.mime || 'image/jpeg', prev);
        }).then(function (f) {
          return S.getQuestion(qId).then(function (q) {
            if (q) { q.drive_image_id = f.id; return S.putQuestionShallow(q); }
            return null;
          }).then(function () { return f; });
        }).then(function (f) {
          /* 目次にも反映する。ここを飛ばすと別端末が見つけられない。 */
          return readIndex().then(function (idx) {
            var key = String(qId) + '|';
            var hit = null;
            (idx.items || []).forEach(function (it) { if (keyOf(it) === key) { hit = it; } });
            if (!hit) {
              hit = { q_id: qId, atom_id: null, memo: null, updated_at: 0 };
              idx.items = (idx.items || []).concat([hit]);
            }
            hit.image_name = qId + '.jpg';
            hit.image_file_id = f.id;
            hit.image_updated_at = Number(rec.updated_at || nowMs());
            hit.image_deleted_at = 0;
            hit.updated_at = nowMs();
            return writeIndex({ items: idx.items });
          });
        }).then(function () { return { ok: true, q_id: qId }; });
      });
    }).catch(function (e) {
      return { skipped: true, reason: (e && e.message) || 'ERROR' };
    });
  }

  /* 図を1枚消したら、その場でドライブからも消す（V1.39）。
     pushOneImage の対。これが無いと、消したことが次の全体同期まで
     伝わらず、その間に別端末を開くと消したはずの図が戻ってくる。 */
  function pushImageDelete(qId) {
    if (!tokenValid()) { return Promise.resolve({ skipped: true, reason: 'NOT_SIGNED_IN' }); }
    return hasConsent().then(function (okd) {
      if (!okd) { return { skipped: true, reason: 'CONSENT_REQUIRED' }; }
      return withFolderRetry(function () { return readIndex(); }).then(function (idx) {
        var key = String(qId) + '|', hit = null;
        (idx.items || []).forEach(function (it) { if (keyOf(it) === key) { hit = it; } });
        if (!hit || !hit.image_file_id) { return { skipped: true, reason: 'NOT_ON_DRIVE' }; }
        var fileId = hit.image_file_id;
        hit.image_file_id = null;
        hit.image_name = null;
        hit.image_deleted_at = nowMs();
        hit.updated_at = hit.image_deleted_at;
        return deleteFile(fileId).catch(function () { /* 既に無くても目次は直す */ })
          .then(function () { return writeIndex({ items: idx.items }); })
          .then(function () {
            return S.getQuestion(qId).then(function (q) {
              if (!q) { return null; }
              q.drive_image_id = null;
              return S.putQuestionShallow(q);
            });
          })
          .then(function () { return { ok: true, q_id: qId, deleted: true }; });
      });
    }).catch(function (e) {
      return { skipped: true, reason: (e && e.message) || 'ERROR' };
    });
  }

  /* --- ログイン＝同期（V1.39） ---
     ボタンを2つに分けても、利用者にとっては「押す回数が増える」だけで
     区別に意味がない。押した1回で、必要ならログインし、そのまま同期する。
     ※ 呼び出しは【必ず利用者の操作から直接】。間に await を挟むと
       iOS と一部のブラウザがポップアップを塞ぐ。 */
  function signInAndSync(onProgress) {
    var need = !tokenValid();
    var step = need ? signIn() : Promise.resolve(state.token);
    return step.then(function () {
      return syncNow(onProgress);
    });
  }

  /* 押さずに走る同期。ポップアップは絶対に出さない。
     期限内のトークンがあるときだけ動き、無ければ黙って何もしない。 */
  function autoSync(onProgress) {
    return restoreToken().then(function (t) {
      if (!t) { return { skipped: true, reason: 'NOT_SIGNED_IN' }; }
      return hasConsent().then(function (okd) {
        if (!okd) { return { skipped: true, reason: 'CONSENT_REQUIRED' }; }
        return syncNow(onProgress);
      });
    }).catch(function (e) {
      return { skipped: true, reason: (e && e.message) || 'ERROR' };
    });
  }

  /* 未同期の件数。ログインしていなくても数えられる（通信しない）。 */
  function pendingCount() {
    return S.getDirty().then(function (v) { return Number(v || 0); })
      .catch(function () { return 0; });
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

    prepare          : prepare,
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

    /* V1.59：圧縮まわり。テストから直接叩けるように出しておく。 */
    canGzip          : canGzip,
    gzipText         : gzipText,
    blobToText       : blobToText,
    fileStamp        : fileStamp,

    collectLocal     : collectLocal,
    mergeIndex       : mergeIndex,
    syncNow          : syncNow,
    syncProgress     : syncProgress,
    collectProgress  : collectProgress,
    readProgress     : readProgress,
    writeProgress    : writeProgress,
    mergeMeta        : mergeMeta,
    applyProgress    : applyProgress,
    pushOneImage     : pushOneImage,
    pushImageDelete  : pushImageDelete,
    saveToken        : saveToken,
    restoreToken     : restoreToken,
    rememberHint     : rememberHint,
    signInAndSync    : signInAndSync,
    autoSync         : autoSync,
    pendingCount     : pendingCount,
    mergeStars       : mergeStars,
    normalizeStars   : normalizeStars,
    META_MAX_KEYS    : META_MAX_KEYS,
    META_OR_KEYS     : META_OR_KEYS,
    META_UNION_KEYS  : META_UNION_KEYS,
    META_NEWER_KEYS  : META_NEWER_KEYS,
    PROGRESS_NAME    : PROGRESS_NAME,
    lastSync         : lastSync,

    /* テスト用。本番では触らない。 */
    __setTransport   : setTransport,
    __state          : state
  };

}(typeof window !== 'undefined' ? window : this));
