# skills-youtube-make

YouTube動画用のスライド素材を、殴り書きメモまたは Cursor の会話ログ（`*.jsonl`）から順序立てて作成する Cursor Agent Skill。  
Googleスライドへの配置は、**画像を Drive へ手動アップロードしたあと**、`upload_to_slides.py` で一括投入する。

## 入力について

| 入力 | スキルの動き |
|------|-------------|
| 殴り書きメモ | そのまま構成作成へ |
| AI との会話履歴（`*.jsonl`） | **まず要約**（`source-notes.md`）→ 内容を承認してから構成へ |

jsonl は肥大化しやすくノイズも多いため、全文をそのままスライド化せず、要約を正本にする。

## フロー

```
skills-youtube-make（このリポ）で @youtube-video-make
  →（入力が *.jsonl なら）先に要約 → source-notes.md を承認
  → Phase 0 で形式・枚数・スタイル・確認ポイント
  → ../youtube-videos/{slug}/ に成果物を出力（サムネ含む）
  →【手動】images/（thumbnail.png 含む）を Drive ステージングへアップロード
  →【手動】空の Google スライドを SA に編集者共有
  → ターミナルで upload_to_slides.py（--presentation-id）一括投入
  →【手動】Vids → YouTube
```

## スキルの場所

`.cursor/skills/youtube-video-make/SKILL.md`（詳細手順・Phase 定義はこちら）

## リポジトリ構成（主要）

```
skills-youtube-make/
├── .cursor/skills/youtube-video-make/   # スキル本体
├── scripts/upload_to_slides.py          # Googleスライド投入
├── config/drive_staging.json            # 画像ステージングフォルダ ID
├── secrets/                             # サービスアカウント JSON（gitignore）
├── examples/sample-upload.json          # upload.json の例
└── requirements.txt
```

## 出力先

**スキルリポ内には書かない。** デフォルトはスキルリポの **1つ上** の `youtube-videos/{slug}/` です。

```
（任意の親フォルダ）/
├── skills-youtube-make/          ← スキル・スクリプト（このリポ）
└── youtube-videos/
    └── {slug}/                   ← 動画1本ごと（例: skill-appify-intro）
        ├── source-notes.md       # jsonl 入力時のみ
        ├── brief.md
        ├── structure.md
        ├── content.md
        ├── narrations.md
        ├── upload.json           # スクリプト用（必須）
        ├── youtube-meta.md
        ├── manual-steps.md
        ├── slides-result.json    # アップロード成功後に記録
        └── images/
            ├── thumbnail.png     # 必須・upload.json の先頭スライド
            └── slide-01.png …    # プレゼン型の例
```

ワークスペースを `youtube-videos/{slug}/` だけに開いた場合は、成果物はそのフォルダのルート（`.`）に出す（スキル SKILL.md 参照）。

### なぜ upload.json？

| Markdown だけ | JSON も出す |
|--------------|------------|
| 人間が読みやすい | スクリプトが壊れにくい |
| Python でパースが必要 | `json.load()` だけ |
| 画像パスとナレーションの紐付けが曖昧 | 1スライド1オブジェクトで明確 |

**おすすめ**: Markdown は人間用、`upload.json` は機械用として両方生成。`slides[0]` は必ずサムネ（`thumbnail.png`）。

## Googleスライドへアップロード

サービスアカウント（SA）は **Drive の保存容量が 0** のため、ローカル画像を直接新規アップロードできない。  
また SA 単体では **新規プレゼンの作成ができない** ため、先に空の Google スライドを用意し、SA を **編集者** で共有する。

| 項目 | 内容 |
|------|------|
| SA メール（共有用） | `sheets-to-stockscode20@getstockdata05.iam.gserviceaccount.com` |
| 画像ステージング | `config/drive_staging.json` の `image_folder_id` / URL（フォルダは SA に閲覧者以上で共有） |
| 認証 JSON | `secrets/getstockdata05-service-account.json`（gitignore） |

### 手順

1. **空の Google スライド**を新規作成し、上記 SA を **編集者** で共有。URL を控える。
2. ステージング用 Drive フォルダへ **`thumbnail.png` を含む** `images/` 一式を手動アップロード（フォルダは `config/drive_staging.json` 参照）。
3. リポジトリルートで実行:

```bash
pip install -r requirements.txt
python scripts/upload_to_slides.py ../youtube-videos/{slug} \
  --presentation-id "https://docs.google.com/presentation/d/PRESENTATION_ID/edit"
  # --image-folder-id は省略可（config/drive_staging.json を使用）
```

- 検証のみ（API 呼び出しなし）: `--dry-run`（`upload.json` とローカル `images/` の存在確認）
- 成功すると `{slug}/slides-result.json` にプレゼン URL が記録される
- `--prepend` は過去デッキ復旧用。**新規動画では使わない**（サムネは `upload.json` 先頭に含める）

### 動画フォルダをワークスペースにした場合

```bash
python /path/to/skills-youtube-make/scripts/upload_to_slides.py . \
  --credentials /path/to/skills-youtube-make/secrets/getstockdata05-service-account.json \
  --presentation-id "https://docs.google.com/presentation/d/PRESENTATION_ID/edit"
```

## 手動で行う作業

- Drive への画像アップロード（ステージング）
- Google スライドの新規作成と SA への共有
- Vids への動画変換・AI voiceover
- YouTube への公開

## トークンを節約する使い方

このリポジトリを「スキル置き場」と「動画ごとの作業場」に分けると、無駄なコンテキスト消費を抑えられる。

### 何がトークンを食うか

| 要因 | 目安 |
|------|------|
| スキル自動読み込み | SKILL.md + reference など 数千トークン |
| 会話の蓄積 | 1動画ごとに増える（最大の要因） |
| `youtube-videos/` の過去成果物 | スキルリポ外ならインデックス対象外 |
| 会話ログ `*.jsonl` | 1ファイルで数万トークン級になりうる |

### おすすめの運用

**A. リポジトリを2つに分ける（最もおすすめ）**

```
skills-youtube-make/              ← スキル・スクリプトだけ（このリポ）
youtube-videos/cursor-intro/      ← 動画1本＝1フォルダ（スキルリポの外）
youtube-videos/another-slug/      ← 2本目…
```

動画用フォルダにはスキルをコピーしない。個人スキルに置けば全プロジェクトから `@youtube-video-make` で呼べる:

```
~/.cursor/skills/youtube-video-make/   ← SKILL.md をここにコピー
```

**B. 1リポで続ける場合**

- **動画ごとに新しいチャット**を開く（会話履歴が最大の消費源）
- スキルは **明示的に呼ぶ**（`@youtube-video-make` または「スキルでスライド作って」）
- 成果物は `../youtube-videos/{slug}/` に出す（スキルリポ内に溜めない）
- 会話ログ `*.jsonl` はリポに置かない

### スキルの読み込み設定

`disable-model-invocation: true` にしている。自動では載らず、**呼んだときだけ** SKILL.md がコンテキストに入る。
