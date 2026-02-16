# YouTube Keyword Ecosystem Analyzer (Web App)

1つの「メインキーワード」から、類義語・サジェスト（関連語）を網羅的に検索し、それぞれのキーワードの動画市場規模・ボリューム・トレンド・**掲載順位**を詳細分析するツールです。

**Current Version: v1.4.0**

## 特徴
1. **掲載順位 (Rank) 取得**:
    - YouTube検索結果（おすすめ順）の1位〜上位の順位を記録します。
    - シークレットモード（ゲスト）と同等の標準的な順位を取得します。
2. **詳細動画リスト**:
    - キーワードごとの集計だけでなく、ヒットした全動画のリスト（順位、タイトル、再生数、URL etc）もダウンロード可能になりました。
3. **エコシステム分析**:
    - 類義語 (Datamuse API)
    - サジェスト (YouTube Autosuggest)
4. **厳密な指標**:
    - 動画数内訳（～365日）
    - 平均再生数（上位層別）

## セットアップ

1. **Pythonの準備**: Python 3.8以上。
2. **インストール**:
    ```bash
    pip install -r requirements.txt
    ```
3. **APIキー**: YouTube Data APIキーが必要です。

## 起動方法

```bash
streamlit run app.py
```

## 出力データ (CSV)

### 1. `ecosystem_analysis.csv` (キーワード集計)
- **keyword**: キーワード
- **video_count**: ヒット数
- **avg_top_XX**: 各層の平均再生数
- ...他（市場規模分析用）

### 2. `video_list_detailed.csv` (動画詳細 & 順位)
- **Keyword**: 検索キーワード
- **Rank**: **検索順位** (1位～)
- **Title**: 動画タイトル
- **Channel**: チャンネル名
- **Views**: 再生数
- **Duration(s)**: 動画時間
- **Published**: 投稿日時
- **URL**: 動画リンク

## 別のPCへの移行方法 (配布方法)

このツールを別のPCで使用するには、以下の手順を行ってください。

1. **フォルダのコピー**:
    - `channel_search` フォルダ全体を ZIP 圧縮して、別のPCに送ります。
    - 別のPCで ZIP を解凍します。

2. **Pythonのインストール**:
    - もし移動先のPCにPythonが入っていない場合、[公式サイト](https://www.python.org/downloads/)からインストールしてください (Python 3.10以上推奨)。
    - インストール時、**「Add Python to PATH」** にチェックを入れるのを忘れないでください。

3. **セットアップ (初回のみ)**:
    - 解凍したフォルダの中でコマンドプロンプト（またはターミナル）を開きます。
    - 以下のコマンドを実行して、必要なライブラリをインストールします。
    ```bash
    pip install -r requirements.txt
    ```

4. **起動**:
    - 以下のコマンドで起動します。
    ```bash
    streamlit run app.py
    ```

5. **APIキー**:
    - フォルダ内の `.env` ファイルも一緒にコピーされていれば、APIキーはそのまま引き継がれます。
    - もしコピーされていない場合は、起動後の画面で再度入力してください。
