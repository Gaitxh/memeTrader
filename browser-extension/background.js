const DEFAULTS = {
  bridgeUrl: "http://127.0.0.1:8765",
  watchlistUrl: "http://127.0.0.1:8787/api/watchlist",
  token: "",
  watchTerms: [],
  watchAccounts: [],
  watchAccountEntries: [],
  priorityPostRequests: [],
  platformStates: {},
  officialAccounts: [],
  maxPostAgeMinutes: 30,
  autoWatchEnabled: true,
  autoWatchCriticalCursor: 0,
  autoWatchNormalCursor: 0,
  autoWatchLaneCursor: 0,
  autoWatchTabId: null,
  autoWatchCriticalTabId: null,
  autoWatchNormalTabId: null,
  priorityPostCursor: 0,
  priorityPostTabId: null,
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
  if (platformName(item?.platform) === "telegram") return Promise.resolve();
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
    const eligible = state.pendingObservations.filter((item) => platformName(item?.platform) !== "telegram");
    if (eligible.length !== state.pendingObservations.length) {
      await chrome.storage.local.set({pendingObservations: eligible});
    }
    if (eligible.length === 0) return;
    const batch = eligible.slice(0, 100);
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
  const extensionVersion = /^\d+(?:\.\d+){1,3}$/.test(String(detail.extension_version || ""))
    ? String(detail.extension_version)
    : "";
  const safeDetail = {
    platform,
    ...(extensionVersion ? {extension_version: extensionVersion} : {}),
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

function sourceEntityId(value) {
  const entityId = String(value || "").trim();
  return /^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?$/.test(entityId) ? entityId : "";
}

function publicAccountUrl(item) {
  const platform = platformName(item?.platform);
  const handle = String(item?.handle || "").trim().replace(/^@/, "");
  if (!handle || /[\s/?#]/.test(handle)) return "";
  if (platform === "x") return `https://x.com/${encodeURIComponent(handle)}`;
  if (platform === "bluesky") return `https://bsky.app/profile/${encodeURIComponent(handle)}`;
  if (platform === "truth") return `https://truthsocial.com/@${encodeURIComponent(handle)}`;
  return "";
}

async function rotateWatchAccounts() {
  const state = await settings();
  if (!state.autoWatchEnabled) return;
  const lanes = ["critical", "normal", "critical"];
  let laneIndex = Math.max(0, Number(state.autoWatchLaneCursor) || 0) % lanes.length;
  let critical = lanes[laneIndex] === "critical";
  let entries = (state.watchAccountEntries || []).filter((item) => {
    if (!item || state.platformStates?.[platformName(item.platform)] === false) return false;
    if (!publicAccountUrl(item)) return false;
    return (item.watch_cadence === "critical") === critical;
  });
  if (!entries.length) {
    critical = !critical;
    entries = (state.watchAccountEntries || []).filter((item) => {
      if (!item || state.platformStates?.[platformName(item.platform)] === false) return false;
      if (!publicAccountUrl(item)) return false;
      return (item.watch_cadence === "critical") === critical;
    });
  }
  if (!entries.length) return;
  const cursorKey = critical ? "autoWatchCriticalCursor" : "autoWatchNormalCursor";
  const index = Math.max(0, Number(state[cursorKey]) || 0) % entries.length;
  const target = entries[index];
  const url = publicAccountUrl(target);
  let tabId = Number(state.autoWatchTabId)
    || Number(state.autoWatchCriticalTabId)
    || Number(state.autoWatchNormalTabId)
    || null;
  try {
    if (!tabId) throw new Error("missing rotation tab");
    await chrome.tabs.update(tabId, {url, active: false});
  } catch (_) {
    const tab = await chrome.tabs.create({url, active: false});
    tabId = tab.id || null;
  }
  await chrome.storage.local.set({
    [cursorKey]: (index + 1) % entries.length,
    autoWatchLaneCursor: (laneIndex + 1) % lanes.length,
    autoWatchTabId: tabId,
    [`${critical ? "autoWatchCritical" : "autoWatchNormal"}LastAt`]: new Date().toISOString(),
    [`${critical ? "autoWatchCritical" : "autoWatchNormal"}LastAccount`]: `${target.platform}:${target.handle}`
  });
}

async function rotatePriorityPosts() {
  const state = await settings();
  if (!state.autoWatchEnabled) return;
  const requests = (state.priorityPostRequests || []).filter((item) => {
    if (!item || state.platformStates?.[platformName(item.platform)] === false) return false;
    const firstObservedAt = Date.parse(String(item.first_observed_at || ""));
    if (!Number.isFinite(firstObservedAt) || Date.now() - firstObservedAt > 15 * 60 * 1000) return false;
    try {
      const parsed = new URL(String(item.url || ""));
      return parsed.protocol === "https:" && ["x.com", "twitter.com", "bsky.app", "truthsocial.com"].includes(parsed.hostname.toLowerCase());
    } catch (_) {
      return false;
    }
  });
  if (!requests.length) return;
  const index = Math.max(0, Number(state.priorityPostCursor) || 0) % requests.length;
  const target = requests[index];
  let tabId = Number(state.priorityPostTabId) || null;
  try {
    if (!tabId) throw new Error("missing priority post tab");
    await chrome.tabs.update(tabId, {url: target.url, active: false});
  } catch (_) {
    const tab = await chrome.tabs.create({url: target.url, active: false});
    tabId = tab.id || null;
  }
  await chrome.storage.local.set({
    priorityPostCursor: (index + 1) % requests.length,
    priorityPostTabId: tabId,
    priorityPostLastAt: new Date().toISOString(),
    priorityPostLastUrl: target.url
  });
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
    platformStates.telegram = false;
    const watchAccountEntries = [];
    for (const item of Array.isArray(payload.watch_accounts) ? payload.watch_accounts.slice(0, 500) : []) {
      if (!item || typeof item !== "object" || item.enabled === false) continue;
      const handle = String(item.handle || "").trim().replace(/^@/, "").slice(0, 120);
      const platform = platformName(item.platform);
      const entityId = sourceEntityId(item.entity_id);
      if (platform === "telegram") continue;
      if (handle && platform) watchAccountEntries.push({
        platform,
        handle,
        entity_id: entityId,
        watch_cadence: item.watch_cadence === "critical" ? "critical" : "normal"
      });
    }
    const watchTerms = (Array.isArray(payload.topics) ? payload.topics : [])
      .map((item) => String(item || "").trim().slice(0, 160))
      .filter(Boolean)
      .slice(0, 100);
    const priorityPostRequests = (Array.isArray(payload.priority_post_requests) ? payload.priority_post_requests : [])
      .filter((item) => item && typeof item === "object")
      .slice(0, 12)
      .map((item) => ({
        url: String(item.url || "").slice(0, 2048),
        platform: platformName(item.platform),
        handle: String(item.handle || "").slice(0, 120),
        entity_id: sourceEntityId(item.entity_id),
        first_observed_at: String(item.first_observed_at || "")
      }));
    await chrome.storage.local.set({
      platformStates,
      watchAccountEntries,
      watchAccounts: [...new Set(watchAccountEntries.map((item) => item.handle))],
      watchTerms,
      priorityPostRequests,
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
  await chrome.alarms.clear("memetrader-auto-watch-critical");
  await chrome.alarms.clear("memetrader-auto-watch-normal");
  chrome.alarms.create("memetrader-auto-watch", {periodInMinutes: 0.5});
  chrome.alarms.create("memetrader-priority-posts", {periodInMinutes: 0.5});
  await syncWatchlist();
  await rotateWatchAccounts();
  await rotatePriorityPosts();
}

chrome.runtime.onInstalled.addListener(initialize);
chrome.runtime.onStartup.addListener(() => {
  initialize().then(flushQueue);
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "memetrader-flush") flushQueue();
  if (alarm.name === "memetrader-watchlist-sync") syncWatchlist();
  if (alarm.name === "memetrader-auto-watch") rotateWatchAccounts();
  if (alarm.name === "memetrader-priority-posts") rotatePriorityPosts();
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
