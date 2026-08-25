/* ==========================================================================
 * 20260815_main_part1_V1.38.js
 * アプリ本体【前半】：起動 〜 出題 〜 解説 〜 サムゾーン1肢固定ステート
 *
 * 【改版履歴】
 *  V1.00 初版
 *  V1.38 (1) 覆いのフォーカス（V1.64）。開く前にいた場所を覚え、
 *            中の最初の押せるものへ移し、閉じたら元へ戻す。
 *            それまでは位置が覆いの外に残り、Tabで裏の画面をたどれた。
 *        (2) 見出しをそのまま aria-label にする。見出しは差し替わる
 *            ことがあるので、開くたびに読み直す。
 *        (3) Tab を覆いの中で折り返す（軽い閉じ込め）。
 *  V1.37 (1) 更新の受け渡しを作り直した（V1.62）。SKIP_WAITING の直後に
 *            reload していたため、新しい版が主導権を取る前に読み込み直され、
 *            **古い版のまま案内だけが消えていた**（実測で確認）。
 *            リロードは controllerchange で行い、時間切れの保険を置く。
 *        (2) 起動時に待っている版があれば案内し直す。［あとで］を押した人が
 *            次の更新まで古い版に取り残されていた。
 *        (3) 出題中と他の覆いが開いている間は案内を保留し、
 *            片付いてから出す。
 *  V1.36 (1) 保存に失敗したら、覆いを出して手を止めさせる（V1.60）。
 *            トーストだと数秒で消え、**記録が残らなかったことに
 *            気づかないまま解き続ける**ことになる。
 *        (2) 文言は storage.js の describeError に一本化。
 *            「保存に失敗しました：quota」では何も伝わらない。
 *  V1.35 (1) 出題プール分離（V1.56）：力試しカードに
 *            【予想問題 ◯問が待機中】を出す。模試用に取り込んだ問題は
 *            ランダムにも単元学習にも出ないので、どこにも出さないと
 *            「取り込んだのに消えた」と読まれる。
 *        (2) ◀戻るでホームへ帰るときに refreshHome() を呼ぶ。
 *            ホームへ来る経路は3つあるのに、数え直していたのは2つだけで、
 *            戻るで帰ると「解いたのにバッジが減らない」が起きていた。
 *        (3) UIツアーのスタブ（runUiTour）を撤去。後半で実装ごと消した。
 *  V1.35 (旧) 力試しカードに【予想問題 ◯問が待機中】を出す。
 *            模試用に取り込んだ問題はランダムにも単元学習にも出ないので、
 *            どこにも出さないと「取り込んだのに消えた」と読まれる。
 *  V1.34 (1) 取り消せない操作の共通確認（confirmAction）。
 *            個別にモーダルを増やす方式だと、増やし忘れた操作だけが
 *            素通りする。実際「すべて元の文に戻す」「この図を消す」が
 *            1タップで通っていた。入口を1つにした。
 *        (2) Escape で覆いを畳めるようにした（§4-14 の二重の経路）。
 *            背景タップは指なら届くが、PCでは逃げ道が［やめる］1つだった。
 *  V1.33 (1) 買い切りライセンス（アプリ V1.53）。無料枠は 200問。
 *            止めるのは【初見の問題】だけで、復習は鍵が無くても続く。
 *            解いた記録を人質に取らないことを前提にした。取れば
 *            使えるが、その瞬間にこのアプリは信用を失う。
 *        (2) 鍵の照合は refreshHome より前に置く。あとに置くと、
 *            起動直後の1回だけ「使い切りました」が出て次の描画で消える。
 *        (3) 購入ページのURLは BUY_URL 1箇所だけに持つ。文面へ散らすと
 *            販売先を移したときに死んだリンクが残る。
 *  V1.23 (1) 押せるものすべてに立体感（面＋影）を出し、押した瞬間に
 *            1px沈む動きを付けた。押せるかどうかを影の有無だけで
 *            読めるようにするため、押せないレベル欄は影なしのまま据え置く。
 *        (2) 全体解説の書き換えボタンを「✏ 書き換える」に。
 *            28px角のアイコンだけでは押せるものだと気づけない。
 *  V1.22 (1) バッチC-1：自作の図解画像。1問1枚、長辺1200px・JPEG0.72へ縮小して
 *            IndexedDB の user_files に持つ。questions には id だけを置く。
 *            questions は再インポートで丸ごと put し直すストアなので、
 *            画像本体をそこへ入れると取り込みのたびに消える。
 *        (2) 全体解説にも書き換えの入口（✏）を出した。保存の仕組みは
 *            選択肢のメモと同じものが既にあり、入口だけが無かった。
 *        (3) レベル欄を押せない見た目へ（影と枠を外し、背景を一段沈める）。
 *            他のカードと同じ立体感だと押したくなる。
 *        (4) 解説の正誤チップの組版。左の余白が2pxしかなく数字が枠に触れ、
 *            行が続くとチップ同士が縦にも触れていた。
 *  V1.21 (1) ホーム最下部の版表示を消し、カード間の隙間を詰めた（実測で計130px）。
 *            版の文字列は設定のいちばん下に同じものが出ているので、
 *            ホームからは外しても不具合の報告時に困らない。
 *            DOMからは消さない：起動診断が版を読む経路を残すため、
 *            表示だけ止める。
 *  V1.20 (1) ホームの2列レイアウト（V1.19）を撤去し、縦1列へ戻した。
 *            縦幅は「設定をヘッダーの歯車へ移してツール一覧を1行減らす」ほうで詰める。
 *        (2) 設定をヘッダー（テーマ切替の隣）へ移設。どの画面からでも届く。
 *        (3) 解答画面でも、基本4つのあとにガイドを1問1件ずつ渡す（第2幕）。
 *            0.5秒のインターロック中には出さない。押せない理由が2つ重なると
 *            「壊れている」と読まれるため。
 *  V1.19 (1) ホーム画面を、横幅760px以上では2列に組む（PCでスクロールが
 *            要らない高さに収めるため）。実測：1280×720 で内容が986px、
 *            ヘッダー69pxと合わせて約1055px あり、335px はみ出していた。
 *            スマホ幅の並びと寸法は1pxも変えていない。
 *  V1.18 (1) 出題形式の自動選択を追加。本日の復習で「期日の肢が1本だけ」かつ
 *            13列目が分割可の問題は、その1肢だけの一問一答（○×）で出す。
 *            2本以上なら4択のまま。閾値は設定で変えられる。
 *            仕上がった3肢まで毎回考えさせないための分岐で、
 *            期日の肢が2本以上なら問題文1回で2肢ぶんを回収できるので4択が安い。
 *        (2) 一問一答では cur.atoms をその1肢だけに絞る。こうすると
 *            推奨評価・コミット門番・弱点ptの計算経路が4択とまったく同じになり、
 *            一問一答専用の分岐をロジック側に一切作らずに済む。
 *  V1.17 (1) ヘッダーの表示を「今日解いた問題数 ◯ 問」だけにした。
 *            復習の残数は「本日の復習」カードに同じ数が出ている。
 *            同じ数が2箇所にあると、どちらが正なのかを毎回確かめることになる。
 *        (2) 「本日の復習」カードから肩書き（主動線）と説明文を撤去。
 *            タイトルと右上の件数で用が足りる。件数0のときは何も出ないが、
 *            それが「やることが無い」ことの表示になる。
 *        (3) ランダムモードのバッジを、残り1000問以下で残数の表示に切り替えた。
 *            1000問より多いうちは遠すぎて数える意味がないので従来どおり。
 *  V1.16 (1) ポモドーロがモードを跨ぐたびに 25:00 へ巻き戻っていたのを修正。
 *            endSession() が stopPomodoro() を呼び、次の startPomodoro() で
 *            startedAt が現在時刻に置き換わっていた。実測：1.5秒学習して
 *            ホームへ戻り、次のモードを始めると残り時間が 24:58 → 25:00 に戻る。
 *            ホームに長居する使い方ではないので、モードを跨いでも時計は
 *            回り続けるのが正しい。
 *        (2) 代わりに「最後の解答から一定時間なにもしていない」ときだけ
 *            リセットする。出題中でなければ5分、出題中でも25分。
 *            出題中に5分で切らないのは、計算問題を1問5分考えるのが
 *            実際にあり、勉強中のリセットは「休憩が遅れる」だけで済むが、
 *            放置後に即通知が出るほうは時計そのものが信用されなくなるため。
 *        (3) 経過時刻を IndexedDB に保存し、アプリを開き直しても続きから。
 *            再読み込みはモード切替と同じ扱いにする（同じ理由で巻き戻さない）。
 *  V1.15 (1) 期日前の選択肢に評価を書き込まないようにした。
 *            1問を出すと4肢そろって画面に出るため、これまでは「次へ」を
 *            押すだけで、まだ期日でない肢の期日まで書き換わっていた。
 *            実測：10分後の苦手肢が1本あるだけで、残り3肢が
 *            30日 → 90日 → 180日 へ 20分で駆け上がる。
 *            期日前の肢は評価ボタンを出さず、「次回 9/14（あと24日）」と
 *            出して読むだけにする。ボタンを disabled で並べる案は採らない。
 *            押せないボタンが4つ並ぶと、押し忘れたのか押せないのかが
 *            区別できず、毎回同じ迷いが発生するため。
 *        (2) ただし「間違えた」ときは期日前でも降格を記録する。
 *            昇格は「その間隔でも覚えていた」という主張で、間隔を待って
 *            いない以上は根拠が無い。降格は「今忘れている」という直接の
 *            観測なので、いつ取っても正しい。この非対称は意図的。
 *        (3) 正解したが自信が無い肢のために「忘れていた（復習に戻す）」を
 *            1タップで置く。長押しでの解除は採らない（発見できない）。
 *        (4) 門番の対象は「1日以上の段」だけ。10分・1時間の段まで期日で
 *            切ると、早期復習割り込み（第5章②）で答えた結果が1件も
 *            記録されなくなる。割り込みは期日より前に出す仕組みなので、
 *            期日で判定してはいけない。テストで実測して発見した。
 *  V1.14 (1) ランダムモードのカードを3段階で変身させる。
 *            初見が尽きた時点でこのカードは役目を終えるが、位置を空けたり
 *            別モードを勝手に始めたりはしない。押したときに何が起きるかを
 *            常にカード上に書いたまま、中身だけを差し替える。
 *            解禁前の「いじわる模試」を非アクティブの予告として見せる。
 *  V1.13 (1) Level欄の数字だけを太字（800）＋1px大きく表示。
 *  V1.13 (1) Level欄の数字だけを太字（800）＋1px大きく表示。
 *            実測で地の文は10.88px、+1pxの差は約9%で判別は難しい。
 *            効いているのは太さのほうだが、指示どおり両方を適用する。
 *        (2) ポモドーロのON/OFFをヘッダーの専用ボタン（⏸/▶）1タップに。
 *            表示は ON / OFF の文字。⏸/▶ の記号は端末によって色付き絵文字に
 *            化けるため使わない（配色が崩れ、端末差も大きい）。
 *            残り時間チップとは別の当たり判定にして、時間を見るだけの
 *            タップでOFFになる事故を防ぐ。OFF中もチップを薄く残すので、
 *            「不安になった瞬間にONへ戻す」も上部から届く。
 *            ヘッダー・設定のスイッチ・経過シートの3入口を
 *            setPomodoroEnabled() 1本に束ね、挙動の食い違いを構造的に消した。
 *  V1.12 (1) レベル表示を簡素化。
 *  V1.12 (1) レベル表示を簡素化。「Level 2 数量マイルストーン」の肩書きと
 *            散文の説明をやめ、「学習◯日目・連続起動◯日目・累計解答◯問」＋
 *            「残り◯問／目標◯問」の2行に固定した。どのレベルでも同じ形。
 *        (2) 全体解説の組版：文字を 15.2px → 13.4px（選択肢の解説13pxに寄せる）、
 *            行頭の「・」を削除、「①正解：」「②誤り：」を「1.○：」「2.×：」へ。
 *            記号は読む前に意味が取れる。漢字2文字は毎回読ませることになる。
 *        (3) ポモドーロを「どこで始まったか分からない」状態から救出。
 *            初回開始時に1度だけトーストで場所を教え、ヘッダーの時間を
 *            タップしたときのモーダル文言を、残り時間に応じて出し分ける。
 *            旧実装は残り20分でも「25分が経過しました」と嘘をついていた。
 *        (4) 復習が20件以上たまった状態でランダム／単元別／模試へ行こうと
 *            したとき、1日1回だけソフト警告を出す（ブロックはしない）。
 *  V1.11 (1) タグ表示を問題単位の1行へ完全統合。
 *  V1.11 (1) タグ表示を問題単位の1行へ完全統合。全肢のタグを重複除去して
 *            解説の最上部に並べ、肢ごとのインライン表示（cx-tags-inline）を全廃した。
 *            「どの選択肢がどのタグか」は学習の判断に一度も使われておらず、
 *            肢ごとに出すと同じ文字列の反復か、判別に使えない断片のどちらかになる。
 *            V1.09 の「全肢同一なら1回／異なる場合のみ末尾へインライン」は廃止。
 *        (2) Level 2 の説明文を変更。「延べ8問。次の目標は100→300→500→1000問」は
 *            初日の学習者に到達不能な数字を4つ並べるだけで、行動を1つも示さない。
 *            学習日数と、いま見えている次の1段（あと◯問）だけを出す。
 *  V1.01 (1) ファイル名を英数字化。日本語ファイル名は sw.js の
 *            cache.addAll() でパーセントエンコード解釈が環境により割れ、
 *            SW登録失敗＝オフライン動作の全損を招くため。
 *        (2) 後半モジュールが解答フローへ割り込むためのフックを3点追加
 *            （Main.hooks.afterGrade / afterCommit / onFinish）。
 *            力試し模試（解説を挟まず全問回答→一括採点）と
 *            オンボーディング（10問ごとの進行制御）が、
 *            前半のコードを書き換えずに成立するようにするための最小の穴。
 *        (3) Main.stepForward / finishSession を公開
 *  V1.02 (1) ヘッダーのパンくず(#hdr-crumb)を、出題・解説画面でのみ表示。
 *            ホームや設定では各画面の見出しと二重になり、
 *            前の問題のランク・階層が残って誤読を招くため。
 *        (2) 内部用語「アトム」をUI文言から排除（一般学習者向けの表記へ）。
 *        (3) 図解エンジン(mermaid 3.3MB)を <head> の同期読み込みから、
 *            「図解」タブを最初に開いた時だけの遅延読み込みへ変更。
 *            起動時に3.3MBを待たせると、モバイルの初回表示が数秒止まるため。
 *  V1.10 (1) 解説中の <b>…</b> と **…** を重要語句として強調表示。
 *            **…** は取り込み時ではなく描画時に <b> へ変換する。
 *            比較表の中だけは強調を打ち消し、表が赤く染まるのを防ぐ。
 *        (2) 図解エンジンの取得を「ローカル → CDN」の2段構えに。
 *            CDN単独にすると圏外で図解が出ず、完全オフライン要件が崩れる。
 *            vendor/ が欠けていてもCDNで拾えるので手動配置は不要。
 *  V1.09 (1) タグ表示を整理。実データでは4肢すべてが同一タグのため、
 *            肢ごとに1行ずつ出すと同じ文字列を4回繰り返すだけになる。
 *            全肢が同一なら問題単位で1回だけ、異なる場合のみ
 *            解説の末尾へインラインで続ける（改行しない）。
 *        (2) 解説の文字を1段小さくし、下限を12pxに揃えた。
 *  V1.08 (1) 解説画面の情報の重みづけを見直し。選択肢本文は解答時に
 *            すでに読んでいるので一段下げ、主役を解説側へ移した。
 *        (2) 既に「易しい」「マスター」まで到達した肢は、畳まずに
 *            存在感だけ下げる（data-strength）。自力で説明できるか
 *            怪しい肢もあるため、隠さずサッと目視できる状態は保つ。
 *        (3) 解説画面の追加ガイド（評価サマリー・詳しい解説・書き換え・
 *            ★・タグ）が一度も発火していなかったのを修正。
 *  V1.07 (1) 選択肢ごとの解説を、自分の言葉へ書き換えられるようにした（上書き型）。
 *            書き換えると「編集済」を出し、元の解説はいつでも開ける。
 *        (2) トーストが下部の固定バーに重なっていたのを、解説画面では
 *            バーの上へ逃がすよう修正。
 *  V1.06 (1) 選択肢ブロックを2行構成へ圧縮。番号・正誤チップで1行使っていた
 *            のをやめ、「① 本文」→「⇒ 誤り：解説」の形にした。
 *            解説文が持つ「① 誤り：」の丸数字は行頭の番号と重複するため、
 *            ⇒ に置き換えて冗長さを消している。1肢あたり約22px短縮。
 *        (2) 問題文カードを可変高さ（56〜118px）に。短い問題文で余白が
 *            無駄になり、長い問題文が3行目で切れる問題を同時に解消する。
 *        (3) 初心者ガイドを一括ツアーから、その場・その時だけ出す方式へ。
 *            Half2.tip() を要所で呼ぶだけにし、内容は後半モジュールが持つ。
 *  V1.05 (1) 解説画面を全面刷新。タブと肢セレクターを廃止し、
 *            評価ボタンを各選択肢の解説直下へ移した。1肢固定モデルは
 *            残り3肢の評価を隠してしまい「どれをどう評価したか分からない」
 *            という致命的な見落としを生んでいたため。
 *        (2) 正誤を非ブロッキングのポップアップで提示（正解0.6秒／
 *            不正解1.6秒／複数選択2.4秒）。問題文カードには小さな○×を残す。
 *        (3) 評価ボタンの縦位置ズレを修正。align-items:baseline は縦を
 *            「上端」に寄せるため、実測で24px上にずれていた。
 *        (4) 選択肢の右トグルをモード別に。通常＝★／模試＝根拠チェック。
 *        (5) 分析精度は出題中は非表示。100%到達後は「今日◯問」へ差し替え。
 *  V1.04 (1) window.Storage / window.Scheduler がブラウザの組み込みグローバルと
 *            衝突していたため、存在確認だけの依存チェックが常に成功していた。
 *            APP_BUILD の有無で判定するよう厳密化。
 *  V1.03 (1) 【重大】イベント束ねを boot() の Promise チェーンから切り離し、
 *            スクリプト読み込み直後に同期実行するよう変更。
 *            旧構造では bindGlobalEvents() が S.loadMeta() の .then() 内に
 *            あったため、IndexedDB が使えない環境（file:// で直接開く、
 *            プライベートモード、ストレージ拒否）ではリスナーが1つも張られず、
 *            「全ボタンが無反応」になっていた。DOM操作はDBに依存しないので、
 *            束ねは常に先に済ませ、DBが要る処理だけを boot() に残す。
 *        (2) 起動失敗を握りつぶさず、原因と対処を画面に出す診断パネルを追加。
 *        (3) window.__APP_READY / __BOOT_ERROR を公開し、
 *            index.html 側の自己診断スクリプトから状態を参照できるようにした。
 *        (4) 用語統一（案A）：「テーマ別 弱点ノック」
 *            「最優先で埋めたいテーマ TOP 3」
 *
 * 【前半の担当範囲】
 *   1. 起動シーケンス（DB初期化 / テーマ適用 / PWA登録 / App Badging / 起動ダイアログ）
 *   2. 画面ルーティングとホーム画面の描画
 *   3. 出題フェーズ（問題文・選択肢カード・0.5秒 思考インターロック・消去法トグル・数値入力）
 *   4. 採点と解説フェーズ（3ブロック絶対座標固定 / タブ / 比較表 / Mermaid）
 *   5. サムゾーン（肢セレクター・1肢固定ステート・初期点灯・4大評価ボタン・次へ）
 *   6. 評価のコミットと次問遷移（早期復習割り込みの発火・復帰を含む）
 *   7. ポモドーロ 25分カウントダウンと経過モーダルの発火
 *
 * 【後半（20260815_main_後半_V1.00.js）の担当範囲】
 *   分析ダッシュボード / キーワード検索 / 74概念アナライザー / マイ★ノート /
 *   3階層ツリー / ランダム2段階選択 / 力試し模試 / 概念別弱点ノック /
 *   設定・インポート・バックアップ / オンボーディング / 長休憩・通知権限
 *   → 本ファイル末尾の Half2 に、全シグネチャをスタブとして明記してある。
 *
 * 【依存】 window.Storage → window.Scheduler → 本ファイル の順に読み込むこと
 * ========================================================================== */

