# -*- coding: utf-8 -*-
"""過去問仕上げの出力を機械で検証する（V1.25）。

V1.25（2026-09-09）：「作り直しのうち新しい方だけを見る」の判定を、
ファイルの更新時刻から **ファイル名の番号** に変えた。更新時刻で決めていたため、
同じフォルダに同じコマンドを打っても環境によって結果が変わっていた
（実測：Linux NG 33問／Windows NG 98問。差はチェック2だけ）。詳しくは本文の該当箇所。
V1.24 は消していない。

V1.24：確度Xの行を**引いただけ**でNGにしていた。

  §10 が禁じているのは「確度Xの行の**数値を書くこと**」であって、
  その行を見ることではない。値が割れている項目について
  「割れているので数値は示さない」と説明するために id を控えるのは、
  むしろ規則どおりの振る舞い。

  実測：6件のうち**3件は数値を1つも書いていなかった**（引いただけ）。
    第112回 午前問50（H033 血清アルブミン）    表の値 3.6/3.8/4.8/5.0 → 本文に0個
    第112回 午後問91（H031 白血球数）          表の値 3300/4000/8600/9000 → 本文に0個
    第112回 午後問91（H034 血清ナトリウム）    表の値 135/138/145 → 本文に0個

  残る3件は本物だった。
    第111回 午前問8（H024 乳児の脈拍）    選択肢に無い「120」を書いている
    第112回 午後問61（H049 子宮復古）      「4〜6週間（あるいは6〜8週間）」と両方書いた
    第114回 午前問112（H049）             H049 は子宮復古の行なのに後陣痛の値として引用

  **その行の数値が本文に出ているときだけ NG**。出ていなければ警告に落とす。

V1.23：論点キーワードの照合を、NG から**警告**へ落とす。

V1.23：論点キーワードの照合を、NG から**警告**へ落とす。

  必修のNGに残っていた3件を1つずつ読んだところ、**3件とも解説は正しく書けていた**。
  外れていたのは論点キーワードとの**文字列一致だけ**。

    論点 ['低温','危険']  解説「30℃は体温に比べて**低く**、…**リスク**がある」
                          → 「低温」「危険」の字は無いが、同じことを言っている
    論点 ['遅すぎる']     解説「生後8〜10日は…体重が増加している時期であるため誤り」
                          → 「遅すぎる」の字は無いが、時期が違うことは書けている
    論点 ['積み木']       肢は「10か月」、解説は「首がすわる基準月齢としては遅すぎる」
                          → **論点キーワードのほうが問題とずれている**

  言い換えを機械で判定することはできない。3/3が偽陽性なら、
  NGのまま再投入しても作問は同じものを返すだけで、PADの実行回数が無駄になる。
  **数は出し続けるが、再投入の対象からは外す**（警告）。

  戻したいときは REPORT_KW_AS_NG を True にするだけでよい。

V1.22：**入力に選択肢が無い問題**で、読み違えを毎回NGにしていた。

V1.22：**入力に選択肢が無い問題**で、読み違えを毎回NGにしていた。

  選択肢が図・写真だけの問題は、機械抽出の時点で肢が1つも取れていない
  （atoms が0個・is_correct も無い）。そこで検証は
      正答 [] ／ LMの自答 [4]
  を比べて「読み違え」と数えていた。**比べる相手がいない。**

  実測：必修250問のうち3問がこれ。
      第113回 午後問21 ／ 第115回 午前問16 ／ 第115回 午前問22
  どれも入力の肢数が0。第113回午後問21 は除外リストにも
  「no_answer・削除」で載っている問題。

  チェック2 は V1.14 で「0肢のときは数を見ない」と直してあったが、
  チェック11 は直っていなかった。同じ扱いにそろえる。

V1.21：桁を省いた同じ数値を、別の数値として数えていた。

V1.21：桁を省いた同じ数値を、別の数値として数えていた。

  実例（第114回 午後問90・BMIの計算問題）
    evidence   第114回 午後問90 の正答：23.4（計算式：60÷1.6^2＝23.437...）
    全体解説   … ＝ 23.4375... となる。小数点以下第2位を四捨五入するため …
  evidence の「23.437」と解説の「23.4375」は同じ数を指しているのに、
  文字列が違うので「裏づけが無い」と数えていた。

  そこで、**小数の桁を落としただけ**のものは同じとみなす。
    ・どちらかがどちらかの**前方一致**で
    ・かつ短いほうが3桁以上（1桁2桁の偶然の一致を拾わない）
    ・かつ小数点をまたぐ（整数どうしの前方一致は別の数。9,640 と 9,600 は別）

  実測：35件のうち4件がこれ。残り31件は本物なので、そのまま作問へ返す。

V1.20：「書き換わっている」に、**どこがどう違うか**を添える。

V1.20：「書き換わっている」に、**どこがどう違うか**を添える。

  これまでは「stem が書き換わっている」としか出さず、
  人が入力バッチを開いて突き合わせるまで中身が分からなかった。
  実際に29件を1つずつ開いて読むのに、それなりの手間がかかった。

  読んでみると、すべて**作問の写し崩れ**だった。入力は正しい。

    倦怠感  → 倦慢感        来院 → 来来        返事 → 返気
    増悪   → 増増悪        おにぎり → おおにぎり   順調 → 順順
    レクリエーション → レキュリエーション
    訪問看護を利用 → 訪問看護利用（助詞が落ちた）
    重症度分類 → 重症度分類的（字が増えた）

  「1文字だけの違いは入力側の欠字を補ったのだろう」という見立ては**外れ**。
  1文字だからと通すと、これを全部見逃す。だから通さない。

  そのかわり、差分を指摘文に載せる。作問へ返すときにそのまま使える。

V1.19：**候補側が途中で切れている**。切れた候補で作問を責めない。

V1.19：**候補側が途中で切れている**。切れた候補で作問を責めない。

  出題基準PDFの抽出で、小項目の末尾が落ちているものがある。

    候補   災害各期における要支援者を含むすべての被災者へ      ← 「の看護」が無い
    出力   災害各期における要支援者を含むすべての被災者への看護  ← こちらが正しい

    候補   医療・看護の標準化（標準看護計画、クリニカルパ      ← 「ス）」が無い
    出力   医療・看護の標準化（標準看護計画、クリニカルパス）

  作問は正しく書いているのに、機械が「候補外」と数えていた。
  正のほうが壊れているので、機械には直せない。
  そこで、候補が出力の**前方一致**になっているときは通す。

  切れた候補そのものは、入力バッチを作り直すときに直す（別レーンの仕事）。

V1.18：小項目の比較にも中黒の正規化を掛ける。**また中黒だった。**

V1.18：小項目の比較にも中黒の正規化を掛ける。**また中黒だった。**

  出題基準PDFから抽出した候補側は半角中黒 `･`(U+FF65)、
  作問の出力は全角中黒 `・`(U+30FB)。人間の目には同じ字。

    候補   人工的水分･栄養補給法＜AHN＞
    出力   人工的水分・栄養補給法＜AHN＞   ← これで「候補外」にされていた

  タグでは `·`(U+00B7)、小項目では `･`(U+FF65)。出どころが違うので化け方も違う。
  マスタと一字一句で比べる欄は、すべて normtag() を通す。

V1.17：小項目（sub_item）もタグと同じ2段階にする。

V1.17：小項目（sub_item）もタグと同じ2段階にする。

  sub_candidates も問題ごとの狭い目安リスト。
  出題基準の小項目そのものを選んでいるのに「候補外」と数えていた。

  実例（どれも出題基準に実在する文言）
    人工的水分・栄養補給法〈AHN〉
    災害各期における要支援者を含むすべての被災者への看護
    医療・看護の標準化（標準看護計画、クリニカルパス）

  小項目のマスタはアプリ側に無い（TAXONOMY_MASTER は3階層まで）。
  そこで**全バッチの sub_candidates を集めた全体**をマスタ代わりにする。
  1200問ぶんを集めれば、出題基準の小項目のほぼ全体になる。

    全体に無い          → NG（打ち間違い・作り話の疑い）
    全体にあるが候補外   → 警告（別の中項目の小項目を選んでいる、程度）

V1.16：タグの「候補外」を2段階に分ける。**候補外＝間違い、ではなかった。**

V1.16：タグの「候補外」を2段階に分ける。**候補外＝間違い、ではなかった。**

  【何が起きていたか】
    tag_candidates は問題ごとに2〜3個しか無い、ごく狭い目安リスト。
    作問がその外の**正しいタグ**を選ぶと、機械は一律 NG にしていた。

    実測：候補外と数えた17種のうち、**13種は概念タグマスタに実在していた**。
      #与薬・注射・点滴管理 ／ #栄養投与・経管栄養管理 ／ #慢性心不全・自己管理
      #急性呼吸不全・人工呼吸 ／ #慢性呼吸不全・COPD ／ #糖尿病・血糖自己管理
      #小児の先天性・慢性疾患 ／ #疼痛評価・オピオイド管理 ／ #感染予防・標準予防策
      #医療保険・福祉制度 ほか

    アプリはマスタにあるタグなら集計する。捨てないので、実害が無い。
    本当に困るのは**マスタに無いタグ**（アプリが黙って捨てる）だけ。

    さらに中黒の化けがあった。`·`(U+00B7) と `・`(U+30FB) は別の字で、
    「#医療安全·アクシデント防止」はマスタの「#医療安全・アクシデント防止」と
    一字違い。人間の目には同じに見える。

  そこで
    マスタに無い          → NG（アプリが捨てる。直さないと消える）
    マスタにあるが候補外   → 警告（集計される。狙いと違うかもしれない、程度）
  中黒・全角空白は正規化してから比べる。

  概念タグマスタの正はアプリ側 questions.js の CONCEPT_TAGS_MASTER（103個）。
  ここで再定義しない（§24 データ契約は二重に持たない）。

V1.15：**同じ問題が何度も作られている**。source ごとに、いちばん新しい出力だけを見る。

V1.15：**同じ問題が何度も作られている**。source ごとに、いちばん新しい出力だけを見る。

  【なぜ】1165問の中で、983 source のうち **146 が重複**していた（最大5回）。
    作問が同じ問題を作り直しているためで、古いほうには直る前の欠点が残っている。

    実例：第112回 午後問56
      G0141.json（09-06 06:34）evidence に「確度C」の注記が **無い**
      H0123.json（09-06 17:08）evidence に「確度C・原典未特定」が **ある**

    検証は全ファイルを individually に見ていたので、**古いほうを NG に数えていた**。
    結合ツールは「更新時刻の新しい方を採る」ので、
    NG に数えた古い出力は**そもそも配布物に入らない**。

    実測：この重複のせいで「確度Cの注記が無い」が84件出ていたが、
    84件すべてが古いほうの出力だった。作問レーンは既に直っている。
    プロンプトを直す必要は無かった。

  結合と同じ規則（source ごとに新しい方）に揃える。
  古いほうを見たいときは --all を付ける。

V1.14：2つを「書き換え」と数えるのをやめる。

V1.14：2つを「書き換え」と数えるのをやめる。どちらも**そうするのが正しい**もの。

  ①「次の文を読み115〜117の問いに答えよ。」の1行を、出力が落としている（実測37件の一部）
     アプリは連問を1問ずつ出すので、この指示文は画面上で意味を持たない。
     事例文の本体は残っている。**落とすほうが親切**。
     比べるときは両側からこの1行を外す。

  ② 選択肢の数が 0→4（実測7件）
     入力の肢が0個なのは「選択肢が図」の問題で、
     Claude が図を読んで起こしたぶんが出力に入っている（ext_v4）。
     **増えているのが正しい**。入力が0肢のときは数を見ない。

  緩めているのではなく、**そうであるべきものを間違いと数えていた**のをやめる。
  本文の書き換えはこれまでどおり検出する。

V1.13：連問（状況設定問題）の stem を、`lead + stem` でも合格にする。

V1.13：連問（状況設定問題）の stem を、`lead + stem` でも合格にする。

  【なぜ】入力バッチは事例文を `lead`、設問文を `stem` に**別々に**持っている。
    LM は両方をつないで stem に入れている。**LM のほうが正しい。**

    アプリ側（scheduler.js V2.56）は
      「事例文は各問の stem に丸ごと入っているので単独でも解ける」
    を前提にしていて、**§18 のスキーマに `lead` は無い**。
    取り込み時に lead は捨てられるので、LM がつながなかったら
    連問の2問目以降は事例文なしで出題され、**解けない**。

    つまり契約は既に「stem に含める」で、検証だけがそれを見ていなかった。
    新しい判断ではなく、**検証を契約（§18）に合わせる**修正。

    実測：これで「入力と一字一句違う」が 94件 → 大きく減る。

  合格にするのは次の3つのどれか。それ以外は今までどおり書き換えとして検出する。
    ① stem がそのまま一致
    ② lead ＋ stem が一致
    ③ 「次の文を読み◯〜◯の問いに答えよ。」を外した lead ＋ stem が一致

V1.12：括弧の化けの道具を V1.01 に差し替え（3組目 V→〈 Z→〉 に対応）。

V1.12：括弧の化けの道具を V1.01 に差し替え（3組目 V→〈 Z→〉 に対応）。

【V1.11 の説明】

V1.11：チェック2（入力と一字一句同じか）の比較を、**両側に同じ正規化を掛けて**行う。

  【なぜ】入力バッチ（抽出の結果）そのものに文字化けが入っている。
      ポリオ?急性灰白髄炎C   （正しくは ポリオ〈急性灰白髄炎〉）
      法律u男女雇用機会均等法x
      大W骨 ／ 末? ／ 発達段階 of の組合せ
    出力側の化けを直すと、入力と一字一句違うことになり NG が増える。
    実測：化けを直したら チェック2 が 47件 → 76件へ**増えた**。

    化けを直したことが悪いのではなく、**片側だけ直して比べた**のが悪い。
    比べるときは両側に同じ直しを掛ける。これは規則を緩めるのではなく、
    同じ土俵に乗せること。書き換え（本文の改変）はこれまでどおり検出する。

  対象は unit / target / rank / major / medium / source / stem / question_type と
  各肢の text。is_correct や番号のずれは文字ではないので触らない。

V1.10：偽陽性を2つ落とす。緩めるのではなく、**測れないものを測るのをやめる**。

V1.10：偽陽性を2つ落とす。緩めるのではなく、**測れないものを測るのをやめる**。
  ・チェック11（読み違え）を計算問題（question_type=="numeric"）で行わない。
    計算問題の答えは**数値**であって肢番号ではない。
    実測：第113回午後問90（滴下数）は答え48が正しいのに、
    「LMの自答[48]が正答[1]と違う」と出ていた。48は肢番号ではない。
  ・チェック12（全体解説が正解肢に触れているか）を、
    選択肢が図の問題（本文が「別冊No.1」等）で行わない。
    肢の文字が「④別　冊No. 1」なので、解説がそこに触れるはずがない。
    実測：第115回午前問63。

V1.09：検証側の落ち度2つ（出典の空白ゆれ・全角数字）を直し、

V1.09：検証側の落ち度2つ（出典の空白ゆれ・全角数字）を直し、
is_splittable の未記入を NG から警告へ落とす。
緩めるのではなく重さを直す：この項目には仕様上の安全な既定（false）があり、
取り込み側もそう倒している。既定のある欠損は「間違い」ではなく「未記入」。

V1.08：除外リスト（照合/除外リスト_V1.00.tsv）の問題を再投入バッチから外す。
作問に投げても必ず空で返るため。削除（正解が存在しない）と
保留（選択肢が図・別冊待ち・抽出失敗）は集計で分けて出す。

V1.07：BOM付きJSONを読めるようにし（utf-8-sig）、1ファイルの読み込み失敗で
全数が止まらないようにした。BOMの本数と読めなかったファイルは最後に報告する。

目的は目視をなくすこと。PADが res_finish/ に落としたJSONを全数チェックし、
NGになった問題だけを再投入用のバッチにまとめ直す。人は件数だけを見る。

使い方
  python3 20260830_仕上げ検証_V1.00.py                 # res_finish/ を検証
  python3 20260830_仕上げ検証_V1.00.py --selftest      # スクリプト自身のテスト
  python3 20260830_仕上げ検証_V1.00.py --dir 別フォルダ

出力
  out/検証結果_<日付>.tsv     1行＝1指摘（source / チェック番号 / 内容）
  out/再投入_<日付>/R###.txt  NGだった問題だけを集めた再投入バッチ
  標準出力にチェックごとの件数

チェック
  1 21キー・順番・型
  2 stem / atoms[].text / is_correct / source / 分類 が入力と一字一句同じか
  3 pool=="main" ／ variant・origin_key・image_url が null ／ question_type と select_count
  4 tags ⊂ tag_candidates ／ sub_item ∈ sub_candidates
  5 全アトムに statement がある
  6 解説に出てくる数値が、選択肢・問題文・evidence・標準値表のどれかに存在するか
  7 evidence の書式（標準値表を引いたなら id、確度Cなら注記）
  8 許可していないHTML（img / on*属性 / script）
  9 ですます調（NG）・全体解説と肢の重複（警告。鑑別問題では意図的に繰り返すことがある）
 10 論点キーワード（hints にある問題だけ）
      §10で数値を書けない論点だけでできている肢は、照合を免除して警告に落とす
 11 answers（LMが自分で解いた答え）が correct と一致するか＝読み違えの検出
 12 全体解説が正解肢に触れているか＝正解を取り違えたまま書いていないか

   ※ V1.03 にあった「誤答肢に否定表現があるか」の検査は外しました。
     語彙リストでは判定できず、17問の試走で16件がすべて偽陽性でした。
     「尿量は増える」「転落の危険が高い」のように、否定語を使わずに
     誤りを示す書き方が普通にあるためです。
"""
import json, io, os, re, sys, hashlib, collections, datetime, glob, unicodedata


