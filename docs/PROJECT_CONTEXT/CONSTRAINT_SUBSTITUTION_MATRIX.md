# 受限需求的合法替代路径

最后更新：2026-08-31（Asia/Shanghai）

本文件把“曲线实现”定义为**合法、可运行、可验证的目标替代链**，不是规避平台条款、安全边界或证据规则。每个受限需求都必须保留五项：原始目的、现实约束、替代路径、证据差距、升级门。Web `Audit` 页同步展示 `constraint-substitution-matrix/v1`。

硬规则：替代实现不得泄露 secret、绕过访问控制、使用未来数据、回填历史、把 transport 当独立 origin、把 Paper 当真实利润，或开启 Mainnet Live。没有等价证据时必须写 `partial` / `not_equivalent`，不得写成已完整实现。

| 原始目的 | 现实约束 | 当前替代路径 | 明确证据差距 | 升级门 |
|---|---|---|---|---|
| Telegram 辅助的及时信息发现 | 官方条款阻止自动摄取消息正文并交给 Agent | 本机 `telegram-manual-external-origin-handoff/v1` 只接收用户主动提交的站外原始 URL；移除查询参数，执行公网地址、DNS、重定向、大小与文本类型检查，再本机抓取 | 不代表 Telegram 全量覆盖、频道权威、消息发布时间或平台热度；Telegram 只记 discovery/transport；生成项固定 `identity/context`、`affects=investigation_only` | 平台书面许可及内容权利人的明确、可撤销、限定授权 |
| X 高影响账号的早期发现 | 未配置有许可的全量 firehose | 已登录浏览器中的精确公开页面观察、Agent Web 搜索、官网/RSS/站外原帖交叉验证 | 不宣称 X 全覆盖、全平台互动或 10 秒级完整分母 | 合法授权的 API/export 或发布者机器 feed |
| 远程访问 Web 控制台 | 没有用户自有域名和永久 Tunnel | 本机固定 loopback + 带认证的临时 HTTPS Quick Tunnel | 公网 URL 重启后可能变化 | 用户自有域名和带认证的 named tunnel |
| 验证执行就绪 | 当前发布线永久锁定 Mainnet Live | Solana Devnet 签名/转账验证 + 带手续费、滑点和税的不可回填 Paper 前向执行 | 不证明 Mainnet swap 路由、成交、流动性、滑点或利润 | 当前发布之外的独立安全审查与明确授权；本项目仍保持锁定 |
| OKX/Pump 新币和聪明钱信息 | 未配置兼容条款的 OKX Premium/私有 feed | PumpPortal、DexScreener、GeckoTerminal 公开发现面及冻结 provenance | 不宣称 OKX 排名等价、聪明钱身份或独家覆盖 | 官方稳定 feed、清晰条款和可冻结来源时间 |
| unique buyers、holder breadth、smart money | 当前公开快照不能证明钱包独立性或地址身份 | buys/sells/tx/provider label 仅进入 shadow/context 数据可用性研究 | 不等于 unique wallets、真实持有人变化或因果收益 | 经验证索引器 + 预注册前向 outcome 研究 |

## Telegram 站外原始链接交接

- 入口仅存在于本机 `http://127.0.0.1:8787/#/sources`；受保护公网控制台只读，POST 返回 403。
- 请求只接受已审计 Telegram 目录实体、一个站外 URL 和主动提交确认；未知字段失败关闭。
- 不接受 `t.me`、`telegram.me`、`telegram.org`、URL 凭据、私网/loopback/metadata 地址或指向这些地址的重定向。
- 不保存 Telegram 正文、caption、消息 ID、服务器时间、Cookie、Session、验证码或账号密码；原始 URL 查询参数不抓取、不保存。
- 每次尝试在网络请求前写入 append-only 分母；结果为 `verified / duplicate / zero_yield / rejected / error`，不能更新或删除。
- 站外页只能生成 `identity` 上下文。它不会改变 attention、独立确认、CandidateEvaluator、安全门、仓位、Paper 或 Live。
