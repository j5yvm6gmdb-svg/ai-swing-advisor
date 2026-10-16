# iPhoneだけで始める手順

## 必要なもの
- Safari（iPhone標準アプリ）
- 「ファイル」（iPhone標準アプリ）
- GitHubの無料アカウント（https://github.com/signup）。GitHubアプリは不要。Safariの「デスクトップ用Webサイトを表示」が便利。
- Discordは通知を希望する場合だけ。FMP APIキーも任意。

## 最初の設定
1. このZIPをiPhoneの「ファイル」に保存してタップして展開する。
2. Safariで github.com/new を開き、`ai-swing-advisor` という **Public** repositoryを作る（個人情報を入れない）。
3. リポジトリの **Add file → Upload files** を開き、ZIPを除く展開フォルダの中身をアップロード。`.github/workflows` の隠しフォルダも必須。iPhoneのブラウザからフォルダ全体を選べない場合、PCを一時的に使うかGitHub WebのCreate new fileで `.github/workflows/radar.yml` と `backtest.yml` を作成する。**ZIPをそのままアップロードしても実行できない。**
4. **Settings → Pages → Source → GitHub Actions** を選択。
5. **Actions → AI Swing Advisor → Run workflow** で日次ダッシュボードを初回実行。
6. **Actions → Swing Backtest → Run workflow** でバックテストを実行。
7. 完了した実行の **Artifacts → backtest-results** をタップして結果ZIPを取得。`backtest_summary.json` に集計、`backtest_trades.csv` に各シグナルの結果が入る。
8. ダッシュボードは **Settings → Pages → Visit site** で表示し、Safari共有→ホーム画面に追加。

## 注意
バックテストは **v3のファンダ・ガイダンス込み80点** の再現ではない。過去時点の業績予想・ガイダンス履歴がないため、**日足・週足だけで作った代替スコア80点**の探索的検証。未来データはシグナルに使わず、シグナル翌日の寄り付きで買った想定。手数料、スリッページ、税金、銘柄の生存者バイアスは未調整。出力は運用成績の保証ではない。現在のスコア重みを最適化するには、学習期間と未使用の検証期間を分ける必要がある。