def gen_key(path):
    """世代の順番（大きいほど新しい）。V1.25。

    ファイル名は F0003.json / G0190.json / H0149.json / I8004.json の形で、
    英字1文字が世代、数字4桁がその世代の連番。生成した順に増える。
    更新時刻と違って、掃除で書き直しても、別のPCへコピーしても変わらない。
    形が違うファイルは (0, 名前) にして、必ず番号付きより古い扱いにする。
    """
    b = os.path.basename(path)
    m = re.match(r'^([A-Za-z])(\d+)', b)
    if not m:
        return (0, '', 0, b)
    return (1, m.group(1).upper(), int(m.group(2)), b)

HERE = os.path.dirname(os.path.abspath(__file__))
def P(*a): return os.path.join(HERE, *a)

KEYS = ['unit','target','rank','major','medium','sub_item','source','pool','question_type',
        'select_count','image_url','stem','numeric_answer','overall_explanation',
        'comparison_table','mermaid_code','evidence','is_splittable','variant','origin_key','atoms']
AKEYS = ['original_num','is_correct','text','statement','explanation','tags']
ALLOW_TAGS = {'b','br','table','thead','tbody','tr','th','td','ul','ol','li','strong','em','p','span'}

def norm(s):
    return re.sub(r'\s+', '', s or '')


