function lines(value) {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

async function load() {
  const state = await chrome.storage.local.get({
    bridgeUrl: "http://127.0.0.1:8765",
    token: "",
    watchTerms: [],
    watchAccounts: [],
    platformStates: {},
    officialAccounts: [],
    maxPostAgeMinutes: 30,
    autoWatchEnabled: true,
    autoWatchCriticalLastAt: "",
    autoWatchCriticalLastAccount: "",
    autoWatchNormalLastAt: "",
    autoWatchNormalLastAccount: "",
    pendingObservations: [],
    watchlistLastSyncAt: "",
    watchlistLastSyncError: ""
  });
  document.getElementById("bridgeUrl").value = state.bridgeUrl;
  document.getElementById("token").value = state.token;
  document.getElementById("maxPostAgeMinutes").value = state.maxPostAgeMinutes;
  document.getElementById("autoWatchEnabled").checked = state.autoWatchEnabled !== false;
  document.getElementById("watchTerms").value = (state.watchTerms || []).join("\n");
  document.getElementById("watchAccounts").value = (state.watchAccounts || []).join("\n");
  document.getElementById("officialAccounts").value = (state.officialAccounts || []).join("\n");
  document.getElementById("queueStatus").textContent = `待发送：${(state.pendingObservations || []).length} 条`;
  document.getElementById("autoWatchStatus").textContent = state.autoWatchEnabled === false
    ? "账号轮换：已关闭"
    : `账号轮换：critical ${state.autoWatchCriticalLastAccount || "等待"} · normal ${state.autoWatchNormalLastAccount || "等待"}`;
  const syncStatus = document.getElementById("watchlistSyncStatus");
  syncStatus.textContent = state.watchlistLastSyncAt
    ? `网页关注清单：最后同步 ${new Date(state.watchlistLastSyncAt).toLocaleString()}${state.watchlistLastSyncError ? `；最近错误 ${state.watchlistLastSyncError}` : ""}`
    : `网页关注清单：尚未同步${state.watchlistLastSyncError ? `；${state.watchlistLastSyncError}` : ""}`;
  const entries = Object.entries(state.platformStates || {});
  document.getElementById("platformStatus").textContent = entries.length
    ? `平台开关：${entries.map(([name, enabled]) => `${name} ${enabled ? "开" : "关"}`).join(" · ")}`
    : "平台开关：等待网页控制台同步";
}

document.getElementById("save").addEventListener("click", async () => {
  const maxPostAgeMinutes = Math.max(
    1,
    Math.min(240, Number(document.getElementById("maxPostAgeMinutes").value) || 30)
  );
  await chrome.storage.local.set({
    bridgeUrl: document.getElementById("bridgeUrl").value.trim().replace(/\/$/, ""),
    token: document.getElementById("token").value.trim(),
    maxPostAgeMinutes,
    autoWatchEnabled: document.getElementById("autoWatchEnabled").checked,
    officialAccounts: lines(document.getElementById("officialAccounts").value)
  });
  const status = document.getElementById("status");
  status.textContent = "已保存";
  setTimeout(() => { status.textContent = ""; }, 1500);
  await load();
});

load();
