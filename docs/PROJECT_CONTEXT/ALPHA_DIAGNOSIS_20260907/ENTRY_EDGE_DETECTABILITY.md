# Entry edge detectability：离线诊断

输入 6064 机会 / 93 Token；严格可核验子集 6041 机会 / 82 Token。

主标签为15分钟内门槛触发后下一合格原池帧仍净正。固定15分钟结果为独立对照；30/60分钟仅敏感性，不选择最好horizon。缺失标签不填0。所有模型只用信号时可用L0，未来路径仅形成标签。

固定10:30、12:00 UTC两次walk-forward；训练的完整标签容差窗在测试前成熟，测试Token从训练彻底删除。预处理仅fit训练。每Token等权训练/主要指标，Logistic C=1；小树depth=3/leaf=5；不寻优。训练小于20、测试小于5或训练单类时标不足；这些是可运行门槛，不是alpha充分性门槛。

经济分位使用测试Token平均分数排序，固定horizon的模拟净结果是entry诊断，不是该分类器交易收益；未观测结果不进入EV，完整分母见覆盖表。bootstrap不消除MNAR或单日期局限。

| H | 标签 | 测试起点 | 模型 | Train/Test Token | AUC | PR-AUC | Brier | Top10%净均值 | Bottom10%净均值 |
|---:|---|---|---|---|---:|---:|---:|---:|---:|
| 15 | observed_hit | 10:30 | constant | 21/30 | 0.5000 | 0.4855 | 0.2674 | -0.0686 | -1.0000 |
| 15 | observed_hit | 10:30 | market_baseline | 21/30 | 0.3966 | 0.4026 | 0.3388 | -0.5393 | -0.1072 |
| 15 | observed_hit | 10:30 | full_logit | 21/30 | 0.6579 | 0.5571 | 0.2345 | -0.9077 | -0.0713 |
| 15 | observed_hit | 10:30 | full_tree | 21/30 | 0.4183 | 0.4637 | 0.4360 | -1.0000 | -0.0853 |
| 15 | observed_hit | 10:30 | minus_activity | 21/30 | 0.5960 | 0.5060 | 0.2571 | -0.5393 | -0.0713 |
| 15 | observed_hit | 10:30 | minus_age | 21/30 | 0.7156 | 0.6189 | 0.2081 | -0.2739 | -0.0713 |
| 15 | observed_hit | 10:30 | within_chain_hour_shuffle | 21/30 | 0.3265 | 0.3728 | 0.4165 | -0.0741 | -0.0853 |
| 15 | observed_hit | 12:00 | constant | 41/36 | 0.5000 | 0.5808 | 0.2435 | -0.2914 | -0.4550 |
| 15 | observed_hit | 12:00 | market_baseline | 41/36 | 0.6714 | 0.7181 | 0.2205 | 0.0214 | -0.0766 |
| 15 | observed_hit | 12:00 | full_logit | 41/36 | 0.7483 | 0.7867 | 0.1909 | -0.0537 | -0.2364 |
| 15 | observed_hit | 12:00 | full_tree | 41/36 | 0.5957 | 0.6276 | 0.2642 | 0.0840 | -0.3464 |
| 15 | observed_hit | 12:00 | minus_activity | 41/36 | 0.7281 | 0.7739 | 0.2114 | -0.1435 | -0.2386 |
| 15 | observed_hit | 12:00 | minus_age | 41/36 | 0.7434 | 0.7808 | 0.1914 | -0.1310 | -0.2364 |
| 15 | observed_hit | 12:00 | within_chain_hour_shuffle | 41/36 | 0.4308 | 0.5025 | 0.2825 | -0.1148 | -0.0426 |
| 15 | fixed_positive | 10:30 | constant | 20/28 | 0.5000 | 0.1704 | 0.1715 | -0.0557 | -1.0000 |
| 15 | fixed_positive | 10:30 | market_baseline | 20/28 | 0.3542 | 0.1248 | 0.2292 | -0.0741 | -0.2232 |
| 15 | fixed_positive | 10:30 | full_logit | 20/28 | 0.6620 | 0.2376 | 0.1494 | -0.2739 | -0.3838 |
| 15 | fixed_positive | 10:30 | full_tree | 20/28 | 0.4915 | 0.1990 | 0.2169 | -0.3197 | -0.6380 |
| 15 | fixed_positive | 10:30 | minus_activity | 20/28 | 0.6011 | 0.2016 | 0.1580 | -0.2438 | -0.0741 |
| 15 | fixed_positive | 10:30 | minus_age | 20/28 | 0.6803 | 0.2578 | 0.1450 | -0.2739 | -0.3838 |
| 15 | fixed_positive | 10:30 | within_chain_hour_shuffle | 20/28 | 0.5459 | 0.1719 | 0.2830 | -0.0741 | -1.0000 |
| 15 | fixed_positive | 12:00 | constant | 39/32 | 0.5000 | 0.2921 | 0.2091 | -0.3776 | -0.0176 |
| 15 | fixed_positive | 12:00 | market_baseline | 39/32 | 0.5588 | 0.3788 | 0.2123 | -0.0933 | -0.4906 |
| 15 | fixed_positive | 12:00 | full_logit | 39/32 | 0.6994 | 0.4810 | 0.1915 | 0.2953 | -0.1283 |
| 15 | fixed_positive | 12:00 | full_tree | 39/32 | 0.5681 | 0.3351 | 0.2384 | 0.0290 | -0.4729 |
| 15 | fixed_positive | 12:00 | minus_activity | 39/32 | 0.5871 | 0.3804 | 0.2036 | 0.0650 | -0.1596 |
| 15 | fixed_positive | 12:00 | minus_age | 39/32 | 0.6991 | 0.4753 | 0.1928 | 0.2953 | -0.1283 |
| 15 | fixed_positive | 12:00 | within_chain_hour_shuffle | 39/32 | 0.4968 | 0.2812 | 0.2683 | -0.1657 | -0.4552 |
| 30 | observed_hit | 10:30 | constant | 16/29 | 0.5000 | 0.6337 | 0.2570 | 0.0879 | -0.5309 |
| 30 | observed_hit | 10:30 | market_baseline | 16/29 | 0.3768 | 0.5431 | 0.3123 | -0.4003 | -0.0721 |
| 30 | observed_hit | 10:30 | full_logit | 16/29 | 0.6884 | 0.6961 | 0.1866 | -0.8618 | -0.0800 |
| 30 | observed_hit | 10:30 | full_tree | 16/29 | 0.5222 | 0.6420 | 0.3993 | -0.4021 | -0.2218 |
| 30 | observed_hit | 10:30 | minus_activity | 16/29 | 0.5506 | 0.6110 | 0.2276 | -0.4003 | -0.0800 |
| 30 | observed_hit | 10:30 | minus_age | 16/29 | 0.7551 | 0.7702 | 0.1684 | 0.4388 | -0.0800 |
| 30 | observed_hit | 10:30 | within_chain_hour_shuffle | 16/29 | 0.3920 | 0.5333 | 0.3554 | -0.0800 | -1.0000 |
| 30 | observed_hit | 12:00 | constant | 36/33 | 0.5000 | 0.7257 | 0.1990 | -0.5054 | -0.7265 |
| 30 | observed_hit | 12:00 | market_baseline | 36/33 | 0.6928 | 0.8551 | 0.1817 | 0.3937 | -0.1550 |
| 30 | observed_hit | 12:00 | full_logit | 36/33 | 0.8425 | 0.9120 | 0.1278 | -0.0898 | -0.3961 |
| 30 | observed_hit | 12:00 | full_tree | 36/33 | 0.6384 | 0.7949 | 0.2604 | -0.3348 | -0.1080 |
| 30 | observed_hit | 12:00 | minus_activity | 36/33 | 0.7894 | 0.8866 | 0.1654 | 0.0341 | -0.4473 |
| 30 | observed_hit | 12:00 | minus_age | 36/33 | 0.8406 | 0.9110 | 0.1292 | -0.2563 | -0.3961 |
| 30 | observed_hit | 12:00 | within_chain_hour_shuffle | 36/33 | 0.7345 | 0.8794 | 0.1678 | -0.1106 | -0.3312 |
| 30 | fixed_positive | 10:30 | constant | 15/23 | 0.5000 | 0.2244 | 0.2857 | -0.0595 | -1.0000 |
| 30 | fixed_positive | 10:30 | market_baseline | 15/23 | 0.3664 | 0.1713 | 0.3248 | -0.0850 | -0.1622 |
| 30 | fixed_positive | 10:30 | full_logit | 15/23 | 0.7182 | 0.3726 | 0.1899 | 0.0514 | -0.0800 |
| 30 | fixed_positive | 10:30 | full_tree | 15/23 | 0.3299 | 0.1829 | 0.6402 | -0.0718 | -0.3388 |
| 30 | fixed_positive | 10:30 | minus_activity | 15/23 | 0.6167 | 0.2701 | 0.2250 | -0.4452 | -0.0800 |
| 30 | fixed_positive | 10:30 | minus_age | 15/23 | 0.8109 | 0.5821 | 0.1665 | 0.4194 | -0.0800 |
| 30 | fixed_positive | 10:30 | within_chain_hour_shuffle | 15/23 | 0.8262 | 0.5395 | 0.1756 | 0.0787 | -0.0800 |
| 30 | fixed_positive | 12:00 | constant | 31/24 | 0.5000 | 0.3107 | 0.2165 | -0.5054 | -0.7265 |
| 30 | fixed_positive | 12:00 | market_baseline | 31/24 | 0.4948 | 0.2804 | 0.2518 | 0.2241 | -0.4771 |
| 30 | fixed_positive | 12:00 | full_logit | 31/24 | 0.5181 | 0.3973 | 0.2330 | 0.2456 | -0.4410 |
| 30 | fixed_positive | 12:00 | full_tree | 31/24 | 0.5957 | 0.3885 | 0.2845 | 0.0242 | -0.7265 |
| 30 | fixed_positive | 12:00 | minus_activity | 31/24 | 0.6408 | 0.4236 | 0.2042 | 0.0184 | -0.4400 |
| 30 | fixed_positive | 12:00 | minus_age | 31/24 | 0.5896 | 0.4458 | 0.2138 | -0.0650 | -0.4410 |
| 30 | fixed_positive | 12:00 | within_chain_hour_shuffle | 31/24 | 0.6486 | 0.4322 | 0.2017 | -0.0650 | -0.3577 |
| 60 | observed_hit | 10:30 | constant | 6/29 | 0.5000 | 0.7405 | 0.2007 | 0.0574 | -1.0000 |
| 60 | observed_hit | 10:30 | market_baseline | 6/29 | 0.5239 | 0.7448 | 0.2135 | -0.3982 | 0.0004 |
| 60 | observed_hit | 10:30 | full_logit | 6/29 | 0.6625 | 0.8115 | 0.2303 | -0.3982 | -0.0214 |
| 60 | observed_hit | 10:30 | full_tree | 6/29 | 0.5879 | 0.7763 | 0.2628 | -0.5385 | 0.0278 |
| 60 | observed_hit | 10:30 | minus_activity | 6/29 | 0.5381 | 0.7527 | 0.2740 | -0.3982 | -0.0214 |
| 60 | observed_hit | 10:30 | minus_age | 6/29 | 0.6794 | 0.8209 | 0.2258 | -0.3669 | -0.0214 |
| 60 | observed_hit | 10:30 | within_chain_hour_shuffle | 6/29 | 0.6625 | 0.8115 | 0.2303 | -0.3982 | -0.0214 |
| 60 | observed_hit | 12:00 | constant | 27/30 | 0.5000 | 0.8451 | 0.1312 | -0.5053 | 0.4693 |
| 60 | observed_hit | 12:00 | market_baseline | 27/30 | 0.6615 | 0.9257 | 0.1300 | 0.7713 | 0.0186 |
| 60 | observed_hit | 12:00 | full_logit | 27/30 | 0.7800 | 0.9466 | 0.1135 | -0.7900 | 0.5009 |
| 60 | observed_hit | 12:00 | full_tree | 27/30 | 0.6262 | 0.8926 | 0.1607 | - | 0.0634 |
| 60 | observed_hit | 12:00 | minus_activity | 27/30 | 0.6151 | 0.9163 | 0.1349 | 0.3318 | 0.0186 |
| 60 | observed_hit | 12:00 | minus_age | 27/30 | 0.7574 | 0.9403 | 0.1167 | -0.7900 | 0.1217 |
| 60 | observed_hit | 12:00 | within_chain_hour_shuffle | 27/30 | 0.3837 | 0.7807 | 0.1449 | -0.6701 | -1.0000 |
| 60 | fixed_positive | 10:30 | INSUFFICIENT_FOR_FIXED_MODEL | 1/18 | - | - | - | - | - |
| 60 | fixed_positive | 12:00 | constant | 13/17 | 0.5000 | 0.3529 | 0.2422 | -0.5053 | 0.0210 |
| 60 | fixed_positive | 12:00 | market_baseline | 13/17 | 0.5276 | 0.4624 | 0.2499 | 0.0925 | 0.5518 |
| 60 | fixed_positive | 12:00 | full_logit | 13/17 | 0.5036 | 0.3452 | 0.2821 | 0.0925 | 0.5518 |
| 60 | fixed_positive | 12:00 | full_tree | 13/17 | 0.4693 | 0.3379 | 0.4535 | 0.1055 | -0.6361 |
| 60 | fixed_positive | 12:00 | minus_activity | 13/17 | 0.5097 | 0.3318 | 0.2866 | -0.9999 | 0.5518 |
| 60 | fixed_positive | 12:00 | minus_age | 13/17 | 0.5006 | 0.3466 | 0.2840 | 0.0925 | 0.5518 |
| 60 | fixed_positive | 12:00 | within_chain_hour_shuffle | 13/17 | 0.5878 | 0.4342 | 0.2573 | -0.2002 | 0.5518 |