# --- V1.11：文字化けを両側で同じように直してから比べるための正規化 ---
# 直し方は既にある道具をそのまま使う（規則を二重に持たない）。
import importlib.util as _ilu


def _load(path, name):
    sp = _ilu.spec_from_file_location(name, path)
    m = _ilu.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


_HOME = os.path.expanduser('~/omo/tools')
try:
    _garble = _load(os.path.join(_HOME, '助詞の英単語化けを直す_V1.00.py'), '_g')
    _kakko = _load(os.path.join(_HOME, '括弧と欠字の化けを直す_V1.01.py'), '_k')
except Exception:
    _garble = _kakko = None


_LEAD_LABEL = re.compile(r'次の文を読み\s*\d+\s*[〜～\-]\s*\d+\s*の問いに答えよ。')


def stem_ok(got, o, h):
    """stem が入力と同じか。

    V1.13：連問は lead を前に付けた形も合格。
    V1.14：「次の文を読み◯〜◯の問いに答えよ。」は両側から外して比べる。
           アプリは1問ずつ出すので、この指示文は画面上で意味を持たない。"""
    g = normc(_LEAD_LABEL.sub('', str(got or '')))
    base = _LEAD_LABEL.sub('', str(o.get('stem') or ''))
    if g == normc(base):
        return True
    lead = str((o.get('lead') or h.get('lead') or ''))
    if not lead:
        return False
    if g == normc(lead + base) or g == normc(_LEAD_LABEL.sub('', lead) + base):
        return True
    return False


