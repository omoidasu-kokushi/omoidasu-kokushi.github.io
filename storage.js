/* ==========================================================================
 * 20260815_NurseExamApp_V1.00  /  storage.js
 * データ保存層：IndexedDB（6ストア） ＋ 12列TSV/JSON インポータ
 *
 * 【この層が引き受ける責務】
 *  - IndexedDB 6ストアのスキーマ定義と非同期CRUD（排他制御つき）
 *  - 12列TSV / JSON のパースと正規化（表・図解・アトム別解説の分離）
 *  - 正解列の0-based解釈 ＋ 解説文とのクロスチェック（不一致行はスキップ）
 *  - 解禁フラグの永続保持とハイウォーターマーク（Math.max）適用
 *  - バックアップ書き出し／復元／セーフティリセット
 *
 * 【この層が引き受けない責務】
 *  - 弱点pt・出題優先度・忘却間隔の算定  → scheduler.js
 *  - 画面描画・イベント制御               → main.js
 *
 * 【実データ検証で確定した前提】
 *  1. 10列目の正解番号は 0-based（サンプル5行で確認）
 *  2. 12列目のタグはJSON.parseが5/5行で失敗する（二重エスケープ残骸）
 *     → 2段階サニタイザで復元する
 *  3. 11列目のMermaidコードの改行はリテラル "\n"（2文字）
 *     → 実改行へ変換しないと描画できない
 *  4. IndexedDBは boolean をキーに使えないため、索引用に 0/1 の内部
 *     ミラーフィールド（_star / _unlearned）を併置する
 * ========================================================================== */

