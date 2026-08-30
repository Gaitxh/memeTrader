(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.MemeTraderDetailRequests = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function createDetailRequestState() {
    let generation = 0;
    let activeKey = null;
    let controller = null;

    const keyFor = (type, id) => `${String(type || '')}:${String(id || '')}`;

    return {
      begin(type, id) {
        if (controller) controller.abort();
        controller = new AbortController();
        activeKey = keyFor(type, id);
        generation += 1;
        return { key: activeKey, generation, signal: controller.signal };
      },
      isCurrent(request, type, id) {
        return Boolean(
          request
          && request.generation === generation
          && request.key === activeKey
          && request.key === keyFor(type, id)
          && !request.signal.aborted
        );
      },
      cancel() {
        if (controller) controller.abort();
        controller = null;
        activeKey = null;
        generation += 1;
      },
    };
  }

  return { createDetailRequestState };
});