def normc(s):
    """空白を落とし、**化けを直してから**比べる（V1.11）。

    入力バッチ側にも化けが入っているので、片側だけ直すと
    「書き換えられた」に見える。両側に同じ直しを掛ける。"""
    t = s or ''
    if _garble is not None:
        t, _ = _garble.fix_text(t)
    if _kakko is not None:
        t, _ = _kakko.fix_text(t)
    return norm(t)

# ---------- 参照データ ----------
def load_tag_master():
    """概念タグマスタ（103個）をアプリの questions.js から読む。

    正はアプリ側（§24：データ契約を二重に持たない）。
    見つからなければ空を返し、この判定そのものを黙って見送る。
    無いものを NG にすると、全問が真っ赤になって何も分からなくなる。"""
    for p in [os.path.expanduser('~/omo/questions.js'),
              '/sessions/ecstatic-wizardly-dijkstra/mnt/owner/omo/questions.js',
              P('questions.js')]:
        try:
            t = io.open(p, encoding='utf-8').read()
            i = t.index('CONCEPT_TAGS_MASTER = [')
            blk = t[i:t.index('\n];', i)]
            m = re.findall(r'"(#[^"]+)"', blk)
            if m:
                return set(normtag(x) for x in m)
        except Exception:
            continue
    return set()


def normtag(v):
    """タグを比べるための形にそろえる。

    中黒が3種類ある（・ U+30FB ／ · U+00B7 ／ ･ U+FF65）。
    見た目がほぼ同じで、一字違いのまま候補外にされていた（実測3種）。"""
    t = unicodedata.normalize('NFKC', str(v or ''))
    for c in ('\u00b7', '\uff65', '\u2027', '\u30fb'):
        t = t.replace(c, '')
    return t.replace(' ', '').replace('\u3000', '')



def load_ref():
    ref = {}
    ref['batches'] = {}
    for f in sorted(glob.glob(P('batches_finish_v2', 'F*.txt'))):
        t = io.open(f, encoding='utf-8-sig').read()
        j = json.loads(t[t.index('\n{\n'):])
        hints = {h['source']: h for h in j['hints']}
        for q in j['questions']:
            ref['batches'][tidy_src(q['source'])] = {'q': q, 'hint': hints.get(q['source'], {}), 'file': f}   # V1.09
    std = P('20260830_標準値表_V1.05.tsv')
    rows = []
    if os.path.exists(std):
        L = io.open(std, encoding='utf-8-sig').read().split('\n')
        cols = L[0].split('\t')
        for l in L[1:]:
            if l.strip(): rows.append(dict(zip(cols, l.split('\t'))))
    ref['tag_master'] = load_tag_master()
    # V1.17：小項目は「全バッチの候補を集めた全体」をマスタ代わりにする
    ref['sub_master'] = set()
    for v in ref['batches'].values():
        for x in (v['hint'].get('sub_candidates') or []):
            ref['sub_master'].add(normtag(x))   # V1.18：中黒もそろえる
    ref['std'] = rows
    ref['std_by_id'] = {r['id']: r for r in rows}
    # 全問共通の行に出てくる数値（この問題のみの行は、その問題でだけ許す）
    ref['std_nums_common'] = set()
    ref['std_nums_by_source'] = collections.defaultdict(set)
    for r in rows:
        ns = set(re.findall(r'\d[\d,\.]*', r['値'] + ' ' + r.get('条件', '')))
        if r.get('適用範囲') == '全問共通': ref['std_nums_common'] |= ns
        else:
            m = re.search(r'第\d+回 (?:午前|午後)問\d+', r.get('出典', ''))
            if m: ref['std_nums_by_source'][m.group(0)] |= ns
    return ref

# --- V1.20 ---
def diff_note(a, b, width=12):
    """入力aと出力bの違いを、前後の文字を添えた1行にする。

    「stem が書き換わっている」だけでは、人が入力バッチを開くまで分からない。
    どこがどう違うかを、そのまま作問へ返せる形で出す。"""
    import difflib
    a = str(a or ''); b = str(b or '')
    out = []
    for t, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if t == 'equal':
            continue
        pre = a[max(0, i1 - width):i1].replace('\n', ' ')
        post = a[i2:i2 + width].replace('\n', ' ')
        out.append('…%s【入 %r → 出 %r】%s…'
                   % (pre, a[i1:i2][:30], b[j1:j2][:30], post))
        if len(out) >= 3:
            out.append('…ほか')
            break
    return ' '.join(out)


# --- V1.09 ---
def tidy_src(v):
    """出典の空白ゆれを詰める。アプリ側（V2.60）と同じ詰め方に揃える。
    ここが揃っていないと「第113回　　午後問104」が参照と一致せず、
    内容が正しくても『この source が入力バッチに無い』で丸ごとNGになる。"""
    return re.sub(r'[ \t]+', ' ', str(v or '').replace('\u3000', ' ')).strip()

_Z2H = {chr(0xFF10 + i): chr(0x30 + i) for i in range(10)}
def han(v):
    """全角数字を半角へ。解説の「２」を半角と比べて
    『裏づけが無い』と判定していた（実測2問）。"""
    return ''.join(_Z2H.get(c, c) for c in str(v or ''))

# 論点キーワードを外したときに NG にするか（V1.23）。
# 既定は警告。実測で3/3が偽陽性（解説は正しく、字が違うだけ）だったため。
# 戻すならここを True にするだけでよい。
REPORT_KW_AS_NG = False

# is_splittable の未記入を NG にするか。
# 既定（false＝切り出さない）が仕様（§18）にも取り込み側にもあるので、既定は警告。
# 戻すならここを True にするだけでよい。
NG_SPLITTABLE = False


def numbers(s):
    """文中の数値を拾う。桁区切りと小数点は数値の一部。
    英字の直後の数字は語の一部なので拾わない（N95・B12・CO2・PaO2・HbA1c）。"""
    t = re.sub(r'<[^>]+>', ' ', han(s or ''))   # V1.09：全角数字も拾う
    return set(re.findall(r'(?<![A-Za-z])(\d[\d,\.]*)', t))

def canon(n):
    return n.replace(',', '').rstrip('.').lstrip('0') or '0'


def same_number(n, allowed):
    """V1.21：小数の桁を落としただけの同じ数を、同じとみなす。

    23.437（evidence）と 23.4375（解説）は同じ数。
    9,640 と 9,600 は違う数。前者だけを通したいので、
    **小数点をまたぐ前方一致**に限る。整数どうしは通さない。"""
    if '.' not in n:
        return False
    for a in allowed:
        if '.' not in a:
            continue
        lo, hi = (a, n) if len(a) <= len(n) else (n, a)
        if len(lo) >= 3 and hi.startswith(lo):
            return True
    return False


