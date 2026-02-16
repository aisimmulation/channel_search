# WordPressへの移行・導入ガイド

このフォルダには、YouTube検索ツールをサーバーへ移行するためのファイル一式が含まれています。
本ツールは **Python製のWebアプリケーション** (Streamlit) であるため、WordPressのプラグインとして直接アップロードすることはできません。

以下の手順で、サーバー上でPythonアプリケーションとして稼働させ、WordPressから利用できるようにしてください。

## 1. サーバー要件

WordPressが動作しているサーバー（または別のサーバー）で、以下の環境が必要です。

- **OS**: Linux (Ubuntuなど) または Windows Server
- **Python**: バージョン 3.8 以上
- **権限**: コマンドライン（ターミナル/SSH）での操作権限

※一般的なレンタルサーバー（エックスサーバーの標準プランなど）ではPythonアプリを常駐させることができない場合があります。その場合は **VPS** (Xserver VPS, ConoHa VPS, AWS EC2など) を利用するか、**Streamlit Community Cloud** などのクラウドサービスを利用してください。

## 2. 設置手順 (VPS/サーバーの場合)

1. **ファイルのアップロード**:
   このフォルダの中身をサーバーの任意のディレクトリ（例: `/var/www/channel_search` や `/home/user/app`）にアップロードします。

2. **Python環境の準備**:
   ```bash
   # 仮想環境の作成（推奨）
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **ライブラリのインストール**:
   ```bash
   pip install -r requirements.txt
   ```

4. **APIキーの設定**:
   `.env` ファイルを開き、自身のYouTube Data APIキーが設定されているか確認してください。
   ```
   YOUTUBE_API_KEY=あなたのAPIキー
   ```

5. **アプリケーションの起動**:
   バックグラウンドで実行し続けるには `nohup` などを使用します。
   ```bash
   nohup streamlit run app.py --server.port 8501 &
   ```
   これで `http://サーバーIP:8501` でアクセスできるようになります。

## 3. WordPressへの埋め込み

WordPressの固定ページなどに、以下のHTMLコード（iframe）を貼り付けることで、サイトの一部として表示できます。

```html
<iframe src="http://あなたのサーバーIPまたはドメイン:8501" width="100%" height="800" frameborder="0"></iframe>
```

※HTTPSのサイト（WordPress）からHTTPのアプリ（Streamlit）を埋め込むとブロックされる場合があります。その場合は、Streamlit側もSSL化（nginxでのリバースプロキシ設定など）が必要です。

## 4. ファイル構成

- `app.py`: メインプログラム
- `youtube_api.py`: YouTubeデータ取得・検索ロジック
- `keyword_utils.py`: キーワード関連処理
- `metrics_utils.py`: 指標計算処理
- `requirements.txt`: 必要なライブラリ一覧
- `.env`: APIキー設定ファイル
