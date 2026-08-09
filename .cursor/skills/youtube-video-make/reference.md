# リファレンス: テンプレートと手動手順

## source-notes.md（jsonl 要約時・正本）

`*.jsonl` 入力時、Phase 0S で作成する。以降の構成・本文はこのファイルだけを正本にする。

```markdown
# 動画用メモ（会話ログ要約）

## テーマ
## ゴール
## 前提
## 手順（時系列）
1.
2.

## ハマりどころ・注意点
-

## 使ったコマンド / API / 画面（重要だけ）
-

## 動画で省略してよいこと
-

## 元ログ
- ファイル:
- 要約日:
```

秘密情報（トークン、パスワード等）は書かない。

## upload.json（アップロード用・必須）

スキルが Phase 6 で生成する。**人間用の Markdown と機械用の JSON を両方出す。**

| ファイル | 用途 |
|---------|------|
| `content.md` / `narrations.md` | 人間が読んで確認・修正 |
| `upload.json` | `upload_to_slides.py` が読む（Markdown 解析不要） |

### なぜ JSON 化するか

- Markdown を Python でパースする必要がない（壊れにくい）
- スライド番号・ナレーション・画像パスが1オブジェクトにまとまる
- `--dry-run` でアップロード前に検証できる
- テスト用の JSON を差し替えてスクリプトだけ試せる

### スキーマ（version 1）

#### プレゼン型

```json
{
  "version": 1,
  "title": "動画タイトル",
  "format": "presentation",
  "aspect_ratio": "16:9",
  "slides": [
    {
      "index": 1,
      "slide_type": "opening",
      "title": "スライドタイトル",
      "bullets": ["要点1", "要点2", "要点3"],
      "narration": "読み上げ台本（スピーカーノートに入る）",
      "image": "images/slide-01.png"
    }
  ]
}
```

#### マンガ型

```json
{
  "version": 1,
  "title": "動画タイトル",
  "format": "manga",
  "aspect_ratio": "16:9",
  "slides": [
    {
      "index": 1,
      "slide_type": "opening",
      "scene": "場面の説明（人間用メモ）",
      "narration": "読み上げ台本（スピーカーノートに入る）",
      "image": "images/scene-01.png"
    }
  ]
}
```

### フィールドルール

| フィールド | 必須 | 説明 |
|-----------|------|------|
| `version` | ✅ | 常に `1` |
| `title` | ✅ | Googleスライドのタイトル |
| `format` | ✅ | `presentation` または `manga` |
| `slides[].index` | ✅ | 1始まりの連番 |
| `slides[].slide_type` | ✅ | `thumbnail` / `opening` / `body` / `ending` など |
| `slides[].narration` | ✅ | スピーカーノートに書き込まれる |
| `slides[].image` | ✅ | 成果物フォルダからの相対パス（例: `images/slide-01.png`） |
| `slides[].title` | プレゼン型 | スライド見出し（サムネは短くてよい） |
| `slides[].bullets` | プレゼン型 | 箇条書き（文字列の配列）。サムネは `[]` 可 |
| `slides[].scene` | マンガ型 | 場面メモ（アップロードには使わない） |

`image` のパスは必ずスラッシュ区切り。

**先頭スライドは必ずサムネ:**

```json
{
  "index": 1,
  "slide_type": "thumbnail",
  "title": "動画タイトル",
  "bullets": [],
  "narration": "短いフック（8〜15秒）",
  "image": "images/thumbnail.png"
}
```

アップロード時、`slide_type: "thumbnail"` は **全面画像**（BLANK レイアウト）として配置する。

**新規動画では** `upload.json` 作成時点でサムネを含める。本編完成後にサムネだけ `--prepend` する流れは標準にしない（既存デッキの緊急復旧用）。

## content.md テンプレート

### プレゼン型

```markdown
# 確定コンテンツ: {タイトル}

## スライド 1 — サムネ
**タイトル**: {動画タイトル}
**箇条書き**:
- （なし。画像が主役）

**スピーカーノート**: YouTubeサムネ兼用。導入ナレーション用
**画像の方向性**: 16:9サムネ。大きなタイトル文字入り可。スタイルは brief.md に合わせる

---

## スライド 2 — オープニング
**タイトル**: {見出し}
**箇条書き**:
- {要点1}
- {要点2}

**スピーカーノート**: {制作メモ・補足説明}
**画像の方向性**: {何を描くか。スタイルは brief.md 参照}

---

## スライド 3 — 本編
（以下同様）
```

### マンガ型

