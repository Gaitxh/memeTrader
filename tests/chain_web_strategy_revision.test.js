'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const appPath = path.join(
  __dirname,
  '..',
  'src',
  'memetrader',
  'chain_web_static',
  'app.js'
);
const app = fs.readFileSync(appPath, 'utf8');
const startup = app.indexOf("window.addEventListener('hashchange'");
assert.notEqual(startup, -1, 'expected app startup boundary');

const context = vm.createContext({console});
vm.runInContext(`${app.slice(0, startup)}
globalThis.revisionUi = {
  label(family, strategies) {
    universe = {families: []};
    state = {strategies};
    return strategyLabel(family);
  },
  ingest(data) { return ingestStrategyHistory(data); },
  lifecycle(family) { return fidelityLabel(family); },
  explanation(family,opened) { return strategyExplanationMarkup(family,opened); },
  safety: cohortSafetyText,
  entry: value => readable(value,entryLabels),
  positionMarkText, positionPendingText, accountPendingText, sellabilityText,
  search: universeSearchHay, delivery: deliveryCycleForFamily, deliveryPanels,
};`, context);

const family = {
  display_index: 122,
  active_arm_ids: ['strategy-122'],
  strategy_revision: 1,
};
assert.match(context.revisionUi.positionMarkText({indicative_source:'dex_price_mark_sell_slippage_haircut',indicative_sell_slippage_pct:4}),/公开池价格，已扣 4%/);
const nativePending={indicative_source:'native_protocol_model',indicative_value_usd:null,valuation_unavailable_reason:'native_exit_capacity_unavailable'};
assert.match(context.revisionUi.positionMarkText(nativePending),/可卖储备不足/);
assert.doesNotMatch(context.revisionUi.positionPendingText(nativePending),/行情待更新/);
assert.match(context.revisionUi.accountPendingText({valuation_unavailable_reasons:{native_exit_capacity_unavailable:1}}),/可卖储备不足/);
assert.equal(context.revisionUi.sellabilityText('NATIVE_EXIT_UNAVAILABLE'),'原生退出受阻');
assert.equal(
  context.revisionUi.label(family, [{arm_id: 'strategy-122', strategy_revision: 2}]),
  '策略 122-V002',
  'the current live strategy revision must override cached family metadata'
);
assert.equal(context.revisionUi.ingest({version: 'epoch-1', strategies: []}), false);
assert.equal(context.revisionUi.ingest({version: 'epoch-2', strategies: []}), true);
assert.match(
  app,
  /universe&&\(epochChanged\|\|Number\(universe\.families\?\.length\|\|0\)!==strategies\.length\)\)refreshUniverse\(\)/,
  'an epoch transition must invalidate the strategy-universe cache even when its count is unchanged'
);
assert.match(app, /strategyLabel\(f,live\.strategy\)/);
assert.match(app, /strategyLabel\(item\.family,item\.live\.strategy\)/);
assert.match(context.revisionUi.lifecycle({account_lifecycle:'RETIRED_DUPLICATE',fidelity_status:'ADDITIVE_FORWARD'}), /重复账户已退役/);
assert.match(context.revisionUi.lifecycle({account_lifecycle:'PAUSED_NEW_ENTRY'}), /暂停新入场/);
assert.match(context.revisionUi.lifecycle({account_lifecycle:'RETIRED_DEPLETED'}), /资金接近耗尽/);
for(const [status,label] of Object.entries({FAILED:'负收益实验已停止',EXPERIMENT_COMPLETE_POSITIVE:'盈利实验已完成',DUPLICATE_SUPERSEDED:'重复或已被替代',DATA_BLOCKED:'数据输入受阻',INSUFFICIENT:'证据不足',ACTIVE:'前向运行'})){
  assert.match(context.revisionUi.lifecycle({assessment_status:status}),new RegExp(label));
}
assert.match(context.revisionUi.lifecycle({account_lifecycle:'PAUSED_NEW_ENTRY',assessment_status:'EXPERIMENT_COMPLETE_POSITIVE'}),/盈利实验已完成 · 暂停新入场/);
assert.match(app, /f\.default_visible!==false\|\|\$\('#universe-show-retired'\)\?\.checked/);
const explanation=context.revisionUi.explanation({strategy_logic:{purpose:'<img>',entry_rules:['仅使用 & 当时数据'],entry_sequence:['先观察'],exit_rules:['退出'],data_requirements:['原始池'],risk_controls:['止损'],lineage:{source_arm_ids:['<source>'],revision:'r1',paired_entry_group:'g',paired_entry_size:'20'},lifecycle_explanation:{assessment:'证据不足',operation:'暂停新入场',note:'样本不是 alpha',evidence:['e'],pause_basis:['p'],lesson:['l'],benchmark:['b']}}});
assert.match(explanation,/&lt;img&gt;/);
assert.match(explanation,/&amp; 当时数据/);
assert.match(explanation,/暂停新入场表示该账户不再开新仓/);
assert.doesNotMatch(explanation,/<img>/);
assert.match(app,/\['FAILED','负收益停止'\]/);
assert.match(app,/activeResults\.positive/);
assert.match(app,/heldValue\('held_fetch'\)/);
assert.match(app,/heldValue\('held_apply_exit'\)/);
assert.match(app,/\['安全判定',safety/);
assert.match(app,/\['后帧准入 → 安全授权 → BUY'/);
assert.match(explanation,/实际交付状态/);
assert.match(explanation,/UNKNOWN/);
assert.match(app,/runtime-loaded-manifest/);
assert.equal(context.revisionUi.entry('dex_compression_breakout_v1'),'压缩后突破');
assert.equal(context.revisionUi.safety({counts:{WAIT_SECURITY:2,BUY_AUTHORIZED_UNKNOWN:1,BUY:1}}),'WAIT_SECURITY 2 / BUY_AUTHORIZED_UNKNOWN 1');
const deliveryFamily={display_index:312,canonical_id:'trajectory144_sparse_peer_hot_fast_v1',active_arm_ids:['trajectory144_sparse_peer_hot_fast_v1'],name:'稀疏同龄HOT·自身轨迹',entry_family:'trajectory144_sparse_peer_hot_fast_v1'};
assert.match(context.revisionUi.search(deliveryFamily),/#312/);
assert.match(context.revisionUi.search({...deliveryFamily,display_index:281,registration_index:312}),/#312/);
assert.match(context.revisionUi.search(deliveryFamily),/稀疏同龄hot/);
assert.equal(context.revisionUi.delivery(deliveryFamily),'144');
assert.equal(context.revisionUi.delivery({display_index:144,registration_index:144,canonical_id:'old_strategy'}),'',
  'numeric display and registration indexes are not delivery provenance');
assert.equal(context.revisionUi.delivery({canonical_id:'ordinary_strategy',trajectory_engine:'v144'}),'144');
assert.equal(context.revisionUi.delivery({canonical_id:'recipe145_abc_v1'}),'145');
assert.equal(context.revisionUi.delivery({canonical_id:'trajectory145_sparse_trend_runner_v1'}),'145');
assert.equal(context.revisionUi.delivery({canonical_id:'trajectory145_sparse_trend_runner_v1',trajectory_engine:'v144'}),'145');
assert.equal(context.revisionUi.delivery({canonical_id:'recipe145_x',trajectory_engine:'v144'}),'145');
assert.equal(context.revisionUi.delivery({canonical_id:'trajectory146_learned_mode_selector_v1',trajectory_engine:'v144'}),'146');
const panels=context.revisionUi.deliveryPanels({'mode-learning144:status':{version:'mode-learning144/v3',releases:0,updated_at:'2026-09-11T00:00:00Z'}});
assert.match(panels[2][1],/固定基线，尚无学习模型发布/);
assert.match(panels[3][1],/mode-learning145 UNKNOWN/);
const observedPanels=context.revisionUi.deliveryPanels({
  'trajectory144:status':{pools:2,counts:{'signal:trajectory144_alpha':2,'signal:trajectory144_beta':3}},
  'mode-learning144:status':{horizons:{'5':{observed:3,unknown:1,model_floor_event:2}}},
  'mode-learning145:status':{decision_eligible:false,horizons:{'30':{OBSERVED:4,UNKNOWN:2,MODEL_FLOOR_EVENT:1}},economic_comparison:{status:'NO_MATCHED_BASELINE'}},
});
assert.match(observedPanels[1][1],/实际信号 5（signal:<arm> 合计）/);
assert.match(observedPanels.find(row=>row[0]==='5 分钟标签')[1],/OBSERVED 3 · UNKNOWN 1 · 模型floor 2/);
assert.match(observedPanels.find(row=>row[0]==='145 研究 30 分钟标签')[1],/OBSERVED 4 · UNKNOWN 2 · 模型floor 1/);
assert.equal(observedPanels.find(row=>row[0]==='145 固定优先级对照')[1],'NO_MATCHED_BASELINE');
const learnedPanels=context.revisionUi.deliveryPanels({
  'mode-learning145:status':{schema:'mode-learning146/v5',affects:'trajectory146_learned_mode_selector_v1',unique_episodes:5,
    counts:{strict_entry:4},model:{version:'fixed_priority/v1',releases:0},horizons:{5:{OBSERVED:1,UNKNOWN:2,MODEL_FLOOR_EVENT:1}},
    arms:{trajectory146_learned_mode_selector_v1:{signal_decisions:2,independent_buy_receipts:1,terminal_receipts:0}}},
  'recipe145:status':{candidates:[{arm_id:'trajectory145_sparse_trend_runner_v1',status:'LOADED',origin:'USER_AUTHORIZED_SEED',comparison:{economic_status:'INSUFFICIENT',missing:['20_same_fill_terminals']}}]},
});
assert.equal(learnedPanels.find(row=>row[0]==='146 独立学习episode')[1],'5');
assert.match(learnedPanels.find(row=>row[0]==='trajectory146_learned_mode_selector_v1')[1],/信号 2 · BUY 1 · 终局 0/);
assert.match(learnedPanels.find(row=>row[0]==='146 5 分钟标签')[1],/OBSERVED 1 · UNKNOWN 2 · 模型floor 1/);
assert.match(learnedPanels.find(row=>row[0]==='trajectory145_sparse_trend_runner_v1')[1],/INSUFFICIENT/);
assert.match(learnedPanels.find(row=>row[0]==='trajectory145_sparse_trend_runner_v1')[2],/20_same_fill_terminals/);
const sharedPanels=context.revisionUi.deliveryPanels({'coverage145:status':{shared_batch148:{enabled:true,active:2,max_active:6,waiting:3,counts:{EXACT_FRESH_RESPONSES:7},opportunities:[]}}});
assert.match(sharedPanels.find(row=>row[0]==='共享批量覆盖148')[1],/额外观察 2\/6 · 等待 3/);
assert.match(sharedPanels.find(row=>row[0]==='共享批量覆盖148')[2],/不增加HTTP批次/);
assert.match(panels.find(row=>row[0]==='共享批量覆盖148')[1],/尚未加载/);
assert.match(app,/strategy\.max_hold_minutes==null\?'UNKNOWN'/);
assert.match(app,/\['现有漏斗'/);

context.clearTimeout = () => {};
context.document = {visibilityState: 'hidden'};
context.fetch = () => { throw new Error('hidden page must not fetch live state'); };
context.setTimeout = () => { throw new Error('hidden page must not keep polling'); };
vm.runInContext('refreshLive()', context).then(() => {
  console.log('chain web strategy revision and hidden polling: ok');
  context.document = {visibilityState:'visible'};
  context.setTimeout = () => 0;
  context.fetch = async () => ({ok:true,json:async()=>({})});
  return vm.runInContext(`(async()=>{
    let clock=60000,calls=0;Date.now=()=>clock;
    lastPage='strategies';performanceRequestedAt=0;
    selectedStrategyArm=()=>'';renderLive=()=>{};
    refreshPerformance=async()=>{calls++;performanceRequestedAt=Date.now();};
    await refreshLive();await refreshLive();
    if(calls!==1)throw Error('summary must refresh once, not every live poll');
    clock+=30000;await refreshLive();
    if(calls!==2)throw Error('visible summary must advance after30s');
    document.visibilityState='hidden';clock+=30000;await refreshLive();
    if(calls!==2)throw Error('hidden summary must not poll');
  })()`,context);
});

assert.match(context.revisionUi.explanation({},true),/class="strategy-explanation" open/);
assert.match(app,/held仅指OPEN仓/);
assert.match(app,/priority\.actual_open/);
assert.match(app,/priority\.obsolete_filtered/);

assert.match(context.revisionUi.positionMarkText({indicative_source:'dex_price_mark_configured_execution',indicative_sell_slippage_pct:4}),/公开池价格，已扣 4%/);