(function (global) {
  'use strict';

  /* 【改版履歴】
   *  V1.00 初版
   *  V1.01 (1) importText 冒頭の trim() を撤去。
   *            trim() は文字列末尾の空白＝TSVの区切りタブまで削るため、
   *            12列目（タグ）を空にしたまま貼り付けると、最終行だけが
   *            「列数が 11 しかありません（12列必要）」で落ちていた。
   *            エラー文が列数の話なので、利用者はスプレッドシートを数えに行き、
   *            12列あることを確認して原因を見失う。最も気づきにくい壊れ方だった。
   *            途中の行は落ちず最終行だけが消えるため、被害にも気づきにくい。
   *            以後、行の区切り（前後の改行）だけを落とし、タブは1文字も触らない。
   */

  /* ======================================================================
   * 0. 定数
   * ====================================================================== */

  var APP_BUILD   = '20260815_NurseExamApp_V1.00';
  var DB_NAME     = 'nurse_srs_db';
  /* V1.27：自作の図解画像を入れるため 1 → 2。
     既存の6ストアには一切触らず、user_files を足すだけの上げ方にする。
     onupgradeneeded は oldVersion を見て、足りないストアだけを作る。 */
  var DB_VERSION  = 2;
  var SCHEMA_VER  = 2;

  var STORE = {
    QUESTIONS : 'questions',
    ATOMS     : 'atoms',
    PROGRESS  : 'progress_log',
    CONCEPT   : 'concept_stat',
    GUARD     : 'guard_log',
    META      : 'meta',
    FILES     : 'user_files'
  };

  /* 丸数字（①〜⑳）。すべてBMP内の単一コード単位なので indexOf が使える */
  var CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳';

  /* 模試の解禁定義（第11章）。req_q は「DB登録問題数の絶対ガード」 */
  var MOCK_DEFS = [
    { id: 'mock_30',   flag: 'unlock_mock_30',   label: '30問プチ模試',            req_q: 30,  need_unique: 0.15, need_normal_plus: 0.40 },
    { id: 'mock_60',   flag: 'unlock_mock_60',   label: '60問ハーフ模試',          req_q: 60,  need_unique: 0.35, need_normal_plus: 0.45 },
    { id: 'mock_120',  flag: 'unlock_mock_120',  label: '120問フル模試',           req_q: 120, need_unique: 0.50, need_normal_plus: 0.50 },
    { id: 'mock_weak', flag: 'unlock_mock_weak', label: 'いじわる模試（弱点120問）', req_q: 120, need_unique: null, need_normal_plus: null }
  ];

  /* meta ストアの初期値。未知のキーを読んだ場合はここが既定値になる */
  var DEFAULT_META = {
    schema_version          : SCHEMA_VER,
    app_build               : APP_BUILD,
    user_id                 : null,          /* 将来のクラウドDB連携用 */
    created_at              : null,
    updated_at              : null,

    /* --- 表示・進捗（不退転ハイウォーターマーク） --- */
    max_pct                 : 0,             /* 5段階レベルの最高到達率 */
    level_current           : 1,
    scan_answered_qids      : [],            /* 分析スキャン精度の分子（ユニーク問題ID） */

    /* --- 模試の解禁フラグ（一度trueにしたら永久に戻さない） --- */
    unlock_mock_30          : false,
    unlock_mock_60          : false,
    unlock_mock_120         : false,
    unlock_mock_weak        : false,
    unlock_pct_mock_30      : 0,             /* 解禁進捗率のハイウォーターマーク */
    unlock_pct_mock_60      : 0,
    unlock_pct_mock_120     : 0,
    unlock_pct_mock_weak    : 0,
    full_mock_pass_streak   : 0,             /* フル模試の連続合格回数 */

    /* --- オンボーディング --- */
    onboarding_done         : false,
    onboarding_step         : 0,
    tutorial_answered       : 0,             /* 中断時のチェックポイント */
    tutorial_finished       : false,
    random_qty_unlocked     : false,         /* 2回目以降の全出題数解放 */
    ui_tour_done            : false,

    /* --- ポモドーロ --- */
    pomodoro_enabled        : true,
    pomodoro_session_count  : 0,
    pomodoro_alarm          : 'chime',
    pomodoro_longbreak_min  : 15,
    notify_enabled          : false,
    badge_enabled           : true,

    /* --- 生活リズム・表示 --- */
    day_boundary_hour       : 4,             /* 日界＝午前4:00 */
    theme                   : 'light',
    visual_theme            : 'challenge',
    prefer_frequent         : true,          /* 「頻出問題を優先する」トグル */

    /* --- 単元番号の採番テーブル（num_codeの安定生成用） --- */
    unit_index_map          : {},

    /* --- 日次カウンタ（分析精度100%到達後の表示差し替え用） --- */
    daily_key               : null,          /* 日界4:00基準の「その日」の開始時刻 */
    daily_count             : 0,             /* 今日解いた問題数 */
    total_questions_answered: 0,

    /* --- 表示設定 --- */
    verdict_popup_enabled   : true,          /* 正誤ポップアップ */

    /* --- インポート履歴 --- */
    last_import_at          : null,
    last_import_report      : null,
    total_imported_rows     : 0
  };

  /* ======================================================================
   * 1. 汎用ユーティリティ
   * ====================================================================== */

  function nowMs() { return Date.now(); }

  function clamp(v, lo, hi) { return v < lo ? lo : (v > hi ? hi : v); }

  function isNum(v) { return typeof v === 'number' && isFinite(v); }

  /* FNV-1a 32bit：同一行の再インポートを「追加」ではなく「更新」にするための安定ID生成 */
  function fnv1a(str) {
    var h = 0x811c9dc5, i;
    for (i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
    }
    return h >>> 0;
  }

  function hash6(str) {
    var s = fnv1a(str).toString(36).toUpperCase();
    while (s.length < 6) { s = '0' + s; }
    return s.slice(0, 6);
  }

  function circledToIndex(ch) {
    var i = CIRCLED.indexOf(ch);
    return i < 0 ? -1 : i;
  }

  function indexToCircled(i) {
    return (i >= 0 && i < CIRCLED.length) ? CIRCLED.charAt(i) : String(i + 1);
  }

  /* 日界（既定4:00）を考慮した「その日の始まり」のepoch ms */
  function dayStart(ts, boundaryHour) {
    var h = isNum(boundaryHour) ? boundaryHour : 4;
    var d = new Date(ts);
    if (d.getHours() < h) { d.setDate(d.getDate() - 1); }
    d.setHours(h, 0, 0, 0);
    return d.getTime();
  }

  function safeParseJson(text, fallback) {
    try { return JSON.parse(text); } catch (e) { return fallback; }
  }

  function stripHtml(html) {
    return String(html == null ? '' : html)
      .replace(/<br\s*\/?>/gi, ' ')
      .replace(/<[^>]+>/g, '')
      .replace(/&nbsp;/g, ' ')
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/\s{2,}/g, ' ')
      .trim();
  }

  /* ======================================================================
   * 2. IndexedDB コア（非同期 ＋ 書き込み排他制御）
   * ====================================================================== */

  var _db = null;
  var _openPromise = null;
  /* すべての書き込みを直列化するキュー。並行トランザクションによる
     読み書き競合（例：インポート中の自動セーブ）を根本から防ぐ。 */
  var _writeChain = Promise.resolve();

  function req2promise(request) {
    return new Promise(function (resolve, reject) {
      request.onsuccess = function () { resolve(request.result); };
      request.onerror   = function () { reject(request.error); };
    });
  }

  function tx2promise(tx) {
    return new Promise(function (resolve, reject) {
      tx.oncomplete = function () { resolve(); };
      tx.onerror    = function () { reject(tx.error); };
      tx.onabort    = function () { reject(tx.error || new Error('transaction aborted')); };
    });
  }

  function upgradeSchema(db, oldVersion) {
    /* --- questions --- */
    if (!db.objectStoreNames.contains(STORE.QUESTIONS)) {
      var q = db.createObjectStore(STORE.QUESTIONS, { keyPath: 'q_id' });
      q.createIndex('unit',       'unit',       { unique: false });
      q.createIndex('major',      'major',      { unique: false });
      q.createIndex('medium',     'medium',     { unique: false });
      q.createIndex('sub_item',   'sub_item',   { unique: false });
      q.createIndex('rank',       'rank',       { unique: false });
      q.createIndex('num_code',   'num_code',   { unique: false });
      q.createIndex('_star',      '_star',      { unique: false });
      q.createIndex('updated_at', 'updated_at', { unique: false });
    }

    /* --- atoms（questions から非正規化した独立ストア）
       IndexedDBは入れ子配列に索引を張れないため、アトムを分離しないと
       「本日の復習（due_date順）」が全件走査になり、1000問規模で起動が固まる。 */
    if (!db.objectStoreNames.contains(STORE.ATOMS)) {
      var a = db.createObjectStore(STORE.ATOMS, { keyPath: 'atom_id' });
      a.createIndex('q_id',        'q_id',        { unique: false });
      a.createIndex('tags',        'tags',        { unique: false, multiEntry: true });
      a.createIndex('due_date',    'due_date',    { unique: false });
      a.createIndex('last_eval',   'last_eval',   { unique: false });
      a.createIndex('srs_step',    'srs_step',    { unique: false });
      a.createIndex('_star',       '_star',       { unique: false });
      a.createIndex('_unlearned',  '_unlearned',  { unique: false });
      a.createIndex('rank',        'rank',        { unique: false });
      a.createIndex('unit',        'unit',        { unique: false });
      a.createIndex('major',       'major',       { unique: false });
      a.createIndex('medium',      'medium',      { unique: false });
      a.createIndex('sub_item',    'sub_item',    { unique: false });
    }

    /* --- progress_log（弱点ptの新近性補正・連続誤答ボーナスの計算根拠）
       第6章②「直近が簡単以外なら過去の-5ptを全て無効化」は累積値では
       表現できないため、評価の全履歴をここに保持して毎回再計算する。 */
    if (!db.objectStoreNames.contains(STORE.PROGRESS)) {
      var p = db.createObjectStore(STORE.PROGRESS, { keyPath: 'log_id', autoIncrement: true });
      p.createIndex('atom_id',     'atom_id',     { unique: false });
      p.createIndex('q_id',        'q_id',        { unique: false });
      p.createIndex('answered_at', 'answered_at', { unique: false });
      p.createIndex('mode',        'mode',        { unique: false });
    }

    /* --- concept_stat（74概念の理解率） --- */
    if (!db.objectStoreNames.contains(STORE.CONCEPT)) {
      var c = db.createObjectStore(STORE.CONCEPT, { keyPath: 'tag' });
      c.createIndex('score',      'score',      { unique: false });
      c.createIndex('category',   'category',   { unique: false });
      c.createIndex('updated_at', 'updated_at', { unique: false });
    }

    /* --- guard_log（トピックガードのFIFOパージ用） --- */
    if (!db.objectStoreNames.contains(STORE.GUARD)) {
      var g = db.createObjectStore(STORE.GUARD, { keyPath: 'q_id' });
      g.createIndex('answered_at', 'answered_at', { unique: false });
      g.createIndex('tags',        'tags',        { unique: false, multiEntry: true });
    }

    /* --- meta --- */
    if (!db.objectStoreNames.contains(STORE.META)) {
      db.createObjectStore(STORE.META, { keyPath: 'key' });
    }

    /* --- user_files（V1.27／DB v2）：利用者が入れた画像を Blob のまま持つ ---
       画像を questions に埋めない理由：questions は再インポートで丸ごと
       put し直すストアなので、そこに置くと取り込みのたびに画像が消える。
       別ストアにして q_id で結びつけ、questions 側は id だけを持つ。 */
    if (!db.objectStoreNames.contains(STORE.FILES)) {
      var f = db.createObjectStore(STORE.FILES, { keyPath: 'file_id' });
      f.createIndex('q_id',       'q_id',       { unique: false });
      f.createIndex('kind',       'kind',       { unique: false });
      f.createIndex('updated_at', 'updated_at', { unique: false });
    }

    void oldVersion;
  }

  function open() {
    if (_db) { return Promise.resolve(_db); }
    if (_openPromise) { return _openPromise; }

    _openPromise = new Promise(function (resolve, reject) {
      if (!global.indexedDB) {
        reject(new Error('この端末では IndexedDB が使えません。ブラウザを更新するか、プライベートモードを解除してください。'));
        return;
      }
      var request = global.indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = function (ev) {
        upgradeSchema(request.result, ev.oldVersion);
      };
      request.onsuccess = function () {
        _db = request.result;
        _db.onversionchange = function () {
          _db.close();
          _db = null;
          _openPromise = null;
        };
        resolve(_db);
      };
      request.onerror = function () { reject(request.error); };
      request.onblocked = function () {
        reject(new Error('別のタブでアプリが開かれています。他のタブを閉じてから、もう一度お試しください。'));
      };
    });

    return _openPromise;
  }

  /* 読み取り専用トランザクション */
  function readTx(storeNames) {
    return open().then(function (db) {
      return db.transaction(storeNames, 'readonly');
    });
  }

  /* 書き込みトランザクション。必ず _writeChain に載せて直列化する */
  function write(storeNames, fn) {
    var run = _writeChain.then(function () {
      return open().then(function (db) {
        var tx = db.transaction(storeNames, 'readwrite');
        var stores = {};
        (Array.isArray(storeNames) ? storeNames : [storeNames]).forEach(function (n) {
          stores[n] = tx.objectStore(n);
        });
        var result = fn(stores, tx);
        return Promise.resolve(result).then(function (r) {
          return tx2promise(tx).then(function () { return r; });
        });
      });
    });
    /* 失敗しても後続の書き込みを止めない */
    _writeChain = run.then(function () {}, function () {});
    return run;
  }

  function getAll(storeName, indexName, range, limit) {
    return readTx([storeName]).then(function (tx) {
      var src = tx.objectStore(storeName);
      if (indexName) { src = src.index(indexName); }
      if (typeof src.getAll === 'function') {
        return req2promise(src.getAll(range || null, limit || undefined));
      }
      /* getAll 非対応環境向けのカーソルフォールバック */
      return new Promise(function (resolve, reject) {
        var out = [];
        var cur = src.openCursor(range || null);
        cur.onsuccess = function () {
          var c = cur.result;
          if (!c || (limit && out.length >= limit)) { resolve(out); return; }
          out.push(c.value);
          c.continue();
        };
        cur.onerror = function () { reject(cur.error); };
      });
    });
  }

  function getOne(storeName, key) {
    return readTx([storeName]).then(function (tx) {
      return req2promise(tx.objectStore(storeName).get(key));
    });
  }

  function countStore(storeName, indexName, range) {
    return readTx([storeName]).then(function (tx) {
      var src = tx.objectStore(storeName);
      if (indexName) { src = src.index(indexName); }
      return req2promise(src.count(range || null));
    });
  }

  /* ======================================================================
   * 3. meta ストア
   * ====================================================================== */

  var _metaCache = null;

  function loadMeta() {
    if (_metaCache) { return Promise.resolve(_metaCache); }
    return getAll(STORE.META).then(function (rows) {
      var m = {}, k;
      for (k in DEFAULT_META) {
        if (Object.prototype.hasOwnProperty.call(DEFAULT_META, k)) {
          m[k] = DEFAULT_META[k];
        }
      }
      rows.forEach(function (r) { m[r.key] = r.value; });
      _metaCache = m;
      return m;
    });
  }

  function getMeta(key, fallback) {
    return loadMeta().then(function (m) {
      var v = m[key];
      if (v === undefined || v === null) {
        return (fallback !== undefined) ? fallback
             : (DEFAULT_META[key] !== undefined ? DEFAULT_META[key] : null);
      }
      return v;
    });
  }

  function setMeta(key, value) {
    return write([STORE.META], function (s) {
      s[STORE.META].put({ key: key, value: value, updated_at: nowMs() });
      s[STORE.META].put({ key: 'updated_at', value: nowMs(), updated_at: nowMs() });
    }).then(function () {
      if (_metaCache) {
        _metaCache[key] = value;
        _metaCache.updated_at = nowMs();
      }
      return value;
    });
  }

  function setMetaBulk(obj) {
    var ts = nowMs();
    return write([STORE.META], function (s) {
      Object.keys(obj).forEach(function (k) {
        s[STORE.META].put({ key: k, value: obj[k], updated_at: ts });
      });
      s[STORE.META].put({ key: 'updated_at', value: ts, updated_at: ts });
    }).then(function () {
      if (_metaCache) {
        Object.keys(obj).forEach(function (k) { _metaCache[k] = obj[k]; });
        _metaCache.updated_at = ts;
      }
      return obj;
    });
  }

  /* 数値metaにハイウォーターマーク（Math.max）を適用して保存する。
     問題追加やデータ入れ替えでパーセンテージが後戻りするのを防ぐ。 */
  function raiseMeta(key, candidate) {
    return getMeta(key, 0).then(function (cur) {
      var next = Math.max(isNum(cur) ? cur : 0, isNum(candidate) ? candidate : 0);
      if (next === cur) { return cur; }
      return setMeta(key, next);
    });
  }

  function ensureInitialized() {
    return loadMeta().then(function (m) {
      if (m.created_at) { return m; }
      var uid = 'local-' + hash6(String(nowMs()) + Math.random());
      return setMetaBulk({
        schema_version : SCHEMA_VER,
        app_build      : APP_BUILD,
        user_id        : m.user_id || uid,
        created_at     : nowMs(),
        updated_at     : nowMs()
      }).then(function () { return loadMeta(); });
    });
  }

  /* ======================================================================
   * 4. パーサ（純関数群 / テスト可能なように Parser として公開する）
   * ====================================================================== */

  /* ---- 4-1. TSV 行分割（クォート内のタブを壊さない状態機械）
     外側のクォートは剥がさずに返す。剥がすのは csvUnquote の仕事にして、
     実データで検証済みのサニタイズ手順を1本に保つ。 */
  function splitTsvRow(line) {
    var cells = [];
    var buf = '';
    var inQuotes = false;
    var atFieldStart = true;
    var i, ch, next;

    for (i = 0; i < line.length; i++) {
      ch = line.charAt(i);

      if (inQuotes) {
        if (ch === '"') {
          next = line.charAt(i + 1);
          if (next === '"') { buf += '""'; i++; }
          else { buf += '"'; inQuotes = false; }
        } else {
          buf += ch;
        }
        continue;
      }

      if (ch === '\t') {
        cells.push(buf);
        buf = '';
        atFieldStart = true;
        continue;
      }

      if (ch === '"' && atFieldStart) {
        inQuotes = true;
        buf += '"';
        atFieldStart = false;
        continue;
      }

      buf += ch;
      atFieldStart = false;
    }
    cells.push(buf);
    return cells;
  }

  /* ---- 4-2. CSVアンクォート */
  function csvUnquote(cell) {
    var s = String(cell == null ? '' : cell).trim();
    if (s.length >= 2 && s.charAt(0) === '"' && s.charAt(s.length - 1) === '"') {
      s = s.slice(1, -1).replace(/""/g, '"');
    }
    return s;
  }

  /* ---- 4-3. リテラルエスケープの実体化
     スプレッドシート経由の1セルには実改行を入れられないため、
     Mermaidの改行が "\n"（バックスラッシュ + n の2文字）で来る。
     これを実改行に戻さないと Mermaid.js が構文エラーで描画に失敗する。 */
  function unescapeLiteral(text) {
    return String(text == null ? '' : text)
      .replace(/\\r\\n/g, '\n')
      .replace(/\\n/g, '\n')
      .replace(/\\r/g, '\n')
      .replace(/\\t/g, '\t')
      .replace(/\\"/g, '"')
      .replace(/\\'/g, "'");
  }

  /* ---- 4-4. JSON セルの2段階サニタイザ
     実データ検証：12列目は JSON.parse が 5/5 行で失敗する。
     さらに5行目は末尾のクォート数が足りず構造そのものが壊れている。
     段階1（厳格）で拾えない行を段階2（括弧＋#タグ直接抽出）で救う。 */
  function sanitizeJsonCell(raw) {
    var s = csvUnquote(raw);
    if (!s) { return { value: null, method: 'empty' }; }

    var direct = safeParseJson(s, undefined);
    if (direct !== undefined) { return { value: direct, method: 'direct' }; }

    var cleaned = s
      .replace(/\\+"/g, '"')
      .replace(/"{2,}/g, '"')
      .replace(/,\s*([\]}])/g, '$1');

    var strict = safeParseJson(cleaned, undefined);
    if (strict !== undefined) { return { value: strict, method: 'strict' }; }

    return { value: null, method: 'failed', cleaned: cleaned };
  }

  /* ---- 4-5. タグ列（アトム別の入れ子配列）の復元 */
  function sanitizeTagCell(raw, atomCount) {
    var out = [];
    var i, j;
    var res = sanitizeJsonCell(raw);
    var method = res.method;
    var v = res.value;

    if (Array.isArray(v)) {
      for (i = 0; i < v.length; i++) {
        if (Array.isArray(v[i])) {
          out.push(v[i].map(function (t) { return String(t).trim(); }).filter(Boolean));
        } else if (typeof v[i] === 'string' && v[i].trim()) {
          out.push([v[i].trim()]);
        } else {
          out.push([]);
        }
      }
    } else {
      /* 段階2：括弧のかたまりごとに #タグを直接回収する */
      var src = csvUnquote(raw);
      var groups = src.match(/\[([^\[\]]*)\]/g) || [];
      for (i = 0; i < groups.length; i++) {
        out.push((groups[i].match(/#[^"',\]\s]+/g) || []).map(function (t) { return t.trim(); }));
      }
      if (out.length) { method = 'fallback'; }
      else {
        var flat = (src.match(/#[^"',\]\s]+/g) || []).map(function (t) { return t.trim(); });
        if (flat.length) { out.push(flat); method = 'flat'; }
        else { method = 'none'; }
      }
    }

    /* アトム数に合わせて長さを揃える（不足分は先頭タグで補う） */
    if (isNum(atomCount) && atomCount > 0) {
      if (out.length > atomCount) { out = out.slice(0, atomCount); }
      var seed = out.length ? out[0] : [];
      for (j = out.length; j < atomCount; j++) { out.push(seed.slice()); }
    }
    return { tags: out, method: method };
  }

  /* ---- 4-6. <table> の抽出（比較表フィールドへ分離） */
  function extractTables(html) {
    var src = String(html == null ? '' : html);
    var found = src.match(/<table[\s\S]*?<\/table>/gi) || [];
    var rest = src.replace(/<table[\s\S]*?<\/table>/gi, '');
    return { table: found.join('\n'), rest: rest };
  }

  /* ---- 4-7. ```mermaid ... ``` の抽出（図解フィールドへ分離） */
  function extractMermaid(html) {
    var src = String(html == null ? '' : html);
    var codes = [];
    var re = /```\s*mermaid([\s\S]*?)```/gi;
    var m;
    while ((m = re.exec(src)) !== null) {
      codes.push(unescapeLiteral(m[1]).replace(/^\s*\n/, '').replace(/\s+$/, ''));
    }
    var rest = src.replace(/```\s*mermaid[\s\S]*?```/gi, '');

    /* mermaid 指定のない裸のコードフェンスでも、図解構文なら拾う */
    if (!codes.length) {
      var re2 = /```([\s\S]*?)```/g;
      var m2;
      while ((m2 = re2.exec(src)) !== null) {
        var body = unescapeLiteral(m2[1]);
        if (/^\s*(graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|gantt|pie|erDiagram|journey|mindmap)\b/i.test(body)) {
          codes.push(body.replace(/^\s*\n/, '').replace(/\s+$/, ''));
          rest = rest.replace(m2[0], '');
        }
      }
    }
    return { mermaid: codes.join('\n'), rest: rest };
  }

  /* ---- 4-8. [IMAGE: images/xxx.png] の抽出 */
  function extractImage(stem) {
    var src = String(stem == null ? '' : stem);
    var m = src.match(/\[\s*IMAGE\s*:\s*([^\]]+)\]/i);
    if (!m) { return { image_url: null, stem: src.trim() }; }
    return {
      image_url: m[1].trim(),
      stem: src.replace(/\[\s*IMAGE\s*:\s*[^\]]+\]/ig, '').trim()
    };
  }

  /* ---- 4-9. 解説本文を ①②③④ でアトム別に分解する
     戻り値 byIndex[i] は i番目の選択肢に対応する解説断片。
     ◆関連知識 以降は全体解説側にだけ残し、アトムには混ぜない。 */
  function splitAtomExplanations(body, atomCount) {
    var src = String(body == null ? '' : body);
    var byIndex = new Array(atomCount);
    var i;
    for (i = 0; i < atomCount; i++) { byIndex[i] = ''; }

    var markers = [];
    var re = /(?:・\s*)?<span[^>]*>\s*([①-⑳])/g;
    var m;
    while ((m = re.exec(src)) !== null) {
      markers.push({ start: m.index, idx: circledToIndex(m[1]) });
    }
    if (!markers.length) {
      /* span を使わない書式へのフォールバック */
      var re2 = /(?:<br\s*\/?>|^)\s*・?\s*([①-⑳])\s*[^\s]/g;
      while ((m = re2.exec(src)) !== null) {
        markers.push({ start: m.index, idx: circledToIndex(m[1]) });
      }
    }
    if (!markers.length) { return { byIndex: byIndex, matched: 0 }; }

    /* 「◆」「【周辺知識】」以降は関連知識ブロックとして切り離す */
    var lastStart = markers[markers.length - 1].start;
    var tailPos = -1;
    var tailPatterns = [/◆/g, /【周辺知識】/g, /【関連知識】/g, /【全体像】/g, /【まとめ】/g];
    tailPatterns.forEach(function (tp) {
      tp.lastIndex = 0;
      var t;
      while ((t = tp.exec(src)) !== null) {
        if (t.index > lastStart && (tailPos < 0 || t.index < tailPos)) { tailPos = t.index; }
      }
    });
    var hardEnd = (tailPos >= 0) ? tailPos : src.length;

    var matched = 0;
    for (i = 0; i < markers.length; i++) {
      var from = markers[i].start;
      var to = (i + 1 < markers.length) ? markers[i + 1].start : hardEnd;
      if (to > hardEnd) { to = hardEnd; }
      if (to <= from) { continue; }
      var chunk = src.slice(from, to)
        .replace(/^\s*・\s*/, '')
        .replace(/(?:<br\s*\/?>|\s)+$/i, '')
        .trim();
      var at = markers[i].idx;
      if (at >= 0 && at < atomCount) {
        byIndex[at] = byIndex[at] ? (byIndex[at] + '<br>' + chunk) : chunk;
        matched++;
      }
    }
    return { byIndex: byIndex, matched: matched };
  }

  /* ---- 4-10. 解説文から「どの丸数字が正解と書かれているか」を検出する
     承認済み仕様：10列目の 0-based 解釈をここで必ずクロスチェックする。 */
  function detectCorrectFromExplanation(body) {
    var src = String(body == null ? '' : body);
    var correct = [], wrong = [], m;

    var reC = /<span[^>]*>\s*([①-⑳])\s*(?:正解|正しい)/g;
    var reW = /<span[^>]*>\s*([①-⑳])\s*(?:誤り|誤|正しくない|不適切|不適当)/g;
    while ((m = reC.exec(src)) !== null) { correct.push(circledToIndex(m[1])); }
    while ((m = reW.exec(src)) !== null) { wrong.push(circledToIndex(m[1])); }
    if (correct.length || wrong.length) {
      return { correct: uniqSorted(correct), wrong: uniqSorted(wrong), method: 'span' };
    }

    /* span を使わない書式：丸数字 ＋ 正解 ＋ コロン に限定して誤検出を抑える */
    var reC2 = /([①-⑳])\s*(?:正解|正しい)\s*[：:]/g;
    var reW2 = /([①-⑳])\s*(?:誤り|正しくない|不適切|不適当)\s*[：:]/g;
    while ((m = reC2.exec(src)) !== null) { correct.push(circledToIndex(m[1])); }
    while ((m = reW2.exec(src)) !== null) { wrong.push(circledToIndex(m[1])); }
    if (correct.length || wrong.length) {
      return { correct: uniqSorted(correct), wrong: uniqSorted(wrong), method: 'loose' };
    }

    return { correct: [], wrong: [], method: 'none' };
  }

  function uniqSorted(arr) {
    var seen = {}, out = [], i;
    for (i = 0; i < arr.length; i++) {
      if (arr[i] >= 0 && !seen[arr[i]]) { seen[arr[i]] = 1; out.push(arr[i]); }
    }
    return out.sort(function (a, b) { return a - b; });
  }

  /* ---- 4-11. 10列目（正解）のパース。0-based を基本とする */
  function parseAnswerCell(raw, qtype, optCount) {
    var s = csvUnquote(raw).trim();
    if (qtype === 'numeric') {
      var num = parseFloat(s.replace(/[,，\s]/g, ''));
      if (!isFinite(num)) {
        return { indices: [], numeric: null, error: '数値解答が読み取れません（10列目: "' + s + '"）' };
      }
      return { indices: [], numeric: num, error: null };
    }

    var body = s.replace(/^\[/, '').replace(/\]$/, '').replace(/["']/g, '');
    var parts = body.split(/[,、\/\s|]+/).filter(function (t) { return t !== ''; });
    if (!parts.length) {
      return { indices: [], numeric: null, error: '正解番号が空です（10列目）' };
    }

    var indices = [], i, n;
    for (i = 0; i < parts.length; i++) {
      /* 丸数字で書かれていた場合も受け入れる（この場合は 1-based 相当） */
      var ci = circledToIndex(parts[i]);
      if (ci >= 0) { indices.push(ci); continue; }
      n = parseInt(parts[i], 10);
      if (!isFinite(n)) {
        return { indices: [], numeric: null, error: '正解番号に数値でない値があります（10列目: "' + parts[i] + '"）' };
      }
      indices.push(n);
    }

    indices = uniqSorted(indices);
    for (i = 0; i < indices.length; i++) {
      if (indices[i] < 0 || indices[i] >= optCount) {
        return {
          indices: indices, numeric: null,
          error: '正解番号 ' + indices[i] + ' が選択肢数（' + optCount + '）の範囲外です。0-based で記述してください'
        };
      }
    }
    return { indices: indices, numeric: null, error: null };
  }

  /* ---- 4-12. クロスチェック（承認済み：不一致行はスキップ） */
  function crossCheckAnswer(declared, detected, optCount) {
    if (!detected || detected.method === 'none' || !detected.correct.length) {
      return { status: 'unverified', hint: '解説文に「①〜⑤ 正解」の記述が見つからず、自動検算できませんでした' };
    }
    var d = uniqSorted(declared.slice());
    var e = uniqSorted(detected.correct.slice());

    if (d.join(',') === e.join(',')) { return { status: 'ok', hint: null }; }

    /* 宣言された正解肢が、解説では明確に「誤り」と書かれている場合は確実な不一致 */
    var contradicted = d.filter(function (x) { return detected.wrong.indexOf(x) >= 0; });

    /* 1-based で記述されている疑いの検出（全問ズレを未然に潰すためのヒント） */
    var shifted = d.map(function (x) { return x - 1; }).filter(function (x) { return x >= 0 && x < optCount; });
    if (shifted.length === d.length && shifted.join(',') === e.join(',')) {
      return {
        status: 'mismatch',
        hint: '10列目が 1-based で記述されている可能性があります（解説では ' +
              e.map(function (x) { return indexToCircled(x); }).join('') + ' が正解）'
      };
    }

    return {
      status: 'mismatch',
      hint: '10列目の指定は ' + d.map(function (x) { return indexToCircled(x); }).join('') +
            ' ですが、解説文では ' + e.map(function (x) { return indexToCircled(x); }).join('') + ' が正解と記述されています' +
            (contradicted.length ? '（指定肢は解説で「誤り」と明記）' : '')
    };
  }

  /* ---- 4-13. 階層コード [1-1-A-a] の生成 */
  function leadingNumber(text) {
    var m = String(text == null ? '' : text).match(/^\s*(\d+)/);
    return m ? m[1] : null;
  }
  function leadingUpper(text) {
    var m = String(text == null ? '' : text).match(/^\s*([A-Za-z])/);
    return m ? m[1].toUpperCase() : null;
  }
  function leadingLower(text) {
    var m = String(text == null ? '' : text).match(/^\s*([A-Za-z])/);
    return m ? m[1].toLowerCase() : null;
  }
  function buildNumCode(unitNo, major, medium, sub) {
    return '[' + (unitNo || '?') + '-' +
           (leadingNumber(major) || '?') + '-' +
           (leadingUpper(medium) || '?') + '-' +
           (leadingLower(sub) || '?') + ']';
  }

  /* ---- 4-14. 選択肢テキストの正規化（先頭の丸数字を落として本文だけ残す） */
  function stripLeadingCircle(text) {
    return String(text == null ? '' : text).replace(/^\s*[①-⑳]\s*/, '').trim();
  }

  /* ---- 4-15. 1行 → 固定スキーマのオブジェクトへ変換 ---- */
  var QTYPE_ALIAS = {
    'single': 'single', 'multiple': 'multiple', 'numeric': 'numeric',
    'multi': 'multiple', 'calc': 'numeric', 'number': 'numeric',
    '単一': 'single', '単一選択': 'single', '複数': 'multiple', '複数選択': 'multiple',
    '計算': 'numeric', '数値': 'numeric'
  };

  /* 13列目に書ける値。書き忘れ（空欄）は必ず「分割しない」へ落ちる。 */
  var SPLIT_YES = ['split', '1', 'true', 'yes', 'y', 'o', '可', '○', '〇'];
  var SPLIT_NO  = ['', '0', 'false', 'no', 'n', 'x', '不可', '×'];

  function buildQuestionFromRow(cells, ctx) {
    var warnings = [];

    if (!cells || cells.length < 12) {
      return { ok: false, error: '列数が ' + (cells ? cells.length : 0) + ' しかありません（12列必要）' };
    }

    var unit    = csvUnquote(cells[0]).trim();
    var target  = csvUnquote(cells[1]).trim();
    var rank    = csvUnquote(cells[2]).trim().toUpperCase();
    var major   = csvUnquote(cells[3]).trim();
    var medium  = csvUnquote(cells[4]).trim();
    var subItem = csvUnquote(cells[5]).trim();
    var qtypeIn = csvUnquote(cells[6]).trim().toLowerCase();
    var stemRaw = csvUnquote(cells[7]);
    var optsRaw = cells[8];
    var ansRaw  = cells[9];
    var expRaw  = csvUnquote(cells[10]);
    var tagsRaw = cells[11];

    /* --- 13列目：分割可否（V1.23で追加） ---
       「この問題を1肢ずつの一問一答に切り出してよいか」。
       空欄は「不可」に倒す。誤りの向きが非対称なため：
         分割不可を分割 → 「最も近いのはどれか」型が1肢になり問題が壊れる（致命）
         分割可を4択で出す → 何も壊れない（従来どおり）
       書き忘れは必ず安全側へ落ちる。
       13列目はもともと「出典」を受ける将来拡張枠だったが、作問プロンプトは
       12列しか出さず、同梱データにも出典は1件も入っていなかった（実測）。
       ここを分割可否に使い、出典と画像は14・15へ1つずつ後ろへ送る。 */
    var splitRaw = (cells.length > 12) ? csvUnquote(cells[12]).trim().toLowerCase() : '';
    var isSplittable = SPLIT_YES.indexOf(splitRaw) >= 0;
    if (splitRaw && !isSplittable && SPLIT_NO.indexOf(splitRaw) < 0) {
      warnings.push('13列目の "' + splitRaw + '" は分割可否として読めないため「分割しない」として扱いました');
    }

    var source   = (cells.length > 13 && csvUnquote(cells[13]).trim()) ? csvUnquote(cells[13]).trim() : null;
    var imageCol = (cells.length > 14 && csvUnquote(cells[14]).trim()) ? csvUnquote(cells[14]).trim() : null;

    if (!unit)    { return { ok: false, error: '1列目（単元）が空です' }; }
    if (!stemRaw) { return { ok: false, error: '8列目（問題文）が空です' }; }

    if (['S', 'A', 'B', 'C'].indexOf(rank) < 0) {
      warnings.push('3列目のランク "' + rank + '" は S/A/B/C ではないため B として扱いました');
      rank = 'B';
    }

    var qtype = QTYPE_ALIAS[qtypeIn] || null;
    if (!qtype) {
      warnings.push('7列目の形式 "' + qtypeIn + '" が不明のため single として扱いました');
      qtype = 'single';
    }

    /* --- 問題文と画像パス --- */
    var img = extractImage(stemRaw);
    var stem = img.stem;
    var imageUrl = imageCol || img.image_url || null;

    /* --- 解説：比較表 → 図解 の順に切り離す --- */
    var t1 = extractTables(expRaw);
    var t2 = extractMermaid(t1.rest);
    var body = t2.rest.replace(/(?:<br\s*\/?>\s*){3,}/gi, '<br><br>').trim();
    var comparisonTable = t1.table || null;
    var mermaidCode = t2.mermaid || null;

    /* --- 選択肢 --- */
    var options = [];
    if (qtype !== 'numeric') {
      var optRes = sanitizeJsonCell(optsRaw);
      if (Array.isArray(optRes.value)) {
        options = optRes.value.map(function (o) { return String(o); });
      } else {
        var flat = csvUnquote(optsRaw);
        if (flat) {
          options = flat.split(/\s*\|\s*|\r?\n/).filter(function (o) { return o.trim() !== ''; });
          if (options.length > 1) {
            warnings.push('9列目がJSON配列として読めなかったため、区切り文字で分割しました');
          }
        }
      }
      if (options.length < 2) {
        return { ok: false, error: '9列目（選択肢）が2件以上のJSON配列として読めません' };
      }
      if (optRes.method === 'strict' || optRes.method === 'failed') {
        warnings.push('9列目のJSONにエスケープの乱れがあったため正規化しました');
      }
    }

    /* --- 正解 --- */
    var ans = parseAnswerCell(ansRaw, qtype, options.length || 1);
    if (ans.error) { return { ok: false, error: ans.error }; }

    /* --- クロスチェック（承認済み：不一致行はスキップ） --- */
    var verify = { status: 'skipped', hint: null };
    if (qtype !== 'numeric') {
      var detected = detectCorrectFromExplanation(body);
      verify = crossCheckAnswer(ans.indices, detected, options.length);
      if (verify.status === 'mismatch') {
        return { ok: false, error: verify.hint, mismatch: true };
      }
      if (verify.status === 'unverified') { warnings.push(verify.hint); }
    }

    /* --- 階層コード ＆ ID --- */
    var unitNo = ctx.unitIndexMap[unit];
    if (!unitNo) {
      unitNo = ctx.nextUnitNo++;
      ctx.unitIndexMap[unit] = unitNo;
    }
    var numCode = buildNumCode(unitNo, major, medium, subItem);
    var idSeed = unit + '|' + major + '|' + medium + '|' + subItem + '|' + stem;
    var qId = 'ORIG_' + (leadingNumber(major) || '0') + '_' +
              (leadingUpper(medium) || 'X') + '_' + hash6(idSeed);

    /* --- アトム生成 --- */
    var atoms = [];
    var i;

    if (qtype === 'numeric') {
      /* 計算問題の例外パース：入力数値と解説から単一の計算アトムを自動生成する */
      var numTagRes = sanitizeTagCell(tagsRaw, 1);
      atoms.push({
        atom_id      : qId + '_1',
        original_num : 1,
        is_correct   : true,
        text         : String(ans.numeric),
        statement    : stripHtml(stem) || String(ans.numeric),
        explanation  : body || '',
        is_starred   : false,
        tags         : numTagRes.tags[0] || []
      });
      if (numTagRes.method === 'fallback' || numTagRes.method === 'flat') {
        warnings.push('12列目のタグJSONが壊れていたため、タグを直接抽出して復元しました');
      }
    } else {
      var tagRes = sanitizeTagCell(tagsRaw, options.length);
      if (tagRes.method === 'fallback' || tagRes.method === 'flat') {
        warnings.push('12列目のタグJSONが壊れていたため、タグを直接抽出して復元しました');
      } else if (tagRes.method === 'none') {
        warnings.push('12列目からタグを1件も読み取れませんでした（概念アナライザーの対象外になります）');
      } else if (tagRes.method === 'strict') {
        warnings.push('12列目のタグJSONに二重エスケープがあったため正規化しました');
      }

      var split = splitAtomExplanations(body, options.length);
      if (split.matched === 0) {
        warnings.push('11列目を ①②③④ で分解できなかったため、各選択肢の解説は空になります');
      }

      for (i = 0; i < options.length; i++) {
        var textBody = stripLeadingCircle(options[i]);
        var stmt = stripHtml(split.byIndex[i]).replace(/^[①-⑳]\s*(正解|誤り|正しい|正しくない)\s*[：:]\s*/, '');
        atoms.push({
          atom_id      : qId + '_' + (i + 1),
          original_num : i + 1,
          is_correct   : ans.indices.indexOf(i) >= 0,
          text         : textBody,
          /* statement 未設定時は選択肢本文で自動補填する（仕様2項） */
          statement    : stmt || textBody,
          explanation  : split.byIndex[i] || '',
          is_starred   : false,
          tags         : tagRes.tags[i] || []
        });
      }
    }

    var question = {
      q_id               : qId,
      unit               : unit,
      target             : target || null,
      rank               : rank,
      major              : major,
      medium             : medium,
      sub_item           : subItem,
      source             : source,
      question_type      : qtype,
      select_count       : (qtype === 'multiple') ? ans.indices.length : 1,
      image_url          : imageUrl,
      stem               : stem,
      numeric_answer     : (qtype === 'numeric') ? ans.numeric : null,
      overall_explanation: body || '',
      comparison_table   : comparisonTable,
      mermaid_code       : mermaidCode,
      is_starred         : false,
      /* 自作の図解画像（V1.27）。実体は user_files にあり、ここは参照だけ。 */
      user_image_id      : null,
      user_image_updated_at: null,
      /* ドライブ上の図のID（V1.31）。同期していなければ null。 */
      drive_image_id     : null,
      /* 13列目。一問一答へ切り出してよいか。既定は false（安全側）。 */
      is_splittable      : isSplittable,
      user_memo          : null,      /* 利用者が上書きした解説（Markdown-lite） */
      memo_updated_at    : null,
      num_code           : numCode,
      unit_no            : unitNo,
      atom_count         : atoms.length,
      verify_status      : verify.status,
      created_at         : nowMs(),
      updated_at         : nowMs()
    };

    return { ok: true, question: question, atoms: atoms, warnings: warnings };
  }

  /* ======================================================================
   * 5. インポート
   * ====================================================================== */

  /* アトムを IndexedDB レコードへ展開する（進捗フィールドを初期化して付与） */
  function toAtomRecord(atom, q, prev) {
    var rec = {
      atom_id        : atom.atom_id,
      q_id           : q.q_id,
      original_num   : atom.original_num,
      is_correct     : !!atom.is_correct,
      text           : atom.text,
      statement      : atom.statement,
      explanation    : atom.explanation,
      tags           : Array.isArray(atom.tags) ? atom.tags : [],
      is_starred     : false,
      _star          : 0,
      user_memo      : null,   /* 利用者が書き換えた選択肢解説（Markdown-lite） */
      memo_updated_at: null,

      /* --- 進捗（再インポート時は既存値を必ず引き継ぐ） --- */
      srs_step       : 0,
      interval_code  : null,
      due_date       : null,
      last_eval      : null,
      last_answered_at: null,
      answer_count   : 0,
      correct_count  : 0,
      hard_streak    : 0,
      weakness_pt    : 0,
      _unlearned     : 1,

      /* --- 出題フィルタ用の非正規化メタ --- */
      unit           : q.unit,
      major          : q.major,
      medium         : q.medium,
      sub_item       : q.sub_item,
      rank           : q.rank,
      num_code       : q.num_code,
      updated_at     : nowMs()
    };

    if (prev) {
      rec.is_starred       = !!prev.is_starred;
      rec._star            = prev.is_starred ? 1 : 0;
      /* 書き換えた解説は、再インポートで絶対に失わせない。
         この2行の追加漏れが、気づかれないままメモ全消失を招く。 */
      rec.user_memo        = (prev.user_memo !== undefined) ? prev.user_memo : null;
      rec.memo_updated_at  = (prev.memo_updated_at !== undefined) ? prev.memo_updated_at : null;
      rec.srs_step         = prev.srs_step || 0;
      rec.interval_code    = prev.interval_code || null;
      rec.due_date         = isNum(prev.due_date) ? prev.due_date : null;
      rec.last_eval        = prev.last_eval || null;
      rec.last_answered_at = isNum(prev.last_answered_at) ? prev.last_answered_at : null;
      rec.answer_count     = prev.answer_count || 0;
      rec.correct_count    = prev.correct_count || 0;
      rec.hard_streak      = prev.hard_streak || 0;
      rec.weakness_pt      = prev.weakness_pt || 0;
      rec._unlearned       = rec.answer_count > 0 ? 0 : 1;
    }
    return rec;
  }

  function looksLikeHeaderRow(cells) {
    if (!cells || cells.length < 7) { return false; }
    var c7 = csvUnquote(cells[6]).trim().toLowerCase();
    if (QTYPE_ALIAS[c7]) { return false; }
    var joined = cells.slice(0, 8).map(csvUnquote).join('');
    return /単元|問題文|選択肢|正解|解説|ランク|大項目|中項目|小項目|形式/.test(joined);
  }

  /* ここで trim() を使ってはいけない（V1.01で撤去）。
     末尾の空白を削る動作が、TSVの「空の最終列」を区切りタブごと消してしまう。
     落とすのは前後の改行だけ。タブと半角スペースは1文字も触らない。 */
  function importText(text, options) {
    options = options || {};
    var raw = String(text == null ? '' : text)
      .replace(/^\uFEFF/, '')
      .replace(/^[\r\n]+/, '')
      .replace(/[\r\n]+$/, '');
    if (!/\S/.test(raw)) {
      return Promise.reject(new Error('取り込むデータが空です。12列のTSVかJSONを貼り付けてください。'));
    }
    /* JSONかTSVかの判定にだけ、先頭の空白を飛ばした写しを使う。
       判定用と解析用を分けておけば、判定の都合でデータを削らずに済む。 */
    var sniff = raw.replace(/^[\s\uFEFF]+/, '');

    return ensureInitialized().then(function () {
      if (sniff.charAt(0) === '[' || sniff.charAt(0) === '{') {
        return importJsonPayload(sniff, options);
      }
      return importTsvPayload(raw, options);
    });
  }

  function importTsvPayload(raw, options) {
    return loadMeta().then(function (meta) {
      var lines = raw.split(/\r\n|\r|\n/);
      var unitMap = {}, k;
      var stored = meta.unit_index_map || {};
      var maxNo = 0;
      for (k in stored) {
        if (Object.prototype.hasOwnProperty.call(stored, k)) {
          unitMap[k] = stored[k];
          if (stored[k] > maxNo) { maxNo = stored[k]; }
        }
      }
      var ctx = { unitIndexMap: unitMap, nextUnitNo: maxNo + 1 };

      var report = {
        ok: true, source: 'tsv', started_at: nowMs(),
        total_lines: 0, parsed: 0, imported: 0, updated: 0,
        skipped: 0, mismatch: 0, atoms: 0, unverified: 0,
        errors: [], warnings: [], messages: []
      };

      var payload = [];
      var i, line, cells, built;

      for (i = 0; i < lines.length; i++) {
        line = lines[i];
        if (!line || !line.trim()) { continue; }
        report.total_lines++;
        cells = splitTsvRow(line);

        if (i === 0 && looksLikeHeaderRow(cells)) {
          report.messages.push('1行目をヘッダー行と判定して読み飛ばしました');
          continue;
        }

        built = buildQuestionFromRow(cells, ctx);

        if (!built.ok) {
          report.skipped++;
          if (built.mismatch) {
            report.mismatch++;
            /* 承認済みの文言でレポートする */
            report.errors.push({
              line: i + 1,
              type: 'mismatch',
              message: (i + 1) + '行目で正解判定の不一致を検出しスキップしました（' + built.error + '）'
            });
          } else {
            report.errors.push({
              line: i + 1,
              type: 'parse',
              message: (i + 1) + '行目を取り込めませんでした：' + built.error
            });
          }
          continue;
        }

        report.parsed++;
        if (built.question.verify_status === 'unverified') { report.unverified++; }
        (built.warnings || []).forEach(function (w) {
          report.warnings.push({ line: i + 1, message: (i + 1) + '行目：' + w });
        });
        payload.push(built);
      }

      if (!payload.length) {
        report.ok = false;
        report.finished_at = nowMs();
        return setMetaBulk({
          unit_index_map: ctx.unitIndexMap,
          last_import_at: nowMs(),
          last_import_report: report
        }).then(function () { return report; });
      }

      return persistImportPayload(payload, report, ctx, options);
    });
  }

  function importJsonPayload(raw, options) {
    return loadMeta().then(function (meta) {
      var data = safeParseJson(raw, null);
      if (!data) { throw new Error('JSONとして読み取れませんでした。書き出したバックアップファイルをそのまま貼り付けてください。'); }

      /* バックアップファイルが渡された場合はそちらの経路へ回す */
      if (data && data.stores && data.schema_version) {
        return restoreBackup(data, options.restoreMode || 'merge');
      }

      var list = Array.isArray(data) ? data : (Array.isArray(data.questions) ? data.questions : [data]);
      var unitMap = {}, k, maxNo = 0;
      var stored = meta.unit_index_map || {};
      for (k in stored) {
        if (Object.prototype.hasOwnProperty.call(stored, k)) {
          unitMap[k] = stored[k];
          if (stored[k] > maxNo) { maxNo = stored[k]; }
        }
      }
      var ctx = { unitIndexMap: unitMap, nextUnitNo: maxNo + 1 };

      var report = {
        ok: true, source: 'json', started_at: nowMs(),
        total_lines: list.length, parsed: 0, imported: 0, updated: 0,
        skipped: 0, mismatch: 0, atoms: 0, unverified: 0,
        errors: [], warnings: [], messages: []
      };

      var payload = [];
      list.forEach(function (q, idx) {
        if (!q || !q.stem || !Array.isArray(q.atoms) || !q.atoms.length) {
          report.skipped++;
          report.errors.push({
            line: idx + 1, type: 'parse',
            message: (idx + 1) + '件目を取り込めませんでした：stem または atoms がありません'
          });
          return;
        }
        var unitNo = ctx.unitIndexMap[q.unit];
        if (!unitNo) { unitNo = ctx.nextUnitNo++; ctx.unitIndexMap[q.unit] = unitNo; }

        var qq = {};
        Object.keys(q).forEach(function (key) { if (key !== 'atoms') { qq[key] = q[key]; } });
        qq.q_id        = q.q_id || ('ORIG_' + (leadingNumber(q.major) || '0') + '_' +
                                    (leadingUpper(q.medium) || 'X') + '_' +
                                    hash6([q.unit, q.major, q.medium, q.sub_item, q.stem].join('|')));
        qq.num_code    = q.num_code || buildNumCode(unitNo, q.major, q.medium, q.sub_item);
        qq.unit_no     = unitNo;
        qq.rank        = (q.rank || 'B').toUpperCase();
        qq.question_type = QTYPE_ALIAS[String(q.question_type || 'single').toLowerCase()] || 'single';
        qq.is_starred  = !!q.is_starred;
        qq.atom_count  = q.atoms.length;
        qq.verify_status = q.verify_status || 'json';
        qq.created_at  = q.created_at || nowMs();
        qq.updated_at  = nowMs();

        var atoms = q.atoms.map(function (a, ai) {
          return {
            atom_id      : a.atom_id || (qq.q_id + '_' + (ai + 1)),
            original_num : isNum(a.original_num) ? a.original_num : (ai + 1),
            is_correct   : !!a.is_correct,
            text         : stripLeadingCircle(a.text || ''),
            statement    : (a.statement && String(a.statement).trim()) || stripLeadingCircle(a.text || ''),
            explanation  : a.explanation || '',
            is_starred   : !!a.is_starred,
            tags         : Array.isArray(a.tags) ? a.tags : []
          };
        });

        report.parsed++;
        payload.push({ ok: true, question: qq, atoms: atoms, warnings: [] });
      });

      if (!payload.length) {
        report.ok = false;
        report.finished_at = nowMs();
        return report;
      }
      return persistImportPayload(payload, report, ctx, options);
    });
  }

  /* パースが通った分だけを 200件ずつのトランザクションで書き込む。
     1件ごとに既存レコードを読んでから put するため、
     再インポートでも学習進捗と★は失われない（追加ではなく更新）。 */
  function persistImportPayload(payload, report, ctx, options) {
    var CHUNK = 200;
    var chunks = [];
    var i;
    for (i = 0; i < payload.length; i += CHUNK) {
      chunks.push(payload.slice(i, i + CHUNK));
    }

    var seq = Promise.resolve();
    chunks.forEach(function (chunk) {
      seq = seq.then(function () {
        return write([STORE.QUESTIONS, STORE.ATOMS], function (s) {
          var jobs = chunk.map(function (item) {
            var q = item.question;
            return req2promise(s[STORE.QUESTIONS].get(q.q_id)).then(function (prevQ) {
              if (prevQ) {
                report.updated++;
                q.created_at = prevQ.created_at || q.created_at;
                q.is_starred = !!prevQ.is_starred;
                /* 利用者が書いたメモは、再インポートで絶対に失わせない。
                   ここへの追加漏れが、気づかれないままメモ全消失を招く。 */
                if (prevQ.user_memo !== undefined) { q.user_memo = prevQ.user_memo; }
                if (prevQ.memo_updated_at !== undefined) { q.memo_updated_at = prevQ.memo_updated_at; }
                /* 自作の図解画像は再インポートで絶対に失わせない。
                   画像そのものは user_files にあるが、questions 側の
                   id を引き継がないと、画面から二度とたどり着けなくなる。 */
                if (prevQ.user_image_id !== undefined) { q.user_image_id = prevQ.user_image_id; }
                if (prevQ.user_image_updated_at !== undefined) {
                  q.user_image_updated_at = prevQ.user_image_updated_at;
                }
                /* ドライブ上の図のID（V1.31）。引き継がないと、取り込み直すたびに
                   同じ図をもう一度アップロードして二重に増える。 */
                if (prevQ.drive_image_id !== undefined) { q.drive_image_id = prevQ.drive_image_id; }
                /* is_splittable は引き継がない。13列目に書いた値がそのまま正で、
                   作問側で直したものが取り込みで反映されないと直せなくなる。
                   ここは「利用者が画面で作った値」ではなくデータそのもの。 */
              } else {
                report.imported++;
              }
              q._star = q.is_starred ? 1 : 0;
              s[STORE.QUESTIONS].put(q);

              var atomJobs = item.atoms.map(function (a) {
                return req2promise(s[STORE.ATOMS].get(a.atom_id)).then(function (prevA) {
                  var rec = toAtomRecord(a, q, prevA);
                  s[STORE.ATOMS].put(rec);
                  report.atoms++;
                });
              });
              return Promise.all(atomJobs);
            });
          });
          return Promise.all(jobs);
        });
      });
    });

    return seq.then(function () {
      report.finished_at = nowMs();
      report.duration_ms = report.finished_at - report.started_at;
      return getMeta('total_imported_rows', 0);
    }).then(function (prevTotal) {
      return setMetaBulk({
        unit_index_map      : ctx.unitIndexMap,
        last_import_at      : nowMs(),
        last_import_report  : report,
        total_imported_rows : (prevTotal || 0) + report.parsed
      });
    }).then(function () {
      return refreshConceptCatalog();
    }).then(function () {
      return report;
    });
  }

  /* ======================================================================
   * 6. 問題・アトムの読み出し
   * ====================================================================== */

  /* メモを1件でも持っているか。持っていれば、再インポート前に自動退避する。 */
  function countMemos() {
    return Promise.all([getAllQuestions(), getAllAtoms()]).then(function (r) {
      var has = function (x) { return x.user_memo && String(x.user_memo).trim(); };
      return r[0].filter(has).length + r[1].filter(has).length;
    });
  }

  /* 解説の書き換えを保存する。kind は 'atom'（選択肢）か 'question'（全体）。
     空文字を渡すと書き換えを取り消し、元の解説へ戻す。 */
  function setMemo(kind, id, text) {
    var body = (text == null) ? '' : String(text).trim();
    var patch = { user_memo: body || null, memo_updated_at: body ? nowMs() : null };
    return (kind === 'question') ? updateQuestion(id, patch) : updateAtom(id, patch);
  }

  function getQuestion(qId) { return getOne(STORE.QUESTIONS, qId); }
  function getAllQuestions() { return getAll(STORE.QUESTIONS); }
  function countQuestions() { return countStore(STORE.QUESTIONS); }
  function getAtom(atomId) { return getOne(STORE.ATOMS, atomId); }
  function getAllAtoms() { return getAll(STORE.ATOMS); }
  function countAtoms() { return countStore(STORE.ATOMS); }

  function getAtomsByQuestion(qId) {
    return getAll(STORE.ATOMS, 'q_id', IDBKeyRange.only(qId)).then(function (list) {
      return list.sort(function (a, b) { return a.original_num - b.original_num; });
    });
  }

  function getAtomsByTag(tag) {
    return getAll(STORE.ATOMS, 'tags', IDBKeyRange.only(tag));
  }

  function getQuestionsByScope(field, value) {
    if (!field || value == null) { return getAllQuestions(); }
    return getAll(STORE.QUESTIONS, field, IDBKeyRange.only(value));
  }

  function getAtomsByScope(field, value) {
    if (!field || value == null) { return getAllAtoms(); }
    return getAll(STORE.ATOMS, field, IDBKeyRange.only(value));
  }

  /* 問題本体とアトムを1つに組み立てて返す（画面描画用） */
  function getQuestionFull(qId) {
    return Promise.all([getQuestion(qId), getAtomsByQuestion(qId)]).then(function (r) {
      if (!r[0]) { return null; }
      var q = {};
      Object.keys(r[0]).forEach(function (k) { q[k] = r[0][k]; });
      q.atoms = r[1];
      return q;
    });
  }

  function getQuestionsFull(qIds) {
    return Promise.all(qIds.map(getQuestionFull)).then(function (list) {
      return list.filter(Boolean);
    });
  }

  /* --- 復習期日を迎えたアトム（due_date 昇順 = 緊急度昇順） --- */
  function getDueAtoms(now, limit) {
    var cutoff = isNum(now) ? now : nowMs();
    return getAll(STORE.ATOMS, 'due_date', IDBKeyRange.upperBound(cutoff), limit).then(function (list) {
      return list.sort(function (a, b) { return (a.due_date || 0) - (b.due_date || 0); });
    });
  }

  function getDueCount(now) {
    var cutoff = isNum(now) ? now : nowMs();
    return countStore(STORE.ATOMS, 'due_date', IDBKeyRange.upperBound(cutoff));
  }

  /* --- 未学習（一度も解答していない）アトム --- */
  function getUnlearnedAtoms(limit) {
    return getAll(STORE.ATOMS, '_unlearned', IDBKeyRange.only(1), limit);
  }

  /* --- 既存データへの分割可否の後付け（V1.24） ---
     13列目は V1.23 で入れたので、それ以前に取り込んだ問題には値が無い。
     値が無い＝分割不可なので、そのままだと一問一答が一度も出てこない。
     ここで問題文から機械的に判定する。判定は必ず「安全側に外す」向きで、
     少しでも比較や反転が疑われる言い回しがあれば対象から外す。
     取り込み直せば13列目の値が必ず勝つ（この判定は上書きされる）。 */
  var SPLIT_NG_WORDS = [
    '最も', 'もっとも', '誤っている', '誤りはどれ', '間違っている',
    '正しくないのは', '適切でないのは', '不適切', 'ではないのはどれ',
    '当てはまらない', 'あてはまらない', '除くのはどれ', '該当しないのは'
  ];

  function judgeSplittable(q) {
    if (!q || q.question_type !== 'single') { return false; }
    var stem = String(q.stem || '');
    var i;
    for (i = 0; i < SPLIT_NG_WORDS.length; i++) {
      if (stem.indexOf(SPLIT_NG_WORDS[i]) >= 0) { return false; }
    }
    return true;
  }

  /* dryRun:true なら数えるだけで書き込まない（押す前に件数を見せるため） */
  function autoMarkSplittable(options) {
    options = options || {};
    var dry = !!options.dryRun;
    return getAllQuestions().then(function (qs) {
      var hit = [], miss = 0;
      qs.forEach(function (q) {
        if (judgeSplittable(q)) { hit.push(q); } else { miss++; }
      });
      var result = { total: qs.length, marked: hit.length, skipped: miss, dry_run: dry };
      if (dry || !hit.length) { return result; }
      return write([STORE.QUESTIONS], function (s) {
        hit.forEach(function (q) {
          q.is_splittable = true;
          q._star = q.is_starred ? 1 : 0;
          s[STORE.QUESTIONS].put(q);
        });
      }).then(function () { return result; });
    });
  }

  function clearSplittable() {
    return getAllQuestions().then(function (qs) {
      var hit = qs.filter(function (q) { return q.is_splittable; });
      if (!hit.length) { return { cleared: 0 }; }
      return write([STORE.QUESTIONS], function (s) {
        hit.forEach(function (q) {
          q.is_splittable = false;
          q._star = q.is_starred ? 1 : 0;
          s[STORE.QUESTIONS].put(q);
        });
      }).then(function () { return { cleared: hit.length }; });
    });
  }

  /* ======================================================================
   * 自作の図解画像（V1.27）
   *
   * ・1問につき1枚。file_id は 'img_' + q_id で決まるので、入れ直すと上書き。
   * ・長辺1200pxへ縮小し、JPEG品質0.72で保存する。
   *   元のままだと1枚2〜5MBになり、バックアップJSONが実用にならない
   *   （50枚で100MB超）。1200px・0.72なら図表1枚あたり150〜250KBに収まる。
   * ・保存前に「縮小後のサイズ」を返す。利用者が実際の重さを見られるようにする。
   * ====================================================================== */

  var USER_IMG_MAX_EDGE = 1200;
  var USER_IMG_QUALITY  = 0.72;
  var USER_IMG_MAX_BYTES = 2 * 1024 * 1024;   /* 縮小後がこれを超えたら断る */

  function imageIdFor(qId) { return 'img_' + qId; }

  /* Blob → 縮小済み Blob。canvas が使えない環境ではそのまま返す。 */
  function shrinkImage(blob) {
    if (!global.document || !global.createImageBitmap) { return Promise.resolve({ blob: blob, w: 0, h: 0 }); }
    return global.createImageBitmap(blob).then(function (bmp) {
      var scale = Math.min(1, USER_IMG_MAX_EDGE / Math.max(bmp.width, bmp.height));
      var w = Math.max(1, Math.round(bmp.width * scale));
      var h = Math.max(1, Math.round(bmp.height * scale));
      var cv = global.document.createElement('canvas');
      cv.width = w; cv.height = h;
      var ctx = cv.getContext('2d');
      /* 透過PNGをJPEGにすると黒く抜けるので、白で塗ってから描く。 */
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, w, h);
      ctx.drawImage(bmp, 0, 0, w, h);
      if (bmp.close) { bmp.close(); }
      return new Promise(function (resolve) {
        cv.toBlob(function (out) {
          resolve({ blob: out || blob, w: w, h: h });
        }, 'image/jpeg', USER_IMG_QUALITY);
      });
    }).catch(function () { return { blob: blob, w: 0, h: 0 }; });
  }

  /* opts.skipShrink：すでに縮小済みのものを入れ直すとき（ドライブからの取り込み）に使う。
     JPEGは開いて保存し直すたびに劣化する。同期のたびに再圧縮すると、
     何度か往復しただけで図の細い線が読めなくなるので、取り込みでは触らない。 */
  function putUserImage(qId, fileBlob, opts) {
    if (!qId || !fileBlob) { return Promise.reject(new Error('画像が選ばれていません')); }
    var prep = (opts && opts.skipShrink)
      ? Promise.resolve({ blob: fileBlob, w: (opts.w || 0), h: (opts.h || 0) })
      : shrinkImage(fileBlob);
    return prep.then(function (r) {
      if (r.blob.size > USER_IMG_MAX_BYTES) {
        throw new Error('縮小しても ' + Math.round(r.blob.size / 1024) +
                        'KB あり、上限の2MBを超えています。もっと小さい画像を選んでください。');
      }
      var rec = {
        file_id: imageIdFor(qId), kind: 'image', q_id: qId,
        blob: r.blob, mime: r.blob.type || 'image/jpeg',
        bytes: r.blob.size, w: r.w, h: r.h, updated_at: nowMs()
      };
      return write([STORE.FILES, STORE.QUESTIONS], function (s) {
        s[STORE.FILES].put(rec);
        return req2promise(s[STORE.QUESTIONS].get(qId)).then(function (q) {
          if (!q) { return; }
          q.user_image_id = rec.file_id;
          q.user_image_updated_at = rec.updated_at;
          s[STORE.QUESTIONS].put(q);
        });
      }).then(function () { return rec; });
    });
  }

  function getUserImage(qId) {
    if (!qId) { return Promise.resolve(null); }
    return getOne(STORE.FILES, imageIdFor(qId));
  }

  function deleteUserImage(qId) {
    if (!qId) { return Promise.resolve(false); }
    return write([STORE.FILES, STORE.QUESTIONS], function (s) {
      s[STORE.FILES]['delete'](imageIdFor(qId));
      return req2promise(s[STORE.QUESTIONS].get(qId)).then(function (q) {
        if (!q) { return; }
        q.user_image_id = null;
        q.user_image_updated_at = null;
        s[STORE.QUESTIONS].put(q);
      });
    }).then(function () { return true; });
  }

  /* --- 自作のアラーム音（V1.28） ---
     画像と同じ user_files に kind:'audio' で置く。ストアを分けない理由は、
     バックアップ・復元・全消去の3経路に足す対象を1つに保つため。
     縮小はしない（音は再エンコードすると質が落ちるうえ、
     ブラウザだけで安全に変換する手段が無い）。代わりに上限を1MBにする。
     25分に1回・数秒鳴らすだけなので、1MBあれば足りる。 */
  var ALARM_FILE_ID   = 'alarm_custom';
  var ALARM_MAX_BYTES = 1024 * 1024;

  function putUserAudio(fileBlob) {
    if (!fileBlob) { return Promise.reject(new Error('音のファイルが選ばれていません')); }
    if (fileBlob.size > ALARM_MAX_BYTES) {
      return Promise.reject(new Error(
        Math.round(fileBlob.size / 1024) + 'KB あり、上限の1MBを超えています。' +
        '短い音（5秒程度）を選んでください。'));
    }
    var rec = {
      file_id: ALARM_FILE_ID, kind: 'audio', q_id: null,
      blob: fileBlob, mime: fileBlob.type || 'audio/mpeg',
      bytes: fileBlob.size, w: 0, h: 0, updated_at: nowMs()
    };
    return write([STORE.FILES], function (s) { s[STORE.FILES].put(rec); })
      .then(function () { return rec; });
  }

  function getUserAudio() { return getOne(STORE.FILES, ALARM_FILE_ID); }

  function deleteUserAudio() {
    return write([STORE.FILES], function (s) { s[STORE.FILES]['delete'](ALARM_FILE_ID); })
      .then(function () { return true; });
  }

  /* 問題レコードだけを書き戻す（アトムには触らない）。
     ドライブ同期が q.drive_image_id を更新するために使う。
     _star は索引用の派生値なので、put のたびに必ず作り直す。 */
  function putQuestionShallow(q) {
    if (!q || !q.q_id) { return Promise.reject(new Error('問題が指定されていません')); }
    q._star = q.is_starred ? 1 : 0;
    q.updated_at = nowMs();
    return write([STORE.QUESTIONS], function (s) { s[STORE.QUESTIONS].put(q); })
      .then(function () { return q; });
  }

  function getAllUserFiles() { return getAll(STORE.FILES); }
  function countUserFiles() { return countStore(STORE.FILES); }

  function countUnlearned() {
    return countStore(STORE.ATOMS, '_unlearned', IDBKeyRange.only(1));
  }

  /* 3階層ツリーの未学習バッジ用：スコープごとの未学習アトム数を一括集計する */
  function countUnlearnedByScope() {
    return getAll(STORE.ATOMS, '_unlearned', IDBKeyRange.only(1)).then(function (list) {
      var out = { unit: {}, major: {}, medium: {}, sub_item: {}, total: list.length };
      list.forEach(function (a) {
        out.unit[a.unit]         = (out.unit[a.unit] || 0) + 1;
        out.major[a.major]       = (out.major[a.major] || 0) + 1;
        out.medium[a.medium]     = (out.medium[a.medium] || 0) + 1;
        out.sub_item[a.sub_item] = (out.sub_item[a.sub_item] || 0) + 1;
      });
      return out;
    });
  }

  /* 単元 ＞ 大項目 ＞ 中項目 の3階層ツリーを構築して返す */
  function buildTree() {
    return Promise.all([getAllQuestions(), countUnlearnedByScope()]).then(function (r) {
      var questions = r[0], badge = r[1];
      var unitOrder = [], unitMap = {};
      questions.forEach(function (q) {
        if (!unitMap[q.unit]) {
          unitMap[q.unit] = { key: q.unit, label: q.unit, unit_no: q.unit_no || 0,
                              unlearned: badge.unit[q.unit] || 0, count: 0, children: {}, order: [] };
          unitOrder.push(q.unit);
        }
        var u = unitMap[q.unit];
        u.count++;
        if (!u.children[q.major]) {
          u.children[q.major] = { key: q.major, label: q.major,
                                  unlearned: badge.major[q.major] || 0, count: 0, children: {}, order: [] };
          u.order.push(q.major);
        }
        var mj = u.children[q.major];
        mj.count++;
        if (!mj.children[q.medium]) {
          mj.children[q.medium] = { key: q.medium, label: q.medium,
                                    unlearned: badge.medium[q.medium] || 0, count: 0, q_ids: [] };
          mj.order.push(q.medium);
        }
        var md = mj.children[q.medium];
        md.count++;
        md.q_ids.push(q.q_id);
      });

      return unitOrder
        .map(function (uk) { return unitMap[uk]; })
        .sort(function (a, b) { return (a.unit_no || 0) - (b.unit_no || 0); })
        .map(function (u) {
          return {
            key: u.key, label: u.label, count: u.count, unlearned: u.unlearned,
            children: u.order.map(function (mk) {
              var mj = u.children[mk];
              return {
                key: mj.key, label: mj.label, count: mj.count, unlearned: mj.unlearned,
                children: mj.order.map(function (dk) { return mj.children[dk]; })
              };
            })
          };
        });
    });
  }

  /* ======================================================================
   * 7. 進捗の書き込み（scheduler.js から呼ばれる）
   * ====================================================================== */

  /* アトムの進捗フィールドを更新し、同一トランザクションで履歴を1件積む。
     _unlearned ミラーの更新もここで一元管理し、索引のズレを防ぐ。 */
  function commitAnswer(atomId, patch, logEntry) {
    return write([STORE.ATOMS, STORE.PROGRESS], function (s) {
      return req2promise(s[STORE.ATOMS].get(atomId)).then(function (a) {
        if (!a) { throw new Error('選択肢が見つかりません: ' + atomId); }
        Object.keys(patch || {}).forEach(function (k) { a[k] = patch[k]; });
        if (patch && patch.is_starred !== undefined) { a._star = patch.is_starred ? 1 : 0; }
        a._unlearned = (a.answer_count > 0) ? 0 : 1;
        a.updated_at = nowMs();
        s[STORE.ATOMS].put(a);

        if (logEntry) {
          var log = {};
          Object.keys(logEntry).forEach(function (k) { log[k] = logEntry[k]; });
          log.atom_id     = atomId;
          log.q_id        = log.q_id || a.q_id;
          log.answered_at = isNum(log.answered_at) ? log.answered_at : nowMs();
          s[STORE.PROGRESS].add(log);
        }
        return a;
      });
    });
  }

  /* 進捗を書き換えずにフィールドだけ更新する（★の付け外しなど） */
  function updateAtom(atomId, patch) {
    return write([STORE.ATOMS], function (s) {
      return req2promise(s[STORE.ATOMS].get(atomId)).then(function (a) {
        if (!a) { throw new Error('選択肢が見つかりません: ' + atomId); }
        Object.keys(patch || {}).forEach(function (k) { a[k] = patch[k]; });
        if (patch && patch.is_starred !== undefined) { a._star = patch.is_starred ? 1 : 0; }
        a._unlearned = (a.answer_count > 0) ? 0 : 1;
        a.updated_at = nowMs();
        s[STORE.ATOMS].put(a);
        return a;
      });
    });
  }

  function updateQuestion(qId, patch) {
    return write([STORE.QUESTIONS], function (s) {
      return req2promise(s[STORE.QUESTIONS].get(qId)).then(function (q) {
        if (!q) { throw new Error('問題が見つかりません: ' + qId); }
        Object.keys(patch || {}).forEach(function (k) { q[k] = patch[k]; });
        if (patch && patch.is_starred !== undefined) { q._star = patch.is_starred ? 1 : 0; }
        q.updated_at = nowMs();
        s[STORE.QUESTIONS].put(q);
        return q;
      });
    });
  }

  function toggleQuestionStar(qId) {
    return getQuestion(qId).then(function (q) {
      if (!q) { throw new Error('問題が見つかりません: ' + qId); }
      return updateQuestion(qId, { is_starred: !q.is_starred });
    });
  }

  function toggleAtomStar(atomId) {
    return getAtom(atomId).then(function (a) {
      if (!a) { throw new Error('選択肢が見つかりません: ' + atomId); }
      return updateAtom(atomId, { is_starred: !a.is_starred });
    });
  }

  /* マイ★お気に入りノート：問題★とアトム★を単一の統合リストで返す */
  function getStarredNote() {
    return Promise.all([
      getAll(STORE.QUESTIONS, '_star', IDBKeyRange.only(1)),
      getAll(STORE.ATOMS, '_star', IDBKeyRange.only(1))
    ]).then(function (r) {
      var starQ = r[0], starA = r[1];
      var qids = {};
      starQ.forEach(function (q) { qids[q.q_id] = { q_id: q.q_id, kind: 'question', marked_atoms: [] }; });
      starA.forEach(function (a) {
        if (!qids[a.q_id]) { qids[a.q_id] = { q_id: a.q_id, kind: 'atom', marked_atoms: [] }; }
        else if (qids[a.q_id].kind === 'question') { qids[a.q_id].kind = 'both'; }
        qids[a.q_id].marked_atoms.push(a.atom_id);
      });
      var keys = Object.keys(qids);
      return getQuestionsFull(keys).then(function (full) {
        return full.map(function (q) {
          return {
            question     : q,
            kind         : qids[q.q_id].kind,
            marked_atoms : qids[q.q_id].marked_atoms
          };
        });
      });
    });
  }

  /* ======================================================================
   * 8. 履歴（progress_log）
   * ====================================================================== */

  function getLogsByAtom(atomId) {
    return getAll(STORE.PROGRESS, 'atom_id', IDBKeyRange.only(atomId)).then(function (list) {
      return list.sort(function (a, b) { return a.answered_at - b.answered_at; });
    });
  }

  function getLogsSince(sinceTs) {
    return getAll(STORE.PROGRESS, 'answered_at', IDBKeyRange.lowerBound(sinceTs));
  }

  function getAllLogs() { return getAll(STORE.PROGRESS); }
  function countLogs() { return countStore(STORE.PROGRESS); }

  /* 弱点ptの再計算に必要な「アトムごとの全履歴」をまとめて取得する。
     新近性補正（直近が簡単以外なら過去の -5pt を無効化）は累積値では
     表現できないため、scheduler はここから毎回組み立て直す。 */
  function getLogMapByAtoms(atomIds) {
    var want = {};
    atomIds.forEach(function (id) { want[id] = true; });
    return getAllLogs().then(function (logs) {
      var map = {};
      logs.forEach(function (l) {
        if (!want[l.atom_id]) { return; }
        if (!map[l.atom_id]) { map[l.atom_id] = []; }
        map[l.atom_id].push(l);
      });
      Object.keys(map).forEach(function (k) {
        map[k].sort(function (a, b) { return a.answered_at - b.answered_at; });
      });
      return map;
    });
  }

  /* ======================================================================
   * 9. トピックガード（FIFO安全パージ）
   * ====================================================================== */

  function pushGuard(qId, tags) {
    return write([STORE.GUARD], function (s) {
      s[STORE.GUARD].put({
        q_id: qId,
        tags: Array.isArray(tags) ? tags : [],
        answered_at: nowMs()
      });
    });
  }

  /* 直近 windowMs 以内に解答した問題のタグ集合（既定30分） */
  function getGuardTags(windowMs) {
    var w = isNum(windowMs) ? windowMs : 30 * 60 * 1000;
    var since = nowMs() - w;
    return getAll(STORE.GUARD, 'answered_at', IDBKeyRange.lowerBound(since)).then(function (rows) {
      var set = {}, list = [];
      rows.forEach(function (r) {
        (r.tags || []).forEach(function (t) {
          if (!set[t]) { set[t] = 1; list.push(t); }
        });
      });
      return { tags: list, rows: rows.length };
    });
  }

  /* 候補枯渇時のフォールバック：最も古いトピックから順にガードを解除する */
  function purgeOldestGuard(count) {
    var n = isNum(count) && count > 0 ? count : 1;
    return getAll(STORE.GUARD, 'answered_at').then(function (rows) {
      rows.sort(function (a, b) { return a.answered_at - b.answered_at; });
      var victims = rows.slice(0, n);
      if (!victims.length) { return 0; }
      return write([STORE.GUARD], function (s) {
        victims.forEach(function (v) { s[STORE.GUARD].delete(v.q_id); });
      }).then(function () { return victims.length; });
    });
  }

  function clearGuard() {
    return write([STORE.GUARD], function (s) { s[STORE.GUARD].clear(); });
  }

  /* 古すぎるガード記録の定期掃除（既定：2時間より前を削除） */
  function trimGuard(maxAgeMs) {
    var age = isNum(maxAgeMs) ? maxAgeMs : 2 * 60 * 60 * 1000;
    var before = nowMs() - age;
    return getAll(STORE.GUARD, 'answered_at', IDBKeyRange.upperBound(before)).then(function (rows) {
      if (!rows.length) { return 0; }
      return write([STORE.GUARD], function (s) {
        rows.forEach(function (r) { s[STORE.GUARD].delete(r.q_id); });
      }).then(function () { return rows.length; });
    });
  }

  /* ======================================================================
   * 10. 74概念タグ（concept_stat）
   * ====================================================================== */

  function conceptMaster() {
    var m = global.CONCEPT_TAGS_MASTER;
    return Array.isArray(m) ? m : [];
  }

  /* 概念カタログの棚卸し：74タグそれぞれに紐づくアトム数を数え直す。
     score はここでは触らない（評価の平均は scheduler が算出して書き戻す）。 */
  function refreshConceptCatalog() {
    var master = conceptMaster();
    return getAllAtoms().then(function (atoms) {
      var counts = {};
      atoms.forEach(function (a) {
        (a.tags || []).forEach(function (t) { counts[t] = (counts[t] || 0) + 1; });
      });
      return getAll(STORE.CONCEPT).then(function (existing) {
        var prev = {};
        existing.forEach(function (r) { prev[r.tag] = r; });

        var rows = [];
        master.forEach(function (def) {
          var p = prev[def.tag];
          rows.push({
            tag             : def.tag,
            label           : def.label || def.tag.replace(/^#/, ''),
            category        : def.category || null,
            score           : p && p.score !== undefined ? p.score : null,
            evaluated_count : p ? (p.evaluated_count || 0) : 0,
            atom_count      : counts[def.tag] || 0,
            in_master       : true,
            updated_at      : nowMs()
          });
          delete counts[def.tag];
        });
        /* マスターに無いタグもデータ側にあれば記録し、取りこぼしを可視化する */
        Object.keys(counts).forEach(function (t) {
          var p = prev[t];
          rows.push({
            tag             : t,
            label           : t.replace(/^#/, ''),
            category        : null,
            score           : p && p.score !== undefined ? p.score : null,
            evaluated_count : p ? (p.evaluated_count || 0) : 0,
            atom_count      : counts[t],
            in_master       : false,
            updated_at      : nowMs()
          });
        });

        return write([STORE.CONCEPT], function (s) {
          rows.forEach(function (r) { s[STORE.CONCEPT].put(r); });
        }).then(function () { return rows.length; });
      });
    });
  }

  function getConceptStats() { return getAll(STORE.CONCEPT); }

  /* scheduler が算出した理解率を書き戻す。
     全アトム未評価の概念は score=null のまま保持し、未学習と0%を混同させない。 */
  function saveConceptScores(scoreMap) {
    return write([STORE.CONCEPT], function (s) {
      return Promise.all(Object.keys(scoreMap).map(function (tag) {
        return req2promise(s[STORE.CONCEPT].get(tag)).then(function (row) {
          var v = scoreMap[tag];
          var rec = row || {
            tag: tag, label: tag.replace(/^#/, ''), category: null,
            atom_count: 0, in_master: false
          };
          rec.score           = (v && v.score !== undefined) ? v.score : null;
          rec.evaluated_count = (v && v.evaluated_count) || 0;
          if (v && isNum(v.atom_count)) { rec.atom_count = v.atom_count; }
          rec.updated_at = nowMs();
          s[STORE.CONCEPT].put(rec);
        });
      }));
    });
  }

  /* ======================================================================
   * 11. 模試の解禁（永久フラグ ＋ ハイウォーターマーク）
   * ====================================================================== */

  /* 解禁の絶対前提ガード：DB登録問題数が要求問数に届いていなければ、
     成績条件を満たしていても解禁しない（第11章①）。
     一度 true にしたフラグは、この関数からは決して false に戻さない。 */
  function evaluateUnlocks(stats) {
    stats = stats || {};
    var totalQ        = isNum(stats.totalQuestions) ? stats.totalQuestions : 0;
    var uniqueRatio   = isNum(stats.uniqueAnsweredRatio) ? stats.uniqueAnsweredRatio : 0;
    var normalRatio   = isNum(stats.normalPlusRatio) ? stats.normalPlusRatio : 0;
    var passStreak    = isNum(stats.fullMockPassStreak) ? stats.fullMockPassStreak : 0;

    return loadMeta().then(function (meta) {
      var updates = {};
      var results = [];

      MOCK_DEFS.forEach(function (def) {
        var already = !!meta[def.flag];
        var qGate = totalQ >= def.req_q;
        var pctParts = [];
        var conditionMet;

        if (def.id === 'mock_weak') {
          pctParts.push(clamp(passStreak / 2, 0, 1));
          pctParts.push(clamp(totalQ / def.req_q, 0, 1));
          conditionMet = (passStreak >= 2) && qGate;
        } else {
          pctParts.push(clamp(uniqueRatio / def.need_unique, 0, 1));
          pctParts.push(clamp(normalRatio / def.need_normal_plus, 0, 1));
          pctParts.push(clamp(totalQ / def.req_q, 0, 1));
          conditionMet = (uniqueRatio >= def.need_unique) &&
                         (normalRatio >= def.need_normal_plus) && qGate;
        }

        var rawPct = Math.round(Math.min.apply(null, pctParts) * 100);
        var pctKey = 'unlock_pct_' + def.id;
        var storedPct = isNum(meta[pctKey]) ? meta[pctKey] : 0;
        /* 承認済み：進捗率にもハイウォーターマークを適用し、
           TSV追加で母数が増えても表示が後戻りしないようにする */
        var pct = Math.max(storedPct, rawPct);
        var unlocked = already || conditionMet;

        if (unlocked) { pct = 100; }
        if (pct !== storedPct) { updates[pctKey] = pct; }
        if (unlocked && !already) { updates[def.flag] = true; }

        results.push({
          id: def.id, flag: def.flag, label: def.label,
          unlocked: unlocked, newly_unlocked: unlocked && !already,
          pct: pct, raw_pct: rawPct,
          q_gate_met: qGate, required_questions: def.req_q, total_questions: totalQ
        });
      });

      if (!Object.keys(updates).length) { return results; }
      return setMetaBulk(updates).then(function () { return results; });
    });
  }

  function getUnlockState() {
    return loadMeta().then(function (meta) {
      return MOCK_DEFS.map(function (def) {
        return {
          id: def.id, flag: def.flag, label: def.label,
          unlocked: !!meta[def.flag],
          pct: isNum(meta['unlock_pct_' + def.id]) ? meta['unlock_pct_' + def.id] : 0,
          required_questions: def.req_q
        };
      });
    });
  }

  /* フル模試の合否を記録する。2回連続合格でいじわる模試が解禁される。 */
  function recordFullMockResult(passed) {
    return getMeta('full_mock_pass_streak', 0).then(function (streak) {
      var next = passed ? ((streak || 0) + 1) : 0;
      return setMeta('full_mock_pass_streak', next).then(function () { return next; });
    });
  }

  /* 5段階レベルの表示率。display_pct = Math.max(current_pct, max_pct) */
  function applyHighWaterPct(currentPct) {
    var cur = clamp(isNum(currentPct) ? currentPct : 0, 0, 100);
    return getMeta('max_pct', 0).then(function (maxPct) {
      var display = Math.max(isNum(maxPct) ? maxPct : 0, cur);
      if (display === maxPct) { return display; }
      return setMeta('max_pct', display).then(function () { return display; });
    });
  }

  /* 今日の解答数。日界（既定4:00）をまたいだら自動でリセットする。
     カレンダー日付ではなく学習日で数えるため、深夜0時をまたいでも
     同じ「1日」として積み上がる。 */
  function bumpDailyCount(boundaryHour) {
    return loadMeta().then(function (meta) {
      var h = isNum(boundaryHour) ? boundaryHour : (meta.day_boundary_hour || 4);
      var key = dayStart(nowMs(), h);
      var count = (meta.daily_key === key) ? (meta.daily_count || 0) + 1 : 1;
      return setMetaBulk({ daily_key: key, daily_count: count }).then(function () {
        return { daily_key: key, daily_count: count };
      });
    });
  }

  function getDailyCount(boundaryHour) {
    return loadMeta().then(function (meta) {
      var h = isNum(boundaryHour) ? boundaryHour : (meta.day_boundary_hour || 4);
      var key = dayStart(nowMs(), h);
      return (meta.daily_key === key) ? (meta.daily_count || 0) : 0;
    });
  }

  /* --- 分析スキャン精度（全60問モデル・分母ガード付き） --- */
  function recordScanProgress(qId) {
    return Promise.all([getMeta('scan_answered_qids', []), countQuestions()]).then(function (r) {
      var list = Array.isArray(r[0]) ? r[0].slice() : [];
      var totalQ = r[1];
      if (qId && list.indexOf(qId) < 0) { list.push(qId); }
      var denom = Math.min(totalQ, 60);
      var pct = denom > 0 ? Math.round(clamp(list.length / denom, 0, 1) * 100) : 0;
      return setMeta('scan_answered_qids', list).then(function () {
        return { answered: list.length, denominator: denom, pct: pct, total_questions: totalQ };
      });
    });
  }

  function getScanProgress() {
    return Promise.all([getMeta('scan_answered_qids', []), countQuestions()]).then(function (r) {
      var list = Array.isArray(r[0]) ? r[0] : [];
      var totalQ = r[1];
      var denom = Math.min(totalQ, 60);
      var pct = denom > 0 ? Math.round(clamp(list.length / denom, 0, 1) * 100) : 0;
      return { answered: list.length, denominator: denom, pct: pct, total_questions: totalQ };
    });
  }

  /* ======================================================================
   * 12. キーワード検索
   * ====================================================================== */

  function normalizeForSearch(s) {
    return String(s == null ? '' : s)
      .replace(/[Ａ-Ｚａ-ｚ０-９]/g, function (ch) {
        return String.fromCharCode(ch.charCodeAt(0) - 0xFEE0);
      })
      .replace(/[\u3000]/g, ' ')
      .toLowerCase();
  }

  /* 問題文・選択肢・解説を横断して検索する。
     ヒット箇所（どのフィールドか）も返し、検索結果カードの抜粋に使う。 */
  function searchAll(keyword) {
    var kw = normalizeForSearch(String(keyword || '').trim());
    if (!kw) { return Promise.resolve({ keyword: '', hits: [], summary: {}, total: 0 }); }

    return Promise.all([getAllQuestions(), getAllAtoms()]).then(function (r) {
      var questions = r[0], atoms = r[1];
      var atomsByQ = {};
      atoms.forEach(function (a) {
        if (!atomsByQ[a.q_id]) { atomsByQ[a.q_id] = []; }
        atomsByQ[a.q_id].push(a);
      });

      var hits = [];
      var summary = { S: 0, A: 0, B: 0, C: 0 };

      questions.forEach(function (q) {
        var list = (atomsByQ[q.q_id] || []).sort(function (a, b) { return a.original_num - b.original_num; });
        var fields = [];

        if (normalizeForSearch(q.stem).indexOf(kw) >= 0) { fields.push('stem'); }
        /* 自分の言葉で書いた文章は、本人にとって最も探しやすい語彙になる。
           検索から外すと「書いたはずなのに出てこない」が起きる。 */
        if (q.user_memo && normalizeForSearch(q.user_memo).indexOf(kw) >= 0) { fields.push('memo'); }
        if (normalizeForSearch(stripHtml(q.overall_explanation)).indexOf(kw) >= 0) { fields.push('explanation'); }
        if (q.comparison_table && normalizeForSearch(stripHtml(q.comparison_table)).indexOf(kw) >= 0) { fields.push('table'); }

        var matchedAtoms = list.filter(function (a) {
          return normalizeForSearch(a.text).indexOf(kw) >= 0 ||
                 normalizeForSearch(stripHtml(a.explanation)).indexOf(kw) >= 0 ||
                 (a.user_memo && normalizeForSearch(a.user_memo).indexOf(kw) >= 0);
        });
        if (matchedAtoms.some(function (a) {
          return a.user_memo && normalizeForSearch(a.user_memo).indexOf(kw) >= 0;
        })) { fields.push('memo'); }
        if (matchedAtoms.length) { fields.push('atom'); }
        if (!fields.length) { return; }

        var excerptSrc = fields.indexOf('stem') >= 0 ? q.stem
                       : (matchedAtoms.length ? matchedAtoms[0].text : stripHtml(q.overall_explanation));
        hits.push({
          q_id: q.q_id, num_code: q.num_code, rank: q.rank,
          unit: q.unit, major: q.major, medium: q.medium, sub_item: q.sub_item,
          stem: q.stem, fields: fields,
          matched_atom_ids: matchedAtoms.map(function (a) { return a.atom_id; }),
          excerpt: makeExcerpt(excerptSrc, keyword)
        });
        if (summary[q.rank] === undefined) { summary[q.rank] = 0; }
        summary[q.rank]++;
      });

      var rankOrder = { S: 0, A: 1, B: 2, C: 3 };
      hits.sort(function (a, b) {
        var d = (rankOrder[a.rank] === undefined ? 9 : rankOrder[a.rank]) -
                (rankOrder[b.rank] === undefined ? 9 : rankOrder[b.rank]);
        if (d !== 0) { return d; }
        return String(a.num_code).localeCompare(String(b.num_code));
      });

      return { keyword: keyword, hits: hits, summary: summary, total: hits.length };
    });
  }

  function makeExcerpt(text, keyword) {
    var plain = stripHtml(text);
    var norm = normalizeForSearch(plain);
    var kw = normalizeForSearch(keyword);
    var at = norm.indexOf(kw);
    if (at < 0) { return plain.slice(0, 90); }
    var from = Math.max(0, at - 28);
    var to = Math.min(plain.length, at + kw.length + 52);
    return (from > 0 ? '…' : '') + plain.slice(from, to) + (to < plain.length ? '…' : '');
  }

  /* ======================================================================
   * 13. バックアップ・復元・リセット
   * ====================================================================== */

  /* --- Blob ⇔ base64（バックアップ用） ---
     JSONにBlobは入らないので base64 にする。3割ほど太るので、
     全部で30MBを超えるときは画像と音を入れずに書き出し、
     その事実を payload と報告に必ず残す（黙って落とさない）。 */
  var BACKUP_FILES_CAP = 30 * 1024 * 1024;

  function blobToBase64(blob) {
    return new Promise(function (resolve, reject) {
      if (typeof FileReader === 'undefined') { resolve(null); return; }
      var fr = new FileReader();
      fr.onload = function () {
        var s = String(fr.result || '');
        var i = s.indexOf(',');
        resolve(i >= 0 ? s.slice(i + 1) : '');
      };
      fr.onerror = function () { reject(fr.error || new Error('画像を読み出せませんでした')); };
      fr.readAsDataURL(blob);
    });
  }

  function base64ToBlob(b64, mime) {
    var bin = global.atob(b64);
    var len = bin.length;
    var buf = new Uint8Array(len);
    for (var i = 0; i < len; i++) { buf[i] = bin.charCodeAt(i); }
    return new Blob([buf], { type: mime || 'application/octet-stream' });
  }

  function packUserFiles() {
    return getAllUserFiles().then(function (list) {
      var total = list.reduce(function (n, f) { return n + (f.bytes || 0); }, 0);
      if (!list.length) { return { files: [], skipped: 0, bytes: 0 }; }
      if (total > BACKUP_FILES_CAP) {
        return { files: [], skipped: list.length, bytes: total, over_cap: true };
      }
      return Promise.all(list.map(function (f) {
        return blobToBase64(f.blob).then(function (b64) {
          return {
            file_id: f.file_id, kind: f.kind, q_id: f.q_id, mime: f.mime,
            bytes: f.bytes, w: f.w, h: f.h, updated_at: f.updated_at, data_b64: b64
          };
        });
      })).then(function (out) {
        return { files: out.filter(function (x) { return x.data_b64; }),
                 skipped: 0, bytes: total };
      });
    }).catch(function () { return { files: [], skipped: -1, bytes: 0 }; });
  }

  function exportBackup() {
    return Promise.all([
      getAllQuestions(), getAllAtoms(), getAllLogs(),
      getConceptStats(), getAll(STORE.GUARD), getAll(STORE.META), packUserFiles()
    ]).then(function (r) {
      var packed = r[6];
      return {
        schema_version : SCHEMA_VER,
        app_build      : APP_BUILD,
        exported_at    : nowMs(),
        exported_at_iso: new Date().toISOString(),
        counts: {
          questions: r[0].length, atoms: r[1].length, progress_log: r[2].length,
          concept_stat: r[3].length, guard_log: r[4].length, meta: r[5].length,
          user_files: packed.files.length,
          user_files_skipped: packed.skipped,
          user_files_bytes: packed.bytes
        },
        /* 入らなかったときに、あとから見て理由が分かるようにしておく */
        notes: packed.over_cap
          ? ['画像と音の合計が30MBを超えたため、このバックアップには含めていません']
          : [],
        stores: {
          questions    : r[0],
          atoms        : r[1],
          progress_log : r[2],
          concept_stat : r[3],
          guard_log    : r[4],
          meta         : r[5],
          user_files   : packed.files
        }
      };
    });
  }

  function timestampName() {
    var d = new Date();
    function p(n) { return (n < 10 ? '0' : '') + n; }
    return d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + '_' +
           p(d.getHours()) + p(d.getMinutes()) + p(d.getSeconds());
  }

  /* JSONファイルとしてブラウザにダウンロードさせる（バックアップと文言パックで共用）。
     Blob / URL が無い環境（テストランナー等）では downloaded:false を返すだけで、
     例外は投げない。呼び出し側が「保存できませんでした」を出せるようにする。 */
  function downloadJson(filename, payload) {
    var text = JSON.stringify(payload);
    if (typeof Blob === 'undefined' || typeof URL === 'undefined' || !global.document) {
      return { filename: filename, payload: payload, downloaded: false };
    }
    var blob = new Blob([text], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var a = global.document.createElement('a');
    a.href = url;
    a.download = filename;
    a.style.display = 'none';
    global.document.body.appendChild(a);
    a.click();
    global.setTimeout(function () {
      global.document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 1500);
    return { filename: filename, payload: payload, downloaded: true };
  }

  function downloadBackup(prefix) {
    return exportBackup().then(function (payload) {
      var name = (prefix || 'NurseExamApp_Backup') + '_' + timestampName() + '_V1.00.json';
      return downloadJson(name, payload);
    });
  }

  /* mode: 'replace' … 全消去してから復元 ／ 'merge' … 既存に上書き追加 */
  function restoreBackup(payload, mode) {
    if (!payload || !payload.stores) {
      return Promise.reject(new Error('バックアップの形式が違います。書き出したJSONファイルの中身をそのまま渡してください。'));
    }
    var m = (mode === 'replace') ? 'replace' : 'merge';
    var s = payload.stores;
    var report = {
      ok: true, source: 'backup', mode: m, restored_at: nowMs(),
      questions: 0, atoms: 0, progress_log: 0, concept_stat: 0, guard_log: 0, meta: 0,
      user_files: 0,
      errors: [], warnings: [], messages: []
    };

    if (payload.schema_version !== SCHEMA_VER) {
      report.warnings.push({
        line: 0,
        message: 'バックアップのスキーマ版（' + payload.schema_version + '）が現在の版（' + SCHEMA_VER + '）と異なります。読み込めない項目があるかもしれません。'
      });
    }

    var names = [STORE.QUESTIONS, STORE.ATOMS, STORE.PROGRESS, STORE.CONCEPT,
                 STORE.GUARD, STORE.META, STORE.FILES];

    return write(names, function (st) {
      if (m === 'replace') {
        names.forEach(function (n) { st[n].clear(); });
      }
      (s.questions || []).forEach(function (q) {
        q._star = q.is_starred ? 1 : 0;
        st[STORE.QUESTIONS].put(q); report.questions++;
      });
      (s.atoms || []).forEach(function (a) {
        a._star = a.is_starred ? 1 : 0;
        a._unlearned = (a.answer_count > 0) ? 0 : 1;
        st[STORE.ATOMS].put(a); report.atoms++;
      });
      (s.progress_log || []).forEach(function (l) {
        var rec = {};
        Object.keys(l).forEach(function (k) { if (k !== 'log_id') { rec[k] = l[k]; } });
        st[STORE.PROGRESS].add(rec); report.progress_log++;
      });
      (s.concept_stat || []).forEach(function (c) { st[STORE.CONCEPT].put(c); report.concept_stat++; });
      (s.guard_log || []).forEach(function (g) { st[STORE.GUARD].put(g); report.guard_log++; });
      (s.meta || []).forEach(function (mm) { st[STORE.META].put(mm); report.meta++; });
      /* 画像と音は base64 で入っている。Blob に戻してから put する。 */
      (s.user_files || []).forEach(function (f) {
        if (!f || !f.data_b64) { return; }
        try {
          st[STORE.FILES].put({
            file_id: f.file_id, kind: f.kind, q_id: f.q_id || null,
            blob: base64ToBlob(f.data_b64, f.mime), mime: f.mime,
            bytes: f.bytes, w: f.w, h: f.h, updated_at: f.updated_at
          });
          report.user_files++;
        } catch (e) {
          report.warnings.push({ line: 0, message: '画像を1件戻せませんでした：' + f.file_id });
        }
      });
    }).then(function () {
      _metaCache = null;
      return loadMeta();
    }).then(function () {
      return refreshConceptCatalog();
    }).then(function () {
      report.finished_at = nowMs();
      return report;
    });
  }

  /* 全初期化。仕様どおり、消す直前に必ずJSONを自動退避してから実行する。 */
  function resetAll() {
    return downloadBackup('NurseExamApp_AutoBackup_BeforeReset').then(function (saved) {
      var names = [STORE.QUESTIONS, STORE.ATOMS, STORE.PROGRESS, STORE.CONCEPT,
                   STORE.GUARD, STORE.META, STORE.FILES];
      return write(names, function (st) {
        names.forEach(function (n) { st[n].clear(); });
      }).then(function () {
        _metaCache = null;
        return ensureInitialized();
      }).then(function () {
        return { ok: true, backup_filename: saved.filename, downloaded: saved.downloaded };
      });
    });
  }

  /* 中項目単位のリセット。問題データは残し、学習の進捗と履歴だけを消す。 */
  function resetProgressByScope(field, value) {
    if (['unit', 'major', 'medium', 'sub_item'].indexOf(field) < 0) {
      return Promise.reject(new Error('リセット範囲の指定が不正です: ' + field));
    }
    return getAtomsByScope(field, value).then(function (atoms) {
      if (!atoms.length) { return { ok: true, atoms: 0, logs: 0 }; }
      var ids = {};
      atoms.forEach(function (a) { ids[a.atom_id] = true; });

      return getAllLogs().then(function (logs) {
        var victims = logs.filter(function (l) { return ids[l.atom_id]; });
        return write([STORE.ATOMS, STORE.PROGRESS], function (st) {
          atoms.forEach(function (a) {
            a.srs_step = 0;
            a.interval_code = null;
            a.due_date = null;
            a.last_eval = null;
            a.last_answered_at = null;
            a.answer_count = 0;
            a.correct_count = 0;
            a.hard_streak = 0;
            a.weakness_pt = 0;
            a._unlearned = 1;
            a.updated_at = nowMs();
            st[STORE.ATOMS].put(a);
          });
          victims.forEach(function (l) { st[STORE.PROGRESS].delete(l.log_id); });
        }).then(function () {
          return { ok: true, atoms: atoms.length, logs: victims.length };
        });
      });
    });
  }

  /* 問題データを消さずに、学習の進捗だけをすべて初期化する */
  function resetProgressAll() {
    return downloadBackup('NurseExamApp_AutoBackup_BeforeProgressReset').then(function (saved) {
      return getAllAtoms().then(function (atoms) {
        return write([STORE.ATOMS, STORE.PROGRESS, STORE.GUARD], function (st) {
          atoms.forEach(function (a) {
            a.srs_step = 0; a.interval_code = null; a.due_date = null;
            a.last_eval = null; a.last_answered_at = null;
            a.answer_count = 0; a.correct_count = 0; a.hard_streak = 0;
            a.weakness_pt = 0; a._unlearned = 1; a.updated_at = nowMs();
            st[STORE.ATOMS].put(a);
          });
          st[STORE.PROGRESS].clear();
          st[STORE.GUARD].clear();
        });
      }).then(function () {
        return setMetaBulk({
          scan_answered_qids: [],
          tutorial_answered: 0,
          tutorial_finished: false,
          onboarding_done: false,
          onboarding_step: 0
        });
      }).then(function () {
        return { ok: true, backup_filename: saved.filename };
      });
    });
  }

  /* ======================================================================
   * 14. 統計サマリー（scheduler / main が起動時に使う）
   * ====================================================================== */

  function getSummary() {
    return Promise.all([
      countQuestions(), countAtoms(), countUnlearned(),
      getDueCount(), countLogs(), loadMeta(), getScanProgress()
    ]).then(function (r) {
      var totalAtoms = r[1];
      var unlearned = r[2];
      var answeredUnique = totalAtoms - unlearned;
      return {
        total_questions      : r[0],
        total_atoms          : totalAtoms,
        unlearned_atoms      : unlearned,
        answered_unique_atoms: answeredUnique,
        unique_answered_ratio: totalAtoms > 0 ? (answeredUnique / totalAtoms) : 0,
        due_count            : r[3],
        total_logs           : r[4],
        meta                 : r[5],
        scan                 : r[6],
        app_build            : APP_BUILD,
        schema_version       : SCHEMA_VER
      };
    });
  }

  /* ======================================================================
   * 15. 公開API
   * ====================================================================== */

  var API = {
    /* --- 定数 --- */
    APP_BUILD    : APP_BUILD,
    DB_NAME      : DB_NAME,
    DB_VERSION   : DB_VERSION,
    SCHEMA_VER   : SCHEMA_VER,
    STORE        : STORE,
    MOCK_DEFS    : MOCK_DEFS,
    DEFAULT_META : DEFAULT_META,

    /* --- ライフサイクル --- */
    open              : open,
    ensureInitialized : ensureInitialized,
    getSummary        : getSummary,

    /* --- meta --- */
    getMeta       : getMeta,
    setMeta       : setMeta,
    setMetaBulk   : setMetaBulk,
    raiseMeta     : raiseMeta,
    loadMeta      : loadMeta,

    /* --- インポート --- */
    importText    : importText,

    /* --- 読み出し --- */
    getQuestion        : getQuestion,
    getQuestionFull    : getQuestionFull,
    getQuestionsFull   : getQuestionsFull,
    getAllQuestions    : getAllQuestions,
    countQuestions     : countQuestions,
    countMemos         : countMemos,
    setMemo            : setMemo,
    getQuestionsByScope: getQuestionsByScope,
    getAtom            : getAtom,
    getAllAtoms        : getAllAtoms,
    countAtoms         : countAtoms,
    getAtomsByQuestion : getAtomsByQuestion,
    getAtomsByTag      : getAtomsByTag,
    getAtomsByScope    : getAtomsByScope,
    getDueAtoms        : getDueAtoms,
    getDueCount        : getDueCount,
    getUnlearnedAtoms  : getUnlearnedAtoms,
    putUserAudio       : putUserAudio,
    getUserAudio       : getUserAudio,
    deleteUserAudio    : deleteUserAudio,
    ALARM_FILE_ID      : ALARM_FILE_ID,
    ALARM_MAX_BYTES    : ALARM_MAX_BYTES,
    putUserImage       : putUserImage,
    getUserImage       : getUserImage,
    deleteUserImage    : deleteUserImage,
    putQuestionShallow : putQuestionShallow,
    getAllUserFiles    : getAllUserFiles,
    countUserFiles     : countUserFiles,
    shrinkImage        : shrinkImage,
    USER_IMG_MAX_EDGE  : USER_IMG_MAX_EDGE,
    judgeSplittable    : judgeSplittable,
    autoMarkSplittable : autoMarkSplittable,
    clearSplittable    : clearSplittable,
    countUnlearned     : countUnlearned,
    countUnlearnedByScope: countUnlearnedByScope,
    buildTree          : buildTree,

    /* --- 書き込み --- */
    commitAnswer       : commitAnswer,
    updateAtom         : updateAtom,
    updateQuestion     : updateQuestion,
    toggleQuestionStar : toggleQuestionStar,
    toggleAtomStar     : toggleAtomStar,
    getStarredNote     : getStarredNote,

    /* --- 履歴 --- */
    getLogsByAtom     : getLogsByAtom,
    getLogsSince      : getLogsSince,
    getAllLogs        : getAllLogs,
    countLogs         : countLogs,
    getLogMapByAtoms  : getLogMapByAtoms,

    /* --- トピックガード --- */
    pushGuard        : pushGuard,
    getGuardTags     : getGuardTags,
    purgeOldestGuard : purgeOldestGuard,
    trimGuard        : trimGuard,
    clearGuard       : clearGuard,

    /* --- 74概念 --- */
    refreshConceptCatalog : refreshConceptCatalog,
    getConceptStats       : getConceptStats,
    saveConceptScores     : saveConceptScores,

    /* --- 解禁・進捗率 --- */
    evaluateUnlocks       : evaluateUnlocks,
    getUnlockState        : getUnlockState,
    recordFullMockResult  : recordFullMockResult,
    applyHighWaterPct     : applyHighWaterPct,
    recordScanProgress    : recordScanProgress,
    getScanProgress       : getScanProgress,
    bumpDailyCount        : bumpDailyCount,
    getDailyCount         : getDailyCount,

    /* --- 検索 --- */
    searchAll : searchAll,

    /* --- バックアップ --- */
    exportBackup         : exportBackup,
    blobToBase64         : blobToBase64,
    base64ToBlob         : base64ToBlob,
    packUserFiles        : packUserFiles,
    BACKUP_FILES_CAP     : BACKUP_FILES_CAP,
    downloadJson         : downloadJson,
    timestampName        : timestampName,
    downloadBackup       : downloadBackup,
    restoreBackup        : restoreBackup,
    resetAll             : resetAll,
    resetProgressAll     : resetProgressAll,
    resetProgressByScope : resetProgressByScope,

    /* --- 共有ユーティリティ（scheduler / main から使う） --- */
    util : {
      nowMs             : nowMs,
      clamp             : clamp,
      dayStart          : dayStart,
      fnv1a             : fnv1a,
      hash6             : hash6,
      stripHtml         : stripHtml,
      circledToIndex    : circledToIndex,
      indexToCircled    : indexToCircled,
      normalizeForSearch: normalizeForSearch,
      makeExcerpt       : makeExcerpt
    },

    /* --- パーサ（純関数：単体テスト可能） --- */
    Parser : {
      splitTsvRow                : splitTsvRow,
      csvUnquote                 : csvUnquote,
      unescapeLiteral            : unescapeLiteral,
      sanitizeJsonCell           : sanitizeJsonCell,
      sanitizeTagCell            : sanitizeTagCell,
      extractTables              : extractTables,
      extractMermaid             : extractMermaid,
      extractImage               : extractImage,
      splitAtomExplanations      : splitAtomExplanations,
      detectCorrectFromExplanation: detectCorrectFromExplanation,
      crossCheckAnswer           : crossCheckAnswer,
      parseAnswerCell            : parseAnswerCell,
      buildNumCode               : buildNumCode,
      stripLeadingCircle         : stripLeadingCircle,
      looksLikeHeaderRow         : looksLikeHeaderRow,
      buildQuestionFromRow       : buildQuestionFromRow
    }
  };

  global.Storage = API;
  if (typeof module !== 'undefined' && module.exports) { module.exports = API; }

})(typeof window !== 'undefined' ? window : this);
