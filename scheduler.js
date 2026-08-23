/* ==========================================================================
 * 20260815_NurseExamApp_V1.00  /  scheduler.js
 * 進捗管理・ロジック層
 *
 * 【この層が引き受ける責務】
 *  - 忘却スケジューリング（10m/1h/1d/1w/30d/90d/180d ＋ 日界4:00補正）
 *  - 弱点スコア算定（新近性補正・連続誤答ボーナス・ランク重み係数）
 *  - 出題優先度ソートとトピックガード（30分除外・FIFO安全パージ）
 *  - 74概念理解率（concept_score）の集計（未評価は null 保持）
 *  - 5段階レベル判定と不退転ハイウォーターマーク
 *  - 分析スキャン精度（全60問モデル・分母ガード）
 *  - 正誤確定後の初期点灯（推奨評価）判定
 *  - インライン早期復習割り込みの発火・復帰・上限制御
 *  - 模試の履歴連動 自動昇格／安全降格
 *
 * 【依存】 window.Storage（storage.js が先に読み込まれている必要がある）
 *
 * 【仕様の解釈を確定した箇所】
 *  A. 弱点ptは 0 で下限クランプしてからランク重みを掛ける。
 *     負値のまま掛けると「Sランクの得意問題」が「Cランクの得意問題」より
 *     下位に沈み、頻出優先トグルの意図が逆転するため。
 *  B. Level 1 は「ユニーク解答問題数」、Level 2 は「延べ解答問題数」で数える。
 *     Level 1 の 60問 が分析精度100%（ユニーク基準）と直結しているため。
 *  C. 不退転は「レベル別」に保持する（max_pct_lv1〜5）。
 *     単一の max_pct だけだと、レベルが上がった瞬間に前レベルの高い値が
 *     居座り、新レベルの進捗が永久に100%表示になって壊れるため。
 *  D. 概念別弱点ノックは「忘却スケジュールは更新しないが、評価の記録・
 *     弱点pt・概念理解率は更新する」。更新しないと、ノックで克服しても
 *     概念理解率が永久に低いままで最優先TOP3から抜けられないため。
 *     単語自由検索の演習は、仕様どおり一切更新しない。
 *  E. 評価を書き込んでよいのは「未学習の肢」と「自分の期日が来た肢」だけ。
 *     1問を出すと4肢そろって画面に出るが、期日前の肢にまで評価を書くと、
 *     その間隔を待たずに梯子が1段昇る。実測（V1.18 で修正する前の挙動）：
 *     10分後の苦手肢が1本あるだけで、残り3肢が 30日 → 90日 → 180日 へ
 *     20分で駆け上がった。間隔だけが実力より先に伸びる状態になる。
 *     ただし「間違えた」は前倒しでも有効な観測なので、降格だけは受け付ける。
 *     昇格は「その間隔でも覚えていた」という主張だが、その間隔を待って
 *     いない以上、主張の根拠が無い。降格は「今この瞬間忘れている」という
 *     直接の観測なので、いつ取っても正しい。この非対称が門番の設計理由。
 *     ただし門番が見るのは「1日以上の段」だけ。10m / 1h は1回の学習の中で
 *     回すための刻みで、第5章②の早期復習割り込みはこの2段を期日より前に
 *     出題する仕組みそのもの。ここを塞ぐと割り込みが記録されなくなる。
 * ========================================================================== */

