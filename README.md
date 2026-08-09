# skills-youtube-make

YouTube動画用のスライド素材を、殴り書きメモから順序立てて作成し、Googleスライドに自動アップロードする Cursor Agent Skill。

## フロー

```
skills-youtube-make（このリポ）で @youtube-video-make
  →（入力が *.jsonl なら）先に要約 → source-notes.md を承認
  → Phase 0 で形式・枚数・スタイル・確認ポイント
  → ../youtube-videos/{slug}/ に成果物を出力（サムネ含む）
  →【手動】images/（thumbnail.png 含む）を Drive ステージングへアップロード
  → ターミナルで upload_to_slides.py（--presentation-id）一括投入
  →【手動】Vids → YouTube
```

## スキルの場所

`.cursor/skills/youtube-video-make/SKILL.md`

## 出力先

**スキルリポ内には書かない。** デフォルト:

```
C:\Users\sinzy\
├── skills-youtube-make/          ← スキル・スクリプト（このリポ）
└── youtube-videos/
    └── cursor-intro/             ← 動画1本ごとの成果物
        ├── upload.json
        ├── images/
        └── ...
```

### なぜ upload.json？

| Markdown だけ | JSON も出す |
|--------------|------------|
| 人間が読みやすい | スクリプトが壊れにくい |
| Python でパースが必要 | `json.load()` だけ |
| 画像パスとナレーションの紐付けが曖昧 | 1スライド1オブジェクトで明確 |

**おすすめ**: Markdown は人間用、`upload.json` は機械用として両方生成。

## Googleスライドへアップロード

サービスアカウントは Drive 容量が無いため、**先に画像を共有フォルダへ手動アップロード**する。

1. 画像ステージング用の Drive フォルダへ `images/` をアップロード  
   （フォルダ ID / URL は `config/drive_staging.json` を参照。README には書かない）
2. 空の Google スライドを SA に編集者共有
3. 実行:

```bash
pip install -r requirements.txt
python scripts/upload_to_slides.py ../youtube-videos/{slug} \
  --presentation-id "https://docs.google.com/presentation/d/PRESENTATION_ID/edit"
  # --image-folder-id は省略可（config/drive_staging.json を使用）
```

- 認証: `secrets/getstockdata05-service-account.json`
- 検証のみ: `--dry-run`

## 手動で行う作業

- Drive への画像アップロード（ステージング）
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
skills-youtube-make/     ← スキル・スクリプトだけ（このリポ）
youtube-videos/cursor-intro/    ← 動画1本＝1フォルダ（スキルリポの外）
youtube-video-python/    ← 動画2本分…
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
