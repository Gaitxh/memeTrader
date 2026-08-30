(() => {
  "use strict";

  const host = location.hostname.toLowerCase();
  const PRIVATE_PATH = [
    /(?:x|twitter)\.com\/(messages|i\/bookmarks)/i,
    /instagram\.com\/direct/i,
    /reddit\.com\/(message|chat)/i,
    /threads\.net\/(activity|inbox)/i,
    /tiktok\.com\/(messages|inbox)/i,
    /youtube\.com\/feed\/history/i,
    /truthsocial\.com\/messages/i
  ];
  if (PRIVATE_PATH.some((pattern) => pattern.test(location.href))) return;

  const seen = new Set();
  let scheduled = false;
  let firstScan = true;
  let lastSelectorCount = 0;
  let lastRecentCount = 0;
  let settings = {
    watchTerms: [],
    watchAccounts: [],
    watchAccountEntries: [],
    platformStates: {},
    officialAccounts: [],
    maxPostAgeMinutes: 30
  };

  function normalize(value) {
    return (value || "").replace(/\s+/g, " ").trim();
  }

  function hash(value) {
    let result = 2166136261;
    for (let i = 0; i < value.length; i += 1) {
      result ^= value.charCodeAt(i);
      result = Math.imul(result, 16777619);
    }
    return (result >>> 0).toString(16);
  }

  function platform() {
    if (host === "x.com" || host === "twitter.com") return "x";
    if (host === "truthsocial.com") return "truth";
    if (host === "bsky.app") return "bluesky";
    if (host.includes("reddit.com")) return "reddit";
    if (host === "www.threads.net" || host === "threads.net") return "threads";
    if (host === "www.instagram.com" || host === "instagram.com") return "instagram";
    if (host === "www.tiktok.com" || host === "tiktok.com") return "tiktok";
    if (host === "www.youtube.com" || host === "youtube.com") return "youtube";
    if (host === "t.me") return "telegram";
    return host;
  }

  function platformEnabled() {
    const states = settings.platformStates || {};
    return !Object.prototype.hasOwnProperty.call(states, platform()) || states[platform()] !== false;
  }

  function safePageUrl() {
    return `${location.origin}${location.pathname}`.slice(0, 2048);
  }

  function candidateNodes() {
    if (host === "x.com" || host === "twitter.com") return document.querySelectorAll("article");
    if (host === "truthsocial.com") return document.querySelectorAll("article,.status");
    if (host === "bsky.app") return document.querySelectorAll("main article,main [data-testid*='feedItem']");
    if (host.includes("reddit.com")) return document.querySelectorAll("shreddit-post,article");
    if (host === "www.threads.net" || host === "threads.net" || host === "www.instagram.com" || host === "instagram.com") {
      return document.querySelectorAll("article");
    }
    if (host === "www.tiktok.com" || host === "tiktok.com") {
      return document.querySelectorAll("[data-e2e='recommend-list-item-container'],[data-e2e='search-card-video-caption']");
    }
    if (host === "www.youtube.com" || host === "youtube.com") {
      return document.querySelectorAll("ytd-rich-item-renderer,ytd-video-renderer,ytd-comment-thread-renderer");
    }
    if (host === "t.me") return document.querySelectorAll(".tgme_widget_message");
    return [];
  }

  function absoluteUrl(value) {
    try {
      return new URL(value, location.href).href;
    } catch (_) {
      return location.href;
    }
  }

  function findPermalink(node) {
    const selectors = host === "t.me"
      ? [".tgme_widget_message_date"]
      : [
          "a[href*='/status/']",
          "a[href*='/post/']",
          "a[href*='/comments/']",
          "a[href*='/video/']",
          "a[href*='/watch']",
          "a[href*='/shorts/']",
          "a[href]"
        ];
    for (const selector of selectors) {
      const link = node.querySelector(selector);
      if (link?.getAttribute("href")) return absoluteUrl(link.getAttribute("href"));
    }
    return location.href;
  }

  function findAuthor(node, permalink) {
    const explicit = node.getAttribute("author") || node.getAttribute("data-author") || "";
    if (explicit) return normalize(explicit);
    const profile = node.querySelector(
      "a[href^='/@'],a[href*='/profile/'],a[href*='/user/'],a[href*='/channel/'],.tgme_widget_message_author_name"
    );
    const label = normalize(profile?.textContent || profile?.getAttribute("href") || "");
    if (label) return label.replace(/^@/, "");
    const match = permalink.match(
      /(?:x\.com|twitter\.com|bsky\.app\/profile|threads\.net\/@|instagram\.com\/)([^/]+)/i
    );
    return match ? match[1].replace(/^@/, "") : "";
  }

  function findPublishedAt(node) {
    const time = node.querySelector("time[datetime]");
    const value = time?.getAttribute("datetime") || node.getAttribute("data-timestamp") || "";
    if (!value) return null;
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return null;
    const futureToleranceMs = 5 * 60 * 1000;
    if (parsed.getTime() > Date.now() + futureToleranceMs) return null;
    return parsed.toISOString();
  }

  function accountKey(value) {
    return String(value || "").trim().toLowerCase().replace(/^@/, "");
  }

  function priority(text, author) {
    const lower = text.toLowerCase();
    const authorLower = accountKey(author);
    let value = 0;
    if ((settings.watchTerms || []).some((term) => lower.includes(String(term).toLowerCase()))) value += 1;
    const platformAccounts = (settings.watchAccountEntries || []).filter(
      (item) => item && item.platform === platform()
    );
    const watchedAccount = (settings.watchAccountEntries || []).length
      ? platformAccounts.some((item) => authorLower === accountKey(item.handle))
      : (settings.watchAccounts || []).some((name) => authorLower === accountKey(name));
    if (watchedAccount) value += 2;
    if ((settings.officialAccounts || []).some((name) => authorLower === accountKey(name))) value += 3;
    return value;
  }

  function isRecent(publishedAt, observedAt) {
    if (!publishedAt) return false;
    const ageMs = new Date(observedAt).getTime() - new Date(publishedAt).getTime();
    const maxAgeMinutes = Math.max(1, Number(settings.maxPostAgeMinutes) || 30);
    return ageMs >= -5 * 60 * 1000 && ageMs <= maxAgeMinutes * 60 * 1000;
  }

  function scan() {
    scheduled = false;
    if (!platformEnabled()) {
      lastSelectorCount = 0;
      lastRecentCount = 0;
      return;
    }
    const capturePhase = firstScan ? "initial" : "live";
    const observedAt = new Date().toISOString();
    const nodes = candidateNodes();
    lastSelectorCount = nodes.length;
    lastRecentCount = 0;

    for (const node of nodes) {
      const text = normalize(node.innerText || node.textContent || "");
      if (text.length < 8 || text.length > 20000) continue;
      const publishedAt = findPublishedAt(node);
      if (!isRecent(publishedAt, observedAt)) continue;
      lastRecentCount += 1;
      const url = findPermalink(node);
      const author = findAuthor(node, url);
      const fingerprint = hash(`${platform()}\n${url}\n${author}\n${text}`);
      if (seen.has(fingerprint)) continue;
      seen.add(fingerprint);
      if (seen.size > 10000) seen.delete(seen.values().next().value);

      const isOfficial = (settings.officialAccounts || []).some(
        (name) => accountKey(author) === accountKey(name)
      );
      chrome.runtime.sendMessage({
        type: "MEMETRADER_OBSERVATION",
        item: {
          source: `${platform()}:${author || host}`,
          source_kind: isOfficial ? "official_social" : "social",
          source_item_id: url === location.href ? `${platform()}:${fingerprint}` : url,
          title: text.slice(0, 500),
          text,
          url,
          author,
          published_at: publishedAt,
          observed_at: observedAt,
          capture_phase: capturePhase,
          priority: priority(text, author),
          page_url: safePageUrl(),
          platform: platform()
        }
      });
    }

    firstScan = false;
  }

  function scheduleScan() {
    if (scheduled) return;
    scheduled = true;
    setTimeout(scan, 750);
  }

  chrome.runtime.sendMessage({type: "MEMETRADER_SETTINGS"}, (value) => {
    if (value) settings = {...settings, ...value};
    scan();
  });

  chrome.storage.onChanged.addListener((changes) => {
    for (const key of ["watchTerms", "watchAccounts", "watchAccountEntries", "platformStates", "officialAccounts", "maxPostAgeMinutes"]) {
      if (changes[key]) settings[key] = changes[key].newValue ?? settings[key];
    }
  });

  new MutationObserver(scheduleScan).observe(document.documentElement, {subtree: true, childList: true});
  setInterval(() => {
    const pageText = normalize(document.body?.innerText || "").slice(0, 5000).toLowerCase();
    const loginPrompt = /\b(log in|sign in)\b|登入|登录|登錄/.test(pageText);
    const accessState = lastRecentCount > 0
      ? "content_visible"
      : (lastSelectorCount > 0 ? "no_recent_items" : (loginPrompt ? "login_prompt" : "no_recent_items"));
    chrome.runtime.sendMessage({
      type: "MEMETRADER_HEARTBEAT",
      source: platform(),
      detail: {
        platform: platform(),
        visible: document.visibilityState === "visible",
        selector_count: platformEnabled() ? candidateNodes().length : 0,
        page_url: safePageUrl(),
        access_state: accessState
      }
    });
  }, 30000);
  setInterval(scan, 60000);
})();
