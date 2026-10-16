# AI Swing Advisor — iPhone / GitHub Actions版

AI関連銘柄を、保有銘柄に限定せずAIエコシステム全体からスクリーニングし、**数日〜数週間のスイングトレード**向けに順位付けする意思決定支援ツールです。

## 時間軸
短期足は使いません。

- 日足: エントリー、押し目、ブレイク、相対強度、過熱判定
- 週足: 大きなトレンド、13週相対強度、週足MACD/RSI、13週高値
- ファンダ: 業績、翌期売上/EPS予想、EPS予想修正、ガイダンス、バリュエーション

## スコア
- Technical: 40点
  - 日足: 25点
  - 週足: 15点
- Forward / Guidance: 25点
- Fundamental Quality: 20点
- Valuation: 10点
- Market Regime: ±5点
- Risk penalty: 最大マイナス

高得点でも日足21EMAから大きく乖離していれば「押し目待ち」、週足トレンドが弱ければ「週足確認待ち」になります。

## テクニカル評価
### 日足 25点
- 21EMA / 50DMA / 200DMA
- 日足の移動平均の上昇整列
- 20日高値ブレイク
- RSI14
- MACD
- SMH比 20日 / 60日
- 出来高
- ATRと21EMAからの乖離

### 週足 15点
- 10週EMA / 30週EMA
- 週足トレンド整列
- 週足RSI14
- 週足MACD
- SMH比 13週
- 13週高値ブレイク

## 自動実行
GitHub Actionsは**米国市場引け後に1日1回**動きます。スイング用なので5分ごとの監視はしません。

## データ
### APIキーなし
- Yahoo Finance / yfinance
- 日足OHLCV
- 財務比率
- 翌期売上/EPS予想
- EPS予想修正
- アナリスト目標株価

### FMP APIキーあり（任意）
- analyst estimates
- price target consensus
- earnings call transcript
- guidance/outlook文の抽出とトーン判定

FMPのプランによって一部endpointは利用できない場合があります。その場合はYahoo側のデータのみで継続します。

## iPhoneでセットアップ
1. GitHubでPublic repositoryを作る。
2. このフォルダの中身を全部アップロード。
3. GitHub → Settings → Pages → Sourceを `GitHub Actions` にする。
4. Actions → `AI Swing Advisor` → `Run workflow`。
5. Pages URLをSafariで開く。
6. Safari → 共有 → ホーム画面に追加。

### Discord通知
Repository → Settings → Secrets and variables → Actions → New repository secret
- `DISCORD_WEBHOOK_URL`

### FMPを使う場合
- `FMP_API_KEY`

## 自分の保有銘柄
`portfolio.example.json` を `portfolio.json` にコピーして編集します。

```json
{
  "positions": [
    {"symbol": "NVDA", "avg_cost": 123.45},
    {"symbol": "MU", "avg_cost": 180.00}
  ]
}
```

## 出力の読み方
- `スイング・エントリー候補`: 日足・週足・総合スコアが揃い、過度な乖離がない
- `スイング・ブレイク候補`: 日足または週足の高値更新を伴う
- `押し目待ち`: 良い銘柄だが21EMAから伸びすぎ
- `週足確認待ち`: 日足だけでは良いが大きなトレンドが弱い
- `監視・押し目待ち`: まだ条件が十分ではない
- `見送り`: 現状は優先度が低い

## 重要
このツールは機械的な意思決定支援です。自動発注はしません。データ欠損、Yahoo側の遅延、アナリスト予想の誤差、決算トランスクリプトの自動解釈ミスは起こり得ます。発注前に会社IR/SEC等の一次情報とブローカー価格を確認してください。
