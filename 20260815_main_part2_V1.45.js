/* ==========================================================================
 * 20260815_main_part2_V1.42.js
 * アプリ本体【後半】：分析・検索・★ノート・単元別・力試し・設定・
 *                     オンボーディング・ポモドーロ完了処理
 *
 * 前半（20260815_main_part1_V1.01.js）が用意した window.Half2 のスタブ群を、
 * このファイルが実処理で上書きする。読み込み順は必ず part1 → part2。
 *
 * 【前半への割り込みは Main.hooks の3点のみ】
 *   afterGrade  : 力試し模試（解説を挟まず全問回答 → 一括採点）
 *   afterCommit : オンボーディング（10問／20問のチェックポイント）
 *   onFinish    : 模試・ノック・オンボーディングの独自終了処理
 *
 * 【改版履歴】
 *  V1.45 (1) 「同期で残せなかったメモ」（V1.72）。競合で負けた文面の控えを
 *            設定から読める・写せる・片づけられるようにした。従来は
 *            「両方で直したもの N件（新しい方を採用）」のトーストだけで
 *            負けた側の文面は永久に消えていた。
 *  V1.44 (1) 取り込みレポートに分類ガードの警告（V1.71）。出題基準に無い
 *            unit/major/medium を件数と実例で表示。NB分類の表記ゆれによる
 *            ツリー分裂を、取り込んだ直後に気づけるようにする。
 *  V1.43 (0) 白紙印刷バグ修正。#print-sheet が #modal-layer 内にあり、
 *            印刷CSSがレイヤーごと消すため、間違いノート印刷は V1.51 以来
 *            実機で白紙だった。組み立て時に body 直下へ移して解消。
 *  V1.43 (1) 学習レポート（V1.70）。定着率・弱点・学習量をA4一枚に印刷/PDF。
 *            戦略レビュー§1-2（学校パイロットの本命）。間違いノートの
 *            印刷機構を再利用し、実測値だけを載せる（予測値は載せない）。
 *  V1.00 初版
 *  V1.42 (1) 模試結果のシェア画像（V1.67）。端末内Canvasで1080×1080を
 *            生成し、共有シート→だめならPNGダウンロードの2段。通信ゼロ。
 *            合格可能性%は載せない（母集団データが無い数字は捏造）。
 *            載せるのは実測の点数と合格ラインまでの距離だけ。
 *            不合格の画像に合格帯は出さない（煽らない）。
 *  V1.41 (1) 間違いノートPDFの末尾に出典表記を1行（V1.66）。
 *            このノートは実習室で紙のまま回覧される。出どころが
 *            書いていない紙は「自作プリント」で終わり、見た人が
 *            アプリへたどり着く経路が無い。本文より小さく・薄く、
 *            最終ページの右下に1行だけ（広告然とさせない）。
 *  V1.40 (1) 検索結果を div から button へ（V1.64）。押すと演習が始まるのに
 *            div のままで、Tabでたどれず・読み上げがボタンと言わず・
 *            押した手ごたえも無かった。他の一覧（.concept-row / .bar-row）は
 *            すでに button で、ここだけ取り残されていた。
 *  V1.39 (1) 設定に保存領域の欄（V1.60）。既定のブラウザ保存は
 *            「いつ消されてもおかしくない」扱いなので、状態を見せて
 *            ［消えないようにする］を1つ置く。
 *        (2) 取り込みの前に空き容量を見る。途中で満杯になって落ちるより、
 *            始める前に断るほうがよい。
 *        (3) チュートリアル完了時と取り込み成功時に persist を要求する。
 *            起動直後には呼ばない（何も積み上がっていない時点で聞くと
 *            断られて終わり、二度と聞けない）。
 *  V1.38 (1) 復元（入れ替え）に確認を挟んだ。取り込み欄に同じファイルを
 *            貼ると足し合わせになり、**同じファイルなのに入口で結果が
 *            正反対**になっていた。入れ替え側にだけ確認を置く。
 *        (2) 取り込み欄がバックアップを受け取ったときは、
 *            「足し合わせました」と明示する。同じ見出しだと、
 *            利用者は問題を足したつもりのままになる。
 *        (3) UIツアー（TOUR_STEPS / runUiTour / promptRandom10）を撤去。
 *            その場ガイドへ置き換え済みで、呼び出し元が1つも無かった。
 *        (4) 模試だけが予想問題（pool:'mock'）を拾う（includeMock）。
 *            「模試モードかどうか」で判定しない。exam 以外の経路が
 *            増えるたびに漏れるので、拾う側が明示する形にした。
 *        (2) 取り込み結果にプールの内訳を出す。黙っていると、
 *            ランダムに予想問題が出てきて初めて誤りに気づくことになる。
 *  V1.37 (1) 「すべて元の文に戻す」「この音を消す」に確認を挟んだ。
 *            前半の confirmAction を通す。個別モーダルは増やさない。
 *  V1.36 (1) 模試の分類を【最後に見てからの距離】へ作り直した。
 *            V1.52〜V1.54 の familiar / novel は「その中項目を学んだか」で
 *            決めていたため、**学習が進むと必ず消える**分類だった。
 *            消えた瞬間、模試が「解いた問題」だらけになって実力が測れない。
 *  V1.35 (1) 設定にライセンス欄。残数の数え方は scheduler の solved_ever
 *            ただ1つに寄せた。2箇所で数えると必ずホームと設定でずれる。
 *        (2) 鍵が通らない理由を3つに分けて出す（形が違う／端末が非対応／
 *            署名が合わない）。「無効です」だけだと貼り間違いなのか
 *            鍵違いなのか判別できず、そのまま問い合わせになる。
 *  V1.34 (1) 模試の混合を3分類へ作り直した（V1.33の2分類を置き換え）。
 *            「解いた／解いていない」では本番に寄せられない。
 *            本番で出るのは【文字は初見だが知識は既習】がほとんどで、
 *            2分類ではそこを表せなかった。
 *  V1.33 (1) 模試の出題を「既出＋初見」の混合にした。
 *            本番モード6割／直前モード8割を既出から出す。
 *            全問を初見にすると本番より難しくなるため。
 *        (2) 復習の予定をカレンダー（.ics）へ書き出せるようにした。
 *            iOS は App Badging も Web Push も実質使えないので、
 *            「アプリが通知する」のをやめて OS のカレンダーに任せる。
 *        (3) ★と「難しい」だけを集めた紙面を印刷／PDF保存できるようにした。
 *            実習中の病院ではスマホを出せないため、紙が唯一の持ち出し手段になる。
 *  V1.32 (1) 模試に「本番モード／直前モード」を足した。
 *            直前モードは S/A ランク中心・一度解けた問題を先に出す。
 *            ただし【合格基準は本番と同じまま】変えない。
 *            基準まで甘くすると達成感が偽物になり、当日に効かないため。
 *  V1.31 (1) 画面を閉じる直前は、どの画面からでも同期するようにした。
 *            従来はホーム/設定のとき以外は runAutoSync が即 return していたため、
 *            「学習を終える→ホーム→8秒待たずに閉じる」がまるごと未同期だった。
 *  V1.30 (1) 同期に失敗したとき、その理由を設定画面に出すようにした。
 *            V1.48 で drive.js が失敗を握りつぶすのをやめたが、自動同期は
 *            画面に何も出さないため、直しただけでは利用者に届かない。
 *            未同期バッジが減らないことに加えて、理由も読めるようにする。
 *  V1.29 (1) V1.44 でヘッダーの同期ボタンを外したとき、未同期件数のバッジを
 *            更新する呼び出しも一緒に消えていた。実機で確認したところ、
 *            未同期が7件あってもバッジは一度も出ない状態だった
 *            （テストは refreshHdrSync() を手で呼んでいたため気づけなかった）。
 *            refreshDrive() と scheduleAutoSync() から呼ぶよう結び直した。
 *        (2) 撤去済みボタンの世話をするコードを削除。
 *            同期関数の本体・その処理中フラグ・撤去済みボタンのラベルと
 *            クラスを触る部分・そのボタンへの click 結び付けの4つ。
 *            どれも null 判定で素通りするだけだったが、残すと
 *            「ボタンがまだある」と読めてしまう。
 *            ※ ここに識別子をそのまま書かないこと。batchY が
 *              「残っていないか」を文字列で見ているため、履歴に書くと引っかかる。
 *        (3) refreshHdrSync を refreshSyncBadge へ改名。
 *            ヘッダーの同期ボタンはもう無く、実際に更新しているのは
 *            設定ボタンのバッジだけなので、名前が実態と合っていなかった。
 *  V1.21 (1) バッチC-3：アラーム音に「自分の音」を追加。取り込んだ音は
 *            画像と同じ user_files に kind:'audio' で入れる。
 *            ストアを分けないのは、バックアップ・復元・全消去の3経路に
 *            足す対象を1つに保つため。
 *        (2) 自分の音が選ばれているのにファイルが無いときは、
 *            黙って無音にせず合成音（チャイム）へ落とす。
 *            タイマーが鳴らないと「壊れた」ではなく「気づけない」になる。
 *  V1.20 (1) 全体解説を書き換えたあと、その場で表示へ反映するようにした。
 *            保存の仕組み（question の user_memo）は前からあったが、
 *            画面を出し直さないと変わらなかった。
 *  V1.19 (1) E-4：ガイドを全ボタン網羅へ。未案内だった15箇所を追加し、
 *            第2幕（解答画面の残り）・第3幕（ホーム周辺）・第4幕（各画面の初回）
 *            に割り当てた。原則は変えない：1画面1件・初回だけ・一度出したら出さない。
 *        (2) ホームは「毎日押す4カード → 周辺（精度・レベル・設定・テーマ・戻る・一言）」
 *            の順に配る。逆にすると初日が歯車の説明から始まる。
 *  V1.18 (1) 既存データに分割可否を後付けする自動判定を追加。
 *            13列目は V1.23 で入れたので、それ以前に取り込んだ問題には値が無く、
 *            そのままでは一問一答が一度も出てこない。
 *        (2) 設定の章立てを直した。「一問一答」と「文言の編集」が
 *            「リセット・問い合わせ」の中に紛れていた。7章を新設して移し、
 *            リセットは8章へ。
 *  V1.17 (1) 13列目（分割可否）の説明と、設定「一問一答の出しかた」を追加。
 *        (2) 実シート再現の表を13列（A〜M）に更新。
 *  V1.16 (1) 単元別ツリーの「この範囲をまとめて出題」に範囲名を入れた。
 *            単元を開くと大項目ぶんと単元ぶんが同じ文言で縦に並び、
 *            どちらがどの範囲なのか判別できなかった。
 *        (2) 一言欄10件を利用者の編集内容へ差し替え。
 *  V1.15 (1) 得意・不得意ダッシュボードとテーマ別弱点分析を「弱点分析」1画面へ統合。
 *            目的（次にどこを回すか）が同じで、並び順も同じで、片方は行を押しても
 *            何も起きなかった。2画面に分ける理由になっていない。
 *            軸を5択（単元／大項目／中項目／小項目／テーマ）にし、既定は小項目。
 *        (2) 全軸で「行タップ＝その範囲を出題」に統一。テーマ軸は弱点ノック、
 *            それ以外は単元別出題（mode:'tree'）。眺めるだけの画面にしない。
 *        (3) キーワード検索を独立画面へ。「単語を探す」と「苦手を並べる」は
 *            目的が違い、同居させるとスクロール量が倍になる。
 *        (4) data-level="sub" の不具合を修正。scheduler は a['sub_item'] で
 *            集計するので、"sub" を渡すと全行が「(未分類)」1行に潰れていた。
 *            開いた直後にどの軸ボタンも点灯しない状態にもなっていた。
 *        (5) ガイド concept を dashboard へ統合（画面が1つになったため）。
 *  V1.14 (1) 一言欄21件とガイド3件の文を、利用者が編集した内容で差し替えた。
 *            端末側の text_overrides に置いたままだと「その端末だけ」の
 *            書き換えになるので、配布物の既定文そのものを入れ替えている。
 *            g.search.text の「言葉をなどを」は誤字と判断して
 *            「言葉などを」に直した（画面に出る文なので申告する）。
 *        (2) 一言欄の本文で改行を改行として描くようにした（styles.css）。
 *            編集画面で入れた \n が空白に潰れていた。pre-wrap ではなく
 *            pre-line にして、コピペ由来の連続スペースは潰したままにする。
 *  V1.13 (1) 一言欄に [◀ 前へ] を追加。送りすぎたら戻れる。
 *        (2) 一言欄の高さを、その端末の実測最大値に固定した。
 *            34件は本文の長さがまちまちで、実測 390px幅で 134〜203px、
 *            320px幅では 134〜245px と最大111pxも動いていた。送るたびに
 *            下のカードが跳ねる。固定値をCSSに焼くと端末幅・文字サイズ設定で
 *            必ずズレるので、初回描画時に34件を画面外で1度測って最大値を採る。
 *        (3) ガイド・一言欄の文言を、アプリの中から自分で書き換えられるように
 *            した（設定 ＞ 8. 文言の編集）。書き換えは meta の text_overrides に
 *            id 単位で保存する。元の文も一緒に保存しておき、アプリ更新で
 *            元の文が変わったときは「元が更新されました」と出す。
 *            黙って古い自作文が残り続けると、実装と食い違ったまま気づけない。
 *  V1.12 (1) ガイド「4/4 次へ」の文を修正。
 *            「触らなかった選択肢は、そのままの評価で保存されます」は、
 *            期日前の肢を保存しなくなった時点で事実と違う。
 *            画面に出る文が実装と食い違うのは、コードのバグより始末が悪い。
 *        (2) ロック表示を説明するガイド（locked）を1件追加。
 *            評価ボタンが消えている理由が分からないと、壊れたと思われる。
 *            対象が画面に無いときは tip() が false を返して次へ回るので、
 *            ロックされた肢が出てくるまで自然に待つ。
 *  V1.11 (1) 評価4ボタンの一言を指定文へ差し替え。
 *            期間は scheduler.js の nextStepIndex() と一致していることを
 *            tests/test_batchG.py で毎回突き合わせる。
 *        (2) 一言欄34件を動線順に並び替えた。
 *            「使い方 → 評価の期間 → 仕組み（忘却曲線）→ 各モード →
 *              解説画面の使いこなし → ポモドーロ → 設定 → 製作者から」。
 *            製作者の話を最後に置くのは、初日に読ませても行動が変わらないため。
 *            初日に必要なのは「何をどう押すか」だけ。
 *  V1.10 (1) 一言欄の修正：3件削除・3件差し替え・4件追加。
 *  V1.10 (1) 一言欄の修正：3件削除（設定④／数字は下がりません／
 *            データは端末内だけ）、3件差し替え（「簡単」の心構え／忘却曲線②／
 *            本日の復習）、4件追加（難・普・易・マを押したときの期間）。
 *            期間はすべて scheduler.js の nextStepIndex() を読んで書いた。
 *            「他端末対応」の一言は、実装がゼロなので削除している。
 *        (2) 初見が尽きた状態の案内を openAllClearedSheet() として独立させ、
 *            いじわる模試の解禁条件を予告として見せる。
 *  V1.09 (1) 12列TSVの列ごとに [？] の説明を用意。
 *  V1.09 (1) 12列TSVの列ごとに [？] の説明を用意（1・2・3・4・5・6・7・9・12）。
 *            8・10・11（問題文／正解／解説）は読めば分かるため説明を置かない。
 *            とくにランクと形式は「分からなければ空でOK」を明記する。
 *        (2) 使い方カードのタイトルを任意化。ラベルと重複していた15件
 *            （製作者から3・忘却曲線4・ポモドーロ4・設定4）はタイトルを空にし、
 *            番号をラベル側へ寄せた。同じ文字列が大小2回出るのをやめる。
 *        (3) 設定のポモドーロスイッチを Main.setPomodoroEnabled() 経由へ。
 *            ヘッダーの⏸/▶と挙動を一本化する。
 *  V1.08 (1) ランダムモードを「初見の問題だけ」に限定（newOnly）。
 *  V1.08 (1) ランダムモードを「初見の問題だけ」に限定（newOnly）。
 *            従来は未学習を前方へ寄せるだけで既習も混ざっていた。
 *            尽きたときは専用ダイアログで復習・ノックへ逃がす。
 *            黙って「出題できる問題がありません」と出すと行き止まりになる。
 *        (2) ホームの使い方カードを全面差し替え（12件 → 33件）。
 *            製作者の意図・忘却曲線・各モード・ポモドーロ・設定を網羅。
 *            事実と食い違っていた3件（「簡単」の間隔／模試の解禁条件／
 *            更新頻度の断定）を実装に合わせて修正した。
 *  V1.07 (1) 生活リズム設定を 0〜23時の全時刻から選べるようにした。
 *  V1.07 (1) 生活リズム設定を 0〜23時の全時刻から選べるようにした。
 *            あわせて setDayBoundary の `parseInt(hour,10) || 4` を修正。
 *            0 は falsy なので、深夜0時を選ぶと黙って4時に戻る既存の不具合だった。
 *        (2) 設定の各見出しに [？] を追加し、共通ヘルプモーダルで解説を出す。
 *        (3) 12列TSVの取り込み手順を、設定画面内の折りたたみで全文提示。
 *        (4) 中項目リセットの prompt() 番号入力を廃止し、一覧から選ぶ2段階UIへ。
 *            番号をメモさせる摩擦に設計上の根拠は無い。取り消せない操作の
 *            歯止めは「対象名と件数を出す確認ダイアログ」で担保する。
 *        (5) ホーム最下部に、使い方と設計意図を1件ずつ送るカードを追加。
 *            主動線（本日の復習）の座標を1pxも動かさない位置に限定する。
 *        (6) 解説画面の追加ガイドを、上から順に6件へ再編。
 *            問題文★（rv-star）が一度も案内されていなかったのを追加し、
 *            対象要素が画面に無いガイドで行列が止まる不具合も直した。
 *        (7) 初回起動時に、3行だけの概要モーダルを1枚挟む。
 *  V1.01 (1) 内部用語「アトム」「概念」をUI文言から排除（一般学習者向けの表記へ）
 *        (2) IndexedDB が完全に空のときは questions.js の初回シードを
 *            自動投入してからチュートリアルを開く初期ルーティングを追加。
 *            データ0件だと「問1」が存在せず、初回起動が空白で終わるため。
 *  V1.02 (1) 【重大】bind() を init() から切り離し、読み込み直後に同期実行。
 *            旧構造では M.state.booted を待ってから束ねていたため、
 *            IndexedDB が使えない環境では後半画面のボタンが全て無反応だった。
 *        (2) 用語統一（案A）：「テーマ別 弱点ノック」
 *            「最優先で埋めたいテーマ TOP 3」へ統一。
 *            内部識別子（concept_score / CONCEPT_TAGS_MASTER / mode='knock'）は
 *            一切変更していないため、ロジックへの影響はゼロ。
 *  V1.03 (1) タグをタップしたときの理解度シート（画面遷移せずモーダル表示）
 *        (2) 正誤ポップアップのON/OFF設定
 *        (3) 模試の根拠チェックのヒントを初回のみ出す状態管理
 *  V1.06 (1) 解説画面の追加ガイド5件（評価サマリー・詳しい解説・書き換え・
 *            ★・タグ）が定義だけで一度も発火していなかったのを修正。
 *            4ステップの基本操作を終えた人に、1問につき1つずつ出す。
 *  V1.05 (1) 解説の書き換え（上書き型メモ）を実装。Markdown-lite で
 *            **太字** ==マーカー== - 箇条書き だけを許可する。
 *            入力は先に全てエスケープしてから記法だけを復元するため、
 *            HTMLやスクリプトを書かれても実行されない。
 *  V1.04 (1) 初心者ガイドを一括ツアーから「その場・その時・1つずつ」へ全面変更。
 *            10問チュートリアル＋UIツアー＋ランダム誘導の20問構成は、
 *            最初にまとめて説明しすぎて頭に残らない。
 *            いま押してほしいボタン、または初めて開いた画面でだけ、
 *            1つずつ出す方式（TIPS）にした。全ての主要ボタンを網羅する。
 * ========================================================================== */

