# Wallet / Solana Devnet 验证记录（2026-08-30）

## 验证边界

- 常驻策略继续运行在 Paper；`live.enabled=false`，Mainnet 没有启用接口。
- 真链测试只使用固定的 `https://api.devnet.solana.com`，并校验 Solana Devnet genesis hash。
- 使用运行时生成的一次性钱包；没有使用聊天中出现过的私钥，也没有记录、上传或输出测试私钥。

## 实际结果

1. 通过本机 `127.0.0.1` Wallet API 连接一次性钱包：成功。
2. Devnet 集群身份、地址、余额和近期交易读取：成功。
3. 向官方 Devnet RPC 请求 `0.01 SOL` airdrop：失败，返回 `Solana Devnet RPC is unavailable`。
4. 因没有获得测试 SOL，没有执行发送步骤，也没有产生可核验的公开 Devnet signature。
5. 测试结束后调用断开接口；`wallet.dpapi` 与 `wallet.json` 均未残留，Mainnet 未被调用。

这是外部 faucet / RPC 的实测阻塞，不代表交易已经成功。后端的签名序列化、余额与手续费门、`simulateTransaction`、`sendTransaction`、确认轮询和 `getTransaction` 回执核对由自动化测试覆盖；只有未来官方 faucet 成功返回测试 SOL 并得到公开确认回执后，才可以把端到端 Devnet 交易标记为通过。

## 自动化覆盖

- 私钥仅 DPAPI 密文落盘，公开视图脱敏；
- 非 loopback 钱包变更返回 `403`；
- Devnet genesis hash 不匹配时失败关闭；
- 转账上限 `0.05 SOL`，确认语必须为 `DEVNET ONLY`；
- 余额不足、无有效手续费、模拟失败、签名不一致或回执不匹配均不能被标记为成功；
- 钱包连接不能修改 Paper 模式或 Mainnet 锁。
