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
    onboarding: null, facts: [], graph: null, graphError: null, assessment: null, assessments: [], roadmap: null, roadmapSourceAssessment: null,
    documents: [], documentFilter: 'all', members: [], frameworks: [], controls: [], score: null, scoreHistory: [], activeFrameworkVersionId: null, selectedControlId: null, selectedControlEvidence: [], documentPollTimer: null, documentPollAttempts: 0,
    editingFactId: null,
    copilot: { visible: false, mode: 'docked', unread: false, projectId: null, conversationId: null, messages: [], loading: false, historyLoading: false, error: '', notice: '', controller: null, historyController: null, generationConversationId: null, requestId: null, status: null, pollTimer: null, pollAttempts: 0, context: { documentId: null, versionId: null, analysisId: null } },
  };

  function route() {
    const params = new URLSearchParams(window.location.search);
    return { view: params.get('view') || 'dashboard', projectId: params.get('project'), tab: params.get('tab') || 'overview', version: params.get('version'), document: params.get('document'), analysis: params.get('analysis') };
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
    if (error?.name === 'AbortError') return 'La demande a été interrompue.';
    if (error?.status === 401 || error?.code === 'unauthenticated') return 'Votre session a expiré. Reconnectez-vous.';
    if (error?.status === 403) return 'Vous n’avez pas accès à ce contexte.';
    if (error?.status === 404) return 'Ce projet ou cette ressource n’existe pas ou n’est plus accessible.';
    if ([400, 422].includes(error?.status)) return 'Les informations envoyées ne sont pas valides. Vérifiez les champs.';
    if (error?.status === 409) return 'Cette opération est incompatible avec l’état actuel. Actualisez puis réessayez.';
    if (error?.status === 429) return 'Le service IA a atteint sa limite temporaire. Réessayez dans quelques instants.';
    if (error?.code === 'request_timeout') return 'Le délai de réponse est dépassé. Réessayez dans quelques instants.';
    if (error?.code === 'invalid_roadmap_response') return 'Le format de la roadmap reçu est invalide. Réessayez ou contactez le support.';
    if (error instanceof TypeError) return 'Connexion momentanément indisponible. Vérifiez le serveur et votre connexion.';
    return 'Le service est momentanément indisponible. Réessayez dans quelques instants.';
  }

  function resetCopilotContext(projectId, announce = false) {
    if (state.copilot.controller) state.copilot.controller.abort();
    if (state.copilot.historyController) state.copilot.historyController.abort();
    if (state.copilot.pollTimer) window.clearTimeout(state.copilot.pollTimer);
    state.copilot = {
      visible: state.copilot.visible, mode: state.copilot.mode, unread: false,
      projectId,
      conversationId: null,
      messages: [],
      loading: false,
      historyLoading: false,
      error: '',
      notice: announce && projectId ? 'Projet actif modifié. Une nouvelle conversation a été ouverte.' : '',
      controller: null,
      historyController: null,
      generationConversationId: null,
      requestId: null,
      status: null,
      pollTimer: null,
      pollAttempts: 0,
      context: { documentId: null, versionId: null, analysisId: null },
    };
    renderCopilot();
    document.querySelector('#copilot-question').value = '';
    const history = document.querySelector('[data-copilot-history]');
    if (history) { history.hidden = true; history.innerHTML = ''; }
  }

  function newCopilotConversation() {
    const copilot = state.copilot;
    if (copilot.historyController) copilot.historyController.abort();
    copilot.historyController = null;
    copilot.historyLoading = false;
    copilot.conversationId = null;
    copilot.messages = [];
    copilot.error = '';
    copilot.notice = copilot.loading
      ? 'Nouvelle conversation prête. La réponse précédente continue dans son historique.'
      : 'Nouvelle conversation prête.';
    const history = document.querySelector('[data-copilot-history]');
    history.hidden = true;
    history.innerHTML = '';
    document.querySelector('#copilot-question').value = '';
    renderCopilot();
    document.querySelector('#copilot-question').focus();
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

  const copilotStageLabels = Object.freeze({
    CONTEXT_BUILDING: 'Préparation du contexte',
    RETRIEVING_EVIDENCE: 'Recherche des sources',
    ASSESSING_EVIDENCE: 'Évaluation des sources',
    RETRIEVING_MISSING_DOMAIN_EVIDENCE: 'Recherche complémentaire des sources',
    REASSESSING_EVIDENCE: 'Réévaluation des sources',
    RETRIEVING_AUTHORITATIVE_EVIDENCE: 'Recherche des sources officielles',
    REASSESSING_AUTHORITATIVE_EVIDENCE: 'Réévaluation des sources',
    GENERATING: 'Génération de la réponse',
    VERIFYING: 'Vérification de la réponse',
    COMPLETED: 'Terminé',
    FAILED: 'Échec',
    CANCELLED: 'Annulé',
  });

  function clearCopilotPolling(copilot = state.copilot) {
    if (copilot.pollTimer) window.clearTimeout(copilot.pollTimer);
    copilot.pollTimer = null;
  }

  function renderCopilotProgress(copilot) {
    const status = copilot.status;
    const label = document.querySelector('[data-copilot-stage-label]');
    const progress = document.querySelector('[data-copilot-progress]');
    const diagnostics = document.querySelector('[data-copilot-diagnostics]');
    const diagnosticsContent = document.querySelector('[data-copilot-diagnostics-content]');
    if (!label || !progress || !diagnostics || !diagnosticsContent) return;
    const stages = (Array.isArray(status?.stages) ? status.stages : []).filter((item) => (
      !['RETRIEVING_MISSING_DOMAIN_EVIDENCE', 'REASSESSING_EVIDENCE', 'RETRIEVING_AUTHORITATIVE_EVIDENCE', 'REASSESSING_AUTHORITATIVE_EVIDENCE'].includes(item.stage)
      || item.status !== 'not_started'
    ));
    label.textContent = copilotStageLabels[status?.current_stage] || 'Connexion au Copilote';
    progress.innerHTML = stages.map((item) => `<li data-status="${views.escape(item.status)}">${item.status === 'succeeded' ? '✓' : item.status === 'running' ? '●' : '○'} ${views.escape(copilotStageLabels[item.stage] || item.stage)}</li>`).join('');
    const data = status?.diagnostics;
    diagnostics.hidden = !data;
    if (data) {
      const rows = [
        ['Request ID', status.request_id], ['Sources récupérées', data.retrieved_chunk_count], ['Couverture', status.evidence_status],
        ['Domaines requis', (data.required_domains || []).join(', ')], ['Couverts', (data.covered_domains || []).join(', ')],
        ['À vérifier', (data.missing_domains || []).join(', ')], ['Fournisseur / modèle', [data.provider, data.model].filter(Boolean).join(' / ')],
        ['Dérivation', data.resolution_source], ['Signaux', (data.matched_signals || []).join(', ')],
        ['Précision requise', data.needs_clarification ? 'Oui' : 'Non'], ['Vérification', data.verification_verdict], ['Code échec', data.failure_code],
        ['Question scope', data.question_scope], ['Scope signals', (data.scope_signals || []).join(', ')],
        ['Scope supported', data.scope_supported === true ? 'Yes' : data.scope_supported === false ? 'No' : null], ['Scope reason', data.scope_support_reason],
        ['Verification reason', data.verification_reason], ['Claims analysed', data.semantic_claim_count],
        ['Supported claims', data.supported_claim_count], ['Unsupported claims', data.unsupported_claim_count],
        ['Unverified claims', data.unverified_claim_count],
        ['Sources initiales', data.initial_evidence_count], ['Statut initial', data.initial_evidence_status],
        ['Couverts initialement', (data.initial_covered_domains || []).join(', ')], ['Manquants initialement', (data.initial_missing_domains || []).join(', ')],
        ['Initial question scope', data.initial_question_scope], ['Initial scope supported', data.initial_scope_supported === true ? 'Yes' : data.initial_scope_supported === false ? 'No' : null], ['Initial scope reason', data.initial_scope_support_reason],
        ['Recherche complémentaire', data.fallback_attempted ? 'Oui' : 'Non'], ['Domaines recherchés', (data.fallback_domains || []).join(', ')],
        ['Sources complémentaires', data.fallback_evidence_count], ['Nouvelles sources uniques', data.fallback_unique_evidence_count],
        ['Échecs complémentaires', (data.fallback_failed_domains || []).join(', ')], ['Sources finales', data.final_evidence_count],
        ['Statut final', data.final_evidence_status], ['Couverts finalement', (data.final_covered_domains || []).join(', ')],
        ['Manquants finalement', (data.final_missing_domains || []).join(', ')],
        ['Final question scope', data.final_question_scope], ['Final scope supported', data.final_scope_supported === true ? 'Yes' : data.final_scope_supported === false ? 'No' : null], ['Final scope reason', data.final_scope_support_reason],
        ['Sources officielles consultées', data.authoritative_fallback_attempted ? 'Oui' : 'Non'],
        ['Sources officielles', (data.authoritative_sources_attempted || []).join(', ')],
        ['Sources officielles indisponibles', (data.authoritative_sources_failed || []).join(', ')],
        ['Extraits officiels retenus', data.authoritative_external_evidence_count],
      ].filter(([, value]) => value !== null && value !== undefined && value !== '');
      diagnosticsContent.innerHTML = rows.map(([key, value]) => `<dt>${views.escape(key)}</dt><dd>${views.escape(String(value))}</dd>`).join('');
    }
  }

  function renderCopilot() {
    const copilot = state.copilot;
    document.body.classList.toggle('copilot-open', copilot.visible);
    document.body.classList.toggle('copilot-fullscreen', copilot.mode === 'fullscreen');
    const drawer = document.querySelector('[data-copilot-drawer]');
    const modalPresentation = copilot.mode === 'fullscreen' || window.matchMedia('(max-width: 600px)').matches;
    drawer.setAttribute('role', modalPresentation ? 'dialog' : 'complementary');
    if (modalPresentation) drawer.setAttribute('aria-modal', 'true');
    else drawer.removeAttribute('aria-modal');
    drawer.inert = !copilot.visible;
    drawer.setAttribute('aria-hidden', String(!copilot.visible));
    const expand = document.querySelector('[data-expand-copilot]');
    expand.setAttribute('aria-pressed', String(copilot.mode === 'fullscreen'));
    expand.setAttribute('aria-label', copilot.mode === 'fullscreen' ? 'Réduire le copilote' : 'Agrandir le copilote');
    expand.textContent = copilot.mode === 'fullscreen' ? '−' : '⛶';
    document.querySelector('[data-open-copilot]').setAttribute('aria-label', copilot.unread ? 'Copilote : réponse disponible' : copilot.loading ? 'Copilote : réponse en cours' : 'Ouvrir le copilote');
    document.querySelector('[data-open-copilot]').classList.toggle('has-unread', copilot.unread);
    document.querySelectorAll('[data-new-copilot], [data-show-copilot-history]').forEach((control) => { control.disabled = copilot.historyLoading; });
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
    renderCopilotProgress(copilot);
    const confirmed = state.project?.confirmed_fields || [];
    const fields = [['activity', 'Activité', 'activity'], ['sector', 'Secteur', 'sector'], ['technology', 'Technologie', 'technology'], ['data', 'Données', 'data'], ['market', 'Marché', 'target_market'], ['location', 'Localisation', 'location']];
    const available = fields.filter(([key, , property]) => confirmed.includes(key) && state.project[property]);
    document.querySelector('[data-copilot-context-count]').textContent = `${available.length}/6 informations déclarées confirmées`;
    document.querySelector('[data-copilot-context-details]').innerHTML = available.map(([, label, property]) => `<dt>${label}</dt><dd>${views.escape(state.project[property])}</dd>`).join('');
    submit.disabled = state.copilot.loading || !state.project;
    const suggestions = state.project ? [
      'Quelles obligations réglementaires principales concernent ce projet ?',
      'Quelles informations réglementaires dois-je encore préciser ?',
      ...(state.assessment ? ['Explique les obligations réglementaires de ce projet.'] : []),
      ...(state.roadmap ? ['Quelles sont mes prochaines étapes ?'] : []),
    ] : [];
    quick.innerHTML = suggestions.map((question) => `<button type="button" data-copilot-question="${views.escape(question)}">${views.escape(question)}</button>`).join('');
    const candidateLabel = { technology: 'Technologie', data: 'Données', market: 'Marché', provider: 'Fournisseur / infrastructure' };
    const knowledgeCandidates = (message) => Array.isArray(message?.content_json?.knowledge_candidates) ? message.content_json.knowledge_candidates : [];
    const candidateCards = (message) => knowledgeCandidates(message).map((candidate) => {
      const removal = candidate.operation === 'REMOVE';
      return `<section class="copilot-knowledge-candidates" aria-label="Informations détectées sur votre projet"><p>INFORMATIONS DÉTECTÉES SUR VOTRE PROJET</p><article class="copilot-knowledge-candidate"><div><strong>${views.escape(candidate.value)}</strong><span>${views.escape(removal ? `Retirer : ${candidateLabel[candidate.domain] || candidate.domain}` : candidateLabel[candidate.domain] || candidate.domain)}</span><small>À confirmer</small></div><div class="copilot-candidate-actions"><button type="button" data-action="confirm-fact" data-fact-id="${views.escape(candidate.id)}">${removal ? 'Confirmer le retrait' : 'Confirmer'}</button><button type="button" data-action="correct-fact" data-from-copilot="true" data-fact-id="${views.escape(candidate.id)}">Corriger</button><button type="button" data-action="reject-fact" data-fact-id="${views.escape(candidate.id)}">Rejeter</button></div></article></section>`;
    }).join('');
    messages.innerHTML = state.copilot.messages.length
      ? state.copilot.messages.filter((message) => ['user', 'assistant'].includes(message.role)).map((message) => {
        const sources = copilotSources(message);
        const warnings = copilotWarnings(message);
        const references = copilotReferences(message);
        return `<article class="copilot-message copilot-message-${views.escape(message.role)}"><span>${views.escape(message.content)}</span>${references.length ? `<div class="copilot-references" aria-label="Références utilisées">${references.map((reference) => `<span>${views.escape(reference)}</span>`).join('')}</div>` : ''}${sources.length ? `<div class="copilot-sources"><strong>Sources utilisées</strong>${sources.map((source) => `<span>${views.escape(source)}</span>`).join('')}</div>` : ''}${warnings.length ? `<div class="copilot-warnings">${warnings.map((warning) => `<span>${views.escape(warning)}</span>`).join('')}</div>` : ''}${candidateCards(message)}${message.created_at ? `<time>${views.date(message.created_at)}</time>` : ''}</article>`;
      }).join('')
      : '<p class="copilot-empty">Posez une question réglementaire sur votre projet. La réponse utilisera uniquement le contexte autorisé et les sources disponibles.</p>';
    messages.scrollTop = messages.scrollHeight;
  }

  // Each operation owns one captured state object and controller. Late completions
  // cannot update a new turn, project, or session even if abort is ignored upstream.
  function ownsCopilot(copilot, controller) {
    return state.copilot === copilot && copilot.controller === controller && !controller.signal.aborted;
  }

  async function ensureCopilotConversation(copilot, controller, startingConversationId) {
    if (startingConversationId) return startingConversationId;
    const conversation = await api.createConversation(copilot.projectId, 'Copilote — Projet', controller.signal, 15000);
    if (ownsCopilot(copilot, controller) && copilot.conversationId === startingConversationId) copilot.conversationId = conversation.id;
    return conversation.id;
  }

  async function pollCopilotStatus(copilot, controller, conversationId, requestId) {
    if (!ownsCopilot(copilot, controller) || !copilot.loading || copilot.requestId !== requestId) return;
    try {
      const status = await api.copilotStatus(conversationId, requestId, controller.signal);
      if (!ownsCopilot(copilot, controller) || copilot.requestId !== requestId) return;
      copilot.status = status;
      copilot.pollAttempts = 0;
      renderCopilot();
      if (['completed', 'failed', 'cancelled'].includes(status.status)) return;
    } catch (error) {
      if (!ownsCopilot(copilot, controller) || controller.signal.aborted) return;
      // The POST can legitimately reach the backend milliseconds after the first poll.
      if (error?.status !== 404 || copilot.pollAttempts >= 3) copilot.notice = 'Le suivi de progression est momentanément indisponible.';
      copilot.pollAttempts += 1;
    }
    if (ownsCopilot(copilot, controller) && copilot.loading && copilot.pollAttempts < 20) {
      copilot.pollTimer = window.setTimeout(() => pollCopilotStatus(copilot, controller, conversationId, requestId), 900);
    }
  }

  async function submitCopilot(form) {
    const input = form.elements.content;
    const content = input.value.trim();
    if (!content || state.copilot.loading || !state.project) return;
    const copilot = state.copilot;
    const startingConversationId = copilot.conversationId;
    const requestContext = { ...copilot.context };
    const controller = new AbortController();
    copilot.controller = controller;
    copilot.generationConversationId = startingConversationId;
    copilot.requestId = null;
    copilot.status = null;
    copilot.pollAttempts = 0;
    clearCopilotPolling(copilot);
    copilot.loading = true;
    copilot.error = '';
    copilot.notice = '';
    copilot.messages.push({ role: 'user', content });
    input.value = '';
    renderCopilot();
    const timeout = window.setTimeout(() => {
      if (ownsCopilot(copilot, controller)) {
        cancelCopilot();
        state.copilot.error = 'Le délai de réponse est dépassé. Vous pouvez réessayer.';
        renderCopilot();
      }
    }, 180000);
    try {
      const conversationId = await ensureCopilotConversation(copilot, controller, startingConversationId);
      if (!ownsCopilot(copilot, controller)) return;
      copilot.generationConversationId = conversationId;
      const requestId = window.crypto.randomUUID();
      copilot.requestId = requestId;
      const turnPromise = api.askCopilot(conversationId, content, controller.signal, {
        document_id: requestContext.documentId,
        document_version_id: requestContext.versionId,
        analysis_id: requestContext.analysisId,
      }, requestId);
      void pollCopilotStatus(copilot, controller, conversationId, requestId);
      const turn = await turnPromise;
      if (!ownsCopilot(copilot, controller)) return;
      // The response already contains the persisted messages; no unbounded second fetch.
      if (!turn.user_message?.id || !turn.assistant_message?.id) throw new Error('Réponse du Copilote invalide.');
      if (copilot.conversationId === conversationId) {
        copilot.messages = [...copilot.messages.filter((message) => message.id), turn.user_message, turn.assistant_message];
      }
      copilot.unread = !copilot.visible;
    } catch (error) {
      if (!ownsCopilot(copilot, controller)) return;
      if (copilot.conversationId === copilot.generationConversationId || (copilot.generationConversationId === null && copilot.conversationId === null)) {
        copilot.messages = copilot.messages.filter((message) => message.id);
        copilot.error = errorMessage(error);
      }
    } finally {
      window.clearTimeout(timeout);
      clearCopilotPolling(copilot);
      if (ownsCopilot(copilot, controller)) {
        copilot.loading = false;
        copilot.controller = null;
        copilot.generationConversationId = null;
        renderCopilot();
        if (copilot.visible) input.focus();
      }
    }
  }

  async function loadCopilotHistory(conversationId = null) {
    const copilot = state.copilot;
    if (copilot.historyController) copilot.historyController.abort();
    const controller = new AbortController();
    copilot.historyController = controller;
    copilot.historyLoading = true;
    copilot.error = '';
    renderCopilot();
    try {
      if (conversationId) {
        const conversation = await api.conversation(conversationId, controller.signal, 15000);
        if (state.copilot !== copilot || copilot.historyController !== controller || controller.signal.aborted) return;
        if (conversation.subject_type !== 'project' || conversation.subject_id !== copilot.projectId || !Array.isArray(conversation.messages)) {
          throw new Error('Cette conversation ne correspond pas au projet actif.');
        }
        copilot.conversationId = conversation.id;
        copilot.messages = conversation.messages;
        const history = document.querySelector('[data-copilot-history]');
        history.hidden = true;
        copilot.notice = copilot.loading && copilot.generationConversationId !== conversation.id
          ? 'Une autre conversation continue de recevoir une réponse en arrière-plan.'
          : '';
      } else {
        const conversations = await api.conversations(copilot.projectId, controller.signal, 15000);
        if (state.copilot !== copilot || copilot.historyController !== controller || controller.signal.aborted) return;
        const history = document.querySelector('[data-copilot-history]');
        history.innerHTML = conversations.map((item) =>
          `<button type="button" data-copilot-thread="${views.escape(item.id)}"><span>${views.escape(item.title || 'Conversation')}</span><time>${views.date(item.updated_at)}</time></button>`).join('');
        history.hidden = false;
        copilot.notice = conversations.length ? 'Sélectionnez une conversation pour la reprendre.' : 'Aucune conversation enregistrée pour ce projet.';
      }
    } catch (error) {
      if (state.copilot === copilot && copilot.historyController === controller && !controller.signal.aborted) copilot.error = errorMessage(error);
    } finally {
      if (state.copilot === copilot && copilot.historyController === controller && !controller.signal.aborted) {
        copilot.historyLoading = false;
        copilot.historyController = null;
        renderCopilot();
      }
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
    try { return await call(); } catch (error) {
      if (error?.status === 404) return fallback;
      throw error;
    }
  }

  async function loadDocuments(projectId) {
    const documents = await api.projectDocuments(projectId);
    return Promise.all(documents.map(async (document) => ({
      document,
      versions: await safe(() => api.documentVersions(document.id), []),
      analyses: await safe(() => api.documentAnalyses(document.id), []),
    })));
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
      Object.assign(state, { onboarding: null, facts: [], graph: null, graphError: null, assessment: null, assessments: [], roadmap: null, roadmapSourceAssessment: null, documents: [], members: [], frameworks: [], controls: [], score: null, scoreHistory: [], activeFrameworkVersionId: null, selectedControlId: null, selectedControlEvidence: [] });
      return;
    }
    const id = state.project.id;
    const [onboarding, facts, assessment, roadmap, documents] = await Promise.all([
      state.project.project_type === 'idea' ? safe(() => api.getOnboarding(id)) : Promise.resolve(null), safe(() => api.facts(id), []), safe(() => api.latestAssessment(id)), safe(() => api.latestRoadmap(id)), safe(() => loadDocuments(id), []),
    ]);
    let graph = null;
    let graphError = null;
    try { graph = await api.knowledgeGraph(id); } catch (error) { graphError = error?.status === 401 || error?.status === 403 || error?.status === 404 ? 'authorization' : 'technical'; }
    Object.assign(state, { onboarding, facts, graph, graphError, assessment, roadmap, documents });
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
      if (state.tab === 'graph') window.RegBridgeKnowledgeGraph?.mount(workspace.querySelector('[data-project-graph]'), state.graph);
    } else if (state.view === 'regulatory') {
      state.assessments = await safe(() => api.assessments(state.project.id), []);
      if (routeState.version) state.assessment = await safe(() => api.assessment(state.project.id, routeState.version), state.assessment);
      workspace.innerHTML = views.regulatory(state);
    } else if (state.view === 'roadmap') {
      const roadmaps = await api.roadmaps(state.project.id);
      if (routeState.version) state.roadmap = await api.roadmap(state.project.id, routeState.version);
      const assessments = await api.assessments(state.project.id);
      const roadmapAssessment = assessments.find((item) => item.id === state.roadmap?.regulatory_assessment_id);
      state.roadmapSourceAssessment = [...assessments].reverse().find((item) => (
        item.status === 'completed'
        && ['pass', 'pass_with_warnings'].includes(item.verification_verdict)
        && ['obligations', 'recommendations'].some((key) => item.result?.[key]?.length)
      )) || null;
      workspace.innerHTML = views.roadmap({
        ...state,
        assessment: state.roadmapSourceAssessment,
        latestAssessment: state.assessment,
        roadmaps,
        roadmapAssessment,
      });
    }
    else if (state.view === 'documents') {
      state.documents = await loadDocuments(state.project.id);
      workspace.innerHTML = views.documents({ ...state, selectedDocumentId: routeState.document, selectedVersionId: routeState.version });
    } else if (state.view === 'contracts') {
      state.documents = await loadDocuments(state.project.id);
      workspace.innerHTML = views.contracts({ ...state, selectedDocumentId: routeState.document, selectedVersionId: routeState.version, selectedAnalysisId: routeState.analysis });
    } else if (state.view === 'access') {
      state.members = await safe(() => api.members(state.project.id), []);
      workspace.innerHTML = views.access(state);
    } else if (state.view === 'compliance') {
      let complianceError = null;
      state.frameworks = [];
      state.scoreHistory = [];
      if (state.project.project_type !== 'idea') {
        state.frameworks = await safe(() => api.frameworks(), []);
        if (state.activeFrameworkVersionId && !state.frameworks.some((framework) => (framework.versions || []).some((version) => version.id === state.activeFrameworkVersionId && version.status === 'active'))) state.activeFrameworkVersionId = null;
      }
      if (state.project.project_type !== 'idea') {
        try { state.controls = await api.controls(state.project.id); } catch (error) { complianceError = errorMessage(error); }
        state.scoreHistory = await safe(() => api.scoreHistory(state.project.id, state.activeFrameworkVersionId), []);
        // History already provides the immutable calculations in chronological
        // order; an empty history is normal, not a failing latest-score request.
        state.score = state.scoreHistory.at(-1) || null;
        state.selectedControlEvidence = state.selectedControlId ? await safe(() => api.controlEvidence(state.project.id, state.selectedControlId), []) : [];
      }
      workspace.innerHTML = views.compliance({ ...state, error: complianceError });
    } else {
      window.history.replaceState({}, '', routeUrl('dashboard'));
      state.view = 'dashboard';
      workspace.innerHTML = views.dashboard(state);
    }
  }

  async function loadRoute() {
    if (state.documentPollTimer) { window.clearTimeout(state.documentPollTimer); state.documentPollTimer = null; }
    state.documentPollAttempts = 0;
    workspace.setAttribute('aria-busy', 'true');
    workspace.innerHTML = '<div class="workspace-skeleton" aria-label="Chargement"><span></span><span></span><span></span></div>';
    const current = route();
    try {
      await hydrateProjects(current.projectId);
      await loadProjectContext();
      state.copilot.context = current.document && current.version
        ? { documentId: current.document, versionId: current.version, analysisId: current.analysis || null }
        : { documentId: null, versionId: null, analysisId: null };
      await renderView(current);
      renderShell();
      if (['documents', 'contracts'].includes(current.view)) scheduleDocumentPolling();
      if (!state.copilot.visible) workspace.focus({ preventScroll: true });
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
    if (name === 'profile-logout') return logout();
    if (name === 'open-project') return navigate('project');
    if (name === 'open-graph') return navigate('project', { tab: 'graph' });
    if (name === 'open-onboarding') return state.project?.project_type === 'idea' ? navigate('onboarding') : navigate('project');
    if (name === 'open-facts') return navigate('facts');
    if (name === 'open-regulatory') return navigate('regulatory');
    if (name === 'open-roadmap') return navigate('roadmap');
    if (name === 'open-documents') return navigate('documents');
    if (name === 'open-contracts') return navigate('contracts');
    if (name === 'adopt-framework') return perform(target, 'Activation...', () => api.adoptFramework(state.project.id, target.dataset.frameworkVersionId), loadRoute);
    if (name === 'calculate-score') return perform(target, 'Calcul...', () => api.calculateScore(state.project.id, target.dataset.frameworkVersionId || state.activeFrameworkVersionId || null), loadRoute);
    if (name === 'view-control-evidence') {
      state.selectedControlId = target.dataset.controlId;
      state.selectedControlEvidence = await safe(() => api.controlEvidence(state.project.id, state.selectedControlId), []);
      return renderView(route());
    }
    if (name === 'save-control') return saveComplianceControl(target);
    if (name === 'attach-evidence') return attachComplianceEvidence(target);
    if (name === 'revoke-evidence') return perform(target, 'Revocation...', () => api.revokeEvidence(state.project.id, target.dataset.evidenceId), loadRoute);
    if (name === 'project-tab') return navigate('project', { tab: target.dataset.tab });
    if (name === 'select-assessment') return navigate('regulatory', { version: target.dataset.version });
    if (name === 'select-roadmap') return navigate('roadmap', { version: target.dataset.version });
    if (name === 'filter-roadmap') {
      document.querySelectorAll('[data-action="filter-roadmap"]').forEach((item) => item.classList.toggle('active', item === target));
      document.querySelectorAll('[data-roadmap-status]').forEach((item) => { item.hidden = target.dataset.filter !== 'all' && item.dataset.roadmapStatus !== target.dataset.filter; });
      return;
    }
    if (name === 'show-upload') { document.querySelector('[data-form="upload-document"]').hidden = false; return; }
    if (name === 'filter-documents') {
      state.documentFilter = target.dataset.filter || 'all';
      document.querySelectorAll('[data-document-filter]').forEach((item) => item.classList.toggle('active', item === target));
      document.querySelectorAll('[data-document-classification]').forEach((item) => { item.hidden = state.documentFilter !== 'all' && item.dataset.documentClassification !== state.documentFilter; });
      return;
    }
    if (name === 'submit-create') return submitCreate(target);
    if (name === 'submit-onboarding') return submitOnboarding(target);
    if (name === 'infer-facts') {
      if (state.project?.project_type !== 'idea') return showToast('La déduction initiale est réservée aux projets au stade idée.');
      return perform(target, 'Déduction…', () => api.inferFacts(state.project.id), () => navigate('facts'));
    }
    if (name === 'confirm-fact') return perform(target, 'Confirmation…', () => api.confirmFact(state.project.id, target.dataset.factId), loadRoute);
    if (name === 'reject-fact') return perform(target, 'Rejet…', () => api.rejectFact(state.project.id, target.dataset.factId), loadRoute);
    if (name === 'enrich-knowledge') return perform(target, 'Suggestions...', () => api.enrichKnowledgeCandidates(state.project.id), () => navigate('facts'));
    if (name === 'correct-fact') {
      state.editingFactId = target.dataset.factId;
      if (target.dataset.fromCopilot === 'true') return navigate('facts');
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
      return perform(target, 'Génération…', () => api.generateRoadmap(state.project.id), () => navigate('roadmap'));
    }
    if (name === 'complete-roadmap-item') return perform(target, 'Mise à jour…', () => api.updateRoadmapItem(state.project.id, state.roadmap.version, target.dataset.itemId, 'completed'), loadRoute);
    if (name === 'submit-upload') return submitUpload(target);
    if (name === 'show-version-upload') return uploadVersion(target.dataset.documentId);
    if (name === 'open-document') return navigate('documents', { document: target.dataset.documentId, version: target.dataset.versionId });
    if (name === 'open-version') return navigate('documents', { document: target.dataset.documentId, version: target.dataset.versionId });
    if (name === 'download-version') return downloadVersion(target.dataset.documentId, target.dataset.versionId);
    if (name === 'retry-extraction') return retryExtraction(target);
    if (name === 'copilot-document') return analyzeDocumentContract(target);
    if (name === 'copilot-analysis') {
      state.copilot.context = { documentId: target.dataset.documentId, versionId: target.dataset.versionId, analysisId: target.dataset.analysisId };
      return openCopilot();
    }
    if (name === 'open-contract-analysis') return navigate('contracts', { document: target.dataset.documentId, version: target.dataset.versionId, analysis: target.dataset.analysisId });
    if (name === 'focus-contract-clause') {
      const detail = document.querySelector(`#contract-clause-${CSS.escape(target.dataset.clauseId)}`);
      if (detail) { detail.open = true; detail.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' }); detail.focus({ preventScroll: true }); }
      return;
    }
    if (name === 'filter-contract-clauses') {
      const filter = target.dataset.filter || 'all';
      const matches = (item) => filter === 'all' || (filter === 'priority' && ['high', 'critical'].includes(item.dataset.clauseRisk)) || (filter === 'medium' && item.dataset.clauseRisk === 'medium') || (filter === 'missing' && item.dataset.clauseStatus === 'MISSING') || (filter === 'contradictions' && item.dataset.clauseStatus === 'CONTRADICTORY');
      document.querySelectorAll('[data-action="filter-contract-clauses"]').forEach((item) => item.classList.toggle('active', item === target));
      document.querySelectorAll('[data-contract-clause], .contract-clause-navigation button[data-clause-status]').forEach((item) => { item.hidden = !matches(item); });
      return;
    }
    if (name === 'document-contracts') return navigate('contracts', { document: target.dataset.documentId });
    if (name === 'analyze-contract') return analyzeContract(target);
  }

  async function perform(button, label, call, done) {
    setBusy(button, true, label);
    try { const result = await call(); await done(result); }
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
        state.project = await api.getProject(state.project.id);
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

  async function saveComplianceControl(button) {
    const card = button.closest('[data-control-id]');
    if (!card) return;
    const status = card.querySelector('[data-control-status]')?.value;
    const applicability = card.querySelector('[data-control-applicability]')?.value;
    await perform(button, 'Enregistrement...', () => api.updateControl(state.project.id, button.dataset.controlId, { status, applicability }), loadRoute);
  }

  async function attachComplianceEvidence(button) {
    const form = button.closest('[data-evidence-form]');
    const versionId = new FormData(form).get('document_version_id');
    if (!versionId || !state.selectedControlId) return;
    await perform(button, 'Association...', () => api.attachEvidence(state.project.id, { control_id: state.selectedControlId, document_version_id: versionId }), loadRoute);
  }

  async function submitUpload(button) {
    const form = button.closest('form');
    if (!form.reportValidity()) return;
    const data = new FormData(form); const file = data.get('upload');
    formError(form, ''); setBusy(button, true, 'Import…');
    try {
      if (!(file instanceof File) || !file.size) throw new Error('Sélectionnez un fichier non vide.');
      if (!['.pdf', '.docx', '.txt'].includes(file.name.slice(file.name.lastIndexOf('.')).toLowerCase())) throw new Error('Formats acceptés : PDF, DOCX ou TXT.');
      await api.uploadDocument(state.project.id, file, { title: data.get('title'), classification: data.get('classification'), visibility: data.get('visibility') });
      await loadRoute();
    } catch (error) { setBusy(button, false); formError(form, errorMessage(error)); }
  }

  async function uploadVersion(documentId) {
    const input = document.createElement('input'); input.type = 'file'; input.accept = '.pdf,.docx,.txt';
    input.addEventListener('change', async () => {
      if (!input.files[0]) return;
      try { await api.uploadDocumentVersion(documentId, input.files[0]); await loadRoute(); }
      catch (error) { window.alert(errorMessage(error)); }
    });
    input.click();
  }

  async function downloadVersion(documentId, versionId) {
    try {
      const result = await api.downloadDocumentVersion(documentId, versionId);
      const url = URL.createObjectURL(result.blob);
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = result.filename; document.body.append(anchor); anchor.click(); anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { showToast(errorMessage(error)); }
  }

  async function retryExtraction(button) {
    await perform(button, 'Nouvelle tentativeâ€¦', () => api.retryDocumentExtraction(button.dataset.documentId, button.dataset.versionId), loadRoute);
  }

  async function analyzeContract(button) {
    const select = document.querySelector('[data-contract-document]');
    if (!select?.value) { select?.focus(); return; }
    const [documentId, versionId] = select.value.split('|');
    await perform(button, 'Analyse…', () => api.analyzeContract(documentId, versionId), (analysis) => navigate('contracts', { document: documentId, version: versionId, analysis: analysis.id }));
  }

  async function analyzeDocumentContract(button) {
    const documentId = button.dataset.documentId;
    const versionId = button.dataset.versionId;
    if (!documentId || !versionId) return;
    await perform(button, 'Analyse…', () => api.analyzeContract(documentId, versionId), (analysis) => navigate('contracts', { document: documentId, version: versionId, analysis: analysis.id }));
  }

  function scheduleDocumentPolling() {
    const pending = state.documents.some(({ versions }) => versions.some((version) => ['pending', 'processing'].includes(version.extraction_status)));
    if (!pending || state.documentPollAttempts >= 6) return;
    const delays = [2000, 3000, 5000, 5000, 5000, 5000];
    const delay = delays[state.documentPollAttempts++];
    state.documentPollTimer = window.setTimeout(async () => {
      state.documentPollTimer = null;
      if (!['documents', 'contracts'].includes(route().view)) return;
      try {
        state.documents = await loadDocuments(state.project.id);
        const current = route();
        if (current.view === 'documents') workspace.innerHTML = views.documents({ ...state, selectedDocumentId: current.document, selectedVersionId: current.version });
        else workspace.innerHTML = views.contracts({ ...state, selectedDocumentId: current.document, selectedVersionId: current.version, selectedAnalysisId: current.analysis });
        scheduleDocumentPolling();
      } catch { /* the regular route error path handles the next navigation */ }
    }, delay);
  }

  function openSidebar() { document.body.classList.add('sidebar-open'); document.querySelector('[data-open-sidebar]').setAttribute('aria-expanded', 'true'); }
  function closeSidebar() { document.body.classList.remove('sidebar-open'); document.querySelector('[data-open-sidebar]').setAttribute('aria-expanded', 'false'); }
  async function openCopilot() {
    if (!state.project) return;
    state.copilot.visible = true;
    state.copilot.unread = false;
    document.body.classList.add('copilot-open');
    document.querySelector('[data-copilot-drawer]').setAttribute('aria-hidden', 'false');
    document.querySelector('[data-close-copilot]').focus();
    renderCopilot();
    document.querySelector('#copilot-question')?.focus();
  }
  function closeCopilot() {
    state.copilot.visible = false;
    state.copilot.mode = 'docked';
    renderCopilot();
    document.querySelector('[data-open-copilot]').focus();
  }
  function toggleCopilotMode() {
    state.copilot.mode = state.copilot.mode === 'fullscreen' ? 'docked' : 'fullscreen';
    renderCopilot();
    document.querySelector('[data-expand-copilot]').focus();
  }
  function cancelCopilot() {
    const controller = state.copilot.controller;
    if (!controller) return;
    const generationConversationId = state.copilot.generationConversationId;
    controller.abort();
    clearCopilotPolling(state.copilot);
    state.copilot.loading = false;
    state.copilot.controller = null;
    state.copilot.generationConversationId = null;
    state.copilot.requestId = null;
    if (state.copilot.conversationId === generationConversationId || (generationConversationId === null && state.copilot.conversationId === null)) {
      state.copilot.messages = state.copilot.messages.filter((message) => message.id);
      state.copilot.conversationId = null;
    }
    // A disconnected HTTP request may still finish server-side. A new thread
    // prevents its result leaking into the next active exchange; history is kept.
    state.copilot.error = '';
    state.copilot.notice = 'L’attente a été arrêtée. Un traitement déjà commencé peut encore se terminer côté serveur.';
    renderCopilot();
  }

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
    if (event.target.matches('[data-compliance-framework]')) { state.activeFrameworkVersionId = event.target.value || null; state.selectedControlId = null; state.selectedControlEvidence = []; await loadRoute(); }
    if (event.target.matches('[data-roadmap-item]')) {
      const select = event.target;
      const previous = state.roadmap.items.find((item) => item.id === select.dataset.roadmapItem)?.status;
      try { setBusy(select, true); await api.updateRoadmapItem(state.project.id, state.roadmap.version, select.dataset.roadmapItem, select.value); await loadRoute(); }
      catch (error) { select.value = previous; setBusy(select, false); showToast(errorMessage(error)); }
    }
  });
  document.querySelector('[data-open-sidebar]').addEventListener('click', openSidebar);
  document.querySelector('[data-close-sidebar]').addEventListener('click', closeSidebar);
  document.querySelector('[data-sidebar-scrim]').addEventListener('click', closeSidebar);
  document.querySelector('[data-open-copilot]').addEventListener('click', openCopilot);
  document.querySelector('[data-close-copilot]').addEventListener('click', closeCopilot);
  document.querySelector('[data-expand-copilot]').addEventListener('click', toggleCopilotMode);
  document.querySelector('[data-cancel-copilot]').addEventListener('click', cancelCopilot);
  document.querySelector('[data-copilot-form]').addEventListener('submit', (event) => { event.preventDefault(); submitCopilot(event.currentTarget); });
  async function logout() {
    resetCopilotContext(null);
    closeCopilot();
    workspace.innerHTML = '';
    await runtime.logout();
  }
  document.querySelector('[data-logout]').addEventListener('click', logout);
  document.querySelector('[data-new-copilot]').addEventListener('click', newCopilotConversation);
  document.querySelector('[data-show-copilot-history]').addEventListener('click', () => loadCopilotHistory());
  document.querySelector('[data-copilot-history]').addEventListener('click', (event) => {
    const thread = event.target.closest('[data-copilot-thread]');
    if (thread) loadCopilotHistory(thread.dataset.copilotThread);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Tab' && state.copilot.visible && (state.copilot.mode === 'fullscreen' || window.matchMedia('(max-width: 600px)').matches)) {
      const controls = [...document.querySelector('[data-copilot-drawer]').querySelectorAll('button, select, textarea, a[href], summary')].filter((node) => !node.disabled && node.getClientRects().length);
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
    if (event.key !== 'Escape') return;
    if (state.copilot.visible) {
      if (state.copilot.mode === 'fullscreen') toggleCopilotMode();
      else closeCopilot();
    }
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