校准、按链/小时/流动性层分组、Token bootstrap、leave-one-token-out均值范围、移除top1/top3、特征消融与标签置换全部保存 `data/research/alpha_diagnosis_20260907/detectability/results.json`。原始样本/预测留在data，不写生产DB。

仅同一天修复后窗口，不能完成跨日期稳定性验证。测试Token可在两个未来块重复，汇总不能再把跨fold条数当独立Token。任何正分位或漂亮AUC都不是已发现alpha。

## 经济目标对齐与并列分数修正（复用既有预测，无重新训练）

上表固定horizon净结果不等于主标签的首次阈值退出收益。下表另对齐为首次阈值触发后下一帧退出；未触发则固定15m退出，缺帧仍UNKNOWN。它仍是离线Paper诊断合同，不是现有策略实盘PnL。

原上表分位按稳定排序在同分中取前N，会产生任意选择。下表在边界包含全部同分Token，常数模型的高/低组因此都等于全体；这是指标解释修正，不是挑结果或调整模型。

| 标签 | 块 | 模型 | Top/Bottom Token(含同分) | 对齐净均值 Top/Bottom | 固定15m净均值 Top/Bottom |
|---|---|---|---:|---|---|
| fixed_positive | 10:30 | constant | 28/27 | -0.1763/-0.1814 | -0.3911/-0.4044 |
| fixed_positive | 10:30 | full_logit | 3/3 | -0.0424/-0.3814 | -0.2739/-0.3838 |
| fixed_positive | 10:30 | full_tree | 3/6 | -0.0906/-0.2228 | -0.3197/-0.3972 |
| fixed_positive | 10:30 | market_baseline | 3/3 | -0.0717/-0.1506 | -0.0741/-0.2232 |
| fixed_positive | 12:00 | constant | 31/30 | -0.0875/-0.0993 | -0.1280/-0.1179 |
| fixed_positive | 12:00 | full_logit | 4/4 | 0.0530/-0.1127 | 0.2953/-0.1283 |
| fixed_positive | 12:00 | full_tree | 4/4 | 0.0206/-0.1323 | 0.0290/-0.4729 |
| fixed_positive | 12:00 | market_baseline | 4/4 | -0.2398/-0.2736 | -0.0933/-0.4906 |
| observed_hit | 10:30 | constant | 30/30 | -0.1574/-0.1574 | -0.3911/-0.3911 |
| observed_hit | 10:30 | full_logit | 3/3 | -0.3520/-0.0689 | -0.9077/-0.0713 |
| observed_hit | 10:30 | full_tree | 3/4 | -0.4138/-0.0459 | -1.0000/-0.0822 |
| observed_hit | 10:30 | market_baseline | 3/3 | -0.3515/-0.0478 | -0.5393/-0.1072 |
| observed_hit | 12:00 | constant | 36/36 | -0.0824/-0.0824 | -0.1439/-0.1439 |
| observed_hit | 12:00 | full_logit | 4/4 | -0.0074/-0.2591 | -0.0537/-0.2364 |
| observed_hit | 12:00 | full_tree | 4/4 | -0.0505/-0.2673 | 0.0840/-0.3464 |
| observed_hit | 12:00 | market_baseline | 4/4 | 0.0225/-0.0189 | 0.0214/-0.0766 |

## 覆盖与生存诊断

每Token只取修复后最早严格机会，N=82；首次事件计数={'profit': 36, 'failure': 25, 'censored': 21}。profit=严格后帧净正；failure=先到净−20%或fresh原池floor；否则按首个观察缺口/15m右删失。保存Aalen–Johansen描述曲线，不拟合/部署hazard策略。

删失很可能依赖市场/提供商状态，不满足独立删失假设，因此曲线仅描述观测机制，不声称市场总体failure概率。标记间的先后也只是本地观察时钟，不是每笔链上交易时钟。

Master中实际有策略BUY的机会 404，有共享receipt记录 6058；这两者不能混称实际成交。未投影到策略账户的共享receipt仍可构造市场诊断标签，但不是已执行交易收益。

当前可标记样本来自87个有fill token的已有后续快照，持仓/活跃偏差尚未消除。完整chain/coverage表已保存。未知结果有−100%有限下界、理论上无有限收益上界，因此不能诚实地给出完整universe的双侧EV界。
