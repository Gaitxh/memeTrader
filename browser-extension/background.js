const DEFAULTS = {
  bridgeUrl: "http://127.0.0.1:8765",
  token: "",
  watchTerms: [],
  watchAccounts: [],
  officialAccounts: [],
  maxPostAgeMinutes: 30,
  pendingObservations: []
};

let flushInProgress = false;
let queueMutation = Promise.resolve();

function withQueueLock(action) {
  const pending = queueMutation.then(action, action);
  queueMutation = pending.catch(() => undefined);
  return pending;
}

async function settings() {
  const state = await chrome.storage.local.get({...DEFAULTS, queue: []});
  if ((!state.pendingObservations || state.pendingObservations.length === 0) && Array.isArray(state.queue) && state.queue.length) {
    state.pendingObservations = state.queue;
    await chrome.storage.local.set({pendingObservations: state.pendingObservations});
    await chrome.storage.local.remove("queue");
  }
  return state;
}

function queueId(item) {
  if (item?._queue_id) return String(item._queue_id);
  const seed = `${item?.platform || ""}\n${item?.url || ""}\n${item?.author || ""}\n${item?.text || item?.title || ""}`;
  let value = 2166136261;
  for (let i = 0; i < seed.length; i += 1) {
    value ^= seed.charCodeAt(i);
    value = Math.imul(value, 16777619);
  }
  return `${Date.now()}-${(value >>> 0).toString(16)}`;
}

function appendQueue(item) {
  return withQueueLock(async () => {
    const state = await settings();
    const pendingObservations = Array.isArray(state.pendingObservations) ? state.pendingObservations : [];
    const stored = {...item, _queue_id: queueId(item)};
    if (!pendingObservations.some((row) => row._queue_id === stored._queue_id)) {
      pendingObservations.push(stored);
    }
    while (pendingObservations.length > 5000) pendingObservations.shift();
    await chrome.storage.local.set({pendingObservations});
  });
}

async function flushQueue() {
  if (flushInProgress) return;
  flushInProgress = true;
  try {
    const state = await withQueueLock(settings);
    if (!state.token || !Array.isArray(state.pendingObservations) || state.pendingObservations.length === 0) return;
    const batch = state.pendingObservations.slice(0, 100);
    const sentIds = new Set(batch.map((item) => item._queue_id));
    const response = await fetch(`${state.bridgeUrl.replace(/\/$/, "")}/v1/observe`, {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-MemeTrader-Token": state.token},
      body: JSON.stringify(batch),
      cache: "no-store",
      credentials: "omit"
    });
    if (!response.ok) {
      await chrome.storage.local.set({lastError: `HTTP ${response.status}`, lastErrorAt: new Date().toISOString()});
      return;
    }
    await withQueueLock(async () => {
      const latest = await settings();
      const remaining = (latest.pendingObservations || []).filter((item) => !sentIds.has(item._queue_id));
      await chrome.storage.local.set({
        pendingObservations: remaining,
        lastSuccessAt: new Date().toISOString(),
        lastError: ""
      });
    });
  } catch (error) {
    await chrome.storage.local.set({lastError: String(error), lastErrorAt: new Date().toISOString()});
  } finally {
    flushInProgress = false;
  }
}

async function heartbeat(source, detail = {}) {
  const state = await settings();
  if (!state.token) return;
  try {
    await fetch(`${state.bridgeUrl.replace(/\/$/, "")}/v1/heartbeat`, {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-MemeTrader-Token": state.token},
      body: JSON.stringify({source, url: source, time: new Date().toISOString(), ...detail}),
      cache: "no-store",
      credentials: "omit"
    });
  } catch (_) {}
}

async function initialize() {
  const current = await chrome.storage.local.get({...DEFAULTS, queue: []});
  const pendingObservations = Array.isArray(current.pendingObservations) && current.pendingObservations.length
    ? current.pendingObservations
    : (Array.isArray(current.queue) ? current.queue : []);
  await chrome.storage.local.set({...DEFAULTS, ...current, pendingObservations});
  await chrome.storage.local.remove("queue");
  chrome.alarms.create("memetrader-flush", {periodInMinutes: 0.5});
}

chrome.runtime.onInstalled.addListener(initialize);
chrome.runtime.onStartup.addListener(() => {
  initialize().then(flushQueue);
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "memetrader-flush") flushQueue();
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "MEMETRADER_OBSERVATION") {
    appendQueue(message.item).then(flushQueue).then(() => sendResponse({ok: true}));
    return true;
  }
  if (message?.type === "MEMETRADER_HEARTBEAT") {
    heartbeat(message.source || sender.tab?.url || "browser", message.detail || {}).then(() => sendResponse({ok: true}));
    return true;
  }
  if (message?.type === "MEMETRADER_SETTINGS") {
    settings().then((value) => sendResponse(value));
    return true;
  }
  return false;
});
