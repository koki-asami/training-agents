# 防災訓練自動化システム

AI Agentによる自治体向け状況付与訓練シミュレーションシステム。

豪雨災害を想定し、AI が各部署・住民を演じることで、大勢が集まらなくても隙間時間に防災訓練を実施できます。

## 特徴

- **マルチエージェント**: 8種の役割（総務部・消防局・建設部・福祉部・住民・気象情報等）をAIが担当
- **複数人参加**: 任意の役割を人間が担当可能。1人でも複数人でも訓練できる
- **動的シナリオ**: 参加者の行動に応じてシナリオが自動で変化（対応遅延→被害拡大 等）
- **3段階の難易度**: 初級（ヒント付き）〜上級（リソース不足・同時多発・時間圧迫）
- **自動スコアリング**: 応答時間・判断品質・優先順位付けを評価しレポート生成
- **Anthropic / OpenAI 両対応**: 環境変数で切り替え

## アーキテクチャ

```
[参加者A]  [参加者B]  [参加者C]
 ブラウザ    ブラウザ    ブラウザ
     |          |          |
     +--- WebSocket -------+
                |
         [FastAPI Backend]
                |
     +----------+----------+
     |          |          |
 [Scenario  [State     [Event
  Master]   Manager]   Scheduler]
     |
 [総務部] [消防局] [建設部] [福祉部] [住民x3] [気象情報]
  AI/人間  AI/人間  AI/人間  AI/人間   AI      AI
```

## セットアップ

### 必要環境

- Python 3.11+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) (Pythonパッケージマネージャ)

### インストール

```bash
# バックエンド
uv sync

# フロントエンド
cd frontend
npm install
```

### 環境変数

`.env.example` を `.env` にコピーして API キーを設定:

```bash
cp .env.example .env
```

**Anthropic を使う場合（デフォルト）:**

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

**OpenAI を使う場合:**

```
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxx
OPENAI_MODEL=gpt-4o
```

### 起動

```bash
# バックエンド（ターミナル1）
uv run uvicorn src.api.app:app --reload

# フロントエンド（ターミナル2）
cd frontend
npm run dev
```

ブラウザで http://localhost:5173 を開くとセッション設定画面が表示されます。

## 使い方

### 1. セッション作成

- 自治体名・難易度・シナリオファイルを選択
- 各役割（本部長・総務部・消防局・建設部・福祉部）を「人間」か「AI」に割り当て
- 「訓練セッションを作成」をクリック

### 2. 訓練実施

- 「訓練開始」で時間が進行し、シナリオに沿って状況が付与される
- 各部署（AI）から報告が届くので、指示を出す
- チャットは部署別チャンネルで切り替え可能
- 右側パネルで気象・水位・リソース状況をリアルタイム確認

### 3. スコア確認

訓練終了後、`GET /api/sessions/{session_id}/report` でレポートを取得:

- イベントごとの評価（5段階）
- 応答時間の分析
- 強み・弱み・改善提案

## 難易度

| | 初級 | 中級 | 上級 |
|--|------|------|------|
| 時間圧縮 | 2:1（一時停止可） | 3:1 | 4:1 |
| 情報品質 | 明確 | 一部未確認 | 断片的・矛盾 |
| イベント数 | ~10（逐次） | ~20（2-3並行） | ~30+（4-5並行） |
| リソース | 十分 | やや不足 | 深刻な不足 |
| ヒント | あり | なし | なし |

上級では全タスクを時間内に完了できない状況が意図的に作られ、ボトルネック分析と優先度判断の訓練を行います。

## シナリオ

`data/scenarios/sample.json` にサンプルシナリオ（熊本市・豪雨災害・6イベント）が含まれています。

シナリオの自動生成には [training-scenario-generator](https://github.com/koki-asami/training-scenario-generator) を利用できます。

### シナリオ形式

```json
{
  "municipality": "熊本市",
  "events": [
    {
      "付与番号": "1",
      "付与内容": "大雨注意報発表",
      "時間": "06:00",
      "情報源": "気象台",
      "内容_管理用詳細": "...",
      "内容_訓練者向け": "...",
      "期待される対応行動": "...",
      "想定される課題": "..."
    }
  ]
}
```

## API

| エンドポイント | メソッド | 説明 |
|---|---|---|
| `/api/sessions` | POST | セッション作成 |
| `/api/sessions` | GET | セッション一覧 |
| `/api/sessions/{id}` | GET | セッション詳細 |
| `/api/sessions/{id}/start` | POST | 訓練開始 |
| `/api/sessions/{id}/stop` | POST | 訓練終了 |
| `/api/sessions/{id}/pause` | POST | 一時停止（初級のみ） |
| `/api/sessions/{id}/scores` | GET | スコア取得 |
| `/api/sessions/{id}/report` | GET | 訓練レポート |
| `/api/sessions/{id}/messages` | GET | メッセージ履歴 |
| `/api/ws/simulation/{id}/{pid}` | WS | リアルタイム通信 |

起動後 http://localhost:8000/docs で Swagger UI から確認できます。

## プロジェクト構造

```
src/
├── agents/          # AI Agent（シナリオマスター・各部署・住民・気象）
├── api/             # FastAPI（REST + WebSocket）
├── engine/          # シミュレーションエンジン（時計・スケジューラー・状態管理）
├── scoring/         # スコアリング・レポート生成
├── tools/           # 各Agentのツール定義（救助派遣・道路封鎖・避難所開設等）
├── models/          # Pydanticデータモデル
├── loaders/         # シナリオ読込（JSON/Excel）
├── difficulty/      # 難易度プロファイル
└── persistence/     # SQLite永続化
frontend/            # React + TypeScript（統合ダッシュボード）
data/scenarios/      # シナリオファイル
```

## 関連リポジトリ

- [training-scenario-generator](https://github.com/koki-asami/training-scenario-generator) - 訓練シナリオの自動生成
- [disaster-management-workflow-extraction-system](https://github.com/koki-asami/disaster-management-workflow-extraction-system) - 災害対応タスクと依存関係の抽出
