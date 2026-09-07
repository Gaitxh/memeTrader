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
assert.match(app, /f\.default_visible!==false\|\|\$\('#universe-show-retired'\)\?\.checked/);

console.log('chain web strategy revision: ok');
