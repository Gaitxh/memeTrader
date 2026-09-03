from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest


def test_x_repost_preserves_actor_and_original_content_lineage() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the browser-extension syntax/behavior check")
    content_path = Path(__file__).parents[1] / "browser-extension" / "content.js"
    harness = r"""
const fs = require("fs");
const vm = require("vm");
const epoch = 1288834974657n;
const nowMs = Date.now();
const actorMs = nowMs - 10_000;
const originalMs = nowMs - 5 * 60 * 60 * 1000;
const actorId = ((BigInt(actorMs) - epoch) << 22n).toString();
const originalId = ((BigInt(originalMs) - epoch) << 22n).toString();
const actorUrl = `https://x.com/elonmusk/status/${actorId}`;
const originalUrl = `https://x.com/tunguz/status/${originalId}`;
global.location = new URL(actorUrl);
global.MutationObserver = class { observe() {} };
global.setTimeout = (callback) => { callback(); return 1; };
global.setInterval = () => 1;
const article = {
  innerText: "Elon Musk reposted Bojan Tunguz @tunguz Any day.",
  textContent: "Elon Musk reposted Bojan Tunguz @tunguz Any day.",
  getAttribute: () => "",
  querySelector: (selector) => {
    if (selector === "time[datetime]") {
      return {getAttribute: () => new Date(originalMs).toISOString()};
    }
    if (selector === "a[href*='/status/']") {
      return {getAttribute: () => new URL(originalUrl).pathname};
    }
    return null;
  }
};
global.document = {
  documentElement: {},
  body: {innerText: article.innerText},
  visibilityState: "visible",
  querySelectorAll: () => [article]
};
const messages = [];
global.chrome = {
  runtime: {
    sendMessage: (message, callback) => {
      if (message.type === "MEMETRADER_SETTINGS") {
        callback({
          watchTerms: [],
          watchAccounts: ["elonmusk"],
          watchAccountEntries: [{
            platform: "x", handle: "@elonmusk", entity_id: "elon_musk"
          }],
          platformStates: {x: true},
          officialAccounts: [],
          maxPostAgeMinutes: 240
        });
      } else {
        messages.push(message);
        if (callback) callback({ok: true});
      }
    }
  },
  storage: {onChanged: {addListener: () => {}}}
};
vm.runInThisContext(fs.readFileSync(process.env.CONTENT_JS_PATH, "utf8"), {
  filename: process.env.CONTENT_JS_PATH
});
const observation = messages.find((message) => message.type === "MEMETRADER_OBSERVATION");
if (!observation) throw new Error("repost observation was not emitted");
process.stdout.write(JSON.stringify({item: observation.item, actorUrl, originalUrl, actorMs, originalMs}));
"""
    completed = subprocess.run(
        [node, "-e", harness],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "CONTENT_JS_PATH": str(content_path.resolve())},
        check=True,
    )
    payload = json.loads(completed.stdout)
    item = payload["item"]

    assert item["source"] == "x:elonmusk"
    assert item["author"] == "elonmusk"
    assert item["url"] == payload["actorUrl"]
    assert item["source_action"] == "repost"
    assert item["source_entity_id"] == "elon_musk"
    assert item["content_author"] == "tunguz"
    assert item["content_url"] == payload["originalUrl"]
    assert item["priority"] == 2
    published_ms = int(datetime.fromisoformat(
        item["published_at"].replace("Z", "+00:00")
    ).timestamp() * 1000)
    assert abs(published_ms - payload["actorMs"]) < 1000
    assert published_ms - payload["originalMs"] > 4 * 60 * 60 * 1000
