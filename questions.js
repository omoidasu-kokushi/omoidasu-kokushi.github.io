/* ==========================================================================
 * 20260815_NurseExamApp_V1.00 / questions.js（データ層・最小版）
 * 74個の標準概念タグ マスター辞書。
 * 問題データ本体は IndexedDB に保持するため、ここには定数のみを置く。
 * ========================================================================== */
const CONCEPT_TAGS_MASTER = [
  // 1. 人口・統計・制度・法規
  { tag: "#人口動態統計", label: "人口動態統計", category: "法規・制度" },
  { tag: "#保健統計指標", label: "保健統計指標", category: "法規・制度" },
  { tag: "#看護倫理・法的責任", label: "看護倫理・法的責任", category: "法規・制度" },
  { tag: "#医療保険・福祉制度", label: "医療保険・福祉制度", category: "法規・制度" },
  { tag: "#介護保険・高齢者支援", label: "介護保険・高齢者支援", category: "法規・制度" },
  { tag: "#母子保健・成育基本法", label: "母子保健・成育基本法", category: "法規・制度" },
  { tag: "#精神保健福祉法", label: "精神保健福祉法", category: "法規・制度" },

  // 2. 人体の構造・機能・生理学
  { tag: "#神経系・脳機能", label: "神経系・脳機能", category: "解剖生理" },
  { tag: "#心臓・循環器生理", label: "心臓・循環器生理", category: "解剖生理" },
  { tag: "#呼吸・ガス交換生理", label: "呼吸・ガス交換生理", category: "解剖生理" },
  { tag: "#消化・吸収・代謝生理", label: "消化・吸収・代謝生理", category: "解剖生理" },
  { tag: "#腎・体液・酸塩基平衡", label: "腎・体液・酸塩基平衡", category: "解剖生理" },
  { tag: "#内分泌・ホルモン動態", label: "内分泌・ホルモン動態", category: "解剖生理" },
  { tag: "#免疫・生体防御機構", label: "免疫・生体防御機構", category: "解剖生理" },

  // 3. 薬理学・薬物動態
  { tag: "#循環器作用薬", label: "循環器作用薬", category: "薬理" },
  { tag: "#呼吸器・アレルギー薬", label: "呼吸器・アレルギー薬", category: "薬理" },
  { tag: "#精神・神経作用薬", label: "精神・神経作用薬", category: "薬理" },
  { tag: "#抗菌薬・抗ウイルス薬", label: "抗菌薬・抗ウイルス薬", category: "薬理" },
  { tag: "#抗悪性腫瘍薬・分子標的薬", label: "抗悪性腫瘍薬・分子標的薬", category: "薬理" },
  { tag: "#薬物代謝・血中濃度管理", label: "薬物代謝・血中濃度管理", category: "薬理" },

  // 4. 検査・画像・モニタリング
  { tag: "#血液・生化学検査基準", label: "血液・生化学検査基準", category: "検査診断" },
  { tag: "#心電図・不整脈読影", label: "心電図・不整脈読影", category: "検査診断" },
  { tag: "#血液ガス・酸塩基判定", label: "血液ガス・酸塩基判定", category: "検査診断" },
  { tag: "#画像診断・内視鏡検査", label: "画像診断・内視鏡検査", category: "検査診断" },
  { tag: "#尿・便・穿刺液検査", label: "尿・便・穿刺液検査", category: "検査診断" },
  { tag: "#バイタルサイン・生体計測", label: "バイタルサイン・生体計測", category: "検査診断" },

  // 5. 共通基本看護技術・安全管理
  { tag: "#感染予防・標準予防策", label: "感染予防・標準予防策", category: "看護技術" },
  { tag: "#医療安全・アクシデント防止", label: "医療安全・アクシデント防止", category: "看護技術" },
  { tag: "#与薬・注射・点滴管理", label: "与薬・注射・点滴管理", category: "看護技術" },
  { tag: "#輸血療法・血液製剤管理", label: "輸血療法・血液製剤管理", category: "看護技術" },
  { tag: "#体位変換・移乗・ポジショニング", label: "体位変換・移乗・ポジショニング", category: "看護技術" },
  { tag: "#排泄援助・導尿管理", label: "排泄援助・導尿管理", category: "看護技術" },
  { tag: "#栄養投与・経管栄養管理", label: "栄養投与・経管栄養管理", category: "看護技術" },
  { tag: "#皮膚・創傷・褥瘡ケア", label: "皮膚・創傷・褥瘡ケア", category: "看護技術" },

  // 6. 成人・急性期・救急看護
  { tag: "#心肺蘇生・BLS/ALS", label: "心肺蘇生・BLS/ALS", category: "急性期看護" },
  { tag: "#ショック・循環破綻管理", label: "ショック・循環破綻管理", category: "急性期看護" },
  { tag: "#急性冠症候群・心不全", label: "急性冠症候群・心不全", category: "急性期看護" },
  { tag: "#急性呼吸不全・人工呼吸", label: "急性呼吸不全・人工呼吸", category: "急性期看護" },
  { tag: "#急性期脳血管障害", label: "急性期脳血管障害", category: "急性期看護" },
  { tag: "#周術期看護・麻酔管理", label: "周術期看護・麻酔管理", category: "急性期看護" },
  { tag: "#救急トリアージ・災害医療", label: "救急トリアージ・災害医療", category: "急性期看護" },

  // 7. 成人・慢性期・生活習慣病看護
  { tag: "#糖尿病・血糖自己管理", label: "糖尿病・血糖自己管理", category: "慢性期看護" },
  { tag: "#慢性腎臓病・透析管理", label: "慢性腎臓病・透析管理", category: "慢性期看護" },
  { tag: "#慢性呼吸不全・COPD", label: "慢性呼吸不全・COPD", category: "慢性期看護" },
  { tag: "#慢性心不全・自己管理", label: "慢性心不全・自己管理", category: "慢性期看護" },
  { tag: "#肝硬変・消化器慢性疾患", label: "肝硬変・消化器慢性疾患", category: "慢性期看護" },
  { tag: "#自己免疫・膠原病看護", label: "自己免疫・膠原病看護", category: "慢性期看護" },
  { tag: "#がん化学療法・放射線看護", label: "がん化学療法・放射線看護", category: "慢性期看護" },

  // 8. 緩和ケア・終末期看護
  { tag: "#疼痛評価・オピオイド管理", label: "疼痛評価・オピオイド管理", category: "終末期看護" },
  { tag: "#終末期症状緩和・呼吸困難", label: "終末期症状緩和・呼吸困難", category: "終末期看護" },
  { tag: "#意思決定支援・ACP", label: "意思決定支援・ACP", category: "終末期看護" },
  { tag: "#スピリチュアルケア・家族支援", label: "スピリチュアルケア・家族支援", category: "終末期看護" },
  { tag: "#エンゼルケア・死後処置", label: "エンゼルケア・死後処置", category: "終末期看護" },

  // 9. 老年・リハビリ・在宅看護
  { tag: "#認知症ケア・BPSD対応", label: "認知症ケア・BPSD対応", category: "老年看護" },
  { tag: "#せん妄予防・急性混乱ケア", label: "せん妄予防・急性混乱ケア", category: "老年看護" },
  { tag: "#廃用症候群・リハビリ支援", label: "廃用症候群・リハビリ支援", category: "老年看護" },
  { tag: "#誤嚥性肺炎・摂食嚥下訓練", label: "誤嚥性肺炎・摂食嚥下訓練", category: "老年看護" },
  { tag: "#フレイル・サルコペニア対策", label: "フレイル・サルコペニア対策", category: "老年看護" },
  { tag: "#在宅療養支援・訪問看護", label: "在宅療養支援・訪問看護", category: "在宅看護" },
  { tag: "#多職種連携・退院支援", label: "多職種連携・退院支援", category: "在宅看護" },

  // 10. 小児・母性・成育看護
  { tag: "#小児の発達段階・マイルストーン", label: "小児の発達段階・マイルストーン", category: "小児看護" },
  { tag: "#小児の急性疾患・感染症", label: "小児の急性疾患・感染症", category: "小児看護" },
  { tag: "#小児の先天性・慢性疾患", label: "小児の先天性・慢性疾患", category: "小児看護" },
  { tag: "#正常妊娠・胎児発育動態", label: "正常妊娠・胎児発育動態", category: "母性看護" },
  { tag: "#妊娠期異常・ハイリスク管理", label: "妊娠期異常・ハイリスク管理", category: "母性看護" },
  { tag: "#正常分娩・産褥期管理", label: "正常分娩・産褥期管理", category: "母性看護" },
  { tag: "#新生児生理・初期評価", label: "新生児生理・初期評価", category: "母性看護" },
  { tag: "#母乳育児・育児不安支援", label: "母乳育児・育児不安支援", category: "母性看護" },

  // 11. 精神看護・メンタルヘルス
  { tag: "#統合失調症・急性期/維持期", label: "統合失調症・急性期/維持期", category: "精神看護" },
  { tag: "#気分障害（うつ・双極性）", label: "気分障害（うつ・双極性）", category: "精神看護" },
  { tag: "#不安症・ストレス関連障害", label: "不安症・ストレス関連障害", category: "精神看護" },
  { tag: "#摂食障害・パーソナリティ障害", label: "摂食障害・パーソナリティ障害", category: "精神看護" },
  { tag: "#依存症・アディクションケア", label: "依存症・アディクションケア", category: "精神看護" },
  { tag: "#リエゾン精神看護・心理教育", label: "リエゾン精神看護・心理教育", category: "精神看護" }
];