```markdown
# 確定コンテンツ: {タイトル}

## シーン 1 — オープニング
**場面**: {何が起きているか}
**ナレーション概要**: {このコマで話すことの要約}

**画像プロンプト要素**:
- 人物: {外見の固定描写 — 全シーンで再利用}
- 動作: {何をしているか}
- 背景: {場所・雰囲気}
- 画風: {brief.md の画像スタイル}
- 文字: なし（デフォルト）

---

## シーン 2
（以下同様）
```

## キャラ一貫性（マンガ型）

同一キャラが複数シーンに登場する場合、`brief.md` に固定描写を記録する:

```markdown
## キャラ設定
- 主人公: 20代女性、短い黒髪、オレンジのパーカー、丸眼鏡
```

各画像プロンプトの先頭にこの描写を含める。

## manual-steps.md テンプレート

```markdown
# 手動連携手順

## 前提
- 成果物フォルダ: `../youtube-videos/{slug}/` または動画専用フォルダ
- 形式: {マンガ型 / プレゼン型}
- 枚数: {N}枚

## Step 1: 画像を Drive ステージングフォルダへアップロード（必須）

サービスアカウントは Drive 容量が無いため、ローカル画像を直接上げられない。

1. フォルダを開く: https://drive.google.com/drive/folders/1lBk5TQFmcA-Atygu0jV1NKGwT3o4kicB?usp=sharing
2. 成果物の `images/` 内ファイル（**`thumbnail.png` 必須** + `slide-XX.png` または `scene-XX.png`）をアップロード（同名は上書き）
3. 空の Google スライドを用意し、SA を編集者で共有。URL を控える

## Step 2: Googleスライドに素材を配置

**自動（推奨）:**

```bash
pip install -r requirements.txt
python scripts/upload_to_slides.py ../youtube-videos/{slug} \
  --presentation-id "https://docs.google.com/presentation/d/PRESENTATION_ID/edit" \
  --image-folder-id "1lBk5TQFmcA-Atygu0jV1NKGwT3o4kicB"
```

`slides-result.json` にプレゼン URL が記録される。

**手動（スクリプトを使わない場合）:**

### プレゼン型
1. Googleスライドで新規プレゼンテーションを作成（16:9）
2. 各スライドに `content.md` のタイトル・箇条書きを入力
3. `images/slide-XX.png` を対応するスライドに配置（右側または下部）
4. デザインテーマを統一

### マンガ型
1. Googleスライドで新規プレゼンテーションを作成（16:9）
2. 各スライドに `images/scene-XX.png` を全面配置
3. テキストは入れない（ナレーションで説明）

## Step 3: Vids に連携
1. Googleスライドで「動画に変換」ボタンを押す
2. Google Vids に連携される
3. `narrations.md` を参考に、各ページのナレーション（音声）を設定

## Step 4: YouTube に公開
1. Vids で「YouTubeに変換」を押す
2. `youtube-meta.md` のタイトル・説明・タグを入力
3. サムネイル・公開設定を調整して公開
```

## 画像プロンプトの書き方

### プレゼン型（補助画像）

```
{画風} style illustration, 16:9 aspect ratio.
Subject: {概念・図解の内容}.
Simple, clean, no text, no watermark.
Colors: {配色方針}.
Purpose: supplementary visual for a presentation slide about {トピック}.
```

### マンガ型（場面画像）

```
{画風} style scene illustration, 16:9 aspect ratio.
Character: {brief.md のキャラ設定}.
Action: {動作・表情}.
Setting: {背景・場所}.
No text, no speech bubbles, no watermark.
Consistent character design across scenes.
```

## 枚数の目安（長さから逆算）

| 動画の長さ | プレゼン型 | マンガ型 |
|-----------|-----------|---------|
| 1〜2分 | 5〜7枚 | 6〜8コマ |
| 3分 | 8〜10枚 | 10〜12コマ |
| 5分 | 12〜15枚 | 15〜18コマ |
| 10分 | 20〜25枚 | 25〜30コマ |

「内容に合わせて提案して」と指定された場合は、メモの情報量から上表を参考に提案する。

## 確認ポイントの動作

| 選択 | Phase 1後 | Phase 3後 | Phase 4後 | Phase 5 |
|------|----------|----------|----------|---------|
| A | 停止 | 自動 | 自動 | 自動 |
| B | 停止 | 停止 | 自動 | 自動 |
| C | 停止 | 停止 | 停止 | 自動 |
| D | 自動 | 自動 | 自動 | 自動 |

「停止」= ユーザー承認を待つ。「自動」= 承認なしで次へ進む。
