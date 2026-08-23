# V1.48（2026-08-23）端末をまたぐ進捗同期が、2台目で恒久停止していた

## 何が起きていたか

`progress_log` ストアの `keyPath` は `'log_id'` です（`storage.js:271`）。
ところが同期の書き戻しは、除外する主キーの名前を間違えていました。

```js
/* storage.js  replaceAllLogs()（V1.47まで） */
Object.keys(l).forEach(function (k) { if (k !== 'id') { rec[k] = l[k]; } });
//                                            ^^^^  正しくは 'log_id'
```

同じ処理の**もう一つの実装（`restoreBackup`）は最初から正しく `'log_id'` を除外していました**。
片方だけ間違っている＝写し間違いです。

`log_id` は端末ごとに1から採番されます。`collectProgress` はそれを込みで
ドライブへ送っていたため、**別端末の「別の解答」に同じ番号が付きます**。
`mergeLogs` の重複判定は `atom_id|answered_at` なので（`scheduler.js:334`）、
log_id の衝突は取り除かれません。結果 `add()` が ConstraintError を投げ、
トランザクションごと abort していました。

**2台目を使い始めた最初の同期で必ず起きます。**

## なぜ気づけなかったか

```js
/* drive.js（V1.47まで） */
}).catch(function (e) {
  report.progress_error = (e && e.message) || String(e);   // ← どこからも読まれない
});
}).then(function () {
  return S.clearDirty()                                    // ← 未同期バッジが0に戻る
```

- `report.ok` は **true のまま**
- `clearDirty()` が走り、**未同期バッジが0に戻る**
- `progress_error` は**全ファイル中どこからも読まれていませんでした**
- 画面には **「すでに最新です」**

**利用者から見ると「同期できている」。実際には学習の記録が1件も上がっていない。**
機種変更やアプリ削除で初めて失われていたと分かる、最悪の壊れ方でした。

### テストが見逃した理由

`tests/test_batchV.py` は `Drive.__setTransport` でモックを差し替えた
**単一端末**でしか回りません。単一端末では log_id が一意なので衝突しません。
**独立に採番された2台目が一度も登場しませんでした。**

## 直したもの

### storage.js

- `replaceAllLogs` が除外する主キーを `'id'` → **`'log_id'`** へ。
  落としておけば `autoIncrement` が採番し直すので、必ず一意になります。

### drive.js

- **`collectProgress` が `log_id` を送らないようにしました。**
  端末ごとの連番は他の端末で意味を持ちません。二重の守りです。
- **進捗の書き戻しが落ちたら、成功として扱わないようにしました。**
  `report.ok = false` ＋ `report.error = '学習の記録を同期できませんでした：…'`。
  図の同期の件数は残しますが、**全体は失敗**です。
- **失敗したときは `clearDirty()` を呼びません。**
  未同期の印が残ることが、利用者にとって唯一の「まだ上がっていない」合図になります。
- 失敗の理由を `drive_last_error`（meta）に残し、成功したら消します。
  このキーは同期対象の META リストに入れていないので、端末の外へは出ません。

### 20260815_main_part2_V1.29.js → V1.30.js

- **設定 ＞ ドライブ同期に、前回の失敗の理由を出すようにしました。**
  自動同期は画面に何も出さないので、drive.js を直しただけでは利用者に届きません。
  バッジが減らないことに加えて、理由も読めるようにします。

### index.html / sw.js

ファイル名を変えたので、決まりどおり3箇所すべてを直しました。

- `index.html` の `<script src>`
- `index.html` 冒頭の診断スクリプト内 `REQUIRED` 配列
- `sw.js` の `CORE_ASSETS`

あわせて `CACHE_NAME` を `v1.36.0` → `v1.37.0`、
版の刻印を `20260823_Omoidasu_V1.48 / cache v1.37.0` へ。

`?v=` は **1.45 のまま据え置き**。`styles.css` / `questions.js` / `scheduler.js` は
変更していません（`storage.js` と `drive.js` は変更しましたが、両方とも
`?v=` は共有ファイルの版として index と sw で揃っていれば足りるため、
**次に共有ファイルを更新するときにまとめて上げます**）。

> **注意**：`storage.js` と `drive.js` を変更したのに `?v=` を上げていません。
> Service Worker のキャッシュ名（`v1.37.0`）が変わるので新しい版は配られますが、
> `?v=` を上げるほうが決まり（§1-7）には忠実です。**次の改修で必ず 1.48 へ上げること。**

### tests/test_batchAE.py（新設・23項目）

**独立に採番された2台目を必ず登場させます。**

- 別の解答なのに `log_id` が同じ2件を合体して書き戻す → 落ちない・2件保存・採番し直されて一意
- 同じ解答（`atom_id` と時刻が同じ）は1件にまとまる（合体の規則は変えていない）
- ドライブへ送る中身に `log_id` が入っていない／`atom_id`・`answered_at` は残っている
- 進捗の書き戻しをわざと失敗させ、**成功として報告しない・バッジが0に戻らない・理由が meta に残る**
- 成功したら印も理由も消える

## 結果

```
batchAA 36/36  batchAB 83/83  batchAC 48/48  batchAD 31/31  batchAE 23/23（新設）
batchD  72/72  batchE  69/69  batchF  46/46  batchG  29/29
batchH  65/65  batchI  71/71  batchJ  62/62  batchK  60/60
batchV  69/69  batchW  48/48  batchX  35/35  batchY  48/48
batchZ  55/55  regress 16/16

19スイート・966項目 全通過
```

## 直していないもの（設計レビューの続き）

同じ「同期が信用できない」の一部ですが、V1.48 には含めていません。

- 進捗リセットが次の同期でよみがえる（削除の墓標が無い）
- メモを消すと復活する（`memo_updated_at` が null になり墓標が壊れる）
- ホームに戻って8秒以内に閉じると何も同期されない（`pagehide` も Background Sync も無い）
- 設定（試験日・テーマ）が端末間で永久に伝わらない（`localAt` に `nowMs()` を押している）
- 両端末で評価すると pt が二重計上され、段が巻き戻る