# ---------- 検証本体 ----------
def check(q, ref, ans=None):
    """1問を検証して、指摘のリスト [(番号, 内容)] を返す。"""
    ng = []
    src = tidy_src(q.get('source'))   # V1.09：詰めてから引く
    b = ref['batches'].get(src)

    # 1 キー
    if list(q.keys()) != KEYS:
        miss = [k for k in KEYS if k not in q]; extra = [k for k in q if k not in KEYS]
        if miss or extra: ng.append((1, '不足=%s 余分=%s' % (miss, extra)))
        else: ng.append((1, 'キーの順番が違う'))
    for i, a in enumerate(q.get('atoms') or []):
        if list(a.keys()) != AKEYS:
            ng.append((1, 'atoms[%d] のキー: 不足=%s 余分=%s' %
                       (i, [k for k in AKEYS if k not in a], [k for k in a if k not in AKEYS])))
    if not isinstance(q.get('select_count'), int): ng.append((1, 'select_count が整数でない'))
    # V1.09：既定（false＝切り出さない）が仕様にも取り込み側にもあるので、
    # 未記入は「間違い」ではなく「未記入」。既定では警告に落とす。
    if not isinstance(q.get('is_splittable'), bool):
        _n = 1 if NG_SPLITTABLE else -1
        ng.append((_n, 'is_splittable が未記入（既定の false で取り込まれる。内容には影響しない）'
                   if q.get('is_splittable') is None else 'is_splittable が真偽値でない'))

    if b is None:
        ng.append((2, 'この source が入力バッチに無い'))
        return ng
    o = b['q']; h = b['hint']

    # 2 入力と同じか
    for k in ('unit', 'target', 'rank', 'major', 'medium', 'source', 'question_type'):
        if normc(str(q.get(k))) != normc(str(o.get(k))):
            ng.append((2, '%s が書き換わっている %s'
                       % (k, diff_note(o.get(k), q.get(k)))))
    # V1.13：stem は「事例文（lead）を前に付けた形」も合格にする。
    # アプリは事例文が stem に入っている前提で、§18 に lead は無い。
    if not stem_ok(q.get('stem'), o, h):
        ng.append((2, 'stem が書き換わっている %s'
                   % diff_note(o.get('stem'), q.get('stem'))))
    oa, qa = o['atoms'], (q.get('atoms') or [])
    # V1.14：入力が0肢なのは「選択肢が図」の問題。Claude が起こしたぶんが
    # 出力に入るので、増えているのが正しい。0肢のときは数を見ない。
    if len(oa) and len(oa) != len(qa):
        ng.append((2, '選択肢の数が %d→%d' % (len(oa), len(qa))))
    elif len(oa):
        for x, y in zip(oa, qa):
            if normc(x['text']) != normc(y.get('text')):
                ng.append((2, '肢%d の text が書き換わっている %s'
                           % (x['original_num'], diff_note(x['text'], y.get('text')))))
            if x['is_correct'] != y.get('is_correct'): ng.append((2, '肢%d の is_correct が反転している' % x['original_num']))
            if x['original_num'] != y.get('original_num'): ng.append((2, '肢の番号がずれている'))

    # 3 固定値
    if q.get('pool') != 'main': ng.append((3, 'pool が "%s"' % q.get('pool')))
    for k in ('image_url', 'variant', 'origin_key'):
        if q.get(k) is not None: ng.append((3, '%s が null でない' % k))
    if q.get('numeric_answer') != o.get('numeric_answer'): ng.append((3, 'numeric_answer が入力と違う'))
    nc = sum(1 for a in qa if a.get('is_correct'))
    if q.get('question_type') != 'numeric' and q.get('select_count') != nc:
        ng.append((3, 'select_count=%s だが正解肢は %d 個' % (q.get('select_count'), nc)))
    if q.get('question_type') != 'single' and q.get('is_splittable') is not False:
        ng.append((3, 'single 以外なのに is_splittable が false でない'))

    # 4 候補の中か
    # V1.17：候補外＝間違い、ではない。全バッチの候補を集めた全体に在るかで分ける。
    subs = h.get('sub_candidates') or []
    smaster = ref.get('sub_master') or set()
    nsub = normtag(q.get('sub_item'))          # V1.18
    nsubs = {normtag(x) for x in subs}
    # V1.19：候補が出力の前方一致なら、候補側が切れているとみなして通す。
    #        10文字以上のときだけ（短い語の偶然の一致を拾わない）。
    cut = any(len(x) >= 10 and nsub.startswith(x) for x in nsubs)
    if subs and nsub not in nsubs and not cut:
        if smaster and nsub not in smaster:
            ng.append((4, 'sub_item「%s」が出題基準の小項目のどこにも無い' % q.get('sub_item')))
        else:
            ng.append((-4, 'sub_item「%s」は出題基準にあるが、この問題の候補外（警告）'
                       % q.get('sub_item')))
    # V1.16：候補外＝間違い、ではない。マスタに在るかどうかで分ける。
    cand = {normtag(t) for t in (h.get('tag_candidates') or [])}
    master = ref.get('tag_master') or set()
    for a in qa:
        for t in (a.get('tags') or []):
            nt = normtag(t)
            if master and nt not in master:
                ng.append((4, '肢%s のタグ「%s」が概念タグマスタに無い（アプリが捨てる）'
                           % (a.get('original_num'), t)))
            elif cand and nt not in cand:
                # 警告はチェック番号を負で表す（この道具の作法）
                ng.append((-4, '肢%s のタグ「%s」はマスタにあるが、この問題の候補外（警告）'
                           % (a.get('original_num'), t)))

    # 5 statement
    for a in qa:
        if not (a.get('statement') or '').strip():
            ng.append((5, '肢%s に statement が無い' % a.get('original_num')))

    # 6 数値の裏づけ
    ok = set()
    for a in qa: ok |= numbers(a.get('text'))
    ok |= numbers(o.get('stem'))
    ok |= numbers(q.get('evidence'))
    ok |= ref['std_nums_common'] | ref['std_nums_by_source'].get(src, set())
    for kw in (h.get('論点キーワード') or []):
        for w in kw.get('kw', []): ok |= numbers(w)
    # 狭い許可集合＝この問題だけで裏が取れる数値。論点照合の免除判定に使う
    narrow = set()
    for a in qa: narrow |= numbers(a.get('text'))
    narrow |= numbers(o.get('stem')) | numbers(q.get('evidence'))
    narrow |= ref['std_nums_by_source'].get(src, set())
    for i in re.findall(r'\b([QH]\d{3})\b', q.get('evidence') or ''):
        r = ref['std_by_id'].get(i)
        if r: narrow |= numbers(r['値'] + ' ' + r.get('条件', ''))
    narrow = {canon(x) for x in narrow}
    ok = {canon(x) for x in ok} | {str(i) for i in range(1, 10)}   # 1桁の数字は肢番号などで頻出のため許す
    texts = [('全体解説', q.get('overall_explanation')), ('比較表', q.get('comparison_table')),
             ('図解', q.get('mermaid_code'))]
    texts += [('肢%s' % a.get('original_num'), a.get('explanation')) for a in qa]
    for where, t in texts:
        for n in numbers(t):
            if canon(n) not in ok and not same_number(canon(n), ok):
                ng.append((6, '%s の数値「%s」に裏づけが無い' % (where, n)))

    # 7 evidence の書式
    ev = q.get('evidence') or ''
    used_std = re.findall(r'\b([QH]\d{3})\b', ev)
    for i in used_std:
        r = ref['std_by_id'].get(i)
        if r is None: ng.append((7, 'evidence の標準値表id「%s」が表に無い' % i))
        else:
            if r['確度'] == 'X':
                # V1.24：引いただけならNGにしない。その行の数値を実際に
                # 本文へ書いたときだけ責める（§10が禁じているのは書くこと）。
                xn = {canon(n) for n in numbers(r['値'] + ' ' + r.get('条件', ''))}
                body = ' '.join([q.get('overall_explanation') or ''] +
                                [(a.get('explanation') or '') for a in qa])
                wrote = xn & {canon(n) for n in numbers(body)}
                if wrote:
                    ng.append((7, '%s は確度X。数値を書いてはいけない（書いた値：%s）'
                               % (i, '・'.join(sorted(wrote)[:4]))))
                else:
                    ng.append((-7, '%s は確度Xの行。数値は書いていないので通す（警告）' % i))
            if r['確度'] == 'C' and '確度C' not in ev: ng.append((7, '%s は確度Cだが evidence に注記が無い' % i))
            if r.get('適用範囲') == 'この問題のみ':
                m = re.search(r'第\d+回 (?:午前|午後)問\d+', r.get('出典', ''))
                if m and m.group(0) != src:
                    ng.append((7, '%s は「%s」専用の行。この問題には使えない' % (i, m.group(0))))
    if not ev.strip():
        # 数値を解説に書いたのに evidence が無い、を拾う（肢テキスト由来の数値は除く）
        own = set()
        for a in qa: own |= numbers(a.get('text'))
        own |= numbers(o.get('stem'))
        own = {canon(x) for x in own} | {str(i) for i in range(1, 10)}
        for where, t in texts:
            outside = {canon(n) for n in numbers(t)} - own
            if outside:
                ng.append((7, 'evidence が空だが %s に %s の数値がある' % (where, sorted(outside)[:3])))
                break

    # 8 HTML
    for where, t in texts:
        for tag in re.findall(r'<\s*/?\s*([A-Za-z][A-Za-z0-9]*)', t or ''):
            if tag.lower() not in ALLOW_TAGS: ng.append((8, '%s に許可外のタグ <%s>' % (where, tag)))
        if re.search(r'\son[a-z]+\s*=', t or '', re.I): ng.append((8, '%s に on*属性' % where))

    # 9 文体・重複
    for where, t in texts:
        if re.search(r'(です|ます)[。、]', t or ''): ng.append((9, '%s がですます調' % where))
    ov = norm(q.get('overall_explanation'))
    for a in qa:
        e = norm(a.get('explanation'))
        for i in range(0, max(0, len(e) - 35)):
            if e[i:i + 35] and e[i:i + 35] in ov:
                ng.append((-9, '肢%s の解説が全体解説と35字以上重複（警告）' % a.get('original_num'))); break

    # 10 論点キーワード（2文字の並びが1つでも入っていれば触れているとみなす）
    #    §10で数値を書けない論点は、外していても責められない。免除して警告に落とす。
    #    例：子宮復古（H049は確度X）。数値を書かせない以上、その論点には触れられない。
    def touched(w, e):
        w = norm(w)
        if len(w) <= 2: return w in e
        return any(w[i:i+2] in e for i in range(len(w) - 1))
    def writable(w):
        ns = numbers(w)
        return (not ns) or all(canon(n) in narrow for n in ns)
    kws = {k['num']: k.get('kw', []) for k in (h.get('論点キーワード') or [])}
    for a in qa:
        kw = kws.get(a.get('original_num'))
        if not kw: continue
        e = norm(a.get('explanation'))
        wk = [w for w in kw if writable(w)]
        if not wk:
            ng.append((-10, '肢%s の論点 %s は裏づけの取れない数値だけでできている。照合を免除（警告）'
                       % (a.get('original_num'), kw)))
            continue
        if not any(touched(w, e) for w in wk):
            # V1.23：既定は警告。言い換えを機械で判定できないため。
            ng.append((10 if REPORT_KW_AS_NG else -10,
                       '肢%s が論点 %s を外している%s'
                       % (a.get('original_num'), wk,
                          '' if REPORT_KW_AS_NG else
                          '（警告：言い換えかもしれないので人が見る）')))

    # 11 読み違えの検出（answers があるときだけ）
    #
    # V1.10：計算問題は見ない。計算問題の答えは**数値**であって肢番号ではないので、
    # 肢番号の集合と比べても意味がない。
    # 実測：第113回午後問90（滴下数）は「10000滴÷210分＝47.6→四捨五入48」で
    # 48が正しいのに、「LMの自答[48]が正答[1]と違う」と出ていた。
    correct = sorted(x['original_num'] for x in oa if x['is_correct'])
    # V1.22：入力に肢が1つも無い問題（選択肢が図・写真）は、比べる相手がいない。
    # チェック2 と同じ扱いにそろえる。
    if ans is not None and q.get('question_type') != 'numeric' and len(oa) > 0:
        got = sorted(ans.get('num') or [])
        if got != correct:
            ng.append((11, 'LMが自分で解いた答え %s が正答 %s と違う＝読み違え' % (got, correct)))

    # 12 全体解説が正解肢に触れているか
    #
    # V1.10：肢の文字が「別冊No.◯」など**図の参照**でしかない問題は見ない。
    # 中身が無いので、解説がそこに触れるはずがない。
    # 実測：第115回午前問63「④別　冊No. 1」。
    ovr = norm(q.get('overall_explanation'))
    for x in oa:
        if not x['is_correct']: continue
        t = norm(x['text']).rstrip('。')
        if len(t) < 2: continue
        if '別冊' in t.replace(' ', '').replace('\u3000', ''): continue
        if not any(t[i:i+2] in ovr for i in range(len(t) - 1)):
            ng.append((12, '全体解説が正解肢%d「%s」に触れていない' % (x['original_num'], x['text'][:24])))

    return ng

