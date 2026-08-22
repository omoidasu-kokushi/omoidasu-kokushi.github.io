# 復旧手順（作業環境が巻き戻ったとき）

このZIPは**正本**です。作業用のクラウド環境は巻き戻ることがあり、
V1.23 以降で**7回**発生しました。そのときはここから戻します。

**V1.40 から `tests/` をZIPに同梱しています。** これ以前のZIPにはテストが入っておらず、
V1.39 の復旧時に batchL〜batchU の10スイートを失いました。同じことを繰り返さないための同梱です。

---

## 1. まず確認する

作業環境で次を実行し、**版番号がZIPより古ければ巻き戻っています**。

```bash
ls appH/*main_part1_V*.js appH/*main_part2_V*.js
grep "CACHE_NAME = " appH/sw.js
ls appH/drive.js appH/tests/
```

---

## 2. 戻す

1. このZIPをPC側で展開する
2. 展開したフォルダをステージして作業環境へ戻す
3. **md5 で1ファイルずつ突き合わせる**

```bash
cd <展開先> && md5sum $(find . -type f | sort) > /tmp/src.md5
cd appH        && md5sum $(find . -type f | sort) > /tmp/dst.md5
diff /tmp/src.md5 /tmp/dst.md5
```

**見た目が同じでも中身が違うことがあります。** 目視で済ませないこと。

4. 全スイートを通す（ここまでやって初めて「復旧できた」と言える）

```bash
cd appH && python3 -m http.server 8900 &
for t in tests/test_batch*.py tests/test_regress.py; do
  printf "%-24s " "$(basename $t)"; python3 "$t" 2>&1 | tail -1
done
```

**V1.42 時点の期待値：15スイート・821項目・全通過。**

---

## 3. ステージが `hardlinked` で拒否されたら

ファイルをいったんコピーしてからステージします。
それでも通らなければ、**旧版ZIPとの差分だけを取り出し、
exact-match 置換のパッチスクリプトで再構成**するのが確実です。

```python
def edit(src, old, new, count, label):
    n = src.count(old)
    if n != count:
        print('!! MISMATCH [%s]: expected %d, found %d' % (label, count, n))
        sys.exit(1)
    return src.replace(old, new, count)
```

**改修は常にこの形で行うこと。** 期待した文字列が無ければ即座に止まるので、
**巻き戻った版に誤ってパッチを当てる事故**を構造的に防げます。

---

## 4. ファイル名を変えたときに直す3箇所（＋1）

1. `index.html` の `<script src>`
2. `index.html` 冒頭の診断スクリプト内 `REQUIRED` 配列
3. `sw.js` の `CORE_ASSETS`
4. **`sw.js` の `CACHE_NAME` を必ず上げる**（上げ忘れると利用者に古いコードが残り続ける）

---

## 5. 中身の一覧

| 種別 | 内容 |
|---|---|
| アプリ | `index.html` `styles.css` `questions.js` `storage.js` `scheduler.js` `drive.js` `*main_part1*` `*main_part2*` |
| PWA | `sw.js` `manifest.json` `icons/` |
| 公開ページ | `about.html` `privacy.html` `terms.html` |
| 設計記録 | `DESIGN_DECISIONS.md` `CHANGELOG_*.md` `RECOVERY.md`（このファイル） |
| テスト | `tests/`（15スイート ＋ `mock_drive.js`） |
| その他 | `sample/` `vendor/mermaid.min.js` |

**作業を始める前に、必ず `DESIGN_DECISIONS.md` を読むこと。**
