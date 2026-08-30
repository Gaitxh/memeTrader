# Public Feed Bridge

Chrome/Edge Manifest V3 extension for forwarding newly rendered **public** feed items from already-open pages to `http://127.0.0.1:8765`.

It does not read cookies, credentials, DMs or browser history; it does not auto-scroll or perform social actions. Items require a parseable recent `<time datetime>` so an old page loaded today is not silently treated as a live historical observation. The outbound queue is persisted in `chrome.storage.local` and retried after browser-worker or robot interruptions.

The local Web watchlist may include an optional stable `entity_id`. The extension forwards it only when the rendered author exactly matches the configured platform and handle. The Runtime independently checks the same local watchlist before persisting that ID, so arbitrary page content cannot choose a cross-platform deduplication identity. Display names and follower counts are never used to infer ownership.
