# 定期取得デモ

[![定期取得](https://github.com/nanasejob7-ai/auto-collect-demo/actions/workflows/collect.yml/badge.svg)](https://github.com/nanasejob7-ai/auto-collect-demo/actions/workflows/collect.yml)
[![公開ページ](https://img.shields.io/badge/公開ページ-稼働中-2dd4bf)](https://nanasejob7-ai.github.io/auto-collect-demo/)

公開データを毎日決まった時刻に取得し、蓄積して表示するサンプルです。
業務自動化の受注時にお渡しする構成を、そのまま公開できる題材で組んだものです。

### 📡 実際に動いているところを見る

| | |
|---|---|
| **表示ページ（自動更新）** | https://nanasejob7-ai.github.io/auto-collect-demo/ |
| **実行履歴（毎朝の記録）** | [Actions タブ](https://github.com/nanasejob7-ai/auto-collect-demo/actions/workflows/collect.yml) |
| **蓄積データ（生JSON）** | [docs/data.json](docs/data.json) |
| **品質レポート（自動生成）** | [docs/quality_report.md](docs/quality_report.md) |

上のバッジは**現在の実行状態をリアルタイムで表示**しています。緑なら直近の自動実行が成功しています。
実行履歴はログまで公開されているので、いつ・何を取得したかを誰でも確認できます。

---

## 何をしているか

```
毎朝 06:10 JST（GitHub Actions）
    ↓
公開データを取得        scripts/collect.py
    ↓
構造を検証             想定と違えば「続行せず停止」
    ↓
必要な値だけ抽出        日付・天気・気温
    ↓
蓄積して保存           docs/data.json（同じ日付は上書き）
    ↓
品質を記録             docs/quality_report.md（必須項目の充足率）
    ↓
コミット & 表示更新
    ↓
失敗したら Issue を自動作成（sync-error ラベル）
```

---

## 設計で意識したこと

### 1. 想定と違ったら、黙って続けない

取得元の構造が変わったとき、近い名前のキーを拾って処理を続けると、
**間違ったデータが正しい顔をして保存されます。**

そのため構造の変化を検出したら `SchemaChangedError` で異常終了させ、
ログに「近い名前のキーで処理を続けると誤ったデータが保存されます」と明示します。

### 2. 欠損を埋めない

最低気温は予報に含まれない日があります。
見た目を整えるために 0 や前日値で埋めると、
**エラーは出ていないのに数字だけが合わない**という最も気づきにくい不具合になります。

空欄は空欄のまま残し、充足率としてレポートに出します。

### 3. 失敗を人間が見に行かなくていい

ワークフローが失敗すると Issue が自動で立ち、GitHub からメールが飛びます。
同じ内容の Issue を毎日作らないよう、既存の open Issue を確認してから作成します。

### 4. あとから監査できる

全レコードに `source` / `source_url` / `fetched_at` を持たせています。
「この数字はいつ、どこから取ったのか」を後から追えます。

---

## 動かし方

```bash
python3 scripts/collect.py
```

- 追加ライブラリは不要です（標準ライブラリのみ）
- `docs/data.json` と `docs/quality_report.md` が更新されます
- 同じ日付のレコードは上書きされるので、何度実行しても重複しません

**手動実行（GitHub上）:** Actions タブ → 「定期取得」 → Run workflow

---

## 止め方

- 一時的に止める: Actions タブ → 「定期取得」 → `···` → Disable workflow
- 恒久的に止める: `.github/workflows/collect.yml` を削除

---

## うまくいかないときの確認手順

| 症状 | 確認すること |
|---|---|
| ログに `[構造の変化を検出]` | 取得元の仕様変更。`extract()` の参照キーを修正する |
| 取得はできるが値が空 | 取得元が一時的にデータを出していない可能性。時間をおいて手動実行 |
| コミットされない | `docs/` に差分が無い場合はスキップする仕様（正常） |
| 実行自体が始まらない | スケジュール実行は混雑時に遅延することがある。手動実行で切り分け |

---

## 費用について

このリポジトリは**公開リポジトリ**なので、GitHub Actions の実行時間は無料枠の対象外（無制限）です。

非公開リポジトリの場合は無料枠に上限があります（Free プランで月2,000分）。
実行頻度やデータ量によっては費用が発生するため、
実際のご依頼では想定される実行回数をうかがったうえで、着手前に試算をお伝えしています。

---

## 構成

```
.
├── .github/workflows/collect.yml   定期実行と失敗通知
├── scripts/collect.py              取得・検証・蓄積・品質レポート
└── docs/
    ├── index.html                  表示ページ
    ├── data.json                   蓄積データ（自動生成）
    └── quality_report.md           品質レポート（自動生成）
```

取得元は気象庁の公開データ（認証不要）です。
