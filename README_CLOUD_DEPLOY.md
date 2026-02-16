# 無料でWeb公開する方法 (Streamlit Community Cloud)

WordPressの一般的なレンタルサーバー（FTPでアップロードするタイプ）では、残念ながらPython製のアプリを動かすことができません。
その代わり、**Streamlit Community Cloud** という無料サービスを使うのが最も簡単で標準的な方法です。

この方法なら、サーバーの契約も難しいコマンド操作も不要です。

## 手順

### 1. GitHubアカウントの作成（必須）
まだ持っていない場合は [GitHub](https://github.co.jp/) で無料アカウントを作成してください。
※これだけは必要になります。

### 2. ファイルのアップロード
1. GitHubにログインし、「New repository」から新しいリポジトリを作ります（名前は何でもOK、例: `youtube-search-app`）。
   - **Public**（公開）か **Private**（非公開）を選べますが、Privateをお勧めします。
2. 作成したリポジトリのページで「uploading an existing file」というリンクをクリックします。
3. この `channel_search_wp_ready` フォルダの中身（`.env` **以外**）をすべてドラッグ＆ドロップしてアップロードします。
   - **注意**: `.env` ファイルはアップロードしないでください（APIキー漏洩防止のため）。

### 3. Streamlit Cloud と連携
1. [Streamlit Community Cloud](https://streamlit.io/cloud) にアクセスし、「Sign up」または「Log in」します（GitHubアカウントでログイン）。
2. 「New app」ボタンを押します。
3. 先ほど作ったリポジトリ (`youtube-search-app`) を選択します。
4. "Main file path" に `app.py` と入力されていることを確認し、「Deploy!」を押します。

### 4. APIキーの設定（ここが重要！）
1. デプロイ中または完了後の画面右下の「Manage app」をクリック（または右上の「Settings」→「Secrets」）。
2. 「Secrets」欄に、APIキーを以下の形式で貼り付けます。
   ```toml
   YOUTUBE_API_KEY = "あなたのAPIキー"
   ```
3. 「Save」を押すと、アプリが自動的に再起動し、使えるようになります。

### 5. WordPressへの埋め込み
発行されたURL（例: `https://your-app-name.streamlit.app`）をコピーし、WordPressの記事編集画面で「埋め込み」ブロックを使うか、以下のカスタムHTMLを貼り付ければ完了です。

```html
<iframe src="https://your-app-name.streamlit.app" width="100%" height="800" frameborder="0"></iframe>
```

これで、あなたのWordPressサイト上で動くようになります！
