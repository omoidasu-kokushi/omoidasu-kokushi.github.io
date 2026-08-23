/* ==========================================================================
 * license.js  V1.00（20260823 / アプリ V1.53）
 *
 * 改版履歴
 *   V1.00  新設。買い切りライセンスの検証。
 *          ・なぜ7つ目のモジュールにしたか
 *            鍵の検証は storage / scheduler / main のどれの仕事でもない。
 *            main に入れると 7,500 行の中に埋もれ、
 *            scheduler に入れると「出題の理屈」と「売り方の理屈」が混ざる。
 *            売り方は今後いちばん変わる場所なので、独立させて隔離する。
 *          ・なぜサーバを使わないか
 *            このアプリの設計判断は【全データが端末の中で完結する】。
 *            照合サーバを置くと、その約束がライセンスだけ破れ、
 *            オフラインで使えなくなる。ECDSA の署名検証なら
 *            公開鍵を同梱するだけで、通信ゼロで真偽が判定できる。
 *          ・防げないこと（承知のうえ）
 *            鍵の使い回しは防げない。防ぐにはサーバと端末登録が要り、
 *            上の約束を捨てることになる。捨てる価値は無いと判断した。
 * ========================================================================== */
(function (global) {
  'use strict';

  /* storage.js は global.Storage に載る。ブラウザ組み込みの Storage と
     名前が衝突するので、このアプリ固有の APP_BUILD の有無で見分ける
     （DESIGN §1-2）。存在確認だけだと必ず誤判定する。 */
  var S = (global.Storage && global.Storage.APP_BUILD) ? global.Storage : null;

  /* 公開鍵。対応する秘密鍵はこのリポジトリにも配布物にも入れない。
     鍵を作り直すと、それまでに発行した鍵が全部無効になる。 */
  var PUBLIC_JWK = {
    kty: 'EC', crv: 'P-256',
    x: 've_A6Ij-Jz58MiYTVBKVgSzw4DbArLkUPLuG92VTuCg',
    y: 'TAIciL2mXb2eeBVeIV9IjT9uL8Vu_oxNHzZ4PrTUINM'
  };

  /* 無料で解ける問題数。「解いた問題」＝全部の肢に一度は答えた問題。
     肢ではなく問題で数える理由は、利用者から見た数え方と揃えるため
     （ホームの「残り◯問」も問題で数えている）。 */
  var FREE_LIMIT = 200;

  var PREFIX = 'OMOI1';

  var state = { checked: false, ok: false, payload: null, key: null };

  /* ---------- base64url ---------- */
  function b64uToBytes(s) {
    s = String(s || '').replace(/-/g, '+').replace(/_/g, '/');
    while (s.length % 4) { s += '='; }
    var bin = global.atob(s), out = new Uint8Array(bin.length), i;
    for (i = 0; i < bin.length; i++) { out[i] = bin.charCodeAt(i); }
    return out;
  }
  function bytesToUtf8(b) {
    return decodeURIComponent(Array.prototype.map.call(b, function (c) {
      return '%' + ('00' + c.toString(16)).slice(-2);
    }).join(''));
  }
  function utf8ToBytes(s) {
    var esc = unescape(encodeURIComponent(s));
    var out = new Uint8Array(esc.length), i;
    for (i = 0; i < esc.length; i++) { out[i] = esc.charCodeAt(i); }
    return out;
  }

  function normalize(text) {
    /* 貼り付けの事故を吸収する。改行・空白・全角空白を落とす。
       利用者はメールやBOOTHの購入画面から写すので、折り返しが必ず混ざる。 */
    return String(text || '').replace(/[\s　]+/g, '');
  }

  /* ---------- 検証 ---------- */
  function verify(text) {
    var raw = normalize(text);
    var parts = raw.split('.');
    if (parts.length !== 3 || parts[0] !== PREFIX) {
      return Promise.resolve({ ok: false, reason: 'format' });
    }
    if (!global.crypto || !global.crypto.subtle) {
      return Promise.resolve({ ok: false, reason: 'nocrypto' });
    }
    var payloadB64 = parts[1], sigB64 = parts[2], payload;
    try {
      payload = JSON.parse(bytesToUtf8(b64uToBytes(payloadB64)));
    } catch (e) {
      return Promise.resolve({ ok: false, reason: 'format' });
    }
    /* 署名の対象は【前置き＋ペイロード】の文字列そのもの。
       JSON を作り直して署名対象にすると、キーの並び順が変わっただけで
       検証が落ちる。文字列を触らないのが唯一の安全な作り方。 */
    var signed = utf8ToBytes(PREFIX + '.' + payloadB64);
    return global.crypto.subtle.importKey(
      'jwk', PUBLIC_JWK, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['verify']
    ).then(function (k) {
      return global.crypto.subtle.verify(
        { name: 'ECDSA', hash: 'SHA-256' }, k, b64uToBytes(sigB64), signed
      );
    }).then(function (good) {
      return good ? { ok: true, payload: payload, key: raw }
                  : { ok: false, reason: 'signature' };
    }).catch(function () {
      return { ok: false, reason: 'signature' };
    });
  }

  /* 保存済みの鍵を読み直す。起動時に1回。 */
  function load() {
    /* storage.js が読めていない環境では、鍵の有無を判定しない。
       ここで例外を投げると起動そのものが止まり、
       【売り物の都合で学習が止まる】という一番まずい壊れ方になる。 */
    if (!S) { state = { checked: true, ok: false, payload: null, key: null }; return Promise.resolve(state); }
    return S.loadMeta().then(function (m) {
      var k = m.license_key;
      if (!k) { state = { checked: true, ok: false, payload: null, key: null }; return state; }
      return verify(k).then(function (r) {
        state = { checked: true, ok: !!r.ok, payload: r.payload || null, key: r.ok ? r.key : null };
        return state;
      });
    });
  }

  /* 入力された鍵を検証して保存する。偽物は保存しない
     （保存してから判定にすると、起動のたびに検証が走って重くなるうえ、
       「入れたのに効かない」が起きて問い合わせになる）。 */
  function activate(text) {
    return verify(text).then(function (r) {
      if (!r.ok) { return r; }
      if (!S) { return { ok: false, reason: 'nostore' }; }
      return S.setMeta('license_key', r.key).then(function () {
        state = { checked: true, ok: true, payload: r.payload, key: r.key };
        return r;
      });
    });
  }

  function deactivate() {
    if (!S) { return Promise.resolve(state); }
    return S.setMeta('license_key', null).then(function () {
      state = { checked: true, ok: false, payload: null, key: null };
      return state;
    });
  }

  function isPaid() { return !!state.ok; }
  function payload() { return state.payload; }

  /* 無料枠の残り。home の値をそのまま渡す。
     ここで数え直さないのは、数え方が2箇所に分かれると必ずずれるから。 */
  function gate(solvedEver) {
    var used = Math.max(0, Number(solvedEver || 0));
    if (isPaid()) {
      return { paid: true, locked: false, used: used, limit: null, left: null };
    }
    return {
      paid: false,
      locked: used >= FREE_LIMIT,
      used: used,
      limit: FREE_LIMIT,
      left: Math.max(0, FREE_LIMIT - used)
    };
  }

  global.NurseLicense = {
    FREE_LIMIT: FREE_LIMIT,
    verify: verify,
    load: load,
    activate: activate,
    deactivate: deactivate,
    isPaid: isPaid,
    payload: payload,
    gate: gate,
    _state: function () { return state; }
  };
})(window);