(function (global) {
  'use strict';

  var S = global.Storage;
  var D = global.Drive;
  var K = global.Scheduler;
  var M = global.Main;
  var doc = global.document;

  if (!M) { console.error('[part2] 前半モジュールが読み込まれていません'); return; }

  var $ = M.$, $$ = M.$$, on = M.on;
  var toast = M.toast, openModal = M.openModal, closeModals = M.closeModals;
  var esc = M.escapeHtml, circled = M.circled, formatClock = M.formatClock;

  function setText(sel, t) { var e = $(sel); if (e) { e.textContent = t == null ? '' : String(t); } }
  function setHtml(sel, h) { var e = $(sel); if (e) { e.innerHTML = h == null ? '' : h; } }
  function show(sel) { var e = $(sel); if (e) { e.hidden = false; } }
  function hide(sel) { var e = $(sel); if (e) { e.hidden = true; } }
  function cls(el, c, on2) { if (el) { el.classList[on2 ? 'add' : 'remove'](c); } }
  function noop() {}
  function isNum(v) { return typeof v === 'number' && isFinite(v); }

  /* 後半モジュールのローカル状態 */
  var st = {
    dashboard : { level: 'sub_item', metric: 'retention', cfilter: 'low' },
    search    : { keyword: '', hits: [], cfilter: 'low' },
    starred   : { filter: 'all' },
    random    : { scope: null, count: 10, units: [] },
    knock     : { tag: null, minutes: 5, endsAt: 0, tick: null, solved: 0 },
    memo      : null,
    exam      : { id: null, questions: [], answers: [], index: 0, startedAt: 0 },
    onboard   : { active: false, step: 0, phase: null, target: 10 },
    breakT    : { endsAt: 0, tick: null, minutes: 0 },
    audio     : null,
    resetMedium : null,   /* 進捗リセットの確認待ち中項目 */
    welcomeNext : null    /* 初回概要モーダルの [はじめる] 待ち */
  };

  /* ======================================================================
   * 1. ランダムモード（第9章①：単元・大項目 2段階UI）
   * ====================================================================== */

  /* --- 階層ドリルダウン（V1.41） ---
     仕様§9-①は「中項目階層を排した2段階（決定迷いゼロ）」だった。
     排した理由は【階層が深いと、どこを選ぶかで止まって出題まで届かない】から。
     一方で「まだ手をつけていない単元があるので範囲を絞りたい」という
     要求が実利用で強く出た。両立させるために、
     【どの階層でも最上部に「ここまででランダム」を必ず置く】。
     掘るのは任意で、いつでもその場から始められる。これなら
     階層が増えても「決定」は1タップのまま増えない。

     st.random.path = [] / [unitKey] / [unitKey, majorKey] */

  function pickNode() {
    var tree = st.random.units || [];
    var path = st.random.path || [];
    if (!path.length) {
      var total = 0;
      tree.forEach(function (u) { total += u.count; });
      return { key: null, label: '全単元', count: total, children: tree,
               field: null, depth: 0 };
    }
    var u = null;
    tree.forEach(function (x) { if (x.key === path[0]) { u = x; } });
    if (!u) { st.random.path = []; return pickNode(); }
    if (path.length === 1) {
      return { key: u.key, label: u.label, count: u.count, children: u.children,
               field: 'unit', depth: 1, hard: u.hard, unlearned: u.unlearned };
    }
    var mj = null;
    (u.children || []).forEach(function (x) { if (x.key === path[1]) { mj = x; } });
    if (!mj) { st.random.path = [path[0]]; return pickNode(); }
    return { key: mj.key, label: mj.label, count: mj.count, children: mj.children,
             field: 'major', depth: 2, hard: mj.hard, unlearned: mj.unlearned };
  }

  /* 難しい件数（赤）を主、未学習件数（灰）を従にする。
     両方を同時に出すと、どちらを見て決めればいいのか分からなくなる。
     赤が出ているうちは赤だけを見せる。 */
  function pickBadge(item) {
    var h = Number(item.hard || 0), u = Number(item.unlearned || 0);
    if (h > 0) {
      return '<span class="badge-line">' + (h > 99 ? '99+' : h) + '</span>';
    }
    if (u > 0) {
      return '<span class="badge-soft">' + (u > 99 ? '99+' : u) + '</span>';
    }
    return '';
  }

  function renderRandomPick() {
    var node = pickNode();
    var path = st.random.path || [];

    /* パンくず。0階層のときは出さない（場所を取るだけになる）。 */
    var crumb = $('#pick-crumb');
    if (crumb) {
      crumb.hidden = (path.length === 0);
      if (path.length) {
        var parts = ['<button type="button" data-up="0">全単元</button>'];
        var tree = st.random.units || [], u = null;
        tree.forEach(function (x) { if (x.key === path[0]) { u = x; } });
        if (path.length === 1) {
          parts.push('<span class="pick-crumb-sep">＞</span>' +
                     '<span class="pick-crumb-here">' + esc(u ? u.label : '') + '</span>');
        } else {
          parts.push('<span class="pick-crumb-sep">＞</span>' +
                     '<button type="button" data-up="1">' + esc(u ? u.label : '') + '</button>');
          parts.push('<span class="pick-crumb-sep">＞</span>' +
                     '<span class="pick-crumb-here">' + esc(node.label) + '</span>');
        }
        setHtml('#pick-crumb', parts.join(''));
      }
    }

    setText('#unit-hero-title', node.depth === 0
      ? '全単元からランダム出題' : (node.label + ' すべてからランダム出題'));
    setText('#unit-hero-sub', '全 ' + node.count + ' 問から出題');
    var hero = $('#unit-hero');
    if (hero) {
      hero.dataset.field = node.field || '';
      hero.dataset.key = node.key || '';
    }

    var kids = node.children || [];
    var childField = (node.depth === 0) ? 'unit' : (node.depth === 1 ? 'major' : 'medium');
    setHtml('#major-list', kids.map(function (it) {
      var hasKids = !!(it.children && it.children.length);
      var main = '<button type="button" class="pick-main" data-field="' + childField +
                 '" data-key="' + esc(it.key) + '" data-drill="' + (hasKids ? '1' : '0') + '">' +
                 '<span class="pick-name">' + esc(it.label) + '</span>' +
                 pickBadge(it) +
                 '<span class="pick-count">' + it.count + '問</span>' +
                 (hasKids ? '<span class="tool-arrow" aria-hidden="true"></span>' : '') +
                 '</button>';
      /* 絵柄ではなく言葉にする。サイコロ＝ランダムという連想は
         人によって無い。押した先が何かは、文字で書くのが一番速い。 */
      var dice = '<button type="button" class="pick-dice" data-field="' + childField +
                 '" data-key="' + esc(it.key) + '" aria-label="' + esc(it.label) +
                 ' からランダム出題">ランダム</button>';
      return '<div class="pick-row">' + main + dice + '</div>';
    }).join(''));
  }

  function openRandomSelect() {
    return Promise.all([S.buildTree(), S.loadMeta()]).then(function (r) {
      var tree = r[0], meta = r[1];
      if (!tree.length) { toast('先に設定から問題データを取り込んでください'); return; }
      st.random.units = tree;
      st.random.path = [];
      st.random.scope = null;
      global.setTimeout(function () {
        tip('unit_hero').then(function (shown) { return shown ? true : tip('qty'); });
      }, 600);

      renderRandomPick();

      /* 初回ランダム10問の完了で全出題数を永久解放する（第8章③） */
      var unlocked = !!meta.random_qty_unlocked;
      $$('#qty-block .qty-btn').forEach(function (b) {
        var q = parseInt(b.getAttribute('data-qty'), 10);
        var locked = !unlocked && q !== 10;
        b.disabled = locked;
        cls(b, 'is-locked', locked);
        cls(b, 'is-active', q === st.random.count);
      });
      setText('#qty-note', unlocked
        ? '出題数はすべて解放されています'
        : '初回ランダム10問の完了で、全出題数（20/30/50/120問）が永久解放されます。');

      return M.go('random');
    });
  }

  /* ランダムモードは「まだ一度も解いていない問題」だけを出す。
     未学習を前方へ寄せるだけだと既習が混ざり、「初見だけ」という
     利用者の期待と実装がずれる。ずれたまま案内文だけ直すのは筋が悪い。

     ただし全問を一周すると候補が0になる。黙ってトーストで終わると
     行き止まりなので、次にどこへ行けばいいかを必ず出す。 */
  /* --- ランダム → 克服 の切り替え（V1.41） ---
     判定は【選んだ範囲の中】で行う。全体では初見が残っていても、
     「必修問題」だけを見れば読破済み、ということが普通に起きる。
     全体の数で決めると、その範囲では何も出せずに行き止まりになる。

     まず初見だけで組み、0件なら同じ範囲の苦手順で組み直す。
     どちらになったかは必ず言葉で伝える。黙って中身が変わるのが
     一番混乱する。 */
  function startRandom(scope, count) {
    st.random.scope = scope || null;
    st.random.count = count || st.random.count;
    var opts = {
      mode: 'random', count: st.random.count, scope: scope || null,
      newOnly: true, shuffle: true
    };
    return M.startSession(opts).then(function (sess) {
      if (sess) { return sess; }
      /* この範囲の初見が尽きた＝克服モードへ */
      return M.startSession({
        mode: 'conquer', count: st.random.count, scope: scope || null,
        shuffle: false
      }).then(function (s2) {
        if (!s2) { openModal('#modal-no-new'); return null; }
        toast('この範囲は読破ずみです。苦手な順に出題します', 3600);
        maybeShowClearedSheet();
        return s2;
      });
    });
  }

  /* 「全問読破」の祝いは、全体の初見が0になった最初の1回だけ出す。
     カードから独立した動線を消したので、ここが唯一の出しどころ。 */
  function maybeShowClearedSheet() {
    return S.loadMeta().then(function (m) {
      if (m.cleared_sheet_shown) { return null; }
      return K.refreshAll({ recomputeWeakness: false }).then(function (h) {
        var left = h && h.level && h.level.stats ? h.level.stats.unlearned_atoms : null;
        if (typeof left !== 'number' || left > 0) { return null; }
        return S.setMeta('cleared_sheet_shown', true).then(function () {
          return openAllClearedSheet();
        });
      });
    }).catch(function () { return null; });
  }

  /* ======================================================================
   * 2. 3階層ツリー（第3章①②）
   * ====================================================================== */

  /* openTree（単元別学習の画面）は V1.41 で撤去した。
     ランダムの階層ドリルダウンが同じ3階層を、
     「見る」だけでなく「その場で出す」までやるようになったため、
     眺めるだけの画面が二重になっていた。
     範囲を指定した出題そのものは startByScope が引き続き担う
     （弱点分析のグラフから直接出題する経路で使う）。 */

  function startByScope(field, value) {
    return M.startSession({ mode: 'tree', count: 20, scope: { field: field, value: value } });
  }

  /* ======================================================================
   * 3. 分析ダッシュボード（第6章①）
   * ====================================================================== */

  function openDashboard(level) {
    if (level) { st.dashboard.level = level; }
    return M.go('dashboard').then(function () {
      return renderDashboard(st.dashboard.level, st.dashboard.metric);
    }).then(function (r) {
      global.setTimeout(function () {
        tip('dashboard').then(function (shown) { return shown ? true : tip('rank_weight'); });
      }, 500);
      return r;
    });
  }

  function renderDashboard(level, metric) {
    st.dashboard.level = level || st.dashboard.level;
    st.dashboard.metric = metric || st.dashboard.metric;

    $$('#screen-dashboard .seg-btn[data-level]').forEach(function (b) {
      cls(b, 'is-active', b.getAttribute('data-level') === st.dashboard.level);
    });
    $$('#screen-dashboard .seg-btn[data-metric]').forEach(function (b) {
      cls(b, 'is-active', b.getAttribute('data-metric') === st.dashboard.metric);
    });

    /* テーマ軸だけは指標が「理解率」1本なので、定着率／弱点スコアの
       切り替えを出さない。押しても何も起きないボタンを残さない。 */
    var isTag = (st.dashboard.level === 'tag');
    var mSeg = $('#dash-metric'), cSeg = $('#dash-concept');
    if (mSeg) { mSeg.hidden = isTag; }
    if (cSeg) { cSeg.hidden = !isTag; }
    setText('#dash-hint', isTag
      ? 'テーマをタップすると、そのテーマだけの弱点ノックが始まります。'
      : '行をタップすると、その範囲だけを出題します。');

    if (isTag) {
      show('#concept-list');
      setHtml('#bar-chart', '');
      hide('#dash-empty');
      return renderConceptRanking(st.dashboard.cfilter);
    }
    hide('#concept-list');
    show('#bar-chart');

    return K.buildDashboard(st.dashboard).then(function (d) {
      var tg = $('#toggle-rank-weight');
      if (tg) { tg.checked = !!d.prefer_frequent; }

      if (d.empty || !d.rows.length) {
        setHtml('#bar-chart', '');
        show('#dash-empty');
        return d;
      }
      hide('#dash-empty');

      /* 既定は「定着率が低い（苦手な）項目」が最上位に来る昇順ソート */
      setHtml('#bar-chart', d.rows.map(function (r) {
        var val = (st.dashboard.metric === 'weakness') ? r.priority : r.retention_pct;
        var width = (st.dashboard.metric === 'weakness')
          ? Math.min(100, d.rows[0].priority > 0 ? (r.priority / d.rows[0].priority) * 100 : 0)
          : r.retention_pct;
        var unit = (st.dashboard.metric === 'weakness') ? 'pt' : '%';
        return '<button type="button" class="bar-row" data-scope-field="' +
               esc(st.dashboard.level) + '" data-scope-value="' + esc(r.key) + '">' +
               '<div class="bar-meta">' +
               '<span class="rank-badge ' + esc(r.rank) + '">' + esc(r.rank) + '</span>' +
               '<small class="num-code">' + esc(r.num_code || '') + '</small>' +
               '<span class="bar-val">' + val + unit + '</span>' +
               '<span class="bar-crumb">' + esc(r.crumb) + '</span>' +
               '</div>' +
               '<div class="bar-track"><div class="bar-fill lv-' + r.band + '" style="width:' + width + '%"></div></div>' +
               '<div class="bar-sub">定着率 ' + r.retention_pct + '% ／ 弱点 ' + r.weakness_pt + 'pt ／ ' +
               '未学習 ' + r.unlearned_atoms + ' ・ 難 ' + r.hard_atoms + ' ・ マ ' + r.mastered_atoms +
               '（全' + r.total_atoms + '肢）</div></button>';
      }).join(''));
      return d;
    });
  }

  /* 行タップ＝その範囲を出題。テーマ軸は弱点ノック側で処理する。
     「見て終わり」の画面にしないための唯一の動線なので、ここで黙って
     失敗させない（対象0件ならその旨を出す）。 */
  function startScopeDrill(field, value) {
    if (!field || value == null) { return Promise.resolve(null); }
    return M.startSession({
      mode: 'tree', scope: { field: field, value: value }, count: 20
    });
  }

  function setPreferFrequent(onFlag) {
    return K.setPreferFrequent(onFlag).then(function () {
      return S.loadMeta();
    }).then(function (meta) {
      M.state.meta = meta;
      toast(onFlag ? '頻出問題（Sランク）を優先して出題します' : '頻出度を無視し、純粋な弱点順で出題します', 2800);
      return renderDashboard();
    });
  }

  /* ======================================================================
   * 4. キーワード検索 ＆ テーマ別 弱点分析（第12章「74概念アナライザー」）
   * ====================================================================== */

  function openSearch() {
    return M.go('search').then(function () {
      var input = $('#search-input');
      if (input) { input.value = st.search.keyword; }
      return null;
    }).then(function (r) {
      global.setTimeout(function () { tip('search'); }, 500);
      /* 検索結果が出てからでないと [この結果を今すぐ解く] は画面に無い。
         tip() は対象が無ければ false を返して次回に回るので、
         ここで空振りしても順番は崩れない。 */
      global.setTimeout(function () { tip('solve_now'); }, 3400);
      return r;
    });
  }

  function runSearch(keyword) {
    st.search.keyword = keyword || '';
    if (!st.search.keyword.trim()) {
      hide('#search-summary'); hide('#btn-solve-now'); hide('#search-mode-note');
      setHtml('#search-results', '');
      st.search.hits = [];
      return Promise.resolve(null);
    }

    return S.searchAll(st.search.keyword).then(function (res) {
      st.search.hits = res.hits;

      var chips = ['S', 'A', 'B', 'C'].filter(function (r) { return res.summary[r]; })
        .map(function (r) { return '<span class="sum-chip">' + r + 'ランク: <b>' + res.summary[r] + '</b>件</span>'; });
      chips.unshift('<span class="sum-chip">該当 <b>' + res.total + '</b> 問</span>');
      setHtml('#search-summary', chips.join(''));
      show('#search-summary');

      if (!res.total) {
        setHtml('#search-results', '<p class="dash-empty">「' + esc(st.search.keyword) + '」に一致する問題は見つかりませんでした</p>');
        hide('#btn-solve-now'); hide('#search-mode-note');
        return res;
      }

      setHtml('#search-results', res.hits.map(function (h) {
        /* --- button にする（V1.64） ---
           押すとその問題の演習が始まるのに、div のままだった。
           影が付いていて見た目は押せるのに、
             ・Tab でたどり着けない
             ・読み上げが「ボタン」と言わない
             ・押した手ごたえ（:active）が無い
           の3つが欠けていた。他の一覧（.concept-row / .bar-row）は
           すでに button なので、ここだけが取り残されていた。 */
        return '<button type="button" class="search-hit" data-qid="' + esc(h.q_id) + '"' +
               ' aria-label="' + esc(h.rank) + 'ランク ' + esc(h.num_code || '') +
               ' この問題を解く">' +
               '<span class="search-hit-head">' +
               '<span class="rank-badge ' + esc(h.rank) + '">' + esc(h.rank) + '</span>' +
               '<small class="num-code">' + esc(h.num_code || '') + '</small>' +
               '<span class="sum-chip">' + h.fields.map(fieldLabel).join('・') + '</span></span>' +
               '<span class="search-hit-body">' + mark(h.excerpt, st.search.keyword) + '</span></button>';
      }).join(''));
      show('#btn-solve-now'); show('#search-mode-note');
      return res;
    });

    function fieldLabel(f) {
      return { stem: '問題文', atom: '選択肢', explanation: '解説', table: '比較表' }[f] || f;
    }
  }

  function mark(text, kw) {
    var t = esc(text);
    if (!kw) { return t; }
    var k = esc(kw).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    try { return t.replace(new RegExp(k, 'gi'), function (m2) { return '<mark>' + m2 + '</mark>'; }); }
    catch (e) { return t; }
  }

  /* 検索結果の即時演習。忘却スケジュールも弱点ptも更新しない独立モード。
     評価チップの入力もスキップされる（前半の renderReview が mode で分岐）。 */
  function startSearchDrill(qIds) {
    var ids = qIds || st.search.hits.map(function (h) { return h.q_id; });
    if (!ids.length) { toast('演習できる問題がありません'); return Promise.resolve(); }
    toast('この演習は忘却スケジュールを更新しません', 3000);
    return M.startSession({ mode: 'search', qIds: ids, count: ids.length, applyGuard: false });
  }

  /* テーマ別の理解度ランキング。V1.15 から弱点分析画面（テーマ軸）に住む。 */
  function renderConceptRanking(order) {
    st.dashboard.cfilter = order || st.dashboard.cfilter;
    st.search.cfilter = st.dashboard.cfilter;   /* 旧キーも同じ値に保つ */
    $$('#screen-dashboard .seg-btn[data-cfilter]').forEach(function (b) {
      cls(b, 'is-active', b.getAttribute('data-cfilter') === st.dashboard.cfilter);
    });

    return K.recomputeConceptScores().then(function () {
      /* 「苦手な順／得意な順」でも、データはあるが未評価のテーマを末尾に残す。
         評価済0件のときに一覧が真っ白になり、次の一手を見失うのを防ぐ。 */
      return K.getConceptRanking({
        order: st.dashboard.cfilter,
        onlyEvaluated: false,
        withAtomsOnly: st.dashboard.cfilter !== 'unlearned'
      });
    }).then(function (rows) {
      if (!rows.length) {
        setHtml('#concept-list', '<p class="dash-empty">まだ解答していないため、理解度を出せるテーマがありません</p>');
        return rows;
      }
      setHtml('#concept-list', rows.map(function (r) {
        var known = isNum(r.score);
        var band = !known ? 'lv-mid' : r.score >= 90 ? 'lv-top' : r.score >= 65 ? 'lv-good' : r.score >= 35 ? 'lv-mid' : 'lv-bad';
        return '<button type="button" class="concept-row' + (known && r.score < 50 ? ' is-critical' : '') +
               (known ? '' : ' is-null') + '" data-tag="' + esc(r.tag) + '">' +
               '<span class="concept-main">' +
               '<span class="concept-name">' + esc(r.tag) + '</span>' +
               '<span class="concept-cat">' + esc(r.category || 'その他') + ' ／ ' + r.atom_count + '肢' +
               (known ? '（解答済 ' + r.evaluated_count + '）' : '（未評価）') + '</span>' +
               '<span class="concept-gauge"><i class="bar-fill ' + band + '" style="width:' + (known ? r.score : 0) + '%"></i></span>' +
               '</span>' +
               '<span class="concept-pct">' + (known ? r.score + '%' : '未解答') + '</span></button>';
      }).join(''));
      return rows;
    });
  }

  /* 最優先で埋めたいテーマ TOP 3（第12章③「最優先克服概念 TOP 3」） */
  function showTop3Popin() {
    return K.recomputeConceptScores().then(function () {
      return K.getTop3Concepts();
    }).then(function (top3) {
      if (!top3.length) {
        toast('理解度50%未満のテーマはありません。この調子です', 3000);
        return null;
      }
      setHtml('#top3-list', top3.map(function (t, i) {
        return '<button type="button" class="top3-item" data-tag="' + esc(t.tag) + '">' +
               '<span class="top3-rank">' + (i + 1) + '</span>' +
               '<span class="top3-main">' +
               '<span class="top3-name">' + esc(t.tag) + '</span>' +
               '<span class="top3-score">理解度 ' + t.score + '% ／ ' + t.atom_count + '肢</span></span>' +
               '<span class="tool-arrow"></span></button>';
      }).join(''));
      openModal('#modal-top3');
      return top3;
    });
  }

  /* タグをタップしたときの理解度シート。
     画面遷移すると、入力途中の評価がすべて破棄されてしまうため、
     モーダルで見せて学習の流れを切らない（案C）。 */
  function openTagSheet(tag) {
    if (!tag) { return Promise.resolve(); }
    return K.recomputeConceptScores().then(function () {
      return K.getConceptRanking({ order: 'low', onlyEvaluated: false, withAtomsOnly: false });
    }).then(function (rows) {
      var r = rows.filter(function (x) { return x.tag === tag; })[0];
      var known = r && typeof r.score === 'number';
      setText('#tagsheet-name', tag);
      setHtml('#tagsheet-body', r
        ? '<div class="score-cell ' + (known ? (r.score < 50 ? 'is-fail' : 'is-pass') : '') + '">' +
          '<b>' + (known ? r.score + '%' : '—') + '</b><small>理解度</small></div>' +
          '<div class="score-cell"><b>' + (r.atom_count || 0) + '</b><small>この中の選択肢</small></div>' +
          '<div class="score-cell"><b>' + (r.evaluated_count || 0) + '</b><small>解答済</small></div>'
        : '<p class="dash-empty">このテーマの集計がまだありません</p>');
      $('#modal-tagsheet').dataset.tag = tag;
      M.openModal('#modal-tagsheet');
      return r;
    });
  }

  /* ======================================================================
   * 5. テーマ別 弱点ノック（第7章「概念別弱点ノック」）
   * ====================================================================== */

  /* 初見が尽きた状態でランダムのカードを押したとき。
     まず到達を認め、そのうえで次の一手を出す。
     いじわる模試が未解禁なら、解禁条件を予告として見せる（ここに出てくる、と分かる）。 */
  function openAllClearedSheet() {
    return S.getUnlockState().then(function (states) {
      var w = states.filter(function (x) { return x.id === 'mock_weak'; })[0];
      var unlocked = !!(w && w.unlocked);
      setText('#nonew-title', '初見の問題は残っていません');
      setHtml('#nonew-body',
        'この範囲は<b>すべて解き終えました</b>。ここからは、忘れた分を戻すのが伸びる道です。' +
        (unlocked
          ? '<br><br><b>いじわる模試</b>が解禁されています。このカードから挑戦できます。'
          : '<br><br>この場所には、いずれ <b>いじわる模試（弱点だけの120問）</b> が出てきます。' +
            '力試しモードのフル模試に<b>2回連続で合格</b>すると解禁されます。'));
      openModal('#modal-no-new');
      return w;
    });
  }

  function openKnockDialog(tag) {
    var pick = tag ? Promise.resolve(tag) : K.getTop3Concepts().then(function (t) {
      return t.length ? t[0].tag : null;
    });
    return pick.then(function (t) {
      if (!t) {
        return K.getConceptRanking({ order: 'low', withAtomsOnly: true }).then(function (r) {
          return r.length ? r[0].tag : null;
        });
      }
      return t;
    }).then(function (t) {
      if (!t) { toast('先に何問か解いて、克服したいテーマを決めましょう', 3200); return null; }
      st.knock.tag = t;
      setText('#knock-target', t);
      openModal('#modal-knock-time');
      return t;
    });
  }

  /* トピックガードを一時無効化し、忘却スケジュールも更新しない独立集中演習。
     評価・弱点pt・概念理解率だけは更新するため、克服がスコアに反映される。 */
  function startKnock(tag, minutes) {
    st.knock.tag = tag || st.knock.tag;
    st.knock.minutes = minutes || 5;
    st.knock.solved = 0;

    return K.getKnockQueue(st.knock.tag, { minutes: st.knock.minutes }).then(function (q) {
      if (!q.questions.length) { toast(q.reason || 'このテーマの問題がありません'); return null; }

      /* 時間経過だけが終了条件なので、キューを周回できるよう十分に積む */
      var pool = q.questions.slice();
      while (pool.length < st.knock.minutes * 4 && q.questions.length) {
        pool = pool.concat(q.questions);
      }

      closeModals();
      mountKnockTimer(q.tag, st.knock.minutes);

      M.hooks.onFinish = function (sess) {
        if (sess.mode !== 'knock') { return false; }
        finishKnock(st.knock.solved);
        return true;
      };
      /* 途中で戻った・ホームを押した場合はここに来る。
         まとめの画面もアラームも出さず、時計だけを止めて片付ける。 */
      M.hooks.onAbort = function (mode) {
        if (mode !== 'knock') { return; }
        abortKnock();
      };
      M.hooks.afterCommit = function (qq, sess) {
        if (sess.mode === 'knock') { st.knock.solved++; }
      };

      M.state.session = {
        mode: 'knock', sessionId: 'KN' + Date.now().toString(36),
        questions: pool, index: 0, answeredCount: 0, startedAt: Date.now(),
        hostQueue: null, hostIndex: 0
      };
      K.Interrupt.endSession();
      return M.go('quiz').then(function () { M.renderQuestion(); return q; });
    });
  }

  function mountKnockTimer(tag, minutes) {
    var el = $('#knock-timer');
    if (!el) { return; }
    /* position:fixed なので、画面要素の外へ出しても位置は保たれる */
    doc.body.appendChild(el);
    doc.body.classList.add('is-knock');
    el.hidden = false;
    setText('#knock-concept', tag);

    st.knock.endsAt = Date.now() + minutes * 60 * 1000;
    global.clearInterval(st.knock.tick);
    st.knock.tick = global.setInterval(tickKnock, 250);
    tickKnock();
  }

  function tickKnock() {
    var left = st.knock.endsAt - Date.now();
    var total = st.knock.minutes * 60 * 1000;
    setText('#knock-time', formatClock(Math.max(0, left)));
    var bar = $('#knock-bar-fill');
    if (bar) { bar.style.width = Math.max(0, (left / total) * 100) + '%'; }
    if (left <= 0) {
      global.clearInterval(st.knock.tick);
      st.knock.tick = null;
      finishKnock(st.knock.solved);
    }
  }

  /* 時計を止めて後片付けだけする。まとめもアラームも出さない。
     M.endSession() は【呼ばない】：ここは endSession から呼ばれる側なので、
     呼び返すと入れ子になる。 */
  function abortKnock() {
    global.clearInterval(st.knock.tick);
    st.knock.tick = null;
    st.knock.endsAt = 0;
    unmountKnockTimer();
    M.hooks.onFinish = null;
    M.hooks.afterCommit = null;
    M.hooks.onAbort = null;
  }

  function finishKnock(solved) {
    global.clearInterval(st.knock.tick);
    st.knock.tick = null;
    st.knock.endsAt = 0;
    unmountKnockTimer();
    M.hooks.onFinish = null;
    M.hooks.afterCommit = null;
    M.hooks.onAbort = null;
    M.endSession();

    setText('#knock-solved', solved || 0);
    return K.refreshAll({ recomputeWeakness: false })
      .then(function () { return M.refreshHome(); })
      .then(function () { return M.go('home', { replace: true }); })
      .then(function () { openModal('#modal-knock-summary'); playAlarm(); });
  }

  function unmountKnockTimer() {
    var el = $('#knock-timer');
    if (el) { el.hidden = true; }
    doc.body.classList.remove('is-knock');
    var host = $('#screen-knock');
    if (el && host && el.parentNode === doc.body) { host.insertBefore(el, host.firstChild); }
  }

  /* ======================================================================
   * 6. マイ★お気に入りノート（第13章）
   * ====================================================================== */

  /* ---------------- 一問一答の出しかた ---------------- */

  /* しきい値は「期日の肢が この本数以上 なら4択」。
     1 は「1本以上＝常に4択」で、下の [常に4択で出す] と同じ意味になるため
     選択肢に出さない。同じことをする操作を2つ置かない。 */
  var ONEQ_LABEL = {
    2: '期日の選択肢が1本のときだけ一問一答',
    3: '期日の選択肢が2本までなら一問一答'
  };

  function oneqThreshold(meta) {
    var v = meta ? meta.split_threshold : null;
    return (v === 2 || v === 3) ? v : 2;
  }

  function renderOneQ() {
    var meta = M.state.meta || {};
    var th = oneqThreshold(meta);
    var always = meta.always_multi === true;
    $$('#modal-oneq .seg-btn[data-oneq]').forEach(function (b) {
      cls(b, 'is-active', parseInt(b.getAttribute('data-oneq'), 10) === th);
    });
    var sw = $('#set-always-multi');
    if (sw) { sw.checked = always; }
    setText('#oneq-state', always ? '常に4択で出す' : ONEQ_LABEL[th]);
  }

  function openOneQSheet() {
    renderOneQ();
    openModal('#modal-oneq');
    return refreshOneQStat();
  }

  /* 押す前に「何問に付くのか」を見せる。押してから件数を知る作りにすると、
     取り消したくなったときにはもう全部書き換わっている。 */
  function refreshOneQStat() {
    return Promise.all([
      S.autoMarkSplittable({ dryRun: true }),
      S.getAllQuestions()
    ]).then(function (r) {
      var d = r[0];
      var already = r[1].filter(function (q) { return q.is_splittable; }).length;
      setText('#oneq-auto-stat',
        '全 ' + d.total + ' 問中、いま印が付いているのは ' + already + ' 問。' +
        '自動判定なら ' + d.marked + ' 問に付きます（' + d.skipped + ' 問は対象外）。');
      return d;
    }).catch(function () {
      setText('#oneq-auto-stat', '件数を数えられませんでした');
      return null;
    });
  }

  function runOneQAuto() {
    return S.autoMarkSplittable().then(function (d) {
      toast(d.marked + ' 問に印を付けました（' + d.skipped + ' 問は対象外）', 4000);
      return refreshOneQStat();
    });
  }

  function runOneQClear() {
    return S.clearSplittable().then(function (d) {
      toast(d.cleared + ' 問の印を外しました', 3000);
      return refreshOneQStat();
    });
  }

  function setSplitThreshold(v) {
    var th = (v === 2 || v === 3) ? v : 2;
    return S.setMeta('split_threshold', th).then(function () {
      M.state.meta.split_threshold = th;
      renderOneQ();
      toast(ONEQ_LABEL[th], 2600);
      return th;
    });
  }

  function setAlwaysMulti(on2) {
    var v = !!on2;
    return S.setMeta('always_multi', v).then(function () {
      M.state.meta.always_multi = v;
      renderOneQ();
      toast(v ? '常に4択で出します' : '一問一答を使います', 2400);
      return v;
    });
  }

  /* ---------------- 文言の編集画面 ---------------- */

  var textUi = { filter: 'all', q: '', editing: null };

  function openTextEditor() {
    return loadTextOverrides()
      .then(function () { return M.go('text'); })
      .then(function () { return renderTextList(); });
  }

  function renderTextList() {
    var list = $('#text-list');
    if (!list) { return Promise.resolve(0); }
    return loadTextOverrides().then(function () {
      var q = String(textUi.q || '').trim();
      var rows = textCatalog().filter(function (r) {
        if (textUi.filter === 'tip' && r.group !== '一言欄') { return false; }
        if (textUi.filter === 'guide' && r.group !== 'ガイド') { return false; }
        if (textUi.filter === 'edited' && !textOv[r.id]) { return false; }
        if (!q) { return true; }
        return (r.def + ' ' + r.ctx + ' ' + ov(r.id, r.def)).indexOf(q) >= 0;
      });

      setHtml('#text-list', rows.map(function (r) {
        var cur = ov(r.id, r.def);
        var edited = !!textOv[r.id];
        var stale = ovStale(r.id, r.def);
        return '<button type="button" class="text-row' + (edited ? ' is-edited' : '') +
               '" data-tid="' + esc(r.id) + '">' +
               '<span class="text-row-head">' +
                 '<span class="text-row-group">' + esc(r.group) +
                   (r.no ? ' ' + r.no : '') + '</span>' +
                 '<span class="text-row-name">' + esc(r.ctx) + '／' + esc(r.name) + '</span>' +
                 (edited ? '<span class="text-badge">直した</span>' : '') +
                 (stale ? '<span class="text-badge is-stale">元が更新</span>' : '') +
               '</span>' +
               '<span class="text-row-body">' + esc(cur || '（空欄）') + '</span>' +
               '</button>';
      }).join('') || '<p class="dash-empty">あてはまる文がありません。</p>');

      var n = Object.keys(textOv).length;
      setText('#text-count', rows.length + ' 件を表示中' +
              (n ? '　／　書き換え済み ' + n + ' 件' : ''));
      return rows.length;
    });
  }

  function openTextItem(id) {
    return loadTextOverrides().then(function () {
      var r = textCatalog().filter(function (x) { return x.id === id; })[0];
      if (!r) { return null; }
      textUi.editing = r;
      setText('#text-edit-title', r.ctx + '／' + r.name);
      setText('#text-edit-where', r.group + (r.no ? ' ' + r.no + '件目' : '') + '　（' + r.id + '）');
      var area = $('#text-edit-area');
      if (area) { area.value = ov(id, r.def); }
      setText('#text-edit-default', r.def || '（元は空欄です）');
      var st2 = $('#text-edit-stale');
      if (st2) { st2.hidden = !ovStale(id, r.def); }
      M.openModal('#modal-text-edit');
      return r;
    });
  }

  function saveTextItem() {
    var r = textUi.editing;
    if (!r) { return Promise.resolve(false); }
    var area = $('#text-edit-area');
    var v = area ? area.value : '';
    return setOverride(r.id, v, r.def).then(function () {
      M.closeModals();
      tipFixedFor = null;            /* 文が変われば最大高さも変わる */
      return renderTextList();
    }).then(function () {
      return renderHomeTips();
    }).then(function () {
      M.toast('保存しました', 1800);
      return true;
    });
  }

  function revertTextItem() {
    var r = textUi.editing;
    if (!r) { return Promise.resolve(false); }
    return clearOverride(r.id).then(function () {
      M.closeModals();
      tipFixedFor = null;
      return renderTextList();
    }).then(function () { return renderHomeTips(); })
      .then(function () { M.toast('元の文に戻しました', 1800); return true; });
  }

  function resetAllText() {
    /* V1.55：確認を挟む。書き換えた文は一つずつ手で直したもので、
       一括で消すと全部やり直しになる。1タップで通してはいけない。 */
    return M.confirmAction({
      title: 'すべて元の文に戻しますか',
      body: '書き換えた文をすべて元に戻します。元には戻せません。'
          + '書き出しておけば、あとから貼り直せます。',
      ok: 'すべて戻す'
    }).then(function (yes) {
      if (!yes) { return false; }
      return doResetAllText();
    });
  }

  function doResetAllText() {
    return clearAllOverrides().then(function () {
      tipFixedFor = null;
      return renderTextList();
    }).then(function () { return renderHomeTips(); })
      .then(function () { M.toast('すべて元の文に戻しました', 2200); return true; });
  }

  /* 書き出しは「今の文」と「元の文」を並べて出す。
     元の文が無いと、パソコン側で直すときに何を変えたのか分からなくなる。 */
  function buildTextPack() {
    var items = {};
    textCatalog().forEach(function (r) {
      items[r.id] = { where: r.group + '／' + r.ctx + '／' + r.name,
                      text: ov(r.id, r.def), original: r.def };
    });
    return { schema: 'nurse_text_pack_v1', exported_at: Date.now(), items: items };
  }

  function exportTextPack() {
    return loadTextOverrides().then(function () {
      var r = S.downloadJson('NurseExamApp_TextPack_' + S.timestampName() + '_V1.00.json',
                             buildTextPack());
      M.toast(r.downloaded ? '書き出しました：' + r.filename
                           : 'この環境ではファイルを保存できません', 4000);
      return r;
    });
  }

  function importTextPack(text) {
    var data;
    try { data = JSON.parse(String(text)); }
    catch (e) { M.toast('JSONとして読めませんでした', 4000); return Promise.resolve(null); }
    if (!data || !data.items || typeof data.items !== 'object') {
      M.toast('文言パックの形式ではありません（items がありません）', 4000);
      return Promise.resolve(null);
    }
    return loadTextOverrides().then(function () {
      var cat = {}, applied = 0, unknown = 0, same = 0;
      textCatalog().forEach(function (r) { cat[r.id] = r.def; });
      Object.keys(data.items).forEach(function (id) {
        if (!(id in cat)) { unknown++; return; }
        var v = data.items[id];
        var t = (v && typeof v.text === 'string') ? v.text : null;
        if (t === null) { return; }
        if (t === cat[id]) { delete textOv[id]; same++; return; }
        textOv[id] = { text: t, base: cat[id], at: Date.now() };
        applied++;
      });
      return S.setMeta('text_overrides', textOv).then(function () {
        tipFixedFor = null;
        return renderTextList();
      }).then(function () { return renderHomeTips(); })
        .then(function () {
          M.toast('取り込みました：書き換え ' + applied + ' 件／元のまま ' + same + ' 件' +
                  (unknown ? '／不明なID ' + unknown + ' 件は無視' : ''), 5000);
          return { applied: applied, same: same, unknown: unknown };
        });
    });
  }

  /* ======================================================================
   * 復習の予定をカレンダーへ（V1.51）
   *
   * 【なぜ要るか】
   *   iOS は navigator.setAppBadge に対応していない。Web Push も
   *   16.4以降かつホーム画面に追加した場合だけで、しかもサーバーが要る。
   *   つまり iPhone では「復習が溜まったこと」に気づく方法が
   *   アプリを開くまで存在しない。
   *   そこで【アプリが通知するのをやめて、OSのカレンダーに任せる】。
   *   .ics はただのテキストなので、サーバーも通信も要らない。
   *
   * 【割り切り】
   *   書き出した時点の予定を写すだけなので、学習が進むとずれる。
   *   完全な同期は諦めて、設定画面に「前回の書き出し」を出して
   *   週1回の書き出しを促す。
   * ====================================================================== */
  var ICS_DAYS_AHEAD = 14;      /* これ以上先は、どうせ予定が変わる */

  function icsEscape(s) {
    return String(s == null ? '' : s)
      .replace(/\\/g, '\\\\').replace(/;/g, '\\;')
      .replace(/,/g, '\\,').replace(/\r?\n/g, '\\n');
  }

  function icsStamp(d) {
    var p = function (n) { return String(n).padStart(2, '0'); };
    return d.getUTCFullYear() + p(d.getUTCMonth() + 1) + p(d.getUTCDate()) + 'T' +
           p(d.getUTCHours()) + p(d.getUTCMinutes()) + '00Z';
  }

  function icsDay(d) {
    var p = function (n) { return String(n).padStart(2, '0'); };
    return d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate());
  }

  /* 期日ごとに1件。同じ日の分はまとめる（1日に20件も並べない）。 */
  function buildIcs(byDay, plan, hour) {
    var out = ['BEGIN:VCALENDAR', 'VERSION:2.0',
               'PRODID:-//Omoidasu//Review Plan//JA', 'CALSCALE:GREGORIAN'];
    var now = new Date();
    Object.keys(byDay).sort().forEach(function (key, i) {
      var d = byDay[key];
      var n = d.count;
      var title = 'オモイダス：復習 ' + n + '問';
      var desc = '期日を迎えた選択肢が ' + n + " 件あります。";
      if (plan && plan.has_exam && plan.pace === 'ok') {
        desc += '\n新しい問題の目安は1日 ' + plan.need_new + ' 問です。';
      }
      var start = new Date(d.date.getFullYear(), d.date.getMonth(), d.date.getDate(), hour, 0, 0);
      var end   = new Date(start.getTime() + 30 * 60000);
      out.push('BEGIN:VEVENT');
      out.push('UID:omoidasu-' + icsDay(d.date) + '-' + i + '@omoidasu');
      out.push('DTSTAMP:' + icsStamp(now));
      out.push('DTSTART:' + icsDay(start) + 'T' + String(hour).padStart(2, '0') + '0000');
      out.push('DTEND:' + icsDay(end) + 'T' + String(end.getHours()).padStart(2, '0') + '3000');
      out.push('SUMMARY:' + icsEscape(title));
      out.push('DESCRIPTION:' + icsEscape(desc));
      /* 15分前に鳴らす。これが iOS で唯一まともに届く「通知」になる。 */
      out.push('BEGIN:VALARM', 'TRIGGER:-PT15M', 'ACTION:DISPLAY',
               'DESCRIPTION:' + icsEscape(title), 'END:VALARM');
      out.push('END:VEVENT');
    });
    out.push('END:VCALENDAR');
    return out.join('\r\n');
  }

  function downloadText(filename, text, mime) {
    if (typeof Blob === 'undefined' || typeof global.URL === 'undefined') { return false; }
    var blob = new Blob([text], { type: mime || 'text/plain;charset=utf-8' });
    var url = global.URL.createObjectURL(blob);
    var a = global.document.createElement('a');
    a.href = url; a.download = filename; a.style.display = 'none';
    global.document.body.appendChild(a);
    a.click();
    global.setTimeout(function () {
      global.document.body.removeChild(a);
      global.URL.revokeObjectURL(url);
    }, 1500);
    return true;
  }

  function exportReviewCalendar() {
    return Promise.all([S.getAllAtoms(), S.loadMeta(), K.getHomeState()]).then(function (r) {
      var atoms = r[0], meta = r[1], home = r[2];
      var hour = isNum(meta.day_boundary_hour) ? Math.max(6, meta.day_boundary_hour + 3) : 7;
      var now = Date.now();
      var limit = now + ICS_DAYS_AHEAD * 86400000;
      var byDay = {};
      atoms.forEach(function (a) {
        if (!isNum(a.due_date)) { return; }
        /* 期日を過ぎた分は「今日」にまとめる。過去の日付で予定を作らない。 */
        var t = Math.max(a.due_date, now);
        if (t > limit) { return; }
        var d = new Date(t);
        var key = icsDay(d);
        if (!byDay[key]) { byDay[key] = { date: d, count: 0 }; }
        byDay[key].count++;
      });
      if (!Object.keys(byDay).length) {
        toast('これから2週間に復習の予定がありません', 3600);
        return { events: 0 };
      }
      var text = buildIcs(byDay, home.plan, hour);
      var ok2 = downloadText('omoidasu_review.ics', text, 'text/calendar;charset=utf-8');
      return S.setMeta('ics_exported_at', Date.now()).then(function () {
        if (ok2) { toast('カレンダーに追加してください（' + Object.keys(byDay).length + '日ぶん）', 4600); }
        return { events: Object.keys(byDay).length, text: text };
      });
    });
  }

  /* ======================================================================
   * 間違いノート（印刷／PDF）（V1.51）
   *
   * 【なぜ紙なのか】
   *   実習中の病院ではスマホを出せない。実習は数週間から数ヶ月あり、
   *   その間このアプリは開けない。紙なら白衣のポケットに入る。
   *   ここは他のアプリが埋めていない穴。
   *
   * 【なぜ用紙を選ばせるのか】
   *   白衣に入れたいならA5、カバンで持ち歩けるならA4と、
   *   置かれた状況で最適が変わる。既定はA4＋中折り。
   *   家庭用プリンタはA5給紙に対応していないことが多く、
   *   A5指定は「選べるのに印刷できない」になりやすいため。
   * ====================================================================== */
  var PAPER = { A4: 'A4', A5: 'A5', B4: 'B4', B5: 'JIS-B5' };

  /* --- 印刷量の上限（V1.74） ---
     実測：1,173問を入れて「難しい」が100問たまった状態で印刷すると、
     A4・1段・解説ありで **34.5枚**（400問なら233枚）。
     いまは上限が無く、枚数が分からないまま印刷画面が開く。
     数を絞るときは【何問中の何問か】を紙面にも書く。黙って切らない。 */
  function limitNoteItems(items, limit) {
    if (!limit || items.length <= limit) { return items; }
    /* 絞るときだけ並べ替える。全部のときは順序を変えない（従来どおり）。 */
    return items.slice().sort(function (a, b) {
      return (b.last_at || 0) - (a.last_at || 0);
    }).slice(0, limit);
  }

  function collectNoteItems(kind) {
    return Promise.all([S.getStarredNote(), S.getAllAtoms()]).then(function (r) {
      var starred = r[0] || [], atoms = r[1] || [];
      var hardByQ = {};
      atoms.forEach(function (a) {
        if (a.last_eval !== 'hard') { return; }
        if (!hardByQ[a.q_id]) { hardByQ[a.q_id] = []; }
        hardByQ[a.q_id].push(a.atom_id);
      });
      /* 絞り込みの並べ替えに使う「最後に解いた時刻」を問題ごとに拾う（V1.74） */
      var lastAt = {};
      atoms.forEach(function (a) {
        var t = a.last_answered_at || 0;
        if (t > (lastAt[a.q_id] || 0)) { lastAt[a.q_id] = t; }
      });
      var map = {};
      if (kind !== 'hard') {
        starred.forEach(function (x) {
          map[x.question.q_id] = { question: x.question, marks: x.marked_atoms.slice(), why: '★',
                                   last_at: lastAt[x.question.q_id] || 0 };
        });
      }
      if (kind !== 'star') {
        var ids = Object.keys(hardByQ).filter(function (id) { return !map[id]; });
        if (!ids.length) { return Object.keys(map).map(function (k) { return map[k]; }); }
        return S.getQuestionsFull(ids).then(function (full) {
          full.forEach(function (q) {
            map[q.q_id] = { question: q, marks: hardByQ[q.q_id], why: '難',
                            last_at: lastAt[q.q_id] || 0 };
          });
          Object.keys(map).forEach(function (k) {
            if (hardByQ[k] && map[k].why === '★') { map[k].why = '★難'; }
          });
          return Object.keys(map).map(function (k) { return map[k]; });
        });
      }
      return Object.keys(map).map(function (k) { return map[k]; });
    });
  }

  function noteItemHtml(item, opts) {
    var q = item.question;
    var marks = {};
    (item.marks || []).forEach(function (id) { marks[id] = 1; });
    var head = '<div class="pn-head"><span class="pn-why">' + item.why + '</span>' +
               '<span class="pn-code">' + (q.num_code || '') + '</span>' +
               '<span class="pn-path">' + [q.unit, q.major, q.medium].filter(Boolean).join(' ＞ ') + '</span></div>';
    var stem = '<div class="pn-stem">' + (q.stem || '') + '</div>';
    var list = (q.atoms || []).map(function (a) {
      var mark = a.is_correct ? '●' : '○';
      var star = marks[a.atom_id] ? '<span class="pn-mark">▲</span>' : '';
      return '<li class="pn-atom' + (a.is_correct ? ' is-correct' : '') + '">' +
             '<span class="pn-num">' + mark + '</span>' + star +
             '<span class="pn-text">' + (a.text || '') + '</span></li>';
    }).join('');
    var body = '';
    if (opts.explain !== 'none') {
      var exp = (q.atoms || []).filter(function (a) { return a.explanation; })
        .map(function (a) {
          return '<li><b>' + (a.is_correct ? '○' : '×') + '</b> ' + a.explanation + '</li>';
        }).join('');
      body = '<div class="pn-exp' + (opts.explain === 'back' ? ' pn-back' : '') + '">' +
             (q.overall_explanation ? '<p>' + q.overall_explanation.replace(/<[^>]+>/g, ' ') + '</p>' : '') +
             (exp ? '<ul>' + exp + '</ul>' : '') +
             /* 自分で書いたメモも、紙に出すときは必ずエスケープする（V1.84）。
                「<」を書いただけで紙面が崩れる。 */
             (q.user_memo ? '<p class="pn-memo">✎ ' + esc(q.user_memo) + '</p>' : '') +
             '</div>';
    }
    return '<article class="pn-item">' + head + stem + '<ul class="pn-atoms">' + list + '</ul>' + body + '</article>';
  }

  function buildPrintSheet(cfg) {
    return collectNoteItems(cfg.kind).then(function (all) {
      var total = all.length;
      var items = limitNoteItems(all, cfg.limit);
      if (!items.length) {
        toast('★も「難しい」もまだありません', 3600);
        return { count: 0, total: 0 };
      }
      var sheet = $('#print-sheet');
      if (!sheet) { return { count: 0 }; }
      /* --- 白紙印刷バグの修正（V1.70） ---
         #print-sheet は index.html 上 #modal-layer の中にあるが、
         印刷CSSは modal-layer を display:none で消す（2箇所とも）。
         中にいる限り、紙面は組み上がっていても【必ず白紙で出る】。
         初回の組み立て時に body 直下へ移して、覆いの生死と縁を切る。 */
      if (sheet.parentElement !== global.document.body) {
        global.document.body.appendChild(sheet);
      }
      var style = $('#print-page-style');
      if (!style) {
        style = global.document.createElement('style');
        style.id = 'print-page-style';
        global.document.head.appendChild(style);
      }
      /* @page の size は CSS変数では指定できないので、都度書き換える。 */
      style.textContent = '@page{ size:' + (PAPER[cfg.paper] || 'A4') + '; margin:12mm 10mm; }';
      sheet.setAttribute('data-cols', cfg.cols === '2' ? '2' : '1');
      sheet.innerHTML =
        '<h1 class="pn-title">オモイダス　間違いノート</h1>' +
        '<p class="pn-meta">' +
        (items.length < total
          ? total + '問中 ' + items.length + '問（最後に解いた順）'
          : items.length + '問') + '　／　' +
        (cfg.kind === 'star' ? '★のみ' : cfg.kind === 'hard' ? '「難しい」のみ' : '★と「難しい」') +
        '　／　' + (PAPER[cfg.paper] || 'A4') + '</p>' +
        items.map(function (it) { return noteItemHtml(it, cfg); }).join('') +
        /* --- 出典表記（V1.66） ---
           このノートは実習室や図書館で紙のまま回覧される。
           出どころが書いていない紙は「あの子の自作プリント」で終わり、
           見た人がアプリへたどり着く経路が無い。
           控えめに最終ページの末尾へ1行だけ。広告然とさせない。 */
        printCredit();
      return { count: items.length, total: total };
    });
  }

/* --- 印刷用QR（V1.75・tools/make_qr.py で生成） ---
   中身: https://omoidasu-kokushi.github.io/
   版3・誤り訂正M・29×29モジュール
   URLを変えたら make_qr.py を実行して差し替えること。 */
var QR_URL = 'https://omoidasu-kokushi.github.io/';
var QR_MATRIX = [
  '11111110010011101111001111111',
  '10000010111110110101101000001',
  '10111010011011101011101011101',
  '10111010000101110011101011101',
  '10111010101110101111001011101',
  '10000010001101011101101000001',
  '11111110101010101010101111111',
  '00000000010001101111100000000',
  '10101010010000111110000010010',
  '01110101010110100000111001001',
  '00010010101001000100011110111',
  '01100000010000001100010110010',
  '10011010000010011101111001011',
  '11101101100111001100111001001',
  '11110010101110100100001101011',
  '00111001101101110110100011010',
  '11010111001010111101111001011',
  '01101100000010101000101001101',
  '10100111111001001010001110011',
  '01001000001010001110001011010',
  '10001011100100011101111110000',
  '00000000100011000111100010111',
  '11111110011100101001101011011',
  '10000010000001100100100011001',
  '10111010100100101100111110001',
  '10111010001100101000000110111',
  '10111010101111100011010111001',
  '10000010000010111101100010010',
  '11111110100000000100111100011'
];

  /* --- 紙のQR（V1.75） ---
     【なぜURLの文字だけでは足りないか】
     このノートは実習室や図書館で紙のまま回る（V1.66の出典表記の狙い）。
     ところが**紙のURLは打ち込まれない。** 見た人がアプリへ来る経路として
     文字列は事実上機能しないので、その場で読めるQRにする。

     【なぜ画像を貼らないか】
     外部のQR生成APIはオフライン要件に反する（圏外で真っ白になる）。
     符号化器を積むとコードが6〜8KB増える。URLは固定なので、
     **行列だけを定数で持ち、その場でSVGを組む**のがいちばん軽くて壊れない。

     【印刷での寸法】
     29モジュール＋クワイエットゾーン4モジュール（規格上必須。
     余白を削ると読み取り率が落ちる）。紙面では22mm角で出す
     （スマホのカメラが安定して読める下限が15mm前後）。
     色は必ず黒／白で焼く。テーマ色を使うと、セピアやダークの設定のまま
     刷ったときにコントラストが落ちて読めなくなる。 */
  function qrSvg(label) {
    var n = QR_MATRIX.length, quiet = 4, span = n + quiet * 2;
    var d = '', y, x, row;
    for (y = 0; y < n; y++) {
      row = QR_MATRIX[y];
      for (x = 0; x < n; x++) {
        if (row.charAt(x) === '1') {
          d += 'M' + (x + quiet) + ' ' + (y + quiet) + 'h1v1h-1z';
        }
      }
    }
    return '<svg class="pn-qr" viewBox="0 0 ' + span + ' ' + span + '" role="img" ' +
           'aria-label="' + esc(label || QR_URL) + '" shape-rendering="crispEdges">' +
           '<rect width="' + span + '" height="' + span + '" fill="#fff"/>' +
           '<path d="' + d + '" fill="#000"/></svg>';
  }

  /* 紙の隅に置く出典。QRを主にし、URLの文字は読めなかったときの控えとして小さく残す。 */
  function printCredit() {
    return '<div class="pn-credit">' + qrSvg('オモイダス ' + QR_URL) +
           '<span class="pn-credit-text">オモイダス<br>看護師国家試験 対策アプリ<br>' +
           '<small>omoidasu-kokushi.github.io</small></span></div>';
  }

  /* --- 印刷する前に「何問・およそ何枚か」を見せる（V1.74） ---
     枚数は実測から出す：A4・1段・解説ありで **1問あたり約0.35枚**
     （1,173問投入・「難しい」100問で34.5枚を実測。幅794px＝A4相当で計測）。
     2段で約0.28枚／問、解説なしなら約0.20枚／問（同条件の実測）。
     紙は実際の内容量で前後するので「およそ」と書く。
     数字を出す目的は正確さではなく、**200枚の印刷を知らずに始めさせないこと**。 */
  var NOTE_PAGE_PER_Q = { '1all': 0.35, '1none': 0.20, '2all': 0.28, '2none': 0.13 };

  function noteSheetsFor(n, cols, explain) {
    var key = (cols === '2' ? '2' : '1') + (explain === 'none' ? 'none' : 'all');
    return Math.max(1, Math.round(n * (NOTE_PAGE_PER_Q[key] || 0.35)));
  }

  function refreshNoteCount() {
    var el = $('#note-count');
    if (!el) { return Promise.resolve(0); }
    var kind = ($('#note-kind') || {}).value || 'both';
    var limit = parseInt(($('#note-limit') || {}).value || '0', 10) || 0;
    var cols = ($('#note-cols') || {}).value || '1';
    var explain = ($('#note-explain') || {}).value || 'all';
    return collectNoteItems(kind).then(function (all) {
      var n = limit ? Math.min(all.length, limit) : all.length;
      if (!all.length) {
        el.textContent = '対象がまだありません（★を付けるか「難しい」を押すと集まります）';
        return 0;
      }
      var sheets = noteSheetsFor(n, cols, explain);
      el.textContent = '対象 ' + n + '問'
        + (n < all.length ? '（全' + all.length + '問中・最後に解いた順）' : '')
        + '　／　' + (PAPER[($('#note-paper') || {}).value] || 'A4')
        + 'でおよそ ' + sheets + '枚';
      return n;
    }).catch(function () { el.textContent = ''; return 0; });
  }

  function runPrintNote() {
    var cfg = {
      kind:  ($('#note-kind') || {}).value || 'both',
      paper: ($('#note-paper') || {}).value || 'A4',
      cols:  ($('#note-cols') || {}).value || '1',
      explain: ($('#note-explain') || {}).value || 'all',
      limit: parseInt(($('#note-limit') || {}).value || '0', 10) || 0
    };
    return buildPrintSheet(cfg).then(function (r) {
      if (!r.count) { return r; }
      closeModals();
      global.document.body.classList.add('is-printing');
      global.setTimeout(function () {
        try { global.print(); } catch (e) { /* 印刷できない環境では何もしない */ }
        global.setTimeout(function () {
          global.document.body.classList.remove('is-printing');
        }, 800);
      }, 120);
      return r;
    });
  }

  /* ======================================================================
   * 学習レポート（V1.70）
   *
   * 【なぜ作るか】
   *   戦略レビュー§1-2：学校パイロットの本命。教員が欲しいのは管理画面では
   *   なく「誰が危ないか」の一覧。サーバーを持たない代わりに、学生が自分で
   *   レポートを書き出して提出する。自己確認にもそのまま使える。
   *
   * 【設計の線引き】
   *   ・載せるのは実測値だけ（定着率・解答量・苦手の並び）。
   *     合格可能性の「%」の類は載せない（§2-1と同じ理由：母集団が無い）
   *   ・間違いノート（V1.51）の印刷機構をそのまま使う。新しい画面を作らない
   *   ・A4固定・設定なし。提出物は形が揃っていることに価値がある
   * ====================================================================== */

  function reportRow(cells) {
    return '<tr>' + cells.map(function (c, i) {
      return (i === 0 ? '<th>' + c + '</th>' : '<td>' + c + '</td>');
    }).join('') + '</tr>';
  }

  function buildReportSheet() {
    return Promise.all([
      K.getHomeState(),
      K.buildDashboard({ level: 'unit' }),
      K.buildDashboard({ level: 'medium' }),
      S.getConceptStats(),
      S.loadMeta()
    ]).then(function (r) {
      var home = r[0], byUnit = r[1], byMedium = r[2], concepts = r[3] || [], meta = r[4];

      var answeredTotal = home.solved_questions || 0;
      if (!answeredTotal) {
        toast('まだ解答がありません。少し解いてから書き出せます', 3600);
        return { count: 0 };
      }

      var sheet = $('#print-sheet');
      if (!sheet) { return { count: 0 }; }
      /* --- 白紙印刷バグの修正（V1.70） ---
         #print-sheet は index.html 上 #modal-layer の中にあるが、
         印刷CSSは modal-layer を display:none で消す（2箇所とも）。
         中にいる限り、紙面は組み上がっていても【必ず白紙で出る】。
         初回の組み立て時に body 直下へ移して、覆いの生死と縁を切る。 */
      if (sheet.parentElement !== global.document.body) {
        global.document.body.appendChild(sheet);
      }
      var style = $('#print-page-style');
      if (!style) {
        style = global.document.createElement('style');
        style.id = 'print-page-style';
        global.document.head.appendChild(style);
      }
      style.textContent = '@page{ size:A4; margin:14mm 12mm; }';
      sheet.setAttribute('data-cols', '1');

      var d = new Date();
      var dateStr = d.getFullYear() + '-' +
        ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);

      /* 試験日カウントダウン（設定されているときだけ） */
      var b = (typeof meta.day_boundary_hour === 'number') ? meta.day_boundary_hour : 4;
      var rest = K.examRemainingDays ? K.examRemainingDays(meta, Date.now(), b) : null;
      var examLine = (rest !== null && rest !== undefined && rest >= 0)
        ? '　／　試験日まで ' + rest + ' 日' : '';

      /* --- 1. 学習量（実測） --- */
      var vol =
        '<table class="rp-table">' +
        reportRow(['学習日数', (meta.open_days_total || 0) + ' 日（連続 ' + (meta.open_streak || 0) + ' 日）']) +
        reportRow(['解答済みの問題', answeredTotal + ' ／ ' + (home.total_questions || 0) + ' 問']) +
        reportRow(['分析スキャン精度', ((home.scan && home.scan.pct) || 0) + '%（弱点分析の信頼度）']) +
        '</table>';

      /* --- 2. 単元ごとの定着率（低い順・実測） ---
         定着率＝「普通以上」の割合。分母は範囲内の全肢（未学習を含む）。
         手つかずの単元が100%に見える事故を防ぐ（scheduler と同じ定義）。 */
      var unitRows = (byUnit.rows || []).map(function (g) {
        var answered = Math.max(0, (g.total_atoms || 0) - (g.unlearned_atoms || 0));
        return reportRow([
          esc(g.label),
          (g.retention_pct || 0) + '%',
          answered + ' ／ ' + (g.total_atoms || 0) + ' 肢',
          (g.hard_atoms || 0) + ' 肢'
        ]);
      }).join('');
      var units =
        '<table class="rp-table rp-grid">' +
        '<tr><th>単元（定着率が低い順）</th><th>定着率</th><th>解答済み</th><th>「難しい」</th></tr>' +
        unitRows + '</table>';

      /* --- 3. 弱点の中項目 TOP5（解答があるものだけ） --- */
      var weak = (byMedium.rows || []).filter(function (g) {
        return ((g.total_atoms || 0) - (g.unlearned_atoms || 0)) > 0;
      }).slice(0, 5);
      var weakRows = weak.map(function (g) {
        var crumb = String(g.crumb || '').split(' ＞ ').slice(0, 3).join(' ＞ ');
        return reportRow([
          (g.num_code ? esc(g.num_code) + ' ' : '') + esc(crumb || g.label),
          (g.retention_pct || 0) + '%',
          (g.hard_atoms || 0) + ' 肢'
        ]);
      }).join('');
      var weakHtml = weak.length
        ? '<table class="rp-table rp-grid">' +
          '<tr><th>次に固めるべき中項目（定着率が低い順）</th><th>定着率</th><th>「難しい」</th></tr>' +
          weakRows + '</table>'
        : '';

      /* --- 4. 苦手な概念 TOP5（評価済みのタグだけ。null は未学習＝載せない） --- */
      var weakConcepts = concepts.filter(function (c) {
        return c.in_master && c.score !== null && c.score !== undefined && (c.atom_count || 0) > 0;
      }).sort(function (a, bb) { return a.score - bb.score; }).slice(0, 5);
      var conceptRows = weakConcepts.map(function (c) {
        return reportRow([esc(c.label), Math.round(c.score) + '%', (c.evaluated_count || 0) + ' 肢']);
      }).join('');
      var conceptHtml = weakConcepts.length
        ? '<table class="rp-table rp-grid">' +
          '<tr><th>苦手な概念（理解率が低い順）</th><th>理解率</th><th>評価済み</th></tr>' +
          conceptRows + '</table>'
        : '';

      sheet.innerHTML =
        '<h1 class="pn-title">オモイダス　学習レポート</h1>' +
        '<p class="pn-meta">書き出し日 ' + dateStr + examLine +
        '　／　氏名：<span class="rp-name"></span></p>' +
        '<h2 class="rp-sec">学習量</h2>' + vol +
        '<h2 class="rp-sec">単元ごとの定着率</h2>' + units +
        (weakHtml ? '<h2 class="rp-sec">弱点の中項目 TOP5</h2>' + weakHtml : '') +
        (conceptHtml ? '<h2 class="rp-sec">苦手な概念 TOP5</h2>' + conceptHtml : '') +
        '<p class="rp-note">定着率＝「普通」以上の評価が付いた選択肢の割合（未学習を含む全肢が分母）。' +
        'すべてこのアプリでの実測値です。</p>' +
        printCredit();

      return { count: answeredTotal };
    });
  }

  function runPrintReport() {
    return buildReportSheet().then(function (r) {
      if (!r.count) { return r; }
      closeModals();
      global.document.body.classList.add('is-printing');
      global.setTimeout(function () {
        try { global.print(); } catch (e) { /* 印刷できない環境では何もしない */ }
        global.setTimeout(function () {
          global.document.body.classList.remove('is-printing');
        }, 800);
      }, 120);
      return r;
    });
  }

  /* ======================================================================
   * 同期で残せなかったメモ（V1.72）
   * 競合の解決は「新しい方を採用」のまま（§11の設計どおり）。
   * ここは負けた側の文面の控え置き場：復元はしない（勝った方を黙って
   * 上書きするのは、消えるより性質が悪い）。読む・写す・片づけるの3つだけ。
   * ====================================================================== */
  function conflictEntries() {
    return S.loadMeta().then(function (mm) {
      return Array.isArray(mm.sync_conflicts) ? mm.sync_conflicts.slice() : [];
    });
  }

  function renderConflictList() {
    return conflictEntries().then(function (list) {
      var box = $('#conflict-list');
      if (!box) { return list; }
      if (!list.length) {
        setHtml('#conflict-list', '<p class="set-note">控えはありません。</p>');
        return list;
      }
      var qids = list.map(function (e) { return String(e.key).split('|')[0]; });
      return S.getQuestionsFull(qids).then(function (qs) {
        var stemBy = {};
        (qs || []).forEach(function (q) { stemBy[q.q_id] = q.stem || ''; });
        setHtml('#conflict-list', list.map(function (e, i) {
          var qid = String(e.key).split('|')[0];
          var d = new Date(Number(e.at || 0));
          var when = d.getFullYear() ? (d.getMonth() + 1) + '/' + d.getDate() : '';
          return '<div class="conflict-item" data-ci="' + i + '">' +
            '<p class="conflict-head"><b>' + esc(when) + '</b>　' +
            esc((stemBy[qid] || qid).slice(0, 36)) + '…</p>' +
            '<p class="conflict-memo">' + esc(e.memo || '') + '</p>' +
            '<div class="conflict-actions">' +
            '<button type="button" class="btn-ghost btn-sm" data-ccopy="' + i + '">文面をコピー</button>' +
            '<button type="button" class="btn-ghost btn-sm is-danger" data-cdel="' + i + '">片づける</button>' +
            '</div></div>';
        }).join(''));
        return list;
      });
    });
  }

  function openSyncConflicts() {
    return renderConflictList().then(function () { openModal('#modal-conflicts'); });
  }

  function conflictCopy(i) {
    return conflictEntries().then(function (list) {
      var e = list[i];
      if (!e) { return; }
      var t = e.memo || '';
      var done = function () { toast('メモの文面をコピーしました', 2600); };
      if (global.navigator.clipboard && global.navigator.clipboard.writeText) {
        return global.navigator.clipboard.writeText(t).then(done)
          .catch(function () { toast('コピーできませんでした。長押しで選択してください', 3600); });
      }
      toast('コピーできませんでした。長押しで選択してください', 3600);
    });
  }

  function conflictDismiss(i) {
    return M.confirmAction({
      title: 'この控えを片づけますか？',
      body: '片づけると、この文面はどこにも残りません。必要な部分は先にコピーしてください。',
      ok: '片づける'
    }).then(function (yes) {
      if (!yes) { return null; }
      return conflictEntries().then(function (list) {
        list.splice(i, 1);
        return S.setMeta('sync_conflicts', list);
      }).then(function () { return refreshDrive(); })
        /* 確認の覆いが一覧を畳んでいるので、続けて片づけられるよう開き直す */
        .then(function () { return openSyncConflicts(); });
    });
  }

  function conflictClearAll() {
    return M.confirmAction({
      title: 'すべての控えを片づけますか？',
      body: '片づけると、これらの文面はどこにも残りません。必要な部分は先にコピーしてください。',
      ok: 'すべて片づける'
    }).then(function (yes) {
      if (!yes) { return null; }
      return S.setMeta('sync_conflicts', []).then(function () {
        return refreshDrive();
      }).then(function () { closeModals(); toast('すべて片づけました', 2600); });
    });
  }

  function openStarredNote() {
    return M.go('starred').then(function () { return renderStarredNote(st.starred.filter); })
      .then(function (r) {
        global.setTimeout(function () {
          tip('starred').then(function (shown) { return shown ? true : tip('unstar'); });
        }, 500);
        return r;
      });
  }

  function renderStarredNote(filter) {
    st.starred.filter = filter || st.starred.filter;
    $$('#screen-starred .seg-btn[data-sfilter]').forEach(function (b) {
      cls(b, 'is-active', b.getAttribute('data-sfilter') === st.starred.filter);
    });

    return S.getStarredNote().then(function (list) {
      var f = st.starred.filter;
      var rows = list.filter(function (x) {
        if (f === 'question') { return x.kind === 'question' || x.kind === 'both'; }
        if (f === 'atom') { return x.kind === 'atom' || x.kind === 'both'; }
        return true;
      });

      if (!rows.length) {
        setHtml('#star-list', '');
        show('#star-empty');
        return rows;
      }
      hide('#star-empty');

      /* 文脈保持表示：問題文・全選択肢・拡張解説を全文出し、
         ★の付いた箇所だけ 太字＋黄色ハイライトで強調する */
      setHtml('#star-list', rows.map(function (x) {
        var q = x.question;
        var qStar = (x.kind === 'question' || x.kind === 'both');
        var marked = {};
        x.marked_atoms.forEach(function (id) { marked[id] = true; });

        return '<article class="star-item" data-qid="' + esc(q.q_id) + '">' +
          '<div class="star-item-head">' +
          '<span class="rank-badge ' + esc(q.rank) + '">' + esc(q.rank) + '</span>' +
          '<small class="num-code">' + esc(q.num_code || '') + '</small>' +
          '<span class="star-item-kind">' + kindLabel(x.kind) + '</span>' +
          '<button type="button" class="star-unmark" data-unstar="question" data-qid="' + esc(q.q_id) + '"' +
          ' aria-label="問題★を外す">' + (qStar ? '★' : '☆') + '</button></div>' +
          '<div class="star-item-body">' +
          '<p class="star-stem' + (qStar ? ' is-marked' : '') + '">' + esc(q.stem) + '</p>' +
          '<div class="star-choices">' + (q.atoms || []).map(function (a) {
            return '<div class="star-choice' + (marked[a.atom_id] ? ' is-marked' : '') + '">' +
                   '<span class="star-choice-num">' + circled(a.original_num) + '</span>' +
                   '<span>' + esc(a.text) + (a.is_correct ? '　【正】' : '') + '</span>' +
                   '<button type="button" class="star-unmark" data-unstar="atom" data-atom="' + esc(a.atom_id) + '"' +
                   ' aria-label="選択肢★を外す">' + (marked[a.atom_id] ? '★' : '☆') + '</button></div>';
          }).join('') + '</div>' +
          '<div class="explanation-body">' + M.prepareExplanationHtml(q.overall_explanation || '') + '</div>' +
          (q.comparison_table ? '<div class="explanation-body">' + M.prepareExplanationHtml(q.comparison_table) + '</div>' : '') +
          '</div></article>';
      }).join(''));
      return rows;
    });

    function kindLabel(k) {
      return k === 'both' ? '問題に★ ＋ 選択肢に★' : k === 'question' ? '問題に★' : '選択肢に★';
    }
  }

  /* ======================================================================
   * 7. 力試しモード（第11章）
   * ====================================================================== */

  var EXAM_SIZE = { mock_30: 30, mock_60: 60, mock_120: 120, mock_weak: 120 };

  function openExamList() {
    return Promise.all([K.refreshUnlocks(), S.countQuestions()]).then(function (r) {
      var unlocks = r[0].unlocks, totalQ = r[1];
      var byId = {};
      unlocks.forEach(function (u) { byId[u.id] = u; });

      $$('#exam-list .exam-card').forEach(function (card) {
        var id = ({ mini30: 'mock_30', half60: 'mock_60', full120: 'mock_120', evil120: 'mock_weak' })[card.getAttribute('data-exam')];
        var u = byId[id];
        if (!u) { return; }
        card.dataset.examId = id;
        cls(card, 'is-unlocked', u.unlocked);
        cls(card, 'is-locked', !u.unlocked);
        var fill = card.querySelector('.exam-prog i');
        if (fill) { fill.style.width = u.pct + '%'; }
        var state2 = card.querySelector('.exam-state');
        if (state2) {
          state2.textContent = u.unlocked ? '解禁ずみ'
            : (totalQ < u.required_questions
                ? '問題数 ' + totalQ + ' / ' + u.required_questions + ' 問'
                : '解放 ' + u.pct + '%');
        }
      });
      return M.go('exam');
    }).then(function (r) { global.setTimeout(function () { tip('exam'); }, 500); return r; });
  }

  /* --- 模試の受け方（V1.50） ---
     'real'  … 本番モード。全ランク・本番と同じ配分。実力を測る
     'final' … 直前モード。S/A中心・一度解けた問題から。成功体験のため
     どちらも【合格基準は本番と同じ】。変えるのは出題だけ。 */
  /* --- 模試の混ぜ方（V1.54。V1.52 の分類を置き換え） ---
     ものさしは【最後に見てからの距離】。
       fresh  … 最近解いた。文面を覚えている ＝ 記憶で解けてしまい測定を汚す
       faded  … 解いたが、文面を思い出せないところまで離れた ＝ **本番に最も近い**
       unseen … この問題自体が初見

     V1.52 の分類（solved / familiar / novel）を捨てた理由：
     familiar と novel は「その中項目を学んだか」で決めていた。
     **学習が進むと全ての中項目が学習済みになり、novel が消える。**
     消えた瞬間、模試は解いた問題ばかりになって実力が測れなくなる。
     分類が学習の進行に耐えられていなかった。

     ■ 本番モード（実力を測る）
       fresh 25% … 実測した本番の再出題率（言い回し違い込み 25.0%）に合わせる
       faded 45% … 本番の主成分。文面は忘れたが知識はある、という状態
       unseen 30% … 本番にも初見は出る。ゼロにしない

     ■ 直前モード（成功体験）
       fresh 55% ／ faded 45% ／ unseen 0%
       初見はぶつけない。ただし合格基準は本番と同じまま変えない。 */
  var EXAM_MIX = {
    real : { fresh: 0.25, faded: 0.45, unseen: 0.30 },
    final: { fresh: 0.55, faded: 0.45, unseen: 0.00 }
  };

  function examStyleOpts(style, examId) {
    if (examId === 'mock_weak') { return {}; }        /* いじわる模試は弱点順のまま */
    var mix = EXAM_MIX[style === 'final' ? 'final' : 'real'];
    if (style !== 'final') { return { mix: mix }; }
    return { ranks: ['S', 'A'], mix: mix };
  }

  function askExamStyle(examId) {
    st.exam.pendingStyleId = examId;
    openModal('#modal-exam-style');
    return null;
  }

  function startExam(examId, style) {
    var size = EXAM_SIZE[examId] || 30;

    return S.getUnlockState().then(function (states) {
      var s2 = states.filter(function (x) { return x.id === examId; })[0];
      if (!s2 || !s2.unlocked) { toast('この模試はまだ解禁されていません'); return null; }
      return K.shouldWarnBeforeExam(examId);
    }).then(function (warn) {
      if (!warn) { return null; }
      if (warn.warn) {
        /* 定着率が基準未満でも使用可。伴走ダイアログで自律選択させる（第11章②） */
        st.exam.pendingId = examId;
        setHtml('#modal-exam-warn .modal-body',
          '今の定着率は <b>' + warn.current + '%</b>（推奨 ' + warn.required + '%）。' +
          'ただ、単元学習で少し知識を補強しておくと、合格率がもっと上がるかも。どうする？');
        openModal('#modal-exam-warn');
        return null;
      }
      /* 受け方をまだ選んでいなければ先に聞く（いじわる模試は聞かない）。 */
      if (!style && examId !== 'mock_weak') { return askExamStyle(examId); }
      return launchExam(examId, size, style);
    });
  }

  function launchExam(examId, size, style) {
    /* --- 模試だけが予想問題を拾える（V1.56） ---
       'mock' プールの問題は、ランダムにも単元学習にも復習にも出ない。
       ここで初めて出会わせる。一度出会えば台帳に履歴が付き、
       以降は普通の問題として復習にも出るようになる。

       いじわる模試（弱点120問）は【すでに解いた弱点を狙う】モードなので、
       初見の予想問題を混ぜる意味がない。ここだけ拾わない。 */
    var opts = (examId === 'mock_weak')
      ? { mode: 'exam', count: size, applyGuard: false, preferFrequent: true }   /* 弱点順で抽出 */
      : { mode: 'exam', count: size, applyGuard: false, shuffle: true, includeMock: true };
    var extra = examStyleOpts(style, examId);
    Object.keys(extra).forEach(function (k) { opts[k] = extra[k]; });

    return K.buildQueue(opts).then(function (q) {
      /* 直前モードで候補が足りないことがある（S/Aだけでは数が揃わない）。
         そのときは黙って本番モードに落とさず、断わってから落とす。 */
      if (style === 'final' && q.questions.length < size) {
        toast('S・Aランクだけでは ' + size + '問に届かないので、他のランクも混ぜます', 4200);
        return K.buildQueue({ mode: 'exam', count: size, applyGuard: false,
                              shuffle: true, preferKnown: true, includeMock: true })
          .then(function (q2) { return finishLaunch(examId, q2, style); });
      }
      return finishLaunch(examId, q, style);
    });
  }

  function finishLaunch(examId, q, style) {
    return Promise.resolve().then(function () {
      if (!q.questions.length) { toast('出題できる問題がありません'); return null; }

      st.exam = {
        id: examId, style: style || 'real',
        questions: q.questions, answers: [], index: 0,
        startedAt: Date.now(), size: q.questions.length
      };

      /* 模試は解説を挟まず全問回答 → 一括採点。前半のフックで割り込む。 */
      M.hooks.afterGrade = function (cur) {
        st.exam.answers.push({
          q_id: cur.question.q_id,
          atoms: cur.atoms.map(function (a) {
            return {
              atom_id: a.atom_id,
              original_num: a.original_num,
              is_correct: !!a.is_correct,
              picked: cur.selected.indexOf(a.original_num) >= 0,
              ground_on: !!cur.eliminated[a.atom_id]
            };
          }),
          answered_right: cur.answeredRight,
          /* 反応時間はこの瞬間にしか取れない（採点は最後にまとめて走る）。V1.79 */
          think_ms: (typeof M.thinkMsForCurrent === 'function') ? M.thinkMsForCurrent() : null,
          unit: cur.question.unit
        });
        M.state.session.answeredCount++;
        M.stepForward();
        return false;   /* 解説フェーズを描画しない */
      };
      M.hooks.onFinish = function (sess) {
        if (sess.mode !== 'exam') { return false; }
        gradeExam(st.exam.answers);
        return true;
      };

      /* --- 途中でやめたときの後片付け（V1.85・新設） -----------------------
         `endSession()` は **hooks を消さない**。消すのは各モードの役目で、
         概念ノックは `onAbort` で片付けている（`abortKnock`）。
         模試だけ `onAbort` を張っていなかったため、
         **［ホーム］で模試を抜けたあと afterGrade / onFinish が生き残り**、
         次に始めた通常学習の解答が、死んだ模試の answers へ吸い込まれていた。

         実測（画面から再現）：模試を1問解いて［ホーム］→ ランダムを開始 →
         1問解いても **解説が出ず（phase が answer のまま）**、
         **［次へ］も押せず**、**記録は1件も増えない**。JSエラーも出ない。
         「解いても解いても増えない」が延々続く。

         模試を始めてやめるのは、ごく普通の操作。ここは必ず片付ける。 */
      M.hooks.onAbort = function (mode) {
        if (mode !== 'exam') { return; }
        abortExam();
      };

      global.setTimeout(function () { tip('ground'); }, 1200);
      M.state.session = {
        mode: 'exam', sessionId: 'EX' + Date.now().toString(36),
        questions: q.questions, index: 0, answeredCount: 0,
        startedAt: Date.now(), hostQueue: null, hostIndex: 0
      };
      K.Interrupt.endSession();
      return M.go('quiz').then(function () { M.renderQuestion(); return st.exam; });
    });
  }

  /* 模試を最後まで行かずに畳んだときの後片付け。
     `M.endSession()` は【呼ばない】：ここは endSession から呼ばれる側なので、
     呼び返すと入れ子になる（概念ノックの `abortKnock` と同じ理由）。
     採点はしない。受験の途中で抜けた以上、点数は出しようがない。 */
  function abortExam() {
    M.hooks.afterGrade = null;
    M.hooks.onFinish = null;
    M.hooks.onAbort = null;
    if (st.exam) { st.exam.answers = []; st.exam.aborted = true; }
  }

  /* 採点：肢ごとに履歴連動 自動昇格／安全降格を適用する（第11章③）。
     ・正解 ＋ 根拠ON → [易]30日 or [マ]180日
     ・不正解 または 根拠OFF → 一律 [難]10分へ安全降格 */
  function gradeExam(answers) {
    var seq = Promise.resolve();
    var patterns = { A: 0, B: 0, C: 0 };

    answers.forEach(function (a) {
      a.atoms.forEach(function (at) {
        seq = seq.then(function () {
          var handledRight = (at.picked === at.is_correct);
          return K.applyExamResult(at.atom_id, {
            correct: handledRight,
            ground_on: at.ground_on
          }, { sessionId: st.exam.sessionId, thinkMs: a.think_ms }).then(function (r) {
            patterns[r.pattern] = (patterns[r.pattern] || 0) + 1;
          });
        });
      });
    });

    return seq.then(function () {
      /* 必修は正答率80%以上、一般・状況設定は250点満点換算で180点以上 */
      var hisshu = answers.filter(function (a) { return /必修/.test(a.unit || ''); });
      var ippan = answers.filter(function (a) { return !/必修/.test(a.unit || ''); });
      var hOk = hisshu.filter(function (a) { return a.answered_right; }).length;
      var iOk = ippan.filter(function (a) { return a.answered_right; }).length;

      var hPct = hisshu.length ? Math.round((hOk / hisshu.length) * 100) : null;
      var iScore = ippan.length ? Math.round((iOk / ippan.length) * 250) : null;
      var hPass = (hPct === null) || (hPct >= 80);
      var iPass = (iScore === null) || (iScore >= 180);
      var passed = hPass && iPass;

      var result = {
        exam_id: st.exam.id,
        style: st.exam.style || 'real',
        total: answers.length,
        correct: answers.filter(function (a) { return a.answered_right; }).length,
        hisshu: { total: hisshu.length, correct: hOk, pct: hPct, pass: hPass },
        ippan: { total: ippan.length, correct: iOk, score: iScore, pass: iPass },
        passed: passed,
        patterns: patterns,
        elapsed_ms: Date.now() - st.exam.startedAt
      };

      var record = (st.exam.id === 'mock_120')
        ? S.recordFullMockResult(passed)
        : Promise.resolve(null);

      return record.then(function () { return showExamResult(result); });
    });
  }

  function showExamResult(result) {
    M.hooks.afterGrade = null;
    M.hooks.onFinish = null;
    /* V1.85：onAbort も必ず外す。張ったままだと、次のモードを畳んだときに
       模試の後片付けが走る（いまは無害だが、無害さに寄りかからない）。 */
    M.hooks.onAbort = null;
    M.endSession();

    var r = result;
    var cells = [
      cell('総合', r.correct + ' / ' + r.total, r.passed),
      r.hisshu.total ? cell('必修', r.hisshu.pct + '%', r.hisshu.pass) : '',
      r.ippan.total ? cell('一般換算', r.ippan.score + '点', r.ippan.pass) : '',
      cell('所要', Math.round(r.elapsed_ms / 60000) + '分', true)
    ].join('');

    /* シェア画像はモーダルを閉じたあとでも作れるよう、結果を控える（V1.67） */
    st.exam.lastResult = r;

    setText('#exam-result-title', r.passed ? '合格ラインを超えました 🎉' : '採点結果');
    setHtml('#exam-score', cells +
      '<div class="score-cell" style="grid-column:1/-1">' +
      '<small>自動昇格：易 ' + (r.patterns.A || 0) + '肢 ／ マスター ' + (r.patterns.B || 0) + '肢' +
      '　安全降格：難 ' + (r.patterns.C || 0) + '肢</small></div>');

    return K.refreshAll({ recomputeWeakness: false })
      .then(function () { return M.refreshHome(); })
      .then(function () { return M.go('home', { replace: true }); })
      .then(function () {
        openModal('#modal-exam-result');
        if (r.passed) { M.fireConfetti(); }
        return r;
      });

    function cell(label, val, pass) {
      return '<div class="score-cell ' + (pass ? 'is-pass' : 'is-fail') + '">' +
             '<b>' + esc(val) + '</b><small>' + esc(label) + '</small></div>';
    }
  }

  /* ======================================================================
   * 7-B. 模試結果のシェア画像（V1.67）
   *
   * 【なぜ作るか】
   *   看護学生の横のつながりはSNS上にある。模試の点数は
   *   「載せたくなる瞬間」が明確に存在する数少ない出力で、
   *   サーバー無しで作れる唯一の拡散経路（戦略レビュー §1-3）。
   *
   * 【設計の線引き】
   *   ・端末内の Canvas だけで生成する。通信ゼロ。個人情報ゼロ
   *   ・合格可能性「%」は載せない（母集団データが無い数字は捏造）。
   *     載せるのは実測の点数と、合格ラインまでの距離だけ
   *   ・アプリのテーマ（ライト/セピア）には追従させず、固定の1デザイン。
   *     外へ出る画像は、誰の端末から出ても同じ顔であるべき（ブランド）
   * ====================================================================== */

  var SHARE_W = 1080, SHARE_H = 1080;

  function examLabel(examId) {
    var hit = (S.MOCK_DEFS || []).filter(function (d) { return d.id === examId; })[0];
    return hit ? hit.label : '模擬試験';
  }

  /* 角丸矩形。ctx.roundRect は iOS 15 以前に無いので自前で描く */
  function rr(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  /* 結果オブジェクト → 1080×1080 の Canvas。
     描画だけを担い、Blob化・シェアは呼び出し側の仕事に分ける
     （テストが「絵が正しいか」だけを単独で確かめられるように）。 */
  function buildShareCard(r) {
    var cv = global.document.createElement('canvas');
    cv.width = SHARE_W; cv.height = SHARE_H;
    var ctx = cv.getContext('2d');
    var FONT = '-apple-system, BlinkMacSystemFont, "Hiragino Sans", "Noto Sans JP", sans-serif';

    /* --- 地：紺の縦グラデーション。スクショ列の中で沈まない濃さ --- */
    var bg = ctx.createLinearGradient(0, 0, 0, SHARE_H);
    bg.addColorStop(0, '#141C2B');
    bg.addColorStop(1, '#0D1420');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, SHARE_W, SHARE_H);

    /* うっすら模様（単色べた塗りはスクショで安っぽく見える） */
    ctx.fillStyle = 'rgba(255,255,255,0.025)';
    for (var gy = 0; gy < 5; gy++) {
      ctx.beginPath();
      ctx.arc(SHARE_W - 60, -40 + gy * 30, 340 - gy * 60, 0, Math.PI * 2);
      ctx.fill();
    }

    /* --- 上段：アプリ名・模試名・日付 --- */
    ctx.fillStyle = '#7FD8E2';
    ctx.font = '700 40px ' + FONT;
    ctx.textBaseline = 'alphabetic';
    ctx.fillText('オモイダス', 72, 106);
    ctx.fillStyle = 'rgba(255,255,255,0.55)';
    ctx.font = '500 30px ' + FONT;
    ctx.fillText('看護師国家試験 対策', 72, 152);

    var d = new Date();
    var dateStr = d.getFullYear() + '.' +
      String(d.getMonth() + 1).padStart(2, '0') + '.' +
      String(d.getDate()).padStart(2, '0');
    ctx.textAlign = 'right';
    ctx.fillStyle = 'rgba(255,255,255,0.55)';
    ctx.font = '600 32px ' + FONT;
    ctx.fillText(dateStr, SHARE_W - 72, 106);
    ctx.textAlign = 'left';

    ctx.fillStyle = '#FFFFFF';
    ctx.font = '800 62px ' + FONT;
    var title = examLabel(r.exam_id) +
      (r.style === 'final' ? '（直前モード）' : '');
    ctx.fillText(title, 72, 268);

    /* --- 中央：総合スコア --- */
    ctx.textAlign = 'center';
    ctx.fillStyle = '#FFFFFF';
    ctx.font = '800 200px ' + FONT;
    var main = r.correct + ' / ' + r.total;
    ctx.fillText(main, SHARE_W / 2, 560);
    ctx.fillStyle = 'rgba(255,255,255,0.6)';
    ctx.font = '600 40px ' + FONT;
    ctx.fillText('正答数', SHARE_W / 2, 630);

    /* 合格帯（超えたときだけ出す。落ちた画像を煽らない） */
    if (r.passed) {
      ctx.fillStyle = '#1FA97A';
      rr(ctx, SHARE_W / 2 - 210, 668, 420, 74, 37);
      ctx.fill();
      ctx.fillStyle = '#FFFFFF';
      ctx.font = '800 42px ' + FONT;
      ctx.fillText('合格ライン突破', SHARE_W / 2, 719);
    }
    ctx.textAlign = 'left';

    /* --- 下段：必修・一般の2枚パネル。距離（±）まで書く --- */
    var panels = [];
    if (r.hisshu && r.hisshu.total) {
      var hd = r.hisshu.pct - 80;
      panels.push({ label: '必修', val: r.hisshu.pct + '%',
                    sub: 'ライン80%まで ' + (hd >= 0 ? '+' : '') + hd,
                    ok: r.hisshu.pass });
    }
    if (r.ippan && r.ippan.total) {
      var idlt = r.ippan.score - 180;
      panels.push({ label: '一般・状況（250点換算）', val: r.ippan.score + '点',
                    sub: 'ボーダー目安180点まで ' + (idlt >= 0 ? '+' : '') + idlt,
                    ok: r.ippan.pass });
    }
    var pw = panels.length === 2 ? 444 : 936, px0 = 72, py = 790, ph = 168;
    panels.forEach(function (pn, i) {
      var x = px0 + i * (pw + 48);
      ctx.fillStyle = 'rgba(255,255,255,0.07)';
      rr(ctx, x, py, pw, ph, 22);
      ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.6)';
      ctx.font = '600 28px ' + FONT;
      ctx.fillText(pn.label, x + 32, py + 52);
      ctx.fillStyle = pn.ok ? '#4ADCA9' : '#FFB3BD';
      ctx.font = '800 62px ' + FONT;
      ctx.fillText(pn.val, x + 32, py + 122);
      ctx.fillStyle = 'rgba(255,255,255,0.5)';
      ctx.font = '500 26px ' + FONT;
      ctx.fillText(pn.sub, x + 32, py + 156);
    });

    /* --- 最下段：出どころ。これが無いと画像を見た人が来られない --- */
    ctx.fillStyle = 'rgba(255,255,255,0.45)';
    ctx.font = '600 30px ' + FONT;
    ctx.fillText('omoidasu-kokushi.github.io', 72, SHARE_H - 56);

    return cv;
  }

  function canvasToBlob(cv) {
    return new Promise(function (resolve, reject) {
      if (cv.toBlob) {
        cv.toBlob(function (b) {
          if (b) { resolve(b); } else { reject(new Error('画像を作れませんでした')); }
        }, 'image/png');
        return;
      }
      /* toBlob が無い古い環境。dataURL 経由で作る */
      try {
        var parts = cv.toDataURL('image/png').split(',');
        var bin = global.atob(parts[1]);
        var arr = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i++) { arr[i] = bin.charCodeAt(i); }
        resolve(new Blob([arr], { type: 'image/png' }));
      } catch (e) { reject(e); }
    });
  }

  /* シェア本体。順序は
       ① OSの共有シート（対応していれば。X/Instagram へ直接渡る）
       ② だめならPNGをダウンロード
     の2段。②があるので、どの環境でも必ず何かが手に残る。 */
  function shareExamResult() {
    var r = st.exam.lastResult;
    if (!r) { toast('シェアできる結果がありません'); return Promise.resolve(null); }
    var cv = buildShareCard(r);
    return canvasToBlob(cv).then(function (blob) {
      var file = null;
      try {
        file = new File([blob], 'omoidasu_result.png', { type: 'image/png' });
      } catch (e) { /* File が作れない環境はダウンロードへ */ }

      if (file && global.navigator.canShare &&
          global.navigator.canShare({ files: [file] }) && global.navigator.share) {
        return global.navigator.share({
          files: [file],
          title: 'オモイダス 模試結果',
          text: examLabel(r.exam_id) + ' ' + r.correct + '/' + r.total + ' 正解'
        }).catch(function (e) {
          /* 利用者が共有シートを閉じただけなら何もしない。
             失敗扱いにしてダウンロードが落ちてくると驚かせる */
          if (e && e.name === 'AbortError') { return null; }
          return downloadBlobAsFile(blob);
        });
      }
      return downloadBlobAsFile(blob);
    }).catch(function (e) {
      toast('画像を作れませんでした：' + (e && e.message ? e.message : e), 4200);
      return null;
    });
  }

  function downloadBlobAsFile(blob) {
    var url = global.URL.createObjectURL(blob);
    var a = global.document.createElement('a');
    a.href = url;
    a.download = 'omoidasu_result.png';
    global.document.body.appendChild(a);
    a.click();
    a.remove();
    global.setTimeout(function () { global.URL.revokeObjectURL(url); }, 4000);
    toast('画像を保存しました。SNSに貼れます', 3600);
    return null;
  }

  /* ======================================================================
   * 8. 設定・データ（第14章②③）
   * ====================================================================== */

  function openSettings() {
    return S.loadMeta().then(function (meta) {
      M.state.meta = meta;
      fillDaylineOptions(meta.day_boundary_hour);
      var p = $('#set-pomodoro');      if (p) { p.checked = meta.pomodoro_enabled !== false; }
      var a = $('#set-alarm');         if (a) { a.value = meta.pomodoro_alarm || 'chime'; }
      refreshAlarmFileNote().catch(noop);
      var l = $('#set-longbreak');     if (l) { l.value = String(meta.pomodoro_longbreak_min || 15); }
      var b = $('#set-badge');         if (b) { b.checked = meta.badge_enabled !== false; }
      var vp = $('#set-verdict-popup'); if (vp) { vp.checked = meta.verdict_popup_enabled !== false; }
      var n = $('#set-notify');        if (n) { n.checked = !!meta.notify_enabled; }
      $$('#screen-settings .seg-btn[data-theme-set]').forEach(function (x) {
        cls(x, 'is-active', x.getAttribute('data-theme-set') === (meta.theme || 'light'));
      });
      /* 自分で入れた図の表示位置（V1.29）。未設定なら既定の after-figure。 */
      refreshExamNote().catch(noop);
      refreshHissuNote().catch(noop);     /* V1.89 必修の出題比率 */
      refreshExplainMode();
      refreshDrive().catch(noop);
      refreshLicense();
      refreshStorage().catch(noop);
      refreshBackupSize().catch(noop);
      /* 押した瞬間に窓を開けるよう、ここで先に用意しておく。 */
      D.prepare().catch(noop);
      var pos = M.userImagePos();
      $$('#screen-settings input[name="userimgpos"]').forEach(function (r) {
        r.checked = (r.value === pos);
      });
      setText('#notify-note', supportsNotification()
        ? '通知が使えない端末では、アラーム音だけが鳴ります。'
        : 'この端末は通知に対応していないため、アラーム音のみでお知らせします。');
      hide('#import-report');
      return M.go('settings').then(function (r) {
        global.setTimeout(function () { tip('settings'); }, 500);
        return r;
      });
    });
  }

  /* 12列TSV / JSON の一括インポート。
     正解判定の不一致でスキップされた行は、行番号つきで必ず提示する。 */
  function runImport(text) {
    var box = $('#import-report');
    if (!text || !String(text).trim()) { toast('取り込むデータを貼り付けてください'); return Promise.resolve(null); }

    setHtml('#import-report', '<b>取り込み中…</b>');
    if (box) { box.hidden = false; box.classList.remove('is-error'); }

    /* --- 始める前に空き容量を見る（V1.60／V1.73で数え方を修正） ---
       途中で満杯になって落ちるより、始める前に断るほうがよい。
       必要量は「問題数 × 実測12KB」で見積もる。
       V1.72 まではここで**改行の数**を問題数の代わりにしていたが、
       整形済みJSONでは1問が数十行になるため見積もりが数十倍に膨らみ、
       1,173問の取り込みが「保存領域が足りません」で丸ごと拒否された。
       数え方は形式を知っている storage.js に持たせた（estimateImportRows）。 */
    var roughRows = S.estimateImportRows ? S.estimateImportRows(text)
                  : ((String(text).match(/\n/g) || []).length + 1);
    return S.checkRoomFor(roughRows).then(function (room) {
      if (room.ok || room.unknown) { return null; }
      var mb = function (n) { return Math.round(n / 1048576 * 10) / 10; };
      setHtml('#import-report',
        '<b>保存領域が足りません</b><br>' +
        'この取り込みには約 ' + mb(room.need) + 'MB 必要ですが、' +
        '空きは ' + mb(room.free) + 'MB です。<br>' +
        '<small>設定から「バックアップを書き出す」を実行してファイルを保存したうえで、' +
        '端末の写真やアプリを整理するか、自分で入れた図を減らしてから、もう一度お試しください。</small>');
      if (box) { box.classList.add('is-error'); }
      throw new Error('__ROOM__');
    }).then(function () {
    /* メモを持つ問題があるなら、取り込みの前に必ず自動退避する。
       引き継ぎ漏れが起きた場合でも、書いた内容を失わせないための保険。 */
      return S.countMemos();
    }).then(function (n) {
      if (!n) { return null; }
      return S.downloadBackup('NurseExamApp_AutoBackup_BeforeImport').then(function (bk) {
        toast('メモが ' + n + ' 件あるため、取り込み前にバックアップを保存しました', 4200);
        return bk;
      }).catch(function () { return null; });
    }).then(function () {
      return S.importText(text);
    }).then(function (rep) {
      var lines = [];
      /* バックアップJSONを貼ると、取り込みではなく【復元（足し合わせ）】が走る。
         同じ見出しを出すと、利用者は問題を足したつもりでいる（V1.56）。 */
      if (rep.source === 'backup') {
        lines.push('<b>バックアップとして読み取り、いまの中身に足し合わせました</b>');
        lines.push('問題 ' + rep.questions + ' 問 ／ 選択肢 ' + rep.atoms + ' 件 ／ 学習の記録 ' +
                   rep.progress_log + ' 件');
        lines.push('<small>入れ替え（いまの中身を消してから戻す）をしたい場合は、' +
                   '設定の［バックアップから復元］を使ってください。</small>');
        setHtml('#import-report', lines.join('<br>'));
        var box2 = $('#import-report');
        if (box2) { box2.hidden = false; box2.classList.remove('is-error'); }
        return K.refreshAll({ recomputeWeakness: true })
          .then(function () { return M.refreshHome(); })
          /* 件数が変わったので、書き出しの見積り表示も直す（V1.82） */
          .then(function () { return refreshBackupSize().catch(noop); })
          .then(function () { return rep; });
      }
      lines.push('<b>' + (rep.ok ? '取り込みが完了しました' : '取り込めた行がありませんでした') + '</b>');
      lines.push('読み込み ' + rep.total_lines + ' 行 ／ 新規 ' + rep.imported + ' 問 ／ 更新 ' +
                 rep.updated + ' 問 ／ 選択肢 ' + rep.atoms + ' 件');

      /* プールの内訳（V1.56）。模試用が混ざっていたら必ず出す。
         黙っていると、ランダムに予想問題が出てきて初めて気づくことになる。 */
      if (rep.pool_mock) {
        lines.push('<b>本体 ' + (rep.pool_main || 0) + ' 問 ／ 模試用 ' + rep.pool_mock + ' 問</b>');
        lines.push('<small>模試用の問題は、ランダム・単元学習・復習には出ません。' +
                   '力試しモードで初めて出題され、そのあと復習に加わります。</small>');
      }
      /* 分類ガード（V1.71）。中項目名が1字違うだけでツリーが分裂する。
         模試用と同じく「気づけるのは手遅れになってから」の類なので必ず出す。 */
      if (rep.tax_bad) {
        lines.push('<b>⚠ 出題基準に無い分類 ' + rep.tax_bad + ' 問</b>');
        lines.push('<small>単元＞大項目＞中項目の表記が出題基準と一致しません。' +
                   '表記ゆれのまま取り込むと単元ツリーが分裂します。例：' +
                   esc((rep.tax_examples || []).join(' ／ ')) + '</small>');
      }
      /* 概念タグのガード（V1.88）。分類と同じ理由で必ず出す。
         74マスタから外れたタグは、理解率にもノックにもTOP3にも出てこない。
         **どこにもエラーが出ないまま、その機能だけが静かに死ぬ。** */
      if (rep.tag_bad) {
        lines.push('<b>⚠ 74テーマに無いタグ ' + rep.tag_bad + ' 件（' +
                   (rep.tag_bad_rows || 0) + ' 問）</b>');
        lines.push('<small>このタグは74概念の理解率にも、概念別弱点ノックにも、' +
                   '最優先克服概念にも出てきません。例：' +
                   esc((rep.tag_examples || []).join(' ／ ')) + '</small>');
      }
      if (rep.skipped) {
        lines.push('<b>スキップ ' + rep.skipped + ' 行</b>（うち正解判定の不一致 ' + rep.mismatch + ' 行）');
      }
      if (rep.unverified) {
        lines.push('自動検算できなかった行：' + rep.unverified + ' 行（解説に「①〜⑤ 正解」の記述がありません）');
      }
      if (rep.errors.length) {
        lines.push('<ul>' + rep.errors.slice(0, 20).map(function (e) {
          return '<li>' + esc(e.message) + '</li>';
        }).join('') + '</ul>');
        if (rep.errors.length > 20) { lines.push('<small>ほか ' + (rep.errors.length - 20) + ' 件</small>'); }
      }
      if (rep.warnings.length) {
        var uniq = {}, ws = [];
        rep.warnings.forEach(function (w) {
          var key = w.message.replace(/^\d+行目：/, '');
          if (!uniq[key]) { uniq[key] = 0; ws.push(key); }
          uniq[key]++;
        });
        lines.push('<small>注意：' + ws.map(function (k) { return esc(k) + '（' + uniq[k] + '行）'; }).join(' ／ ') + '</small>');
      }

      setHtml('#import-report', lines.join('<br>'));
      if (box) { box.classList[rep.skipped ? 'add' : 'remove']('is-error'); }

      var area = $('#import-area');
      if (area && rep.imported + rep.updated > 0) {
        area.value = '';
        /* 問題を取り込んだ＝この端末に価値が乗った。ここでも要求する（V1.60）。
           すでに許可されていれば storage.js 側が何もしない。 */
        S.requestPersist().then(function () { return refreshStorage(); }).catch(noop);
      }

      return K.refreshAll({ recomputeWeakness: true });
    }).then(function () {
      return M.refreshHome();
    }).then(function () {
      /* 件数が変わったので、書き出しの見積り表示も直す（V1.82） */
      return refreshBackupSize().catch(noop);
    }).catch(function (e) {
      /* 空き不足はすでに画面へ出しているので、ここで上書きしない（V1.60）。 */
      if (e && e.message === '__ROOM__') { return null; }
      /* 文言は storage.js の describeError が決める（V1.60）。
         「取り込みに失敗しましたquota」では何も伝わらない。
         必要なのは【次に何をすればよいか】。 */
      var text = (S && S.describeError) ? S.describeError(e)
               : (e && e.message ? e.message : String(e));
      setHtml('#import-report', '<b>取り込みに失敗しました</b><br>' + esc(text) +
        '<br><small>途中まで取り込めた分は残っています。原因を解消してから、' +
        '同じデータをもう一度貼り付けてください（重複しては入りません）。</small>');
      if (box) { box.classList.add('is-error'); }
      return null;
    });
  }

  function runBackup() {
    return S.downloadBackup().then(function (r) {
      toast(r.downloaded ? 'バックアップを書き出しました：' + r.filename : 'この環境ではファイルを保存できません', 4000);
      return r;
    });
  }

  function runRestore() {
    var input = doc.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.addEventListener('change', function () {
      var f = input.files && input.files[0];
      if (!f) { return; }
      var fr = new FileReader();
      fr.onload = function () {
        var payload = null;
        try { payload = JSON.parse(String(fr.result)); }
        catch (e) { toast('JSONとして読み取れませんでした', 4000); return; }
        /* --- 復元は「入れ替え」なので必ず確認する（V1.56） ---
           このボタンは今の中身を**全部消してから**書き戻す。
           取り込み欄に同じファイルを貼ると 'merge'（足し合わせ）になり、
           **同じファイルなのに入口で結果が正反対**になる。
           入れ替えのほうが取り返しがつかないので、こちらだけ確認を挟む。

           何問入っているかを先に出す。ファイル名では中身が分からず、
           古いバックアップを選んでも気づけない。 */
        var n = (payload.stores && payload.stores.questions) ? payload.stores.questions.length : 0;
        var na = (payload.stores && payload.stores.atoms) ? payload.stores.atoms.length : 0;
        var when = payload.exported_at ? new Date(payload.exported_at).toLocaleString('ja-JP') : '不明';
        M.confirmAction({
          title: 'いまの中身を入れ替えますか',
          body: 'このファイルには 問題 ' + n + '問 ／ 選択肢 ' + na + '件 が入っています'
              + '（書き出し：' + when + '）。'
              + 'いまの学習記録・メモ・図は、すべてこのファイルの中身に置き換わります。'
              + '足し合わせではありません。元には戻せません。',
          ok: '入れ替える'
        }).then(function (yes) {
          if (!yes) { return null; }
          return S.restoreBackup(payload, 'replace').then(function (rep) {
            toast('復元しました：問題 ' + rep.questions + ' 問 ／ 選択肢 ' + rep.atoms + ' 件', 4000);
            return K.refreshAll({ recomputeWeakness: true });
          }).then(function () { return M.refreshHome(); })
            .then(function () { return refreshBackupSize().catch(noop); });
        }).catch(function (e) { toast('復元に失敗しました：' + e.message, 5000); });
      };
      fr.readAsText(f);
    });
    input.click();
    return Promise.resolve();
  }

  /* --- 同梱の見本問題（V1.81） ---
     `init()` は「問題数0 かつ seed_imported が未設定」で見本問題を入れる。
     ところが `resetAll()` は meta ストアごと消すので **seed_imported も一緒に消える**。
     その結果、全初期化したあとページを読み込み直すと**見本問題が戻ってくる**。

     旧来の回避策は「初期化したら、再読込せずにそのまま取り込む」だった。
     手順を1つ外すと戻ってくる作りで、しかも戻ってきたことに気づきにくい
     （問題数が453に見えるだけで、エラーは何も出ない）。

     消したのは利用者の意思なので、**消えたままにする**。
     初期化のあとに印を立て直せば、読み込み直しても入らない。
     いったん消したあとで見本が要るようになったら、
     設定の［同梱の見本問題を入れ直す］から明示的に入れる。 */
  function markSeedConsumed() {
    return S.setMeta('seed_imported', true).catch(noop);
  }

  function restoreSeedQuestions() {
    if (!global.SEED_QUESTIONS_TSV) {
      toast('この配布物には見本問題が入っていません', 4000);
      return Promise.resolve(null);
    }
    return M.confirmAction({
      title: '同梱の見本問題を入れ直しますか？',
      body: '見本問題を取り込みます。いまの問題データや学習の記録は消えません。' +
            '<br><small>同じ問題がすでにある場合は上書きされます（学習の記録は引き継がれます）。</small>',
      ok: '入れ直す'
    }).then(function (yes) {
      if (!yes) { return null; }
      return S.importText(global.SEED_QUESTIONS_TSV).then(function (rep) {
        return markSeedConsumed().then(function () {
          toast('見本問題を入れ直しました：新規 ' + rep.imported + ' 問 ／ 更新 ' + rep.updated + ' 問', 4600);
          return rep;
        });
      }).then(function (rep) {
        return K.refreshAll({ recomputeWeakness: true }).then(function () { return rep; });
      }).then(function (rep) {
        return M.refreshHome().then(function () { return rep; });
      }).catch(function (e) {
        toast('入れ直せませんでした：' + (e && e.message ? e.message : e), 5000);
        return null;
      });
    });
  }

  /* --- 書き出しの大きさを、押す前に見せる（V1.82・新設） ------------------
     上限規模の実測（§6-9）で、バックアップが75.6MBになることが分かった。
     間違いノートの印刷（§4-25）と同じで、**押してから気づくのでは遅い**。
     見積りは storage.js が件数と抜き取りから出す（全件は組み立てない）。 */
  function fmtMB(bytes) {
    var mb = bytes / 1048576;
    if (mb < 1) { return Math.max(1, Math.round(bytes / 1024)) + 'KB'; }
    return (Math.round(mb * 10) / 10) + 'MB';
  }

  function backupSummary(est) {
    var c = est.counts || {};
    var parts = [];
    if (c.questions)    { parts.push('問題 ' + c.questions + '問'); }
    if (c.atoms)        { parts.push('選択肢 ' + c.atoms + '肢'); }
    if (c.progress_log) { parts.push('学習の記録 ' + c.progress_log + '件'); }
    if (est.user_files_bytes) {
      parts.push('自分で入れた図と音 ' + fmtMB(est.user_files_bytes) +
                 (est.user_files_included ? '' : '（30MB超のため書き出しに含みません）'));
    }
    return parts.join('／');
  }

  function refreshBackupSize() {
    var el = $('#backup-size');
    if (!el || !S.estimateBackupBytes) { return Promise.resolve(null); }
    return S.estimateBackupBytes().then(function (est) {
      var body = backupSummary(est);
      if (!body) { el.hidden = true; return est; }
      var txt = 'いまの中身：' + body + ' → 書き出しは約 ' + fmtMB(est.bytes) + ' になります。';
      if (est.big) {
        txt += ' ⚠ 端末の空きと、保存先を先に確かめてください。' +
               '大きいファイルは、貼り付けでの復元ができません（ファイル選択で戻します）。';
      }
      setText('#backup-size', txt);
      cls(el, 'is-warn', !!est.big);
      el.hidden = false;
      return est;
    }).catch(function () { if (el) { el.hidden = true; } return null; });
  }

  /* --- 全初期化の前に、いま何が守られているかを出す（V1.82・新設） --------
     同期が生きているなら、学習の記録は gzip 1.3MB で向こうにも残る（§6-9）。
     生きていないなら、退避は手元のJSONファイル1本だけ。
     **どちらなのかを、押す前に必ず言う。** */
  function driveGuardState() {
    return S.loadMeta().then(function (m) {
      var id = m.drive_client_id || (D.hasBuiltInClientId && D.hasBuiltInClientId() ? 'builtin' : '');
      return { configured: !!id, signedIn: !!(D.tokenValid && D.tokenValid()) };
    }).catch(function () { return { configured: false, signedIn: false }; });
  }

  function openResetModal() {
    setText('#reset-detail', '中身を数えています…');
    openModal('#modal-reset');
    return Promise.all([
      S.estimateBackupBytes ? S.estimateBackupBytes() : Promise.resolve(null),
      driveGuardState()
    ]).then(function (r) {
      var est = r[0], g = r[1];
      var lines = [];
      if (est) {
        lines.push('消えるもの：' + (backupSummary(est) || '（まだ何も入っていません）'));
        lines.push('自動で書き出すファイル：約 ' + fmtMB(est.bytes));
      }
      if (g.signedIn) {
        lines.push('消す前に、学習の記録をドライブへ送ります。送れなかったら中止します。');
      } else if (g.configured) {
        lines.push('⚠ ドライブにログインしていません。退避は、いま書き出すファイル1本だけです。' +
                   'やめて先に［今すぐ同期］を押しておくと、記録は向こうにも残ります。');
      } else {
        lines.push('⚠ 同期を使っていません。退避は、いま書き出すファイル1本だけです。');
      }
      setText('#reset-detail', lines.join(' ／ '));
      return { est: est, guard: g };
    }).catch(function () {
      setText('#reset-detail', '');
      return null;
    });
  }

  /* ログイン中なら、消す前に1回だけ送る。送れなければ**消さない**。
     ここで黙って続けると、「失わないための仕組み」が
     失敗したことにすら気づけないまま消えることになる。 */
  function syncBeforeReset() {
    if (!(D.tokenValid && D.tokenValid())) { return Promise.resolve({ skipped: true }); }
    toast('消す前に、学習の記録をドライブへ送っています…', 4000);
    return D.autoSync().then(function (rep) {
      if (rep && rep.ok === false) { return { ok: false, error: rep.error || null }; }
      return { ok: true, rep: rep };
    }).catch(function (e) {
      return { ok: false, error: (e && e.message) || String(e) };
    });
  }

  /* 全初期化。storage.js 側が、消す直前に自動でJSONを書き出す。 */
  function runResetAll() {
    return syncBeforeReset().then(function (sy) {
      if (sy && sy.ok === false) {
        return M.confirmAction({
          title: 'ドライブへ送れませんでした',
          body: 'いまの中身はまだ消していません。' +
                'このまま消すと、退避はこれから書き出すファイル1本だけになります。' +
                (sy.error ? '（' + sy.error + '）' : ''),
          ok: 'それでも消す'
        });
      }
      return true;
    }).then(function (go) {
      if (!go) { toast('やめました。中身は消えていません', 4000); return null; }
      return doResetAll();
    });
  }

  function doResetAll() {
    return S.resetAll().then(function (r) {
      toast('バックアップ（' + r.backup_filename + '）を保存してから初期化しました', 5000);
      /* 消したものが読み込み直しで戻ってこないようにする（V1.81） */
      return markSeedConsumed().then(function () { return r; });
    }).then(function () {
      return K.refreshAll({ recomputeWeakness: false });
    }).then(function () {
      return M.refreshHome();
    }).then(function () {
      return M.go('home', { replace: true });
    });
  }

  /* 番号をメモさせる prompt() をやめる。
     「進捗を消すのは相当なことだからメモさせるくらいでいい」は成立するが、
     それは摩擦の置き場所が違う。メモの手間が防ぐのは「間違った番号を打つ」
     事故であって、「消すつもりが無かったのに消した」事故ではない。
     一覧から名前で選ばせ、消す直前にもう一度、対象名と件数を出して止める。
     学習記録が無い中項目は、そもそも押せないようにしておく。 */
  function resetByMedium() {
    return Promise.all([S.getAllQuestions(), S.getAllAtoms()]).then(function (r) {
      var qs = r[0], atoms = r[1];
      if (!qs.length) { toast('データがありません'); return null; }

      /* V1.86：中項目は「単元＋大項目＋中項目」でまとめる。
         名前だけでまとめると、成人看護学の「C. 検査を受ける患者の看護」
         12件が1行に潰れ、パンくずは最初に当たった1件しか出ないのに、
         押すと12件ぶん消える。表示と実害が食い違う。 */
      var order = [], byMedium = {};
      qs.forEach(function (q) {
        var k = S.scopeKey(q.unit, q.major, q.medium);
        if (!byMedium[k]) {
          byMedium[k] = { key: k, label: q.medium, unit: q.unit, major: q.major,
                          atoms: 0, learned: 0 };
          order.push(k);
        }
      });
      atoms.forEach(function (a) {
        var m = byMedium[S.scopeKey(a.unit, a.major, a.medium)];
        if (!m) { return; }
        m.atoms++;
        if (a.answer_count > 0) { m.learned++; }
      });

      setHtml('#reset-medium-list', order.map(function (k) {
        var m = byMedium[k];
        var dead = !m.learned;
        return '<button type="button" class="medium-row' + (dead ? ' is-empty' : '') +
               '" data-medium="' + esc(k) + '"' + (dead ? ' disabled' : '') + '>' +
               '<span class="medium-main">' +
               '<span class="medium-name">' + esc(m.label) + '</span>' +
               '<span class="medium-path">' + esc(m.unit) + ' ＞ ' + esc(m.major) + '</span></span>' +
               '<span class="medium-count">' +
               (dead ? '記録なし' : '学習済 ' + m.learned + ' / ' + m.atoms + ' 肢') +
               '</span></button>';
      }).join(''));
      openModal('#modal-reset-medium');
      return byMedium;
    });
  }

  /* medium には「単元＋大項目＋中項目」の複合キーが来る（V1.86）。
     古い形（中項目名だけ）が来ても storage 側が受け取れるようにしてあるが、
     その場合は同名の中項目を全部巻き込むので、ここでは必ず複合キーを渡す。 */
  function mediumLabel(key) { return S.splitScope(key).leaf || String(key || ''); }
  function mediumPath(key) {
    var sc = S.splitScope(key);
    return sc.unit ? (sc.unit + ' ＞ ' + sc.major + ' ＞ ' + sc.leaf) : sc.leaf;
  }

  function confirmResetMedium(medium) {
    if (!medium) { return Promise.resolve(null); }
    return S.getAtomsByScope('medium', medium).then(function (atoms) {
      var learned = atoms.filter(function (a) { return a.answer_count > 0; }).length;
      st.resetMedium = medium;
      setHtml('#reset-medium-confirm-body',
        '<b>' + esc(mediumPath(medium)) + '</b> の学習記録 <b>' + learned + '</b> 件を消します。<br>' +
        '問題文・選択肢・解説はそのまま残り、評価・復習期日・弱点ptだけが未学習の状態に戻ります。' +
        '<br>この操作は取り消せません。');
      openModal('#modal-reset-medium-confirm');
      return learned;
    });
  }

  function runResetMedium() {
    var medium = st.resetMedium;
    if (!medium) { return Promise.resolve(null); }
    closeModals();
    return S.resetProgressByScope('medium', medium).then(function (r) {
      toast('「' + mediumLabel(medium) + '」の ' + r.atoms + ' 肢を未学習に戻しました', 4000);
      st.resetMedium = null;
      return K.refreshAll({ recomputeWeakness: true });
    }).then(function () { return M.refreshHome(); });
  }

  /* 日界は0〜23時から自由に選べる。夜勤明けや深夜型の生活に合わせるため。
     分単位にしないのは、storage.js の dayStart() が setHours(h,0,0,0) で
     時だけを扱っており、刻むと日界計算・日次カウンタ・バックアップ互換の
     3点を同時に触ることになるため。必要になったら day_boundary_min を別途足す。 */
  function fillDaylineOptions(current) {
    var sel = $('#set-dayline');
    if (!sel) { return; }
    var cur = isNum(current) ? current : 4;
    if (cur < 0 || cur > 23) { cur = 4; }
    var html = '', h, note;
    for (h = 0; h < 24; h++) {
      note = (h === 4) ? '（既定）' : (h === 0 ? '（日付が変わった瞬間）' : '');
      html += '<option value="' + h + '"' + (h === cur ? ' selected' : '') + '>' +
              (h < 10 ? '0' : '') + h + ':00' + note + '</option>';
    }
    sel.innerHTML = html;
  }

  function setDayBoundary(hour) {
    var h = parseInt(hour, 10);
    /* 0時を選べるようにしたので `|| 4` は使えない。0 は falsy なので、
       深夜0時の指定が黙って4時に化けていた（V1.06までの不具合）。 */
    if (!isFinite(h) || h < 0 || h > 23) { h = 4; }
    return S.setMeta('day_boundary_hour', h).then(function () {
      return S.loadMeta();
    }).then(function (meta) {
      M.state.meta = meta;
      toast('1日の切り替わりを ' + meta.day_boundary_hour + ':00 に設定しました', 3000);
    });
  }

  /* ======================================================================
   * 8-2. 設定の [？] ヘルプ
   * 「ポモドーロ」「日界」は名前だけでは何が起きるか分からない。
   * かといって常時展開すると他の項目まで読まれなくなる。押した時だけ出す。
   * ====================================================================== */

  var HELP = {
    pomodoro: {
      title: 'ポモドーロタイマーとは',
      body:
        '<p><b>25分だけ集中して、5分休む</b>。これを繰り返す時間の区切り方です。' +
        '「あと25分だけ」と区切ると始めやすく、疲れる前に休むので長く続きます。</p>' +
        '<ul>' +
        '<li>学習を始めると、画面の右上で 25:00 から静かに減っていきます。</li>' +
        '<li>25分を過ぎると、<b>解説画面に切り替わった瞬間に</b>お知らせします。' +
        '解答の途中で邪魔しないよう、わざとそのタイミングにしています。</li>' +
        '<li>そこで「5分休憩」「あと10分延長」「OFFにする」から選べます。乗っているときは延長で構いません。</li>' +
        '<li>25分×4回を終えると、長めの休憩（15〜30分）を提案します。</li>' +
        '</ul>' +
        '<p>アラーム音は3種類から選べます。通知をONにしていない端末でも、音だけは鳴ります。</p>'
    },
    dayline: {
      title: '「1日の切り替わり」とは',
      body:
        '<p>このアプリは、<b>カレンダーの0時ではなく、あなたが決めた時刻で1日を区切ります</b>。</p>' +
        '<ul>' +
        '<li>夜1時に解いて「1日後」になった問題は、翌日の0時ではなく<b>この時刻を過ぎてから</b>出てきます。' +
        '深夜に解いた直後に「もう明日ぶん」が出てこないようにするためです。</li>' +
        '<li>「今日◯問」の集計も、この時刻で切り替わります。</li>' +
        '</ul>' +
        '<p><b>選び方の目安</b>：寝る時刻より後、起きる時刻より前。' +
        '深夜3時まで起きているなら 4:00 〜 6:00、早朝5時から解くなら 3:00 が合います。</p>' +
        '<p>昼の時刻（例 12:00）にすると、午前中の学習が前日ぶんとして数えられます。意図しない限り避けてください。</p>'
    },
    'import': {
      title: '自作問題データの取り込み',
      body:
        '<p>スプレッドシートで作った問題を、<b>12列のまま貼り付けるだけ</b>で取り込めます。' +
        '手順は取り込み欄のすぐ上、「はじめての方へ」を開いてください。</p>' +
        '<ul>' +
        '<li><b>10列目の正解は 0 から数えます。</b>1番目が正解なら 0 です。</li>' +
        '<li><b>8列目は問題文</b>、解説は比較表も図解も<b>すべて11列目</b>です。</li>' +
        '<li>同じ問題をもう一度取り込んでも、★・評価・書き換えた解説は消えません。増えるのではなく上書きされます。</li>' +
        '<li>正解の指定と解説の記述が食い違う行は、取り込まずに行番号を出します。' +
        'この検算があるので、1行ズレたまま何百問も覚えてしまう事故が起きません。</li>' +
        '</ul>' +
        '<p>書き出したバックアップJSONも、同じ欄に貼って復元できます。</p>'
    },
    'drive': {
      title: 'ドライブ同期',
      body:
        '<p>自分で貼った<b>図</b>と、書き換えた<b>解説</b>を、' +
        '<b>あなた自身のGoogleドライブ</b>へ預けます。端末が変わっても、' +
        '同じGoogleアカウントでログインすれば戻ります。</p>' +
        '<ul>' +
        '<li><b>このアプリに運営者のサーバーはありません。</b>通信はあなたの端末から' +
        'Googleへ直接行きます。作った人が中身を見る手段は用意されていません。</li>' +
        '<li>アプリが触れるのは<b>アプリが作ったファイルだけ</b>です。' +
        'ドライブの他の中身は読めません。</li>' +
        '<li><b>同期はボタンを押したときだけ走ります。</b>' +
        'ブラウザだけの仕組みでは、黙って裏で通信し続けることができないためです。</li>' +
        '<li>問題データ本体は同期しません。TSVの取り込みでどの端末でも同じものが作れるので、' +
        '通信量に見合いません。</li>' +
        '</ul>' +
        '<p><b>入れてはいけないもの</b>：参考書や問題集の紙面をそのまま撮った画像、' +
        '患者さんの情報や実習記録など個人が特定できるもの。</p>'
    }
  };

  /* 12列TSVの列ごとの説明。
     8（問題文）・10（正解）・11（解説）は置かない。読めば分かるものに
     説明を付けると、本当に分からない列（ランク・形式・タグ）が埋もれる。 */
  var HELP_COLS = {
    col1: {
      title: '1列目：単元',
      body:
        '<p><b>必須</b>です。空だとその行は取り込まれません。</p>' +
        '<p>出題基準のいちばん大きな区分です。「必修問題」「人体の構造と機能」' +
        '「疾病の成り立ちと回復の促進」など、お手元の出題基準の見出しをそのまま書いてください。</p>' +
        '<ul><li><b>単元別学習</b>のツリーの第1階層になります。</li>' +
        '<li>模試の合否判定で「必修」かどうかを見分ける手がかりにもなります' +
        '（文字列に「必修」が含まれるかで判定します）。</li></ul>'
    },
    col2: {
      title: '2列目：目標',
      body:
        '<p><b>空でOK</b>です。</p>' +
        '<p>出題基準の「目標Ⅰ」「目標Ⅱ」…にあたる部分です。' +
        'いまのところ画面には出さず、内部に持っているだけです。</p>' +
        '<p>将来「目標別の成績」を出すときに使うので、手元にあるなら入れておくと得です。' +
        '無ければ空のままで、何も困りません。</p>'
    },
    col3: {
      title: '3列目：ランク（出題頻度）',
      body:
        '<p><b>分からなければ空でOK</b>です（Bとして扱います）。</p>' +
        '<p>その問題が試験に出る頻度です。<b>S / A / B / C</b> の4段階。' +
        '出題の優先度を決める重みになります。</p>' +
        '<ul>' +
        '<li><b>S</b>（重み ×2.5）… ほぼ毎年出る。必修レベルの定番</li>' +
        '<li><b>A</b>（重み ×1.6）… 数年に1回は出る</li>' +
        '<li><b>B</b>（重み ×1.0）… 標準。迷ったらこれ</li>' +
        '<li><b>C</b>（重み ×0.3）… 細かい知識。後回しでよい</li>' +
        '</ul>' +
        '<p>「頻出問題を優先する」がONのとき、<b>弱点pt × この重み</b>の順に出題されます。' +
        'OFFにすれば重みは無視され、純粋な弱点順になります。</p>' +
        '<p>S/A/B/C 以外の文字を書くと、警告を出してBに直します。</p>'
    },
    col4: {
      title: '4列目：大項目',
      body:
        '<p><b>推奨</b>。空でも取り込めますが、弱点分析の「大項目」の軸が空になります。</p>' +
        '<p><b>先頭に数字を付けてください。</b>例：<code>1. 健康に関する指標</code></p>' +
        '<p>この先頭の数字が、画面に出る階層コード <code>[1-<b>1</b>-A-a]</code> の2桁目になります。' +
        '数字が無いと <code>[1-?-A-a]</code> と表示されます。</p>' +
        '<p>ランダムモードで「大項目だけ」を選ぶときの単位でもあります。</p>'
    },
    col5: {
      title: '5列目：中項目',
      body:
        '<p><b>推奨</b>。空でも取り込めますが、単元別学習の第3階層が空になります。</p>' +
        '<p><b>先頭に英大文字を付けてください。</b>例：<code>A. 人口静態・人口動態</code></p>' +
        '<p>階層コード <code>[1-1-<b>A</b>-a]</code> の3桁目になります。</p>' +
        '<p>設定の「中項目ごとに進捗を消す」は、<b>この列の単位</b>で消します。' +
        '空だと、その範囲を選んで消すことができません。</p>'
    },
    col6: {
      title: '6列目：小項目',
      body:
        '<p><b>推奨</b>。ここを空にすると、<b>いちばんよく使う画面が機能しません。</b></p>' +
        '<p><b>先頭に英小文字を付けてください。</b>例：<code>a. 総人口</code>' +
        '（複数なら <code>a. 総人口、d. 将来推計人口</code> のように並べてOK）</p>' +
        '<p>階層コード <code>[1-1-A-<b>a</b>]</code> の4桁目になります。</p>' +
        '<p>弱点分析の<b>既定の軸がこの小項目</b>です。出題基準の中で最も小さい単位なので、' +
        'ここが埋まっていると「どこが弱いか」が具体的に出ます。空だと粗い分析しかできません。</p>'
    },
    col7: {
      title: '7列目：形式',
      body:
        '<p><b>分からなければ空でOK</b>です（single として扱います）。</p>' +
        '<ul>' +
        '<li><b>single</b> … 選択肢から1つ選ぶ（ふつうの問題）</li>' +
        '<li><b>multiple</b> … 2つ以上選ぶ。いくつ選ぶかは10列目の正解の個数から自動で決まります</li>' +
        '<li><b>numeric</b> … 数値を入力する計算問題。9列目（選択肢）は空でよく、' +
        '10列目に答えの数値をそのまま書きます</li>' +
        '</ul>' +
        '<p>日本語でも受け付けます：<code>単一</code> <code>複数</code> <code>計算</code> <code>数値</code>。</p>' +
        '<p>読めない文字を書くと、警告を出して single に直します。</p>'
    },
    col9: {
      title: '9列目：選択肢',
      body:
        '<p><b>必須</b>です（numeric形式のときだけ空でOK）。</p>' +
        '<p><b>JSONの配列で書きます。</b>ダブルクォートは<b>半角</b>で。</p>' +
        '<p><code>["1億人を下回った","2008年がピーク","増加している","横ばいである"]</code></p>' +
        '<ul>' +
        '<li>選択肢は<b>2つ以上</b>あれば通ります。5つでも構いません。</li>' +
        '<li>先頭に <code>①</code> <code>②</code> を付けていても、自動で外します。</li>' +
        '<li>JSONとして読めないときは <code>|</code>（縦棒）や改行で区切っても拾いますが、' +
        '警告が出ます。JSONで書くのが確実です。</li>' +
        '<li>スプレッドシート経由でクォートが二重になっていても、こちらで直します。</li>' +
        '</ul>' +
        '<p>この並び順が、そのまま <code>①②③④</code> の番号になります。' +
        '<b>10列目の正解も11列目の解説も、この順番を前提にしています。</b>' +
        'あとから並べ替えないでください。</p>'
    },
    col13: {
      title: '13列目：一問一答にしてよいか',
      body:
        '<p><b>任意</b>。<code>split</code> と書いた問題だけが、' +
        '「本日の復習」で1肢だけの一問一答（○×）として出ることがあります。' +
        '<b>空欄なら今までどおり4択のままです。</b></p>' +
        '<p>13列目そのものを付けなくても取り込めます（12列のままで動きます）。</p>' +
        '<p><b>書かないほうが安全な問題があります。</b></p>' +
        '<ul>' +
        '<li>「<b>最も</b>近いのはどれか」「最も適切なのはどれか」のように、' +
        '<b>選択肢どうしを比べないと答えが決まらない</b>問題。' +
        '1肢だけ切り出すと設問が成立しません</li>' +
        '<li>「誤っているのはどれか」のように、正誤の向きが反転している問題</li>' +
        '</ul>' +
        '<p>迷ったら<b>空欄のまま</b>にしてください。空欄で困ることは何も起きません' +
        '（4択で出るだけです）。逆に、切り出してはいけない問題に <code>split</code> を' +
        '書くと、意味の通らない問題が出ます。</p>'
    },
    col12: {
      title: '12列目：テーマタグ',
      body:
        '<p><b>推奨</b>。空だと、その問題は<b>テーマ別の弱点分析と弱点ノックの対象外</b>になります。</p>' +
        '<p><b>選択肢ごとの配列を、さらに配列で包みます。</b></p>' +
        '<p><code>[["#人口動態統計"],["#人口動態統計"],["#人口動態統計"],["#人口動態統計"]]</code></p>' +
        '<ul>' +
        '<li><b>全部同じタグで構いません。</b>実際、ほとんどの問題はそうなります。</li>' +
        '<li>先頭に <code>#</code> を付けてください。</li>' +
        '<li>1つの選択肢に複数付けてもOK：<code>[["#人口動態統計","#高齢化"]]</code></li>' +
        '<li>選択肢の数より少なくても、先頭のタグで自動的に埋めます。</li>' +
        '<li>アプリが持っている74テーマ以外の名前でも登録できます' +
        '（「マスターに無いタグ」として集計されます）。</li>' +
        '</ul>' +
        '<p>この列が空でも取り込みは成功します。<b>最終行が空でも落ちません</b>' +
        '（V1.15で直しました）。</p>'
    }
  };

  function openHelp(key) {
    var h = HELP[key] || HELP_COLS[key];
    if (!h) { return Promise.resolve(null); }
    setText('#help-title', h.title);
    setHtml('#help-body', h.body);
    openModal('#modal-help');
    return Promise.resolve(h);
  }

  /* ======================================================================
   * 9. ポモドーロの休憩・通知・アラーム（第10章②）
   * ====================================================================== */

  /* 外部音源を持たない（完全オフライン要件）。WebAudioで3種類を合成する。 */
  var ALARM_DEFS = {
    chime: { freqs: [880, 1318.5], dur: 0.28, gap: 0.30, type: 'sine',     gain: 0.16 },
    bell:  { freqs: [1568, 1568, 1046.5], dur: 0.16, gap: 0.20, type: 'triangle', gain: 0.14 },
    soft:  { freqs: [523.25, 659.25, 783.99], dur: 0.36, gap: 0.34, type: 'sine', gain: 0.10 }
  };

  /* 自分の音。Blob URL は1つだけ持ち回し、差し替えたときだけ作り直す。 */
  var alarmUrl = null, alarmUrlId = null;

  function customAlarmUrl() {
    return S.getUserAudio().then(function (rec) {
      if (!rec || !rec.blob) {
        if (alarmUrl) { global.URL.revokeObjectURL(alarmUrl); alarmUrl = null; alarmUrlId = null; }
        return null;
      }
      var stamp = String(rec.updated_at || 0);
      if (alarmUrl && alarmUrlId === stamp) { return alarmUrl; }
      if (alarmUrl) { global.URL.revokeObjectURL(alarmUrl); }
      alarmUrl = global.URL.createObjectURL(rec.blob);
      alarmUrlId = stamp;
      return alarmUrl;
    }).catch(function () { return null; });
  }

  function playAlarm(kind) {
    var name = kind || (M.state.meta && M.state.meta.pomodoro_alarm) || 'chime';
    if (name === 'custom') {
      /* 取り込んだ音が消えている・再生できない環境では、黙って無音にせず
         合成音へ落とす。鳴らないと「休憩を挟む」動線ごと消える。 */
      customAlarmUrl().then(function (url) {
        if (!url) { playSynthAlarm('chime'); return; }
        try {
          var au = new global.Audio(url);
          au.volume = 0.9;
          var pr = au.play();
          if (pr && pr.catch) { pr.catch(function () { playSynthAlarm('chime'); }); }
        } catch (e) { playSynthAlarm('chime'); }
      });
      return;
    }
    playSynthAlarm(name);
  }

  function playSynthAlarm(kind) {
    var name = kind || 'chime';
    var def = ALARM_DEFS[name] || ALARM_DEFS.chime;
    var Ctx = global.AudioContext || global.webkitAudioContext;
    if (!Ctx) { return; }
    try {
      if (!st.audio) { st.audio = new Ctx(); }
      if (st.audio.state === 'suspended') { st.audio.resume().catch(noop); }
      var t0 = st.audio.currentTime + 0.02;
      def.freqs.forEach(function (f, i) {
        var osc = st.audio.createOscillator();
        var g = st.audio.createGain();
        var start = t0 + i * def.gap;
        osc.type = def.type;
        osc.frequency.setValueAtTime(f, start);
        g.gain.setValueAtTime(0, start);
        g.gain.linearRampToValueAtTime(def.gain, start + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, start + def.dur);
        osc.connect(g); g.connect(st.audio.destination);
        osc.start(start); osc.stop(start + def.dur + 0.02);
      });
    } catch (e) { /* 音が出せない環境でも学習は止めない */ }
  }

  /* 入れた音の選択肢は、入れる前は <<Free>>、入れたあとは
     そのファイル名にする。「自分の音」のような説明語は、
     3つ入れ替えたときにどれがどれだか分からなくなる。 */
  var FREE_SLOT_LABEL = '<<Free>>';

  function setAlarmOptionLabel(name) {
    var sel = $('#set-alarm');
    if (!sel) { return; }
    var i, opt = null;
    for (i = 0; i < sel.options.length; i++) {
      if (sel.options[i].value === 'custom') { opt = sel.options[i]; }
    }
    if (opt) { opt.textContent = name || FREE_SLOT_LABEL; }
  }

  function refreshAlarmFileNote() {
    return S.getUserAudio().then(function (rec) {
      var del = $('#btn-alarm-del');
      if (rec && rec.blob) {
        var nm = rec.name || null;
        setAlarmOptionLabel(nm);
        setText('#alarm-file-note',
          (nm ? ('「' + nm + '」が') : '音が') + '入っています（' +
          Math.max(1, Math.round(rec.bytes / 1024)) + 'KB）。' +
          '「アラーム音」で選ぶと鳴ります。');
        if (del) { del.hidden = false; }
      } else {
        setAlarmOptionLabel(null);
        setText('#alarm-file-note',
          'まだ入っていません。mp3 / m4a / wav などを1つ（1MBまで）');
        if (del) { del.hidden = true; }
      }
      return rec;
    });
  }

  function saveAlarmFile(file) {
    return S.putUserAudio(file).then(function (rec) {
      return refreshAlarmFileNote().then(function () {
        toast('音を保存しました（' + Math.max(1, Math.round(rec.bytes / 1024)) + 'KB）', 2800);
        /* 入れた直後に選ばれていないと、鳴らして確かめられない。 */
        return S.setMeta('pomodoro_alarm', 'custom');
      }).then(function () {
        return S.loadMeta();
      }).then(function (m) {
        M.state.meta = m;
        var sel = $('#set-alarm'); if (sel) { sel.value = 'custom'; }
        playAlarm('custom');
        return rec;
      });
    }).catch(function (e) {
      toast(e && e.message ? e.message : '音を保存できませんでした', 5000);
      return null;
    });
  }

  function deleteAlarmFile() {
    return S.deleteUserAudio().then(function () {
      return refreshAlarmFileNote();
    }).then(function () {
      /* 「<<Free>>」を選んだまま消すと無音になるので、チャイムへ戻す。 */
      if (M.state.meta && M.state.meta.pomodoro_alarm === 'custom') {
        return S.setMeta('pomodoro_alarm', 'chime').then(function () {
          return S.loadMeta();
        }).then(function (m) {
          M.state.meta = m;
          var sel = $('#set-alarm'); if (sel) { sel.value = 'chime'; }
        });
      }
      return null;
    }).then(function () { toast('音を消しました', 2200); return true; });
  }

  /* 表示位置を保存して、開いている解説にも即座に反映する（V1.29）。 */
  function setUserImagePos(value) {
    if (!M.USERIMG_SLOTS[value]) { value = 'after-figure'; }
    return S.setMeta('user_image_pos', value).then(function () {
      return S.loadMeta();
    }).then(function (m) {
      M.state.meta = m;
      M.placeUserImageSection();
      toast('自分で入れた図の位置を変えました', 2200);
      return value;
    });
  }

  /* --- 国家試験の日（V1.30） ---
     入れると scheduler 側で ①間隔の上限（残り日数の1/3）
     ②直前10日の出題順 の2つが自動で効く。ここは入出力だけを受け持つ。 */
  function fmtExamNote(meta) {
    var b = meta.day_boundary_hour;
    var rest = K.examRemainingDays(meta, Date.now(), b);
    if (rest === null) { return 'まだ入っていません。'; }
    if (rest < 0) {
      return 'この年の試験は終わっています。間隔の上限は外れ、通常（最長180日）に戻っています。'
           + '次の年を選び直してください。';
    }
    var cap = K.examCapMs(meta, Date.now(), b);
    var capTxt = (cap >= 24 * 3600 * 1000)
      ? Math.round(cap / (24 * 3600 * 1000)) + '日'
      : '1時間';
    var phase = K.examPhase(meta, Date.now(), b);
    return 'あと ' + rest + ' 日。復習の間隔は最長 ' + capTxt + ' までに抑えます'
         + (phase === 'final'
            ? '。直前' + K.EXAM_FINAL_DAYS + '日なので、必修と「しばらく解いていない問題」を先に出します。'
            : '。');
  }

  /* --- 受験する年（V1.44） ---
     日付ではなく年だけを選ばせる。この値は「復習間隔の上限」を決める
     残り日数にしか使わないので、日付の精度は要らない。
     逆に画面へ日付を出すと、実際の試験日（2月の日曜。年ごとに動く）と
     ずれたときに【アプリが嘘をつく】ことになる。だから年だけを見せる。

     内部の日付：2027年は 2/14、2028年以降は 2/15 で固定。
     ±2日の差は EXAM_FINAL_DAYS（10日）の粒度に対して無視できる。 */
  function examDateForYear(year) {
    var y = parseInt(year, 10);
    if (!y) { return null; }
    return y + (y === 2027 ? '-02-14' : '-02-15');
  }

  function examYearOf(dateStr) {
    var m = /^(\d{4})-/.exec(String(dateStr || ''));
    return m ? m[1] : '';
  }

  /* 過ぎた年は出さない。選べてしまうと残り日数が負になり、
     間隔の上限計算が壊れる（examCapMs が不定になる）。 */
  function fillExamYears(current) {
    var sel = $('#set-exam-year');
    if (!sel) { return; }
    var now = new Date();
    var y0 = now.getFullYear();
    /* その年の試験日をもう過ぎていれば、翌年から並べる。 */
    if (new Date(examDateForYear(y0) + 'T00:00:00') < now) { y0 += 1; }
    var opts = ['<option value="">選ばない</option>'], y;
    for (y = y0; y < y0 + 6; y++) {
      opts.push('<option value="' + y + '">' + y + '年（2月中旬）</option>');
    }
    /* 保存済みの年が範囲外（＝過ぎた年）なら、それも出しておく。
       黙って別の年へ書き換えると、利用者は設定した覚えのない年を見る。 */
    if (current && opts.join('').indexOf('value="' + current + '"') < 0) {
      opts.splice(1, 0, '<option value="' + current + '">' + current + '年（過ぎています）</option>');
    }
    sel.innerHTML = opts.join('');
    sel.value = current || '';
  }

  /* --- 選択肢ごとの解説の見せ方（V1.44） --- */
  var EXPLAIN_NOTE = {
    hidden: '選択肢ごとの解説は出しません。全体解説を読んで、自分の言葉で書いてみてください。',
    button: '「解説を見る」を押したときだけ出ます。まず自分で説明してみるのがおすすめです。',
    open  : '正解を出した時点で、選択肢ごとの解説も一緒に出ます。'
  };

  function refreshExplainMode() {
    var mode = M.explainMode ? M.explainMode() : 'button';
    $$('#set-explain-mode .seg-btn').forEach(function (b) {
      cls(b, 'is-active', b.getAttribute('data-explain') === mode);
    });
    setText('#explain-mode-note', EXPLAIN_NOTE[mode] || '');
    return mode;
  }

  function setExplainMode(mode) {
    if (!EXPLAIN_NOTE[mode]) { return Promise.resolve(null); }
    return S.setMeta('explain_mode', mode).then(function () {
      return S.loadMeta();
    }).then(function (m) {
      M.state.meta = m;
      refreshExplainMode();
      toast('解説の出し方を変えました', 2200);
      return m;
    });
  }

  function refreshExamNote() {
    return S.loadMeta().then(function (m) {
      M.state.meta = m;
      fillExamYears(examYearOf(m.exam_date));
      var clr = $('#btn-exam-clear');
      if (clr) { clr.hidden = !m.exam_date; }
      setText('#exam-note', fmtExamNote(m));
      return m;
    });
  }

  /* 保存の形（exam_date の YYYY-MM-DD）は変えない。
     scheduler 側の期日計算をそのまま使えるようにするため。
     画面で年しか見せない、というだけの違いにする。 */
  function setExamYear(year) {
    var v = examDateForYear(year);
    if (year && !v) {
      toast('年として読めませんでした', 3000);
      return Promise.resolve(null);
    }
    return S.setMeta('exam_date', v).then(function () {
      return refreshExamNote();
    }).then(function (m) {
      toast(v ? (year + '年の受験で設定しました') : '受験する年を消しました', 2400);
      return m;
    });
  }

  /* ================================================================
   * 必修の出題比率（V1.89）
   *
   * 自動が既定。手動は3択の逃げ道で、**手動が自動より弱いときだけ**案内を出す。
   * 案内は1日1回まで、3回「このまま」を押したら以後出さない（§2-3）。
   * 文言に％は出さない。合格ラインまでの距離だけを出す（戦略§2-1）。
   * ================================================================ */
  var HISSU_LABEL = { auto: '自動', strong: '強め', normal: '本番と同じ' };

  function hissuDistance(fill) {
    /* 必修50問＝200肢相当ではなく、いま持っている必修の肢で「50問中いくつ相当か」に直す。
       ％を出さないための換算で、母数が変わっても意味が変わらない。 */
    var got = Math.round((fill.rate || 0) * 50);
    return { got: got, gap: Math.max(0, 40 - got) };
  }

  function refreshHissuNote() {
    var box = $('#hissu-note');
    return K.getHissuFill().then(function (fill) {
      return S.loadMeta().then(function (meta) {
        var r = K.resolveHissuShare(meta, fill.rate);
        var d = hissuDistance(fill);
        $$('#set-hissu .seg-btn').forEach(function (b) {
          b.classList.toggle('is-active', b.dataset.hissu === r.mode);
        });
        if (box) {
          box.textContent = fill.atoms
            ? ('必修は いま ' + d.got + '/50 相当'
               + (d.gap ? '（合格ラインまで −' + d.gap + '）' : '（合格ラインに乗っています）')
               + '　いまの比率 ' + Math.round(r.share * 100) + '%'
               + (r.mode === 'auto' ? '（自動）' : '（' + HISSU_LABEL[r.mode] + '）'))
            : '必修の問題がまだありません。';
        }
        return r;
      });
    });
  }

  function setHissuMode(mode) {
    if (['auto', 'strong', 'normal'].indexOf(mode) < 0) { return Promise.resolve(null); }
    return S.setMeta('hissu_mode', mode).then(function () {
      return S.loadMeta();
    }).then(function (meta) {
      M.state.meta = meta;
      return refreshHissuNote();
    }).then(function (r) {
      toast(mode === 'auto'
        ? '必修の比率を自動で決めます'
        : ('必修の比率を「' + HISSU_LABEL[mode] + '」に固定しました'), 2800);
      return r;
    });
  }

  /* 起動時に1回だけ呼ぶ。出す条件は「手動 かつ 自動より弱い」。 */
  function maybeHissuHint() {
    return S.loadMeta().then(function (meta) {
      if ((meta.hissu_hint_no || 0) >= 3) { return false; }
      /* 案内は「手動で弱めている人を自動へ戻す」ためだけにある。
         自動のままの人には出しようがない。ここで先に降りないと、
         既定の人まで起動直後に全アトムを読むことになり、
         起動が重くなる（画面が滑って押し損ねるところまで実測した）。 */
      if (((meta.hissu_mode || 'auto') === 'auto')) { return false; }
      var today = new Date(); today.setHours(0, 0, 0, 0);
      if ((meta.hissu_hint_at || 0) >= today.getTime()) { return false; }
      return K.getHissuFill().then(function (fill) {
        if (!fill.atoms) { return false; }
        var r = K.resolveHissuShare(meta, fill.rate);
        if (!r.hint) { return false; }
        var d = hissuDistance(fill);
        setHtml('#hissu-hint-body',
          '必修は いま <b>' + d.got + '/50 相当</b>（合格ラインまで −' + d.gap + '）。<br>' +
          '自動に戻すと、新規・ランダムに必修が出る割合が ' +
          Math.round(r.share * 100) + '% → <b>' + Math.round(r.auto * 100) + '%</b> に増えます。<br>' +
          '<small>本日の復習は変わりません。</small>');
        openModal('#modal-hissu-hint');
        return S.setMeta('hissu_hint_at', Date.now()).then(function () { return true; });
      });
    }).catch(function () { return false; });
  }

  function hissuHintAnswer(toAuto) {
    closeModals();
    if (toAuto) {
      return S.setMeta('hissu_hint_no', 0).then(function () { return setHissuMode('auto'); });
    }
    return S.loadMeta().then(function (meta) {
      return S.setMeta('hissu_hint_no', (meta.hissu_hint_no || 0) + 1);
    });
  }

  /* ================================================================
   * ドライブ同期（V1.31）
   * 通信の中身は drive.js。ここは画面と、押させる順序だけを受け持つ。
   * ================================================================ */

  var DRIVE_ORIGIN_HINT = 'https://<あなたのGitHubアカウント名>.github.io';

  var DRIVE_STEPS = [
    'Google Cloud Console（console.cloud.google.com）を開き、プロジェクトを1つ作る。名前は何でもよい。',
    '「APIとサービス」→「ライブラリ」で <b>Google Drive API</b> を探して有効にする。',
    '「APIとサービス」→「OAuth同意画面」を開く。ユーザーの種類は<b>外部</b>、公開状態は<b>テスト</b>のままでよい。' +
      '<b>テストユーザーに自分のGmailアドレスを追加する</b>（これを忘れるとログインで弾かれる）。',
    'スコープの追加で <b>.../auth/drive.file</b> だけを選ぶ。' +
      '<b>drive や drive.readonly は選ばない</b>（追加審査が必要になり、しかも全部見えてしまう）。',
    '「認証情報」→「認証情報を作成」→ <b>OAuth クライアント ID</b>。種類は <b>ウェブ アプリケーション</b>。',
    '<b>承認済みの JavaScript 生成元</b>に、アプリを置くアドレスを入れる。' +
      '<br>例：<code>' + DRIVE_ORIGIN_HINT + '</code>' +
      '<br>末尾に / を付けない。パス（/nurse/ など）も入れない。<b>ドメインまで</b>。' +
      '<br>PCで試すなら <code>http://localhost:8000</code> も足しておく。',
    '「承認済みのリダイレクトURI」は<b>空のままでよい</b>（この方式では使わない）。',
    '作成後に出る<b>クライアントID</b>（末尾が .apps.googleusercontent.com）をコピーし、上の欄に貼って保存。'
  ];

  function renderDriveSteps() {
    var ol = $('#drive-steps');
    if (!ol || ol.childElementCount) { return; }
    ol.innerHTML = DRIVE_STEPS.map(function (t) { return '<li>' + t + '</li>'; }).join('');
  }

  /* 組み込みIDがあるかどうかで、上級者向けの見出しを変える。
     「壊れているのでは」と思わせないため、状態を言葉で書く。 */
  function refreshDriveAdvanced(hasOwn) {
    var d = $('#drive-advanced');
    if (!d) { return; }
    var sum = d.querySelector('summary');
    if (!sum) { return; }
    sum.textContent = hasOwn
      ? '自分のGoogle Cloudで動かす（設定済み）'
      : '自分のGoogle Cloudで動かす（上級者向け）';
  }

  function fmtStamp(ms) {
    if (!ms) { return 'まだ一度も同期していません'; }
    var d = new Date(ms);
    var p = function (n) { return String(n).padStart(2, '0'); };
    return '最後の同期：' + d.getFullYear() + '/' + p(d.getMonth() + 1) + '/' + p(d.getDate()) +
           ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  /* --- 保存領域の欄（V1.60） ---
     既定のブラウザ保存は「いつ消されてもおかしくない」扱い。
     端末の空きが減ると OS やブラウザが黙って IndexedDB を捨てるし、
     Safari は一定期間開かないサイトのデータを消す。
     **黙って消される状態のまま売ってはいけない**ので、状態を見せる。 */
  function refreshStorage() {
    var row = $('#store-row');
    if (!row) { return Promise.resolve(null); }
    return S.storageInfo().then(function (info) {
      if (!info.supported) { row.hidden = true; return info; }
      row.hidden = false;
      var mb = function (n) { return Math.round(n / 1048576 * 10) / 10; };
      setText('#store-note',
        '使用 ' + mb(info.usage) + 'MB ／ 上限 ' + Math.round(info.quota / 1048576) + 'MB'
        + '（空き ' + mb(info.free) + 'MB）');
      var fill = $('#store-bar-fill');
      if (fill) {
        fill.style.width = info.pct + '%';
        fill.setAttribute('data-tone', info.pct >= 90 ? 'bad' : info.pct >= 70 ? 'warn' : 'ok');
      }
      var btn = $('#btn-persist'), warn = $('#store-warn');
      if (info.persisted === true) {
        if (btn) { btn.hidden = true; }
        if (warn) {
          warn.hidden = false;
          warn.textContent = 'この端末では、空き容量が減っても学習の記録が消されない設定になっています。';
        }
      } else {
        if (btn) { btn.hidden = false; }
        if (warn) {
          warn.hidden = false;
          /* 脅かさない。事実と、対処と、それでも保険が要ることだけを言う。 */
          warn.textContent = '空き容量が減ったとき、ブラウザが学習の記録を消すことがあります。'
            + '［消えないようにする］を押すと、消さないよう要求します。'
            + 'どちらの場合も、ときどきバックアップを書き出しておくのが確実です。';
        }
      }
      return info;
    });
  }

  /* --- ライセンス欄（V1.53） ---
     数え方は scheduler の solved_ever ただ1つ。ここで数え直さない
     （数え方が2箇所に分かれると、ホームと設定で違う数が出る）。 */
  function refreshLicense() {
    var L = global.NurseLicense;
    var block = $('#lic-block');
    if (!block) { return; }
    if (!L) { block.hidden = true; return; }      /* 読めていない環境では出さない */

    var h = M.state.homeState || {};
    var g = L.gate(h.solved_ever);
    var input = $('#lic-input-wrap'), paid = $('#lic-paid-wrap'), bar = $('#lic-bar');
    if (g.paid) {
      var pl = L.payload() || {};
      setText('#lic-state', '購入済み');
      setText('#lic-note', pl.n ? ('登録：' + pl.n) : '全ての問題が開いています');
      if (input) { input.hidden = true; }
      if (paid)  { paid.hidden = false; }
      if (bar)   { bar.hidden = true; }
    } else {
      setText('#lic-state', g.locked ? 'お試し（上限に到達）' : 'お試し中');
      setText('#lic-note', g.locked
        ? '新しい問題は止まっています。復習はこのまま続けられます。'
        : 'あと ' + g.left + '問（' + g.used + ' / ' + g.limit + '問）');
      if (input) { input.hidden = false; }
      if (paid)  { paid.hidden = true; }
      if (bar) {
        bar.hidden = false;
        var f = $('#lic-bar-fill');
        if (f) { f.style.width = Math.min(100, Math.round(g.used / g.limit * 100)) + '%'; }
      }
    }
    setText('#lic-msg', '');
  }

  function applyLicense() {
    var L = global.NurseLicense;
    var box = $('#lic-key');
    if (!L || !box) { return Promise.resolve(null); }
    var v = box.value;
    if (!v || !v.trim()) { setText('#lic-msg', '鍵を貼り付けてください'); return Promise.resolve(null); }
    return L.activate(v).then(function (r) {
      if (r.ok) {
        box.value = '';
        toast('ありがとうございます。全ての問題が開きました');
        refreshLicense();
        M.refreshFreeGate();
        return M.refreshHome ? M.refreshHome() : null;
      }
      /* 失敗の理由を分けて出す。「無効です」だけだと、
         貼り間違いなのか鍵が違うのか分からず問い合わせになる。 */
      setText('#lic-msg',
        r.reason === 'format'   ? '鍵の形が違います。OMOI1. から始まる全体を貼り付けてください。' :
        r.reason === 'nocrypto' ? 'この端末では鍵の確認ができません（古いブラウザの可能性）。' :
                                  'この鍵は確認できませんでした。購入時に届いたものか確かめてください。');
      return null;
    });
  }

  function refreshDrive() {
    renderDriveSteps();
    return Promise.all([D.getClientId(), D.lastSync(), D.hasConsent()]).then(function (r) {
      var id = r[0], last = r[1], consent = r[2];
      var own = null, lastErr = null;
      var inp = $('#drive-client-id');
      /* 入力欄には【自分で入れたIDだけ】を映す。組み込みIDをここへ書くと、
         保存し直したときに自分のIDとして固定されてしまう。 */
      return S.loadMeta().then(function (mm) {
        own = mm.drive_client_id || null;
        lastErr = mm.drive_last_error || null;
        if (inp && !inp.value) { inp.value = own || ''; }
        refreshDriveAdvanced(!!own);
        /* 同期で残せなかったメモ（V1.72）。無いときは行ごと隠す */
        var scRow = $('#btn-sync-conflicts');
        var scList = Array.isArray(mm.sync_conflicts) ? mm.sync_conflicts : [];
        if (scRow) {
          scRow.hidden = !scList.length;
          setText('#sync-conflicts-note',
            scList.length + '件の控えがあります。読んで、必要なら写して、片づけてください');
        }
        return null;
      }).then(function () {

      var signedIn = D.tokenValid();
      var builtIn = D.hasBuiltInClientId();
      var st = !id ? 'まだ使えません'
             : signedIn ? 'ログイン中（このあと約1時間は押さずに同期されます）'
             : '押すとログインして同期します';
      setText('#drive-state', st);
      setText('#drive-note', !id
        ? (builtIn ? 'ログインの準備ができていません。'
                   : 'このアプリにはIDが組み込まれていません。下の「自分のGoogle Cloudで動かす」を開いてください。')
        : fmtStamp(last) + (consent ? '' : '（初回は注意事項の確認があります）')
          /* 自動同期は黙って走るので、失敗はここでしか気づけない。 */
          + (lastErr ? '　⚠ ' + lastErr : ''));

      var logout = $('#btn-drive-logout'), sync = $('#btn-drive-sync');
      var label = $('#drive-sync-label'), badge = $('#drive-pending');
      if (logout) { logout.hidden = !signedIn; }
      /* ログインしていなくても押せる。押した1回でログインまで済ませる。 */
      if (sync)   { sync.disabled = !id; }
      if (label)  { label.textContent = signedIn ? '今すぐ同期' : 'ログインして同期'; }
      return D.pendingCount().then(function (n) {
        if (badge) {
          badge.hidden = !(n > 0);
          badge.textContent = n > 99 ? '99+' : String(n);
        }
        /* 設定画面の中と外で件数が食い違わないよう、同じ n で両方を書く。 */
        refreshSyncBadge(n);
        return { id: id, signedIn: signedIn, last: last, consent: consent,
                 builtIn: builtIn, own: own, pending: n };
      });
      });
    });
  }

  function saveDriveClientId() {
    var inp = $('#drive-client-id');
    var v = inp ? inp.value : '';
    return D.setClientId(v).then(function (saved) {
      toast(saved ? 'クライアントIDを保存しました' : 'クライアントIDを消しました', 2600);
      return refreshDrive();
    }).catch(function (e) {
      toast(e.message || '保存できませんでした', 5000);
      return null;
    });
  }

  /* 初回だけ出す注意書き。ここを通らないと同期は始まらない。 */
  /* 同意の確認。【同期関数】であることが重要。
     ここでDBを読みに行くと、その待ち時間で利用者の操作が切れ、
     iOS Safari がログイン窓を塞ぐ（V1.37 で判明）。
     判定は起動時に読み込み済みの M.state.meta から取る。 */
  function askDriveConsentSync() {
    var m = M.state.meta || {};
    if (m.drive_consent_at) { return true; }
    var ok = global.confirm(
      'Googleドライブとの同期を開始します。\n\n' +
      '同期の対象は、利用者が追加した図および書き換えた解説文です。\n' +
      '保存先は利用者自身のGoogleドライブであり、\n' +
      '開発者が内容を閲覧することはできません。\n\n' +
      '次の内容は取り込まないでください。\n' +
      '・著作権のある資料（市販の参考書・問題集の紙面を撮影した画像等）\n' +
      '・個人を特定できる情報（患者情報、実習記録等）\n\n' +
      '詳細は利用規約およびプライバシーポリシーをご確認ください。\n\n' +
      '同意して続行しますか。');
    if (!ok) { return false; }
    /* 記録は待たない。待つとログイン窓が開かなくなる。 */
    M.state.meta.drive_consent_at = Date.now();
    D.giveConsent().catch(noop);
    return true;
  }

  /* --- ポップアップが開かない端末への案内（V1.39） ---
     Brave は既定でGoogleのログインを遮断する。利用者からは
     「真っ白な窓が出て終わる」としか見えず、アプリ側の不具合に見える。
     どのブラウザでも起こりうるので、名指しにせず条件で書く。 */
  function showBrowserHelp(kind) {
    var el = $('#drive-browser-note');
    if (!el) { return; }
    el.hidden = false;
    el.innerHTML =
      '<b>ログインの窓が開かない・白いまま閉じる場合</b><br>' +
      'お使いのブラウザが、Googleのログインを遮断している可能性があります。' +
      '次のいずれかをお試しください。<br>' +
      '・ポップアップの許可を出す（アドレス欄の右端に出る遮断マーク）<br>' +
      '・ブラウザの「シールド」「トラッキング防止」を、このサイトだけ切る<br>' +
      '・Google Chrome で開き直す<br>' +
      '・「ホーム画面に追加」してアプリとして開く（下の案内をご覧ください）' +
      (kind ? '<br><small>（' + kind + '）</small>' : '');
  }

  function driveLogin() { return driveSync(); }

  function driveLogout() {
    return D.signOut().then(function () {
      toast('ログアウトしました', 2200);
      return refreshDrive();
    });
  }

  function driveSync() {
    /* 同意の確認は【同期関数】のまま。ここでDBを待つと、その間に
       利用者の操作が切れてポップアップが塞がれる（V1.37で判明）。 */
    if (!askDriveConsentSync()) { toast('同期は開始していません', 2400); return Promise.resolve(null); }
    var btn = $('#btn-drive-sync');
    if (btn) { btn.disabled = true; }
    var note = $('#drive-browser-note');
    if (note) { note.hidden = true; }
    setText('#drive-state', '同期しています…');
    /* ここから先に await を挟まないこと。signInAndSync の中で
       必要なときだけログインし、そのまま同期へ続ける。 */
    return D.signInAndSync(function (m) { setText('#drive-note', m); })
    .catch(function (e) {
      var msg = (e && e.message) || String(e);
      if (/popup|ブロック|開けません|中止/.test(msg)) { showBrowserHelp(msg); }
      setText('#drive-note', msg);
      toast(msg, 5000);
      return null;
    }).then(function (rep) {
      if (!rep) { return refreshDrive(); }
      if (!rep.ok && rep.error === 'CONSENT_REQUIRED') {
        setText('#drive-note', '注意事項の確認がまだです。');
        return refreshDrive();
      }
      if (!rep.ok && rep.error === 'EXPIRED') {
        setText('#drive-note', 'ログインの有効期限が切れました。もう一度ログインしてください。');
        D.signOut();
        return refreshDrive();
      }
      if (!rep.ok) {
        setText('#drive-note', '同期できませんでした：' + rep.error);
        return refreshDrive();
      }
      var parts = [];
      if (rep.uploaded)     { parts.push('上げた図 ' + rep.uploaded + '件'); }
      if (rep.downloaded)   { parts.push('取り込んだ図 ' + rep.downloaded + '件'); }
      if (rep.memo_updated) { parts.push('解説 ' + rep.memo_updated + '件'); }
      if (rep.progress && rep.progress.added > 0) {
        parts.push('学習の記録 ' + rep.progress.added + '件');
      }
      if (rep.skipped)      { parts.push('できなかったもの ' + rep.skipped + '件'); }
      if (rep.conflicts.length) {
        parts.push('両方で直したもの ' + rep.conflicts.length + '件（新しい方を採用）');
      }
      /* 「変わりはありません」だけでは、何を見て何が無かったのかが伝わらない。
         利用者はここで詰まる（実際に詰まった）ので、状況を言葉にする。 */
      if (!parts.length) {
        var pr = rep.progress || {};
        setText('#drive-note',
          'この端末から上げるものはなく、ドライブから取り込むものもありませんでした。'
          + '（記録 ' + (pr.logs_after || 0) + '件で一致）');
        toast('すでに最新です', 2800);
      } else {
        toast('同期しました（' + parts.join(' / ') + '）', 4600);
      }
      return refreshDrive();
    });
  }

  /* --- 未同期の件数バッジ（V1.29／もとは V1.41 のヘッダー同期ボタン） ---
     ボタンは V1.44 で撤去したが、件数だけは設定ボタンの上に残してある。
     どこにも出さないと、溜まっていることに気づけないため。
     通信しないので、圏外でも正しい数が出る。
     n を渡せばその値を使う（呼び出し元が既に数えているときの二度手間を避ける）。 */
  function refreshSyncBadge(known) {
    var apply = function (n) {
      var b = $('#hdr-sync-badge');
      if (b) {
        b.hidden = !(n > 0);
        b.textContent = n > 99 ? '99+' : String(n);
      }
      return n;
    };
    if (typeof known === 'number') { return Promise.resolve(apply(known)); }
    return D.pendingCount().then(apply).catch(function () { return 0; });
  }

  /* スプラッシュの［ログインして同期］から呼ぶ。
     設定画面の driveSync と分けている理由は、報告先が違うから
     （設定画面のDOMはまだ描かれていないことがある）。
     ※ 呼び出しは【押したその場】から。await を挟まないこと。 */
  function driveSyncFromSplash(say) {
    say = say || function () {};
    if (!askDriveConsentSync()) { return Promise.resolve(null); }
    return D.signInAndSync(function (m) { say(m); }).then(function (rep) {
      if (!rep || !rep.ok) {
        say('同期できませんでした。あとで設定から試せます');
        return null;
      }
      var moved = (rep.uploaded || 0) + (rep.downloaded || 0) + (rep.deleted || 0) +
                  (rep.removed_local || 0) + (rep.memo_updated || 0) +
                  ((rep.progress && rep.progress.added) || 0);
      say(moved > 0 ? ('同期しました（' + moved + '件）') : 'すでに最新です');
      if (moved > 0 && M.refreshHome) { M.refreshHome().catch(function () {}); }
      return rep;
    }).catch(function (e) {
      var msg = (e && e.message) || String(e);
      /* ここで案内先を握りつぶさない。設定画面にも同じ案内を残す。 */
      if (/popup|ブロック|開けません|中止/.test(msg)) { showBrowserHelp(msg); }
      say('ログインできませんでした。あとで設定から試せます');
      return null;
    });
  }

  /* --- 起動時とホーム復帰時の自動同期（V1.39） ---
     【なぜ押さずに動かせるのか】
       1時間以内なら手元のトークンがまだ生きている。その間だけは
       ポップアップを出さずに通信できる。切れていれば黙って何もしない。
     【なぜ学習中に走らせないのか】
       同期は台帳を丸ごと入れ替えて各肢の状態を作り直す。
       解いている最中に足元の状態が変わると、いま出ている問題の
       期日や評価がすり替わる。ホームか設定にいるときだけ動かす。 */
  var autoSyncTimer = null;
  var autoSyncBusy = false;

  function autoSyncSafeNow() {
    var sc = M.state && M.state.screen;
    return (sc === 'home' || sc === 'settings') && !(M.state.current && M.state.current.question);
  }

  function runAutoSync(reason) {
    if (autoSyncBusy) { return Promise.resolve(null); }
    /* 閉じる直前（reason==='hide'）だけは画面を問わない。
       ここを逃すと、学習を終えてすぐ閉じる人の記録が一度も上がらない。
       解答の途中で閉じても、そこまでの記録は上げてよい。 */
    if (reason !== 'hide' && !autoSyncSafeNow()) { return Promise.resolve(null); }
    autoSyncBusy = true;
    return D.autoSync().then(function (rep) {
      autoSyncBusy = false;
      if (!rep || rep.skipped || !rep.ok) { return refreshDrive(); }
      var moved = (rep.uploaded || 0) + (rep.downloaded || 0) + (rep.deleted || 0) +
                  (rep.removed_local || 0) + (rep.memo_updated || 0) +
                  ((rep.progress && rep.progress.added) || 0);
      if (moved > 0) {
        /* 黙って書き換えない。何が変わったかは必ず見せる。 */
        toast('他の端末の学習を取り込みました（' + moved + '件）', 4200);
        if (M.refreshHome) { M.refreshHome(); }
      }
      return refreshDrive();
    }).catch(function () { autoSyncBusy = false; return null; });
  }

  function scheduleAutoSync(ms) {
    /* 同期そのものは ms 後だが、件数の表示は待たせない。
       ここは通信しないので、ログインしていなくても正しく出る。 */
    refreshSyncBadge();
    if (autoSyncTimer) { global.clearTimeout(autoSyncTimer); }
    autoSyncTimer = global.setTimeout(function () {
      autoSyncTimer = null;
      runAutoSync('timer');
    }, ms || 15000);
  }

  /* --- ホーム画面に追加（PWA） ---
     ブラウザで開いている限り、そのブラウザの制限をそのまま受ける。
     アプリとして入れてしまうのが、遮断問題への一番安い対策になる。 */
  var deferredInstall = null;

  function initPwaInstall() {
    global.addEventListener('beforeinstallprompt', function (e) {
      e.preventDefault();
      deferredInstall = e;
      var b = $('#btn-pwa-install');
      if (b) { b.hidden = false; }
    });
    global.addEventListener('appinstalled', function () {
      deferredInstall = null;
      var b = $('#btn-pwa-install');
      if (b) { b.hidden = true; }
      setText('#pwa-note', 'ホーム画面に追加済みです。');
    });
    if (global.matchMedia && global.matchMedia('(display-mode: standalone)').matches) {
      setText('#pwa-note', 'アプリとして開いています。');
    }
  }

  function pwaInstall() {
    if (!deferredInstall) { return pwaHow(); }
    var e = deferredInstall; deferredInstall = null;
    e.prompt();
    return Promise.resolve(e.userChoice).then(function () {
      var b = $('#btn-pwa-install');
      if (b) { b.hidden = true; }
      return null;
    }).catch(function () { return null; });
  }

  function pwaHow() {
    global.alert(
      'ホーム画面への追加方法\n\n' +
      '【Android / Chrome】\n' +
      '右上の「⋮」→「アプリをインストール」または「ホーム画面に追加」\n\n' +
      '【iPhone / iPad / Safari】\n' +
      '下の「共有」ボタン（□に↑）→「ホーム画面に追加」\n\n' +
      '【パソコン / Chrome・Edge】\n' +
      'アドレス欄の右端に出るインストールのマークを押す\n\n' +
      '追加すると、ブラウザの拡張機能や遮断設定の影響を受けにくくなり、\n' +
      'ログインの窓が開かない問題が起きにくくなります。');
    return Promise.resolve(null);
  }

  /* --- 問い合わせ（V1.35） ---
     宛先はサポート用のGoogleグループ。返信は開発者個人のアドレスからは出さない。
     版とブラウザを本文に入れておく。これが無いと「動きません」だけの報告になり、
     こちらから何往復も聞くことになる。個人を特定する情報は入れない。 */
  var SUPPORT_EMAIL = 'omoidasu-support@googlegroups.com';

  function contactBody() {
    var m = M.state.meta || {};
    var lines = [
      '', '', '----------------------------------------',
      '以下は不具合の調査に使う情報です。消さずに送ってください。',
      '（個人を特定する情報は含まれていません）',
      'アプリ版: ' + (S.APP_BUILD || '不明'),
      'ドライブ同期: ' + (m.drive_last_sync ? '利用中' : '未使用'),
      '画面幅: ' + (global.innerWidth || '?') + 'x' + (global.innerHeight || '?'),
      'ブラウザ: ' + (global.navigator ? global.navigator.userAgent : '不明')
    ];
    return lines.join('\n');
  }

  /* 分類。件名に入れて、こちら側の仕分けをフォーム相当にする。 */
  var CONTACT_KINDS = {
    bug     : '不具合',
    content : '内容の誤り',
    sync    : '同期',
    request : '要望',
    other   : 'その他'
  };

  function openContact() {
    var addr = $('#contact-addr');
    if (addr) { addr.textContent = SUPPORT_EMAIL; }
    var t = $('#contact-text'); if (t) { t.value = ''; }
    var k = $('#contact-kind'); if (k) { k.value = 'bug'; }
    show('#modal-contact');
    global.setTimeout(function () { if (t) { t.focus(); } }, 60);
  }

  function contactText() {
    var k = $('#contact-kind'), t = $('#contact-text');
    var body = (t && t.value ? t.value : '').trim();
    return (body || '（ここに内容をご記入ください）') + contactBody();
  }

  function contactSubject() {
    var k = $('#contact-kind');
    var label = CONTACT_KINDS[k ? k.value : 'other'] || 'その他';
    return '[オモイダス] ' + label;
  }

  function sendContact() {
    var url = 'mailto:' + SUPPORT_EMAIL +
              '?subject=' + encodeURIComponent(contactSubject()) +
              '&body=' + encodeURIComponent(contactText());
    try { global.location.href = url; } catch (e) { /* 下で案内する */ }
    /* メーラーが無い端末では何も起きない。宛先を必ず画面にも出す。 */
    toast('開かないときは［本文をコピー］から手で送ってください', 6000);
  }

  /* クリップボードが使えない環境（古いSafari・非HTTPS）でも詰まないよう、
     失敗したら選択状態にして「手でコピー」できる形に落とす。 */
  function copyContact() {
    var txt = SUPPORT_EMAIL + '\n' + contactSubject() + '\n\n' + contactText();
    var done = function () { toast('コピーしました。メールに貼り付けて送ってください', 4000); };
    if (global.navigator && global.navigator.clipboard && global.navigator.clipboard.writeText) {
      global.navigator.clipboard.writeText(txt).then(done).catch(function () { fallback(txt); });
      return;
    }
    fallback(txt);
    function fallback(s) {
      var t = $('#contact-text');
      if (t) { t.value = s; t.focus(); t.select(); }
      toast('選択しました。長押し（Ctrl+C）でコピーしてください', 5000);
    }
  }

  function supportsNotification() {
    return typeof global.Notification !== 'undefined';
  }

  /* ポモドーロON時に事前に許可を取り、非許可・非対応なら音だけで安全に通知する */
  function requestNotifyPermission() {
    if (!supportsNotification()) { return Promise.resolve(false); }
    if (global.Notification.permission === 'granted') { return Promise.resolve(true); }
    if (global.Notification.permission === 'denied') { return Promise.resolve(false); }
    try {
      var r = global.Notification.requestPermission();
      if (r && typeof r.then === 'function') {
        return r.then(function (p) { return p === 'granted'; }).catch(function () { return false; });
      }
      return Promise.resolve(r === 'granted');
    } catch (e) { return Promise.resolve(false); }
  }

  function notify(title, body) {
    playAlarm();
    if (!supportsNotification() || global.Notification.permission !== 'granted') { return; }
    if (!(M.state.meta && M.state.meta.notify_enabled)) { return; }
    try { new global.Notification(title, { body: body, tag: 'nurse-srs-timer' }); } catch (e) { /* 無視 */ }
  }

  /* 5分休憩／長休憩の共通入口。4セッションごとに長休憩ダイアログを出す。 */
  function startBreak(minutes) {
    var m = parseInt(minutes, 10) || 5;
    st.breakT.minutes = m;
    st.breakT.endsAt = Date.now() + m * 60 * 1000;

    openModal('#modal-break');
    var chip = $('#pomodoro-chip');
    if (chip) { chip.hidden = false; cls(chip, 'is-break', true); }

    global.clearInterval(st.breakT.tick);
    st.breakT.tick = global.setInterval(tickBreak, 250);
    tickBreak();

    return S.getMeta('pomodoro_session_count', 0).then(function (c) {
      return S.setMeta('pomodoro_session_count', (c || 0) + 1);
    });
  }

  function tickBreak() {
    var left = st.breakT.endsAt - Date.now();
    setText('#break-clock', formatClock(Math.max(0, left)));
    setText('#pomodoro-time', formatClock(Math.max(0, left)));
    if (left <= 0) { endBreak(true); }
  }

  function endBreak(natural) {
    global.clearInterval(st.breakT.tick);
    st.breakT.tick = null;
    var chip = $('#pomodoro-chip');
    if (chip) { cls(chip, 'is-break', false); }
    closeModals();

    if (natural) { notify('休憩おわり', '次の25分を始めましょう'); }

    return S.getMeta('pomodoro_session_count', 0).then(function (c) {
      /* 25分×4回達成で長めの休憩を提案する */
      if (natural && c > 0 && c % 4 === 0) { return openLongBreakDialog(); }
      M.startPomodoro();
      return null;
    });
  }

  function openLongBreakDialog() {
    return S.getMeta('pomodoro_longbreak_min', 15).then(function (m) {
      $$('#modal-longbreak .seg-btn[data-lb]').forEach(function (b) {
        cls(b, 'is-active', parseInt(b.getAttribute('data-lb'), 10) === m);
      });
      $('#modal-longbreak').dataset.lb = String(m);
      openModal('#modal-longbreak');
      return m;
    });
  }

  /* ======================================================================
   * 9-2. 解説の書き換え（上書き型メモ）
   *
   * リッチエディタは入力UIが重く、スマホで扱いにくい。
   * 記法方式にして、テキストエリア1つで完結させる。
   * ====================================================================== */

  /* 先に全てエスケープしてから、許可した記法だけをタグへ戻す。
     この順序を逆にすると、書かれたHTMLがそのまま動いてしまう。 */
  function mdLite(src) {
    var s2 = esc(src == null ? '' : String(src));
    s2 = s2.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
    s2 = s2.replace(/==([^=\n]+)==/g, '<mark>$1</mark>');

    var lines = s2.split(/\r?\n/);
    var out = [], inList = false;
    lines.forEach(function (l) {
      var m = l.match(/^\s*[-・*]\s+(.*)$/);
      if (m) {
        if (!inList) { out.push('<ul>'); inList = true; }
        out.push('<li>' + m[1] + '</li>');
        return;
      }
      if (inList) { out.push('</ul>'); inList = false; }
      if (l.trim()) { out.push('<p>' + l + '</p>'); }
    });
    if (inList) { out.push('</ul>'); }
    return out.join('');
  }

  function openMemoEditor(kind, id) {
    var load = (kind === 'question') ? S.getQuestion(id) : S.getAtom(id);
    return load.then(function (rec) {
      if (!rec) { toast('対象が見つかりませんでした'); return null; }
      st.memo = { kind: kind, id: id };

      var label = (kind === 'question')
        ? '全体解説'
        : M.circled(rec.original_num) + ' ' + rec.text;
      setText('#memo-target', label);

      var input = $('#memo-input');
      if (input) { input.value = rec.user_memo || ''; }

      var orig = (kind === 'question') ? rec.overall_explanation : rec.explanation;
      setHtml('#memo-orig-body', M.prepareExplanationHtml(orig || '<p>元の解説はありません</p>'));

      var del = $('#memo-delete');
      if (del) { del.hidden = !rec.user_memo; }

      M.openModal('#modal-memo');
      global.setTimeout(function () { if (input) { input.focus(); } }, 220);
      return rec;
    });
  }

  function saveMemo() {
    if (!st.memo) { return Promise.resolve(); }
    var body = ($('#memo-input') || {}).value || '';
    return S.setMemo(st.memo.kind, st.memo.id, body).then(function () {
      closeModals();
      return refreshCurrentMemo(st.memo.kind, st.memo.id);
    }).then(function () {
      toast(String(($('#memo-input') || {}).value || '').trim()
        ? '書き換えを保存しました' : '元の解説に戻しました', 2600);
    }).catch(function (e) {
      toast('保存できませんでした：' + e.message, 4200);
    });
  }

  function deleteMemo() {
    if (!st.memo) { return Promise.resolve(); }
    var input = $('#memo-input');
    if (input) { input.value = ''; }
    return saveMemo();
  }

  /* 保存後、いま開いている解説画面へ即座に反映する */
  function refreshCurrentMemo(kind, id) {
    var cur = M.state.current;
    if (!cur || !cur.atoms || !cur.atoms.length) { return Promise.resolve(); }
    if (kind === 'atom') {
      return S.getAtom(id).then(function (a) {
        cur.atoms.forEach(function (x, i) {
          if (x.atom_id === id) {
            cur.atoms[i].user_memo = a.user_memo;
            cur.atoms[i].memo_updated_at = a.memo_updated_at;
          }
        });
        M.renderChoiceBlocks();
        return true;
      });
    }
    return S.getQuestion(id).then(function (q) {
      if (cur.question && cur.question.q_id === id) {
        cur.question.user_memo = q.user_memo;
        cur.question.memo_updated_at = q.memo_updated_at;
        /* 描き直さないと、保存したのに画面が変わらない。 */
        M.renderDetailBlock(cur.question);
      }
      return true;
    });
  }

  /* ======================================================================
   * 10. その場ガイド（TIPS）
   *
   * 方針：まとめて教えない。いま押してほしいボタン、または初めて開いた
   *       画面でだけ、1つずつ出す。出したものは二度と出さない。
   *       動線の順に step を振り、「次にどこへ進むか」を必ず1つ示す。
   * ====================================================================== */

  /* ======================================================================
   * 9-3. ホーム最下部：使い方と設計意図を1件ずつ
   * 置き場所は「ツール一覧より下」に限定する。最上部に入れると主動線
   * （本日の復習）が下へ押し下がり、毎日いちばん押すボタンの座標が変わる。
   * 読みたい人だけが下までスクロールしてくる構造にしておく。
   * ====================================================================== */

  /* id は「並び替えても絶対に振り直さない」。
     利用者が書き換えた文は id に紐づいて保存されるので、番号を振り直すと
     その人の文が別の項目に化ける。順序を変えるときは id ごと動かすこと。 */
  var HOME_TIPS = [
    /* ==================================================================
       並び順は「その日に必要な順」。上から順に1件ずつ送られる。
       ① 使い方の中核（何をどう押すか）
       ② 評価4ボタンを押すと次はいつ出るのか
       ③ 仕組みの理解（忘却曲線）
       ④ 各モードの紹介（ホームの並び順に合わせる）
       ⑤ 解説画面の使いこなし
       ⑥ ポモドーロ勉強法
       ⑦ 設定・データ
       ⑧ 製作者から（最後）
       製作者の話を最後に置くのは、初日に読ませても行動が1つも変わらないため。
       初日に必要なのは「何をどう押すか」だけ。
       ================================================================== */

    /* --- ① 使い方の中核 --- */
    { id:'t01', label:'本日の復習',
      title:'このアプリのメイン機能です',
      body:'0件を維持するのが理想です。\n20件以上たまったまま他のモードへ行こうとすると、1日1回だけ引き止めます。' },
    { id:'t02', label:'このアプリの考え方',
      title:'「正解した」と「説明できる」は別物',
      body:'見覚えのある問題文と選択肢というだけで解けてしまう問題があると思います。だからこのアプリは、正誤ではなく「その選択肢の根拠を言えたか」を自分で選ばせます。正解しても根拠を言えなければ、迷わず「難しい」を押してください。そこが伸びしろです。' },
    { id:'t03', label:'このアプリの考え方',
      title:'0.5秒だけ、タップできません',
      body:'問題が出た直後、選択肢は半透明で押せません。すぐ押せると、根拠を思い出す前に指が動いてしまうからです。この0.5秒で「答えを取り出そうとする」ことが、記憶を強くします。短縮する設定はあえて用意していません。' },
    { id:'t04', label:'使い方', title:'「簡単」を押すのは、他人に説明できるときだけ',
      body:'初見で「簡単」を押すと、次の出題は30日後です。そこからさらに「簡単」を重ねると90日・180日と伸びます。うろ覚えのまま簡単は押さないでください。迷ったら「普通」で十分です。' },

    /* --- ② 評価ボタンを押すと、次はいつ出るのか ---
       すべて scheduler.js の nextStepIndex() を読んで書いた事実。
       梯子：10分 → 1時間 → 1日 → 1週間 → 30日 → 90日 → 180日 */
    { id:'t05', label:'評価ボタン：難しい', title:'10分後に再出題',
      body:'いつ押しても必ず10分後に再出題されます。何度押しても10分後のままで、間隔が伸びることはありません。根拠が言えないなら、正解していても迷わずこれ。' },
    { id:'t06', label:'評価ボタン：普通',
      title:'1時間後 →翌日 →1週間に再出題',
      body:'初見なら1時間後。10分後か1時間後の段階なら翌日出題。そこから先は「普通」だけを押し続けても1週間より先へは進みません。1週間の壁を越えるには「簡単」を押す必要があります。' },
    { id:'t07', label:'評価ボタン：簡単', title:'初見で押すと30日後に再出題',
      body:'一度つまずいてから簡単を押した場合は、翌日 →1週間 →30日 →90日 →180日と1段ずつ昇ります。上限は180日です。' },
    { id:'t08', label:'評価ボタン：マスター',
      title:'「二度と見なくていい選択肢」を評価する時',
      body:'30日以上の段階に到達するまで押せません（それまではグレーのまま）。押すと次は半年後。弱点の集計からも外れます。覚悟して押しましょう。' },

    /* --- ③ 仕組みの理解 --- */
    { id:'t09', label:'エビングハウスの忘却曲線 ①',
      title:'長期記憶の最適解！',
      body:'このアプリは復習と定着に強烈にフォーカスしています。エビングハウスの忘却曲線という、長期記憶のために適した復習タイミングを取り入れた設計です。' },
    { id:'t10', label:'エビングハウスの忘却曲線 ②',
      title:'定着度の応じた再出題サイクル',
      body:'「難しい」を選ぶとその日のうちに再出題。「易しい」を選ぶと最短でも翌日まで再出題されません。2度目3度目と「易しい」を選ぶと、どんどん長い期間出題されなくなっていきます。' },
    { id:'t11', label:'エビングハウスの忘却曲線 ③',
      title:'時間になれば定着に適したサイクルで勝手に再出題',
      body:'ランダムモードで学習しているときだけ、期日を過ぎた復習が一定数たまると割り込んできます。本日の復習・弱点ノック・模試・単元別学習の最中は割り込みません。' },
    { id:'t12', label:'エビングハウスの忘却曲線 ④',
      title:'忘却しない自信があれば。',
      body:'一定の条件を満たすと「マスター」という評価ボタンが押せるようになります。これを押すと次の出題は半年後になります。心して押してください。' },

    /* --- ④ 各モード（ホームの並び順に合わせる） --- */
    { id:'t13', label:'ランダムモード',
      title:'復習が終わったら次はここ',
      body:'初見の問題だけが出てきます。単元や大項目でも絞れます。全部解き終えると、このカードは変貌を遂げるとか…？' },
    { id:'t14', label:'テーマ別 弱点ノック',
      title:'スキマ時間用',
      body:'問題それぞれに振り分けられているテーマから苦手分野を分析、苦手な問題をスキマ時間でガンガン解きましょう。' },
    { id:'t15', label:'力試しモード',
      title:'模試です',
      body:'模試＋その分析です。解放されてからのお楽しみ。' },
    { id:'t16', label:'弱点分析',
      title:'5つの見方を切り替えられます',
      body:'単元・大項目・中項目・小項目・テーマの5つで、同じ学習記録を切り替えて見られます。どの見方でも苦手な順に上から並びます。まずは小項目、行き詰まったらテーマで見てください。' },
    { id:'t17', label:'弱点分析',
      title:'行をタップすると、そこだけ出題されます',
      body:'眺めて終わりの画面にはしていません。「テーマ」の行を押すとそのテーマの弱点ノックが、それ以外の行を押すとその範囲の問題が始まります。' },
    { id:'t18', label:'キーワード検索',
      title:'先生、その単語本当に国試出るの？',
      body:'「講義で出てきた単語、そんなの国試に出る？」と思ったら検索してみてください。意外と出るかも。' },
    { id:'t19', label:'マイ★お気に入りノート', title:'用途は自由です',
      body:'アプリ内の解説だけじゃピンと来なかったもの、後で画像を貼り付けたいものなどのマーキング用。用途自由。' },

    /* --- ⑤ 解説画面の使いこなし --- */
    { id:'t20', label:'使い方',
      title:'★(お気に入り)は2種類あります',
      body:'問題まるごとの★（問題文の左上）と、選択肢ひとつだけの★。「この1肢だけが引っかかる」ときは選択肢側に付けてください。どちらもマイ★お気に入りノートに集まります。' },
    { id:'t21', label:'使い方',
      title:'解説を自分の言葉に書き換えよう',
      body:'選択肢の右にある鉛筆から、解説を自分の言葉に置き換えられます。元の解説はいつでも開けます。自分で書いた一言のほうが、本番では確実に出てきます。' },
    { id:'t22', label:'このアプリの考え方', title:'同じテーマを続けて出しません',
      body:'直近30分に解いたテーマは、しばらく出題候補から外れます。同じ話が連続すると、思い出さずに直前の記憶で答えられてしまうためです。' },

    /* --- ⑥ ポモドーロ勉強法 --- */
    { id:'t23', label:'ポモドーロ勉強法 ①',
      title:'持続可能な勉強法',
      body:'25分の集中作業と5分の短い休憩を1セット（1ポモドーロ）として繰り返し、メリハリをつけて学習効率を高める時間管理術です。' },
    { id:'t24', label:'ポモドーロ勉強法 ②',
      title:'こまめな休憩',
      body:'25分×4回（約2時間）を終えると、長めの休憩（15〜30分）を提案します。15分で座って、30分でお風呂・ご飯など調整してください。' },
    { id:'t25', label:'ポモドーロ勉強法 ③',
      title:'寝落ちしないように！',
      body:'休憩時間は目や頭を休めましょう。ベッド・スマホは×。長くとも10分程度・イスに座って仮眠に留めましょう。' },
    { id:'t26', label:'ポモドーロ勉強法 ④',
      title:'邪魔だと思ったら…。',
      body:'機能はOFF/ON出来ます。超集中出来てるのに邪魔くさいと思ったら消してやってください。画面右上の残り時間をタップすると、その場でOFFにできます。' },

    /* --- ⑦ 設定・データ --- */
    { id:'t27', label:'設定 ①', title:'',
      body:'色んな設定があります。テーマの切り替えは画面上部に常に表示してあるので、設定画面までいかないでも大丈夫です。' },
    { id:'t28', label:'設定 ②', title:'',
      body:'夜勉強する方は、少しでも安眠してもらうためにダークモードを推奨しています。' },
    { id:'t29', label:'設定 ③', title:'',
      body:'「7. データ」は、どうしても古い過去問も取り入れたい方や、自分で作問したものを取り入れたい方は使ってください。ただし過去5年より前の過去問は、効率という面で明確に非推奨です。' },
    { id:'t30', label:'使い方',
      title:'問題は自分で足せる',
      body:'スプレッドシートで作った12列のデータを、設定の取り込み欄に貼るだけです。何度取り込んでも、★も評価も書き換えた解説も消えません。' },

    /* --- ⑧ 製作者から（最後） --- */
    { id:'t31', label:'製作者から ①',
      title:'',
      body:'製作者は10年ほど前にとある医療系の国家試験に合格してます。その頃はろくな国家試験対策アプリはありませんでした。' },
    { id:'t32', label:'製作者から ②',
      title:'製作の意図',
      body:'国家試験対策中にほぼ同じ過去問を何十回と目にして無駄な時間を過ごした経験から、このアプリの製作に至りました。' },
    { id:'t33', label:'製作者から ③',
      title:'無駄の無い設計です',
      body:'苦手が分かるのその先、「余裕な問題は出題されない」無駄を省いた効率的なアプリに仕上がったかと思います。' },
    { id:'t34', label:'製作者から', title:'完成はありません',
      body:'このアプリは、使いながら少しずつ直しています。使いにくい所は、直せば直るものとして扱ってください。設定のいちばん下から要望を送れます。' }
  ];

  /* ======================================================================
   * 文言オーバーライド（設定 ＞ 8. 文言の編集）
   *
   * 画面に出る「一言欄」と「ガイド」の文を、利用者が自分で書き換えられる。
   * 保存先は meta の text_overrides（1キーのオブジェクト）。ストアを増やさない
   * のは、バックアップ・復元・全消去がすでに meta ごと丸ごと扱っているため。
   * 新しいストアを足すと、その3経路すべてに追加が要る（DESIGN_DECISIONS 1-3）。
   * ====================================================================== */

  var textOv = null;          /* { id: { text, base, at } } */

  function loadTextOverrides() {
    if (textOv) { return Promise.resolve(textOv); }
    return S.getMeta('text_overrides', {}).then(function (v) {
      textOv = (v && typeof v === 'object') ? v : {};
      return textOv;
    });
  }

  /* 書き換えがあればそれを、無ければ既定文を返す。
     読み込み前に呼ばれても既定文が出るだけで、画面が壊れない。 */
  function ov(id, def) {
    if (!textOv) { return def; }
    var e = textOv[id];
    return (e && typeof e.text === 'string') ? e.text : def;
  }

  /* 既定文が変わったのに、古い既定文をもとに書き換えたままの項目 */
  function ovStale(id, def) {
    var e = textOv && textOv[id];
    return !!(e && typeof e.base === 'string' && e.base !== def);
  }

  function setOverride(id, text, def) {
    return loadTextOverrides().then(function () {
      if (String(text) === String(def)) { delete textOv[id]; }
      else { textOv[id] = { text: String(text), base: String(def), at: Date.now() }; }
      return S.setMeta('text_overrides', textOv);
    });
  }

  function clearOverride(id) {
    return loadTextOverrides().then(function () {
      delete textOv[id];
      return S.setMeta('text_overrides', textOv);
    });
  }

  function clearAllOverrides() {
    textOv = {};
    return S.setMeta('text_overrides', {});
  }

  /* 編集できる文の一覧。id は保存キーそのものなので変えないこと。 */
  function textCatalog() {
    var out = [];
    HOME_TIPS.forEach(function (t, i) {
      out.push({ id: t.id + '.label', group: '一言欄', no: i + 1,
                 name: '見出しラベル', ctx: t.label, def: t.label });
      out.push({ id: t.id + '.title', group: '一言欄', no: i + 1,
                 name: '太字の1行', ctx: t.label, def: t.title || '' });
      out.push({ id: t.id + '.body', group: '一言欄', no: i + 1,
                 name: '本文', ctx: t.label, def: t.body });
    });
    Object.keys(TIPS).forEach(function (k) {
      out.push({ id: 'g.' + k + '.step', group: 'ガイド', no: null,
                 name: '見出し', ctx: k, def: TIPS[k].step || '' });
      out.push({ id: 'g.' + k + '.text', group: 'ガイド', no: null,
                 name: '本文', ctx: k, def: TIPS[k].text || '' });
    });
    return out;
  }

  function renderHomeTips() {
    var box = $('#home-tip');
    if (!box) { return Promise.resolve(null); }
    return loadTextOverrides().then(function () {
      return S.getMeta('home_tip_index', 0);
    }).then(function (i) {
      var n = (isNum(i) ? i : 0) % HOME_TIPS.length;
      var t = HOME_TIPS[n];
      var title = ov(t.id + '.title', t.title || '');
      setText('#home-tip-label', ov(t.id + '.label', t.label));
      /* タイトルは任意。ラベルと同じことを大きい太字でもう一度出さない。 */
      var ttl = $('#home-tip-title');
      if (ttl) {
        ttl.textContent = title;
        ttl.hidden = !title;
      }
      setText('#home-tip-body', ov(t.id + '.body', t.body));
      setText('#home-tip-count', (n + 1) + ' / ' + HOME_TIPS.length);
      box.hidden = false;
      fixHomeTipHeight();
      return n;
    });
  }

  /* --- 高さを実測して固定する ---
     34件は本文の長さがまちまちで、送るたびにカードの丈が変わる。
     固定値をCSSに焼くと、端末幅と文字サイズ設定でかならずズレるので、
     いま表示している幅で34件ぶんを画面外に描いて最大値を採る。
     幅が変わったときだけ測り直す（測定は34回のレイアウトだけ）。 */
  var tipFixedFor = null;

  function fixHomeTipHeight(force) {
    var box = $('#home-tip');
    if (!box || box.hidden) { return null; }
    var w = Math.round(box.getBoundingClientRect().width);
    if (!w) { return null; }
    if (!force && tipFixedFor === w) { return null; }

    var probe = doc.createElement('div');
    probe.className = 'home-tip is-probe';
    probe.style.cssText = 'position:absolute;left:-9999px;top:0;visibility:hidden;' +
                          'min-height:0;width:' + w + 'px;';
    probe.innerHTML = box.innerHTML;
    doc.body.appendChild(probe);

    var pl = probe.querySelector('#home-tip-label') || probe.querySelector('.home-tip-label');
    var pt = probe.querySelector('#home-tip-title') || probe.querySelector('.home-tip-title');
    var pb = probe.querySelector('#home-tip-body') || probe.querySelector('.home-tip-body');
    var max = 0;
    HOME_TIPS.forEach(function (t) {
      var title = ov(t.id + '.title', t.title || '');
      if (pl) { pl.textContent = ov(t.id + '.label', t.label); }
      if (pt) { pt.textContent = title; pt.hidden = !title; }
      if (pb) { pb.textContent = ov(t.id + '.body', t.body); }
      var h = probe.getBoundingClientRect().height;
      if (h > max) { max = h; }
    });
    doc.body.removeChild(probe);

    if (max > 0) {
      box.style.minHeight = Math.ceil(max) + 'px';
      tipFixedFor = w;
    }
    return max;
  }

  /* ホームへ戻るたびに1件送る。手動の [次の話] でも送る。 */
  function advanceHomeTip() {
    return moveHomeTip(1);
  }

  /* 送りすぎたときに戻れるように。34件の環状なので、先頭の [前へ] は末尾へ。 */
  function retreatHomeTip() {
    return moveHomeTip(-1);
  }

  function moveHomeTip(d) {
    var len = HOME_TIPS.length;
    return S.getMeta('home_tip_index', 0).then(function (i) {
      var cur = isNum(i) ? i : 0;
      return S.setMeta('home_tip_index', ((cur + d) % len + len) % len);
    }).then(function () { return renderHomeTips(); });
  }

  var TIPS = {
    /* --- 動線1：解く --- */
    answer:   { step:'1/4 解く',   sel:'#choice-list',
                text:'まずは選択肢をタップして、答えだと思うものを選びます。' },
    confirm:  { step:'2/4 確定',   sel:'#btn-confirm',
                text:'選べたら「解答を確定する」。ここで正誤が出ます。' },
    eval:     { step:'3/4 評価',   sel:'#rv-choices .eval-group',
                text:'<<ここが一番大事>>「答えの根拠を説明できたか」で選びます。' +
                     '記号を覚えたかどうかではありません。',
                place:'below' },
    next:     { step:'4/4 次へ',   sel:'#btn-next',
                text:'保存されるのは、期日が来ている選択肢だけです。' +
                     '触らなければ、点いている評価のまま保存されます。1タップで次へ。' },

    /* --- 動線2：解説画面を、上から順に1つずつ ---
       並び順は画面上の位置と一致させる。
       問題文★（rv-star）は V1.06 まで一度も案内されておらず、
       「問題にも★が付けられる」ことが誰にも伝わっていなかった。 */
    qstar:    { step:'1/6 問題に★',   sel:'#rv-star',
                text:'問題まるごとに★を付けられます。この★は左上、いつでも押せます。' },
    tagpill:  { step:'2/6 テーマ',    sel:'#rv-choices .tag-pill',
                text:'この問題が扱っているテーマです。複数あるときは横に並びます。' +
                     'タップすると、そのテーマのいまの理解度が見られます。' },
    star:     { step:'3/6 選択肢に★', sel:'#rv-choices .cx-star',
                text:'★は選択肢ごとにも付けられます。問題の★とは別物で、' +
                     '「この1肢だけが引っかかる」ときに使います。どちらも★ノートに集まります。' },
    locked:   { step:'期日前の選択肢', sel:'#rv-choices .eval-locked',
                text:'評価ボタンが出ていない選択肢は、まだ次の期日が来ていません。' +
                     '読むだけで、この回は記録しません。' +
                     '思い出せなかったときだけ「忘れていた」を押してください。',
                place:'below' },
    memo:     { step:'4/6 書き換え',  sel:'#rv-choices .cx-memo-btn',
                text:'解説が回りくどいと感じたら、鉛筆から自分の言葉に書き換えられます。' +
                     '元の解説はいつでも開けます。' },
    detail:   { step:'5/6 詳しい解説', sel:'#btn-detail',
                text:'全体解説・比較表・図解はここにまとめてあります。' +
                     '1肢ずつの解説で足りないときに開いてください。' },
    summary:  { step:'6/6 評価の一覧', sel:'#tz-summary',
                text:'4つの丸は各選択肢の評価です。濃い色が自分で選んだもの。タップでその選択肢へ移動します。' },

    /* --- 動線2b：解答画面の残り（その形式に初めて当たったときだけ） --- */
    q_star:   { step:'解答前でも★',  sel:'#q-star',
                text:'この★は解答する前から押せます。' +
                     '「あとで見返したい」と思った瞬間に付けておけます。' },
    stem_expand:{ step:'長い問題文', sel:'#rv-stem-expand',
                text:'問題文が枠に収まらないときは、ここを押すと全文が出ます。' +
                     '問題文カードの高さは固定しているので、操作の位置はずれません。',
                place:'below' },
    img_toggle:{ step:'別冊の画像',  sel:'#btn-img-toggle',
                text:'この問題には画像があります。ここを開くと出ます。' +
                     '画像をタップすればすぐ閉じられます。',
                place:'below' },
    numeric_input:{ step:'計算問題', sel:'#numeric-input',
                text:'計算問題は数値を直接入れます。単位は書かず、数字だけ。' +
                     '小さな丸め誤差は正解として扱います。',
                place:'below' },
    pomodoro: { step:'25分タイマー', sel:'#pomodoro-chip',
                text:'25分たつと休憩をすすめます。ここをタップすると、' +
                     '休憩・延長・OFF が選べます。' },

    /* --- 動線3：ホームの各動線（初めてホームに来たとき順に） --- */
    level:    { step:'いまの位置',   sel:'.level-strip',
                text:'学習日数・連続起動日数・累計解答数と、次の目標までの残りです。' +
                     'この数字は問題を足しても後戻りしません。',
                place:'below' },
    scan:     { step:'分析精度',     sel:'#scan-meter',
                text:'あなたの弱点をどこまで把握できたかの割合です。' +
                     '60問解くと100%になり、そのあとは今日の実績表示に変わります。',
                place:'below' },
    home_tip: { step:'下の一言',     sel:'#home-tip',
                text:'ここに使い方と考え方を1つずつ出しています。' +
                     '［次の話］で送り、［前へ］で戻れます。全34件あります。' },
    /* V1.43：ヘッダーから外したので、案内先を設定のテーマ行へ移す。
       指し先が無いガイドは、吹き出しが画面の隅に出て意味不明になる。 */
    theme:    { step:'見た目を変える', sel:'#set-theme',
                text:'ライト・ダーク・セピアを切り替えます。夜はダークが目に楽です。' },
    settings_btn:{ step:'設定はここ', sel:'#btn-settings',
                text:'設定はこの歯車から。バックアップ、自作データの取り込み、' +
                     '一問一答の出しかた、画面の文言の書き換えもここです。' },
    back:     { step:'戻る',         sel:'#btn-back',
                text:'ひとつ前の画面へ戻ります。学習の途中で戻っても、' +
                     '確定済みの評価は消えません。' },
    home_review: { step:'毎日ここから', sel:'#card-review',
                text:'翌日以降は、まずここ。忘れかけた選択肢だけが、期日順に出てきます。' },
    home_knock:{ step:'苦手つぶし',  sel:'#card-knock',
                text:'苦手なテーマだけを5分・10分で集中演習できます。' },
    home_random:{ step:'新しい問題', sel:'#card-random',
                text:'まだ解いていない問題を増やすときはこちら。単元や大項目でも絞れます。' },
    home_exam:{ step:'力試し',       sel:'#card-exam',
                text:'一定量を解くと模試が解禁されます。いまは解放の進み具合が出ています。' },

    /* --- 動線4：ツール（初めてその画面を開いたとき） --- */
    unit_hero:{ step:'まとめて出す', sel:'#unit-hero',
                text:'この青いボタンは【いま見えている範囲すべて】から出します。' +
                     '下の一覧は、名前を押すと1段深く絞り込み、' +
                     '右の🎲を押すとその範囲でそのまま始まります。' },
    qty:      { step:'出題数',       sel:'#qty-block',
                text:'1回に出す問題数を変えられます。' +
                     '最初は10問だけ、20問以上は一度使ってから開きます。',
                place:'below' },
    rank_weight:{ step:'頻出を優先', sel:'#toggle-rank-weight',
                text:'ONだと、同じ苦手さでも出やすい範囲（Sランク）を先に出します。' +
                     'OFFにすると、出題頻度を無視して純粋に苦手な順になります。',
                place:'below' },
    solve_now:{ step:'その場で解く', sel:'#btn-solve-now',
                text:'検索結果をそのまま演習できます。' +
                     'この演習は復習の予定を変えません。',
                place:'below' },
    unstar:   { step:'★を外す',      sel:'#star-list .star-unmark',
                text:'★はこの一覧から直接外せます。外すとすぐ一覧から消えます。',
                place:'below' },
    dashboard:{ step:'弱点を見る',   sel:'#screen-dashboard .dash-controls',
                text:'苦手な順に上から並びます。単元・大項目・中項目・小項目・テーマの5つに' +
                     '切り替えられます。行をタップすると、その範囲だけを出題します。' },
    search:   { step:'言葉で探す',   sel:'#screen-search .search-bar',
                text:'講義で出た言葉などを入れると、関連する問題をまとめて演習できます。' +
                     'この演習は復習スケジュールを変えません。',
                place:'below' },
    starred:  { step:'★ノート',      sel:'#screen-starred .seg-group',
                text:'★を付けた問題と選択肢がここに集まります。★をタップすれば外せます。',
                place:'below' },
    tree:     { step:'単元別',       sel:'#tree-root',
                text:'赤いバッジは、まだ一度も解いていない選択肢の数です。',
                place:'below' },
    exam:     { step:'模試',         sel:'#exam-list',
                text:'解禁した模試モードは、成績が下がっても二度とロックされません。',
                place:'below' },
    settings: { step:'設定',         sel:'#screen-settings .import-box',
                text:'自作の問題データはここから取り込めます。書き出したバックアップも同じ欄に貼れます。',
                place:'below' },
    ground:   { step:'模試のコツ',   sel:'#choice-list .choice-mark',
                text:'右の☐は「勘ではなく根拠を説明できた」チェック。' +
                     'チェックした肢だけが、正解時に長期記憶へ昇格します。' }
  };

  var tipState = { seen: null, showing: null, queueLock: false };

  function loadTipsSeen() {
    if (tipState.seen) { return Promise.resolve(tipState.seen); }
    return S.getMeta('tips_seen', []).then(function (v) {
      tipState.seen = {};
      (Array.isArray(v) ? v : []).forEach(function (k) { tipState.seen[k] = 1; });
      return tipState.seen;
    });
  }

  /* 1つずつ・初回だけ。すでに何か出ている間は割り込ませない。 */
  function tip(id) {
    var def = TIPS[id];
    if (!def) { return Promise.resolve(false); }
    return loadTextOverrides().then(function () {
      return loadTipsSeen();
    }).then(function (seen) {
      if (seen[id] || tipState.queueLock) { return false; }
      if (tipState.showing === id) { return false; }
      var target = $(def.sel);
      if (!target || target.offsetParent === null) { return false; }

      /* 動線が次へ進んだら、前のガイドは静かに引き継ぐ */
      if (tipState.showing) { tipState.showing = null; }

      tipState.showing = id;
      seen[id] = 1;

      var step = $('#onb-step');
      if (!step) {
        step = doc.createElement('span');
        step.className = 'onb-step';
        step.id = 'onb-step';
        var bubble = $('#onb-bubble');
        bubble.insertBefore(step, bubble.firstChild);
      }
      step.textContent = ov('g.' + id + '.step', def.step || '');

      M.Half2.showCoachMark(def.sel, ov('g.' + id + '.text', def.text), {
        place: def.place, nextLabel: 'わかった', bounce: !!def.bounce
      });
      st.onboard.next = function () { dismissTip(); };

      return S.setMeta('tips_seen', Object.keys(seen)).then(function () { return true; });
    });
  }

  /* 解説画面で出す追加ガイド。基本の4ステップが終わるまでは出さない。
     1問につき1つだけ。詰め込まず、使う順に少しずつ渡す。 */
  /* 画面の上から下へ。読む順序と案内の順序を一致させる。 */
  var REVIEW_EXTRA = ['qstar', 'tagpill', 'star', 'locked', 'memo', 'detail', 'summary'];

  /* 解答画面（第2幕）。基本4つを覚えたあと、1問につき1件だけ渡す。
     画像・計算は「その形式の問題に初めて当たったとき」しか出ない。
     該当する問題を1問も持っていない人には、一生出さないのが正しい。 */
  var ANSWER_EXTRA = ['q_star', 'img_toggle', 'numeric_input', 'pomodoro', 'stem_expand'];

  /* ホーム（第3幕）。上から下へ、画面の並びと同じ順に渡す。 */
  var HOME_EXTRA = ['scan', 'level', 'settings_btn', 'theme', 'back', 'home_tip'];

  function tipAnswerExtra() {
    return loadTipsSeen().then(function (seen) {
      if (!seen.next) { return false; }        /* まず基本操作を覚えてもらう */
      if (tipState.showing) { return false; }
      return ANSWER_EXTRA.filter(function (k) { return !seen[k]; })
        .reduce(function (chain, id) {
          return chain.then(function (shown) { return shown ? true : tip(id); });
        }, Promise.resolve(false));
    });
  }

  function tipHomeExtra() {
    return loadTipsSeen().then(function (seen) {
      if (tipState.showing) { return false; }
      return HOME_EXTRA.filter(function (k) { return !seen[k]; })
        .reduce(function (chain, id) {
          return chain.then(function (shown) { return shown ? true : tip(id); });
        }, Promise.resolve(false));
    });
  }

  function tipReviewExtra() {
    return loadTipsSeen().then(function (seen) {
      if (!seen.next) { return false; }        /* まず基本操作を覚えてもらう */
      if (tipState.showing) { return false; }
      /* 対象が画面に無いガイド（タグが1つも無い問題での「テーマ」など）で
         行列が止まらないよう、出せるものが見つかるまで順に試す。
         先頭1件だけを見る旧実装では、タグ無しの問題が続くと
         以降のガイドが永久に出なくなっていた。 */
      return REVIEW_EXTRA.filter(function (k) { return !seen[k]; })
        .reduce(function (chain, id) {
          return chain.then(function (shown) { return shown ? true : tip(id); });
        }, Promise.resolve(false));
    });
  }

  function dismissTip() {
    tipState.showing = null;
    hideCoachMark();
    st.onboard.next = null;
  }

  /* 吹き出しが出ている間に他の場所を触ったら、そのまま操作させつつ引っ込める。
     読み終わってから「わかった」を押させる手間を強要しない。 */
  function bindTipDismiss() {
    doc.addEventListener('click', function (ev) {
      if (!tipState.showing) { return; }
      if (ev.target.closest && ev.target.closest('#onb-bubble')) { return; }
      dismissTip();
    }, true);
  }

  function resetTips() {
    tipState.seen = null;
    tipState.showing = null;
    return S.setMeta('tips_seen', []).then(function () {
      toast('ガイドをはじめから出すようにしました', 3000);
    });
  }

  /* ======================================================================
   * 11. オンボーディング（第8章）
   * ====================================================================== */

  /* 初回起動時：挨拶も長文説明も挟まず、いきなり問1の解答画面を開く。
     操作は吹き出しで体験させながら覚えさせる（インコンテクスト・ガイド）。 */
  /* 仕様§8-①は「挨拶文や長文説明を一切挟まず、直接問1」だが、
     何のアプリか分からないまま問題が出ると、初回の離脱がむしろ増える。
     妥協点として、3行・5秒で読み切れる量に限って1枚だけ挟む。
     ここに項目を足した瞬間、4-8（一括ツアーは頭に残らない）へ逆戻りする。
     足さないこと。 */
  function showWelcome() {
    return new Promise(function (resolve) {
      openModal('#modal-welcome');
      st.welcomeNext = function () { closeModals(); resolve(true); };
    });
  }

  function startOnboarding(fromStep) {
    return S.countQuestions().then(function (n) {
      if (!n) { toast('先に設定から問題データを取り込んでください', 3600); return null; }

      /* まとめて20問やらせる旧構成をやめ、最初は3問だけ。
         残りは「その場ガイド」が動線に沿って自然に案内する。 */
      st.onboard = { active: true, step: fromStep || 0, phase: 'tutorial', target: 3 };

      M.hooks.afterCommit = function (q, sess) {
        if (!st.onboard.active) { return; }
        st.onboard.step++;
        S.setMeta('tutorial_answered', st.onboard.step).catch(noop);
        if (st.onboard.phase === 'tutorial' && st.onboard.step >= st.onboard.target) {
          global.setTimeout(function () { M.endSession(); finishOnboarding(); }, 260);
        }
        void sess;
      };
      M.hooks.onFinish = function (sess) {
        if (!st.onboard.active) { return false; }
        void sess;
        return true;   /* 既定の終了処理を止め、ツアー側で制御する */
      };

      /* Sランク必修から代表問題を並べる */
      return K.buildQueue({ mode: 'new', count: 12, applyGuard: false, preferFrequent: true })
        .then(function (q) {
          if (!q.questions.length) {
            return K.buildQueue({ mode: 'random', count: 12, applyGuard: false, preferFrequent: true });
          }
          return q;
        })
        .then(function (q) {
          if (!q.questions.length) { toast('出題できる問題がありません'); return null; }
          M.state.session = {
            mode: 'new', sessionId: 'OB' + Date.now().toString(36),
            questions: q.questions, index: 0, answeredCount: 0,
            startedAt: Date.now(), hostQueue: null, hostIndex: 0
          };
          K.Interrupt.endSession();
          return M.go('quiz').then(function () {
            M.renderQuestion();
            /* 最初の吹き出しは part1 が tip('answer') を呼ぶ */
            return st.onboard;
          });
        });
    });
  }

  var INTERLOCK_WAIT = 620;   /* 0.5秒インターロックの解除を待ってから吹き出しを出す */

  /* 対象要素をくり抜いてハイライトし、吹き出しを添える。
     対象が画面外にあるとハイライトも吹き出しも見えなくなるため、
     まず対象を画面内へ送り、描画が落ち着いてから採寸する。 */
  function showCoachMark(targetSel, text, opts) {
    opts = opts || {};
    var layer = $('#onb-layer'), spot = $('#onb-spot'), bubble = $('#onb-bubble');
    if (!layer || !spot || !bubble) { return Promise.resolve(); }

    var target = targetSel ? $(targetSel) : null;
    layer.hidden = false;
    setText('#onb-text', text);
    var nx = $('#onb-next');
    if (nx) { nx.textContent = opts.nextLabel || '次へ'; nx.hidden = !!opts.hideNext; }

    if (!target) {
      spot.style.cssText = 'width:0;height:0;top:50%;left:50%';
      bubble.style.top = '42%'; bubble.style.bottom = 'auto';
      bubble.style.left = '50%'; bubble.style.transform = 'translateX(-50%)';
      cls(bubble, 'is-below', false);
      return Promise.resolve();
    }

    var vh = global.innerHeight, vw = global.innerWidth;
    var r0 = target.getBoundingClientRect();
    var offscreen = (r0.top < 8 || r0.bottom > vh - 8);

    if (offscreen && target.scrollIntoView) {
      target.scrollIntoView({ block: 'center', behavior: 'auto' });
    }

    return new Promise(function (resolve) {
      global.requestAnimationFrame(function () {
        global.requestAnimationFrame(function () {
          place(target, opts, vh, vw);
          resolve();
        });
      });
    });
  }

  function place(target, opts, vh, vw) {
    var spot = $('#onb-spot'), bubble = $('#onb-bubble');
    var b = target.getBoundingClientRect();
    var pad = (opts.pad === undefined) ? 6 : opts.pad;

    spot.style.top = (b.top - pad) + 'px';
    spot.style.left = (b.left - pad) + 'px';
    spot.style.width = (b.width + pad * 2) + 'px';
    spot.style.height = (b.height + pad * 2) + 'px';
    cls(spot, 'is-bounce', !!opts.bounce);

    /* 上下どちらに置くかは、対象の位置と吹き出しの実寸で決める */
    bubble.style.transform = '';
    bubble.style.top = '0px';
    bubble.style.bottom = 'auto';
    var bh = bubble.getBoundingClientRect().height || 120;
    var bw = bubble.getBoundingClientRect().width || 290;

    var below = (opts.place === 'below');
    if (opts.place !== 'above' && opts.place !== 'below') {
      below = (b.bottom + 14 + bh < vh - 12);   /* 下に入るなら下、無理なら上 */
      if (!below && b.top - 14 - bh < 12) { below = true; }
    }

    var top = below ? (b.bottom + 14) : (b.top - 14 - bh);
    /* どちらでも収まらない場合は、画面内に必ず引き戻す */
    top = Math.max(10, Math.min(top, vh - bh - 10));

    bubble.style.top = top + 'px';
    bubble.style.bottom = 'auto';
    bubble.style.left = Math.max(10, Math.min(b.left, vw - bw - 10)) + 'px';
    cls(bubble, 'is-below', below);
  }

  function hideCoachMark() {
    var layer = $('#onb-layer');
    if (layer) { layer.hidden = true; }
  }

  /* --- 撤去：UIツアー（V1.56） ---
     TOUR_STEPS / runUiTour() / promptRandom10() を消した。約90行。

     消した理由は「使っていないから」ではなく、**置き換え済みだから**。
     オンボーディングは「まとめて20問＋ツアーで回る」構成をやめ、
     3問だけ解かせて、あとは動線に沿ってその場ガイド（tip）を
     1件ずつ出す構成になっている。ツアーはその時に役目を終えていたが、
     コードだけが残り、**呼び出し元が1つも無いまま90行が居座っていた**。

     §6-5：UIを撤去したら、それを更新していた関数の呼び出し元も一緒に消える。
     残すと、次に読む人が「どこから呼ばれているのか」を必ず探す。

     meta の ui_tour_done は残す。同期規則（META_OR_KEYS）に載っており、
     消すと端末間で片方だけキーが無い状態になる。値は
     「ツアーを出さない」を意味するので、いまの挙動と矛盾しない。

     ガイドを見直したくなったら、ツアー方式に戻すのではなく
     TIPS（その場ガイド）に足すこと。動線の途中で1件ずつ出すほうが、
     §4-8「その場・その時・1つずつ」に合う。 */

  function finishOnboarding() {
    st.onboard.active = false;
    M.hooks.afterCommit = null;
    M.hooks.onFinish = null;
    hideCoachMark();

    /* --- ここで「消さないでほしい」を要求する（V1.60） ---
       起動直後には呼ばない。Firefox は利用者へ確認を出すので、
       **何も積み上がっていない時点で聞くと、断られて終わる**
       （そして二度と聞けない）。チュートリアルを終えた＝
       この人にとって記録が価値を持ち始めた瞬間に要求する。
       結果は画面に出さない。ここで成否を言っても、まだ意味が伝わらない。
       設定の保存領域欄でいつでも確認・再要求できる。 */
    S.requestPersist().catch(noop);

    /* 2回目以降は全出題数設定（10/20/30/50/120問）を永久解放する */
    return S.setMetaBulk({
      onboarding_done: true,
      tutorial_finished: true,
      ui_tour_done: true,
      random_qty_unlocked: true,
      tutorial_answered: 20
    }).then(function () {
      return K.refreshAll({ recomputeWeakness: true });
    }).then(function () { return M.refreshHome(); })
      .then(function () { return M.go('home', { replace: true }); })
      .then(function () {
        M.fireConfetti();
        return K.getScanAccuracy();
      })
      .then(function (scan) {
        toast('ここまでで分析精度が ' + scan.pct + '% になりました', 4200);
        /* 次に押してほしいボタンを1つだけ案内する */
        return global.setTimeout(function () { tip('home_review'); }, 900);
      });
  }

  /* 中断時のチェックポイント復帰（第8章④） */
  function resumeCheckpoint() {
    return S.loadMeta().then(function (meta) {
      if (meta.onboarding_done || meta.tutorial_finished) { return false; }
      var n = meta.tutorial_answered || 0;
      if (n <= 0) { return false; }
      setText('#resume-n', '問' + (n + 1));
      openModal('#modal-resume');
      return true;
    });
  }

  /* ======================================================================
   * 11. Half2 の差し替え（前半のスタブを実処理で上書き）
   * ====================================================================== */

  var impl = {
    openRandomSelect: openRandomSelect,  startRandom: startRandom,
    startByScope: startByScope,
    renderRandomPick: renderRandomPick,  pickNode: pickNode,  pickBadge: pickBadge,
    maybeShowClearedSheet: maybeShowClearedSheet,
    refreshSyncBadge: refreshSyncBadge,
    openDashboard: openDashboard,        renderDashboard: renderDashboard,
    setPreferFrequent: setPreferFrequent,
    refreshHissuNote: refreshHissuNote, setHissuMode: setHissuMode,
    maybeHissuHint: maybeHissuHint, hissuHintAnswer: hissuHintAnswer,
    hissuDistance: hissuDistance,
    openSearch: openSearch,              runSearch: runSearch,
    startSearchDrill: startSearchDrill,  renderConceptRanking: renderConceptRanking,
    showTop3Popin: showTop3Popin,
    place: place,
    mdLite: mdLite, openMemoEditor: openMemoEditor, saveMemo: saveMemo, deleteMemo: deleteMemo,
    tip: tip, tipReviewExtra: tipReviewExtra,
    tipAnswerExtra: tipAnswerExtra, tipHomeExtra: tipHomeExtra,
    ANSWER_EXTRA: ANSWER_EXTRA, HOME_EXTRA: HOME_EXTRA, REVIEW_EXTRA: REVIEW_EXTRA, dismissTip: dismissTip, resetTips: resetTips, TIPS: TIPS, tipHome: tipHome,
    openTagSheet: openTagSheet,
    openKnockDialog: openKnockDialog,    startKnock: startKnock,
    finishKnock: finishKnock,  abortKnock: abortKnock,
    st: st,                    /* テストから状態を覗くため。本番では触らない。 */
    setAlarmOptionLabel: setAlarmOptionLabel,  FREE_SLOT_LABEL: FREE_SLOT_LABEL,
    openAllClearedSheet: openAllClearedSheet,
    openStarredNote: openStarredNote,    renderStarredNote: renderStarredNote,
    openExamList: openExamList,          startExam: startExam,
    exportReviewCalendar: exportReviewCalendar,
    buildIcs: buildIcs,                  buildPrintSheet: buildPrintSheet,     refreshNoteCount: refreshNoteCount,
    qrSvg: qrSvg,                        printCredit: printCredit,
    noteSheetsFor: noteSheetsFor,        limitNoteItems: limitNoteItems,
    collectNoteItems: collectNoteItems,
    gradeExam: gradeExam,                showExamResult: showExamResult,
    buildReportSheet: buildReportSheet,  runPrintReport: runPrintReport,
    renderConflictList: renderConflictList,  openSyncConflicts: openSyncConflicts,
    buildShareCard: buildShareCard,      shareExamResult: shareExamResult,
    openSettings: openSettings,          runImport: runImport,
    runBackup: runBackup,                runRestore: runRestore,
    refreshStorage: refreshStorage,
    runResetAll: runResetAll,            setDayBoundary: setDayBoundary,
    refreshBackupSize: refreshBackupSize, openResetModal: openResetModal,
    syncBeforeReset: syncBeforeReset,    driveGuardState: driveGuardState,
    fillDaylineOptions: fillDaylineOptions,
    openHelp: openHelp,                  HELP: HELP,
    HELP_COLS: HELP_COLS,
    confirmResetMedium: confirmResetMedium, runResetMedium: runResetMedium,
    mediumLabel: mediumLabel, mediumPath: mediumPath,
    renderHomeTips: renderHomeTips,      advanceHomeTip: advanceHomeTip,
    HOME_TIPS: HOME_TIPS,                showWelcome: showWelcome,
    openOneQSheet: openOneQSheet,        renderOneQ: renderOneQ,
    refreshOneQStat: refreshOneQStat,    runOneQAuto: runOneQAuto,
    runOneQClear: runOneQClear,
    setSplitThreshold: setSplitThreshold, setAlwaysMulti: setAlwaysMulti,
    oneqThreshold: oneqThreshold,
    retreatHomeTip: retreatHomeTip,      moveHomeTip: moveHomeTip,
    fixHomeTipHeight: fixHomeTipHeight,
    loadTextOverrides: loadTextOverrides, textCatalog: textCatalog,
    setOverride: setOverride,            clearOverride: clearOverride,
    clearAllOverrides: clearAllOverrides, ov: ov, ovStale: ovStale,
    openTextEditor: openTextEditor,      renderTextList: renderTextList,
    openTextItem: openTextItem,          saveTextItem: saveTextItem,
    revertTextItem: revertTextItem,      resetAllText: resetAllText,
    restoreSeedQuestions: restoreSeedQuestions, markSeedConsumed: markSeedConsumed,
    buildTextPack: buildTextPack,        importTextPack: importTextPack,
    exportTextPack: exportTextPack,      textUi: textUi,
    startBreak: startBreak,              openLongBreakDialog: openLongBreakDialog,
    requestNotifyPermission: requestNotifyPermission,
    openContact: openContact,        SUPPORT_EMAIL: SUPPORT_EMAIL,
    sendContact: sendContact,        copyContact: copyContact,
    contactText: contactText,        contactSubject: contactSubject,
    CONTACT_KINDS: CONTACT_KINDS,
    setUserImagePos: setUserImagePos,
    refreshDrive: refreshDrive,
    setExamYear: setExamYear,            examDateForYear: examDateForYear,
    examYearOf: examYearOf,              fillExamYears: fillExamYears,
    setExplainMode: setExplainMode,      refreshExplainMode: refreshExplainMode,      saveDriveClientId: saveDriveClientId,
    driveLogin: driveLogin,          driveLogout: driveLogout,
    runAutoSync: runAutoSync,        scheduleAutoSync: scheduleAutoSync,
    syncOnHide      : function () { return runAutoSync('hide'); },
    driveSyncFromSplash: driveSyncFromSplash,
    autoSyncSafeNow: autoSyncSafeNow, initPwaInstall: initPwaInstall,
    pwaInstall: pwaInstall,          pwaHow: pwaHow,
    showBrowserHelp: showBrowserHelp,
    askDriveConsentSync: askDriveConsentSync,
    driveSync: driveSync,
    DRIVE_STEPS: DRIVE_STEPS,
    refreshExamNote: refreshExamNote,
    fmtExamNote: fmtExamNote,
    playAlarm: playAlarm,            playSynthAlarm: playSynthAlarm,
    customAlarmUrl: customAlarmUrl,  refreshAlarmFileNote: refreshAlarmFileNote,
    saveAlarmFile: saveAlarmFile,    deleteAlarmFile: deleteAlarmFile,
    startOnboarding: startOnboarding,    showCoachMark: showCoachMark,
    resumeCheckpoint: resumeCheckpoint,
    /* 後半で追加した処理 */
    resetByMedium: resetByMedium,        endBreak: endBreak,
    hideCoachMark: hideCoachMark,        notify: notify,
    finishOnboarding: finishOnboarding,  launchExam: launchExam,
    state: st
  };

  Object.keys(impl).forEach(function (k) { global.Half2[k] = impl[k]; });
  if (M.Half2 !== global.Half2) {
    Object.keys(impl).forEach(function (k) { M.Half2[k] = impl[k]; });
  }

  /* ======================================================================
   * 12. 後半画面のイベント束ね
   * ====================================================================== */

  function bind() {
    bindTipDismiss();
    /* --- ランダムモード --- */
    on($('#unit-hero'), 'click', function (ev) {
      var f = ev.currentTarget.dataset.field, k = ev.currentTarget.dataset.key;
      startRandom(f ? { field: f, value: k } : null, st.random.count);
    });
    /* 行の左（名前）は掘る、右のサイコロはその場で出す。
       1つのボタンに両方を持たせると、押すたびにどちらが起きるか
       予測できなくなる。 */
    on($('#major-list'), 'click', function (ev) {
      var dice = ev.target.closest('.pick-dice');
      if (dice) {
        startRandom({ field: dice.getAttribute('data-field'),
                      value: dice.getAttribute('data-key') }, st.random.count);
        return;
      }
      var main = ev.target.closest('.pick-main');
      if (!main) { return; }
      var field = main.getAttribute('data-field'), key = main.getAttribute('data-key');
      if (main.getAttribute('data-drill') === '1') {
        st.random.path = (st.random.path || []).concat([key]);
        renderRandomPick();
        return;
      }
      startRandom({ field: field, value: key }, st.random.count);
    });
    on($('#pick-crumb'), 'click', function (ev) {
      var b = ev.target.closest('button[data-up]');
      if (!b) { return; }
      st.random.path = (st.random.path || []).slice(0, parseInt(b.getAttribute('data-up'), 10));
      renderRandomPick();
    });
    on($('#qty-block'), 'click', function (ev) {
      var b = ev.target.closest('.qty-btn');
      if (!b || b.disabled) { return; }
      st.random.count = parseInt(b.getAttribute('data-qty'), 10);
      $$('#qty-block .qty-btn').forEach(function (x) { cls(x, 'is-active', x === b); });
    });


    /* --- ダッシュボード --- */
    on($('.dash-controls'), 'click', function (ev) {
      var b = ev.target.closest('.seg-btn');
      if (!b) { return; }
      if (b.hasAttribute('data-level')) { renderDashboard(b.getAttribute('data-level'), null); }
      if (b.hasAttribute('data-metric')) { renderDashboard(null, b.getAttribute('data-metric')); }
    });
    on($('#toggle-rank-weight'), 'change', function (ev) { setPreferFrequent(ev.target.checked); });

    /* --- 検索 ＆ 概念アナライザー --- */
    var searchTimer = null;
    on($('#search-input'), 'input', function (ev) {
      var v = ev.target.value;
      global.clearTimeout(searchTimer);
      searchTimer = global.setTimeout(function () { runSearch(v); }, 220);
    });
    on($('#search-clear'), 'click', function () {
      var i = $('#search-input');
      if (i) { i.value = ''; }
      runSearch('');
    });
    on($('#btn-solve-now'), 'click', function () { startSearchDrill(); });
    on($('#search-results'), 'click', function (ev) {
      var hit = ev.target.closest('.search-hit');
      if (hit) { startSearchDrill([hit.getAttribute('data-qid')]); }
    });
    /* 弱点分析：テーマの並び順と、行タップの出題 */
    on($('#screen-dashboard'), 'click', function (ev) {
      var seg = ev.target.closest('.seg-btn[data-cfilter]');
      if (seg) { renderConceptRanking(seg.getAttribute('data-cfilter')); return; }
      var crow = ev.target.closest('.concept-row');
      if (crow) { openKnockDialog(crow.getAttribute('data-tag')); return; }
      var brow = ev.target.closest('.bar-row');
      if (brow) {
        startScopeDrill(brow.getAttribute('data-scope-field'),
                        brow.getAttribute('data-scope-value'));
      }
    });

    /* --- ★ノート --- */
    on($('#screen-starred'), 'click', function (ev) {
      var seg = ev.target.closest('.seg-btn[data-sfilter]');
      if (seg) { renderStarredNote(seg.getAttribute('data-sfilter')); return; }
      var un = ev.target.closest('.star-unmark');
      if (!un) { return; }
      ev.stopPropagation();
      var p = (un.getAttribute('data-unstar') === 'question')
        ? S.toggleQuestionStar(un.getAttribute('data-qid'))
        : S.toggleAtomStar(un.getAttribute('data-atom'));
      p.then(function () { return renderStarredNote(); })
       .then(function () { return M.refreshHome(); });
    });

    /* --- 力試し模試 --- */
    on($('#exam-list'), 'click', function (ev) {
      var c = ev.target.closest('.exam-card');
      if (c) { startExam(c.dataset.examId); }
    });
    on($('#warn-study'), 'click', function () { closeModals(); openRandomSelect(); });
    on($('#btn-exam-share'), 'click', function () { shareExamResult(); });
    on($('#warn-go'), 'click', function () {
      var id = st.exam.pendingId;
      closeModals();
      /* 警告のあとも受け方は必ず聞く。ここを飛ばすと、
         警告が出た人だけ本番モード固定になる（V1.50）。 */
      if (id === 'mock_weak') { launchExam(id, EXAM_SIZE[id] || 30); return; }
      askExamStyle(id);
    });

    /* --- 模試の受け方（V1.50） --- */
    on($('#modal-exam-style'), 'click', function (ev) {
      var b = ev.target.closest('[data-exam-style]');
      if (!b) { return; }
      var id = st.exam.pendingStyleId;
      var style = b.getAttribute('data-exam-style');
      closeModals();
      if (!id) { return; }
      launchExam(id, EXAM_SIZE[id] || 30, style);
    });

    /* --- 概念ノック --- */
    on($('#modal-knock-time'), 'click', function (ev) {
      var b = ev.target.closest('[data-knock]');
      if (b) { startKnock(st.knock.tag, parseInt(b.getAttribute('data-knock'), 10)); }
    });
    on($('#modal-top3'), 'click', function (ev) {
      var b = ev.target.closest('.top3-item');
      if (b) { closeModals(); openKnockDialog(b.getAttribute('data-tag')); }
    });

    /* --- 設定 --- */
    on($('#btn-import'), 'click', function () { runImport(($('#import-area') || {}).value); });
    on($('#btn-import-file'), 'click', function () { var f = $('#import-file'); if (f) { f.click(); } });
    on($('#import-file'), 'change', function (ev) {
      var f = ev.target.files && ev.target.files[0];
      if (!f) { return; }
      var fr = new FileReader();
      fr.onload = function () {
        var area = $('#import-area');
        if (area) { area.value = String(fr.result); }
        runImport(String(fr.result));
      };
      fr.readAsText(f);
    });
    on($('#btn-backup'), 'click', function () { runBackup(); });

    /* --- 文言の編集 --- */
    /* --- 一問一答の出しかた --- */
    on($('#btn-oneq'), 'click', function () { openOneQSheet(); });
    on($('#modal-oneq'), 'click', function (ev) {
      var seg = ev.target.closest('.seg-btn[data-oneq]');
      if (seg) { setSplitThreshold(parseInt(seg.getAttribute('data-oneq'), 10)); }
    });
    on($('#set-always-multi'), 'change', function (ev) { setAlwaysMulti(ev.target.checked); });
    on($('#btn-oneq-auto'), 'click', function () { runOneQAuto(); });
    on($('#btn-oneq-clear'), 'click', function () { runOneQClear(); });

    on($('#btn-text-edit'), 'click', function () { openTextEditor(); });
    on($('#text-search'), 'input', function (ev) {
      textUi.q = ev.target.value; renderTextList();
    });
    on($('#screen-text'), 'click', function (ev) {
      var seg = ev.target.closest('.seg-btn[data-tfilter]');
      if (seg) {
        textUi.filter = seg.getAttribute('data-tfilter');
        $$('#screen-text .seg-btn[data-tfilter]').forEach(function (b) {
          cls(b, 'is-active', b === seg);
        });
        renderTextList();
        return;
      }
      var row = ev.target.closest('.text-row');
      if (row) { openTextItem(row.getAttribute('data-tid')); }
    });
    on($('#btn-text-save'), 'click', function () { saveTextItem(); });
    on($('#btn-text-revert'), 'click', function () { revertTextItem(); });
    on($('#btn-text-export'), 'click', function () { exportTextPack(); });
    on($('#btn-text-reset-all'), 'click', function () { resetAllText(); });
    on($('#btn-seed-restore'), 'click', function () { restoreSeedQuestions(); });
    on($('#btn-text-import-file'), 'click', function () {
      var f = $('#text-import-file'); if (f) { f.click(); }
    });
    on($('#text-import-file'), 'change', function (ev) {
      var file = ev.target.files && ev.target.files[0];
      if (!file) { return; }
      var fr = new FileReader();
      fr.onload = function () { importTextPack(fr.result); };
      fr.readAsText(file);
      ev.target.value = '';
    });

    /* --- 一言欄の送り／戻し --- */
    on($('#home-tip-prev'), 'click', function () { retreatHomeTip(); });
    on($('#btn-restore'), 'click', function () { runRestore(); });
    on($('#btn-reset-medium'), 'click', function () { resetByMedium(); });
    on($('#reset-medium-list'), 'click', function (ev) {
      var row = ev.target.closest('.medium-row');
      if (row && !row.disabled) { confirmResetMedium(row.getAttribute('data-medium')); }
    });
    on($('#reset-medium-go'), 'click', function () { runResetMedium(); });
    on($('#nonew-review'), 'click', function () {
      closeModals();
      M.startSession({ mode: 'review' });
    });
    on($('#nonew-knock'), 'click', function () {
      closeModals();
      openKnockDialog();
    });
    on($('#home-tip-next'), 'click', function (ev) {
      ev.stopPropagation();
      advanceHomeTip();
    });
    on($('#welcome-start'), 'click', function () {
      if (typeof st.welcomeNext !== 'function') { closeModals(); return; }
      var f = st.welcomeNext;
      st.welcomeNext = null;
      f();
    });
    on($('#btn-reset-all'), 'click', function () { openResetModal(); });
    on($('#reset-go'), 'click', function () { closeModals(); runResetAll(); });
    on($('#btn-contact'), 'click', function () { openContact(); });
    /* V1.60：保存領域 */
    on($('#btn-persist'), 'click', function () {
      S.requestPersist().then(function (r) {
        if (r.persisted) { toast('学習の記録が消されない設定になりました', 3800); }
        else if (r.supported) {
          /* 断られたことを隠さない。隠すと「押したのに変わらない」になる。 */
          toast('この端末では設定できませんでした。ホーム画面に追加してから'
              + 'もう一度お試しいただくと通ることがあります', 5600);
        } else { toast('この端末はこの設定に対応していません', 3800); }
        return refreshStorage();
      }).catch(noop);
    });

    /* V1.53：ライセンス */
    on($('#lic-apply'), 'click', function () { applyLicense().catch(noop); });
    on($('#lic-buy'), 'click', function () { global.open(M.BUY_URL, '_blank', 'noopener'); });
    on($('#lic-remove'), 'click', function () {
      var L = global.NurseLicense;
      if (!L) { return; }
      L.deactivate().then(function () {
        toast('この端末から鍵を外しました');
        refreshLicense();
        M.refreshFreeGate();
      }).catch(noop);
    });

    on($('#set-onboarding'), 'click', function () {
      resetTips()
        .then(function () { return showWelcome(); })
        .then(function () { return startOnboarding(0); });
    });

    /* ホームへ戻るたびに、未案内の動線を1つだけ出す */
    on(doc, 'click', function (ev) {
      if (!ev.target.closest || !ev.target.closest('[data-action]')) { return; }
      global.setTimeout(function () {
        if (M.state.screen === 'home') { tipHome(); advanceHomeTip().catch(noop); }
      }, 700);
    });
    on($('#set-dayline'), 'change', function (ev) { setDayBoundary(ev.target.value); });
    on($('#set-pomodoro'), 'change', function (ev) {
      var v = ev.target.checked;
      /* ヘッダーの ⏸ / ▶ と同じ経路へ通す。入口が3つあっても結果は1つ。 */
      M.setPomodoroEnabled(v).then(function () {
        return v ? requestNotifyPermission() : false;
      }).then(function (granted) {
        if (v && !granted) { toast('通知は許可されていないため、音のみでお知らせします', 3400); }
      });
    });
    on($('#set-alarm'), 'change', function (ev) {
      S.setMeta('pomodoro_alarm', ev.target.value).then(function () {
        return S.loadMeta();
      }).then(function (m) { M.state.meta = m; playAlarm(ev.target.value); });
    });
    on($('#btn-contact-send'),  'click', function () { sendContact(); });
    on($('#btn-contact-copy'),  'click', function () { copyContact(); });
    on($('#btn-contact-close'), 'click', function () { hide('#modal-contact'); });
    on($('#btn-drive-save-id'), 'click', function () { saveDriveClientId(); });
    on($('#btn-ics'),          'click', function () { exportReviewCalendar(); });
    on($('#btn-note-print'),   'click', function () {
      openModal('#modal-note');
      refreshNoteCount();
    });
    ['#note-kind', '#note-limit', '#note-cols', '#note-explain', '#note-paper'].forEach(function (sel) {
      on($(sel), 'change', function () { refreshNoteCount(); });
    });
    on($('#btn-report-print'), 'click', function () { runPrintReport(); });
    on($('#btn-sync-conflicts'), 'click', function () { openSyncConflicts(); });
    on($('#btn-conflicts-clear'), 'click', function () { conflictClearAll(); });
    on($('#conflict-list'), 'click', function (ev) {
      var c = ev.target.closest('[data-ccopy]');
      if (c) { conflictCopy(Number(c.getAttribute('data-ccopy'))); return; }
      var dl = ev.target.closest('[data-cdel]');
      if (dl) { conflictDismiss(Number(dl.getAttribute('data-cdel'))); }
    });
    on($('#note-go'),          'click', function () { runPrintNote(); });
    on($('#btn-pwa-install'),   'click', function () { pwaInstall(); });
    on($('#btn-pwa-how'),       'click', function () { pwaHow(); });
    on($('#btn-drive-logout'),  'click', function () { driveLogout(); });
    on($('#btn-drive-sync'),    'click', function () { driveSync(); });
    on($('#set-exam-year'), 'change', function (ev) { setExamYear(ev.target.value); });
    on($('#set-hissu'), 'click', function (ev) {
      var b = ev.target.closest ? ev.target.closest('.seg-btn') : null;
      if (b && b.dataset.hissu) { setHissuMode(b.dataset.hissu); }
    });
    on($('#hissu-hint-auto'), 'click', function () { hissuHintAnswer(true); });
    on($('#hissu-hint-keep'), 'click', function () { hissuHintAnswer(false); });
    on($('#set-explain-mode'), 'click', function (ev) {
      var b = ev.target.closest('.seg-btn');
      if (b) { setExplainMode(b.getAttribute('data-explain')); }
    });
    on($('#btn-alarm-pick'), 'click', function () {
      var f = $('#alarm-file'); if (f) { f.value = ''; f.click(); }
    });
    on($('#alarm-file'), 'change', function (ev) {
      var file = ev.target.files && ev.target.files[0];
      if (file) { saveAlarmFile(file); }
    });
    on($('#btn-alarm-test'), 'click', function () {
      playAlarm((M.state.meta && M.state.meta.pomodoro_alarm) || 'chime');
    });
    on($('#btn-alarm-del'), 'click', function () {
      /* 音は入れ直せるので、確認の文面は軽くする。
         ただし「押したら消えた」は同じなので、経路は共通にする。 */
      M.confirmAction({
        title: 'この音を消しますか',
        body: '自分で入れたアラーム音を消します。もう一度使うには入れ直しになります。',
        ok: '消す'
      }).then(function (yes) { if (yes) { deleteAlarmFile(); } }).catch(noop);
    });

    on($('#set-longbreak'), 'change', function (ev) {
      S.setMeta('pomodoro_longbreak_min', parseInt(ev.target.value, 10) || 15);
    });
    on($('#memo-save'), 'click', function () { saveMemo(); });
    on($('#memo-delete'), 'click', function () { deleteMemo(); });
    on($('#set-verdict-popup'), 'change', function (ev) {
      S.setMeta('verdict_popup_enabled', ev.target.checked)
        .then(function () { return S.loadMeta(); })
        .then(function (m) { M.state.meta = m; });
    });
    on($('#modal-tagsheet'), 'click', function (ev) {
      if (ev.target.closest('[data-knock-from-tag]')) {
        var t = $('#modal-tagsheet').dataset.tag;
        closeModals();
        openKnockDialog(t);
      }
    });
    on($('#set-badge'), 'change', function (ev) {
      S.setMeta('badge_enabled', ev.target.checked).then(function () { return S.loadMeta(); })
        .then(function (m) { M.state.meta = m; return S.getDueCount(); })
        .then(function (d) { M.updateAppBadge(ev.target.checked ? d : 0); });
    });
    on($('#set-notify'), 'change', function (ev) {
      if (!ev.target.checked) { return S.setMeta('notify_enabled', false); }
      return requestNotifyPermission().then(function (ok) {
        ev.target.checked = ok;
        if (!ok) { toast('通知が許可されなかったため、アラーム音のみでお知らせします', 3800); }
        return S.setMeta('notify_enabled', ok);
      });
    });
    on($('#screen-settings'), 'click', function (ev) {
      var hb = ev.target.closest('.help-btn');
      if (hb) { ev.stopPropagation(); openHelp(hb.getAttribute('data-help')); return; }
      var b = ev.target.closest('.seg-btn[data-theme-set]');
      if (b) { M.applyTheme(b.getAttribute('data-theme-set')); S.setMeta('theme', b.getAttribute('data-theme-set')); }
    });
    /* 自分で入れた図の表示位置（V1.29）。
       保存先は meta。localStorage にしないのは、バックアップ・復元・
       全消去の3経路から外れて「戻したのに設定だけ違う」が起きるため。 */
    on($('#screen-settings'), 'change', function (ev) {
      var r = ev.target;
      if (!r || r.name !== 'userimgpos' || !r.checked) { return; }
      setUserImagePos(r.value);
    });

    /* --- 休憩・長休憩 --- */
    on($('#break-skip'), 'click', function () { endBreak(false); M.startPomodoro(); });
    on($('#modal-longbreak'), 'click', function (ev) {
      var b = ev.target.closest('.seg-btn[data-lb]');
      if (!b) { return; }
      $$('#modal-longbreak .seg-btn[data-lb]').forEach(function (x) { cls(x, 'is-active', x === b); });
      $('#modal-longbreak').dataset.lb = b.getAttribute('data-lb');
    });
    on($('#lb-start'), 'click', function () {
      var m = parseInt($('#modal-longbreak').dataset.lb, 10) || 15;
      S.setMeta('pomodoro_longbreak_min', m);
      closeModals();
      startBreak(m);
    });

    /* --- オンボーディング --- */
    on($('#onb-next'), 'click', function () {
      hideCoachMark();
      if (typeof st.onboard.next === 'function') {
        var f = st.onboard.next;
        st.onboard.next = null;
        f();
      }
    });
    on($('#onb-skip'), 'click', function () {
      hideCoachMark();
      st.onboard.active = false;
      M.hooks.afterCommit = null;
      M.hooks.onFinish = null;
      S.setMetaBulk({ onboarding_done: true, tutorial_finished: true, random_qty_unlocked: true });
      M.endSession();
      M.go('home', { replace: true }).then(function () { return M.refreshHome(); });
    });
    on($('#resume-continue'), 'click', function () {
      closeModals();
      S.getMeta('tutorial_answered', 0).then(function (n) { startOnboarding(n); });
    });
    on($('#resume-restart'), 'click', function () {
      closeModals();
      S.setMeta('tutorial_answered', 0).then(function () { startOnboarding(0); });
    });

    /* 解答中の吹き出しは、次のガイドが自然に置き換える。
       ここで一律に消すと、直後に出るはずのガイドまで巻き添えで消えていた。 */
  }

  /* ======================================================================
   * 13. 後半モジュールの初期化
   * ====================================================================== */

  /* ホームに来たとき、まだ案内していない動線を1つだけ出す。
     復習が溜まっていれば復習、無ければ新しい問題、という優先順。 */
  /* ホームに戻るたび1件だけ。まず4つのカード（毎日押すもの）を先に配り、
     配り終わってから、周辺（精度・レベル・設定・テーマ・戻る・一言）へ移る。
     順番を逆にすると、初日に「歯車の説明」から始まってしまう。 */
  function tipHome() {
    return S.getDueCount().then(function (due) {
      return due > 0 ? tip('home_review') : tip('home_random');
    }).then(function (shown) { return shown ? true : tip('home_knock'); })
      .then(function (shown) { return shown ? true : tip('home_exam'); })
      .then(function (shown) { return shown ? true : tipHomeExtra(); });
  }

  function init() {
    /* 初回起動判定：履歴も進捗も無ければ、即時体験型チュートリアルを開く。
       途中で閉じていた場合はチェックポイント復帰ダイアログを先に出す。 */
    return Promise.all([S.countLogs(), S.loadMeta(), S.countQuestions()]).then(function (r) {
      var logs = r[0], meta = r[1], totalQ = r[2];

      /* IndexedDB が完全に空なら、同梱シードを1度だけ取り込む。
         データ0件では「問1」が存在せず、初回起動が空白で終わってしまう。 */
      if (!totalQ) {
        if (!global.SEED_QUESTIONS_TSV || meta.seed_imported) { return null; }
        return S.importText(global.SEED_QUESTIONS_TSV)
          .then(function (rep) {
            return S.setMeta('seed_imported', true).then(function () { return rep; });
          })
          .then(function () { return K.refreshAll({ recomputeWeakness: false }); })
          .then(function () { return M.refreshHome(); })
          .then(function () { return route(logs, meta); });
      }
      return route(logs, meta);
    }).then(function (r) {
      renderHomeTips().catch(noop);
      return r;
    }).catch(function (e) { console.error('[part2 init]', e); });

    function route(logs, meta) {
      if (meta.onboarding_done || meta.tutorial_finished) { return null; }
      if (logs > 0 && (meta.tutorial_answered || 0) > 0) { return resumeCheckpoint(); }
      if (logs === 0) {
        return showWelcome().then(function () { return startOnboarding(0); });
      }
      return null;
    }
  }

  /* 束ねは DB に依存しないので、booted を待たずに必ず先に済ませる。
     ここを init() の中に置くと、IndexedDB が使えない環境で
     後半画面のボタンが1つも反応しなくなる（V1.01までの不具合）。 */
  function bindNow() {
    try {
      bind();
      global.__HALF2_BOUND = true;
    } catch (e) {
      console.error('[part2 bind]', e);
    }
  }
  /* 本ファイルも <body> 末尾で読むため、この時点で要素は揃っている。
     DOMContentLoaded を待つと、前半の boot() 失敗ハンドラの方が先に走り、
     「後半は未束ね」と誤って診断されてしまう。 */
  if (doc.getElementById('screen-home')) { bindNow(); }
  else if (doc.readyState === 'loading') { doc.addEventListener('DOMContentLoaded', bindNow); }
  else { bindNow(); }

  /* 初期ルーティング（シード投入・チュートリアル）はDBが要るので booted を待つ */
  if (M.state.booted) { init(); }
  else {
    var wait = global.setInterval(function () {
      if (M.state.booted) { global.clearInterval(wait); init(); }
    }, 60);
    global.setTimeout(function () { global.clearInterval(wait); }, 12000);
  }

  global.Half2Impl = impl;

})(typeof window !== 'undefined' ? window : this);
