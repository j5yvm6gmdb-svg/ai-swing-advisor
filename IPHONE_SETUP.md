# iPhoneセットアップ — AI Swing Advisor

1. GitHubで新しいPublic repositoryを作成。
2. このフォルダの中身をすべてアップロード。
3. Settings → Pages → Build and deployment → Source を `GitHub Actions` に変更。
4. Actions → `AI Swing Advisor` → `Run workflow`。
5. Pages URLをSafariで開き、ホーム画面に追加。

## 自動更新
米国市場引け後に1日1回更新します。スイングトレード用なので、5分足・15分足などの短期足は使いません。

## 通知
Discord WebhookをRepository secret `DISCORD_WEBHOOK_URL` に入れると、新しい上位候補を通知します。

## FMP
会社ガイダンス解析を追加したい場合はRepository secret `FMP_API_KEY` を追加します。

`スイング・エントリー候補` は売買命令ではなく、日足・週足・ファンダの機械的条件が揃った候補です。`押し目待ち` は総合条件が良くても日足21EMAから伸びすぎている状態です。
