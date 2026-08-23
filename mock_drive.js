/* ============================================================
 * mock_drive.js — Google ドライブの代わり（テスト用）
 *
 * 【なぜ要るか】
 *   同期の壊れ方は「黙って何もしない」「消したものが戻る」「往復が
 *   止まらない」の3つで、どれも本物のドライブ相手では再現しづらい。
 *   ここでは fetch を丸ごと差し替え、ファイルの実体をメモリに置いて
 *   往復を何度でも走らせられるようにする。
 *
 * 【バイト列を壊さないこと】
 *   multipart の本文を .text() で読むと JPEG が壊れる（不正なバイトが
 *   U+FFFD に潰される）。ここでは arrayBuffer() を取って
 *   バイト単位で境界を探す。これを守らないと「往復して劣化しない」
 *   という検証そのものが嘘になる。
 * ============================================================ */
(function (global) {
  'use strict';

  function makeMock() {
    var files = {};     /* id -> {id, name, mime, bytes:Uint8Array, parents, modifiedTime} */
    var seq = 0;
    var log = [];       /* 呼ばれた回数を数える（無駄な検索の検出用） */

    function newId() { seq++; return 'f' + seq; }

    function u8(s) {
      var a = new Uint8Array(s.length), i;
      for (i = 0; i < s.length; i++) { a[i] = s.charCodeAt(i) & 0xff; }
      return a;
    }

    function indexOfSeq(hay, needle, from) {
      var n = needle.length, limit = hay.length - n, i, j, ok;
      for (i = from || 0; i <= limit; i++) {
        ok = true;
        for (j = 0; j < n; j++) { if (hay[i + j] !== needle[j]) { ok = false; break; } }
        if (ok) { return i; }
      }
      return -1;
    }

    function lastIndexOfSeq(hay, needle) {
      var n = needle.length, i, j, ok;
      for (i = hay.length - n; i >= 0; i--) {
        ok = true;
        for (j = 0; j < n; j++) { if (hay[i + j] !== needle[j]) { ok = false; break; } }
        if (ok) { return i; }
      }
      return -1;
    }

    function res(status, body, isBlob) {
      return {
        ok: status >= 200 && status < 300,
        status: status,
        json: function () { return Promise.resolve(body); },
        blob: function () { return Promise.resolve(body); },
        text: function () { return Promise.resolve(JSON.stringify(body)); },
        __isBlob: !!isBlob
      };
    }

    function parseMultipart(bodyBlob, contentType) {
      var m = /boundary=([^;]+)/.exec(contentType || '');
      if (!m) { return Promise.resolve({ meta: {}, bytes: new Uint8Array(0) }); }
      var bnd = u8('--' + m[1]);
      return bodyBlob.arrayBuffer().then(function (buf) {
        var all = new Uint8Array(buf);
        var crlf2 = u8('\r\n\r\n');

        /* 1つ目の境界 → JSON部 */
        var p1 = indexOfSeq(all, bnd, 0);
        var j0 = indexOfSeq(all, crlf2, p1) + 4;
        /* 2つ目の境界 → 中身 */
        var p2 = indexOfSeq(all, bnd, j0);
        var jsonBytes = all.subarray(j0, p2 - 2);           /* 直前の \r\n を落とす */
        var b0 = indexOfSeq(all, crlf2, p2) + 4;
        /* 末尾の境界 */
        var p3 = lastIndexOfSeq(all, bnd);
        var bytes = all.subarray(b0, p3 - 2);

        var meta = {};
        try {
          meta = JSON.parse(new TextDecoder('utf-8').decode(jsonBytes));
        } catch (e) { meta = {}; }
        /* subarray は元バッファを共有する。以降で書き換わらないよう複製する。 */
        return { meta: meta, bytes: new Uint8Array(bytes) };
      });
    }

    function mimeOf(contentType, all) {
      /* multipart の2つ目のパートの Content-Type を拾う。テストでは
         画像かJSONしか来ないので、素朴でよい。 */
      return null;
    }

    function fetchImpl(url, opts) {
      opts = opts || {};
      var method = (opts.method || 'GET').toUpperCase();
      log.push(method + ' ' + url.split('?')[0]);

      /* --- 検索 --- */
      if (method === 'GET' && url.indexOf('/drive/v3/files?') === 0 ||
          (method === 'GET' && /\/drive\/v3\/files\?/.test(url))) {
        var q = decodeURIComponent((/[?&]q=([^&]*)/.exec(url) || [])[1] || '');
        var nameM = /name='([^']*)'/.exec(q);
        var wantFolder = q.indexOf('application/vnd.google-apps.folder') >= 0;
        var hit = Object.keys(files).map(function (k) { return files[k]; })
          .filter(function (f) {
            if (wantFolder) { return f.mime === 'application/vnd.google-apps.folder'; }
            if (nameM && f.name !== nameM[1]) { return false; }
            return f.mime !== 'application/vnd.google-apps.folder';
          });
        return Promise.resolve(res(200, {
          files: hit.map(function (f) {
            return { id: f.id, name: f.name, modifiedTime: f.modifiedTime };
          })
        }));
      }

      /* --- 中身の取得 --- */
      var dl = /\/drive\/v3\/files\/([^/?]+)\?alt=media/.exec(url);
      if (method === 'GET' && dl) {
        var f2 = files[dl[1]];
        if (!f2) { return Promise.resolve(res(404, { error: 'not found' })); }
        return Promise.resolve(res(200, new Blob([f2.bytes], { type: f2.mime }), true));
      }

      /* --- 削除 --- */
      var del = /\/drive\/v3\/files\/([^/?]+)$/.exec(url);
      if (method === 'DELETE' && del) {
        if (!files[del[1]]) { return Promise.resolve(res(404, { error: 'not found' })); }
        delete files[del[1]];
        return Promise.resolve(res(204, {}));
      }

      /* --- フォルダ作成（JSON body の POST） --- */
      if (method === 'POST' && /\/drive\/v3\/files\?/.test(url) &&
          typeof opts.body === 'string') {
        var body = JSON.parse(opts.body);
        var id = newId();
        files[id] = {
          id: id, name: body.name, mime: body.mimeType,
          bytes: new Uint8Array(0), parents: body.parents || [],
          modifiedTime: new Date(0).toISOString()
        };
        return Promise.resolve(res(200, { id: id, name: body.name }));
      }

      /* --- アップロード --- */
      var up = /\/upload\/drive\/v3\/files(?:\/([^/?]+))?\?/.exec(url);
      if ((method === 'POST' || method === 'PATCH') && up) {
        var known = up[1] || null;
        var ct = (opts.headers && (opts.headers['Content-Type'] ||
                                   opts.headers['content-type'])) || '';
        return parseMultipart(opts.body, ct).then(function (parsed) {
          var fid = known || newId();
          var mime = /image/.test(String(ct)) ? 'image/jpeg' : null;
          /* 2つ目のパートの Content-Type は本文の中にある。素朴に判定する。 */
          if (!mime) {
            mime = (parsed.meta.name && /\.jpg$/.test(parsed.meta.name))
                     ? 'image/jpeg' : 'application/json';
          }
          var prev = files[fid];
          files[fid] = {
            id: fid,
            name: parsed.meta.name || (prev && prev.name) || 'unnamed',
            mime: mime,
            bytes: parsed.bytes,
            parents: parsed.meta.parents || (prev && prev.parents) || [],
            modifiedTime: new Date(Date.now()).toISOString()
          };
          return res(200, { id: fid, name: files[fid].name,
                            modifiedTime: files[fid].modifiedTime });
        });
      }

      return Promise.resolve(res(400, { error: 'unhandled ' + method + ' ' + url }));
    }

    return {
      fetch: fetchImpl,
      signIn: function () {
        return Promise.resolve({ access_token: 'mock-token', expires_in: 3600 });
      },
      /* --- テストから覗く口 --- */
      __files: files,
      __log: log,
      list: function () {
        return Object.keys(files).map(function (k) {
          return { id: k, name: files[k].name, mime: files[k].mime,
                   bytes: files[k].bytes.length };
        });
      },
      textOf: function (name) {
        var k, f;
        for (k in files) {
          f = files[k];
          if (f.name === name) { return new TextDecoder('utf-8').decode(f.bytes); }
        }
        return null;
      },
      bytesOf: function (name) {
        var k, f;
        for (k in files) {
          f = files[k];
          if (f.name === name) { return Array.prototype.slice.call(f.bytes); }
        }
        return null;
      },
      countCalls: function (re) {
        return log.filter(function (l) { return re.test(l); }).length;
      },
      resetLog: function () { log.length = 0; }
    };
  }

  global.makeDriveMock = makeMock;

}(typeof window !== 'undefined' ? window : this));
