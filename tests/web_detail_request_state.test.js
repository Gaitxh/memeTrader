'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const { createDetailRequestState } = require(path.join(
  __dirname,
  '..',
  'src',
  'memetrader',
  'web_static',
  'detail-request-state.js'
));

const state = createDetailRequestState();
const eventA = state.begin('event', 101);
assert.equal(state.isCurrent(eventA, 'event', 101), true);

const eventB = state.begin('event', 202);
assert.equal(eventA.signal.aborted, true, 'starting B must abort A');
assert.equal(state.isCurrent(eventA, 'event', 101), false, 'A may not commit after B starts');
assert.equal(state.isCurrent(eventB, 'event', 202), true);
assert.equal(state.isCurrent(eventB, 'event', 101), false, 'the response id must match the active id');
assert.equal(state.isCurrent(eventB, 'token', 202), false, 'the response type must match the active type');

state.cancel();
assert.equal(eventB.signal.aborted, true, 'closing the drawer must abort the active request');
assert.equal(state.isCurrent(eventB, 'event', 202), false, 'a closed drawer cannot accept a late response');

const token = state.begin('token', 'solana:abc');
assert.equal(state.isCurrent(token, 'token', 'solana:abc'), true);

console.log('detail request state: ok');
