const DEFAULTS = {
  bridgeUrl: "http://127.0.0.1:8765",
  watchlistUrl: "http://127.0.0.1:8787/api/watchlist",
  token: "",
  watchTerms: [],
  watchAccounts: [],
  watchAccountEntries: [],
  platformStates: {},
  officialAccounts: [],
  maxPostAgeMinutes: 30,
  pendingObservations: [],
  watchlistLastSyncAt: "",
  watchlistLastSyncError: ""
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
  const platform = String(detail.platform || source || "browser").slice(0, 64);
  const accessStates = new Set(["content_visible", "login_prompt", "no_recent_items"]);
  const safeDetail = {
    platform,
    visible: typeof detail.visible === "boolean" ? detail.visible : null,
    selector_count: Math.max(0, Number(detail.selector_count) || 0),
    page_url: String(detail.page_url || "").slice(0, 2048),
    access_state: accessStates.has(detail.access_state) ? detail.access_state : "no_recent_items"
  };
  try {
    await fetch(`${state.bridgeUrl.replace(/\/$/, "")}/v1/heartbeat`, {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-MemeTrader-Token": state.token},
      body: JSON.stringify({source: platform, url: safeDetail.page_url, time: new Date().toISOString(), ...safeDetail}),
      cache: "no-store",
      credentials: "omit"
    });
  } catch (_) {}
}

function platformName(value) {
  return String(value || "").trim().toLowerCase();
}

async function syncWatchlist() {
  const state = await settings();
  try {
    const response = await fetch(state.watchlistUrl, {
      method: "GET",
      cache: "no-store",
      credentials: "omit",
      headers: {"Accept": "application/json"}
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    const platformStates = {};
    for (const item of Array.isArray(payload.platforms) ? payload.platforms.slice(0, 32) : []) {
      if (!item || typeof item !== "object") continue;
      const name = platformName(item.platform);
      if (name) platformStates[name] = item.enabled !== false;
    }
    const watchAccountEntries = [];
    for (const item of Array.isArray(payload.watch_accounts) ? payload.watch_accounts.slice(0, 500) : []) {
      if (!item || typeof item !== "object" || item.enabled === false) continue;
      const handle = String(item.handle || "").trim().replace(/^@/, "").slice(0, 120);
      const platform = platformName(item.platform);
      if (handle && platform) watchAccountEntries.push({platform, handle});
    }
    const watchTerms = (Array.isArray(payload.topics) ? payload.topics : [])
      .map((item) => String(item || "").trim().slice(0, 160))
      .filter(Boolean)
      .slice(0, 100);
    await chrome.storage.local.set({
      platformStates,
      watchAccountEntries,
      watchAccounts: [...new Set(watchAccountEntries.map((item) => item.handle))],
      watchTerms,
      watchlistLastSyncAt: new Date().toISOString(),
      watchlistLastSyncError: ""
    });
  } catch (error) {
    await chrome.storage.local.set({
      watchlistLastSyncError: String(error),
      watchlistLastSyncErrorAt: new Date().toISOString()
    });
  }
}

async function initialize() {
  const current = await chrome.storage.local.get({...DEFAULTS, queue: []});
  const pendingObservations = Array.isArray(current.pendingObservations) && current.pendingObservations.length
    ? current.pendingObservations
    : (Array.isArray(current.queue) ? current.queue : []);
  await chrome.storage.local.set({...DEFAULTS, ...current, pendingObservations});
  await chrome.storage.local.remove("queue");
  chrome.alarms.create("memetrader-flush", {periodInMinutes: 0.5});
  chrome.alarms.create("memetrader-watchlist-sync", {periodInMinutes: 2});
  await syncWatchlist();
}

chrome.runtime.onInstalled.addListener(initialize);
chrome.runtime.onStartup.addListener(() => {
  initialize().then(flushQueue);
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "memetrader-flush") flushQueue();
  if (alarm.name === "memetrader-watchlist-sync") syncWatchlist();
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
