(function createEntrepreneurStore() {
  'use strict';

  const prefix = 'regbridge.entrepreneur';
  let userId = null;

  function scoped(suffix) {
    if (!userId) throw new Error('Entrepreneur store has not been scoped to a user');
    return `${prefix}.${userId}.${suffix}`;
  }

  function readList(key) {
    try {
      const value = JSON.parse(window.localStorage.getItem(key) || '[]');
      return Array.isArray(value) ? value.filter((item) => typeof item === 'string') : [];
    } catch {
      return [];
    }
  }

  function remember(key, id) {
    const values = readList(key).filter((value) => value !== id);
    values.unshift(id);
    window.localStorage.setItem(key, JSON.stringify(values.slice(0, 100)));
  }

  window.RegBridgeEntrepreneurStore = Object.freeze({
    scope(id) { userId = id; },
    activeProject() { return window.localStorage.getItem(scoped('active-project')); },
    setActiveProject(id) { id ? window.localStorage.setItem(scoped('active-project'), id) : window.localStorage.removeItem(scoped('active-project')); },
    documentIds(projectId) { return readList(scoped(`project.${projectId}.documents`)); },
    rememberDocument(projectId, id) { remember(scoped(`project.${projectId}.documents`), id); },
    forgetDocument(projectId, id) {
      const key = scoped(`project.${projectId}.documents`);
      window.localStorage.setItem(key, JSON.stringify(readList(key).filter((value) => value !== id)));
    },
    versionRecords(documentId) {
      try { return JSON.parse(window.localStorage.getItem(scoped(`document.${documentId}.versions`)) || '[]'); } catch { return []; }
    },
    rememberVersion(documentId, version) {
      const records = this.versionRecords(documentId).filter((item) => item.id !== version.id);
      records.unshift(version);
      window.localStorage.setItem(scoped(`document.${documentId}.versions`), JSON.stringify(records.slice(0, 50)));
    },
  });
})();
