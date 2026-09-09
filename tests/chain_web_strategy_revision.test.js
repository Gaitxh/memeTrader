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
};`, context);

const family = {
  display_index: 122,
  active_arm_ids: ['strategy-122'],
  strategy_revision: 1,
};
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
assert.match(app,/\['信号 → 安全 → BUY','UNKNOWN'/);
assert.match(app,/strategy\.max_hold_minutes==null\?'UNKNOWN'/);
assert.match(app,/\['现有漏斗'/);

context.clearTimeout = () => {};
context.document = {visibilityState: 'hidden'};
context.fetch = () => { throw new Error('hidden page must not fetch live state'); };
context.setTimeout = () => { throw new Error('hidden page must not keep polling'); };
vm.runInContext('refreshLive()', context).then(() => {
  console.log('chain web strategy revision and hidden polling: ok');
});

assert.match(context.revisionUi.explanation({},true),/class="strategy-explanation" open/);
