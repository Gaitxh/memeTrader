function lines(value) {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

async function load() {
  const state = await chrome.storage.local.get({
    bridgeUrl: "http://127.0.0.1:8765",
    token: "",
    watchTerms: [],
    watchAccounts: [],
    officialAccounts: [],
    maxPostAgeMinutes: 30,
    pendingObservations: []
  });
  document.getElementById("bridgeUrl").value = state.bridgeUrl;
  document.getElementById("token").value = state.token;
  document.getElementById("maxPostAgeMinutes").value = state.maxPostAgeMinutes;
  document.getElementById("watchTerms").value = (state.watchTerms || []).join("\n");
  document.getElementById("watchAccounts").value = (state.watchAccounts || []).join("\n");
  document.getElementById("officialAccounts").value = (state.officialAccounts || []).join("\n");
  document.getElementById("queueStatus").textContent = `待发送：${(state.pendingObservations || []).length} 条`;
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
    watchTerms: lines(document.getElementById("watchTerms").value),
    watchAccounts: lines(document.getElementById("watchAccounts").value),
    officialAccounts: lines(document.getElementById("officialAccounts").value)
  });
  const status = document.getElementById("status");
  status.textContent = "已保存";
  setTimeout(() => { status.textContent = ""; }, 1500);
  await load();
});

load();