(function (global) {
  'use strict';

  var S = global.Storage;

  /* ======================================================================
   * 0. 定数
   * ====================================================================== */

  var APP_BUILD = '20260815_NurseExamApp_V1.00';

  var MIN = 60 * 1000;
  var HOUR = 60 * MIN;
  var DAY = 24 * HOUR;

  /* 忘却ステップの梯子。srs_step は「この配列の添字 + 1」。0 は未学習。 */
  var STEPS = [
    { code: '10m',  ms: 10 * MIN,  label: '10分後'   },
    { code: '1h',   ms: 1 * HOUR,  label: '1時間後'  },
    { code: '1d',   ms: 1 * DAY,   label: '1日後'    },
    { code: '1w',   ms: 7 * DAY,   label: '1週間後'  },
    { code: '30d',  ms: 30 * DAY,  label: '30日後'   },
    { code: '90d',  ms: 90 * DAY,  label: '90日後'   },
    { code: '180d', ms: 180 * DAY, label: '180日後'  }
  ];

  var STEP_INDEX = {};
  STEPS.forEach(function (s, i) { STEP_INDEX[s.code] = i; });

  /* 緊急度昇順（本日の復習の出題順）。10m が最も緊急。 */
  var URGENCY_ORDER = { '10m': 0, '1h': 1, '1d': 2, '1w': 3, '30d': 4, '90d': 5, '180d': 6 };

  /* マスターボタンの解禁は「30日以上の長期ステップ到達時のみ」 */
  var MASTER_UNLOCK_FROM = STEP_INDEX['30d'];

  var EVAL = { HARD: 'hard', NORMAL: 'normal', EASY: 'easy', MASTER: 'master' };

  var EVAL_LABEL = { hard: '難しい', normal: '普通', easy: '簡単', master: 'マスター' };

  /* 74概念理解率の換算点（第12章②） */
  var EVAL_POINTS = { hard: 0, normal: 50, easy: 80, master: 100 };

  /* 弱点ptの加減算（第6章②） */
  var WEAK_PT = { hard: 10, normal: 2, easy: -5, master: 0 };

  /* 連続誤答ボーナス：1回目 +10 → 2回目 ×1.5(+15) → 3回目以降 ×2.0(+20) */
  var STREAK_MULTIPLIER = [1.0, 1.5, 2.0];

  /* 出題頻度ランク重み係数（第6章③） */
  var RANK_WEIGHT = { S: 2.5, A: 1.6, B: 1.0, C: 0.3 };

  /* トピックガードの既定ウィンドウ（第9章②） */
  var GUARD_WINDOW_MS = 30 * MIN;

  /* 忘却スケジュールを更新しない独立モード */
  var NO_SCHEDULE_MODES = ['knock', 'search'];
  /* 進捗を一切記録しないモード */
  var NO_RECORD_MODES = ['search'];
  /* 早期復習割り込みを許可するモード（絶対ガード：これ以外は完全禁止） */
  var INTERRUPT_ALLOWED_MODES = ['new', 'random'];
  /* トピックガードを無効化するモード */
  var GUARD_DISABLED_MODES = ['knock', 'review', 'search', 'exam'];

  /* 5段階レベル定義（第9章③） */
  var LEVEL_DEFS = [
    { level: 1, name: '初期スキャニング',   milestones: [10, 20, 60] },
    { level: 2, name: '数量マイルストーン', milestones: [100, 300, 500, 1000] },
    { level: 3, name: '全問題読破',         milestones: null },
    { level: 4, name: '弱点・つまずき一掃', milestones: null },
    { level: 5, name: '完全制覇・殿堂入り', milestones: null }
  ];

  /* 3段階ビジュアルテーマ（第15章） */
  var VISUAL_BY_LEVEL = { 1: 'challenge', 2: 'challenge', 3: 'growth', 4: 'growth', 5: 'master' };

  /* 分析スキャンモデル（第8章②） */
  var SCAN_MODEL_SIZE = 60;

  /* 早期復習割り込み（第5章②） */
  var INTERRUPT_TRIGGER = 3;   /* 3問蓄積で発火 */
  var INTERRUPT_BATCH = 3;     /* 1回の割込で出す問題数 */
  var INTERRUPT_MAX_RUN = 5;   /* 連敗時の連続割込上限 */

  /* ======================================================================
   * 1. 小道具
   * ====================================================================== */

  function nowMs() { return Date.now(); }
  function isNum(v) { return typeof v === 'number' && isFinite(v); }
  function clamp(v, lo, hi) { return v < lo ? lo : (v > hi ? hi : v); }
  function has(arr, v) { return arr.indexOf(v) >= 0; }

  function rankWeight(rank) {
    var w = RANK_WEIGHT[String(rank || 'B').toUpperCase()];
    return isNum(w) ? w : 1.0;
  }

  function stepIndexOf(atom) {
    if (!atom) { return -1; }
    if (atom.interval_code && STEP_INDEX[atom.interval_code] !== undefined) {
      return STEP_INDEX[atom.interval_code];
    }
    if (isNum(atom.srs_step) && atom.srs_step > 0) {
      return clamp(atom.srs_step - 1, 0, STEPS.length - 1);
    }
    return -1; /* 未学習 */
  }

  function stepToCode(idx) {
    var i = clamp(idx, 0, STEPS.length - 1);
    return STEPS[i].code;
  }

  /* 日界（既定4:00）を跨ぐ丸め。
     1日以上の間隔は「到達日の朝4:00」に吸着させ、深夜学習で翌日分が
     まるまる1日遅れて出てこなくなる事故を防ぐ（第15章）。 */
  /* ======================================================================
   * 試験日から復習間隔の上限を決める（V1.30）
   *
   * 【なぜ要るか】
   *   梯子の上限は180日。試験まで90日しかない人に180日後の予定を入れると、
   *   その肢は【試験当日までに一度も出てこない】。覚えたつもりのまま本番を迎える。
   *
   * 【上限＝残り日数の1/3】
   *   残り90日 → 30日 ／ 180日 → 60日 ／ 365日 → 120日。
   *   1/3 なら、上限いっぱいの間隔でも試験日までに最低3回は当たる。
   *   （1/2 だと2回、1/4 以下だと直前に復習が渋滞する）
   *
   * 【残りが3日を切ったら】
   *   1/3 が1日未満になる。ここで0日にすると due が過去になり
   *   同じ肢が延々と出続けるので、1時間へ倒して回し続ける。
   *
   * 【試験日を過ぎたら】
   *   上限を外して従来（180日）へ戻す。翌年の受験や、
   *   資格取得後の見直しでそのまま使えるようにするため。
   * ====================================================================== */

  var EXAM_CAP_RATIO   = 1 / 3;
  var EXAM_CAP_MIN_MS  = HOUR;   /* 残り3日未満のときの下限 */
  var EXAM_FINAL_DAYS  = 10;     /* 直前モードへ切り替わる日数 */

  /* 'YYYY-MM-DD' → その日の日界時刻（ミリ秒）。読めない値は null。 */
  function parseExamDate(v, boundaryHour) {
    if (!v || typeof v !== 'string') { return null; }
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v.trim());
    if (!m) { return null; }
    var h = isNum(boundaryHour) ? boundaryHour : 4;
    var d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), h, 0, 0, 0);
    var t = d.getTime();
    return isNum(t) && !isNaN(t) ? t : null;
  }

  /* 試験まであと何日か。当日は0、過ぎていれば負。 */
  function examRemainingDays(meta, now, boundaryHour) {
    var exam = parseExamDate(meta && meta.exam_date, boundaryHour);
    if (exam === null) { return null; }
    var t = isNum(now) ? now : nowMs();
    var today = S.util.dayStart(t, isNum(boundaryHour) ? boundaryHour : 4);
    return Math.round((exam - today) / DAY);
  }

  /* 間隔の上限（ミリ秒）。試験日が無い／過ぎている場合は null＝上限なし。 */
  function examCapMs(meta, now, boundaryHour) {
    var rest = examRemainingDays(meta, now, boundaryHour);
    if (rest === null || rest < 0) { return null; }
    var days = Math.floor(rest * EXAM_CAP_RATIO);
    return days >= 1 ? days * DAY : EXAM_CAP_MIN_MS;
  }

  /* 'normal'（通常）／'final'（直前10日）／null（試験日なし・経過後） */
  function examPhase(meta, now, boundaryHour) {
    var rest = examRemainingDays(meta, now, boundaryHour);
    if (rest === null || rest < 0) { return null; }
    return rest <= EXAM_FINAL_DAYS ? 'final' : 'normal';
  }

  function computeDueDate(fromTs, stepIdx, boundaryHour, capMs) {
    var step = STEPS[clamp(stepIdx, 0, STEPS.length - 1)];
    /* 試験日の上限で頭を押さえる。梯子そのものは書き換えない
       （評価の意味と、次にどの段へ上がるかは今までどおり）。 */
    var span = (isNum(capMs) && capMs > 0) ? Math.min(step.ms, capMs) : step.ms;
    var target = fromTs + span;
    /* 1日未満に潰れたときは日界へ寄せない。寄せると試験日を追い越す。 */
    if (span < DAY) { return target; }
    var snapped = S.util.dayStart(target, isNum(boundaryHour) ? boundaryHour : 4);
    return Math.max(snapped, fromTs + MIN);
  }

  /* ======================================================================
   * 2. 忘却スケジューリング（第4章④）
   * ====================================================================== */

  /* マスターボタンの解禁判定。30日以上の長期ステップに到達している間だけ有効。 */
  function isMasterUnlocked(atom) {
    return stepIndexOf(atom) >= MASTER_UNLOCK_FROM;
  }

  /* 現在ステップと評価から、次のステップ添字を決める。
   *  難  : 常に 10m へ戻す
   *  普  : 初見→1h ／ 10m・1h→1d ／ それ以降は「簡単」を押すまで 1w 固定
   *  易  : 初見→30d ／ つまずき後は 1d→1w→30d→90d→180d と1段ずつ昇る（上限180d）
   *  マ  : 30d以上に到達しているときだけ有効。押下で 180d
   */
  function nextStepIndex(currentIdx, evalKey) {
    var i10m = STEP_INDEX['10m'];
    var i1h  = STEP_INDEX['1h'];
    var i1d  = STEP_INDEX['1d'];
    var i1w  = STEP_INDEX['1w'];
    var i30d = STEP_INDEX['30d'];
    var i90d = STEP_INDEX['90d'];
    var i180 = STEP_INDEX['180d'];

    if (evalKey === EVAL.HARD) { return i10m; }

    if (evalKey === EVAL.NORMAL) {
      if (currentIdx < 0) { return i1h; }
      if (currentIdx === i10m || currentIdx === i1h) { return i1d; }
      return i1w;
    }

    if (evalKey === EVAL.EASY) {
      if (currentIdx < 0) { return i30d; }
      if (currentIdx === i10m || currentIdx === i1h) { return i1d; }
      if (currentIdx === i1d)  { return i1w; }
      if (currentIdx === i1w)  { return i30d; }
      if (currentIdx === i30d) { return i90d; }
      if (currentIdx === i90d) { return i180; }
      return i180;
    }

    if (evalKey === EVAL.MASTER) { return i180; }

    return currentIdx < 0 ? i1h : currentIdx;
  }

  /* 評価を1つ適用した結果の予定を返す（DBには書かない純関数） */
  function planSchedule(atom, evalKey, opts) {
    opts = opts || {};
    var now = isNum(opts.now) ? opts.now : nowMs();
    var boundary = isNum(opts.boundaryHour) ? opts.boundaryHour : 4;
    /* 試験日が入っていれば、ここから先の間隔に上限がかかる（V1.30）。 */
    var capMs = (opts.capMs !== undefined) ? opts.capMs
              : examCapMs(opts.meta, now, boundary);
    var curIdx = stepIndexOf(atom);

    if (evalKey === EVAL.MASTER && !isMasterUnlocked(atom) && !opts.force) {
      /* 未解禁のマスターが渡された場合は「簡単」として安全に処理する */
      evalKey = EVAL.EASY;
    }

    var nextIdx = nextStepIndex(curIdx, evalKey);
    var code = stepToCode(nextIdx);
    return {
      eval          : evalKey,
      srs_step      : nextIdx + 1,
      interval_code : code,
      interval_ms   : STEPS[nextIdx].ms,
      interval_label: STEPS[nextIdx].label,
      due_date      : computeDueDate(now, nextIdx, boundary, capMs),
      /* 上限で押さえたときは、そのことを呼び出し側へ伝える（画面で「試験日まで」
         と出したり、テストで確かめたりするため）。 */
      capped        : (isNum(capMs) && capMs > 0 && capMs < STEPS[nextIdx].ms),
      cap_ms        : isNum(capMs) ? capMs : null,
      from_step     : curIdx,
      from_code     : curIdx >= 0 ? stepToCode(curIdx) : null,
      master_unlocked_next: nextIdx >= MASTER_UNLOCK_FROM
    };
  }

  /* ======================================================================
   * 2-b. 履歴から状態を組み立て直す（V1.38 / 端末をまたぐ同期のため）
   *
   * 【なぜ必要か】
   *   進捗を2台で同期するとき、「新しい方を採る」では正しくない。
   *   スマホで問1〜5、PCで問6〜10を解いたなら、【両方が残る】のが正しい。
   *   片方を丸ごと上書きすると、もう片方の勉強が消える。
   *
   * 【どう解くか】
   *   progress_log は追記しかされない台帳なので、2台ぶんを【合体】できる。
   *   合体した台帳から、各肢の状態（段・期日・回数・弱点pt）を組み立て直す。
   *   これは元々 computeWeaknessFromLogs がやっていることの拡張で、
   *   「弱点ptは累積で持てない」（設計判断1-4）という前提とも一致する。
   *
   * 【同じ解答を二重に数えない】
   *   台帳の1行は atom_id と answered_at の組で一意とみなす。
   *   同じ端末の同じ解答が2度入っても、片方だけが残る。
   * ====================================================================== */

  function logKey(l) {
    return String(l.atom_id) + '|' + String(l.answered_at);
  }

  /* 2つの台帳を合体する。戻り値は時刻順に並べ直した1本の台帳。 */
  function mergeLogs(a, b) {
    var seen = {}, out = [];
    (a || []).concat(b || []).forEach(function (l) {
      if (!l || !l.atom_id || !isNum(l.answered_at)) { return; }
      var k = logKey(l);
      if (seen[k]) { return; }
      seen[k] = 1;
      out.push(l);
    });
    out.sort(function (x, y) { return x.answered_at - y.answered_at; });
    return out;
  }

  /* 合体後の台帳から、1つの肢の状態を作り直す。
     予定（段・期日）を決めるのは【最後に予定を更新した行】。
     単語検索の演習など schedule_updated:false の行は予定に影響させない。 */
  function rebuildAtomState(atom, logs, opts) {
    opts = opts || {};
    var boundary = isNum(opts.boundaryHour) ? opts.boundaryHour : 4;
    var capMs = (opts.capMs !== undefined) ? opts.capMs : null;
    var list = (logs || []).slice().sort(function (x, y) {
      return (x.answered_at || 0) - (y.answered_at || 0);
    });
    if (!list.length) { return null; }

    var answers = 0, corrects = 0, lastSched = null, last = null;
    list.forEach(function (l) {
      answers++;
      if (l.is_correct) { corrects++; }
      last = l;
      if (l.schedule_updated) { lastSched = l; }
    });

    var patch = {
      answer_count     : answers,
      correct_count    : corrects,
      last_eval        : last.eval || null,
      last_answered_at : last.answered_at
    };

    if (lastSched) {
      var idx = STEP_INDEX[lastSched.interval_code];
      if (!isNum(idx)) { idx = Math.max(0, (lastSched.srs_step_after || 1) - 1); }
      patch.srs_step      = idx + 1;
      patch.interval_code = stepToCode(idx);
      patch.due_date      = computeDueDate(lastSched.answered_at, idx, boundary, capMs);
    }

    var w = computeWeaknessFromLogs(list, atom);
    patch.weakness_pt = w.pt;
    patch.hard_streak = w.hard_streak;
    return patch;
  }

  /* ======================================================================
   * 3. 弱点スコア（第6章②③）
   * ====================================================================== */

  /* 履歴の全走査で弱点ptを組み立て直す。
     「直近が簡単以外なら過去の -5pt をすべて無効化」という新近性補正は
     累積値では表現できないため、毎回ここで再計算する。 */
  function computeWeaknessFromLogs(logs, atom) {
    var list = (logs || []).slice().sort(function (a, b) {
      return (a.answered_at || 0) - (b.answered_at || 0);
    });

    if (!list.length) {
      /* 未学習（初見）は 0pt。出題時は最優先で抽出する。 */
      return {
        pt: 0, raw: 0, excluded: false, unlearned: true,
        last_eval: null, hard_streak: 0, easy_active: false,
        counts: { hard: 0, normal: 0, easy: 0, master: 0 }, total: 0
      };
    }

    var lastEval = null, i;
    for (i = list.length - 1; i >= 0; i--) {
      if (list[i].eval) { lastEval = list[i].eval; break; }
    }

    /* 新近性補正：直近が「簡単」でなければ、過去の -5pt はすべて 0pt 扱い */
    var easyActive = (lastEval === EVAL.EASY);

    var raw = 0;
    var streak = 0;
    var counts = { hard: 0, normal: 0, easy: 0, master: 0 };

    for (i = 0; i < list.length; i++) {
      var e = list[i].eval;
      var wrong = (list[i].is_correct === false);

      if (e === EVAL.HARD || wrong) {
        streak++;
        var mIdx = clamp(streak - 1, 0, STREAK_MULTIPLIER.length - 1);
        raw += WEAK_PT.hard * STREAK_MULTIPLIER[mIdx];
        if (e === EVAL.HARD) { counts.hard++; }
        continue;
      }

      streak = 0;
      if (e === EVAL.NORMAL) { raw += WEAK_PT.normal; counts.normal++; }
      else if (e === EVAL.EASY) { raw += (easyActive ? WEAK_PT.easy : 0); counts.easy++; }
      else if (e === EVAL.MASTER) { counts.master++; }
    }

    /* マスターは弱点判定から除外する */
    var excluded = (lastEval === EVAL.MASTER);
    var pt = excluded ? 0 : Math.max(0, raw);

    return {
      pt: Math.round(pt * 10) / 10,
      raw: Math.round(raw * 10) / 10,
      excluded: excluded,
      unlearned: false,
      last_eval: lastEval,
      hard_streak: streak,
      easy_active: easyActive,
      counts: counts,
      total: list.length,
      rank: atom ? atom.rank : null
    };
  }

  function computeWeaknessForAtom(atomId) {
    return Promise.all([S.getAtom(atomId), S.getLogsByAtom(atomId)]).then(function (r) {
      return computeWeaknessFromLogs(r[1], r[0]);
    });
  }

  /* 複数アトムの弱点ptを一括で再計算し、atoms 側のキャッシュへ書き戻す */
  function recomputeWeakness(atomIds) {
    var ids = Array.isArray(atomIds) ? atomIds : null;
    var loadAtoms = ids
      ? Promise.all(ids.map(function (id) { return S.getAtom(id); })).then(function (a) { return a.filter(Boolean); })
      : S.getAllAtoms();

    return loadAtoms.then(function (atoms) {
      var list = atoms.map(function (a) { return a.atom_id; });
      return S.getLogMapByAtoms(list).then(function (logMap) {
        var result = {};
        var writes = atoms.map(function (a) {
          var w = computeWeaknessFromLogs(logMap[a.atom_id] || [], a);
          result[a.atom_id] = w;
          if (a.weakness_pt === w.pt && a.hard_streak === w.hard_streak) { return null; }
          return S.updateAtom(a.atom_id, { weakness_pt: w.pt, hard_streak: w.hard_streak });
        }).filter(Boolean);
        return Promise.all(writes).then(function () { return result; });
      });
    });
  }

  /* 出題優先度 ＝ 弱点pt × ランク重み係数（トグルOFFなら弱点ptのみ） */
  function priorityScore(atom, weakness, preferFrequent) {
    var pt = weakness ? weakness.pt : (isNum(atom.weakness_pt) ? atom.weakness_pt : 0);
    var base = Math.max(0, pt);
    if (!preferFrequent) { return base; }
    return base * rankWeight(atom.rank);
  }

  /* ======================================================================
   * 4. 評価の適用（DBへのコミット）
   * ====================================================================== */

  /* 1つのアトムに評価を適用する。
   * ctx = {
   *   mode        : 'new'|'random'|'review'|'tree'|'knock'|'exam'|'search'
   *   newOnly     : true で未学習アトムを含む問題だけに絞る（ランダムモード用）
   *   isCorrect   : boolean   その肢の選択が正しかったか（誤答は弱点ptで加点）
   *   sessionId   : string
   *   now         : number
   *   boundaryHour: number
   *   force       : boolean   マスター解禁チェックを飛ばす（模試の自動昇格用）
   * }
   */
  /* 門番が守る対象は「1日以上の段」だけ。
     10m / 1h は1回の学習セッションの中で回すための刻みで、第5章②の
     早期復習割り込みは、この2段を “期日より前に” 出題する仕組みそのもの。
     ここまで期日で切ると、割り込みで答えた結果が1件も記録されなくなる。
     実測：10m のアトムを評価した瞬間に due が +10分になるため、直後に
     割り込みで同じ肢が出ても skipped=true で握り潰されていた。 */
  var GATED_STEPS = ['1d', '1w', '30d', '90d', '180d'];

  /* --- コミット門番（解釈E） ---
     戻り値 { commit, demote, reason }
       commit=false … このアトムには一切書き込まない（期日前で、かつ正しく扱えた）
       demote=true  … 期日前だが間違えた。評価を「難しい」に固定して記録する
     UI 側（part1）も同じ関数を呼ぶので、画面の表示と実際の書き込みが
     食い違うことが構造的に起こらない。 */
  function commitDecision(atom, isCorrect, mode, now) {
    var t = isNum(now) ? now : nowMs();
    if (!atom) { return { commit: false, demote: false, reason: 'no-atom' }; }
    /* 概念ノックは解釈Dのとおり「スケジュールは触らないが評価は記録する」
       独立モードなので、門番の対象外。単語検索は手前で弾かれている。 */
    if (has(NO_SCHEDULE_MODES, mode)) { return { commit: true, demote: false, reason: 'schedule-free' }; }
    if (!atom.answer_count)           { return { commit: true, demote: false, reason: 'unlearned' }; }
    if (!isNum(atom.due_date))        { return { commit: true, demote: false, reason: 'no-due' }; }
    if (atom.due_date <= t)           { return { commit: true, demote: false, reason: 'due' }; }
    if (!has(GATED_STEPS, atom.interval_code)) {
      return { commit: true, demote: false, reason: 'short-step' };
    }
    if (isCorrect === false)          { return { commit: true, demote: true,  reason: 'early-miss' }; }
    return { commit: false, demote: false, reason: 'not-due' };
  }

  function applyEvaluation(atomId, evalKey, ctx) {
    ctx = ctx || {};
    var mode = ctx.mode || 'random';
    var now = isNum(ctx.now) ? ctx.now : nowMs();

    /* 単語自由検索の演習は、忘却スケジュールも弱点ptも一切更新しない */
    if (has(NO_RECORD_MODES, mode)) {
      return Promise.resolve({ skipped: true, reason: 'この演習モードは進捗を記録しません', mode: mode });
    }

    /* 試験日の上限を効かせるために meta が要る。呼び出し側に渡させると
       経路ごとの足し忘れが起きるので、ここで自分で読む（loadMeta はキャッシュ済み）。 */
    var metaP = ctx.meta ? Promise.resolve(ctx.meta) : S.loadMeta();

    return Promise.all([S.getAtom(atomId), metaP]).then(function (pair) {
      var atom = pair[0];
      ctx.meta = pair[1];
      if (!atom) { throw new Error('選択肢が見つかりません: ' + atomId); }

      /* 門番。模試は applyExamResult が別経路で処理するので、ここは通らない。 */
      var decision = commitDecision(atom, ctx.isCorrect, mode, now);
      if (!decision.commit) {
        return {
          skipped: true, locked: true, decision: decision, atom: atom, mode: mode,
          reason: 'この選択肢はまだ期日ではないので記録しません'
        };
      }
      /* 期日前に間違えた肢は、押されたボタンに関わらず「難しい」で戻す。
         ここで押された評価をそのまま使うと、期日前の昇格を手動で作れてしまう。 */
      var useEval = decision.demote ? EVAL.HARD : evalKey;

      var boundary = isNum(ctx.boundaryHour) ? ctx.boundaryHour : 4;
      var plan = planSchedule(atom, useEval, {
        now: now, boundaryHour: boundary, force: ctx.force, meta: ctx.meta
      });
      var updateSchedule = !has(NO_SCHEDULE_MODES, mode);
      var wasCorrect = (ctx.isCorrect !== false);

      var patch = {
        last_eval        : plan.eval,
        last_answered_at : now,
        answer_count     : (atom.answer_count || 0) + 1,
        correct_count    : (atom.correct_count || 0) + (wasCorrect ? 1 : 0)
      };

      if (updateSchedule) {
        patch.srs_step      = plan.srs_step;
        patch.interval_code = plan.interval_code;
        patch.due_date      = plan.due_date;
      }

      var log = {
        eval           : plan.eval,
        is_correct     : wasCorrect,
        mode           : mode,
        session_id     : ctx.sessionId || null,
        answered_at    : now,
        interval_code  : updateSchedule ? plan.interval_code : (atom.interval_code || null),
        srs_step_after : updateSchedule ? plan.srs_step : (atom.srs_step || 0),
        schedule_updated: updateSchedule,
        /* 期日前に間違えて戻した肢は、あとから見分けられるようにしておく */
        early_miss     : !!decision.demote
      };

      return S.commitAnswer(atomId, patch, log).then(function () {
        return S.getLogsByAtom(atomId);
      }).then(function (logs) {
        var w = computeWeaknessFromLogs(logs, atom);
        return S.updateAtom(atomId, { weakness_pt: w.pt, hard_streak: w.hard_streak }).then(function (saved) {
          /* 10分・1時間の超早期復習に落ちた肢は、割り込み候補として拾う */
          if (updateSchedule && plan.eval === EVAL.HARD &&
              (plan.interval_code === '10m' || plan.interval_code === '1h')) {
            Interrupt.note(saved, mode);
          }
          return {
            skipped: false,
            atom: saved,
            plan: plan,
            weakness: w,
            schedule_updated: updateSchedule,
            mode: mode
          };
        });
      });
    });
  }

  /* 1問（複数アトム）ぶんの評価をまとめて適用する。
     evaluations = [{ atom_id, eval, is_correct }] */
  function applyQuestionEvaluations(qId, evaluations, ctx) {
    ctx = ctx || {};
    var list = Array.isArray(evaluations) ? evaluations : [];
    var seq = Promise.resolve();
    var results = [];

    list.forEach(function (e) {
      seq = seq.then(function () {
        return applyEvaluation(e.atom_id, e.eval, {
          mode: ctx.mode, isCorrect: e.is_correct, sessionId: ctx.sessionId,
          now: ctx.now, boundaryHour: ctx.boundaryHour, force: ctx.force
        }).then(function (r) { results.push(r); });
      });
    });

    return seq.then(function () {
      if (has(NO_RECORD_MODES, ctx.mode)) { return { results: results, recorded: false }; }
      return recordQuestionAnswered(qId, ctx.mode).then(function (meta) {
        return { results: results, recorded: true, progress: meta };
      });
    });
  }

  /* 1問を解き終えたときの共通後処理。
     ・延べ解答数のカウント（Level 2の分母）
     ・分析スキャン精度の分子（ユニーク問題）
     ・トピックガードへの登録 */
  function recordQuestionAnswered(qId, mode) {
    if (has(NO_RECORD_MODES, mode)) { return Promise.resolve(null); }

    return S.getAtomsByQuestion(qId).then(function (atoms) {
      var tagSet = {}, tags = [];
      atoms.forEach(function (a) {
        (a.tags || []).forEach(function (t) {
          if (!tagSet[t]) { tagSet[t] = 1; tags.push(t); }
        });
      });

      return S.getMeta('total_questions_answered', 0).then(function (total) {
        return S.setMeta('total_questions_answered', (total || 0) + 1);
      }).then(function () {
        return S.recordScanProgress(qId);
      }).then(function (scan) {
        return S.pushGuard(qId, tags).then(function () {
          return { scan: scan, tags: tags };
        });
      });
    });
  }

  /* ---- 模試の履歴連動 自動昇格／安全降格（第11章③） ----
   * 【正解 ＋ 根拠ON】
   *   パターンA（初見 または 過去『難』『普』）      → [易] 30日後 / 80pt
   *   パターンB（すでに『簡単30日以上』へ到達済み） → [マ] 180日後 / 100pt
   * 【不正解 または 根拠OFF】
   *   過去のステップに関わらず一律 [難] 10分後 / 0pt へ安全降格
   */
  function applyExamResult(atomId, outcome, ctx) {
    ctx = ctx || {};
    var correct = !!(outcome && outcome.correct);
    var groundOn = !!(outcome && outcome.ground_on);

    return S.getAtom(atomId).then(function (atom) {
      if (!atom) { throw new Error('選択肢が見つかりません: ' + atomId); }

      var pattern, evalKey;
      if (correct && groundOn) {
        if (isMasterUnlocked(atom) && atom.last_eval === EVAL.EASY) {
          pattern = 'B'; evalKey = EVAL.MASTER;
        } else {
          pattern = 'A'; evalKey = EVAL.EASY;
          /* パターンAは「初見または過去『難』『普』」を必ず 30日後 に置く。
             梯子を1段ずつ昇らせず、仕様どおり直接 30d へ確定させる。 */
        }
      } else {
        pattern = 'C'; evalKey = EVAL.HARD;
      }

      var now = isNum(ctx.now) ? ctx.now : nowMs();
      var boundary = isNum(ctx.boundaryHour) ? ctx.boundaryHour : 4;
      var forcedIdx = (evalKey === EVAL.MASTER) ? STEP_INDEX['180d']
                    : (evalKey === EVAL.EASY)   ? STEP_INDEX['30d']
                    :                             STEP_INDEX['10m'];

      var patch = {
        last_eval        : evalKey,
        last_answered_at : now,
        answer_count     : (atom.answer_count || 0) + 1,
        correct_count    : (atom.correct_count || 0) + (correct ? 1 : 0),
        srs_step         : forcedIdx + 1,
        interval_code    : stepToCode(forcedIdx),
        due_date         : computeDueDate(now, forcedIdx, boundary,
                                          examCapMs(ctx.meta, now, boundary))
      };

      var log = {
        eval            : evalKey,
        is_correct      : correct,
        mode            : 'exam',
        session_id      : ctx.sessionId || null,
        answered_at     : now,
        interval_code   : patch.interval_code,
        srs_step_after  : patch.srs_step,
        schedule_updated: true,
        exam_pattern    : pattern,
        ground_on       : groundOn
      };

      return S.commitAnswer(atomId, patch, log).then(function () {
        return S.getLogsByAtom(atomId);
      }).then(function (logs) {
        var w = computeWeaknessFromLogs(logs, atom);
        return S.updateAtom(atomId, { weakness_pt: w.pt, hard_streak: w.hard_streak });
      }).then(function (saved) {
        return {
          atom: saved, pattern: pattern, eval: evalKey,
          concept_point: EVAL_POINTS[evalKey],
          interval_code: patch.interval_code,
          due_date: patch.due_date
        };
      });
    });
  }

  /* ======================================================================
   * 5. 初期点灯（推奨評価）ルール（第4章③）
   * ====================================================================== */

  /* atoms         : そのアトム配列（original_num 昇順）
   * selectedNums  : ユーザーが選んだ選択肢番号の配列（1始まり）
   * 戻り値        : { atom_id: {eval, master_enabled, reason} } */
  function recommendEvaluations(atoms, selectedNums) {
    var list = Array.isArray(atoms) ? atoms : [];
    var picked = Array.isArray(selectedNums) ? selectedNums : [];

    var correctNums = list.filter(function (a) { return a.is_correct; })
                          .map(function (a) { return a.original_num; });
    var isFirstTime = list.every(function (a) { return !a.answer_count; });
    var answeredRight =
      correctNums.length === picked.length &&
      correctNums.every(function (n) { return picked.indexOf(n) >= 0; });

    var out = {};
    list.forEach(function (a) {
      var prev = a.last_eval || EVAL.NORMAL;
      var val, reason;

      if (isFirstTime && answeredRight) {
        val = EVAL.NORMAL; reason = '初見・正解';
      } else if (isFirstTime && !answeredRight) {
        val = EVAL.HARD;   reason = '初見・不正解';
      } else if (!isFirstTime && answeredRight) {
        val = prev;        reason = '既出・正解（前回の評価を維持）';
      } else {
        var wasPicked = picked.indexOf(a.original_num) >= 0;
        if (wasPicked || a.is_correct) {
          /* 間違えて選んだ誤答肢 と 正解肢 は強制的に「難しい」へ上書き */
          val = EVAL.HARD; reason = '既出・不正解（誤答肢／正解肢を強制リセット）';
        } else {
          val = prev; reason = '既出・不正解（無関係な不選択肢は前回評価を維持）';
        }
      }

      var masterOk = isMasterUnlocked(a);
      if (val === EVAL.MASTER && !masterOk) { val = EVAL.EASY; }

      out[a.atom_id] = {
        atom_id: a.atom_id,
        original_num: a.original_num,
        eval: val,
        master_enabled: masterOk,
        reason: reason,
        preview: previewInterval(a, val)
      };
    });

    return { recommendations: out, is_first_time: isFirstTime, answered_right: answeredRight };
  }

  /* 評価ボタンごとの「次はいつ出るか」を先読みして返す（UIのラベル用） */
  function previewInterval(atom, evalKey) {
    var plan = planSchedule(atom, evalKey, { now: nowMs() });
    return { interval_code: plan.interval_code, label: plan.interval_label };
  }

  function previewAllIntervals(atom) {
    var out = {};
    [EVAL.HARD, EVAL.NORMAL, EVAL.EASY, EVAL.MASTER].forEach(function (k) {
      if (k === EVAL.MASTER && !isMasterUnlocked(atom)) {
        out[k] = { interval_code: null, label: '30日以上で解禁', enabled: false };
        return;
      }
      var plan = planSchedule(atom, k, { now: nowMs() });
      out[k] = { interval_code: plan.interval_code, label: plan.interval_label, enabled: true };
    });
    return out;
  }

  /* ======================================================================
   * 6. トピックガード（第9章②）
   * ====================================================================== */

  /* 直近30分に解答した問題のタグと衝突する候補を除外する。
     除外の結果0件になったら、最も古いトピックから順にガードを解除して
     再試行する（FIFO安全パージ）。出題フリーズは構造的に起こらない。 */
  function applyTopicGuard(candidates, options) {
    options = options || {};
    var enabled = options.enabled !== false;
    var windowMs = isNum(options.windowMs) ? options.windowMs : GUARD_WINDOW_MS;

    if (!enabled || !candidates.length) {
      return Promise.resolve({ list: candidates, purged: 0, guarded: 0, disabled: !enabled });
    }

    var purged = 0;
    var attempts = 0;
    var MAX_ATTEMPTS = 24;

    function step() {
      attempts++;
      if (attempts > MAX_ATTEMPTS) {
        return Promise.resolve({ list: candidates, purged: purged, guarded: 0, exhausted: true });
      }
      return S.getGuardTags(windowMs).then(function (g) {
        if (!g.tags.length) {
          return { list: candidates, purged: purged, guarded: 0 };
        }
        var blocked = {};
        g.tags.forEach(function (t) { blocked[t] = 1; });

        var filtered = candidates.filter(function (c) {
          var tags = c.tags || [];
          for (var i = 0; i < tags.length; i++) { if (blocked[tags[i]]) { return false; } }
          return true;
        });

        if (filtered.length) {
          return { list: filtered, purged: purged, guarded: candidates.length - filtered.length };
        }
        /* 候補が枯渇：最古のトピックを1件解除して再試行 */
        return S.purgeOldestGuard(1).then(function (n) {
          if (!n) { return { list: candidates, purged: purged, guarded: 0, exhausted: true }; }
          purged += n;
          return step();
        });
      });
    }

    return step();
  }

  /* ======================================================================
   * 7. 出題キューの構築
   * ====================================================================== */

  /* アトム配列を「問題単位の候補」へ畳み込む。
     問題の優先度は、その問題が抱える最も弱いアトムで代表させる。 */
  function foldAtomsToCandidates(atoms, weakMap, preferFrequent) {
    var byQ = {};
    var order = [];

    atoms.forEach(function (a) {
      if (!byQ[a.q_id]) {
        byQ[a.q_id] = {
          q_id: a.q_id, rank: a.rank, unit: a.unit, major: a.major,
          medium: a.medium, sub_item: a.sub_item, num_code: a.num_code,
          atoms: [], tags: [], tagSet: {},
          unlearned: 0, max_priority: 0, sum_priority: 0,
          min_due: null, min_urgency: 99,
          /* 直前10日モード用（V1.30）。必修かどうかと、手応えの目安。 */
          hissu: isHissu(a.unit), mastered: 0, last_seen: 0
        };
        order.push(a.q_id);
      }
      var c = byQ[a.q_id];
      c.atoms.push(a);

      (a.tags || []).forEach(function (t) {
        if (!c.tagSet[t]) { c.tagSet[t] = 1; c.tags.push(t); }
      });

      var w = weakMap ? weakMap[a.atom_id] : null;
      var unlearned = w ? w.unlearned : !a.answer_count;
      if (unlearned) { c.unlearned++; }

      if (a.last_eval === EVAL.MASTER || a.last_eval === EVAL.EASY) { c.mastered++; }
      if (isNum(a.last_answered_at) && a.last_answered_at > c.last_seen) {
        c.last_seen = a.last_answered_at;
      }

      var p = priorityScore(a, w, preferFrequent);
      if (p > c.max_priority) { c.max_priority = p; }
      c.sum_priority += p;

      if (isNum(a.due_date)) {
        if (c.min_due === null || a.due_date < c.min_due) { c.min_due = a.due_date; }
      }
      var u = URGENCY_ORDER[a.interval_code];
      if (isNum(u) && u < c.min_urgency) { c.min_urgency = u; }
    });

    return order.map(function (k) { return byQ[k]; });
  }

  /* 出題優先度ソート。
     未学習アトムを含む問題を最上位に据え、以降は弱点優先度の降順。 */
  /* 「必修問題」かどうか。単元名に『必修』が入っていれば必修とみなす。
     模試の必修判定（80%以上）と同じ見分け方に揃えてある。 */
  function isHissu(unit) {
    return String(unit || '').indexOf('必修') >= 0;
  }

  /* --- 直前10日モードの並べ替え（V1.30） -------------------------------
   *
   * 【なぜ順番を変えるか】
   *   通常は弱点が濃い順に出す（覚えていないものほど先）。これは学習効率には
   *   正しいが、直前10日にやると【できない問題ばかり浴びる】ことになる。
   *   本番前に必要なのは、新しい知識より「解ける」という手応えなので、
   *   ここだけ狙いを切り替える。
   *
   * 【必修を最優先にする理由】
   *   必修は50問中40問（8割）という絶対基準で、1問でも足りなければ
   *   一般・状況設定が何点でも不合格になる。落としてはいけない配点が
   *   最も大きいのは必修なので、直前の時間はここへ寄せる。
   *
   * 【しばらく見ていない＝マスターしたもの、を混ぜる理由】
   *   長い間隔まで上がった肢は「覚えている」と判定されたもの。
   *   直前に一度当てておくと、取りこぼしの確認と自信の両方になる。
   *
   * 【未学習を後ろへ下げる理由（除外はしない）】
   *   直前に初見を大量に浴びると手応えが崩れる。ただし完全に切ると
   *   「手つかずの範囲を最後まで知らないまま本番」になるので、
   *   除外はせず順番だけ下げる。
   * ------------------------------------------------------------------ */
  function finalScore(c, now) {
    var s = 0;
    if (c.hissu) { s += 1000; }
    /* 手応え：マスター寄りの肢が多い問題ほど前へ */
    if (c.atoms.length) { s += (c.mastered / c.atoms.length) * 120; }
    /* しばらく見ていないほど前へ（60日で頭打ち） */
    if (c.last_seen) {
      s += Math.min(60, Math.floor((now - c.last_seen) / DAY));
    }
    /* 未学習は後ろへ */
    if (c.unlearned > 0) { s -= 300; }
    return s;
  }

  function sortCandidates(cands, preferFrequent, opts) {
    opts = opts || {};
    if (opts.phase === 'final') {
      var now = isNum(opts.now) ? opts.now : nowMs();
      return cands.slice().sort(function (a, b) {
        var d = finalScore(b, now) - finalScore(a, now);
        if (d !== 0) { return d; }
        var rw = rankWeight(b.rank) - rankWeight(a.rank);
        if (rw !== 0) { return rw; }
        return String(a.num_code || '').localeCompare(String(b.num_code || ''));
      });
    }
    return cands.slice().sort(function (a, b) {
      if (a.unlearned !== b.unlearned) { return b.unlearned - a.unlearned; }
      if (b.max_priority !== a.max_priority) { return b.max_priority - a.max_priority; }
      if (b.sum_priority !== a.sum_priority) { return b.sum_priority - a.sum_priority; }
      var rw = rankWeight(b.rank) - rankWeight(a.rank);
      if (preferFrequent && rw !== 0) { return rw; }
      return String(a.num_code || '').localeCompare(String(b.num_code || ''));
    });
  }

  function shuffle(arr, seed) {
    var a = arr.slice();
    var s = isNum(seed) ? seed : nowMs();
    var i, j, t;
    for (i = a.length - 1; i > 0; i--) {
      s = (s * 1103515245 + 12345) & 0x7fffffff;
      j = s % (i + 1);
      t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  /* --- 本日の復習（第5章①） ---
     期日を迎えたアトムを「次回指定インターバルが短い順」の緊急度昇順で出す。
     due_date 昇順ではなく interval_code 昇順が正であることに注意。 */
  function getReviewQueue(limit) {
    var now = nowMs();
    return S.getDueAtoms(now).then(function (atoms) {
      var sorted = atoms.slice().sort(function (a, b) {
        var ua = isNum(URGENCY_ORDER[a.interval_code]) ? URGENCY_ORDER[a.interval_code] : 99;
        var ub = isNum(URGENCY_ORDER[b.interval_code]) ? URGENCY_ORDER[b.interval_code] : 99;
        if (ua !== ub) { return ua - ub; }
        return (a.due_date || 0) - (b.due_date || 0);
      });

      /* 期日を迎えた肢を、問題ごとに数えて持っておく。
         「期日の肢が何本か」で出題形式（4択／一問一答）が決まるため、
         畳んだ時点で捨ててしまうと、画面側でもう一度DBを引くことになる。 */
      var seen = {}, qIds = [], dueByQ = {};
      sorted.forEach(function (a) {
        if (!dueByQ[a.q_id]) { dueByQ[a.q_id] = []; }
        dueByQ[a.q_id].push(a.atom_id);
        if (!seen[a.q_id]) { seen[a.q_id] = 1; qIds.push(a.q_id); }
      });
      if (isNum(limit) && limit > 0) { qIds = qIds.slice(0, limit); }

      return S.getQuestionsFull(qIds).then(function (questions) {
        var rank = {};
        qIds.forEach(function (id, i) { rank[id] = i; });
        questions.sort(function (x, y) { return rank[x.q_id] - rank[y.q_id]; });
        questions.forEach(function (q) { q.due_atom_ids = dueByQ[q.q_id] || []; });
        return {
          mode: 'review',
          questions: questions,
          due_by_question: dueByQ,
          due_atoms: sorted.length,
          due_questions: qIds.length,
          guard: { disabled: true, reason: '本日の復習ではトピックガードを適用しません' }
        };
      });
    });
  }

  /* ======================================================================
   * 出題形式の自動選択（V1.23）
   *
   * 期日の肢が1本だけなら、残りの3本は仕上がっている。そこを4択で出すと、
   * 読む必要のない3肢まで毎回考えることになる。逆に期日の肢が2本以上なら、
   * 問題文を1回読んで2肢ぶん以上を回収できるので4択のほうが安い。
   * ・時間コストの分岐点は3本（S=問題文、A=1肢として S+4A < 3S+3A）
   * ・2本はほぼ互角なので、比較練習の価値で4択へ倒す（既定の閾値＝2）
   * 分割可否（13列目）が false の問題は、何本であろうと必ず4択。
   * ====================================================================== */

  var FORMAT = { MULTI: 'multi', SINGLE: 'single' };

  /* opts = { threshold: 1|2|3, alwaysMulti: bool } */
  function pickFormat(question, dueAtomIds, opts) {
    opts = opts || {};
    var th = isNum(opts.threshold) ? opts.threshold : 2;
    var due = Array.isArray(dueAtomIds) ? dueAtomIds.length : 0;

    if (opts.alwaysMulti) { return { format: FORMAT.MULTI, reason: 'always-multi', due: due }; }
    if (!question || !question.is_splittable) {
      return { format: FORMAT.MULTI, reason: 'not-splittable', due: due };
    }
    if (question.question_type !== 'single') {
      /* 複数選択・数値問題は1肢に切り出しても設問が成立しない */
      return { format: FORMAT.MULTI, reason: 'question-type', due: due };
    }
    if (due < 1) { return { format: FORMAT.MULTI, reason: 'no-due', due: due }; }
    if (due >= th) { return { format: FORMAT.MULTI, reason: 'due-ge-threshold', due: due }; }
    return { format: FORMAT.SINGLE, reason: 'due-lt-threshold', due: due };
  }

  /* --- 汎用キュー（新規／ランダム／単元別／弱点／概念ノック） --- */
  /* 克服モードの「上位帯」の広さ。出題数の何倍まで候補に入れるか。 */
  var CONQUER_BAND = 3;

  /* 並び済みの上位帯から、点数に比例した重みで count 件を選ぶ（重複なし）。
     点数0のものにも 1 の下駄を履かせるのは、帯の末尾が絶対に
     出ないと「ここから先は永久に出ない」帯ができてしまうため。 */
  function weightedPick(sorted, count, bandFactor) {
    var band = sorted.slice(0, Math.max(count, count * (bandFactor || 3)));
    if (band.length <= count) { return band.slice(0, count); }

    var pool = band.slice();
    var out = [];
    while (out.length < count && pool.length) {
      var total = 0, i;
      for (i = 0; i < pool.length; i++) { total += (Number(pool[i].max_priority) || 0) + 1; }
      var r = Math.random() * total, acc = 0, hit = pool.length - 1;
      for (i = 0; i < pool.length; i++) {
        acc += (Number(pool[i].max_priority) || 0) + 1;
        if (r <= acc) { hit = i; break; }
      }
      out.push(pool[hit]);
      pool.splice(hit, 1);
    }
    return out;
  }

  function buildQueue(options) {
    options = options || {};
    var mode = options.mode || 'random';
    var count = isNum(options.count) && options.count > 0 ? options.count : 10;

    if (mode === 'review') { return getReviewQueue(count); }

    return S.loadMeta().then(function (meta) {
      var preferFrequent = (options.preferFrequent !== undefined && options.preferFrequent !== null)
        ? !!options.preferFrequent
        : !!meta.prefer_frequent;

      var loader;
      if (Array.isArray(options.qIds) && options.qIds.length) {
        loader = Promise.all(options.qIds.map(function (id) { return S.getAtomsByQuestion(id); }))
          .then(function (groups) {
            return groups.reduce(function (acc, g) { return acc.concat(g); }, []);
          });
      } else if (options.tag) {
        loader = S.getAtomsByTag(options.tag);
      } else if (options.scope && options.scope.field && options.scope.value) {
        loader = S.getAtomsByScope(options.scope.field, options.scope.value);
      } else {
        loader = S.getAllAtoms();
      }

      return loader.then(function (atoms) {
        if (!atoms.length) {
          return { mode: mode, questions: [], reason: '出題できる問題がありません', guard: null };
        }

        var ids = atoms.map(function (a) { return a.atom_id; });
        return S.getLogMapByAtoms(ids).then(function (logMap) {
          var weakMap = {};
          atoms.forEach(function (a) {
            weakMap[a.atom_id] = computeWeaknessFromLogs(logMap[a.atom_id] || [], a);
          });

          /* --- 「知識として既習か」を中項目で見る（V1.52） ---
             問題そのものを解いたかどうかと、その知識を学んだかどうかは別。
             本番で問われるのは【文字は初見だが知識は既習】がほとんどで、
             この区別が無いと模試の難しさを本番に寄せられない。

             単位に小項目ではなく中項目を使う理由は2つ。
             ① いまのデータは349小項目に453問＝1小項目あたり1.3問しかなく、
                小項目で見ると「解いた＝その小項目の全部」になり、区別として働かない。
             ② 学習は中項目のまとまりで進む。「人口静態・人口動態」を一通りやった人にとって、
                その中の別の問題は【知識としては既習】に近い。 */
          var cands = foldAtomsToCandidates(atoms, weakMap, preferFrequent);

          /* 学習済みの中項目を、畳んだあとの候補から拾う。
             アトムのレコードは中項目を持っていないので、ここで作る
             （持っていない項目を参照しても静かに空になるだけで、
               気づけないまま familiar が常にゼロになる）。 */
          var learnedScope = {};
          cands.forEach(function (c) {
            if (c.medium && c.unlearned < c.atoms.length) { learnedScope[c.medium] = 1; }
          });

          cands.forEach(function (c) {
            c.solved   = (c.unlearned === 0);                     /* 全部の肢を解いた */
            c.familiar = !c.solved && !!learnedScope[c.medium];   /* 知識は既習・問題は初見 */
          });

          /* options.newOnly は「ランダムモードを初見だけにする」ための入口。
             mode を 'new' に変えてしまうと割り込み許可判定やトピックガードの
             扱いまで一緒に変わるため、フィルタだけを共有する。 */
          if (mode === 'new' || options.newOnly) {
            cands = cands.filter(function (c) { return c.unlearned > 0; });
          }
          if (mode === 'weak') {
            cands = cands.filter(function (c) { return c.unlearned > 0 || c.max_priority > 0; });
          }
          /* --- 克服モード（V1.41） ---
             未学習が0になったあとのランダムモードの顔。
             「一度触れた」だけで覚えたことにはならないので、
             苦手なものから出し直す。
             マスター済み（0pt）は仕様§6-②で弱点判定から外れるので、
             ここでも候補から落とす。全部マスターしたら候補0になり、
             呼び出し側が行き止まりの案内を出す。 */
          if (mode === 'conquer') {
            cands = cands.filter(function (c) { return c.max_priority > 0; });
          }
          /* --- ランクで絞る（V1.50・直前モード用） ---
             本番の出題も基本問題が中心なので、S/A に寄せても
             「本番よりずっと易しい」にはならない。C を外すのが主な効果。 */
          if (Array.isArray(options.ranks) && options.ranks.length) {
            var okRank = {};
            options.ranks.forEach(function (rk) { okRank[String(rk).toUpperCase()] = 1; });
            cands = cands.filter(function (c) { return okRank[String(c.rank || 'B').toUpperCase()]; });
          }
          if (!cands.length) {
            return { mode: mode, questions: [], reason: '条件に合う問題が残っていません', guard: null };
          }

          /* 概念別弱点ノックは、トピックガードを一時無効化して集中出題する */
          var guardEnabled = !has(GUARD_DISABLED_MODES, mode) && options.applyGuard !== false;

          return applyTopicGuard(cands, {
            enabled: guardEnabled,
            windowMs: isNum(options.guardWindowMs) ? options.guardWindowMs : GUARD_WINDOW_MS
          }).then(function (g) {
            var pool = g.list;
            var picked;

            if (options.shuffle && options.mix) {
              /* --- 3つに分けて混ぜる（V1.52。V1.51の2分類を置き換え） ---
                 V1.51 は「解いた／解いていない」の2分類だった。
                 これでは本番に寄せられない。本番で出るのは
                 【文字は初見だが知識は既習】がほとんどだからで、
                 2分類ではそこを表せない。

                   solved   … 全部の肢を解いた問題。記憶で解けてしまう
                   familiar … 同じ小項目を学習済みだが、この問題は初見（本番に最も近い）
                   novel    … その小項目をまだ学んでいない（本番より難しい）

                 足りない分は familiar → solved → novel の順で埋める。
                 本番に近い側を優先して埋め、数は減らさない。 */
              var want = {
                solved:   Math.round(count * (options.mix.solved   || 0)),
                familiar: Math.round(count * (options.mix.familiar || 0)),
                novel:    Math.round(count * (options.mix.novel    || 0))
              };
              var bucket = {
                solved:   shuffle(pool.filter(function (c) { return c.solved; }), options.seed),
                familiar: shuffle(pool.filter(function (c) { return c.familiar; }), options.seed),
                novel:    shuffle(pool.filter(function (c) { return !c.solved && !c.familiar; }), options.seed)
              };
              var taken = [], used = { solved: 0, familiar: 0, novel: 0 };
              ['familiar', 'solved', 'novel'].forEach(function (k) {
                var n = Math.min(want[k], bucket[k].length);
                taken = taken.concat(bucket[k].slice(0, n));
                used[k] = n;
              });
              ['familiar', 'solved', 'novel'].forEach(function (k) {
                if (taken.length >= count) { return; }
                var more = bucket[k].slice(used[k], used[k] + (count - taken.length));
                taken = taken.concat(more);
                used[k] += more.length;
              });
              picked = shuffle(taken, options.seed).slice(0, count);
            } else if (options.shuffle) {
              var un, rest;
              if (options.preferKnown) {
                /* --- 直前モード（V1.50） ---
                   目的は実力測定ではなく【成功体験】。
                   一度でも「易しい／マスター」を付けた肢を含む問題を前に出す。
                   初見をぶつけない。ただし合格基準は本番と同じまま変えない
                   （基準まで甘くすると達成感が偽物になり、当日に効かない）。 */
                un   = shuffle(pool.filter(function (c) { return c.mastered > 0; }), options.seed);
                rest = shuffle(pool.filter(function (c) { return c.mastered === 0; }), options.seed);
              } else {
                /* 純ランダム指定時も、未学習だけは前方に寄せる */
                un   = shuffle(pool.filter(function (c) { return c.unlearned > 0; }), options.seed);
                rest = shuffle(pool.filter(function (c) { return c.unlearned === 0; }), options.seed);
              }
              picked = un.concat(rest).slice(0, count);
            } else {
              /* 直前10日は狙いが変わる。本日の復習は期日順のままで、
                 ここ（新規・ランダム・弱点）だけ並べ替えを差し替える。 */
              var phase = examPhase(meta, nowMs(), meta.day_boundary_hour);
              var sorted = sortCandidates(pool, preferFrequent,
                                          { phase: phase, now: nowMs() });
              /* 克服モードは【上位帯からの重み付き抽出】にする。
                 単純な降順の先頭N件だと、
                   ・毎回まったく同じ顔ぶれになって飽きる
                   ・2番手以降がいつまでも出てこない
                 という2つが同時に起きる。苦手なものほど出やすいまま、
                 顔ぶれだけを揺らすのが狙い。帯の広さは3倍（実測ではなく
                 設計値：狭いと1番と同じ、広いと得意なものが混ざりすぎる）。 */
              picked = (mode === 'conquer')
                ? weightedPick(sorted, count, CONQUER_BAND)
                : sorted.slice(0, count);
            }

            var qIds = picked.map(function (c) { return c.q_id; });
            return S.getQuestionsFull(qIds).then(function (questions) {
              var order = {};
              qIds.forEach(function (id, i) { order[id] = i; });
              questions.sort(function (x, y) { return order[x.q_id] - order[y.q_id]; });
              return {
                mode: mode,
                questions: questions,
                candidates: pool.length,
                prefer_frequent: preferFrequent,
                exam_phase: examPhase(meta, nowMs(), meta.day_boundary_hour),
                exam_remaining_days: examRemainingDays(meta, nowMs(), meta.day_boundary_hour),
                guard: {
                  enabled: guardEnabled,
                  excluded: g.guarded || 0,
                  purged: g.purged || 0,
                  exhausted: !!g.exhausted
                },
                priorities: picked.map(function (c) {
                  return {
                    q_id: c.q_id, rank: c.rank, unlearned: c.unlearned,
                    priority: Math.round(c.max_priority * 10) / 10
                  };
                })
              };
            });
          });
        });
      });
    });
  }

  /* --- 概念別弱点ノック（第7章） ---
     理解率が最も低い概念タグに紐づくアトムを集中的に抽出する。
     トピックガードは無効、忘却スケジュールは更新しない独立モード。 */
  function getKnockQueue(tag, options) {
    options = options || {};
    var minutes = isNum(options.minutes) ? options.minutes : 5;
    /* 1問あたり約20秒として、時間内に解ききれる余裕を持った件数を用意する */
    var count = isNum(options.count) ? options.count : Math.max(6, Math.round(minutes * 3));

    var pickTag = tag
      ? Promise.resolve(tag)
      : getConceptRanking({ onlyEvaluated: true }).then(function (r) {
          return r.length ? r[0].tag : null;
        });

    return pickTag.then(function (t) {
      if (!t) {
        return { mode: 'knock', questions: [], tag: null, minutes: minutes,
                 reason: 'まだ評価が入力されていないため、克服対象の概念を決められません' };
      }
      return buildQueue({
        mode: 'knock', tag: t, count: count,
        applyGuard: false, preferFrequent: options.preferFrequent
      }).then(function (q) {
        q.tag = t;
        q.minutes = minutes;
        q.duration_ms = minutes * 60 * 1000;
        q.schedule_frozen = true;
        return q;
      });
    });
  }

  /* ======================================================================
   * 8. 74概念理解率（第12章②③）
   * ====================================================================== */

  /* 該当タグが紐づくアトムのうち、1度以上評価が入力されたアトムだけを対象に
     最新評価（難0/普50/易80/マ100）の平均を取る。
     全アトムが未評価の概念は score = null のまま保持し、
     「未学習」と「理解率0%」が混同されるのを構造的に防ぐ。 */
  function recomputeConceptScores() {
    return S.getAllAtoms().then(function (atoms) {
      var acc = {};

      function bucket(tag) {
        if (!acc[tag]) { acc[tag] = { sum: 0, evaluated: 0, atom_count: 0 }; }
        return acc[tag];
      }

      atoms.forEach(function (a) {
        (a.tags || []).forEach(function (t) {
          var b = bucket(t);
          b.atom_count++;
          var pt = EVAL_POINTS[a.last_eval];
          if (a.last_eval && isNum(pt)) {
            b.sum += pt;
            b.evaluated++;
          }
        });
      });

      /* マスター辞書側に定義があるがデータが1件も無い概念も、
         score=null / atom_count=0 として必ず台帳に載せる */
      var master = global.CONCEPT_TAGS_MASTER;
      if (Array.isArray(master)) {
        master.forEach(function (def) { bucket(def.tag); });
      }

      var map = {};
      Object.keys(acc).forEach(function (t) {
        var b = acc[t];
        map[t] = {
          score: b.evaluated > 0 ? Math.round(b.sum / b.evaluated) : null,
          evaluated_count: b.evaluated,
          atom_count: b.atom_count
        };
      });

      return S.saveConceptScores(map).then(function () { return map; });
    });
  }

  /* 理解率ランキング。
     order: 'low'（既定・昇順）| 'high'（降順）| 'unlearned'（未評価のみ） */
  function getConceptRanking(options) {
    options = options || {};
    var order = options.order || 'low';
    var onlyEvaluated = options.onlyEvaluated !== false && order !== 'unlearned';

    return S.getConceptStats().then(function (rows) {
      var list = rows.slice();

      if (order === 'unlearned') {
        return list
          .filter(function (r) { return r.score === null || r.score === undefined; })
          .sort(function (a, b) { return (b.atom_count || 0) - (a.atom_count || 0); });
      }

      if (onlyEvaluated) {
        list = list.filter(function (r) { return isNum(r.score); });
      }
      if (options.withAtomsOnly) {
        list = list.filter(function (r) { return (r.atom_count || 0) > 0; });
      }

      /* 評価済と未評価を必ず分けて整列する。
         null を数値扱い（999など）で同じ配列に混ぜると、降順指定のときに
         未評価の概念が「理解率が最も高い」扱いで先頭に来てしまうため。
         未評価は常に末尾へ回し、アトム数の多い順に並べる。 */
      var known = list.filter(function (r) { return isNum(r.score); });
      var unknown = list.filter(function (r) { return !isNum(r.score); });

      known.sort(function (a, b) {
        if (a.score !== b.score) { return order === 'high' ? (b.score - a.score) : (a.score - b.score); }
        return (b.atom_count || 0) - (a.atom_count || 0);
      });
      unknown.sort(function (a, b) { return (b.atom_count || 0) - (a.atom_count || 0); });

      return known.concat(unknown);
    });
  }

  /* 最優先克服概念 TOP 3（第12章③）
     score !== null かつ 50%未満 に限定して下位3件を返す。
     未評価（null）を混ぜないことで、手つかずの概念が「最弱」と
     誤って提示されるのを防ぐ。 */
  function getTop3Concepts() {
    return getConceptRanking({ order: 'low', onlyEvaluated: true }).then(function (list) {
      return list.filter(function (r) { return isNum(r.score) && r.score < 50; }).slice(0, 3);
    });
  }

  /* ======================================================================
   * 9. 分析スキャン精度（第8章②）
   * ====================================================================== */

  /* 分母は Math.min(全登録問題数, 60)。
     問題が60問未満のときに分母0や100%超えが起きないようガードする。 */
  function getScanAccuracy() {
    return S.getScanProgress().then(function (p) {
      return {
        answered: p.answered,
        denominator: p.denominator,
        model_size: SCAN_MODEL_SIZE,
        pct: p.pct,
        total_questions: p.total_questions,
        complete: p.denominator > 0 && p.answered >= p.denominator
      };
    });
  }

  function recordScan(qId) {
    return S.recordScanProgress(qId).then(function (p) {
      return {
        answered: p.answered, denominator: p.denominator,
        pct: p.pct, total_questions: p.total_questions,
        complete: p.denominator > 0 && p.answered >= p.denominator
      };
    });
  }

  /* ======================================================================
   * 10. 5段階レベル ＆ 不退転ハイウォーターマーク（第9章③）
   * ====================================================================== */

  /* マイルストーン梯子の達成率。
     単純な「最終目標に対する割合」ではなく、段の到達数で数える。
     100問到達で 2/4 ではなく 1/4＝25% と見せることで、
     長いLevel 2で進捗が止まって見えるのを防ぐ。 */
  function milestonePct(value, milestones) {
    var n = milestones.length;
    var i;
    for (i = 0; i < n; i++) {
      if (value < milestones[i]) {
        var prev = i === 0 ? 0 : milestones[i - 1];
        var frac = (value - prev) / (milestones[i] - prev);
        return clamp(((i + frac) / n) * 100, 0, 100);
      }
    }
    return 100;
  }

  function computeLevelRaw() {
    return Promise.all([
      S.getAllAtoms(),
      S.getMeta('total_questions_answered', 0),
      getScanAccuracy()
    ]).then(function (r) {
      var atoms = r[0];
      var totalAnswered = r[1] || 0;
      var scan = r[2];

      var totalAtoms = atoms.length;
      var unlearned = 0, hardOrNormal = 0, mastered = 0, evaluated = 0;
      var qSeen = {}, uniqueQ = 0;

      atoms.forEach(function (a) {
        if (!a.answer_count) { unlearned++; }
        else if (!qSeen[a.q_id]) { qSeen[a.q_id] = 1; uniqueQ++; }

        if (a.last_eval) {
          evaluated++;
          if (a.last_eval === EVAL.HARD || a.last_eval === EVAL.NORMAL) { hardOrNormal++; }
          if (a.last_eval === EVAL.MASTER) { mastered++; }
        }
      });

      /* Level 1 は分析スキャン精度に直結させる。
         60問固定にすると、登録問題数が60未満のデータセットでは
         Level 1 を永久にクリアできなくなるため、
         分母ガード済みの scan.pct（10問=16% / 20問=33% / 到達で100%）を採用する。 */
      var l1Done = scan.pct >= 100 && scan.total_questions > 0;
      var l2Done = totalAnswered >= 1000;
      var l3Done = totalAtoms > 0 && unlearned === 0;
      var l4Done = totalAtoms > 0 && unlearned === 0 && hardOrNormal === 0;
      var l5Done = totalAtoms > 0 && mastered === totalAtoms;

      var pcts = {
        1: scan.pct,
        2: milestonePct(totalAnswered, LEVEL_DEFS[1].milestones),
        3: totalAtoms > 0 ? ((totalAtoms - unlearned) / totalAtoms) * 100 : 0,
        4: totalAtoms > 0 ? ((totalAtoms - unlearned - hardOrNormal) / totalAtoms) * 100 : 0,
        5: totalAtoms > 0 ? (mastered / totalAtoms) * 100 : 0
      };

      var done = { 1: l1Done, 2: l2Done, 3: l3Done, 4: l4Done, 5: l5Done };
      var level = 5;
      var i;
      for (i = 1; i <= 5; i++) {
        if (!done[i]) { level = i; break; }
      }
      if (l1Done && l2Done && l3Done && l4Done && l5Done) { level = 5; }

      return {
        level: level,
        level_name: LEVEL_DEFS[level - 1].name,
        current_pct: Math.round(pcts[level]),
        pct_by_level: {
          1: Math.round(pcts[1]), 2: Math.round(pcts[2]), 3: Math.round(pcts[3]),
          4: Math.round(pcts[4]), 5: Math.round(pcts[5])
        },
        done_by_level: done,
        stats: {
          total_atoms: totalAtoms,
          unlearned_atoms: unlearned,
          evaluated_atoms: evaluated,
          hard_or_normal_atoms: hardOrNormal,
          mastered_atoms: mastered,
          unique_answered_questions: uniqueQ,
          total_answered_questions: totalAnswered,
          scan_pct: scan.pct
        },
        all_mastered: l5Done
      };
    });
  }

  /* 不退転ロジック。
     display_pct = Math.max(current_pct, max_pct) をレベル別に適用する。
     単一の max_pct だけで運用すると、レベルが上がった瞬間に
     前レベルの高い値が居座って新レベルが常時100%になるため、
     max_pct_lv1〜5 を個別に持ち、meta.max_pct は現在レベルの値を映す。 */
  function computeLevel() {
    return computeLevelRaw().then(function (raw) {
      /* 到達済みレベルを飛び越えることがあるため、
         現在レベルだけでなく全レベルの高水位を個別に更新する。 */
      var raises = [1, 2, 3, 4, 5].map(function (n) {
        return S.raiseMeta('max_pct_lv' + n, raw.pct_by_level[n]);
      });

      return Promise.all(raises).then(function (maxes) {
        var levelMax = maxes[raw.level - 1] || 0;
        var display = Math.max(levelMax, raw.current_pct);
        return S.getMeta('level_current', 1).then(function (storedLevel) {
          /* レベルも後戻りさせない */
          var lv = Math.max(isNum(storedLevel) ? storedLevel : 1, raw.level);
          var writes = {};
          if (lv !== storedLevel) { writes.level_current = lv; }
          if (lv !== raw.level) { display = Math.max(maxes[lv - 1] || 0, raw.pct_by_level[lv]); }
          writes.max_pct = display;
          writes.visual_theme = VISUAL_BY_LEVEL[lv] || 'challenge';
          return S.setMetaBulk(writes).then(function () {
            return {
              level: lv,
              level_name: LEVEL_DEFS[lv - 1].name,
              current_pct: raw.pct_by_level[lv],
              display_pct: display,
              max_pct: display,
              max_pct_by_level: {
                1: maxes[0], 2: maxes[1], 3: maxes[2], 4: maxes[3], 5: maxes[4]
              },
              visual_theme: VISUAL_BY_LEVEL[lv] || 'challenge',
              theme_cleared: display >= 100,
              pct_by_level: raw.pct_by_level,
              done_by_level: raw.done_by_level,
              stats: raw.stats,
              all_mastered: raw.all_mastered,
              badge: raw.all_mastered ? '👑 ALL MASTERED' : null
            };
          });
        });
      });
    });
  }

  /* ======================================================================
   * 11. 模試の解禁判定（第11章①）
   * ====================================================================== */

  /* 解禁条件に渡す統計を組み立てて Storage.evaluateUnlocks に委譲する。
     ハイウォーターマークと永久フラグの保持は storage.js 側の責務。 */
  function refreshUnlocks() {
    return Promise.all([S.getAllAtoms(), S.countQuestions(), S.getMeta('full_mock_pass_streak', 0)])
      .then(function (r) {
        var atoms = r[0], totalQ = r[1], streak = r[2] || 0;
        var total = atoms.length;
        var answered = 0, normalPlus = 0;

        atoms.forEach(function (a) {
          if (a.answer_count > 0) { answered++; }
          if (a.last_eval === EVAL.NORMAL || a.last_eval === EVAL.EASY || a.last_eval === EVAL.MASTER) {
            normalPlus++;
          }
        });

        return S.evaluateUnlocks({
          totalQuestions      : totalQ,
          uniqueAnsweredRatio : total > 0 ? (answered / total) : 0,
          normalPlusRatio     : total > 0 ? (normalPlus / total) : 0,
          fullMockPassStreak  : streak
        }).then(function (results) {
          return {
            unlocks: results,
            stats: {
              total_questions: totalQ,
              total_atoms: total,
              answered_atoms: answered,
              normal_plus_atoms: normalPlus,
              unique_answered_ratio: total > 0 ? (answered / total) : 0,
              normal_plus_ratio: total > 0 ? (normalPlus / total) : 0,
              full_mock_pass_streak: streak
            }
          };
        });
      });
  }

  /* 定着率が基準を割っているかを返す（模試開始時のソフト警告用・第11章②） */
  function shouldWarnBeforeExam(examId) {
    return refreshUnlocks().then(function (r) {
      var def = null;
      S.MOCK_DEFS.forEach(function (d) { if (d.id === examId) { def = d; } });
      if (!def || def.need_normal_plus === null) { return { warn: false }; }
      var below = r.stats.normal_plus_ratio < def.need_normal_plus;
      return {
        warn: below,
        current: Math.round(r.stats.normal_plus_ratio * 100),
        required: Math.round(def.need_normal_plus * 100)
      };
    });
  }

  /* ======================================================================
   * 12. 得意・不得意ダッシュボード（第6章①）
   * ====================================================================== */

  /* level: 'unit' | 'major' | 'medium' | 'sub_item'
     既定は「定着率が低い（苦手な）項目」が最上位に来る昇順ソート。 */
  function buildDashboard(options) {
    options = options || {};
    var level = options.level || 'sub_item';
    var metric = options.metric || 'retention';

    return S.loadMeta().then(function (meta) {
      var preferFrequent = (options.preferFrequent !== undefined && options.preferFrequent !== null)
        ? !!options.preferFrequent
        : !!meta.prefer_frequent;

      return S.getAllAtoms().then(function (atoms) {
        if (!atoms.length) { return { level: level, metric: metric, rows: [], empty: true }; }

        var ids = atoms.map(function (a) { return a.atom_id; });
        return S.getLogMapByAtoms(ids).then(function (logMap) {
          var groups = {}, order = [];

          atoms.forEach(function (a) {
            var key = a[level];
            if (key === undefined || key === null) { key = '(未分類)'; }
            if (!groups[key]) {
              groups[key] = {
                key: key, label: key,
                unit: a.unit, major: a.major, medium: a.medium, sub_item: a.sub_item,
                num_code: a.num_code, rank: a.rank,
                total: 0, evaluated: 0, unlearned: 0,
                normal_plus: 0, hard: 0, mastered: 0,
                weakness_sum: 0, priority_sum: 0, max_priority: 0
              };
              order.push(key);
            }
            var g = groups[key];
            g.total++;
            if (!a.answer_count) { g.unlearned++; }
            if (a.last_eval) {
              g.evaluated++;
              if (a.last_eval === EVAL.HARD) { g.hard++; }
              if (a.last_eval === EVAL.MASTER) { g.mastered++; }
              if (a.last_eval === EVAL.NORMAL || a.last_eval === EVAL.EASY || a.last_eval === EVAL.MASTER) {
                g.normal_plus++;
              }
            }
            var w = computeWeaknessFromLogs(logMap[a.atom_id] || [], a);
            var p = priorityScore(a, w, preferFrequent);
            g.weakness_sum += w.pt;
            g.priority_sum += p;
            if (p > g.max_priority) { g.max_priority = p; }
            /* Sランクを含む項目は、その中で最も高いランクを代表として表示する */
            if (rankWeight(a.rank) > rankWeight(g.rank)) { g.rank = a.rank; }
          });

          var rows = order.map(function (k) {
            var g = groups[k];
            /* 定着率＝「普通以上」の割合。分母は範囲内の全アトム。
               未学習を分母から外すと、手つかずの単元が100%と表示されてしまう。 */
            var retention = g.total > 0 ? (g.normal_plus / g.total) * 100 : 0;
            return {
              key: g.key, label: g.label, num_code: g.num_code, rank: g.rank,
              crumb: [g.unit, g.major, g.medium, g.sub_item].filter(Boolean).join(' ＞ '),
              total_atoms: g.total,
              evaluated_atoms: g.evaluated,
              unlearned_atoms: g.unlearned,
              normal_plus_atoms: g.normal_plus,
              hard_atoms: g.hard,
              mastered_atoms: g.mastered,
              retention_pct: Math.round(retention),
              weakness_pt: Math.round(g.weakness_sum * 10) / 10,
              priority: Math.round(g.priority_sum * 10) / 10,
              max_priority: Math.round(g.max_priority * 10) / 10,
              band: retention >= 90 ? 'top' : retention >= 65 ? 'good' : retention >= 35 ? 'mid' : 'bad'
            };
          });

          if (metric === 'weakness') {
            rows.sort(function (a, b) { return b.priority - a.priority; });
          } else {
            rows.sort(function (a, b) {
              if (a.retention_pct !== b.retention_pct) { return a.retention_pct - b.retention_pct; }
              return b.priority - a.priority;
            });
          }

          return {
            level: level, metric: metric, prefer_frequent: preferFrequent,
            rows: rows, empty: false
          };
        });
      });
    });
  }

  /* ======================================================================
   * 13. インライン早期復習割り込み（第5章②）
   * ====================================================================== */

  /* 絶対ガード：new / random 以外のモードでは、蓄積も発火も一切行わない。
     本日の復習・概念ノック・力試し模試・単元別学習・単語検索の演習中に
     割り込みが起きないことを、この1箇所で構造的に保証する。 */
  var Interrupt = {
    pool: [],          /* 超早期復習に落ちたアトム（10m / 1h の「難しい」） */
    active: false,
    queue: [],         /* 現在の割り込みで出す q_id */
    served: 0,         /* この割り込みで消化した問題数 */
    run: 0,            /* 連続割り込みの累計（上限5） */
    hostMode: null,

    isAllowed: function (mode) { return has(INTERRUPT_ALLOWED_MODES, mode); },

    note: function (atom, mode) {
      if (!this.isAllowed(mode)) { return false; }
      if (!atom || !atom.q_id) { return false; }
      var i;
      for (i = 0; i < this.pool.length; i++) {
        if (this.pool[i].atom_id === atom.atom_id) { return false; }
      }
      this.pool.push({
        atom_id: atom.atom_id, q_id: atom.q_id,
        interval_code: atom.interval_code, noted_at: nowMs()
      });
      return true;
    },

    /* 3問蓄積 ＋ 許可モード ＋ 割り込み中でない、が揃ったときだけ true */
    shouldTrigger: function (mode) {
      if (!this.isAllowed(mode)) { return false; }
      if (this.active) { return false; }
      if (this.run >= INTERRUPT_MAX_RUN) { return false; }
      return this.uniqueQuestionCount() >= INTERRUPT_TRIGGER;
    },

    uniqueQuestionCount: function () {
      var seen = {}, n = 0;
      this.pool.forEach(function (p) {
        if (!seen[p.q_id]) { seen[p.q_id] = 1; n++; }
      });
      return n;
    },

    /* 割り込みを開始し、出題する問題を返す */
    begin: function (hostMode) {
      var self = this;
      if (!this.isAllowed(hostMode)) {
        return Promise.resolve({ started: false, reason: 'このモードでは割り込みを行いません' });
      }
      var seen = {}, qIds = [];
      this.pool.forEach(function (p) {
        if (!seen[p.q_id] && qIds.length < INTERRUPT_BATCH) {
          seen[p.q_id] = 1; qIds.push(p.q_id);
        }
      });
      if (qIds.length < INTERRUPT_TRIGGER) {
        return Promise.resolve({ started: false, reason: '蓄積が3問に達していません' });
      }

      /* 上限に達する場合は、残り枠ぶんだけに切り詰める */
      var allowance = INTERRUPT_MAX_RUN - this.run;
      if (allowance <= 0) {
        this.reset();
        return Promise.resolve({ started: false, reason: '連続割り込みの上限に達したため通常モードへ戻ります' });
      }
      if (qIds.length > allowance) { qIds = qIds.slice(0, allowance); }

      return S.getQuestionsFull(qIds).then(function (questions) {
        self.active = true;
        self.hostMode = hostMode;
        self.queue = qIds.slice();
        self.served = 0;
        self.pool = self.pool.filter(function (p) { return !seen[p.q_id]; });
        return {
          started: true, questions: questions,
          total: qIds.length, served: 0, run: self.run,
          badge: '⚡ 早期復習タイム (1/' + qIds.length + '問)'
        };
      });
    },

    /* 割り込み中の1問を消化する。3問終われば自動で通常モードへ復帰。 */
    advance: function () {
      if (!this.active) { return { active: false, finished: true, badge: null }; }
      this.served++;
      this.run++;
      var finished = (this.served >= this.queue.length);
      var forced = (this.run >= INTERRUPT_MAX_RUN);

      if (finished || forced) {
        var reason = forced && !finished
          ? '連続割り込みが5問に達したため、通常モードへ戻ります'
          : '3問の早期復習が完了しました';
        this.active = false;
        this.queue = [];
        var served = this.served;
        this.served = 0;
        if (forced) { this.run = 0; this.pool = []; }
        return { active: false, finished: true, served: served, forced: forced, reason: reason, badge: null };
      }

      return {
        active: true, finished: false, served: this.served, total: this.queue.length,
        badge: '⚡ 早期復習タイム (' + (this.served + 1) + '/' + this.queue.length + '問)'
      };
    },

    status: function () {
      return {
        active: this.active, pooled: this.uniqueQuestionCount(),
        served: this.served, total: this.queue.length,
        run: this.run, max_run: INTERRUPT_MAX_RUN,
        trigger_at: INTERRUPT_TRIGGER
      };
    },

    reset: function () {
      this.pool = []; this.active = false; this.queue = [];
      this.served = 0; this.run = 0; this.hostMode = null;
    },

    /* 学習セッションを切り替えるときは必ず呼ぶ（モード跨ぎの誤発火を防ぐ） */
    endSession: function () { this.reset(); }
  };

  /* ======================================================================
   * 14. 起動時のまとめ処理
   * ====================================================================== */

  /* ホーム画面が一度に必要とする数値を、まとめて1回で組み立てる */
  /* ======================================================================
   * 逆算プランナー（V1.50）
   *
   * 【なぜ要るか】
   *   学習アプリの離脱理由でいちばん多いのは「今日何をやればいいか分からない」。
   *   残り日数も未学習の量も既に持っているので、【1つの数字】に落とす。
   *   判断のコストをゼロにするのが目的で、正確な予測が目的ではない。
   *
   * 【0.7 を掛ける理由】
   *   実習・体調・バイトで解けない日が必ずある。残り日数をそのまま分母にすると
   *   「毎日必ず解ける」前提の数字になり、1日落とした時点で破綻して見える。
   *   3割は落ちる前提で組む。
   * ====================================================================== */
  var PLAN_SPARE_RATIO = 0.7;
  var PLAN_MAX_PER_DAY = 120;   /* これを超えたら「間に合わない」と正直に出す */

  function buildPlan(meta, dueCount, unlearnedAtoms, boundaryHour, now) {
    var due = isNum(dueCount) ? dueCount : 0;
    var left = Math.max(0, isNum(unlearnedAtoms) ? unlearnedAtoms : 0);
    var rest = examRemainingDays(meta, now, boundaryHour);
    if (rest === null) {
      return { has_exam: false, rest_days: null, usable_days: null,
               need_new: 0, due: due, today: due, over: 0, pace: 'no-exam' };
    }
    if (rest < 0) {
      return { has_exam: true, rest_days: rest, usable_days: 0,
               need_new: 0, due: due, today: due, over: 0, pace: 'past' };
    }
    /* 試験日当日も1日と数える。0除算は1日に丸める。 */
    var usable = Math.max(1, Math.floor((rest + 1) * PLAN_SPARE_RATIO));
    var needNew = Math.ceil(left / usable);
    var pace = 'ok';
    if (left === 0) { pace = 'done'; }
    else if (needNew > PLAN_MAX_PER_DAY) { pace = 'behind'; }
    return {
      has_exam: true, rest_days: rest, usable_days: usable,
      need_new: needNew, due: due, today: needNew + due,
      over: pace === 'behind' ? (needNew - PLAN_MAX_PER_DAY) : 0,
      pace: pace
    };
  }

  function getHomeState() {
    return S.ensureInitialized().then(function () {
      return Promise.all([
        S.getDueCount(),
        computeLevel(),
        getScanAccuracy(),
        refreshUnlocks(),
        S.countUnlearned(),
        S.countQuestions(),
        S.loadMeta(),
        S.getUnlearnedAtoms()
      ]);
    }).then(function (r) {
      var dueCount = r[0];
      var level = r[1];
      var scan = r[2];
      var unlocks = r[3];
      var unlearned = r[4];
      var totalQ = r[5];
      var meta = r[6];

      /* 未学習アトムを問題単位に畳む。ランダムモードは未学習アトムを
         1つでも含む問題を出すので、利用者から見た「残り」はこの数。 */
      var seenQ = {}, unlearnedQ = 0;
      (r[7] || []).forEach(function (a) {
        if (!seenQ[a.q_id]) { seenQ[a.q_id] = 1; unlearnedQ++; }
      });

      var unlockPct = 0;
      unlocks.unlocks.forEach(function (u) {
        if (u.pct > unlockPct) { unlockPct = u.pct; }
      });

      var boundary2 = isNum(meta.day_boundary_hour) ? meta.day_boundary_hour : 4;

      return {
        due_count: dueCount,
        /* 逆算プランナー（V1.50）。ホーム最上部に1行で出す。 */
        plan: buildPlan(meta, dueCount, unlearned, boundary2, nowMs()),
        /* App Badging API には必ず整数を渡す（文字列を渡すと型エラーで落ちる） */
        badge_value: Math.min(dueCount, 99),
        badge_text: dueCount > 99 ? '99+' : String(dueCount),
        level: level,
        scan: scan,
        unlocks: unlocks.unlocks,
        unlock_pct: unlockPct,
        unlearned_atoms: unlearned,
        /* 「あと何問で読破か」はアトム数ではなく問題数で数える。
           ランダムモードは未学習アトムを1つでも含む問題を出すので、
           利用者から見た残数はこちらが正しい。 */
        unlearned_questions: unlearnedQ,
        total_questions: totalQ,
        prefer_frequent: !!meta.prefer_frequent,
        visual_theme: level.visual_theme,
        random_qty_unlocked: !!meta.random_qty_unlocked,
        pomodoro_enabled: !!meta.pomodoro_enabled,
        day_boundary_hour: isNum(meta.day_boundary_hour) ? meta.day_boundary_hour : 4
      };
    });
  }

  /* 学習セッションの終わり／データ変更の後に呼ぶ再集計。
     概念理解率・弱点pt・レベル・解禁を一括で更新する。 */
  function refreshAll(options) {
    options = options || {};
    return S.trimGuard().then(function () {
      return recomputeConceptScores();
    }).then(function (concepts) {
      return (options.recomputeWeakness ? recomputeWeakness(null) : Promise.resolve(null))
        .then(function () { return concepts; });
    }).then(function (concepts) {
      return Promise.all([computeLevel(), refreshUnlocks(), getTop3Concepts()]).then(function (r) {
        return { concepts: concepts, level: r[0], unlocks: r[1], top3: r[2] };
      });
    });
  }

  /* 「頻出問題を優先する」トグルの保存 */
  function setPreferFrequent(on) {
    return S.setMeta('prefer_frequent', !!on).then(function (v) { return v; });
  }

  /* ======================================================================
   * 15. 公開API
   * ====================================================================== */

  var API = {
    APP_BUILD        : APP_BUILD,
    STEPS            : STEPS,
    STEP_INDEX       : STEP_INDEX,
    URGENCY_ORDER    : URGENCY_ORDER,
    EVAL             : EVAL,
    EVAL_LABEL       : EVAL_LABEL,
    EVAL_POINTS      : EVAL_POINTS,
    WEAK_PT          : WEAK_PT,
    STREAK_MULTIPLIER: STREAK_MULTIPLIER,
    RANK_WEIGHT      : RANK_WEIGHT,
    LEVEL_DEFS       : LEVEL_DEFS,
    VISUAL_BY_LEVEL  : VISUAL_BY_LEVEL,
    SCAN_MODEL_SIZE  : SCAN_MODEL_SIZE,
    GUARD_WINDOW_MS  : GUARD_WINDOW_MS,
    INTERRUPT_TRIGGER: INTERRUPT_TRIGGER,
    INTERRUPT_MAX_RUN: INTERRUPT_MAX_RUN,
    MASTER_UNLOCK_FROM: MASTER_UNLOCK_FROM,
    INTERRUPT_ALLOWED_MODES: INTERRUPT_ALLOWED_MODES,
    NO_SCHEDULE_MODES: NO_SCHEDULE_MODES,
    NO_RECORD_MODES  : NO_RECORD_MODES,

    /* --- 忘却スケジューリング --- */
    planSchedule        : planSchedule,
    nextStepIndex       : nextStepIndex,
    computeDueDate      : computeDueDate,
    isMasterUnlocked    : isMasterUnlocked,
    previewInterval     : previewInterval,
    previewAllIntervals : previewAllIntervals,
    stepIndexOf         : stepIndexOf,

    /* --- 弱点スコア --- */
    computeWeaknessFromLogs : computeWeaknessFromLogs,
    computeWeaknessForAtom  : computeWeaknessForAtom,
    recomputeWeakness       : recomputeWeakness,
    priorityScore           : priorityScore,
    rankWeight              : rankWeight,
    buildPlan               : buildPlan,
    setPreferFrequent       : setPreferFrequent,

    /* --- 評価の適用 --- */
    parseExamDate            : parseExamDate,
    examRemainingDays        : examRemainingDays,
    examCapMs                : examCapMs,
    examPhase                : examPhase,
    isHissu                  : isHissu,
    finalScore               : finalScore,
    sortCandidates           : sortCandidates,
    EXAM_CAP_RATIO           : EXAM_CAP_RATIO,
    EXAM_FINAL_DAYS          : EXAM_FINAL_DAYS,
    mergeLogs                : mergeLogs,
    logKey                   : logKey,
    rebuildAtomState         : rebuildAtomState,
    applyEvaluation          : applyEvaluation,
    commitDecision          : commitDecision,
    FORMAT                  : FORMAT,
    pickFormat              : pickFormat,
    applyQuestionEvaluations : applyQuestionEvaluations,
    applyExamResult          : applyExamResult,
    recordQuestionAnswered   : recordQuestionAnswered,
    recommendEvaluations     : recommendEvaluations,

    /* --- 出題 --- */
    buildQueue      : buildQueue,
    weightedPick    : weightedPick,
    CONQUER_BAND    : CONQUER_BAND,
    getReviewQueue  : getReviewQueue,
    getKnockQueue   : getKnockQueue,
    applyTopicGuard : applyTopicGuard,
    sortCandidates  : sortCandidates,

    /* --- 74概念 --- */
    recomputeConceptScores : recomputeConceptScores,
    getConceptRanking      : getConceptRanking,
    getTop3Concepts        : getTop3Concepts,

    /* --- 分析精度・レベル・解禁 --- */
    getScanAccuracy     : getScanAccuracy,
    recordScan          : recordScan,
    computeLevel        : computeLevel,
    computeLevelRaw     : computeLevelRaw,
    milestonePct        : milestonePct,
    refreshUnlocks      : refreshUnlocks,
    shouldWarnBeforeExam: shouldWarnBeforeExam,

    /* --- ダッシュボード --- */
    buildDashboard : buildDashboard,

    /* --- 割り込み --- */
    Interrupt : Interrupt,

    /* --- まとめ --- */
    getHomeState : getHomeState,
    refreshAll   : refreshAll
  };

  global.Scheduler = API;
  if (typeof module !== 'undefined' && module.exports) { module.exports = API; }

})(typeof window !== 'undefined' ? window : this);
