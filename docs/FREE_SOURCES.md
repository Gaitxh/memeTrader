# 免费、免 Key 和本地信息源

第一版本实际采用：

- Chrome/Edge Manifest V3 内容脚本 + `127.0.0.1` 本地桥，读取已打开的公开社交页面；
- Bluesky 公共搜索；
- RSS/Atom，包括 Google News 搜索 RSS、Reddit 社区 RSS、YouTube 频道 RSS；
- Mastodon-compatible 公共 JSON；
- PumpPortal 免费 `subscribeNewToken` / `subscribeMigration`，不使用付费交易流；
- GeckoTerminal 公共新池；
- DexScreener 公共搜索和 Token pair 报价，仅在事件/候选晋级后请求；
- Honeypot.is 公共 EVM 模拟，仅检查短名单候选。

可选但未内嵌的本地 sidecar：RSSHub、RSS-Bridge、SearXNG、changedetection.io、Huginn。它们有价值，但第一版不强制部署，避免把一个个人电脑机器人做成运维平台。

设计依据：

- https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts
- https://github.com/bluesky-social/jetstream
- https://docs.joinmastodon.org/methods/streaming/
- https://docs.telethon.dev/en/stable/modules/events.html
- https://docs.pumpportal.fun/websocket-api/data-api/real-time
- https://docs.dexscreener.com/api/reference
- https://apiguide.geckoterminal.com/getting-started
- https://docs.honeypot.is/
- https://docs.x.com/x-api/getting-started/pricing

X 官方 API 可能产生使用费用，所以默认通过用户已登录浏览器的公开页面观察；不把非官方高风险抓取脚本作为核心依赖。
