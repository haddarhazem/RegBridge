(function initializeEntrepreneurApp() {
  'use strict';

  const api = window.RegBridgeEntrepreneurApi;
  const store = window.RegBridgeEntrepreneurStore;
  const views = window.RegBridgeEntrepreneurViews;
  const runtime = window.RegBridgeAuthRuntime;
  const workspace = document.querySelector('[data-workspace]');
  const nav = document.querySelector('[data-sidebar-nav]');
  const switcher = document.querySelector('[data-project-switcher]');
  const progressCard = document.querySelector('[data-progress-card]');
  const breadcrumbs = document.querySelector('[data-breadcrumbs]');
  const loading = document.querySelector('[data-app-loading]');

  const state = {
    user: null, projects: [], project: null, view: 'dashboard', tab: 'overview',
    onboarding: null, facts: [], assessment: null, assessments: [], roadmap: null,
    documents: [], members: [], controls: [], score: null,
    editingFactId: null,
    copilot: { projectId: null, conversationId: null, messages: [], loading: false, error: '', notice: '', controller: null },
  };

  function route() {
    const params = new URLSearchParams(window.location.search);
    return { view: params.get('view') || 'dashboard', projectId: params.get('project'), tab: params.get('tab') || 'overview', version: params.get('version') };
  }

  function routeUrl(view, projectId = state.project?.id, extra = {}) {
    const params = new URLSearchParams({ view });
    if (projectId) params.set('project', projectId);
    Object.entries(extra).forEach(([key, value]) => value != null && params.set(key, value));
    return `/entrepreneur/?${params}`;
  }

  function navigate(view, options = {}) {
    const url = routeUrl(view, options.projectId === undefined ? state.project?.id : options.projectId, options);
    window.history.pushState({}, '', url);
    loadRoute();
  }

  function setBusy(element, busy, label) {
    if (!element) return;
    if (element.tagName === 'SELECT') {
      element.disabled = busy;
      element.setAttribute('aria-busy', String(busy));
      return;
    }
    if (!element.dataset.originalLabel) element.dataset.originalLabel = element.textContent;
    element.disabled = busy;
    element.dataset.loading = String(busy);
    element.textContent = busy ? label : element.dataset.originalLabel;
  }

  function formError(form, message) {
    const node = form?.querySelector('[data-form-error]');
    if (!node) return;
    node.hidden = !message;
    node.textContent = message || '';
  }

  function errorMessage(error) {
    if (error?.status === 401 || error?.code === 'unauthenticated') return 'Votre session a expiré. Reconnectez-vous.';
    if (error?.status === 403) return 'Vous n’avez pas accès à ce contexte.';
    if (error?.status === 404) return 'Ce projet n’existe pas ou n’est plus accessible.';
    if (error?.status === 429) return 'Trop de demandes ont été envoyées. Réessayez dans quelques instants.';
    return error?.message || 'Le service est momentanément indisponible.';
  }

  function resetCopilotContext(projectId, announce = false) {
    if (state.copilot.controller) state.copilot.controller.abort();
    state.copilot = {
      projectId,
      conversationId: null,
      messages: [],
      loading: false,
      error: '',
      notice: announce && projectId ? 'Projet actif modifié. Une nouvelle conversation a été ouverte.' : '',
      controller: null,
    };
    renderCopilot();
  }

  function copilotSources(message) {
    const value = message?.content_json?.sources;
    return Array.isArray(value) ? value.filter((item) => typeof item === 'string') : [];
  }

  function copilotWarnings(message) {
    const value = message?.content_json?.warnings;
    return Array.isArray(value) ? value.filter((item) => typeof item === 'string') : [];
  }

  function copilotReferences(message) {
    const value = message?.content_json?.references;
    return Array.isArray(value) ? value.filter((item) => typeof item === 'string') : [];
  }

  function renderCopilot() {
    const messages = document.querySelector('[data-copilot-messages]');
    if (!messages) return;
    const notice = document.querySelector('[data-copilot-notice]');
    const error = document.querySelector('[data-copilot-error]');
    const generating = document.querySelector('[data-copilot-generating]');
    const submit = document.querySelector('[data-submit-copilot]');
    const quick = document.querySelector('[data-copilot-quick-actions]');
    notice.hidden = !state.copilot.notice;
    notice.textContent = state.copilot.notice;
    error.hidden = !state.copilot.error;
    error.textContent = state.copilot.error;
    generating.hidden = !state.copilot.loading;
    submit.disabled = state.copilot.loading || !state.project;
    const suggestions = state.project ? [
      'Quelles obligations réglementaires principales concernent ce projet ?',
      'Quelles informations réglementaires dois-je encore préciser ?',
      ...(state.assessment ? ['Explique les obligations réglementaires de ce projet.'] : []),
      ...(state.roadmap ? ['Quelles sont mes prochaines étapes ?'] : []),
    ] : [];
    quick.innerHTML = suggestions.map((question) => `<button type="button" data-copilot-question="${views.escape(question)}">${views.escape(question)}</button>`).join('');
    messages.innerHTML = state.copilot.messages.length
      ? state.copilot.messages.filter((message) => ['user', 'assistant'].includes(message.role)).map((message) => {
        const sources = copilotSources(message);
        const warnings = copilotWarnings(message);
        const references = copilotReferences(message);
        return `<article class="copilot-message copilot-message-${views.escape(message.role)}"><span>${views.escape(message.content)}</span>${references.length ? `<div class="copilot-references" aria-label="Références utilisées">${references.map((reference) => `<span>${views.escape(reference)}</span>`).join('')}</div>` : ''}${sources.length ? `<div class="copilot-sources"><strong>Sources utilisées</strong>${sources.map((source) => `<span>${views.escape(source)}</span>`).join('')}</div>` : ''}${warnings.length ? `<div class="copilot-warnings">${warnings.map((warning) => `<span>${views.escape(warning)}</span>`).join('')}</div>` : ''}${message.created_at ? `<time>${views.date(message.created_at)}</time>` : ''}</article>`;
      }).join('')
      : '<p class="copilot-empty">Posez une question réglementaire sur votre projet. La réponse utilisera uniquement le contexte autorisé et les sources disponibles.</p>';
    messages.scrollTop = messages.scrollHeight;
  }

  async function ensureCopilotConversation() {
    if (!state.project) return;
    if (state.copilot.projectId === state.project.id && state.copilot.conversationId) return;
    state.copilot.loading = true;
    state.copilot.error = '';
    renderCopilot();
    try {
      const conversations = await api.conversations();
      let conversation = conversations.find((item) => item.subject_type === 'project' && item.subject_id === state.project.id);
      if (!conversation) conversation = await api.createConversation(state.project.id, `Copilote — ${state.project.display_name || 'Projet'}`);
      conversation = await api.conversation(conversation.id);
      state.copilot.projectId = state.project.id;
      state.copilot.conversationId = conversation.id;
      state.copilot.messages = conversation.messages || [];
    } catch (error) {
      state.copilot.error = errorMessage(error);
    } finally {
      state.copilot.loading = false;
      renderCopilot();
    }
  }

  async function submitCopilot(form) {
    const input = form.elements.content;
    const content = input.value.trim();
    if (!content || state.copilot.loading || !state.project) return;
    await ensureCopilotConversation();
    if (!state.copilot.conversationId) return;
    const controller = new AbortController();
    state.copilot.controller = controller;
    state.copilot.loading = true;
    state.copilot.error = '';
    state.copilot.messages.push({ role: 'user', content });
    input.value = '';
    renderCopilot();
    let timedOut = false;
    const timeout = window.setTimeout(() => { timedOut = true; controller.abort(); }, 60000);
    try {
      await api.askCopilot(state.copilot.conversationId, content, controller.signal);
      const conversation = await api.conversation(state.copilot.conversationId);
      state.copilot.messages = conversation.messages || [];
    } catch (error) {
      state.copilot.messages = state.copilot.messages.filter((message) => message.created_at);
      if (error.name === 'AbortError') state.copilot.error = timedOut ? 'Le Copilote met plus de temps que prévu. Réessayez.' : 'La demande a été arrêtée.';
      else if (error?.status === 401 || error?.code === 'unauthenticated') {
        const intended = `${window.location.pathname}${window.location.search}`;
        window.location.replace(`/auth/login/?returnTo=${encodeURIComponent(intended)}`);
        return;
      } else state.copilot.error = errorMessage(error);
    } finally {
      window.clearTimeout(timeout);
      state.copilot.loading = false;
      state.copilot.controller = null;
      renderCopilot();
      input.focus();
    }
  }

  async function hydrateProjects(requestedId) {
    const previousProjectId = state.project?.id || null;
    state.projects = await api.projects();
    if (requestedId && !state.projects.some((project) => project.id === requestedId)) {
      const error = new Error('Ce projet n’existe pas ou n’est plus accessible.');
      error.status = 404;
      state.project = null;
      store.setActiveProject(null);
      resetCopilotContext(null);
      throw error;
    }
    state.project = state.projects.find((project) => project.id === requestedId)
      || state.projects.find((project) => project.id === store.activeProject())
      || state.projects[0]
      || null;
    store.setActiveProject(state.project?.id || null);
    if (previousProjectId !== state.project?.id) resetCopilotContext(state.project?.id || null, previousProjectId !== null);
  }

  async function safe(call, fallback = null) {
    try { return await call(); } catch { return fallback; }
  }

  async function loadDocuments(projectId) {
    const ids = store.documentIds(projectId);
    const rows = await Promise.all(ids.map(async (id) => {
      try {
        const document = await api.getDocument(id);
        if (document.project_id !== projectId || document.deleted_at) { store.forgetDocument(projectId, id); return null; }
        const [analyses] = await Promise.all([safe(() => api.documentAnalyses(id), [])]);
        return { document, versions: store.versionRecords(id), analyses };
      } catch (error) {
        if ([403, 404].includes(error.status)) store.forgetDocument(projectId, id);
        return null;
      }
    }));
    return rows.filter(Boolean);
  }

  function renderProjectSwitcher() {
    if (!state.projects.length) {
      switcher.innerHTML = `<span>PROJET ACTIF</span><strong>Aucun projet pour le moment</strong><small>Créez votre premier projet pour commencer votre parcours.</small>${views.button('+ Créer un projet', 'create-project', 'sidebar')}`;
      return;
    }
    if (state.projects.length === 1) {
      switcher.innerHTML = `<span>PROJET ACTIF</span><strong>${views.escape(state.project.display_name || 'Projet sans nom')}</strong><small>${views.escape(views.lifecycle[state.project.project_type] || state.project.project_type)}</small>`;
      return;
    }
    switcher.innerHTML = `<label><span>PROJET ACTIF</span><select data-project-select aria-label="Projet actif">${state.projects.map((project) => `<option value="${views.escape(project.id)}" ${project.id === state.project.id ? 'selected' : ''}>${views.escape(project.display_name || 'Projet sans nom')}</option>`).join('')}</select></label>`;
  }

  function navGroup(title, items) {
    return `<section><h2>${title}</h2>${items.map(([view, label]) => `<a href="${routeUrl(view)}" data-nav-view="${view}" class="${state.view === view || (view === 'project' && ['facts', 'onboarding'].includes(state.view)) ? 'active' : ''}">${label}</a>`).join('')}</section>`;
  }

  function renderShell() {
    renderProjectSwitcher();
    const hasProject = Boolean(state.project);
    const essential = [['dashboard', 'Tableau de bord'], ...(hasProject ? [['project', 'Mon projet'], ['roadmap', 'Roadmap de lancement'], ['documents', 'Documents']] : [])];
    const analysis = hasProject ? [['regulatory', 'Réglementation'], ['contracts', 'Contrats'], ...(state.project.project_type !== 'idea' ? [['compliance', 'Conformité']] : [])] : [];
    const system = [...(hasProject ? [['access', 'Équipe & accès']] : []), ['profile', 'Profil']];
    nav.innerHTML = navGroup('ESSENTIEL', essential) + (analysis.length ? navGroup('ANALYSE', analysis) : '') + navGroup('SYSTÈME', system);
    document.querySelector('[data-user-email]').textContent = state.user.email;
    document.querySelector('[data-user-initials]').textContent = state.user.email.slice(0, 2).toUpperCase();
    const copilotButton = document.querySelector('[data-open-copilot]');
    const copilotCopy = document.querySelector('[data-copilot-copy]');
    const copilotAvailability = document.querySelector('[data-copilot-availability]');
    document.querySelector('[data-copilot-project]').textContent = state.project?.display_name || 'Aucun projet actif';
    document.querySelector('[data-copilot-project-type]').textContent = state.project ? (views.lifecycle[state.project.project_type] || state.project.project_type) : '';
    copilotButton.disabled = !state.project;
    copilotCopy.textContent = state.project
      ? 'Le copilote utilise uniquement les informations autorisées du projet actif.'
      : 'Créez ou sélectionnez un projet pour activer le contexte du copilote.';
    copilotAvailability.textContent = state.project
      ? 'Le copilote est disponible pour le projet actif.'
      : 'Un projet actif est nécessaire pour ouvrir le copilote.';
    if (!state.project) {
      progressCard.hidden = true;
    } else {
      progressCard.hidden = false;
      const stats = views.progress(state.roadmap);
      progressCard.innerHTML = `<span>LANCEMENT</span><strong>${stats.total ? `${stats.complete} / ${stats.total} étapes` : 'Roadmap non générée'}</strong>${stats.total ? `<i><b style="width:${stats.percent}%"></b></i>` : ''}`;
      progressCard.href = routeUrl('roadmap');
    }
    breadcrumbs.innerHTML = `<a href="/entrepreneur/">RegBridge</a><span>/</span><a href="/workspace/">Entrepreneur</a>${state.project ? `<span>/</span><span>${views.escape(state.project.display_name || 'Projet')}</span>` : ''}<span>/</span><strong>${views.escape(views.labels[state.view] || 'Tableau de bord')}</strong>`;
    renderCopilot();
  }

  async function loadProjectContext() {
    if (!state.project) {
      Object.assign(state, { onboarding: null, facts: [], assessment: null, assessments: [], roadmap: null, documents: [], members: [], controls: [], score: null });
      return;
    }
    const id = state.project.id;
    const [onboarding, facts, assessment, roadmap] = await Promise.all([
      safe(() => api.getOnboarding(id)), safe(() => api.facts(id), []), safe(() => api.latestAssessment(id)), safe(() => api.latestRoadmap(id)),
    ]);
    Object.assign(state, { onboarding, facts, assessment, roadmap });
  }

  function requireProject() {
    if (state.project) return true;
    workspace.innerHTML = views.dashboard({ project: null });
    return false;
  }

  async function renderView(routeState) {
    state.view = routeState.view;
    state.tab = routeState.tab;
    if (state.view === 'create') workspace.innerHTML = views.createProject();
    else if (state.view === 'profile') workspace.innerHTML = views.profile(state);
    else if (state.view === 'dashboard') workspace.innerHTML = views.dashboard(state);
    else if (!requireProject()) return;
    else if (state.view === 'onboarding') workspace.innerHTML = views.onboarding(state);
    else if (state.view === 'project' || state.view === 'facts') {
      const history = state.tab === 'history' ? await safe(() => api.lifecycleHistory(state.project.id), []) : [];
      workspace.innerHTML = views.project({ ...state, history, tab: state.view === 'facts' ? 'facts' : state.tab });
    } else if (state.view === 'regulatory') {
      state.assessments = await safe(() => api.assessments(state.project.id), []);
      if (routeState.version) state.assessment = await safe(() => api.assessment(state.project.id, routeState.version), state.assessment);
      workspace.innerHTML = views.regulatory(state);
    } else if (state.view === 'roadmap') workspace.innerHTML = views.roadmap(state);
    else if (state.view === 'documents') {
      state.documents = await loadDocuments(state.project.id);
      workspace.innerHTML = views.documents(state);
    } else if (state.view === 'contracts') {
      state.documents = await loadDocuments(state.project.id);
      workspace.innerHTML = views.contracts(state);
    } else if (state.view === 'access') {
      state.members = await safe(() => api.members(state.project.id), []);
      workspace.innerHTML = views.access(state);
    } else if (state.view === 'compliance') {
      let complianceError = null;
      if (state.project.project_type !== 'idea') {
        try { state.controls = await api.controls(state.project.id); } catch (error) { complianceError = errorMessage(error); }
        state.score = await safe(() => api.latestScore(state.project.id));
      }
      workspace.innerHTML = views.compliance({ ...state, error: complianceError });
    } else {
      window.history.replaceState({}, '', routeUrl('dashboard'));
      state.view = 'dashboard';
      workspace.innerHTML = views.dashboard(state);
    }
  }

  async function loadRoute() {
    workspace.setAttribute('aria-busy', 'true');
    workspace.innerHTML = '<div class="workspace-skeleton" aria-label="Chargement"><span></span><span></span><span></span></div>';
    const current = route();
    try {
      await hydrateProjects(current.projectId);
      await loadProjectContext();
      await renderView(current);
      renderShell();
      workspace.focus({ preventScroll: true });
    } catch (error) {
      workspace.innerHTML = views.inlineError(errorMessage(error));
    } finally {
      workspace.setAttribute('aria-busy', 'false');
      closeSidebar();
    }
  }

  async function refreshProject() {
    if (!state.project) return loadRoute();
    state.project = await api.getProject(state.project.id);
    return loadRoute();
  }

  async function action(target) {
    const name = target.dataset.action;
    if (!name) return;
    if (name === 'retry') return loadRoute();
    if (name === 'create-project') return navigate('create', { projectId: null });
    if (name === 'profile-logout') return runtime.logout();
    if (name === 'open-project') return navigate('project');
    if (name === 'open-onboarding') return navigate('onboarding');
    if (name === 'open-facts') return navigate('facts');
    if (name === 'open-regulatory') return navigate('regulatory');
    if (name === 'open-roadmap') return navigate('roadmap');
    if (name === 'open-documents') return navigate('documents');
    if (name === 'open-contracts') return navigate('contracts');
    if (name === 'project-tab') return navigate('project', { tab: target.dataset.tab });
    if (name === 'select-assessment') return navigate('regulatory', { version: target.dataset.version });
    if (name === 'filter-roadmap') {
      document.querySelectorAll('[data-action="filter-roadmap"]').forEach((item) => item.classList.toggle('active', item === target));
      document.querySelectorAll('[data-roadmap-status]').forEach((item) => { item.hidden = target.dataset.filter !== 'all' && item.dataset.roadmapStatus !== target.dataset.filter; });
      return;
    }
    if (name === 'show-upload') { document.querySelector('[data-form="upload-document"]').hidden = false; return; }
    if (name === 'submit-create') return submitCreate(target);
    if (name === 'submit-onboarding') return submitOnboarding(target);
    if (name === 'infer-facts') return perform(target, 'Déduction…', () => api.inferFacts(state.project.id), () => navigate('facts'));
    if (name === 'confirm-fact') return perform(target, 'Confirmation…', () => api.confirmFact(state.project.id, target.dataset.factId), loadRoute);
    if (name === 'reject-fact') return perform(target, 'Rejet…', () => api.rejectFact(state.project.id, target.dataset.factId), loadRoute);
    if (name === 'correct-fact') {
      state.editingFactId = target.dataset.factId;
      return renderView(route());
    }
    if (name === 'cancel-fact-correction') { state.editingFactId = null; return renderView(route()); }
    if (name === 'submit-fact-correction') return submitFactCorrection(target);
    if (name === 'transition-project') return perform(target, 'Transition…', () => api.transitionProject(state.project.id, 'startup_in_creation'), refreshProject);
    if (name === 'generate-assessment') {
      if (state.facts.some((fact) => fact.status === 'pending_confirmation')) {
        navigate('facts');
        return showToast('Certaines informations doivent encore être vérifiées.');
      }
      return perform(target, 'Analyse en cours…', () => api.generateAssessment(state.project.id, 'Évaluez les obligations réglementaires principales applicables à cette idée.'), () => navigate('regulatory'));
    }
    if (name === 'generate-roadmap') {
      if (!state.assessment) return navigate('regulatory');
      return perform(target, 'Génération…', () => api.generateRoadmap(state.project.id, state.assessment.id), () => navigate('roadmap'));
    }
    if (name === 'complete-roadmap-item') return perform(target, 'Mise à jour…', () => api.updateRoadmapItem(state.project.id, state.roadmap.version, target.dataset.itemId, 'completed'), loadRoute);
    if (name === 'submit-upload') return submitUpload(target);
    if (name === 'show-version-upload') return uploadVersion(target.dataset.documentId);
    if (name === 'document-contracts') return navigate('contracts', { document: target.dataset.documentId });
    if (name === 'analyze-contract') return analyzeContract(target);
  }

  async function perform(button, label, call, done) {
    setBusy(button, true, label);
    try { await call(); await done(); }
    catch (error) {
      setBusy(button, false);
      showToast(errorMessage(error));
    }
  }

  function showToast(message) {
    const panel = document.createElement('div');
    panel.className = 'toast-error'; panel.setAttribute('role', 'alert'); panel.textContent = message;
    document.body.append(panel); window.setTimeout(() => panel.remove(), 5000);
  }

  async function submitCreate(button) {
    const form = button.closest('form');
    if (!form.reportValidity()) return;
    formError(form, ''); setBusy(button, true, 'Création…');
    try {
      const data = new FormData(form);
      const project = await api.createProject({ project_type: 'idea', display_name: data.get('display_name').trim(), raw_description: data.get('raw_description').trim(), visibility: 'private' });
      store.setActiveProject(project.id);
      workspace.innerHTML = '<section class="surface creation-success" role="status"><span aria-hidden="true">✓</span><h1>Projet créé.</h1><p>Quelques informations supplémentaires nous permettront d’adapter votre parcours.</p></section>';
      await new Promise((resolve) => window.setTimeout(resolve, 650));
      navigate('onboarding', { projectId: project.id });
    } catch (error) { setBusy(button, false); formError(form, errorMessage(error)); }
  }

  async function submitOnboarding(button) {
    const form = button.closest('form');
    if (!form.reportValidity()) return;
    formError(form, ''); setBusy(button, true, 'Enregistrement…');
    try {
      const field = form.dataset.field;
      const keys = { market: 'target_market' };
      const payload = { [keys[field] || field]: new FormData(form).get('value').trim(), confirm: [field] };
      const result = await api.updateOnboarding(state.project.id, payload);
      if (result.status === 'complete') {
        await api.inferFacts(state.project.id);
        state.editingFactId = null;
        navigate('facts');
      } else {
        await refreshProject();
      }
    } catch (error) { setBusy(button, false); formError(form, errorMessage(error)); }
  }

  async function submitFactCorrection(button) {
    const form = button.closest('form');
    if (!form.reportValidity()) return;
    const value = new FormData(form).get('value').trim();
    formError(form, ''); setBusy(button, true, 'Correction…');
    try {
      await api.correctFact(state.project.id, form.dataset.factId, value);
      state.editingFactId = null;
      await loadRoute();
    } catch (error) { setBusy(button, false); formError(form, errorMessage(error)); }
  }

  async function submitUpload(button) {
    const form = button.closest('form');
    if (!form.reportValidity()) return;
    const data = new FormData(form); const file = data.get('upload');
    formError(form, ''); setBusy(button, true, 'Import…');
    try {
      const result = await api.uploadDocument(state.project.id, file, { title: data.get('title'), classification: data.get('classification'), visibility: data.get('visibility') });
      store.rememberDocument(state.project.id, result.document.id); store.rememberVersion(result.document.id, result.version);
      await loadRoute();
    } catch (error) { setBusy(button, false); formError(form, errorMessage(error)); }
  }

  async function uploadVersion(documentId) {
    const input = document.createElement('input'); input.type = 'file'; input.accept = '.pdf,.docx,.txt';
    input.addEventListener('change', async () => {
      if (!input.files[0]) return;
      try { const result = await api.uploadDocumentVersion(documentId, input.files[0]); store.rememberVersion(documentId, result.version); await loadRoute(); }
      catch (error) { window.alert(errorMessage(error)); }
    });
    input.click();
  }

  async function analyzeContract(button) {
    const select = document.querySelector('[data-contract-document]');
    if (!select?.value) { select?.focus(); return; }
    const [documentId, versionId] = select.value.split('|');
    await perform(button, 'Analyse…', () => api.analyzeContract(documentId, versionId), loadRoute);
  }

  function openSidebar() { document.body.classList.add('sidebar-open'); document.querySelector('[data-open-sidebar]').setAttribute('aria-expanded', 'true'); }
  function closeSidebar() { document.body.classList.remove('sidebar-open'); document.querySelector('[data-open-sidebar]').setAttribute('aria-expanded', 'false'); }
  async function openCopilot() {
    if (!state.project) return;
    document.body.classList.add('copilot-open');
    document.querySelector('[data-copilot-drawer]').setAttribute('aria-hidden', 'false');
    document.querySelector('[data-close-copilot]').focus();
    await ensureCopilotConversation();
    document.querySelector('#copilot-question')?.focus();
  }
  function closeCopilot() { document.body.classList.remove('copilot-open'); document.querySelector('[data-copilot-drawer]').setAttribute('aria-hidden', 'true'); }

  document.addEventListener('click', (event) => {
    const suggested = event.target.closest('[data-copilot-question]');
    if (suggested) {
      const input = document.querySelector('#copilot-question');
      input.value = suggested.dataset.copilotQuestion;
      input.focus();
      return;
    }
    const navLink = event.target.closest('[data-nav-view]');
    if (navLink) { event.preventDefault(); navigate(navLink.dataset.navView); return; }
    const target = event.target.closest('[data-action]');
    if (target) { event.preventDefault(); action(target); }
  });
  document.addEventListener('change', async (event) => {
    if (event.target.matches('[data-project-select]')) { store.setActiveProject(event.target.value); navigate('dashboard', { projectId: event.target.value }); }
    if (event.target.matches('[data-roadmap-item]')) await perform(event.target, 'Mise à jour…', () => api.updateRoadmapItem(state.project.id, state.roadmap.version, event.target.dataset.roadmapItem, event.target.value), loadRoute);
  });
  document.querySelector('[data-open-sidebar]').addEventListener('click', openSidebar);
  document.querySelector('[data-close-sidebar]').addEventListener('click', closeSidebar);
  document.querySelector('[data-sidebar-scrim]').addEventListener('click', closeSidebar);
  document.querySelector('[data-open-copilot]').addEventListener('click', openCopilot);
  document.querySelector('[data-close-copilot]').addEventListener('click', closeCopilot);
  document.querySelector('[data-cancel-copilot]').addEventListener('click', () => state.copilot.controller?.abort());
  document.querySelector('[data-copilot-form]').addEventListener('submit', (event) => { event.preventDefault(); submitCopilot(event.currentTarget); });
  document.querySelector('[data-drawer-scrim]').addEventListener('click', closeCopilot);
  document.querySelector('[data-logout]').addEventListener('click', () => runtime.logout());
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    if (document.body.classList.contains('copilot-open')) { closeCopilot(); document.querySelector('[data-open-copilot]').focus(); }
    else if (document.body.classList.contains('sidebar-open')) { closeSidebar(); document.querySelector('[data-open-sidebar]').focus(); }
  });
  window.addEventListener('popstate', loadRoute);

  (async function start() {
    try {
      state.user = await api.me();
      if (!state.user.roles.includes('entrepreneur')) { window.location.replace('/workspace/'); return; }
      store.scope(state.user.id);
      await loadRoute();
      document.body.dataset.appState = 'ready'; loading.hidden = true;
    } catch (error) {
      if (error.code === 'unauthenticated') {
        const intended = `${window.location.pathname}${window.location.search}`;
        window.location.replace(`/auth/login/?returnTo=${encodeURIComponent(intended)}`);
        return;
      }
      loading.innerHTML = `<strong>Impossible d’ouvrir l’espace.</strong><span>${views.escape(errorMessage(error))}</span><a href="/auth/login/">Revenir à la connexion</a>`;
    }
  })();
})();