(function (global) {
  'use strict';

  var S = global.Storage;
  var K = global.Scheduler;

  /* V1.53：購入ページ。販売先を変えたら【ここだけ】直す。
     文面の中にURLを散らすと、移転のたびに死にリンクが残る。 */
  var BUY_URL = 'https://omoidasu-kokushi.github.io/about.html#buy';
  var doc = global.document;

  var APP_BUILD = '20260815_NurseExamApp_V1.00';

  /* 思考インターロック：問題カード表示後、この時間だけ選択肢をタップ不能にする。
     即タップ（勘解答）を封じ、脳に検索練習をさせるための中核仕様。 */
  var INTERLOCK_MS = 500;

  var POMODORO_MS = 25 * 60 * 1000;
  var POMODORO_EXTEND_MS = 10 * 60 * 1000;
  var CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳';

  /* ======================================================================
   * 0. DOM ユーティリティ
   * ====================================================================== */

  function $(sel, root) { return (root || doc).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || doc).querySelectorAll(sel)); }
  function on(el, ev, fn, opts) { if (el) { el.addEventListener(ev, fn, opts || false); } }
  function setText(sel, text) { var el = $(sel); if (el) { el.textContent = text == null ? '' : String(text); } }
  function setHtml(sel, html) { var el = $(sel); if (el) { el.innerHTML = html == null ? '' : html; } }
  function show(sel) { var el = $(sel); if (el) { el.hidden = false; } }
  function hide(sel) { var el = $(sel); if (el) { el.hidden = true; } }
  function toggleClass(el, cls, onFlag) { if (el) { el.classList[onFlag ? 'add' : 'remove'](cls); } }
  function noop() {}

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function circled(n) { return (n >= 1 && n <= CIRCLED.length) ? CIRCLED.charAt(n - 1) : String(n); }

  /* 数字の連なりだけを <b class="lv-n"> で包む。Level欄で数字を目立たせるため。
     setText では実現できないので setHtml を使うが、包む前に必ずエスケープする。
     ここへ外部由来の文字列（問題文など）を通さないこと。 */
  function numHtml(text) {
    return escapeHtml(String(text == null ? '' : text))
      .replace(/\d+/g, '<b class="lv-n">$&</b>');
  }

  var toastTimer = null;
  function toast(message, ms) {
    var el = $('#toast');
    if (!el) { return; }
    setText('#toast-text', message);
    el.hidden = false;
    global.clearTimeout(toastTimer);
    toastTimer = global.setTimeout(function () { el.hidden = true; }, ms || 2600);
  }

  /* ======================================================================
   * 1. アプリ状態
   * ====================================================================== */

  var state = {
    booted: false,
    meta: null,
    screen: 'home',
    screenStack: [],

    /* --- 学習セッション --- */
    session: {
      mode: null,          /* 'new'|'random'|'review'|'tree'|'knock'|'exam'|'search' */
      sessionId: null,
      questions: [],
      index: 0,
      answeredCount: 0,
      startedAt: 0,
      hostQueue: null,     /* 割り込み中に退避した本来のキュー */
      hostIndex: 0
    },

    /* --- 現在の1問 --- */
    current: {
      question: null,
      atoms: [],
      selected: [],        /* original_num の配列 */
      eliminated: {},      /* atom_id -> true（根拠あり／消去完了トグル） */
      graded: false,
      answeredRight: null,
      evals: {},           /* atom_id -> 'hard'|'normal'|'easy'|'master' */
      touched: {},         /* 自分で選び直した肢。推奨のままと区別する */
      lastTouchedEval: null,
      recommendations: null,
      startedAt: 0
    },

    interlock: { timer: null, ready: false },

    pomodoro: {
      enabled: true,
      running: false,
      /* 最後に1問を確定した時刻。無操作リセットの判定に使う。
         「画面を開いていた時間」ではなく「手が動いた時刻」で測る。 */
      lastActiveAt: 0,
      startedAt: 0,
      limitMs: POMODORO_MS,
      tick: null,
      notified: false,
      breakUntil: 0,
      breakTick: null
    },

    mermaidSeq: 0,
    swRegistration: null,
    /* V1.62：更新の受け渡し。
       swReloading      … こちらが頼んだリロードかどうか
       swUpdatePending  … 出題中だったので保留した案内 */
    swReloading: false,
    swUpdatePending: false,
    /* V1.64：覆いのフォーカス。開く前にいた場所と、いま開いているカード。 */
    modalReturnTo: null,
    modalCard: null
  };

  /* ======================================================================
   * 2. 起動
   * ====================================================================== */

  /* DOMの準備を待つ（scriptがbody末尾なら即時実行される） */
  function ready(fn) {
    if (doc.readyState === 'loading') { doc.addEventListener('DOMContentLoaded', fn); }
    else { fn(); }
  }

  /* ----------------------------------------------------------------------
   * イベント束ねは「DBに一切依存しない」ので、boot() より先に必ず済ませる。
   * ここを boot() の .then() に置くと、IndexedDB が使えない環境で
   * リスナーが1本も張られず、画面が完全に無反応になる（V1.02までの不具合）。
   * -------------------------------------------------------------------- */
  var eventsBound = false;
  function bindOnce() {
    if (eventsBound) { return; }
    eventsBound = true;
    try {
      bindGlobalEvents();
      global.__EVENTS_BOUND = true;
    } catch (e) {
      console.error('[bindGlobalEvents]', e);
      global.__BOOT_ERROR = 'イベント登録に失敗しました：' + (e && e.message ? e.message : e);
    }
  }

  function boot() {
    /* 依存モジュールの欠落は、alert ではなく診断パネルで具体的に伝える */
    /* window.Storage / window.Scheduler はブラウザの組み込みグローバルと
       名前が衝突する。存在確認だけでは「読み込めている」と誤判定するので、
       このアプリ固有のプロパティ（APP_BUILD）の有無で判定する。 */
    var hasStorage   = !!(S && S.APP_BUILD && typeof S.ensureInitialized === 'function');
    var hasScheduler = !!(K && K.APP_BUILD && typeof K.buildQueue === 'function');
    if (!hasStorage || !hasScheduler) {
      var lack = [];
      if (!hasStorage) { lack.push('storage.js'); }
      if (!hasScheduler) { lack.push('scheduler.js'); }
      global.__BOOT_ERROR = lack.join(' / ') + ' が読み込まれていません';
      showFatal(
        '必要なファイルが読み込まれていません',
        lack.join(' / ') + ' が見つかりません。',
        'ZIPを展開せずに開いていないか、index.html の <script src="..."> のファイル名が'
        + '実際のファイル名と一致しているかを確認してください。'
      );
      return Promise.reject(new Error(global.__BOOT_ERROR));
    }

    /* DBの成否に関わらず、操作は受け付けられる状態にしておく */
    bindOnce();
    registerServiceWorker();
    applyTheme(doc.documentElement.getAttribute('data-theme') || 'light');

    return S.ensureInitialized()
      .then(function () { return S.loadMeta(); })
      .then(function (meta) {
        state.meta = meta;
        applyTheme(meta.theme || 'light');
        applyVisualTheme(meta.visual_theme || 'challenge');
        state.pomodoro.enabled = meta.pomodoro_enabled !== false;
        /* 開き直しはモード切替と同じ扱い。続きとみなせる間は巻き戻さない。 */
        /* part1 には isNum が無い。part2 のヘルパーを借りずにその場で判定する。 */
        state.pomodoro.startedAt = (typeof meta.pomo_started_at === 'number')
          ? meta.pomo_started_at : 0;
        state.pomodoro.limitMs = (typeof meta.pomo_limit_ms === 'number' && meta.pomo_limit_ms > 0)
          ? meta.pomo_limit_ms : POMODORO_MS;
        state.pomodoro.lastActiveAt = (typeof meta.pomo_last_active === 'number')
          ? meta.pomo_last_active : 0;
        state.pomodoro.notified = !!meta.pomo_notified;
        if (!pomodoroIsFresh()) {
          state.pomodoro.startedAt = 0;
          state.pomodoro.notified = false;
        }
        return bumpOpenStreak(meta);
      })
      .then(function (meta) {
        state.meta = meta;
        /* V1.53：鍵の照合は refreshHome より前。あとにすると、
           起動直後の1回だけ「無料枠を使い切りました」が出て、
           次の描画で消える、という一瞬の嘘が出る。
           照合に失敗しても学習は止めない（未購入として扱うだけ）。 */
        return (global.NurseLicense ? global.NurseLicense.load().catch(noop)
                                    : Promise.resolve(null));
      })
      .then(function () {
        return refreshHome();
      })
      .then(function () {
        state.booted = true;
        global.__APP_READY = true;
        /* スプラッシュを片付けてから起動ダイアログを出す。
           順序を逆にすると、覆いの下でダイアログが開いて
           「押せないボタンがある」状態になる。 */
        return resolveSplash().then(function () { return showBootDialog(); })
          .then(function (r) {
            /* 起動のダイアログが片付いたら、保留していた更新の案内を出す。 */
            if (state.swUpdatePending) {
              global.setTimeout(function () { offerUpdate(); }, 900);
            }
            return r;
          });
      })
      .then(function () {
        /* 起動直後にバックグラウンドで再集計。描画は待たせない。 */
        K.refreshAll({ recomputeWeakness: false })
          .then(function () { return refreshHome(); })
          .catch(noop);

        var H2 = global.Half2Impl;
        if (H2 && H2.initPwaInstall) { try { H2.initPwaInstall(); } catch (e) { /* 続行 */ } }
        return true;
      })
      .catch(function (e) {
        /* 起動に失敗しても覆いは外す。外さないと、
           index.html の自己診断が覆いの下に隠れて読めない。 */
        try { hideSplash(); } catch (e2) { /* 続行 */ }
        console.error('[boot]', e);
        global.__BOOT_ERROR = (e && e.message) ? e.message : String(e);

        /* file:// では IndexedDB も Service Worker も使えない。
           原因と対処を具体名で出す。 */
        var isFile = (global.location && global.location.protocol === 'file:');
        showFatal(
          isFile ? 'ローカルサーバー経由で開いてください' : 'データの保存領域を開けませんでした',
          global.__BOOT_ERROR,
          isFile
            ? 'file:// で直接開くと、ブラウザの制限で保存領域（IndexedDB）と'
              + 'オフライン機能が使えません。フォルダで「python3 -m http.server 8000」を実行し、'
              + 'http://localhost:8000/index.html を開いてください。'
            : 'プライベートブラウズを解除する、別のタブでこのアプリを閉じる、'
              + 'ブラウザのサイトデータ許可を確認する、のいずれかをお試しください。'
        );
        throw e;
      });
  }

  /* 起動不能時に、原因と対処を画面へ出す（コンソールを開かない人にも届かせる）。
     DOMContentLoaded のリスナーは1つ終わるごとにマイクロタスクが流れるため、
     boot() の catch は後半モジュールの束ねより先に走ることがある。
     少し遅らせて、パネルに出す状態が確定してから描画する。 */
  function showFatal(title, detail, remedy) {
    global.setTimeout(function () { showFatalNow(title, detail, remedy); }, 150);
  }

  function showFatalNow(title, detail, remedy) {
    if (typeof global.__showBootDiagnostics === 'function') {
      global.__showBootDiagnostics({ title: title, detail: detail, remedy: remedy });
      return;
    }
    var box = doc.createElement('div');
    box.setAttribute('role', 'alert');
    box.style.cssText = 'position:fixed;z-index:9999;left:12px;right:12px;top:12px;padding:16px 18px;'
      + 'border-radius:14px;background:#18202C;color:#E7EEF7;border:1px solid #FF5568;'
      + 'font:14px/1.7 system-ui,sans-serif;box-shadow:0 10px 40px rgba(0,0,0,.5)';
    box.innerHTML = '<b style="color:#FF5568">' + escapeHtml(title) + '</b><br>'
      + '<span style="opacity:.8;font-size:12px">' + escapeHtml(detail || '') + '</span><br><br>'
      + escapeHtml(remedy || '');
    doc.body.appendChild(box);
  }

  /* 連続起動日数。カレンダー日ではなく日界（既定4:00）基準で数える。
     深夜2時の起動が翌日ぶんに繰り上がると、1日で連続2日になってしまう。
     1.5日ぶんの猶予を見るのは、日界をまたいだ直後の端数を吸収するため。 */
  function bumpOpenStreak(meta) {
    var h = (typeof meta.day_boundary_hour === 'number') ? meta.day_boundary_hour : 4;
    var today = S.util.dayStart(Date.now(), h);
    var last = meta.open_day_last || 0;
    if (last === today) { return Promise.resolve(meta); }
    var cont = last > 0 && (today - last) <= 86400000 * 1.5;
    return S.setMetaBulk({
      open_day_last  : today,
      open_streak    : cont ? (meta.open_streak || 0) + 1 : 1,
      open_days_total: (meta.open_days_total || 0) + 1
    }).then(function () { return S.loadMeta(); })
      .catch(function () { return meta; });
  }

  function applyTheme(theme) {
    doc.documentElement.setAttribute('data-theme', theme);
    var meta = $('meta[name="theme-color"]');
    if (meta) {
      meta.setAttribute('content', theme === 'dark' ? '#0F141C' : theme === 'sepia' ? '#EFE3CE' : '#0FA3B1');
    }
    $$('[data-theme-set]').forEach(function (b) {
      toggleClass(b, 'is-active', b.getAttribute('data-theme-set') === theme);
    });
  }

  function cycleTheme() {
    var order = ['light', 'dark', 'sepia'];
    var cur = doc.documentElement.getAttribute('data-theme') || 'light';
    var next = order[(order.indexOf(cur) + 1) % order.length];
    applyTheme(next);
    return S.setMeta('theme', next);
  }

  function applyVisualTheme(v) {
    doc.documentElement.setAttribute('data-visual', v || 'challenge');
  }

  /* ======================================================================
   * 更新の受け渡し（V1.62で作り直した）
   *
   * 【それまでの壊れ方】
   *   ［更新する］を押すと、SKIP_WAITING を送った**直後に reload()** していた。
   *   新しい Service Worker が有効化して主導権を取るより先にリロードが走るので、
   *   **古い版のまま読み込み直され、案内だけが消える**。
   *   実測で確認：押したあとも controller は古い版、waiting は残ったまま。
   *   利用者は「更新した」と思っているのに、いつまでも古い版を使い続ける。
   *
   * 【直し方】
   *   リロードは controllerchange（主導権が新しい版へ移った合図）で行う。
   *   合図が来ない環境のために、時間切れの保険も置く（§4-14 と同じ考え方で
   *   「必ず先へ進める経路」を二重にする）。
   * ====================================================================== */

  var UPDATE_FALLBACK_MS = 4000;

  function registerServiceWorker() {
    if (!global.navigator || !global.navigator.serviceWorker) { return; }
    var swc = global.navigator.serviceWorker;

    /* 主導権が移ったらリロードする。押した本人の画面だけでなく、
       同じアプリを開いている他のタブもここで揃う。 */
    swc.addEventListener('controllerchange', function () {
      if (!state.swReloading) { return; }   /* こちらが頼んだときだけ従う */
      state.swReloading = false;
      global.location.reload();
    });

    swc.register('./sw.js').then(function (reg) {
      state.swRegistration = reg;

      /* すでに待っている版があるなら案内する。
         これが無いと、［あとで］を押した人や、前回の更新に失敗した人が
         **次の更新が出るまで古い版に取り残される**。

         ただし起動の途中では出さない（保留にする）。起動直後は
         スプラッシュや起動ダイアログが順に開くので、ここで開くと
         **他のダイアログに上書きされて消える**（実際に消えた）。 */
      if (reg.waiting && swc.controller) { state.swUpdatePending = true; }

      reg.addEventListener('updatefound', function () {
        var sw = reg.installing;
        if (!sw) { return; }
        sw.addEventListener('statechange', function () {
          if (sw.state === 'installed' && swc.controller) { offerUpdate(); }
        });
      });
    }).catch(noop);
  }

  /* 出題中には割り込まない。ホームへ戻ったときに出す。
     問題を解いている最中に覆いが出ると、
     ・答えを考えている手が止まる
     ・その場で更新するとリロードで解答中の1問が消える
     の2つが同時に起きる。急ぐ更新ではないので、待てばよい。 */
  function offerUpdate() {
    if (!canShowUpdateNow()) { state.swUpdatePending = true; return; }
    state.swUpdatePending = false;
    openModal('#modal-sw-update');
  }

  /* いま案内を出してよい場面か。
       ・出題中でない … 解いている手を止めない。その場で更新すると
                        リロードで解答中の1問が消える
       ・覆いが開いていない … 開くと相手を上書きして消してしまう
                              （openModal は他のカードを畳むため）
       ・起動が終わっている … 起動の途中はダイアログが順に開く */
  function canShowUpdateNow() {
    if (!state.booted) { return false; }
    if (state.screen === 'quiz') { return false; }
    var layer = $('#modal-layer');
    if (layer && !layer.hidden) { return false; }
    return true;
  }

  function acceptUpdate() {
    closeModals();
    var reg = state.swRegistration;
    if (!reg || !reg.waiting) { global.location.reload(); return; }
    state.swReloading = true;
    reg.waiting.postMessage({ type: 'SKIP_WAITING' });
    /* 合図が来ないまま止まるのがいちばん困る。時間切れで進める。 */
    global.setTimeout(function () {
      if (state.swReloading) { state.swReloading = false; global.location.reload(); }
    }, UPDATE_FALLBACK_MS);
  }

  /* 起動時モーダル（2回目以降・第14章①） */
  /* ======================================================================
   * 起動スプラッシュ（V1.40）
   *
   * 【何のためにあるか】
   *   起動直後は IndexedDB を開いて集計するので、どうしても一瞬止まる。
   *   そこを白いまま見せると「重い」という印象だけが残る。
   *   同じ時間を使って、何をしているかを言葉で見せる。
   *
   * 【ログインを聞く条件を絞っている理由】
   *   毎回の起動で必ず聞くと、利用者自身の要望
   *   「スマホでパッとやるのに毎回ログインが要ると障害になる」
   *   に真っ向から反する。だから聞くのは【聞く意味があるときだけ】。
   *
   *     ・期限内のトークンがある     → 何も聞かず、黙って同期する
   *     ・一度も同期を使っていない   → 何も聞かない（初めての人に
   *                                    Googleログインを先に出すと、
   *                                    まず1問も解かずに離脱する）
   *     ・前に使っていて期限が切れた → ここで初めて2択を出す
   *
   * 【必ず消えること】
   *   覆いは、消えない事故が一番怖い。index.html 側でも6秒の保険を
   *   掛けてあるが、ここでも例外を握りつぶして必ず外す。
   * ====================================================================== */
  var SPLASH_MIN_MS = 700;   /* これ未満だとロゴがチラつくだけになる */
  var splashShownAt = Date.now();
  var splashDone = false;

  function splashSay(t) {
    var el = document.getElementById('splash-status');
    if (el) { el.textContent = t; }
  }

  function hideSplash() {
    if (splashDone) { return Promise.resolve(false); }
    splashDone = true;
    var wait = Math.max(0, SPLASH_MIN_MS - (Date.now() - splashShownAt));
    return new Promise(function (resolve) {
      global.setTimeout(function () {
        var el = document.getElementById('splash');
        if (el) { el.classList.add('is-gone'); }
        resolve(true);
      }, wait);
    });
  }

  function splashAsk() {
    var box = document.getElementById('splash-ask');
    if (!box) { return Promise.resolve('skip'); }
    box.hidden = false;
    /* 状態欄は場所を取るだけなので畳む（空文字にしても高さが残る）。 */
    var stEl = document.getElementById('splash-status');
    if (stEl) { stEl.hidden = true; }
    return new Promise(function (resolve) {
      var done = false;
      var finish = function (v) { if (!done) { done = true; resolve(v); } };
      var lg = document.getElementById('splash-login');
      var sk = document.getElementById('splash-skip');
      /* ログインの窓は【押したその場】でしか開けない。
         ここで await を挟むと、iOS と一部のブラウザが無言で塞ぐ。 */
      if (lg) {
        lg.addEventListener('click', function () {
          if (done) { return; }
          if (stEl) { stEl.hidden = false; }
          splashSay('ログインしています…');
          box.hidden = true;
          var H2 = global.Half2Impl;
          var p = (H2 && H2.driveSyncFromSplash)
                    ? H2.driveSyncFromSplash(splashSay)
                    : Promise.resolve(null);
          p.catch(noop).then(function () { finish('login'); });
        });
      }
      if (sk) {
        sk.addEventListener('click', function () {
          box.hidden = true;
          finish('skip');
        });
      }
    });
  }

  function resolveSplash() {
    var D = global.Drive;
    if (!D) { return hideSplash(); }
    return D.restoreToken().then(function (t) {
      if (t) {
        /* 期限内。聞かずに合わせる。 */
        splashSay('同期しています…');
        return D.autoSync(function (m) { splashSay(m); }).then(function () {
          splashSay('準備できました');
          return hideSplash();
        });
      }
      return Promise.all([D.hasConsent(), D.isConfigured()]).then(function (r) {
        /* 一度も同期を使っていない人には出さない。 */
        if (!r[0] || !r[1]) { return hideSplash(); }
        return splashAsk().then(function () { return hideSplash(); });
      });
    }).catch(function () { return hideSplash(); });
  }

  function showBootDialog() {
    return Promise.all([S.getDueCount(), S.countLogs()]).then(function (r) {
      var due = r[0], logs = r[1];
      if (!logs) { return false; }  /* 履歴なし＝初回。オンボーディングは後半が担当 */

      if (due > 0) {
        setText('#modal-boot-title', '今やれる復習があります！');
        setHtml('#modal-boot-body', '復習待ちが <b>' + due + '</b> 件あります。');
        $('#modal-boot').dataset.action = 'review';
      } else {
        setText('#modal-boot-title', '前回の続きから始めよう！');
        setHtml('#modal-boot-body', '今日の復習は終わっています。ランダムモードで新しい問題に進みますか？');
        $('#modal-boot').dataset.action = 'random';
      }
      openModal('#modal-boot');
      return true;
    });
  }

  /* ======================================================================
   * 3. 画面ルーティング
   * ====================================================================== */

  var SCREEN_TITLE = {
    home: '看護師国家試験 対策',
    quiz: '', random: 'ランダムモード',
    dashboard: 'ダッシュボード', search: 'キーワード検索 ＆ テーマ別 弱点分析',
    starred: 'マイ★お気に入りノート', exam: '力試しモード',
    knock: 'テーマ別 弱点ノック', settings: '設定'
  };

  function go(screen, options) {
    options = options || {};
    if (state.screen && state.screen !== screen && !options.replace) {
      state.screenStack.push(state.screen);
    }
    state.screen = screen;

    /* ホームへ戻ってきたときだけ、少し置いてから自動同期を試す（V1.39）。
       学習中に走らせない理由：同期は台帳を入れ替えて各肢の状態を
       作り直すため、解いている最中だと足元の期日と評価がすり替わる。 */
    if (screen === 'home' && global.Half2Impl && global.Half2Impl.scheduleAutoSync) {
      global.Half2Impl.scheduleAutoSync(8000);
    }

    $$('.screen').forEach(function (el) {
      toggleClass(el, 'is-active', el.getAttribute('data-screen') === screen);
    });

    /* 出題・解説中は分析精度を出さない。集中を妨げるうえ、
       60問到達後は100%固定で情報量がゼロになるため。 */
    toggleClass(doc.body, 'is-quiz', screen === 'quiz');
    updatePomoUi();
    if (screen !== 'quiz') { toggleClass(doc.body, 'is-review', false); }

    var back = $('#btn-back');
    if (back) { back.hidden = (screen === 'home'); }

    /* パンくずは出題・解説画面でのみ出す。
       ホームや設定では各画面の <h2> と二重になるうえ、
       直前に解いた問題のランク・階層コードが残って誤読を生む。 */
    var crumb = $('#hdr-crumb');
    if (screen === 'quiz') {
      if (crumb) { crumb.hidden = false; }
    } else {
      if (crumb) { crumb.hidden = true; }
      setHeaderCrumb(null);
      setText('#hdr-path', SCREEN_TITLE[screen] || '');
    }
    if (global.scrollTo) { global.scrollTo(0, 0); }
    return Promise.resolve(screen);
  }

  function goBack() {
    var prev = state.screenStack.pop() || 'home';
    if (state.screen === 'quiz') { endSession(); }
    return go(prev, { replace: true }).then(function (r) {
      /* --- ◀戻る でホームへ帰るときは数字を取り直す（V1.56） ---
         ホームへ来る経路は3つあるのに、数え直していたのは
         「ホームボタン」と「起動」の2つだけだった。
         ◀戻るで帰ると、いま解いた分が復習バッジにも
         レベルにも反映されないまま古い数字が残る。
         「解いたのに減らない」は不具合として報告される見え方になる。

         描画は待たせない。失敗しても戻る操作そのものは通す。 */
      if (prev === 'home' && state.booted) { refreshHome().catch(noop); }
      return r;
    });
  }

  function setHeaderCrumb(question) {
    var rank = $('#hdr-rank'), code = $('#hdr-code'), path = $('#hdr-path');
    var crumb = $('#hdr-crumb');
    if (!rank || !code || !path) { return; }
    if (!question) {
      rank.hidden = true; code.hidden = true;
      if (crumb) { crumb.hidden = true; }
      return;
    }
    if (crumb) { crumb.hidden = false; }
    rank.hidden = false; code.hidden = false;
    rank.textContent = question.rank;
    rank.className = 'rank-badge ' + question.rank;
    code.textContent = question.num_code || '';
    path.textContent = [question.unit, question.major, question.medium, question.sub_item]
      .filter(Boolean).join(' ＞ ');
  }

  /* ======================================================================
   * 4. ホーム画面
   * ====================================================================== */

  /* --- 逆算プランナー（V1.50） ---
     出すのは1行だけ。数字を2つ以上並べると、また「どれを見ればいいか」に戻る。
     試験日が無いときは何も出さない（設定していない人に余計な行を足さない）。 */
  function renderPlan(plan) {
    var box = $('#home-plan');
    if (!box) { return; }
    if (!plan || !plan.has_exam) { box.hidden = true; return; }

    var main = '', sub = '', tone = '';
    if (plan.pace === 'past') {
      box.hidden = true; return;                     /* 試験が終わった人には出さない */
    } else if (plan.pace === 'done') {
      main = '未学習は残っていません';
      sub  = plan.due > 0 ? ('今日の復習 ' + plan.due + '問') : '今日の復習もありません';
      tone = 'done';
    } else {
      main = '今日はあと ' + plan.today + '問';
      sub  = '新しい問題 ' + plan.need_new + '問 ＋ 復習 ' + plan.due + '問'
           + '　（試験まで ' + plan.rest_days + '日）';
      tone = (plan.pace === 'behind') ? 'behind' : 'ok';
      if (plan.pace === 'behind') {
        /* 間に合わない数字を黙って出さない。届かないことを先に言う。 */
        sub = 'このままでは全部に手が回りません。'
            + 'ランクの高いものから進めるか、試験日を確認してください。'
            + '　（試験まで ' + plan.rest_days + '日）';
      }
    }
    setText('#home-plan-main', main);
    setText('#home-plan-sub', sub);
    box.setAttribute('data-tone', tone);
    box.hidden = false;
  }

  /* いまの無料枠の状態。ライセンスが読めていない環境（license.js が
     欠けている等）では【購入済みと同じ扱い】にする。
     売り物の都合でアプリが使えなくなるのは、いちばんまずい壊れ方。 */
  function licGate(h) {
    var L = global.NurseLicense;
    if (!L) { return { paid: true, locked: false, left: null, limit: null, used: 0 }; }
    return L.gate(h && h.solved_ever);
  }
  function isLocked() { return !!licGate(state.homeState).locked; }

  function renderFreeGate(h) {
    var g = licGate(h);
    var row = $('#free-gate');
    if (!row) { return; }
    if (g.paid) { row.hidden = true; return; }
    row.hidden = false;
    row.setAttribute('data-tone', g.locked ? 'locked' : (g.left <= 30 ? 'near' : 'ok'));
    setText('#free-gate-text', g.locked
      ? '無料でお試しいただける ' + g.limit + '問を解き終えました。復習はこのまま続けられます。'
      : 'お試し中：あと ' + g.left + '問（' + g.used + ' / ' + g.limit + '問）');
  }

  function refreshHome() {
    return K.getHomeState().then(function (h) {
      state.homeState = h;

      /* --- 本日の復習（主動線・LINE風バッジ） --- */
      var badge = $('#review-badge');
      if (badge) {
        if (h.due_count > 0) {
          badge.hidden = false;
          badge.textContent = h.badge_text;   /* DOM は 99+ 文字列 */
          toggleClass(badge, 'is-warm', h.due_count < 10);
        } else {
          badge.hidden = true;
        }
      }
      /* 説明文（#review-sub）は V1.17 で撤去した。件数は右上のバッジが出す。 */

      /* --- 逆算プランナー（V1.50） --- */
      renderPlan(h.plan);

      /* --- 無料枠（V1.53） --- */
      renderFreeGate(h);

      /* 出題中だったので保留していた更新の案内を、ここで出す（V1.62）。
         ホームは「手が空いている」ことが分かる唯一の場所。 */
      if (state.swUpdatePending) {
        global.setTimeout(function () { offerUpdate(); }, 700);
      }

      /* --- レベル ＆ 不退転パーセンテージ --- */
      setHtml('#level-chip', numHtml('Level ' + h.level.level));
      setHtml('#level-pct', numHtml(h.level.display_pct + '%'));
      var bar = $('#level-bar-fill');
      if (bar) { bar.style.width = h.level.display_pct + '%'; }
      setHtml('#level-facts', numHtml(levelFacts(h)));
      setHtml('#level-note', numHtml(h.level.badge ? h.level.badge : levelTargetNote(h.level)));

      /* --- 分析スキャン精度メーター（到達後は今日の学習量へ差し替え） --- */
      refreshScanSlot().catch(noop);

      /* --- サブカード --- */
      setText('#random-badge', randomBadgeText(h));
      var unlockFill = $('#unlock-mini-fill');
      if (unlockFill) { unlockFill.style.width = h.unlock_pct + '%'; }
      /* --- 待機中の予想問題を出す（V1.56） ---
         模試用に取り込んだ問題は、ランダムにも単元学習にも出ない。
         どこにも表示しないと「取り込んだのに消えた」と読まれる。
         解放率より、待っている問題数のほうが情報として強いので、
         待機中があるときはそちらを出す。 */
      var lockedQ = Number(h.mock_locked_questions || 0);
      setText('#exam-tag', lockedQ > 0
        ? ('予想問題 ' + lockedQ + '問が待機中')
        : ('解放 ' + h.unlock_pct + '%'));

      /* --- ビジュアルテーマ --- */
      applyVisualTheme(h.visual_theme);

      /* --- ポモドーロ --- */
      state.pomodoro.enabled = h.pomodoro_enabled;

      /* --- アプリアイコンバッジ（整数厳守） --- */
      updateAppBadge(h.due_count);

      /* --- 概念ノックの対象タグ ＆ ランダムカードの顔 --- */
      return Promise.all([K.getTop3Concepts(), S.getUnlockState()]).then(function (r) {
        var top3 = r[0], unlocks = r[1];
        setText('#knock-tag', top3.length
          ? '最優先：' + top3[0].tag + ' ' + top3[0].score + '%'
          : 'テーマ別 弱点分析と連動');
        var evil = unlocks.filter(function (x) { return x.id === 'mock_weak'; })[0];
        renderRandomCard(h.level && h.level.stats ? h.level.stats.unlearned_atoms : null,
                         !!(evil && evil.unlocked), h.unlearned_questions);
        return h;
      });
    });
  }

  /* 1行目：いま自分が何日続けていて、何問解いたか。
     レベルごとに文体が変わると、毎日見る場所なのに読み方を作り直させる。
     どのレベルでも同じ並びに固定する。 */
  /* ランダムモードのカードは、進行に応じて顔を変える。
     初見が尽きたらこのボタンは死ぬが、位置を空けると主動線の座標が動く。
     また「押したら別のモードが始まる」のは、毎日使うアプリでは不安の種になる。
     位置と『押したら何が起きるか書いてある』ことは保ったまま、中身だけ替える。 */
  /* --- V1.41：カードは2状態だけ ---
     いじわる模試は力試しモードの中にあるので、ホームから独立して
     出す必要がない（同じものへの入口が2つあると、どちらが正か迷う）。
     「全問読破」も、押しても祝いのシートが出るだけの行き止まりだった。
     いまは読破すると【克服モード】という次の行き先に変わる。
     アイコンは隣のカードと被らせない（旗＝力試し、的＝弱点ノック）。 */
  var RANDOM_CARD = {
    random : { icon: 'ico-dice', title: 'ランダムモード', meta: '範囲を選んで出題',
               action: 'go-random' },
    conquer: { icon: 'ico-bolt', title: '克服モード',     meta: '苦手な順に出題',
               action: 'go-random' }
  };

  /* 読破が見えてきたら、残数を数えて出す。
     1000問を超えているうちは数えても遠すぎて意味がないので、
     これまでどおり出題数の設定（10問／全解放）を出す。 */
  var RANDOM_COUNTDOWN_FROM = 1000;

  function isCountdown(left) {
    return (typeof left === 'number' && left > 0 && left <= RANDOM_COUNTDOWN_FROM);
  }

  function randomBadgeText(h) {
    var left = h ? h.unlearned_questions : null;
    if (isCountdown(left)) {
      /* 数字だけを出す。「残り1000」は 320px 幅でカードからはみ出し、
         サイコロのアイコンを押し出してしまった（実測 69px / カード幅89px）。
         何の数かはカード下の説明で受ける。 */
      return String(left);
    }
    return (h && h.random_qty_unlocked) ? '全解放' : '10問';
  }

  function randomCardState(unlearnedAtoms) {
    /* 未学習数が取れないときは、勝手に切り替えない。
       集計が一時的に欠けただけで動線を変えるのが最悪の壊れ方。 */
    if (typeof unlearnedAtoms !== 'number') { return 'random'; }
    return (unlearnedAtoms > 0) ? 'random' : 'conquer';
  }

  function renderRandomCard(unlearnedAtoms, evilUnlocked, unlearnedQuestions) {
    var card = $('#card-random');
    var state = randomCardState(unlearnedAtoms);
    if (!card) { return state; }
    var def = RANDOM_CARD[state];

    card.dataset.state = state;
    card.setAttribute('data-action', def.action);
    var ico = card.querySelector('.sub-icon');
    if (ico) { ico.className = 'sub-icon ' + def.icon; }
    setText('#card-random .sub-title', def.title);
    /* 説明文はここで最終決定する。refreshHome 側でも書くと、
       あとから走るこちらに必ず上書きされて食い違う。 */
    setText('#card-random .sub-meta',
      (state === 'random' && isCountdown(unlearnedQuestions)) ? '未学習の残り' : def.meta);

    var badge = $('#random-badge');
    if (badge) { badge.hidden = (state !== 'random'); }

    var tag = $('#random-tag');
    if (tag) {
      tag.hidden = (state === 'random');
      tag.textContent = '全問に一度は解答ずみ';
    }
    return state;
  }

  function levelFacts(h) {
    var m = state.meta || {};
    var s = (h.level && h.level.stats) || {};
    var parts = [];
    var d = studyDays();
    if (d > 0) { parts.push('学習' + d + '日目'); }
    if (m.open_streak > 0) { parts.push('連続起動' + m.open_streak + '日目'); }
    parts.push('累計解答' + (s.total_answered_questions || 0) + '問');
    return parts.join('　・　');
  }

  /* 2行目：残りいくつで、次の目標がいくつか。
     「100 → 300 → 500 → 1000」と並べても、8問の人には距離しか残らない。
     いま超えられる1段だけを出す。 */
  function levelTargetNote(level) {
    var s = level.stats || {};
    var done, total, unit = '問', i, n;

    switch (level.level) {
      case 1:
        /* 分析スキャンの分母は Math.min(全問題数, 60)。
           60固定にすると、登録が60問未満のデータで永久に達成不能になる。 */
        total = 60;
        if (typeof s.total_questions === 'number' && s.total_questions > 0) {
          total = Math.min(s.total_questions, 60);
        }
        done = s.unique_answered_questions || 0;
        break;
      case 2:
        n = s.total_answered_questions || 0;
        total = LV2_MILESTONES[LV2_MILESTONES.length - 1];
        for (i = 0; i < LV2_MILESTONES.length; i++) {
          if (n < LV2_MILESTONES[i]) { total = LV2_MILESTONES[i]; break; }
        }
        done = n;
        break;
      case 3:
        unit = '肢'; total = s.total_atoms || 0;
        done = total - (s.unlearned_atoms || 0);
        break;
      case 4:
        unit = '肢'; total = s.total_atoms || 0;
        done = total - (s.hard_or_normal_atoms || 0);
        break;
      default:
        unit = '肢'; total = s.total_atoms || 0;
        done = s.mastered_atoms || 0;
        break;
    }

    if (!total) { return ''; }
    var left = Math.max(0, total - done);
    /* 「残り 60問／60問」だけでは、何に対する残りなのかが読み取れない
       （実際に分からないと言われた）。何のための数字かを先に書く。 */
    return left ? ('次のレベルまで　残り ' + left + unit + ' ／ ' + total + unit)
                : ('このレベルは達成（' + total + unit + '）');
  }

  /* Level 2 のマイルストーンは4段あるが、4つ同時に見せると
     「1000問」だけが目に入り、8問の自分との距離しか残らない。
     いま超えられる1段だけを、残り問数つきで出す。 */
  var LV2_MILESTONES = [100, 300, 500, 1000];

  /* 「学習◯日目」はカレンダー日ではなく学習日（日界基準）で数える。
     深夜2時に解いた1問が翌日ぶんに繰り上がると、初日に「2日目」と出てしまう。 */
  function studyDays() {
    var m = state.meta;
    if (!m || !m.created_at) { return 0; }
    var h = (typeof m.day_boundary_hour === 'number') ? m.day_boundary_hour : 4;
    var d0 = S.util.dayStart(m.created_at, h);
    var d1 = S.util.dayStart(Date.now(), h);
    return Math.floor((d1 - d0) / 86400000) + 1;
  }

  /* PWA App Badging：必ず整数を渡す。
     '99+' のような文字列を渡すと setAppBadge が型エラーで落ちるため、
     DOM表示用の文字列とは完全に別経路にしてある。 */
  function updateAppBadge(dueCount) {
    var nav = global.navigator;
    if (!nav) { return; }
    var enabled = !state.meta || state.meta.badge_enabled !== false;
    if (!enabled) { return; }
    var n = Math.min(dueCount | 0, 99);
    try {
      if (n > 0 && typeof nav.setAppBadge === 'function') {
        nav.setAppBadge(n).catch(noop);
      } else if (typeof nav.clearAppBadge === 'function') {
        nav.clearAppBadge().catch(noop);
      }
    } catch (e) { /* 非対応端末では黙って無視する */ }
  }

  /* 分析精度は60問で100%に達したあと一生100%のまま飾りになる。
     到達後は「今日◯問／復習◯」に差し替えて、枠を死なせない。 */
  function refreshScanSlot() {
    return Promise.all([
      K.getScanAccuracy(),
      S.getDailyCount(state.meta ? state.meta.day_boundary_hour : 4)
    ]).then(function (r) {
      var scan = r[0], daily = r[1];
      var meter = $('#scan-meter');
      if (!meter) { return scan; }
      if (scan.complete) {
        meter.classList.add('is-done');
        /* 復習の数はここに出さない。「本日の復習」の巨大カードに
           同じ数が出ているので、同じ情報が2箇所にあると、
           どちらが正なのかを毎回確かめることになる。 */
        setHtml('.scan-label', '今日解いた問題数 <b>' + daily + '</b> 問');
      } else {
        meter.classList.remove('is-done');
        setHtml('.scan-label', '分析精度 <b id="scan-pct">' + scan.pct + '</b>%');
        updateScanMeter(scan, false);
      }
      return scan;
    });
  }

  function updateScanMeter(scan, animate) {
    var fill = $('#scan-fill'), head = $('#scan-head'), meter = $('#scan-meter');
    if (fill) { fill.style.width = scan.pct + '%'; }
    if (head) { head.style.left = scan.pct + '%'; }
    setText('#scan-pct', scan.pct);
    if (meter) {
      meter.setAttribute('aria-valuenow', String(scan.pct));
      if (animate) {
        meter.classList.remove('is-counting');
        void meter.offsetWidth;      /* リフローを強制してアニメーションを再生 */
        meter.classList.add('is-counting');
      }
    }
  }

  /* ======================================================================
   * 5. 学習セッションの開始
   * ====================================================================== */

  /* opts = { mode, count, scope, tag, qIds, shuffle, preferFrequent } */
  function startSession(opts) {
    opts = opts || {};
    var mode = opts.mode || 'random';

    /* V1.53：無料枠を使い切ったら、初見の問題だけを止める。
       復習（mode:'review'）は buildQueue の別経路なので、ここを通らない。
       ＝お金を払わなくても、解いたぶんの復習は最後まで続けられる。 */
    if (isLocked() && mode !== 'review') { opts.solvedOnly = true; }

    return K.buildQueue(opts).then(function (q) {
      if (!q.questions.length) {
        if (q.locked) { return openBuyDialog(); }
        toast(q.reason || '出題できる問題がありません');
        return null;
      }

      K.Interrupt.endSession();   /* モード跨ぎの誤発火を構造的に断つ */

      state.session = {
        mode: mode,
        sessionId: 'S' + Date.now().toString(36),
        questions: q.questions,
        index: 0,
        answeredCount: 0,
        startedAt: Date.now(),
        hostQueue: null,
        hostIndex: 0,
        info: q
      };

      startPomodoro();
      return go('quiz').then(function () {
        renderQuestion();
        return state.session;
      });
    });
  }

  function endSession() {
    /* ここで stopPomodoro() は呼ばない。呼ぶと次の startPomodoro() で
       startedAt が現在時刻に置き換わり、モードを跨ぐたびに 25:00 へ戻る。
       時計はモードを跨いでも回り続け、無操作が続いたときだけ tick が畳む。 */
    savePomodoroState();
    K.Interrupt.endSession();
    global.clearTimeout(state.interlock.timer);

    /* 後半が張ったモード専用のUI（弱点ノックの時計など）を止めさせる。
       畳む前のモードを渡す。ここで渡さないと、後半は何を止めれば
       いいのか分からない。 */
    var was = state.session.mode;
    state.session.mode = null;
    state.session.questions = [];
    state.session.index = 0;
    if (was && typeof hooks.onAbort === 'function') {
      try { hooks.onAbort(was); } catch (e) { console.error('[onAbort]', e); }
    }
  }

  function currentQuestion() {
    var s = state.session;
    return s.questions[s.index] || null;
  }

  /* ======================================================================
   * 6. 出題フェーズ（0.5秒 思考インターロック）
   * ====================================================================== */

  function renderQuestion() {
    var q = currentQuestion();
    if (!q) { return finishSession(); }

    var atoms = (q.atoms || []).slice().sort(function (a, b) {
      return a.original_num - b.original_num;
    });

    /* --- 出題形式を決める。ここで atoms を絞ると、以降の推奨評価・
           コミット門番・弱点ptの経路が4択とまったく同じになる。 --- */
    var fmt = decideFormat(q, atoms);
    if (fmt.format === K.FORMAT.SINGLE && fmt.atom) { atoms = [fmt.atom]; }

    state.current = {
      question: q,
      atoms: atoms,
      format: fmt.format,
      formatReason: fmt.reason,
      selected: [],
      eliminated: {},
      graded: false,
      answeredRight: null,
      evals: {},
      touched: {},
      lastTouchedEval: null,
      recommendations: null,
      startedAt: Date.now(),
      /* --- 反応時間（V1.78・§2-5の約束） ---
         readyAt  … 選択肢が押せるようになった時刻（0.5秒の待ちは含めない）
         firstTapAt … 最初に肢へ触れた時刻。2回目以降は上書きしない */
      readyAt: 0,
      firstTapAt: 0
    };

    var quiz = $('#screen-quiz');
    quiz.setAttribute('data-phase', 'answer');
    toggleClass(doc.body, 'is-review', false);
    toggleClass(quiz, 'is-interrupt', K.Interrupt.status().active);

    setHeaderCrumb(q);

    /* --- メタ行 --- */
    var rank = $('#q-rank');
    if (rank) { rank.textContent = q.rank; rank.className = 'rank-badge ' + q.rank; }
    setText('#q-code', q.num_code || '');
    /* 出典が空なら「AI予想問題」と自動表示する（第3章③） */
    setText('#q-source', (q.source && String(q.source).trim()) ? q.source : 'AI予想問題');
    setText('#q-counter', (state.session.index + 1) + ' / ' + state.session.questions.length);

    /* --- 問題文 ＆ 問題★ --- */
    setText('#q-stem-text', q.stem);
    setStarButton('#q-star', !!q.is_starred);
    setStarButton('#rv-star', !!q.is_starred);

    /* --- 画像アコーディオン --- */
    renderImageAccordion(q);

    /* --- 選択肢 or 数値入力 --- */
    if (q.question_type === 'numeric') {
      renderNumericInput(q);
    } else if (fmt.format === K.FORMAT.SINGLE) {
      renderSingleChoice(atoms[0], q);
    } else {
      renderChoices(atoms, q);
    }

    /* --- 割り込みバー --- */
    renderInterruptBar();

    var btn = $('#btn-confirm');
    if (btn) { btn.disabled = true; btn.textContent = '解答を確定する'; }

    armInterlock();
    /* ガイドは「今それを押してほしい瞬間」にだけ出す */
    global.setTimeout(function () { Half2.tip('answer'); }, INTERLOCK_MS + 140);
    /* 基本4つを覚えたあとは、解答画面でも1問1件ずつ渡していく。
       0.5秒のインターロック中に吹き出しを出すと、押せない理由が
       2つ重なって「壊れている」と読まれる。必ず解除後に出す。 */
    global.setTimeout(function () { Half2.tipAnswerExtra(); }, INTERLOCK_MS + 1500);
  }

  function renderImageAccordion(q) {
    var wrap = $('#q-image-wrap');
    if (!wrap) { return; }
    if (!q.image_url) { wrap.hidden = true; return; }
    wrap.hidden = false;
    var img = $('#q-image');
    if (img) { img.src = q.image_url; img.alt = '別冊画像'; }
    var panel = $('#q-image-panel');
    if (panel) { panel.hidden = true; }
    var t = $('#btn-img-toggle');
    if (t) { t.setAttribute('aria-expanded', 'false'); }
  }

  /* 当たり判定は「中央＝選択」「右＝トグル」の2つだけ。
     左の番号は表示専用にして、誤タップの源を1つ減らす。
     右トグルの役割はモードで変える：
       通常モード ＝ ★（解答前から付けられる）
       力試し模試 ＝ 根拠あり（消去完了）チェック */
  function isExamMode() { return state.session.mode === 'exam'; }

  /* 一問一答にできるのは「本日の復習」だけ。ほかのモードは
     期日という概念が無い（新規・ランダム）か、4択で解くこと自体が
     目的（模試）なので、形式を変える理由がない。 */
  var SPLIT_MODES = ['review'];

  function decideFormat(q, atoms) {
    var meta = state.meta || {};
    var mode = state.session.mode;
    if (SPLIT_MODES.indexOf(mode) < 0) {
      return { format: K.FORMAT.MULTI, reason: 'mode', atom: null };
    }
    var dueIds = q.due_atom_ids || [];
    var d = K.pickFormat(q, dueIds, {
      threshold: (typeof meta.split_threshold === 'number') ? meta.split_threshold : 2,
      alwaysMulti: meta.always_multi === true
    });
    if (d.format !== K.FORMAT.SINGLE) { return { format: d.format, reason: d.reason, atom: null }; }
    var target = atoms.filter(function (a) { return dueIds.indexOf(a.atom_id) >= 0; })[0];
    /* 対象が引けなかったら黙って4択へ戻す。1肢も出せないほうが事故。 */
    if (!target) { return { format: K.FORMAT.MULTI, reason: 'atom-missing', atom: null }; }
    return { format: K.FORMAT.SINGLE, reason: d.reason, atom: target };
  }

  /* ○×の2枚だけを出す。○ には対象肢の番号、× には -1 を持たせ、
     確定時に -1 を捨てることで「選ばなかった」と同じ形にする。
     こうすると採点・評価の経路を4択と共通にできる。 */
  function renderSingleChoice(atom, q) {
    hide('#numeric-wrap');
    show('#choice-list');
    setText('#q-instruction', 'この選択肢は正しいですか？');
    setHtml('#choice-list',
      '<li class="single-stmt"><span class="single-num">' + circled(atom.original_num) + '</span>' +
      '<span class="single-text">' + escapeHtml(atom.text) + '</span></li>' +
      '<li class="choice-card is-ox" data-atom-id="' + escapeHtml(atom.atom_id) +
      '" data-num="' + atom.original_num + '">' +
      '<button type="button" class="choice-body"><span class="choice-text ox-mark">○ 正しい</span></button></li>' +
      '<li class="choice-card is-ox" data-atom-id="' + escapeHtml(atom.atom_id) +
      '" data-num="-1">' +
      '<button type="button" class="choice-body"><span class="choice-text ox-mark">× 誤り</span></button></li>');
  }

  function renderChoices(atoms, q) {
    hide('#numeric-wrap');
    show('#choice-list');
    setText('#q-instruction', q.question_type === 'multiple'
      ? '選択肢を ' + (q.select_count || 2) + ' つ選んでください。'
      : '選択肢を1つ選んでください。');

    var exam = isExamMode();
    var html = atoms.map(function (a) {
      var mark = exam
        ? '<button type="button" class="choice-mark" data-kind="ground" aria-pressed="false"' +
          ' aria-label="根拠を説明できた（消去完了）">☐</button>'
        : '<button type="button" class="choice-mark" data-kind="star" aria-pressed="' +
          (a.is_starred ? 'true' : 'false') + '" aria-label="この選択肢に★を付ける">' +
          (a.is_starred ? '★' : '☆') + '</button>';
      return '<li class="choice-card" data-atom-id="' + escapeHtml(a.atom_id) + '" data-num="' + a.original_num + '">' +
             '<span class="choice-num">' + a.original_num + '</span>' +
             '<button type="button" class="choice-body">' +
             '<span class="choice-text">' + escapeHtml(a.text) + '</span>' +
             '</button>' + mark + '</li>';
    }).join('');
    setHtml('#choice-list', html);

    /* 模試の根拠チェックは、言われないと気づかれない。初回だけ使い方を出す。 */
    var old = $('.ground-hint');
    if (old) { old.parentNode.removeChild(old); }
    if (exam && !state.groundHintShown) {
      state.groundHintShown = true;
      var hint = doc.createElement('p');
      hint.className = 'ground-hint';
      hint.innerHTML = '右の <b>☐</b> は「勘ではなく根拠を説明できた」チェックです。' +
                       'チェックした肢だけが、正解時に長期記憶へ昇格します。';
      var list = $('#choice-list');
      list.parentNode.insertBefore(hint, list);
    }
  }

  function renderNumericInput(q) {
    hide('#choice-list');
    show('#numeric-wrap');
    setText('#q-instruction', '答えを数値で入力してください。');
    var input = $('#numeric-input');
    if (input) { input.value = ''; }
    setText('#numeric-unit', '');
    var btn = $('#btn-confirm');
    if (btn) { btn.disabled = true; }
    void q;
  }

  /* 0.5秒の思考インターロック。
     この間、選択肢カードは flat / opacity .85 / pointer-events:none。
     経過後に「スッ」と浮き上がってタップ可能になる（CSS側の .is-ready）。 */
  function armInterlock() {
    var list = $('#choice-list');
    state.interlock.ready = false;
    global.clearTimeout(state.interlock.timer);
    if (!list) { return; }

    list.classList.remove('is-ready');
    list.classList.add('is-interlocked');

    state.interlock.timer = global.setTimeout(function () {
      list.classList.remove('is-interlocked');
      list.classList.add('is-ready');
      state.interlock.ready = true;
      /* 反応時間の起点は「押せるようになった瞬間」（V1.78）。
         描画時から測ると、全員に同じ0.5秒が乗るだけで区別が付かない。 */
      if (state.current) { state.current.readyAt = Date.now(); }
    }, INTERLOCK_MS);
  }

  function onChoiceTap(card) {
    if (!state.interlock.ready || state.current.graded) { return; }
    /* 最初の1回だけ。選び直しは「迷い」の一部なので起点を動かさない（V1.78） */
    if (!state.current.firstTapAt) { state.current.firstTapAt = Date.now(); }
    var q = state.current.question;
    var num = parseInt(card.getAttribute('data-num'), 10);
    var sel = state.current.selected;
    var at = sel.indexOf(num);

    if (q.question_type === 'multiple') {
      if (at >= 0) { sel.splice(at, 1); }
      else { sel.push(num); }
    } else {
      state.current.selected = (at >= 0) ? [] : [num];
    }

    $$('#choice-list .choice-card').forEach(function (c) {
      var n = parseInt(c.getAttribute('data-num'), 10);
      toggleClass(c, 'is-selected', state.current.selected.indexOf(n) >= 0);
    });

    var need = (q.question_type === 'multiple') ? (q.select_count || 2) : 1;
    var btn = $('#btn-confirm');
    if (btn) {
      btn.disabled = state.current.selected.length !== need;
      btn.textContent = state.current.selected.length === need
        ? '解答を確定する'
        : (need - state.current.selected.length) + 'つ選んでください';
      if (!btn.disabled) { Half2.tip('confirm'); }
    }
  }

  /* 右トグル。模試では根拠チェック、それ以外では★。 */
  function onChoiceMarkTap(card, btn) {
    var id = card.getAttribute('data-atom-id');

    if (btn.getAttribute('data-kind') === 'ground') {
      if (state.current.graded) { return; }
      var on = !state.current.eliminated[id];
      if (on) { state.current.eliminated[id] = true; }
      else { delete state.current.eliminated[id]; }
      toggleClass(card, 'is-eliminated', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      btn.textContent = on ? '☑' : '☐';
      return;
    }

    /* ★は解答前でも付けられる（この場に思ったことを逃さないため） */
    S.toggleAtomStar(id).then(function (saved) {
      var atom = state.current.atoms.filter(function (a) { return a.atom_id === id; })[0];
      if (atom) { atom.is_starred = saved.is_starred; }
      btn.setAttribute('aria-pressed', saved.is_starred ? 'true' : 'false');
      btn.textContent = saved.is_starred ? '★' : '☆';
    }).catch(function (e) { toast('★を保存できませんでした：' + e.message, 3600); });
  }

  /* ======================================================================
   * 7. 採点
   * ====================================================================== */

  function confirmAnswer() {
    var cur = state.current;
    var q = cur.question;
    if (!q || cur.graded) { return; }

    var picked;
    if (q.question_type === 'numeric') {
      var raw = ($('#numeric-input') || {}).value;
      var val = parseFloat(String(raw).replace(/[,，\s]/g, ''));
      if (!isFinite(val)) { toast('数値を入力してください'); return; }
      var expect = q.numeric_answer;
      var tol = Math.max(Math.abs(expect) * 0.005, 0.05);   /* 丸め誤差を許容 */
      picked = (Math.abs(val - expect) <= tol) ? [1] : [];
      cur.numericInput = val;
    } else {
      picked = cur.selected.slice();
      if (!picked.length) { toast('選択肢を選んでください'); return; }
      /* 一問一答の「× 誤り」は -1。ここで捨てて「選ばなかった」に揃える。 */
      picked = picked.filter(function (n) { return n > 0; });
    }

    cur.selected = picked;
    cur.graded = true;

    /* --- 初期点灯（推奨評価）を確定する。
           評価を適用する前の last_eval が必要なので、必ずここで計算する。 --- */
    var rec = K.recommendEvaluations(cur.atoms, picked);
    cur.recommendations = rec.recommendations;
    cur.answeredRight = rec.answered_right;
    cur.evals = {};
    cur.touched = {};
    cur.forgot = {};
    Object.keys(rec.recommendations).forEach(function (id) {
      cur.evals[id] = rec.recommendations[id].eval;
    });

    showVerdictPopup(cur);

    /* --- 選択肢カードに正誤を反映（解答フェーズに一瞬残す） --- */
    $$('#choice-list .choice-card').forEach(function (c) {
      var n = parseInt(c.getAttribute('data-num'), 10);
      var atom = cur.atoms.filter(function (a) { return a.original_num === n; })[0];
      if (!atom) { return; }
      toggleClass(c, 'is-correct', !!atom.is_correct);
      toggleClass(c, 'is-wrong', !atom.is_correct && picked.indexOf(n) >= 0);
    });

    /* 力試し模試は解説を挟まず次問へ進むため、後半モジュールが
       ここで割り込んで描画を抑止する（false を返す） */
    if (typeof hooks.afterGrade === 'function' && hooks.afterGrade(cur) === false) { return; }

    renderReview();
  }

  /* ======================================================================
   * 8. 解説フェーズ（3ブロック絶対座標固定）
   * ====================================================================== */

  function renderReview() {
    var cur = state.current;
    var q = cur.question;

    $('#screen-quiz').setAttribute('data-phase', 'review');
    /* 下部に固定バーがある画面では、トーストをその上へ逃がす */
    toggleClass(doc.body, 'is-review', true);

    /* --- BLOCK A：問題文カード。正誤は26pxの○×だけに留め、
           空いた46pxぶんを問題文の幅に回す。 --- */
    var mark = $('#rv-mark');
    if (mark) {
      mark.textContent = cur.answeredRight ? '○' : '×';
      mark.className = 'rv-mark ' + (cur.answeredRight ? 'is-correct' : 'is-wrong');
      mark.setAttribute('aria-label', cur.answeredRight ? '正解' : '不正解');
    }
    var stem = $('#rv-stem');
    if (stem) {
      toggleClass(stem, 'is-correct', !!cur.answeredRight);
      toggleClass(stem, 'is-wrong', !cur.answeredRight);
    }
    var rank = $('#rv-rank');
    if (rank) { rank.textContent = q.rank; rank.className = 'rank-badge ' + q.rank; }
    setText('#rv-code', q.num_code || '');
    setText('#rv-stem-text', q.stem);
    setStarButton('#rv-star', !!q.is_starred);
    var sc = $('#rv-stem-scroll');
    if (sc) { sc.scrollTop = 0; }
    fitStemHeight();

    /* --- BLOCK B：選択肢ごとの解説 ＋ 直下の評価ボタン --- */
    renderChoiceBlocks();
    renderDetailBlock(q);
    var scroll = $('#rv-scroll');
    if (scroll) { scroll.scrollTop = 0; }

    /* --- BLOCK C：評価サマリー --- */
    renderSummary();

    /* 単語自由検索の演習は評価入力をスキップする（第12章①） */
    var isSearchMode = (state.session.mode === 'search');
    $$('#rv-choices .eval-group').forEach(function (g) { g.hidden = isSearchMode; });
    setText('#tz-summary', '');
    if (!isSearchMode) { renderSummary(); }
    setText('.btn-next-label', isSearchMode ? '次の検索結果へ' : 'この評価で次へ');

    if (!isSearchMode) {
      global.setTimeout(function () { Half2.tip('eval'); }, 240);
      /* 4ステップを終えた人にだけ、1問につき1つずつ追加のガイドを出す */
      global.setTimeout(function () { Half2.tipReviewExtra(); }, 1800);
    }
    checkPomodoro();
  }

  /* 解説文の冒頭にある「① 誤り：」は、行頭の番号と重複して冗長になる。
     丸数字を ⇒ に置き換え、「⇒ 誤り：…」の形に畳む。
     解説に正誤の記述が無い場合は、こちらで補って必ず示す。 */
  function prepareAtomExplanation(html, atom) {
    var out = prepareExplanationHtml(html || '');
    out = out.replace(/^\s*(?:・|<br\s*\/?>)+\s*/i, '');

    var re = /(<span\b[^>]*data-verdict="[^"]*"[^>]*>)\s*[①-⑳]\s*/;
    if (re.test(out)) {
      return out.replace(re, '<span class="cx-arrow" aria-hidden="true">⇒</span>$1');
    }
    if (!out.trim()) {
      return '<span class="cx-arrow" aria-hidden="true">⇒</span>' +
             '<span class="vd-chip" data-verdict="' + (atom.is_correct ? 'correct' : 'wrong') + '">' +
             (atom.is_correct ? '正解' : '誤り') + '</span>' +
             '<span class="cx-noexp">この選択肢の解説はまだありません</span>';
    }
    return '<span class="cx-arrow" aria-hidden="true">⇒</span>' +
           '<span class="vd-chip" data-verdict="' + (atom.is_correct ? 'correct' : 'wrong') + '">' +
           (atom.is_correct ? '正解：' : '誤り：') + '</span>' + out;
  }

  /* 問題文カードは固定84pxだと、短い問題文では余白が無駄になり、
     長い問題文（状況設定など）は3行目で切れる。内容に合わせて
     56〜118pxの範囲で伸縮させ、超える分だけスクロール＋⤢に回す。
     下部の操作パネルは常に画面下端に固定なので、指の位置はブレない。 */
  var STEM_MIN = 56, STEM_MAX = 118, STEM_PAD = 16;
  function fitStemHeight() {
    var review = $('#quiz-review'), sc = $('#rv-stem-scroll'), stem = $('#rv-stem');
    if (!review || !sc || !stem) { return; }
    /* 採寸は必ず最小高で行う。最大高にしてから scrollHeight を読むと、
       内容が短くても「引き伸ばされた枠の高さ」が返り、常に上限になる。 */
    review.style.setProperty('--stem-h', STEM_MIN + 'px');
    var need = sc.scrollHeight + STEM_PAD;
    var h = Math.max(STEM_MIN, Math.min(STEM_MAX, need));
    review.style.setProperty('--stem-h', h + 'px');
    /* 収まりきらない時だけ、下端フェードと⤢を出す */
    toggleClass(stem, 'is-clipped', need > STEM_MAX + 2);
    return h;
  }

  /* --- 選択肢ごとの解説をいつ見せるか（V1.44） ---
     【なぜ隠せるようにするか】
       全体解説を読んで【自分の言葉で書く】ほうが頭に残る（生成効果）。
       先に完成した解説が目に入ると、読んで分かった気になって終わる。
     【なぜ消さないか】
       隠すのは表示だけ。データは残す。消したら二度と戻せない。
     3段階：
       hidden … 出さない（全体解説だけで考える）
       button … ボタンで出せる（既定）
       open   … 最初から出る（V1.43までの動き） */
  var EXPLAIN_MODES = { hidden: 1, button: 1, open: 1 };

  function explainMode() {
    var v = (state.meta || {}).explain_mode;
    return EXPLAIN_MODES[v] ? v : 'button';
  }

  /* 「⇒ 正解：」「⇒ 誤り：」のチップだけを作る。
     解説を畳んでも、正誤そのものは必ず見えていなければならない。 */
  function verdictChipOnly(atom) {
    return '<span class="cx-arrow" aria-hidden="true">\u21d2</span>' +
           '<span class="vd-chip" data-verdict="' + (atom.is_correct ? 'correct' : 'wrong') + '">' +
           (atom.is_correct ? '正解' : '誤り') + '</span>';
  }

  /* 空欄は「欠陥」ではなく「書く場所」。文言と見た目の両方でそう見せる。 */
  function writePrompt() {
    return '<button type="button" class="cx-write cx-memo-btn">' +
           '\u270e 自分の言葉で書く</button>';
  }

  /* 書き換えがあればそれを本文として出し、元の解説は折りたたんで残す。
     消えたのではなく畳まれているだけ、と分かる形にする。 */
  function renderAtomBody(a) {
    var memo = a.user_memo && String(a.user_memo).trim();
    if (!memo) { return renderAtomExplainByMode(a); }
    /* 自分で書いたものは【常に出す】。隠す対象は元の解説だけ。 */
    return '<div class="memo-body">' +
           '<span class="cx-arrow" aria-hidden="true">\u21d2</span>' +
           '<span class="memo-badge">編集済</span>' +
           Half2.mdLite(memo) +
           '</div>' +
           (explainMode() === 'hidden' ? '' :
             '<details class="memo-orig-inline"><summary>元の解説を見る</summary>' +
             '<div class="explanation-body">' + prepareAtomExplanation(a.explanation, a) + '</div>' +
             '</details>');
  }

  function renderAtomExplainByMode(a) {
    var mode = explainMode();
    var raw = a.explanation && String(a.explanation).trim();

    /* 元から解説が無いなら、モードに関係なく「書く」だけを出す。 */
    if (!raw) { return verdictChipOnly(a) + writePrompt(); }
    if (mode === 'open') { return prepareAtomExplanation(a.explanation, a); }

    var head = verdictChipOnly(a) + writePrompt();
    if (mode === 'hidden') { return head; }
    return head +
           '<details class="cx-exp"><summary>解説を見る</summary>' +
           '<div class="explanation-body">' +
           prepareAtomExplanation(a.explanation, a) +
           '</div></details>';
  }

  /* 4肢ぶんを縦に並べる。1肢＝「番号＋本文」「⇒ 解説」「評価」の3段。
     タグは肢ごとに持たせない。問題単位で1行にまとめる（V1.11）。 */

  /* 全肢のタグを、出てきた順のまま重複だけ落として1本にする。
     ソートしないのは、作問者が書いた「主テーマ→副テーマ」の順序が
     そのまま読む順序として意味を持つため。 */
  function unionTags(atoms) {
    var seen = {}, out = [];
    (atoms || []).forEach(function (a) {
      (a.tags || []).forEach(function (t) {
        if (t && !seen[t]) { seen[t] = 1; out.push(t); }
      });
    });
    return out;
  }

  /* この肢を今回記録してよいか。scheduler.js の門番をそのまま呼ぶので、
     画面の表示と実際の書き込みがズレることが構造的に起こらない。 */
  /* --- 反応時間（V1.78・§2-5の約束） ---
     「押せるようになってから最初に肢へ触れるまで」のミリ秒。
     取れないときは null を返す。**推測で埋めない。**
       ・数値入力や、肢に触れずに確定した（＝タップが無い）
       ・画面を離れて戻ってきた等で起点が無い
     上限を10分で切る。放置して戻ってきた1件が、平均を意味の無い値にする。 */
  var THINK_MAX_MS = 600000;

  function thinkMsForCurrent() {
    var c = state.current;
    if (!c || !c.readyAt || !c.firstTapAt) { return null; }
    var ms = c.firstTapAt - c.readyAt;
    if (!(ms >= 0) || ms > THINK_MAX_MS) { return null; }
    return ms;
  }

  function commitDecisionFor(a) {
    var cur = state.current;
    var picked = cur.selected.indexOf(a.original_num) >= 0;
    var ok = (cur.forgot && cur.forgot[a.atom_id]) ? false : (picked === !!a.is_correct);
    return K.commitDecision(a, ok, state.session.mode, Date.now());
  }

  /* 「次回 9/14（あと24日）」。24時間を切ったら日ではなく時間で出す。
     「あと1日」と出してしまうと、今夜の期日なのか明日なのかが伝わらない。 */
  function fmtDueShort(ms) {
    if (!ms) { return '未定'; }
    var diff = ms - Date.now();
    var d = new Date(ms);
    var head = (d.getMonth() + 1) + '/' + d.getDate();
    if (diff < 86400000) {
      return head + '（あと' + Math.max(1, Math.ceil(diff / 3600000)) + '時間）';
    }
    return head + '（あと' + Math.ceil(diff / 86400000) + '日）';
  }

  function lockedPanelHtml(a, dec) {
    if (dec.demote) {
      return '<div class="eval-locked is-demote">' +
             '<span class="el-main">期日前でしたが、間違えたので<b>「難しい」</b>に戻します</span>' +
             '<span class="el-sub">次回：10分後</span></div>';
    }
    return '<div class="eval-locked">' +
           '<span class="el-main">この選択肢は仕上がっています</span>' +
           '<span class="el-sub">次回 ' + escapeHtml(fmtDueShort(a.due_date)) +
           '　この回は記録しません</span>' +
           '<button type="button" class="btn-forgot">忘れていた（復習に戻す）</button>' +
           '</div>';
  }

  /* 正解したのに自信が無かった肢を、自分の判断で復習へ戻す。
     is_correct を false に倒して門番の early-miss 経路へ乗せるので、
     降格の記録のされ方は「実際に間違えた」ときと完全に同じになる。 */
  function forgetAtom(atomId) {
    var cur = state.current;
    var atom = cur.atoms.filter(function (a) { return a.atom_id === atomId; })[0];
    if (!atom || !cur.forgot) { return; }
    cur.forgot[atomId] = true;
    cur.evals[atomId] = 'hard';
    cur.touched[atomId] = true;
    renderChoiceBlocks();
    renderSummary();
    toast('この選択肢を復習に戻します（次回：10分後）', 2200);
  }

  function renderChoiceBlocks() {
    var cur = state.current;

    /* タグは「この問題が扱っているテーマ」として、常に問題単位で1行だけ出す。
       どの肢がどのタグかは、学習中の判断に一度も使われていない。 */
    var allTags = unionTags(cur.atoms);
    var sharedHtml = allTags.length
      ? '<div class="cx-shared-tags"><span class="cx-shared-label">テーマ</span>' +
        allTags.map(function (t) {
          return '<button type="button" class="tag-pill" data-tag="' + escapeHtml(t) + '">' +
                 escapeHtml(t) + '</button>';
        }).join('') + '</div>'
      : '';

    var html = cur.atoms.map(function (a) {
      var picked = cur.selected.indexOf(a.original_num) >= 0;
      var chosen = cur.evals[a.atom_id] || 'normal';
      var masterOk = K.isMasterUnlocked(a);
      var pv = K.previewAllIntervals(a);
      var dec = commitDecisionFor(a);
      var evals = [
        { k: 'hard',   b: '難', s: 'しい' },
        { k: 'normal', b: '普', s: '通' },
        { k: 'easy',   b: '易', s: 'しい' },
        { k: 'master', b: 'マ', s: 'スター' }
      ].map(function (e) {
        var dis = (e.k === 'master' && !masterOk);
        var title = dis ? '30日以上の長期ステップに到達すると押せます' : '次回：' + pv[e.k].label;
        return '<button type="button" class="eval-btn eval-' + e.k + (e.k === chosen ? ' is-active' : '') + '"' +
               ' data-eval="' + e.k + '"' + (dis ? ' disabled' : '') +
               ' title="' + escapeHtml(title) + '">' +
               '<span class="eval-label"><b>' + e.b + '</b><small>' + e.s + '</small></span></button>';
      }).join('');

      /* 期日前の肢は評価ボタンごと差し替える（disabled で並べない） */
      var evalArea = (dec.commit && !dec.demote)
        ? '<div class="eval-group" role="group" aria-label="選択肢' + a.original_num +
          'の評価">' + evals + '</div>'
        : lockedPanelHtml(a, dec);

      /* 解答前の到達度で存在感を決める。易・マスターまで来ている肢は
         静かにして、まだ弱い肢へ視線が向くようにする。 */
      var strength = (a.last_eval === 'easy' || a.last_eval === 'master') ? 'strong'
                   : (a.last_eval === 'hard' || !a.answer_count) ? 'weak' : 'mid';

      return '<article class="cx ' + (a.is_correct ? 'is-correct' : 'is-wrong') +
             (picked ? ' is-picked' : '') + (a.user_memo ? ' has-memo' : '') +
             (dec.commit ? '' : ' is-locked') +
             '" data-strength="' + strength + '" data-locked="' + (dec.commit ? '0' : '1') +
             '" data-atom-id="' + escapeHtml(a.atom_id) +
             '" data-num="' + a.original_num + '">' +
             '<div class="cx-line">' +
             '<span class="cx-num">' + circled(a.original_num) + '</span>' +
             '<span class="cx-text">' + escapeHtml(a.text) + '</span>' +
             (picked ? '<span class="cx-pick">あなたの答え</span>' : '') +
             '<button type="button" class="cx-memo-btn" aria-label="この選択肢の解説を書き換える">✏</button>' +
             '<button type="button" class="cx-star" aria-pressed="' + (a.is_starred ? 'true' : 'false') +
             '" aria-label="この選択肢に★を付ける">' + (a.is_starred ? '★' : '☆') + '</button>' +
             '</div>' +
             '<div class="cx-exp explanation-body">' + renderAtomBody(a) + '</div>' +
             evalArea +
             '</article>';
    }).join('');
    setHtml('#rv-choices', sharedHtml + (html || '<p class="rv-empty">選択肢ごとの解説がありません</p>'));
  }

  /* 全体解説・比較表・図解を1つの開閉ブロックにまとめる。
     タブ切替を無くし、図解エンジン（3.2MB）は開いた時だけ読み込む。 */
  /* --- 自作の図解画像（バッチC-1） ---
     Blob URL は使い終わったら必ず revoke する。問題を送るたびに作ると、
     1セッション数百枚ぶんのメモリが解放されないまま残る。 */
  var userImgUrl = null;

  function clearUserImgUrl() {
    if (userImgUrl) { global.URL.revokeObjectURL(userImgUrl); userImgUrl = null; }
  }

  function renderUserImage(q) {
    var frame = $('#userimg-frame'), img = $('#userimg');
    var empty = $('#userimg-empty'), del = $('#btn-userimg-del');
    clearUserImgUrl();
    if (frame) { frame.hidden = true; }
    if (empty) { empty.hidden = false; }
    if (del) { del.hidden = true; }
    setText('#userimg-note', '');
    if (!q || !q.q_id) { return Promise.resolve(null); }

    return S.getUserImage(q.q_id).then(function (rec) {
      if (!rec || !rec.blob) { return null; }
      userImgUrl = global.URL.createObjectURL(rec.blob);
      if (img) { img.src = userImgUrl; }
      if (frame) { frame.hidden = false; }
      if (empty) { empty.hidden = true; }
      if (del) { del.hidden = false; }
      setText('#userimg-note',
        (rec.w && rec.h ? rec.w + '×' + rec.h + ' / ' : '') +
        Math.max(1, Math.round(rec.bytes / 1024)) + 'KB');
      return rec;
    }).catch(function (e) {
      console.error('[userimg]', e);
      return null;
    });
  }

  /* --- 画像を選ぶ前の確認（V1.36） ---
     【なぜ毎回出すか】
       常時表示の注意書きは3日で背景と同化して読まれなくなる。
       出すべきは「決める瞬間」＝ファイルを選ぶ直前で、しかも毎回。
       ここで止めれば、まだ何も取り込んでいないので引き返せる。
     【なぜ赤字にしないか】
       このアプリで赤は誤り、緑は正解と決まっている（決まり4-1）。
       注意書きに赤を使うと、正誤の赤の意味が薄まる。
     ※「次から表示しない」は付けない。付けた瞬間に意味を失う確認なので。 */
  function pickUserImage() {
    var ok = global.confirm(
      'この問題に図を1枚追加します。\n\n' +
      '次の内容は取り込まないでください。\n' +
      '・著作権のある資料（市販の参考書・問題集の紙面を撮影した画像等）\n' +
      '・個人を特定できる情報（患者情報、実習記録等）\n\n' +
      '利用者自身が作成した図表は対象外です。\n' +
      '画像は本端末内に保存され、開発者が内容を閲覧することはできません。\n\n' +
      '続行しますか。');
    if (!ok) { return false; }
    var f = $('#userimg-file');
    if (f) { f.value = ''; f.click(); }
    return true;
  }

  function saveUserImage(file) {
    var q = state.current.question;
    if (!q || !file) { return Promise.resolve(null); }
    toast('画像を縮めています…', 1600);
    return S.putUserImage(q.q_id, file).then(function (rec) {
      q.user_image_id = rec.file_id;
      q.user_image_updated_at = rec.updated_at;
      return renderUserImage(q).then(function () {
        toast('図を保存しました（' + Math.max(1, Math.round(rec.bytes / 1024)) + 'KB）', 2600);
        /* ログイン済みなら、その場でこの1枚だけ上げる（V1.38）。
           全体同期は台帳ごと送るので重い。1枚＋目次なら軽い。
           未ログイン・期限切れのときは黙って見送る。ここで再ログインを
           促すと、図を貼るたびに邪魔になるため。次の同期で拾われる。 */
        if (global.Drive && global.Drive.pushOneImage) {
          global.Drive.pushOneImage(q.q_id).then(function (r) {
            if (r && r.ok) { toast('ドライブにも保存しました', 2200); }
          }).catch(noop);
        }
        return rec;
      });
    }).catch(function (e) {
      toast(e && e.message ? e.message : '画像を保存できませんでした', 5000);
      return null;
    });
  }

  function removeUserImage() {
    var q = state.current.question;
    if (!q) { return Promise.resolve(false); }
    /* V1.55：確認を挟む。自分で描いた図は作り直せない。
       1タップで戻せなくなる操作に、逃げ道が無かった。 */
    return confirmAction({
      title: 'この図を消しますか',
      body: '自分で入れた図を消します。元には戻せません。'
          + 'もう一度使うには、撮り直すか描き直すことになります。',
      ok: '消す'
    }).then(function (yes) {
      if (!yes) { return false; }
      return doRemoveUserImage(q);
    });
  }

  function doRemoveUserImage(q) {
    return S.deleteUserImage(q.q_id).then(function () {
      q.user_image_id = null;
      q.user_image_updated_at = null;
      return renderUserImage(q);
    }).then(function () {
      /* 消したことも、その場でドライブへ伝える（V1.39）。
         入れたときだけ伝えて消したときに伝えないと、目次に
         image_file_id が残り、別端末が【消したはずの図を拾って戻す】。
         ログインしていなければ黙って見送る（次の全体同期で伝わる）。 */
      if (global.Drive && global.Drive.pushImageDelete) {
        global.Drive.pushImageDelete(q.q_id).catch(function () {});
      }
      toast('図を消しました', 2000);
      return true;
    });
  }

  function overallBodyHtml(q) {
    var memo = q && q.user_memo && String(q.user_memo).trim();
    var orig = q && q.overall_explanation;
    if (!memo) {
      return orig ? prepareOverallHtml(orig) : '<p class="rv-empty">全体解説がありません</p>';
    }
    return '<div class="memo-body">' +
           '<span class="memo-badge">編集済</span>' +
           Half2.mdLite(memo) +
           '</div>' +
           (orig
             ? '<details class="memo-orig-inline"><summary>元の全体解説を見る</summary>' +
               '<div class="explanation-body">' + prepareOverallHtml(orig) + '</div></details>'
             : '');
  }

  /* --- 自分で入れた図の置き場所（V1.29） ---
     3箇所の受け皿のうち1つへ、節ごと差し込む（複製しない）。
     既定は 'after-figure'＝いちばん下。読み込みの重さは増えない：
     画像は V1.27 の時点で「解説を組み立てるたびに1回読む」実装で、
     常時表示にしても読む回数は変わらない（描画されるだけ）。 */
  var USERIMG_SLOTS = {
    'after-explanation': 'userimg-slot-choices',
    'after-table'      : 'userimg-slot-table',
    'after-figure'     : 'userimg-slot-bottom'
  };

  function userImagePos() {
    var v = state.meta && state.meta.user_image_pos;
    return USERIMG_SLOTS[v] ? v : 'after-figure';
  }

  function placeUserImageSection() {
    var sec = $('#sec-userimg');
    if (!sec) { return; }
    var slot = $('#' + USERIMG_SLOTS[userImagePos()]);
    if (!slot || sec.parentNode === slot) { return; }
    slot.appendChild(sec);
  }

  /* --- 誤りの報告（V1.36） ---
     【本文を自動で載せるのは同梱の問題だけ】
       利用者が取り込んだ問題には、他人の著作物が入っている可能性がある。
       それを本文ごと作者のメールボックスへ集めると、避けたいはずのものを
       自分から引き受けることになる。取り込み問題は q_id だけ送る。
     置き場所はサムゾーンではなく解説エリア。サムゾーンは評価専用に保つ。 */
  function isBundledQuestion(q) {
    return !!(q && String(q.q_id || '').indexOf('ORIG_') === 0);
  }

  function reportBody(q) {
    var L = [];
    L.push('■ どこが誤っていましたか（ご記入ください）');
    L.push('');
    L.push('');
    L.push('----------------------------------------');
    L.push('問題ID: ' + (q.q_id || '不明'));
    L.push('分類: ' + [q.unit, q.major, q.medium].filter(Boolean).join(' > '));
    L.push('アプリ版: ' + (S.APP_BUILD || '不明'));
    if (isBundledQuestion(q)) {
      L.push('');
      L.push('--- 問題文 ---');
      L.push(String(q.stem || ''));
      L.push('');
      L.push('--- 選択肢 ---');
      (state.current && state.current.atoms ? state.current.atoms : []).forEach(function (a) {
        L.push(a.original_num + '. ' + String(a.text || '') +
               (a.is_correct ? '  ← 正解' : ''));
      });
      L.push('');
      L.push('--- 解説 ---');
      L.push(String(q.overall_explanation || '').replace(/<[^>]+>/g, ''));
    } else {
      L.push('');
      L.push('（この問題はご自身で取り込まれたものです。');
      L.push('　権利関係の都合上、本文は自動では添付していません。');
      L.push('　必要に応じて、ご自身で貼り付けてください。）');
    }
    return L.join('\n');
  }

  function reportQuestion() {
    var q = state.current && state.current.question;
    if (!q) { return; }
    var url = 'mailto:' + (global.Half2Impl ? global.Half2Impl.SUPPORT_EMAIL : '') +
              '?subject=' + encodeURIComponent('[オモイダス] 内容の誤り: ' + (q.q_id || '')) +
              '&body=' + encodeURIComponent(reportBody(q));
    try { global.location.href = url; } catch (e) { /* 下で案内する */ }
    toast('宛先：' + (global.Half2Impl ? global.Half2Impl.SUPPORT_EMAIL : ''), 6000);
  }

  function renderDetailBlock(q) {
    /* 書き換えがあれば、そちらを本文として出す。選択肢のメモと同じ作法。
       V1.26 までは保存はできるのに一度も表示されていなかった。 */
    setHtml('#rv-overall', overallBodyHtml(q));
    setHtml('#rv-table', q.comparison_table ? prepareExplanationHtml(q.comparison_table) : '');

    var secTable = $('#sec-table'), secMmd = $('#sec-mermaid');
    if (secTable) { secTable.hidden = !q.comparison_table; }
    if (secMmd) { secMmd.hidden = !q.mermaid_code; }
    /* 自作の図のセクションは常に出す。「ここに貼れる」ことを知る場所が
       ほかに無いので、画像が無いときこそ見えている必要がある。 */
    placeUserImageSection();
    renderUserImage(q).catch(noop);

    /* V1.29：全体解説と比較表は最初から開いている。閉じない。 */
    var panel = $('#detail-panel');
    if (panel) { panel.hidden = false; }

    /* 開閉ボタンが受け持つのは図解だけ。図解が無い問題ではボタンごと隠す。 */
    var fig = $('#fig-panel'), btn = $('#btn-detail');
    var hasFig = !!q.mermaid_code;
    if (fig) { fig.hidden = true; }
    if (btn) {
      btn.hidden = !hasFig;
      btn.disabled = false;
      btn.setAttribute('aria-expanded', 'false');
      setText('.detail-toggle-label', '図解を見る');
      setText('#detail-sub', hasFig ? 'この問題の図解' : '');
    }
    state.detailOpened = false;
  }

  function toggleDetail() {
    var fig = $('#fig-panel'), btn = $('#btn-detail');
    if (!fig || !btn || btn.disabled || btn.hidden) { return; }
    var open = fig.hidden;
    fig.hidden = !open;
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    setText('.detail-toggle-label', open ? '図解を閉じる' : '図解を見る');

    if (open && !state.detailOpened) {
      state.detailOpened = true;
      renderMermaid(state.current.question.mermaid_code);
    }
    if (open) {
      global.setTimeout(function () {
        if (btn.scrollIntoView) { btn.scrollIntoView({ block: 'start', behavior: 'smooth' }); }
      }, 60);
    }
  }

  /* 固定バーの評価サマリー。
     薄い＝推奨のまま／濃い＝自分で選んだ、で塗り分ける。 */
  function renderSummary() {
    var cur = state.current;
    var html = cur.atoms.map(function (a) {
      var ev = cur.evals[a.atom_id] || 'normal';
      var touched = !!cur.touched[a.atom_id];
      var dec = commitDecisionFor(a);
      return '<button type="button" class="sum-dot' + (touched ? ' is-touched' : '') +
             (dec.commit ? '' : ' is-locked') +
             (a.is_starred ? ' is-star' : '') + '"' +
             ' data-eval="' + ev + '" data-num="' + a.original_num + '"' +
             ' aria-label="選択肢' + a.original_num + '：' +
             (dec.commit ? K.EVAL_LABEL[ev] : '期日前のため今日は記録しません') + '">' +
             circled(a.original_num) + '</button>';
    }).join('');
    setHtml('#tz-summary', html);

    var tz = $('#thumb-zone');
    if (tz) {
      var last = cur.lastTouchedEval || cur.evals[cur.atoms[0] ? cur.atoms[0].atom_id : ''] || 'normal';
      tz.setAttribute('data-eval', last);
    }
  }

  /* 正誤ポップアップ。非ブロッキングなので、出ている間も指は動かせる。
     正解は認識するだけなので短く、不正解は正解肢を読む時間を確保する。 */
  var verdictTimer = null;
  function showVerdictPopup(cur) {
    var pop = $('#verdict-pop');
    if (!pop) { return; }
    if (state.meta && state.meta.verdict_popup_enabled === false) { return; }

    var correctAtoms = cur.atoms.filter(function (a) { return a.is_correct; });
    var right = !!cur.answeredRight;

    setText('#vp-mark', right ? '○' : '×');
    setText('#vp-title', right ? '正解！' : '不正解');
    setHtml('#vp-answer', '正解は ' + correctAtoms.map(function (a) {
      return '<b>' + circled(a.original_num) + ' ' + escapeHtml(a.text) + '</b>';
    }).join(' と '));

    pop.className = 'verdict-pop ' + (right ? 'is-correct' : 'is-wrong');
    pop.hidden = false;

    /* 正解0.6秒／不正解1.6秒／複数正解2.4秒 */
    var ms = right ? 600 : (correctAtoms.length > 1 ? 2400 : 1600);
    global.clearTimeout(verdictTimer);
    verdictTimer = global.setTimeout(function () { hideVerdictPopup(); }, ms);
  }

  function hideVerdictPopup() {
    var pop = $('#verdict-pop');
    if (!pop || pop.hidden) { return; }
    global.clearTimeout(verdictTimer);
    pop.classList.add('is-out');
    global.setTimeout(function () {
      pop.hidden = true;
      pop.classList.remove('is-out');
    }, 200);
  }

  /* TSV由来のHTMLを描画用に整える。
     1) <table> を .tbl-scroll で包む（包まないと横スクロールせず画面外で切れる）
     2) ①正解／①誤り のハイライトに data-verdict を付け、赤緑に色分けする */
  function prepareExplanationHtml(html) {
    var s = String(html == null ? '' : html);

    /* 重要語句のマークダウン記法を <b> へ寄せる。
       取り込み時ではなく描画時に変換するのは、元データを書き換えずに
       あとから強調ルールだけ差し替えられるようにするため。
       タグの中身を巻き込まないよう <> を除外している。 */
    s = s.replace(/\*\*([^*<>\n]{1,80})\*\*/g, '<b>$1</b>');

    s = s.replace(/<table/gi, '<div class="tbl-scroll"><table')
         .replace(/<\/table>/gi, '</table></div>');
    s = s.replace(
      /(<span\b[^>]*bg-yellow-200[^>]*?)(>)\s*([①-⑳])\s*(正解|正しい|誤り|誤|正しくない|不適切|不適当)/g,
      function (m, pre, gt, num, word) {
        var v = (word === '正解' || word === '正しい') ? 'correct' : 'wrong';
        return pre + ' data-verdict="' + v + '"' + gt + num + ' ' + word;
      }
    );
    return s;
  }

  /* 全体解説だけに効かせる整形。
     ・行頭の「・」は、丸数字と重なって字下げが二重になるだけで意味がない
     ・「①正解：」「②誤り：」は、記号（○×）にすると読む前に意味が取れる
     選択肢ごとの解説（⇒ 正解：）はここを通さない。あちらは1肢に1つしか
     出ないので、記号より語のほうが誤読しにくい。 */
  var CIRCLED_SRC = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳';

  function prepareOverallHtml(html) {
    var s = prepareExplanationHtml(html);
    s = s.replace(/([①-⑳])\s*(正解|正しい|誤り|誤|正しくない|不適切|不適当)/g,
      function (m, c, w) {
        var n = CIRCLED_SRC.indexOf(c) + 1;
        var mark = (w === '正解' || w === '正しい') ? '○' : '×';
        return (n > 0 ? n : '') + '.' + mark;
      });
    /* 行頭の中黒を落とす。<br> 直後と文字列先頭の両方。 */
    s = s.replace(/(^|<br\s*\/?>)\s*(?:・|･)\s*/gi, '$1');
    return s;
  }

  /* 図解エンジンは 3.3MB ある。<head> で同期読み込みすると初回表示が
     数秒止まるため、「図解」タブを最初に開いた瞬間にだけ取りに行く。
     Service Worker がキャッシュ済みなら2回目以降はオフラインでも即時。 */
  /* ローカル同梱を先に試し、無い場合だけCDNへ落ちる。
     CDNを先にすると、圏外や機内モードで図解が出なくなる。 */
  var MERMAID_SOURCES = [
    './vendor/mermaid.min.js',
    'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js'
  ];
  var mermaidLoading = null;

  function loadScript(src) {
    return new Promise(function (resolve) {
      var sc = doc.createElement('script');
      sc.src = src;
      sc.async = true;
      sc.onload = function () { resolve(typeof global.mermaid !== 'undefined'); };
      sc.onerror = function () { resolve(false); };
      doc.head.appendChild(sc);
    });
  }

  function loadMermaid() {
    if (typeof global.mermaid !== 'undefined') { return Promise.resolve(true); }
    if (mermaidLoading) { return mermaidLoading; }

    mermaidLoading = MERMAID_SOURCES.reduce(function (chain, src) {
      return chain.then(function (okSoFar) {
        if (okSoFar) { return true; }
        return loadScript(src);
      });
    }, Promise.resolve(false)).then(function (okLoad) {
      if (!okLoad) { mermaidLoading = null; }
      return okLoad;
    });

    return mermaidLoading;
  }

  function renderMermaid(code) {
    var frame = $('#mermaid-frame');
    if (!frame) { return Promise.resolve(); }

    if (!code) {
      frame.innerHTML = '<p class="mermaid-error">この問題に図解はありません</p>';
      return Promise.resolve();
    }

    if (typeof global.mermaid === 'undefined') {
      frame.innerHTML = '<p class="mermaid-error">図解を読み込んでいます…</p>';
      return loadMermaid().then(function (okLoad) {
        if (!okLoad) {
          /* 取得に失敗しても落とさず、コードをそのまま見せる */
          frame.innerHTML = '<pre class="mermaid-error" style="text-align:left;white-space:pre-wrap">' +
                            escapeHtml(code) + '</pre>';
          return;
        }
        return drawMermaid(frame, code);
      });
    }
    return drawMermaid(frame, code);
  }

  function drawMermaid(frame, code) {
    var id = 'mmd-' + (++state.mermaidSeq);
    try {
      /* 日本語フォントを initialize で渡す。
         CSSで後から font-family を差し替えると、Mermaidが英字フォント幅で
         採寸したノード枠に日本語が入りきらず、ラベルが枠で切れる。 */
      global.mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict',
        theme: 'neutral',
        fontFamily: global.getComputedStyle(doc.body).fontFamily,
        flowchart: { htmlLabels: true, useMaxWidth: true, padding: 12, nodeSpacing: 34, rankSpacing: 40 }
      });
      var out = global.mermaid.render(id, code);
      if (out && typeof out.then === 'function') {
        return out.then(function (r) {
          frame.innerHTML = (r && r.svg) ? r.svg : String(r);
        }).catch(function () {
          frame.innerHTML = '<p class="mermaid-error">図解を表示できませんでした</p>';
        });
      }
      frame.innerHTML = (out && out.svg) ? out.svg : String(out || '');
    } catch (e) {
      frame.innerHTML = '<p class="mermaid-error">図解を表示できませんでした</p>';
    }
    return Promise.resolve();
  }

  /* ======================================================================
   * 9. 評価の操作と★
   * ====================================================================== */

  /* 評価の切り替え。どの肢のボタンを押したかで対象が決まるので、
     肢を選び直す操作そのものが不要になった。 */
  function setEval(atomId, evalKey) {
    var cur = state.current;
    var atom = cur.atoms.filter(function (a) { return a.atom_id === atomId; })[0];
    if (!atom) { return; }
    var dec = commitDecisionFor(atom);
    if (!dec.commit) {
      toast('この選択肢は ' + fmtDueShort(atom.due_date) + ' が期日です。今日は記録しません', 2400);
      return;
    }
    if (dec.demote) { return; }   /* 期日前の誤答は「難しい」で固定 */
    if (evalKey === 'master' && !K.isMasterUnlocked(atom)) {
      toast('「マスター」は30日以上の長期ステップに到達すると押せます');
      return;
    }
    cur.evals[atomId] = evalKey;
    cur.touched[atomId] = true;      /* 自分で選んだ印。サマリーで濃く表示する */
    cur.lastTouchedEval = evalKey;
    Half2.tip('next');               /* 1つ評価できた直後に、次へ進む道を教える */

    var block = null;
    $$('#rv-choices .cx').forEach(function (el) {
      if (el.getAttribute('data-atom-id') === atomId) { block = el; }
    });
    if (block) {
      $$('.eval-btn', block).forEach(function (b2) {
        toggleClass(b2, 'is-active', b2.getAttribute('data-eval') === evalKey);
      });
    }
    renderSummary();
  }

  function setStarButton(sel, on) {
    var el = $(sel);
    if (!el) { return; }
    el.setAttribute('aria-pressed', on ? 'true' : 'false');
    el.textContent = on ? '★' : '☆';
  }

  function toggleCurrentQuestionStar() {
    var q = state.current.question;
    if (!q) { return Promise.resolve(); }
    return S.toggleQuestionStar(q.q_id).then(function (saved) {
      q.is_starred = saved.is_starred;
      setStarButton('#q-star', saved.is_starred);
      setStarButton('#rv-star', saved.is_starred);
      toast(saved.is_starred ? 'この問題に★を付けました' : '★を外しました', 1600);
    });
  }

  /* 解説側の★。解答フェーズで付けた状態とそのまま連動する。 */
  function toggleAtomStarById(atomId, btn) {
    return S.toggleAtomStar(atomId).then(function (saved) {
      var atom = state.current.atoms.filter(function (a) { return a.atom_id === atomId; })[0];
      if (atom) { atom.is_starred = saved.is_starred; }
      if (btn) {
        btn.setAttribute('aria-pressed', saved.is_starred ? 'true' : 'false');
        btn.textContent = saved.is_starred ? '★' : '☆';
      }
      renderSummary();
    });
  }

  /* サマリーの丸をタップしたら、その肢まで滑らせる */
  function scrollToChoice(num) {
    var block = null;
    $$('#rv-choices .cx').forEach(function (el) {
      if (parseInt(el.getAttribute('data-num'), 10) === num) { block = el; }
    });
    if (block && block.scrollIntoView) { block.scrollIntoView({ block: 'center', behavior: 'smooth' }); }
  }

  /* ======================================================================
   * 10. 次の問題へ（評価のコミット）
   * 10. 次の問題へ（評価のコミット）
   * ====================================================================== */

  function nextQuestion() {
    var cur = state.current;
    var q = cur.question;
    if (!q || !cur.graded) { return Promise.resolve(); }

    var btn = $('#btn-next');
    if (btn) { btn.disabled = true; }

    var mode = state.session.mode;

    /* 単語自由検索の演習は、忘却スケジュールも弱点ptも一切更新しない */
    var commit;
    if (mode === 'search') {
      commit = Promise.resolve({ recorded: false });
    } else {
      var evaluations = cur.atoms.map(function (a) {
        var picked = cur.selected.indexOf(a.original_num) >= 0;
        /* 「忘れていた」を押した肢は、実際に間違えたのと同じ扱いにする。
           門番の early-miss 経路に乗るので、降格の記録も同一になる。 */
        var forgot = !!(cur.forgot && cur.forgot[a.atom_id]);
        return {
          atom_id: a.atom_id,
          eval: cur.evals[a.atom_id] || 'normal',
          /* その肢の扱いが正しかったか（選ぶべきを選び、選ばぬべきを選ばなかったか） */
          is_correct: forgot ? false : (picked === !!a.is_correct)
        };
      });
      commit = K.applyQuestionEvaluations(q.q_id, evaluations, {
        mode: mode,
        sessionId: state.session.sessionId,
        boundaryHour: state.meta ? state.meta.day_boundary_hour : 4,
        thinkMs: thinkMsForCurrent()
      });
    }

    return commit.then(function (r) {
      state.session.answeredCount++;
      markPomodoroActivity();   /* 無操作リセットの基準は「手が動いた時刻」 */
      if (typeof hooks.afterCommit === 'function') {
        try { hooks.afterCommit(q, state.session, r); } catch (e) { console.error('[afterCommit]', e); }
      }
      if (r && r.progress && r.progress.scan) {
        updateScanMeter(r.progress.scan, true);
      }
      if (mode !== 'search') {
        S.bumpDailyCount(state.meta ? state.meta.day_boundary_hour : 4)
          .then(function () { return refreshScanSlot(); }).catch(noop);
      }
      return S.getDueCount();
    }).then(function (due) {
      updateAppBadge(due);
      hideVerdictPopup();
      return advanceQueue();
    }).catch(function (e) {
      console.error('[nextQuestion]', e);
      /* --- 保存に失敗したら、必ず止まって知らせる（V1.60） ---
         ここで先へ進めてはいけない。進むと【解いたつもりなのに
         記録が残っていない】状態になり、利用者は気づけない。
         いまの作りでも advanceQueue() はこの catch より前なので
         進まないが、それは偶然ではなく守るべき性質。

         文言は storage.js の describeError が決める。
         「保存に失敗しました：quota」では何も伝わらない。
         必要なのは【何が起きたか】ではなく【次に何をすればよいか】。 */
      var text = (S && S.describeError) ? S.describeError(e)
               : ('保存に失敗しました：' + (e && e.message ? e.message : e));
      openSaveErrorDialog(text);
    }).then(function () {
      if (btn) { btn.disabled = false; }
    });
  }

  /* ======================================================================
   * 11. インライン早期復習割り込み（第5章②）
   * ====================================================================== */

  function advanceQueue() {
    var s = state.session;

    /* --- 割り込み中なら、まずその消化を進める --- */
    if (K.Interrupt.status().active) {
      var ad = K.Interrupt.advance();
      if (!ad.finished) {
        s.index++;
        renderInterruptBar();
        renderQuestion();
        return Promise.resolve();
      }
      /* 3問完了（または上限到達）→ 元の学習モードへ自動復帰 */
      toast(ad.reason, 2600);
      s.questions = s.hostQueue || s.questions;
      s.index = s.hostIndex;
      s.hostQueue = null;
      toggleClass($('#screen-quiz'), 'is-interrupt', false);
      renderInterruptBar();
      return stepForward();
    }

    /* --- 割り込みの発火判定（絶対ガードは Scheduler 側で担保） --- */
    if (K.Interrupt.shouldTrigger(s.mode)) {
      return K.Interrupt.begin(s.mode).then(function (res) {
        if (!res.started) { return stepForward(); }
        s.hostQueue = s.questions;
        s.hostIndex = s.index + 1;
        s.questions = res.questions;
        s.index = 0;
        toggleClass($('#screen-quiz'), 'is-interrupt', true);
        renderInterruptBar();
        renderQuestion();
      });
    }

    return stepForward();
  }

  function stepForward() {
    var s = state.session;
    s.index++;
    if (s.index >= s.questions.length) { return finishSession(); }
    renderQuestion();
    return Promise.resolve();
  }

  function renderInterruptBar() {
    var st = K.Interrupt.status();
    var bar = $('#interrupt-bar');
    if (!bar) { return; }
    if (!st.active) { bar.hidden = true; return; }
    bar.hidden = false;
    setText('#interrupt-count', '(' + Math.min(st.served + 1, st.total) + '/' + st.total + '問)');
  }

  /* ======================================================================
   * 12. セッション終了
   * ====================================================================== */

  function finishSession() {
    var s = state.session;
    var mode = s.mode;
    var solved = s.answeredCount;

    stopPomodoro();
    K.Interrupt.endSession();

    /* 模試・ノック・オンボーディングは独自の終了処理を持つ */
    if (typeof hooks.onFinish === 'function' && hooks.onFinish(s) === true) {
      return Promise.resolve();
    }

    return K.refreshAll({ recomputeWeakness: false })
      .then(function () { return refreshHome(); })
      .then(function () {
        return go('home', { replace: true });
      })
      .then(function () {
        if (mode === 'review') {
          setText('#done-count', solved);
          openModal('#modal-review-done');
          fireConfetti();
          /* ダイアログを閉じたあとの TOP3 ポップインは後半が担当する */
          return;
        }
        if (mode === 'knock') { return Half2.finishKnock(solved); }
        toast(solved + ' 問の学習が完了しました', 3000);
      });
  }

  /* 紙吹雪（外部ライブラリ不要・Canvas 2D） */
  function fireConfetti(durationMs) {
    var cv = $('#confetti');
    if (!cv || !cv.getContext) { return; }
    var ctx = cv.getContext('2d');
    var dpr = global.devicePixelRatio || 1;
    var W = global.innerWidth, H = global.innerHeight;
    cv.width = W * dpr; cv.height = H * dpr;
    cv.style.width = W + 'px'; cv.style.height = H + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cv.hidden = false;

    var colors = ['#E5384F', '#E39A16', '#1FA97A', '#C9962B', '#0FA3B1'];
    var parts = [];
    var i;
    for (i = 0; i < 110; i++) {
      parts.push({
        x: Math.random() * W, y: -20 - Math.random() * H * 0.5,
        w: 5 + Math.random() * 6, h: 8 + Math.random() * 8,
        vy: 2 + Math.random() * 3.2, vx: -1.4 + Math.random() * 2.8,
        rot: Math.random() * Math.PI, vr: -0.14 + Math.random() * 0.28,
        c: colors[i % colors.length]
      });
    }

    var end = Date.now() + (durationMs || 2600);
    function frame() {
      ctx.clearRect(0, 0, W, H);
      parts.forEach(function (p) {
        p.x += p.vx; p.y += p.vy; p.rot += p.vr;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.fillStyle = p.c;
        ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
        ctx.restore();
      });
      if (Date.now() < end) { global.requestAnimationFrame(frame); }
      else { ctx.clearRect(0, 0, W, H); cv.hidden = true; }
    }
    global.requestAnimationFrame(frame);
  }

  /* ======================================================================
   * 13. ポモドーロ 25分タイマー（第10章①）
   * ====================================================================== */

  /* ヘッダーのチップとトグルの見た目を、状態から毎回組み立て直す。
     個別に show/hide を散らすと、3つの入口のどこかで必ず食い違う。 */
  function updatePomoUi() {
    var p = state.pomodoro;
    var onQuiz = (state.screen === 'quiz');
    var chip = $('#pomodoro-chip'), tg = $('#pomodoro-toggle');
    if (chip) {
      chip.hidden = !onQuiz;
      toggleClass(chip, 'is-off', !p.enabled);
      /* OFF中は時間を出さない。0:00 だと「終わった」と誤読される。 */
      if (!p.enabled) { setText('#pomodoro-time', '--:--'); }
    }
    if (tg) {
      tg.hidden = !onQuiz;
      /* ⏸ / ▶（U+23F8 / U+25B6）は環境によって色付き絵文字に化け、
         トリアージ配色の中で1つだけ意味の違う色が浮く。端末差も大きい。
         現在の状態を ON / OFF の文字で出す。どのフォントでも同じ見た目になる。 */
      /* V1.44：ラベル（⏲タイマー）を消さないよう、状態の span だけ書き換える。
         textContent を丸ごと入れ替えると、HTMLに置いた文字も一緒に消える。 */
      setText('#pomodoro-toggle .pomo-toggle-state', p.enabled ? 'ON' : 'OFF');
      tg.setAttribute('aria-pressed', p.enabled ? 'true' : 'false');
      tg.setAttribute('aria-label', p.enabled ? 'ポモドーロをOFFにする' : 'ポモドーロをONにする');
    }
  }

  /* ON/OFFの唯一の入口。ヘッダーの⏸/▶・設定のスイッチ・経過シートの
     [OFFにする] は、すべてここを通す。 */
  function setPomodoroEnabled(on) {
    var v = !!on;
    state.pomodoro.enabled = v;
    if (v) {
      if (state.screen === 'quiz') { startPomodoro(); }
      toast('ポモドーロをONにしました（25:00から）', 2600);
    } else {
      stopPomodoro();
      toast('ポモドーロをOFFにしました', 2600);
    }
    updatePomoUi();
    var sw = $('#set-pomodoro');
    if (sw) { sw.checked = v; }
    if (state.meta) { state.meta.pomodoro_enabled = v; }
    return S.setMeta('pomodoro_enabled', v);
  }

  /* 「もう続きとは言えない」までの無操作時間。
     出題していない画面（ホーム・設定・分析など）にいるなら5分、
     出題中でも25分（＝1ポモドーロぶん）何もしていなければ切る。 */
  var POMODORO_IDLE_MS = 5 * 60 * 1000;
  var POMODORO_IDLE_QUIZ_MS = POMODORO_MS;

  function markPomodoroActivity() {
    var p = state.pomodoro;
    p.lastActiveAt = Date.now();
    savePomodoroState();
  }

  /* 経過をまたぐ情報だけを保存する。tick や DOM は保存しない。 */
  function savePomodoroState() {
    var p = state.pomodoro;
    return S.setMetaBulk({
      pomo_started_at   : p.running ? p.startedAt : 0,
      pomo_limit_ms     : p.limitMs,
      pomo_last_active  : p.lastActiveAt,
      pomo_notified     : !!p.notified
    }).catch(noop);
  }

  /* 続きとみなせるか。startedAt が無ければ当然 false。 */
  function pomodoroIsFresh() {
    var p = state.pomodoro;
    if (!p.startedAt) { return false; }
    var idleLimit = (state.session && state.session.mode)
      ? POMODORO_IDLE_QUIZ_MS : POMODORO_IDLE_MS;
    var last = p.lastActiveAt || p.startedAt;
    return (Date.now() - last) < idleLimit;
  }

  function startPomodoro() {
    var p = state.pomodoro;
    if (!p.enabled) { updatePomoUi(); return; }
    if (p.running) { return; }
    p.running = true;
    /* モードを跨いでも巻き戻さない。前回から間が空きすぎたときだけ切り直す。 */
    if (!pomodoroIsFresh()) {
      p.startedAt = Date.now();
      p.limitMs = POMODORO_MS;
      p.notified = false;
    }
    p.lastActiveAt = Date.now();
    savePomodoroState();
    updatePomoUi();
    /* 「ONにしたはずだが、どこで始まったのか分からない」を初回だけ潰す。
       毎回出すと通知疲れになるので、1度きり。 */
    S.getMeta('pomodoro_hint_shown', false).then(function (seen) {
      if (seen) { return null; }
      toast('ポモドーロ開始（25:00）。右上の時間をタップすると、休憩・延長・OFFが選べます', 5600);
      return S.setMeta('pomodoro_hint_shown', true);
    }).catch(noop);
    global.clearInterval(p.tick);
    p.tick = global.setInterval(tickPomodoro, 1000);
    tickPomodoro();
  }

  function stopPomodoro() {
    var p = state.pomodoro;
    p.running = false;
    global.clearInterval(p.tick);
    p.tick = null;
    updatePomoUi();
  }

  function tickPomodoro() {
    var p = state.pomodoro;
    if (!p.running) { return; }
    /* 放置されたら、次に始めるときは新しい25分にする。
       ここで止めておかないと、戻ってきた瞬間に「25分経過」が出る。 */
    if (!pomodoroIsFresh()) {
      p.startedAt = 0;
      p.notified = false;
      stopPomodoro();
      savePomodoroState();
      return;
    }
    var left = p.limitMs - (Date.now() - p.startedAt);
    var chip = $('#pomodoro-chip');
    if (left <= 0) {
      setText('#pomodoro-time', '00:00');
      toggleClass(chip, 'is-over', true);
      return;
    }
    toggleClass(chip, 'is-over', left < 60 * 1000);
    setText('#pomodoro-time', formatClock(left));
  }

  function formatClock(ms) {
    var t = Math.max(0, Math.round(ms / 1000));
    var m = Math.floor(t / 60), s = t % 60;
    return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
  }

  /* 経過判定は解説画面の表示時に行う。
     解答の途中でモーダルを割り込ませて思考を折らないための設計。 */
  function checkPomodoro() {
    var p = state.pomodoro;
    if (!p.enabled || !p.running || p.notified) { return false; }
    if (Date.now() - p.startedAt < p.limitMs) { return false; }
    p.notified = true;
    openPomodoroSheet();
    Half2.playAlarm();
    return true;
  }

  /* ヘッダーの時間をタップしたときのシート。
     旧実装は無条件で「25分が経過しました」を出していたため、
     残り20分の時点でタップすると嘘の見出しが出ていた。 */
  function openPomodoroSheet() {
    var p = state.pomodoro;
    var left = p.limitMs - (Date.now() - p.startedAt);
    if (!p.enabled) {
      setText('#pomo-title', 'ポモドーロはOFFになっています');
      setHtml('#pomo-body', '設定の「3. ポモドーロタイマー」からいつでもONにできます。');
    } else if (!p.running) {
      setText('#pomo-title', 'ポモドーロは待機中です');
      setHtml('#pomo-body', '問題を解きはじめると、自動で25分の計測がはじまります。');
    } else if (left > 0) {
      setText('#pomo-title', '集中中：残り ' + formatClock(left));
      setHtml('#pomo-body', '25分たつと、<b>解説画面に切り替わったタイミング</b>でお知らせします。' +
                            '解答の途中では邪魔しません。');
    } else {
      setText('#pomo-title', '25分が経過しました。5分休憩しませんか？');
      setHtml('#pomo-body', 'いったん目を離すと、次の25分の集中が戻りやすくなります。');
    }
    openModal('#modal-pomodoro');
  }

  function extendPomodoro() {
    var p = state.pomodoro;
    p.limitMs += POMODORO_EXTEND_MS;
    p.notified = false;
    closeModals();
    toast('10分延長しました。35分時点でまたお知らせします', 3000);
  }

  function disablePomodoro() {
    closeModals();
    return setPomodoroEnabled(false);
  }

  /* ======================================================================
   * 14. モーダル
   * ====================================================================== */

  /* --- 覆いを開く（V1.64でフォーカスと読み上げを足した） ---
     それまでは表示を切り替えるだけで、
       ・キーボードの位置が覆いの外に残る（Tabで裏の画面をたどれてしまう）
       ・読み上げが「何のダイアログか」を言わない
       ・閉じたあと、どこにいたか分からなくなる
     の3つが起きていた。 */
  function openModal(sel) {
    var layer = $('#modal-layer');
    if (!layer) { return; }
    /* 開く前にいた場所を覚える。閉じたらここへ戻す。 */
    var active = doc.activeElement;
    if (active && active !== doc.body && (!layer.contains(active))) {
      state.modalReturnTo = active;
    }
    $$('#modal-layer > .modal-card').forEach(function (c) { c.hidden = true; });
    var card = $(sel);
    if (card) {
      card.hidden = false;
      /* 見出しをそのまま名前にする。見出しは差し替わることがある
         （確認の覆いは中身を毎回書き換える）ので、開くたびに読み直す。 */
      var title = card.querySelector('.modal-title');
      if (title) { card.setAttribute('aria-label', (title.textContent || '').trim()); }
      state.modalCard = card;
      /* 中の最初の押せるものへ移す。
         入力欄があればそちらを優先する（メモや鍵の入力は、
         開いた直後に打ち始められるほうが速い）。 */
      global.setTimeout(function () {
        if (card.hidden) { return; }
        var first = card.querySelector('input:not([type="hidden"]), textarea, select')
                 || card.querySelector('button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])');
        if (first && typeof first.focus === 'function') {
          try { first.focus({ preventScroll: true }); } catch (e) { first.focus(); }
        }
      }, 30);
    }
    layer.hidden = false;
  }

  /* 覆いの中だけを Tab で回す。外へ出ると、裏の画面を触れてしまう。
     完全な閉じ込めではなく「端で折り返す」だけの軽い実装にしてある。 */
  function trapTab(ev) {
    var layer = $('#modal-layer');
    if (!layer || layer.hidden || ev.key !== 'Tab') { return; }
    var card = state.modalCard;
    if (!card || card.hidden) { return; }
    var list = Array.prototype.filter.call(
      card.querySelectorAll('button:not([disabled]), a[href], input:not([type="hidden"]), textarea, select, [tabindex]:not([tabindex="-1"])'),
      function (el) { return el.offsetWidth > 0 || el.offsetHeight > 0; });
    if (!list.length) { return; }
    var first = list[0], last = list[list.length - 1];
    if (!ev.shiftKey && doc.activeElement === last) { ev.preventDefault(); first.focus(); }
    else if (ev.shiftKey && doc.activeElement === first) { ev.preventDefault(); last.focus(); }
    else if (!card.contains(doc.activeElement)) { ev.preventDefault(); first.focus(); }
  }

  /* --- 取り消せない操作の共通確認（V1.55） ---
     個別にモーダルを増やす方式だと、増やし忘れた操作だけが素通りする。
     実際「すべて元の文に戻す」と「この図を消す」は素通りしていた。
     入口を1つにして、確認が要る操作は必ずここを通す。

     Promise<boolean> を返す。押されなければ false のまま解決する
     （reject にすると呼び出し側が毎回 catch を書くことになり、
       書き忘れたところで未処理の拒否が飛ぶ）。 */
  var confirmResolve = null;

  function confirmAction(cfg) {
    cfg = cfg || {};
    /* 前の確認が開いたままなら、それは「やめる」として畳む。
       畳まないと、古い解決関数が残って別の操作に同意したことになる。 */
    if (confirmResolve) { var prev = confirmResolve; confirmResolve = null; prev(false); }
    setText('#confirm-title', cfg.title || '取り消せません');
    setText('#confirm-body', cfg.body || 'この操作は取り消せません。実行しますか？');
    setText('#confirm-go', cfg.ok || '実行する');
    openModal('#modal-confirm');
    return new Promise(function (resolve) { confirmResolve = resolve; });
  }

  function settleConfirm(yes) {
    if (!confirmResolve) { return; }
    var f = confirmResolve;
    confirmResolve = null;
    f(!!yes);
  }

  /* --- 保存に失敗したことを、消えない形で知らせる（V1.60） ---
     トーストにしない。数秒で消えるので、**記録が残らなかったことに
     気づかないまま解き続ける**ことになる。覆いを出して手を止めさせる。 */
  function openSaveErrorDialog(text) {
    setText('#save-error-body', text);
    openModal('#modal-save-error');
    return null;
  }

  /* V1.53：購入案内。買わせる画面ではなく【止まったのは初見だけ】を
     伝える画面。ここで復習まで止まっていると誤解されると、
     いちばん大事な使い方（毎日の復習）ごと離脱される。 */
  function openBuyDialog() {
    var L = global.NurseLicense;
    setText('#buy-count', (L ? L.FREE_LIMIT : 200) + '問');
    openModal('#modal-buy');
    return null;
  }

  function closeModals() {
    /* 覆いを畳むときは、開いていた確認を必ず「やめる」で解決する。
       解決しないまま閉じると、待っている Promise が永久に残る。 */
    settleConfirm(false);
    /* 保留していた更新の案内を、ここでも拾う（V1.62）。
       拾う場所がホームの描画だけだと、起動ダイアログを閉じたあと
       誰も描画し直さない経路で**保留したまま埋もれる**（実際に埋もれた）。 */
    if (state.swUpdatePending) {
      global.setTimeout(function () { offerUpdate(); }, 500);
    }
    var layer = $('#modal-layer');
    if (layer) { layer.hidden = true; }
    $$('#modal-layer > .modal-card').forEach(function (c) { c.hidden = true; });
    state.modalCard = null;
    /* 開く前にいた場所へ戻す。戻さないと、閉じたあと
       キーボードの位置が消えて、先頭からたどり直しになる。
       その要素がもう無いこともあるので、必ず存在を確かめる。 */
    var back = state.modalReturnTo;
    state.modalReturnTo = null;
    if (back && doc.body.contains(back) && typeof back.focus === 'function') {
      try { back.focus({ preventScroll: true }); } catch (e) { back.focus(); }
    }
  }

  /* ======================================================================
   * 15. イベント束ね（イベント委譲で1度だけ張る）
   * ====================================================================== */

  function bindGlobalEvents() {
    /* --- ヘッダー --- */
    on($('#btn-back'), 'click', function () { goBack(); });
    /* テーマの切替はヘッダーから外し、設定 4. に一本化した（V1.43）。
       束ねは残す：設定画面の中にも同じ id のボタンを置く余地があるため、
       $() が null を返しても on() は何もしない。 */
    on($('#btn-theme'), 'click', function () { cycleTheme(); });
    /* V1.41：どの画面からでも1タップでホームへ。
       「戻る」は1段ずつしか戻れないので、深く潜ったときに
       ホームまで何度も押させることになっていた。
       出題中に押されたら、セッションを畳んでから戻る（畳まないと
       裏で問題を抱えたまま別のモードへ入れてしまう）。 */
    on($('#btn-home'), 'click', function () {
      if (state.screen === 'quiz') { endSession(); }
      go('home', { replace: true });
      refreshHome().catch(noop);
    });
    on($('#btn-settings'), 'click', function () { Half2.openSettings(); });
    /* V1.53：無料枠まわり。案内は1箇所（openBuyDialog）に集める。 */
    on($('#free-gate-btn'), 'click', function () { openBuyDialog(); });
    /* 保存に失敗した画面から、そのままバックアップへ逃がす（V1.60）。
       領域が満杯のときこそ、先に書き出しておかないと危ない。 */
    on($('#save-error-backup'), 'click', function () {
      closeModals();
      if (Half2 && Half2.runBackup) { Half2.runBackup(); }
    });
    on($('#buy-open'), 'click', function () {
      closeModals();
      global.open(BUY_URL, '_blank', 'noopener');
    });
    on($('#buy-have'), 'click', function () {
      closeModals();
      Half2.openSettings().then(function () {
        var t = $('#lic-key'); if (t) { t.focus(); }
      }).catch(noop);
    });

    /* --- 自作の図解画像 --- */
    on($('#btn-userimg-pick'), 'click', function () { pickUserImage(); });
    on($('#btn-report'), 'click', function () { reportQuestion(); });
    on($('#userimg-file'), 'change', function (ev) {
      var file = ev.target.files && ev.target.files[0];
      if (file) { saveUserImage(file); }
    });
    on($('#btn-userimg-del'), 'click', function () { removeUserImage(); });
    on($('#btn-edit-overall'), 'click', function () {
      var q = state.current.question;
      if (q) { Half2.openMemoEditor('question', q.q_id); }
    });
    on($('#pomodoro-chip'), 'click', function () { openPomodoroSheet(); });
    on($('#pomodoro-toggle'), 'click', function (ev) {
      ev.stopPropagation();
      setPomodoroEnabled(!state.pomodoro.enabled);
    });

    /* --- ホームの動線（data-action に集約） --- */
    on(doc, 'click', function (ev) {
      var el = ev.target.closest ? ev.target.closest('[data-action]') : null;
      if (!el) { return; }
      handleAction(el.getAttribute('data-action'), el);
    });

    /* --- 出題フェーズ --- */
    on($('#choice-list'), 'click', function (ev) {
      var card = ev.target.closest('.choice-card');
      if (!card) { return; }
      var mark = ev.target.closest('.choice-mark');
      if (mark) { ev.stopPropagation(); onChoiceMarkTap(card, mark); return; }
      onChoiceTap(card);
    });
    on($('#numeric-input'), 'input', function (ev) {
      var btn = $('#btn-confirm');
      if (btn) { btn.disabled = String(ev.target.value).trim() === ''; }
    });
    on($('#btn-confirm'), 'click', function () { confirmAnswer(); });
    on($('#q-star'), 'click', function () { toggleCurrentQuestionStar(); });

    /* --- 画像アコーディオン --- */
    on($('#btn-img-toggle'), 'click', function () {
      var panel = $('#q-image-panel');
      var t = $('#btn-img-toggle');
      if (!panel) { return; }
      var open = panel.hidden;
      panel.hidden = !open;
      t.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    on($('#btn-img-close'), 'click', function () { hide('#q-image-panel'); });
    on($('#q-image'), 'click', function () { hide('#q-image-panel'); });

    /* --- 解説フェーズ --- */
    on($('#rv-star'), 'click', function () { toggleCurrentQuestionStar(); });
    on($('#btn-detail'), 'click', function () { toggleDetail(); });

    /* 選択肢ブロック内：★・評価ボタン・タグ */
    on($('#rv-choices'), 'click', function (ev) {
      /* テーマタグは、共通表示のとき .cx の外側に出るため先に拾う。
         .cx の中だけを見ていると、共通行のタグが反応しなくなる。 */
      var tag0 = ev.target.closest('.tag-pill');
      if (tag0) { Half2.openTagSheet(tag0.getAttribute('data-tag')); return; }

      var block = ev.target.closest('.cx');
      if (!block) { return; }
      var id = block.getAttribute('data-atom-id');

      var star = ev.target.closest('.cx-star');
      if (star) { toggleAtomStarById(id, star); return; }

      var pen = ev.target.closest('.cx-memo-btn');
      if (pen) { Half2.openMemoEditor('atom', id); return; }

      var fg = ev.target.closest('.btn-forgot');
      if (fg) { forgetAtom(id); return; }

      var evb = ev.target.closest('.eval-btn');
      if (evb && !evb.disabled) { setEval(id, evb.getAttribute('data-eval')); return; }

    });

    /* 固定バーのサマリー：タップでその肢まで滑らせる */
    on($('#tz-summary'), 'click', function (ev) {
      var d = ev.target.closest('.sum-dot');
      if (d) { scrollToChoice(parseInt(d.getAttribute('data-num'), 10)); }
    });

    /* ポップアップはタップで即座に消せる */
    on($('#verdict-pop'), 'click', function () { hideVerdictPopup(); });
    on($('#rv-stem-expand'), 'click', function () {
      setText('#stem-overlay-text', state.current.question ? state.current.question.stem : '');
      show('#stem-overlay');
    });
    on($('#stem-overlay-close'), 'click', function () { hide('#stem-overlay'); });
    on($('#stem-overlay'), 'click', function (ev) {
      if (ev.target.id === 'stem-overlay') { hide('#stem-overlay'); }
    });

    /* --- サムゾーン --- */
    on($('#btn-next'), 'click', function () { nextQuestion(); });

    /* --- モーダル共通 --- */
    on($('#confirm-go'), 'click', function () {
      /* 先に解決してから畳む。順序が逆だと closeModals() が
         「やめる」として畳んでしまい、押しても何も起きない。 */
      var f = confirmResolve;
      confirmResolve = null;
      closeModals();
      if (f) { f(true); }
    });
    on($('#modal-layer'), 'click', function (ev) {
      if (ev.target.id === 'modal-layer') { closeModals(); return; }
      if (ev.target.closest('[data-close]')) { closeModals(); }
    });
    on($('#boot-yes'), 'click', function () {
      var action = $('#modal-boot').dataset.action;
      closeModals();
      if (action === 'review') { startSession({ mode: 'review' }); }
      else { Half2.openRandomSelect(); }
    });
    on($('#done-next'), 'click', function () {
      closeModals();
      Half2.showTop3Popin();
    });
    on($('#nag-review'), 'click', function () {
      closeModals();
      state.nagAction = null;
      startSession({ mode: 'review' });
    });
    on($('#nag-go'), 'click', function () {
      var a = state.nagAction;
      state.nagAction = null;
      closeModals();
      if (a) { runAction(a, null); }
    });
    on($('#pomo-break'), 'click', function () { closeModals(); Half2.startBreak(5); });
    on($('#pomo-extend'), 'click', function () { extendPomodoro(); });
    on($('#pomo-off'), 'click', function () { disablePomodoro(); });
    on($('#sw-reload'), 'click', function () { acceptUpdate(); });

    /* --- キーボード（PC操作の補助） --- */
    /* --- Escape で覆いを畳む（V1.55・§4-14 の二重の経路） ---
       覆いが残る事故は白画面より重い。背景タップは指では届くが、
       PCで開いたときに逃げ道が［やめる］ボタン1つしかなかった。
       出題中の判定より前に置く（出題中でも覆いは畳めなければならない）。 */
    on(doc, 'keydown', function (ev) { trapTab(ev); });

    on(doc, 'keydown', function (ev) {
      if (ev.key !== 'Escape' && ev.key !== 'Esc') { return; }
      var layer = $('#modal-layer');
      if (layer && !layer.hidden) { ev.preventDefault(); closeModals(); }
    });

    on(doc, 'keydown', function (ev) {
      if (state.screen !== 'quiz') { return; }
      var phase = $('#screen-quiz').getAttribute('data-phase');
      if (phase === 'answer') {
        if (/^[1-9]$/.test(ev.key)) {
          var card = $('#choice-list .choice-card[data-num="' + ev.key + '"]');
          if (card) { onChoiceTap(card); }
        } else if (ev.key === 'Enter') { confirmAnswer(); }
        return;
      }
      if (/^[1-9]$/.test(ev.key)) { scrollToChoice(parseInt(ev.key, 10)); }
      else if (ev.key === 'd') { toggleDetail(); }
      else if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); nextQuestion(); }
    });

    /* --- 復帰時に復習数を取り直す（他端末・時間経過への追随） --- */
    on(doc, 'visibilitychange', function () {
      if (doc.visibilityState === 'visible' && state.booted && state.screen === 'home') {
        refreshHome().catch(noop);
        return;
      }
      /* 隠れる直前に上げる（V1.49）。
         自動同期はホームへ来た8秒後にしか走らないので、
         「学習を終える→ホーム→すぐ閉じる」がまるごと未同期だった。
         ここが最後の機会になる。await はしない（できない）。 */
      if (doc.visibilityState === 'hidden' && state.booted) { syncOnHide(); }
    });
    /* visibilitychange が来ない環境のための二重の網（§4-14 と同じ考え方）。 */
    on(global, 'pagehide', function () { if (state.booted) { syncOnHide(); } });
  }

  /* 画面を閉じる直前の同期。後半モジュールが持っているので、無ければ何もしない。 */
  function syncOnHide() {
    var H2 = global.Half2Impl;
    if (!H2 || !H2.syncOnHide) { return; }
    try { H2.syncOnHide(); } catch (e) { /* 閉じる途中なので黙って諦める */ }
  }

  /* ホーム画面などの data-action を1箇所で捌く。
     後半モジュールが担当する画面へは Half2 経由で委譲する。 */
  /* 復習が溜まったまま他の学習モードへ行こうとしたときの伴走。
     20件（＝約5問ぶん、所要およそ4分）を下限にする。これ未満で出すと
     毎回出て意味を失う。ブロックはしない。1日1回だけ。 */
  var REVIEW_NAG_MIN = 20;
  var NAG_TARGETS = { 'go-random': 1, 'go-exam': 1 };

  function maybeNagReview(action) {
    return Promise.all([S.getDueCount(), S.getMeta('review_nag_day', 0)]).then(function (r) {
      var due = r[0], last = r[1];
      if (due < REVIEW_NAG_MIN) { return true; }
      var h = (state.meta && typeof state.meta.day_boundary_hour === 'number')
        ? state.meta.day_boundary_hour : 4;
      var today = S.util.dayStart(Date.now(), h);
      if (last === today) { return true; }
      return S.setMeta('review_nag_day', today).then(function () {
        setText('#nag-count', due);
        state.nagAction = action;
        openModal('#modal-review-nag');
        return false;
      });
    }).catch(function () { return true; });
  }

  function handleAction(action, el) {
    if (NAG_TARGETS[action]) {
      return maybeNagReview(action).then(function (proceed) {
        return proceed ? runAction(action, el) : null;
      });
    }
    return runAction(action, el);
  }

  function runAction(action, el) {
    var r = routeAction(action, el);
    /* 画面を開けなかったときに未処理のPromise拒否を残さない。
       DBが使えない環境でも、押した結果が黙って消えないようにする。 */
    if (r && typeof r.catch === 'function') {
      return r.catch(function (e) {
        console.error('[handleAction:' + action + ']', e);
        toast('この画面を開けませんでした：' + (e && e.message ? e.message : e), 4200);
      });
    }
    return r;
  }

  function routeAction(action, el) {
    switch (action) {
      case 'go-review':    return startSession({ mode: 'review' });
      case 'go-random':    return Half2.openRandomSelect();

      case 'go-knock':     return Half2.openKnockDialog();
      case 'go-exam':      return Half2.openExamList();
      case 'go-search':    return Half2.openSearch();
      case 'go-starred':   return Half2.openStarredNote();
      case 'go-dashboard': return Half2.openDashboard();
      case 'go-settings':  return Half2.openSettings();
      case 'go-home':      return go('home', { replace: true });
      default:
        console.warn('[handleAction] 未定義のアクション:', action, el);
        return Promise.resolve();
    }
  }

  /* ======================================================================
   * 16. 後半モジュールのインターフェース（スタブ）
   *
   *  20260815_main_後半_V1.00.js は、読み込み時に下記メソッドを
   *  window.Half2 に上書き代入すること。前半はここ以外から後半を呼ばない。
   *  未実装のまま呼ばれた場合は、落とさずトーストで知らせる。
   * ====================================================================== */

  function pending(name) {
    return function () {
      toast('「' + name + '」は後半モジュール（20260815_main_後半_V1.00.js）で実装します', 3200);
      return Promise.resolve(null);
    };
  }

  /* ----------------------------------------------------------------------
   * 後半モジュール用フック。既定は null＝通常の学習フロー。
   *   afterGrade(current)  : false を返すと解説フェーズの描画を抑止する
   *   afterCommit(q, sess) : 1問ぶんの評価コミット直後に呼ばれる
   *   onFinish(session)    : true を返すと既定のセッション終了処理を抑止する
   * -------------------------------------------------------------------- */
  /* onAbort：最後まで行かずにセッションを畳んだときに呼ぶ（V1.42）。
     onFinish は「出題を終えた」ときにしか呼ばれないので、
     途中で戻った場合に後半が張った時計やバーが止められず、
     ホームへ戻ってもテーマ別弱点ノックの残り時間が動き続けていた。 */
  var hooks = { afterGrade: null, afterCommit: null, onFinish: null, onAbort: null };

  var Half2 = {
    /* --- その場ガイド（初回だけ・1つずつ） ---
       tip(id) : Promise<void>   その要素が「いま押してほしい」瞬間に1度だけ出す */
    tip : function () { return Promise.resolve(); },

    /* --- 解説の書き換え（上書き型メモ） ---
       openMemoEditor(kind, id) : Promise<void>   kind='atom'|'question'
       mdLite(text) : string                      **太字** ==マーカー== - 箇条書き */
    openMemoEditor : function () { return Promise.resolve(); },

    /* 解説画面の追加ガイドを1つだけ出す（サマリー→詳しい解説→書き換え→★→タグ） */
    tipReviewExtra : function () { return Promise.resolve(); },
    mdLite : function (t) { return '<p>' + escapeHtml(t == null ? '' : t) + '</p>'; },

    /* --- ランダムモード（第9章①：単元・大項目2段階UI） ---
       openRandomSelect() : Promise<void>            ランダム選択画面を開く
       startRandom(scope, count) : Promise<void>     scope={field,value}|null */
    openRandomSelect : pending('ランダムモード'),
    startRandom      : pending('ランダム出題'),

    /* --- 3階層ツリー（第3章①） ---
       startByScope(field, value) : Promise<void>    field='unit'|'major'|'medium' */
    startByScope : pending('範囲を指定した出題'),

    /* --- 分析ダッシュボード（第6章①） ---
       openDashboard() : Promise<void>
       renderDashboard(level, metric) : Promise<void>  level='unit'|'major'|'medium'|'sub_item'
       setPreferFrequent(on) : Promise<void>           頻出優先トグル */
    openDashboard     : pending('ダッシュボード'),
    renderDashboard   : pending('ダッシュボード描画'),
    setPreferFrequent : pending('頻出優先トグル'),

    /* --- キーワード検索 ＆ テーマ別 弱点分析（第12章「74概念アナライザー」） ---
       openSearch() : Promise<void>
       runSearch(keyword) : Promise<void>
       startSearchDrill(qIds) : Promise<void>          評価スキップ演習（mode='search'）
       renderConceptRanking(order) : Promise<void>     order='low'|'high'|'unlearned'
       showTop3Popin() : Promise<void>                 最優先で埋めたいテーマ TOP 3 */
    openSearch          : pending('キーワード検索'),
    runSearch           : pending('キーワード検索'),
    startSearchDrill    : pending('検索結果の演習'),
    renderConceptRanking: pending('テーマ別 弱点分析'),
    showTop3Popin       : pending('最優先で埋めたいテーマ TOP 3'),

    /* --- テーマ別 弱点ノック（第7章「概念別弱点ノック」） ---
       openKnockDialog() : Promise<void>              5分/10分の選択ダイアログ
       startKnock(tag, minutes) : Promise<void>
       finishKnock(solved) : Promise<void>            時間経過時のサマリー */
    openKnockDialog : pending('テーマ別 弱点ノック'),
    startKnock      : pending('テーマ別 弱点ノック'),
    finishKnock     : pending('ノック終了サマリー'),

    /* --- マイ★お気に入りノート（第13章） ---
       openStarredNote() : Promise<void>
       renderStarredNote(filter) : Promise<void>      filter='all'|'question'|'atom' */
    openAllClearedSheet: pending('全問読破の案内'),
    openStarredNote   : pending('マイ★お気に入りノート'),
    renderStarredNote : pending('★ノート描画'),

    /* --- 力試しモード（第11章） ---
       openExamList() : Promise<void>
       startExam(examId) : Promise<void>              'mock_30'|'mock_60'|'mock_120'|'mock_weak'
       gradeExam(answers) : Promise<result>           Scheduler.applyExamResult を肢ごとに適用
       showExamResult(result) : Promise<void>         必修80% / 一般180点の合否判定 */
    openExamList   : pending('力試しモード'),
    startExam      : pending('模擬試験'),
    gradeExam      : pending('模試の採点'),
    showExamResult : pending('模試の結果表示'),

    /* --- 設定・データ（第14章） ---
       openSettings() : Promise<void>
       runImport(text) : Promise<report>              Storage.importText のラッパ
       runBackup() / runRestore() / runResetAll() : Promise<void>
       setDayBoundary(hour) : Promise<void> */
    openSettings : pending('設定'),
    runImport    : pending('自作問題データの取り込み'),
    runBackup    : pending('バックアップ'),
    runRestore   : pending('復元'),
    runResetAll  : pending('全初期化'),
    setDayBoundary: pending('生活リズム設定'),

    /* --- ポモドーロの休憩系（第10章②） ---
       startBreak(minutes) : Promise<void>            5分休憩／長休憩の共通入口
       openLongBreakDialog() : Promise<void>          4セッション完了時
       requestNotifyPermission() : Promise<boolean>
       playAlarm() : void                             アラーム音の再生 */
    startBreak             : pending('休憩タイマー'),
    openLongBreakDialog    : pending('長めの休憩'),
    requestNotifyPermission: pending('通知の許可'),
    playAlarm              : function () { /* 後半で差し替え。未実装時は無音で続行する */ },

    /* --- オンボーディング（第8章） ---
       startOnboarding() : Promise<void>              即時体験型チュートリアル
       showCoachMark(targetSel, text, opts) : Promise<void>
       resumeCheckpoint() : Promise<void>             中断からの復帰
       （V1.56：runUiTour は撤去。その場ガイドへ置き換え済み） */
    startOnboarding  : pending('オンボーディング'),
    showCoachMark    : pending('ガイド吹き出し'),
    resumeCheckpoint : pending('チュートリアル復帰')
  };

  /* ======================================================================
   * 17. 公開API
   * ====================================================================== */

  var Main = {
    APP_BUILD    : APP_BUILD,
    INTERLOCK_MS : INTERLOCK_MS,

    boot          : boot,
    bindOnce      : bindOnce,
    showFatal     : showFatal,
    showFatalNow  : showFatalNow,
    state         : state,

    /* 画面 */
    go            : go,
    goBack        : goBack,
    refreshHome   : refreshHome,
    explainMode   : explainMode,
    renderAtomBody: renderAtomBody,
    hideSplash    : hideSplash,
    splashSay     : splashSay,
    resolveSplash : resolveSplash,
    renderRandomCard: renderRandomCard,
    randomCardState : randomCardState,
    RANDOM_CARD   : RANDOM_CARD,
    applyTheme    : applyTheme,
    cycleTheme    : cycleTheme,
    applyVisualTheme: applyVisualTheme,
    setHeaderCrumb: setHeaderCrumb,
    updateScanMeter: updateScanMeter,
    refreshScanSlot: refreshScanSlot,
    updateAppBadge: updateAppBadge,

    /* 出題〜解説 */
    startSession  : startSession,
    endSession    : endSession,
    stepForward   : stepForward,
    finishSession : finishSession,
    hooks         : hooks,
    renderQuestion: renderQuestion,
    armInterlock  : armInterlock,
    confirmAnswer : confirmAnswer,
    renderReview  : renderReview,
    toggleDetail  : toggleDetail,
    showVerdictPopup: showVerdictPopup,
    hideVerdictPopup: hideVerdictPopup,
    prepareExplanationHtml: prepareExplanationHtml,
    prepareOverallHtml: prepareOverallHtml,
    levelFacts    : levelFacts,
    levelTargetNote: levelTargetNote,
    studyDays     : studyDays,
    openPomodoroSheet: openPomodoroSheet,
    maybeNagReview: maybeNagReview,
    REVIEW_NAG_MIN: REVIEW_NAG_MIN,
    prepareAtomExplanation: prepareAtomExplanation,
    MERMAID_SOURCES: MERMAID_SOURCES,
    renderAtomBody: renderAtomBody,
    renderChoiceBlocks: renderChoiceBlocks,
    unionTags     : unionTags,
    fitStemHeight : fitStemHeight,
    renderMermaid : renderMermaid,
    renderUserImage: renderUserImage,  pickUserImage: pickUserImage,
    reportQuestion: reportQuestion,  reportBody: reportBody,
    isBundledQuestion: isBundledQuestion,
    userImagePos: userImagePos,
    placeUserImageSection: placeUserImageSection,
    USERIMG_SLOTS: USERIMG_SLOTS,
    overallBodyHtml: overallBodyHtml,
    renderDetailBlock: renderDetailBlock,
    saveUserImage : saveUserImage,
    removeUserImage: removeUserImage,
    loadMermaid   : loadMermaid,

    /* サムゾーン */
    scrollToChoice: scrollToChoice,
    renderSummary : renderSummary,
    commitDecisionFor: commitDecisionFor,
    thinkMsForCurrent: thinkMsForCurrent,
    fmtDueShort   : fmtDueShort,
    forgetAtom    : forgetAtom,
    setEval       : setEval,
    nextQuestion  : nextQuestion,
    toggleCurrentQuestionStar: toggleCurrentQuestionStar,
    toggleAtomStarById       : toggleAtomStarById,

    /* 共通部品（後半から使う） */
    openModal     : openModal,
    /* V1.62：更新の受け渡し。テストから出題中の割り込みを確かめる。 */
    offerUpdate   : offerUpdate,
    acceptUpdate  : acceptUpdate,
    /* V1.53：ライセンス。後半（設定画面）から呼ぶ。 */
    openBuyDialog : openBuyDialog,
    openSaveErrorDialog : openSaveErrorDialog,
    /* V1.55：取り消せない操作の共通確認。後半からも使う。 */
    confirmAction : confirmAction,
    licGate       : licGate,
    refreshFreeGate: function () { renderFreeGate(state.homeState); },
    BUY_URL       : BUY_URL,
    closeModals   : closeModals,
    toast         : toast,
    fireConfetti  : fireConfetti,
    escapeHtml    : escapeHtml,
    circled       : circled,
    formatClock   : formatClock,
    $             : $,
    $$            : $$,
    on            : on,

    /* ポモドーロ */
    randomBadgeText: randomBadgeText,
    isCountdown   : isCountdown,
    decideFormat  : decideFormat,
    startPomodoro : startPomodoro,
    stopPomodoro  : stopPomodoro,
    markPomodoroActivity: markPomodoroActivity,
    pomodoroIsFresh     : pomodoroIsFresh,
    savePomodoroState   : savePomodoroState,
    checkPomodoro : checkPomodoro,
    updatePomoUi  : updatePomoUi,
    setPomodoroEnabled: setPomodoroEnabled,
    numHtml       : numHtml,

    /* 後半モジュールの差し込み口 */
    Half2         : Half2
  };

  global.Main = Main;
  global.Half2 = Half2;

  /* 束ねを先に、起動を後に。boot() が落ちても操作は生きている。
     本ファイルは <body> 末尾で読むため、この時点で必要な要素は揃っている。
     要素が無い読み込み方をされた場合だけ DOMContentLoaded を待つ。 */
  if ($('#app') && $('#screen-home')) { bindOnce(); }
  else { ready(bindOnce); }

  ready(function () {
    bindOnce();                 /* 冪等。上で済んでいれば何もしない */
    boot().catch(noop);
  });

})(typeof window !== 'undefined' ? window : this);