# ---------- 自己テスト ----------
def good_fixture(ref):
    """入力バッチから、規則をすべて満たす出力を機械的に作る。"""
    src = '第113回 午前問37'
    b = ref['batches'][src]; o = b['q']; h = b['hint']
    q = json.loads(json.dumps(o))
    q['sub_item'] = (h.get('sub_candidates') or [''])[0]
    ct = '／'.join(a['text'] for a in q['atoms'] if a['is_correct'])
    q['overall_explanation'] = '病室の照度は用途で変える。読書に適するのは%sで、全般照明より明るい。' % ct
    q['evidence'] = None
    q['is_splittable'] = False
    tags = (h.get('tag_candidates') or [])[:1]
    kws = {k['num']: k.get('kw', []) for k in (h.get('論点キーワード') or [])}
    for a in q['atoms']:
        a['statement'] = '病室で読書をする際に適した照度は%sである。' % a['text']
        w = (kws.get(a['original_num']) or [''])[0]
        a['explanation'] = '%s にあたる明るさ。' % w
        a['tags'] = list(tags)
    return q

def selftest(ref):
    q = good_fixture(ref)
    base = check(q, ref)
    print('自己テスト')
    print('  正しい出力 … 指摘 %d件 %s' % (len(base), '' if not base else base))
    def mut(name, f, expect):
        x = json.loads(json.dumps(q)); f(x)
        got = {n for n, _ in check(x, ref)}
        ok = expect in got
        print('  %-34s → %s（検出:%s）' % (name, 'OK' if ok else '★見逃し', sorted(got) or 'なし'))
        return ok
    r = []
    r.append(mut('キーを1つ落とす', lambda x: x.pop('target'), 1))
    r.append(mut('stem を書き換える', lambda x: x.update(stem=x['stem'] + '（追記）'), 2))
    r.append(mut('is_correct を反転', lambda x: x['atoms'][0].update(is_correct=not x['atoms'][0]['is_correct']), 2))
    r.append(mut('pool を mock にする', lambda x: x.update(pool='mock'), 3))
    r.append(mut('候補外のタグを入れる', lambda x: x['atoms'][0].update(tags=['#存在しないタグ']), 4))
    r.append(mut('statement を空にする', lambda x: x['atoms'][0].update(statement=''), 5))
    r.append(mut('裏づけの無い数値を書く',
                 lambda x: x.update(overall_explanation=x['overall_explanation'] + '基準は477ルクスである。'), 6))
    # V1.24：引いただけなら警告。**その行の数値を書いたとき**にNG。
    # 観点は「確度Xの値を書かせない」ことなので、書く側でテストする。
    r.append(mut('確度Xの行を引くだけ（V1.24で警告）',
                 lambda x: x.update(evidence='標準値表 H006：病室の照度'), -7))
    r.append(mut('確度Xの行の数値を書く',
                 lambda x: (x.update(evidence='標準値表 H070：病室の照度'),
                            x.update(overall_explanation=(x.get('overall_explanation') or '') +
                                     '病室の照度は100ルクスである。')),
                 7))
    r.append(mut('img タグを入れる',
                 lambda x: x.update(overall_explanation=x['overall_explanation'] + '<img src=x onerror=alert(1)>'), 8))
    r.append(mut('ですます調にする',
                 lambda x: x.update(overall_explanation='病室の照度は用途で変えます。'), 9))
    # V1.23：論点キーワードの照合は警告（-10）に落とした。
    # 「気づけること」は変わらないので、期待する番号だけを直す。
    r.append(mut('論点を外す（V1.23で警告）',
                 lambda x: [a.update(explanation='関係のない話。') for a in x['atoms']],
                 10 if REPORT_KW_AS_NG else -10))
    r.append(mut('全体解説が正解肢に触れない',
                 lambda x: x.update(overall_explanation='照度は用途で変わる。'), 12))
    def _ans(x): pass
    got = {n for n, _ in check(q, ref, {'source': q['source'], 'num': [1]})}
    print('  %-34s → %s（検出:%s）' % ('答えを読み違える', 'OK' if 11 in got else '★見逃し', sorted(got) or 'なし'))
    r.append(11 in got)
    print('  %d/%d を検出。正しい出力の指摘は %d件' % (sum(r), len(r), len(base)))
    return (sum(r) == len(r)) and not base

