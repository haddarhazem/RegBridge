(function initializeAuthPage() {
  'use strict';

  const runtime = window.RegBridgeAuthRuntime;
  const page = document.body.dataset.authPage;
  const stateNode = document.querySelector('[data-auth-state]');
  const roleContainer = document.querySelector('[data-role-options]');
  const submitRolesButton = document.querySelector('[data-role-submit]');
  const userNode = document.querySelector('[data-auth-user]');

  function setState(message, state = 'info') {
    if (!stateNode) return;
    stateNode.hidden = false;
    stateNode.dataset.state = state;
    stateNode.textContent = message;
    stateNode.setAttribute('role', state === 'error' ? 'alert' : 'status');
    document.body.dataset.authStatus = state;
  }

  function setBusy(button, busy, label) {
    if (!button) return;
    button.disabled = busy;
    button.dataset.loading = String(busy);
    button.setAttribute('aria-busy', String(busy));
    if (label) button.textContent = label;
  }

  function selectedRoles() {
    return [...document.querySelectorAll('[data-role-checkbox]:checked')].map((input) => input.value);
  }

  function syncRoleButton() {
    if (submitRolesButton) submitRolesButton.disabled = selectedRoles().length === 0;
  }

  function renderOnboardingOptions(options, selected) {
    roleContainer.replaceChildren();
    options.forEach((option) => {
      const row = document.createElement('label');
      row.className = 'role-option';
      row.dataset.selected = String(selected.has(option.code));

      const input = document.createElement('input');
      input.type = 'checkbox';
      input.value = option.code;
      input.checked = selected.has(option.code);
      input.dataset.roleCheckbox = '';

      const node = document.createElement('span');
      node.className = 'role-node';
      node.setAttribute('aria-hidden', 'true');
      const copy = document.createElement('span');
      const title = document.createElement('strong');
      title.textContent = option.label;
      const description = document.createElement('small');
      description.textContent = option.description;
      copy.append(title, description);
      const check = document.createElement('span');
      check.className = 'role-check';
      check.setAttribute('aria-hidden', 'true');
      check.textContent = input.checked ? '✓' : '+';
      row.append(input, node, copy, check);
      input.addEventListener('change', () => {
        row.dataset.selected = String(input.checked);
        check.textContent = input.checked ? '✓' : '+';
        syncRoleButton();
      });
      roleContainer.append(row);
    });
    syncRoleButton();
  }

  function renderWorkspace(user) {
    roleContainer.replaceChildren();
    if (userNode) userNode.textContent = user.email;
    const requested = new URLSearchParams(window.location.search).get('role');
    const stored = window.sessionStorage.getItem(runtime.workspaceKey);
    const active = user.roles.includes(requested) ? requested : (user.roles.includes(stored) ? stored : user.roles[0]);
    user.roles.forEach((code) => {
      const option = document.createElement('button');
      option.type = 'button';
      option.className = 'role-option workspace-option';
      option.dataset.selected = String(code === active);
      option.dataset.workspaceRole = code;
      option.setAttribute('aria-pressed', String(code === active));
      const title = document.createElement('strong');
      title.textContent = ({ entrepreneur: 'Entrepreneur / Startup', investor: 'Investisseur', researcher: 'Chercheur' })[code] || code;
      const detail = document.createElement('small');
      detail.textContent = 'Ouvrir cet espace sans modifier les rôles du compte';
      option.append(title, detail);
      option.addEventListener('click', () => {
        window.sessionStorage.setItem(runtime.workspaceKey, code);
        roleContainer.querySelectorAll('[data-workspace-role]').forEach((item) => {
          const selected = item.dataset.workspaceRole === code;
          item.dataset.selected = String(selected);
          item.setAttribute('aria-pressed', String(selected));
        });
        setState(`Espace actif : ${title.textContent}`, 'success');
        if (code === 'entrepreneur') window.location.assign(runtime.workspaceDestination(code));
      });
      roleContainer.append(option);
    });
    window.sessionStorage.setItem(runtime.workspaceKey, active);
    setState('Session active. Choisissez votre contexte de travail.', 'success');
  }

  async function requireUser() {
    try {
      return await runtime.currentUser();
    } catch (error) {
      if (error.code === 'unauthenticated') {
        const intended = runtime.safeReturnTo(`${window.location.pathname}${window.location.search}`);
        if (intended) window.sessionStorage.setItem('regbridge.auth.return_to', intended);
        window.location.replace('/auth/login/');
        return null;
      }
      setState(error.message, 'error');
      return null;
    }
  }

  async function initializeLoginOrRegister() {
    try {
      const user = await runtime.currentUser();
      window.location.replace(runtime.destinationFor(user));
    } catch (error) {
      if (error.code !== 'unauthenticated') setState(error.message, 'error');
      else setState('Aucune session RegBridge active.', 'info');
    }
  }

  async function initializeCallback() {
    setState('Validation sécurisée du retour fournisseur…', 'loading');
    try {
      const result = await runtime.finishCallback();
      setState('Compte RegBridge prêt.', 'success');
      window.location.replace(runtime.destinationFor(result.currentUser, result.returnTo));
    } catch {
      setState('La connexion n’a pas pu être finalisée. Recommencez depuis la page de connexion.', 'error');
    }
  }

  async function initializeOnboarding() {
    const user = await requireUser();
    if (!user) return;
    if (userNode) userNode.textContent = user.email;
    try {
      const options = await runtime.roleOptions();
      renderOnboardingOptions(options, new Set(user.roles));
      setState('Sélectionnez au moins un rôle métier.', 'info');
    } catch (error) {
      setState(error.message, 'error');
    }
  }

  async function initializeWorkspace() {
    const user = await requireUser();
    if (!user) return;
    if (user.needs_role_onboarding || user.roles.length === 0) {
      window.location.replace('/onboarding/roles/');
      return;
    }
    renderWorkspace(user);
  }

  document.querySelectorAll('[data-provider-form]').forEach((form) => {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const button = form.querySelector('[data-provider-action]');
      setBusy(button, true, 'Redirection sécurisée…');
      setState('Connexion à votre fournisseur d’identité…', 'loading');
      try {
        const intended = new URLSearchParams(window.location.search).get('returnTo');
        await runtime.startAuthentication(button.dataset.providerAction, intended);
      } catch (error) {
        const label = button.dataset.providerAction === 'register'
          ? 'Continuer avec votre organisation'
          : 'Se connecter avec votre organisation';
        setBusy(button, false, label);
        setState(error.message, 'error');
      }
    });
  });

  submitRolesButton?.addEventListener('click', async () => {
    setBusy(submitRolesButton, true, 'Enregistrement…');
    setState('Enregistrement de vos rôles…', 'loading');
    try {
      const user = await runtime.replaceRoles(selectedRoles());
      setState('Rôles enregistrés.', 'success');
      window.location.replace(runtime.destinationFor(user));
    } catch (error) {
      setBusy(submitRolesButton, false, 'Continuer');
      setState(error.message, 'error');
    }
  });

  document.querySelectorAll('[data-auth-signout]').forEach((button) => {
    button.addEventListener('click', async () => {
      button.disabled = true;
      setState('Déconnexion…', 'loading');
      await runtime.logout();
    });
  });

  if (page === 'callback') initializeCallback();
  else if (page === 'onboarding') initializeOnboarding();
  else if (page === 'workspace') initializeWorkspace();
  else if (page === 'login' || page === 'register') initializeLoginOrRegister();
})();
