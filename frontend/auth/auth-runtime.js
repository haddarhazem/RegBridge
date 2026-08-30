(function createAuthRuntime() {
  'use strict';

  const RETURN_KEY = 'regbridge.auth.return_to';
  const WORKSPACE_KEY = 'regbridge.workspace.active';
  let managerPromise;

  class AuthError extends Error {
    constructor(code, message, status) {
      super(message);
      this.name = 'AuthError';
      this.code = code;
      this.status = status;
    }
  }

  function safeReturnTo(value) {
    if (typeof value !== 'string' || !value.trim()) return null;
    try {
      const target = new URL(value, window.location.origin);
      if (target.origin !== window.location.origin || !target.pathname.startsWith('/')) return null;
      if (target.pathname.startsWith('/auth/callback')) return null;
      return `${target.pathname}${target.search}${target.hash}`;
    } catch {
      return null;
    }
  }

  async function loadManager() {
    if (managerPromise) return managerPromise;
    managerPromise = (async () => {
      if (!window.oidc || typeof window.oidc.UserManager !== 'function') {
        throw new AuthError('library_unavailable', 'Le client d’authentification est indisponible.');
      }
      const response = await fetch('/auth/config', { headers: { Accept: 'application/json' } });
      if (!response.ok) {
        throw new AuthError('configuration_unavailable', 'L’authentification navigateur n’est pas configurée.', response.status);
      }
      const config = await response.json();
      const storage = new window.oidc.WebStorageStateStore({ store: window.sessionStorage });
      return new window.oidc.UserManager({
        authority: config.authority,
        client_id: config.client_id,
        redirect_uri: config.redirect_uri,
        post_logout_redirect_uri: config.post_logout_redirect_uri || undefined,
        response_type: 'code',
        scope: config.scope,
        extraQueryParams: config.authorization_extra_params || {},
        loadUserInfo: false,
        automaticSilentRenew: false,
        monitorSession: false,
        userStore: storage,
        stateStore: storage,
      });
    })();
    return managerPromise;
  }

  async function getOIDCUser() {
    const manager = await loadManager();
    const user = await manager.getUser();
    if (!user || user.expired || !user.access_token) {
      if (user) await manager.removeUser();
      throw new AuthError('unauthenticated', 'Votre session d’authentification est absente ou expirée.', 401);
    }
    return user;
  }

  async function apiRequest(path, options = {}) {
    const manager = await loadManager();
    const user = await getOIDCUser();
    const headers = new Headers(options.headers || {});
    headers.set('Accept', 'application/json');
    headers.set('Authorization', `Bearer ${user.access_token}`);
    headers.set('X-Request-ID', window.crypto.randomUUID());
    if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
    const response = await fetch(path, { ...options, headers });
    if (response.status === 401) {
      await manager.removeUser();
      throw new AuthError('unauthenticated', 'Votre session a expiré. Reconnectez-vous.', 401);
    }
    if (!response.ok) {
      let detail = response.status === 403
        ? 'Votre compte ne dispose pas de cette autorisation.'
        : 'Le service est momentanément indisponible.';
      try {
        const payload = await response.json();
        if (response.status === 422) detail = 'Les informations envoyées ne sont pas valides.';
        if (response.status === 409) detail = 'Ce compte nécessite une association contrôlée.';
        if (typeof payload.detail === 'string' && response.status < 500) detail = payload.detail;
      } catch {
        // Keep the safe generic message.
      }
      throw new AuthError(response.status === 403 ? 'forbidden' : 'api_error', detail, response.status);
    }
    return response.status === 204 ? null : response.json();
  }

  async function startAuthentication(kind, returnTo) {
    const manager = await loadManager();
    const safeTarget = safeReturnTo(returnTo);
    if (safeTarget) window.sessionStorage.setItem(RETURN_KEY, safeTarget);
    await manager.signinRedirect({
      state: { returnTo: safeTarget, intent: kind === 'register' ? 'register' : 'login' },
    });
  }

  async function finishCallback() {
    const manager = await loadManager();
    const user = await manager.signinRedirectCallback();
    const stateTarget = safeReturnTo(user.state && user.state.returnTo);
    return { currentUser: await apiRequest('/me'), returnTo: stateTarget };
  }

  async function currentUser() {
    return apiRequest('/me');
  }

  async function roleOptions() {
    return apiRequest('/me/roles/options');
  }

  async function replaceRoles(roles) {
    return apiRequest('/me/roles', { method: 'PUT', body: JSON.stringify({ roles }) });
  }

  function destinationFor(user, intended) {
    const safeTarget = safeReturnTo(intended || window.sessionStorage.getItem(RETURN_KEY));
    window.sessionStorage.removeItem(RETURN_KEY);
    if (user.needs_role_onboarding || !Array.isArray(user.roles) || user.roles.length === 0) {
      return '/onboarding/roles/';
    }
    if (safeTarget) return safeTarget;
    if (user.roles.length > 1) return '/workspace/';
    if (user.roles[0] === 'entrepreneur') return '/entrepreneur/';
    return `/workspace/?role=${encodeURIComponent(user.roles[0])}`;
  }

  function workspaceDestination(role) {
    return role === 'entrepreneur' ? '/entrepreneur/' : `/workspace/?role=${encodeURIComponent(role)}`;
  }

  async function logout() {
    const manager = await loadManager();
    window.sessionStorage.removeItem(RETURN_KEY);
    window.sessionStorage.removeItem(WORKSPACE_KEY);
    try {
      await manager.signoutRedirect();
    } catch {
      await manager.removeUser();
      window.location.assign('/auth/login/');
    }
  }

  window.RegBridgeAuthRuntime = Object.freeze({
    AuthError,
    apiRequest,
    currentUser,
    destinationFor,
    finishCallback,
    logout,
    replaceRoles,
    roleOptions,
    safeReturnTo,
    startAuthentication,
    workspaceDestination,
    workspaceKey: WORKSPACE_KEY,
  });
})();