# ---------- 実行 ----------
def main():
    ref = load_ref()
    print('入力バッチ %d問／標準値表 %d行' % (len(ref['batches']), len(ref['std'])))
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest(ref) else 1)
    d = sys.argv[sys.argv.index('--dir') + 1] if '--dir' in sys.argv else 'res_finish'
    files = sorted(glob.glob(P(d, '*.json')))
    if not files:
        print('%s に .json がありません。先に自己テストを走らせてください（--selftest）' % d); sys.exit(1)
    # V1.15：source ごとに、いちばん新しいファイルの出力だけを見る。
    # 結合ツール（tools/仕上げ結果を結合する）と同じ規則に揃える。
    # --all を付けると従来どおり全ファイルを見る。
    #
    # V1.25（2026-09-09）：**「新しい方」を更新時刻で決めるのをやめた。**
    #
    # 何が起きていたか：掃除（tools_出力の後始末）が res_finish_clean の
    # 1,157本を **20秒のあいだに全部書き直す**ので、更新時刻がほぼ同じ値に
    # 固まる。実測では、秒より下まで見れば1,157本すべて別の時刻だが、
    # **秒に丸めると20種類しかなく、1秒あたり最大61本が同着**になる。
    # 同着のときどちらが勝つかは、OS・ファイルシステム・Pythonの版で変わる。
    #
    # 実害：同じフォルダに同じコマンドを打っても、環境が違うと結果が変わった。
    # 実測（2026-09-09）Linux コンテナ NG 33問（チェック2は16件）／
    # Windows 11 NG 98問（チェック2は103件）。他のチェックは1件も違わなかった。
    # チェック2は「入力と出力が一字一句同じか」を見るので、勝つファイルが
    # 変わるとそこだけ大きく動く。
    #
    # 直し方：**ファイル名の番号順**で決める。番号は生成した順に振ってあり
    # （F→G→H→I の順に世代が進み、番号は各世代で単調に増える）、
    # あとから変わらない。誰がどこで実行しても同じ結果になる。
    # 更新時刻と食い違ったファイルは件数を出す（黙って変えない）。
    keep_all = '--all' in sys.argv
    qs = []; ANS = {}; broken = []; bom = 0
    newest = {}          # source -> (世代キー, question)
    pick_name = {}       # source -> 採用したファイル名
    by_mtime = {}        # source -> (更新時刻, ファイル名)  ※見張り用（V1.25）
    dup_dropped = 0
    for f in files:
        # V1.07：BOM付きでも読む。342ファイル中289が BOM 付きで保存されており、
        # utf-8 で読んでいた V1.06 は1ファイル目で落ちて全数が走らなかった。
        raw = io.open(f, 'rb').read()
        if raw.startswith(b'\xef\xbb\xbf'):
            bom += 1
        try:
            j = json.loads(raw.decode('utf-8-sig'))
        except Exception as e:
            # V1.07：1ファイルの都合で全体を止めない。読めなかった事実を残して先へ。
            broken.append((os.path.basename(f), str(e)[:90]))
            continue
        got = j['questions'] if isinstance(j, dict) else j
        if keep_all:
            qs += got
        else:
            mt = gen_key(f)
            tt = os.path.getmtime(f)
            for q in got:
                src = q.get('source') or ('?' + os.path.basename(f))
                if src in newest:
                    dup_dropped += 1
                    if mt <= newest[src][0]:
                        continue
                newest[src] = (mt, q)
                pick_name[src] = os.path.basename(f)
            # 見張り：更新時刻で決めていたら、どのファイルが勝っていたか
            for q in got:
                src = q.get('source') or ('?' + os.path.basename(f))
                if src not in by_mtime or tt > by_mtime[src][0]:
                    by_mtime[src] = (tt, os.path.basename(f))
        for a in (j.get('answers') or []) if isinstance(j, dict) else []:
            ANS[a.get('source')] = a
    if not keep_all:
        qs = [q for _, q in newest.values()]
        # V1.25：更新時刻で決めていた頃と結果が変わる source を数える。
        # 0でなければ、以前の実行結果と数字が変わって当たり前ということ。
        drift = sorted(s2 for s2 in pick_name
                       if s2 in by_mtime and by_mtime[s2][1] != pick_name[s2])
        if drift:
            print('※ 更新時刻で選ぶと %d問 が別のファイルになります'
                  '（V1.25 でファイル名の番号順に変えました）' % len(drift))
            for s2 in drift[:5]:
                print('    %-18s 番号順 %s ／ 更新時刻順 %s'
                      % (s2, pick_name[s2], by_mtime[s2][1]))
    log = []; ngsrc = set(); warn = 0
    for name, msg in broken:
        log.append((name, 0, 'NG', 'ファイルを読めませんでした：' + msg))
    if not ANS: print('※ answers が入っていないので、チェック11（読み違え）は動きません')
    for q in qs:
        for n, msg in check(q, ref, ANS.get(q.get('source'))):
            log.append((q.get('source', '?'), abs(n), ('警告' if n < 0 else 'NG'), msg))
            if n < 0: warn += 1
            else: ngsrc.add(q.get('source'))
    today = datetime.datetime.now().strftime('%Y%m%d')
    os.makedirs(P('out'), exist_ok=True)
    io.open(P('out', '検証結果_%s.tsv' % today), 'w', encoding='utf-8').write(
        'source\tチェック\t重大度\t内容\n' + '\n'.join('%s\t%d\t%s\t%s' % r for r in log))
    cnt = collections.Counter((n, lv) for _, n, lv, _ in log)
    print('検証 %d問 ／ NG %d問（%.1f%%） ／ 指摘 %d件（うち警告 %d件）' %
          (len(qs), len(ngsrc), 100.0 * len(ngsrc) / max(1, len(qs)), len(log), warn))
    if not keep_all and dup_dropped:
        print('※ 同じ問題の作り直しが %d件あり、新しい方だけを見ました'
              '（結合ツールと同じ規則。古い方も見るには --all）' % dup_dropped)
    for k in sorted(cnt): print('  チェック%-3d %-3s %d件' % (k[0], k[1], cnt[k]))
    # V1.07：黙って直さない。BOMはPADの保存設定が変わった合図で、
    # 気づけないと次も同じところで止まる。
    if bom:
        print('※ BOM付きで保存されたファイル %d/%d 本（読めてはいます。'
              'PADの保存設定が「UTF-8（BOM付き）」になっていないか確認してください）'
              % (bom, len(files)))
    if broken:
        print('※ 読めなかったファイル %d本：%s'
              % (len(broken), ' / '.join(n for n, _ in broken[:5])))
    # 再投入バッチ
    # V1.06: LMがsourceの文字列自体を崩して返すことがある（例「第111回 午前1」）。
    # 参照に無いsourceはチェック2でNGとして記録済みなので、再投入の対象からは
    # 外して先へ進む（KeyErrorで全体を落とさない）。
    # --- V1.08：除外リストを外す ---
    # 「作問に投げても必ず空で返る」問題を再投入し続けると、PADの実行回数が
    # そのぶん無駄になる。削除と保留を分けて出すのは、保留には復活の道が
    # あるため（選択肢の図が用意できれば戻る）。
    exc = {}
    xp = P('照合', '除外リスト_V1.00.tsv')
    if os.path.exists(xp):
        for ln in io.open(xp, encoding='utf-8').read().split('\n')[1:]:
            c = ln.split('\t')
            if len(c) >= 3 and c[0].strip():
                exc[c[0].strip()] = (c[1], c[2])
    hit = [s for s in ngsrc if s in exc]
    if hit:
        import collections as _c
        cc = _c.Counter(exc[s][0] for s in hit)
        print('除外リストで再投入から外した %d問（%s）'
              % (len(hit), ' / '.join('%s%d問' % (k, v) for k, v in cc.most_common())))
        for s in sorted(hit):
            print('    %-16s %s（%s）' % (s, exc[s][0], exc[s][1]))
        ngsrc = set(s for s in ngsrc if s not in exc)

    unknown = [s for s in ngsrc if tidy_src(s) not in ref['batches']]
    if unknown:
        print('参照に無いsource（sourceの打ち直し崩れ・再投入対象外） %d件: %s'
              % (len(unknown), ' / '.join(sorted(unknown)[:5])))
        ngsrc = [s for s in ngsrc if tidy_src(s) in ref['batches']]
    if ngsrc:
        od = P('out', '再投入_%s' % today); os.makedirs(od, exist_ok=True)
        head = io.open(P('batch_head_V4.05.txt'), encoding='utf-8-sig').read()
        srcs = sorted(ngsrc, key=lambda s: [int(x) if x.isdigit() else x
                                            for x in re.findall(r'\d+|午前|午後', s)])
        for i in range(0, len(srcs), 3):
            g = srcs[i:i + 3]
            u = ref['batches'][tidy_src(g[0])]['q']['unit']
            body = (head.replace('（単元）', u) + '\n{\n "hints": ' +
                    json.dumps([ref['batches'][tidy_src(s)]['hint'] for s in g], ensure_ascii=False, indent=1) +
                    ',\n "questions": ' +
                    json.dumps([ref['batches'][tidy_src(s)]['q'] for s in g], ensure_ascii=False, indent=1) + '\n}\n')
            io.open(os.path.join(od, 'R%03d.txt' % (i // 3 + 1)), 'w', encoding='utf-8').write(body)
        print('再投入バッチ %d本を out/再投入_%s/ に出しました' % ((len(srcs) + 2) // 3, today))

if __name__ == '__main__':
    main()