/* --------------------------------------------------------------------------
 * 初回起動シード（12列TSV）
 * IndexedDB が完全に空の状態でも、いきなりチュートリアルの「問1」を開けるよう
 * 最小限の問題データを同梱する。part2 の init() が totalQuestions===0 を
 * 検知したときだけ 1 度だけ取り込む（以後はユーザーの取り込みデータが優先）。
 * -------------------------------------------------------------------------- */
const SEED_QUESTIONS_TSV = [
  "必修問題\t目標Ⅰ. 看護の社会的側面及び倫理的側面について基本的な理解を問う。\tS\t1. 健康に関する指標\tA. 人口静態・人口動態\ta. 総人口、d. 将来推計人口\tsingle\t令和5年（2023年）に公表された「日本の将来推計人口（令和5年推計）」において、2070年の総人口の推計値として最も近いのはどれか。\t\"[\"\"① 約7,300万人\"\", \"\"② 約8,700万人\"\", \"\"③ 約9,600万人\"\", \"\"④ 約1億500万人\"\"]\"\t1\t\"【解説】「日本の将来推計人口（令和5年推計）」における将来推計データについての出題である。<br><br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>① 誤り：</span>2070年の推計総人口としては過小である。<br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>② 正解：</span>令和5年（2023年）公表の将来推計人口において、2070年の日本の総人口は約8,700万人（正確には8,700万人をやや下回る水準）に減少すると推計されている。<br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>③ 誤り：</span>約9,600万人（正確には9,615万人）は2060年時点の将来推計総人口である。<br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>④ 誤り：</span>現在の総人口水準に近い数値であり、2070年の推計値としては過大である。<br><br>◆ 関連知識・全体像：<br>将来推計人口（令和5年推計）における年齢3区分（年少、生産年齢、老年）の推移を以下に示す。<table class='w-full text-sm text-left text-gray-600 mt-3 border-collapse border border-gray-300'><thead class='bg-gray-100'><tr><th class='border border-gray-300 px-3 py-2'>年</th><th class='border border-gray-300 px-3 py-2'>総人口推計</th><th class='border border-gray-300 px-3 py-2'>高齢化率推計</th></tr></thead><tbody><tr><td class='border border-gray-300 px-3 py-2'>2060年</td><td class='border border-gray-300 px-3 py-2'>約9,615万人</td><td class='border border-gray-300 px-3 py-2'>約37.9%</td></tr><tr><td class='border border-gray-300 px-3 py-2'>2070年</td><td class='border border-gray-300 px-3 py-2'>約8,700万人</td><td class='border border-gray-300 px-3 py-2'>約38.7%</td></tr></tbody></table><br>```mermaid\\ngraph TD;\\n    A[総人口ピーク: 2008年] --> B[2060年将来推計: 約9,615万人];\\n    B --> C[2070年将来推計: 約8,700万人];\\n```\"\t\"[[\\\"\"#人口動態統計\\\"\\\"], [\\\"\\\"#人口動態統計\\\"\\\"], [\\\"\\\"#人口動態統計\\\"\\\"], [\\\"\\\"#人口動態統計\\\"\\\"]]\"\t",
  "必修問題\t目標Ⅰ. 看護の社会的側面及び倫理的側面について基本的な理解を問う。\tS\t1. 健康に関する指標\tA. 人口静態・人口動態\tb. 年齢別人口\tsingle\t日本の年齢別人口および人口構造の現状（令和4年/2022年）における、老年人口（65歳以上）の占める割合（高齢化率）として最も近いのはどれか。\t\"[\"\"① 約11.5%\"\", \"\"② 約21.0%\"\", \"\"③ 約29.0%\"\", \"\"④ 約59.0%\"\"]\"\t2\t【解説】日本の人口構造および高齢化率の現状（令和4年/2022年）に関する出題である。<br><br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>① 誤り：</span>約11.5%は同年の年少人口（0〜14歳）の割合である。<br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>② 誤り：</span>21%は国連等で「超高齢社会」と定義される基準値であり、日本の現在の高齢化率はこれを大幅に上回っている。<br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>③ 正解：</span>令和4年（2022年）の日本の老年人口割合（高齢化率）は約29.0%であり、超高齢社会がさらに進行している現状を示す。<br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>④ 誤り：</span>約59.0%は同年の生産年齢人口（15〜64歳）の割合である。<br><br>◆ 関連知識・全体像：<br>日本の人口3区分の定義と構成割合（令和4年）は以下の通りである。<table class='w-full text-sm text-left text-gray-600 mt-3 border-collapse border border-gray-300'><thead class='bg-gray-100'><tr><th class='border border-gray-300 px-3 py-2'>人口区分</th><th class='border border-gray-300 px-3 py-2'>対象年齢</th><th class='border border-gray-300 px-3 py-2'>構成割合（令和4年）</th></tr></thead><tbody><tr><td class='border border-gray-300 px-3 py-2'>年少人口</td><td class='border border-gray-300 px-3 py-2'>0〜14歳</td><td class='border border-gray-300 px-3 py-2'>約11.5%</td></tr><tr><td class='border border-gray-300 px-3 py-2'>生産年齢人口</td><td class='border border-gray-300 px-3 py-2'>15〜64歳</td><td class='border border-gray-300 px-3 py-2'>約59.0%</td></tr><tr><td class='border border-gray-300 px-3 py-2'>老年人口</td><td class='border border-gray-300 px-3 py-2'>65歳以上</td><td class='border border-gray-300 px-3 py-2'>約29.0%</td></tr></tbody></table>\t\"[[\\\"\"#保健統計指標\\\"\\\"], [\\\"\\\"#保健統計指標\\\"\\\"], [\\\"\\\"#保健統計指標\\\"\\\"], [\\\"\\\"#保健統計指標\\\"\\\"]]\"\t",
  "必修問題\t目標Ⅰ. 看護の社会的側面及び倫理的側面について基本的な理解を問う。\tS\t1. 健康に関する指標\tA. 人口静態・人口動態\tc. 労働人口\tsingle\t日本の労働力調査における労働力人口の動向および定義において、正しいのはどれか。\t\"[\"\"① 労働力人口は、15歳以上の就業者と完全失業者の合計である。\"\", \"\"② 家事や通学をしている非労働力人口は労働力人口に含まれる。\"\", \"\"③ 女性の労働力率は、結婚や育児の時期にあたる年齢階級で一貫して低下し続けている。\"\", \"\"④ 現在の日本の女性の労働力人口は、男性の労働力人口を上回っている。\"\"]\"\t0\t\"【解説】日本の労働力人口の定義と労働力率の動向に関する出題である。<br><br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>① 正解：</span>労働力人口は、15歳以上人口のうち、仕事をしている「就業者」と、仕事を探している「完全失業者」を足し合わせたものである。<br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>② 誤り：</span>通学や家事のみを行っており、仕事をしておらず求職活動もしていない者は「非労働力人口」に分類され、労働力人口には含まれない。<br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>③ 誤り：</span>女性の労働力率の年齢階級別グラフはかつて顕著な「M字カーブ」を描いていたが、近年は仕事と育児の両立支援の進展によりM字の底が浅くなり、就業を続ける女性が増加している。<br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>④ 誤り：</span>女性の労働力人口および労働力率は年々上昇傾向にあるが、総数としては依然として男性の労働力人口の方が上回っている。<br><br>◆ 関連知識・全体像：<br>```mermaid\\ngraph TD;\\n    A[15歳以上人口] --> B[労働力人口];\\n    A --> C[非労働力人口: 家事・通学・高齢退職者など];\\n    B --> D[就業者];\\n    B --> E[完全失業者: 求職活動中の者];\\n```\"\t\"[[\\\"\"#保健統計指標\\\"\\\"], [\\\"\\\"#保健統計指標\\\"\\\"], [\\\"\\\"#保健統計指標\\\"\\\"], [\\\"\\\"#保健統計指標\\\"\\\"]]\"\tsplit",
  "必修問題\t目標Ⅰ. 看護の社会的側面及び倫理的側面について基本的な理解を問う。\tS\t1. 健康に関する指標\tA. 人口静態・人口動態\te. 世帯数\tsingle\t令和3年（2021年）の国民生活基礎調査における、日本の世帯構造および世帯数割合について正しいのはどれか。\t\"[\"\"① 「三世代世帯」は、全世帯の中で約30%を占め最も割合が高い。\"\", \"\"② 「単独世帯（一人暮らし）」が、全世帯の約32.9%を占め最も割合が高い。\"\", \"\"③ 核家族を構成する「夫婦のみの世帯」は、近年一貫して減少している。\"\", \"\"④ 平均世帯人員は核家族化や単独世帯の増加を背景に、約3.5人へと増加している。\"\"]\"\t1\t【解説】日本の世帯構造と世帯構成割合の現状に関する出題である。<br><br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>① 誤り：</span>三世代世帯は近年急激に減少しており、全体のわずか約4.9%に留まっている。<br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>② 正解：</span>高齢単身世帯や未婚の若者による単独世帯が増加した結果、令和3年調査において「単独世帯」が全体の32.9%を占め、世帯構造別で最多となっている。<br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>③ 誤り：</span>「夫婦のみの世帯」は、子供の独立後や高齢夫婦世帯の増加を背景に、近年増加傾向にある。<br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>④ 誤り：</span>平均世帯人員は核家族化・単身化により減少し続けており、令和3年時点では2.37人である（3.5人は大幅に過大）。<br><br>◆ 関連知識・全体像：<br>世帯構造別の構成比（令和3年）：<table class='w-full text-sm text-left text-gray-600 mt-3 border-collapse border border-gray-300'><thead class='bg-gray-100'><tr><th class='border border-gray-300 px-3 py-2'>世帯構造</th><th class='border border-gray-300 px-3 py-2'>構成比（%）</th><th class='border border-gray-300 px-3 py-2'>特徴</th></tr></thead><tbody><tr><td class='border border-gray-300 px-3 py-2'>単独世帯</td><td class='border border-gray-300 px-3 py-2'>約32.9%</td><td class='border border-gray-300 px-3 py-2'>最多。高齢者の一人暮らし増加が背景。</td></tr><tr><td class='border border-gray-300 px-3 py-2'>夫婦と未婚の子のみ</td><td class='border border-gray-300 px-3 py-2'>約25.2%</td><td class='border border-gray-300 px-3 py-2'>かつての最多区分だが、現在は減少して第2位。</td></tr><tr><td class='border border-gray-300 px-3 py-2'>夫婦のみ</td><td class='border border-gray-300 px-3 py-2'>約24.5%</td><td class='border border-gray-300 px-3 py-2'>高齢者夫婦世帯を中心に増加傾向。</td></tr></tbody></table>\t\"[[\\\"\"#保健統計指標\\\"\\\"], [\\\"\\\"#保健統計指標\\\"\\\"], [\\\"\\\"#保健統計指標\\\"\\\"], [\\\"\\\"#保健統計指標\\\"\\\"]]\"\tsplit",
  "必修問題\t目標Ⅰ. 看護の社会的側面及び倫理的側面について基本的な理解を問う。\tS\t1. 健康に関する指標\tA. 人口静態・人口動態\tg. 出生の動向\tsingle\t日本の出生の動向および合計特殊出生率に関する記述として、正しいのはどれか。\t\"[\"\"① 合計特殊出生率とは、15〜49歳までのすべての女性が産む子供の合計数の「単純平均値」である。\"\", \"\"② 現在の日本において、人口規模を維持するために必要とされる「人口置換水準」は約2.07である。\"\", \"\"③ 近年の日本の合計特殊出生率は上昇に転じており、1.50を超えている。\"\", \"\"④ 晩婚化が進んでいるものの、第1子出産時の母親の平均年齢は25歳未満である。\"\"]\"\t1\t\"【解説】日本の合計特殊出生率および出生動向の定義と基準に関する出題である。<br><br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>① 誤り：</span>合計特殊出生率とは「ある年における15〜49歳までの女性の年齢別出生率を合計したもの」であり、単純に産んだ子供の数の平均値ではない（1人の女性が一生の間に産む子どもの数の目安となる指標）。<br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>② 正解：</span>人口規模を縮小させずに維持するために必要な出生水準を「人口置換水準」と呼び、現在の日本では約2.07である。<br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>③ 誤り：</span>近年の合計特殊出生率は1.30前後で推移しており、人口維持レベルである2.07を大幅に下回る低水準が続いている。<br>・<span class='bg-yellow-200 font-bold px-1 text-gray-900'>④ 誤り：</span>晩婚化・晩産化により、第1子出産時の母親の平均年齢は30歳を超えている（30.7〜30.9歳付近）。<br><br>◆ 関連知識・全体像：<br>```mermaid\\ngraph TD;\\n    A[合計特殊出生率 1.30前後] --> B[人口減少の加速];\\n    C[人口置換水準 2.07] --> D[必要な子供数];\\n    B --> E[少子高齢化問題の深刻化];\\n```\"\t\"[[\\\"\"#人口動態統計\\\"\\\"], [\\\"\\\"#人口動態統計\\\"\\\"], [\\\"\\\"#人口動態統計\\\"\\\"], [\\\"\\\"#人口動態統計\\\"]]\"\tsplit"
].join("\n");

if (typeof window !== "undefined") { window.SEED_QUESTIONS_TSV = SEED_QUESTIONS_TSV; }

if (typeof window !== "undefined") { window.CONCEPT_TAGS_MASTER = CONCEPT_TAGS_MASTER; }
if (typeof module !== "undefined" && module.exports) { module.exports = CONCEPT_TAGS_MASTER; }
