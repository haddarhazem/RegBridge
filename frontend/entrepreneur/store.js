(function createEntrepreneurStore() {
  'use strict';

  const prefix = 'regbridge.entrepreneur';
  let userId = null;

  function scoped(suffix) {
    if (!userId) throw new Error('Entrepreneur store has not been scoped to a user');
    return `${prefix}.${userId}.${suffix}`;
  }

  window.RegBridgeEntrepreneurStore = Object.freeze({
    scope(id) { userId = id; },
    activeProject() { return window.localStorage.getItem(scoped('active-project')); },
    setActiveProject(id) { id ? window.localStorage.setItem(scoped('active-project'), id) : window.localStorage.removeItem(scoped('active-project')); },
  });
})();
