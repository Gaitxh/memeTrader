'use strict';

// The entry-evaluation log is the surface an operator reads to answer "why is the system not
// trading?". Four reasons dominate it (measured 2026-09-13 over 61,862 evaluations:
// cohort_observation 34.4%, pattern_observation 26.9%, entry_pool_liquidity_absent_curve_stage
// 7.1%, invalid_exact_asof_market_snapshot 4.7%) and every one of them previously fell through
// reasonText()'s generic branches and rendered as a RAW ENGLISH IDENTIFIER.
//
// Worse, `entry_snapshot_too_old` contains the substring 'entry' and so matched the
// `value.includes('entry')` branch, rendering as "策略入场条件成立" - "entry conditions met" - for a
// frame that was REJECTED for being too old. A label that says the opposite of the truth is a
// defect on a truthful-operating surface, not a cosmetic issue.
//
// Two of the four are not rejections at all: they are the observer's own bookkeeping, and one is a
// data-availability limit rather than a fault. The labels must not imply a fault where there is
// none, and must not say "stale" for the identity check (that exact confusion cost a round).

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
globalThis.ui = { reasonText };`, context);

const reasonText = context.ui.reasonText;

// 1. The actively-wrong label. This is the assertion that would have caught the bug.
assert.equal(
  reasonText('entry_snapshot_too_old'),
  '行情快照过旧，超过入场新鲜度上限',
  'a too-old snapshot must not render as "entry conditions met"'
);
assert.doesNotMatch(reasonText('entry_snapshot_too_old'), /入场条件成立/);

// 2. The dominant reasons must no longer leak raw identifiers.
const dominant = [
  'cohort_observation',
  'pattern_observation',
  'entry_pool_liquidity_absent_curve_stage',
  'invalid_exact_asof_market_snapshot',
];
for (const reason of dominant) {
  const label = reasonText(reason);
  assert.notEqual(label, reason, `${reason} must not render as its raw identifier`);
  assert.match(label, /[\u4e00-\u9fff]/, `${reason} must render a Chinese label`);
}

// 3. The observer-bookkeeping reasons must say they are NOT a rejection, so an operator does not
//    read 61% of the log as strategy refusals.
assert.match(reasonText('cohort_observation'), /非策略拒绝/);
assert.match(reasonText('pattern_observation'), /非策略拒绝/);

// 4. The identity check must not be described as staleness - that confusion cost a round.
assert.doesNotMatch(reasonText('invalid_exact_asof_market_snapshot'), /过旧|陈旧|过期/);
assert.match(reasonText('invalid_exact_asof_market_snapshot'), /有效性/);

// 5. The curve-stage reason is a data limit, not a pool fault: it must not claim an anomaly.
assert.doesNotMatch(reasonText('entry_pool_liquidity_absent_curve_stage'), /异常/);

// 6. The deployed experiment arms' own entry floors must be legible on the console.
assert.match(reasonText('activity_floor_trades_not_met'), /成交笔数/);
assert.match(reasonText('activity_floor_volume_not_met'), /成交额/);
assert.match(reasonText('runup_floor_exceeded'), /涨幅/);
assert.match(reasonText('runup_floor_window_unknown'), /涨幅未知/);
for (const reason of ['activity_floor_trades_not_met', 'activity_floor_volume_not_met',
                      'runup_floor_exceeded', 'runup_floor_window_unknown']) {
  assert.notEqual(reasonText(reason), reason, `${reason} must not render as its raw identifier`);
}

// 7. Pre-existing behaviour that must not regress.
assert.equal(reasonText('no_active_matching_entry_policy'), '当前行情未匹配任何启用的入场策略');
assert.equal(reasonText('entry_pool_liquidity_unknown'), '等待原池流动性数据');
assert.equal(reasonText('strategy_open_slot_limit'), '已达到策略同时持仓上限');
assert.equal(reasonText('entry_pool_liquidity_below_1000_usd'), '原池流动性低于 1000 美元，禁止买入');
assert.equal(reasonText(''), '—');
assert.equal(reasonText('market_mark_take_profit_1:dex_mark_paper_fill'), '达到分批止盈条件');
assert.equal(reasonText('market_mark_hard_stop:dex_mark_paper_fill'), '触发止损');
assert.equal(reasonText('market_mark_trailing_exit:dex_mark_paper_fill'), '从高点回撤，保护利润');
assert.equal(reasonText('market_mark_max_hold:dex_mark_paper_fill'), '达到持有时间');

console.log('chain_web_reason_text: ok');
