(function createEntrepreneurViews() {
  'use strict';

  const labels = {
    dashboard: 'Tableau de bord', project: 'Mon projet', onboarding: 'Onboarding', facts: 'Faits',
    regulatory: 'Réglementation', roadmap: 'Roadmap de lancement', documents: 'Documents',
    contracts: 'Contrats', access: 'Équipe & accès', compliance: 'Conformité', create: 'Créer un projet', profile: 'Profil',
  };
  const lifecycle = { idea: 'Projet idée', startup_in_creation: 'Startup en création', existing_startup: 'Startup existante' };
  const statuses = { pending: 'À faire', in_progress: 'En cours', completed: 'Terminé', skipped: 'Ignoré' };
  const factDomains = { activity: 'Activité', sector: 'Secteur', technology: 'Technologie', data: 'Données', market: 'Marché', location: 'Localisation' };

  function escape(value) {
    return String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character]);
  }

  function date(value) {
    if (!value) return 'Date indisponible';
    return new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium' }).format(new Date(value));
  }

  function pageHeader(eyebrow, title, description, actions = '') {
    return `<header class="page-header"><div><p class="eyebrow">${escape(eyebrow)}</p><h1>${escape(title)}</h1>${description ? `<p>${escape(description)}</p>` : ''}</div>${actions ? `<div class="page-actions">${actions}</div>` : ''}</header>`;
  }

  function button(label, action, kind = 'primary', attrs = '') {
    return `<button class="app-button app-button-${kind}" type="button" data-action="${escape(action)}" ${attrs}>${escape(label)}</button>`;
  }

  function emptyState(title, copy, action = '') {
    return `<section class="empty-state"><span class="empty-node" aria-hidden="true">RB</span><h2>${escape(title)}</h2><p>${escape(copy)}</p>${action}</section>`;
  }

  function inlineError(message) {
    return `<section class="inline-error" role="alert"><strong>Chargement impossible</strong><p>${escape(message)}</p>${button('Réessayer', 'retry', 'secondary')}</section>`;
  }

  function badge(value, type = '') {
    return `<span class="status-badge ${type ? `status-${escape(type)}` : ''}">${escape(value)}</span>`;
  }

  function progress(roadmap) {
    if (!roadmap || !roadmap.items?.length) return { complete: 0, total: 0, percent: 0 };
    const complete = roadmap.items.filter((item) => item.status === 'completed').length;
    return { complete, total: roadmap.items.length, percent: Math.round((complete / roadmap.items.length) * 100) };
  }

  function dashboard({ project, onboarding, facts = [], assessment, roadmap }) {
    if (!project) {
      return `${pageHeader('ESPACE ENTREPRENEUR', 'Transformez votre idée en parcours concret.', 'Créez votre premier projet pour identifier les informations utiles, préparer vos démarches et suivre votre lancement.')}
        <section class="surface dashboard-onboarding"><div><p class="eyebrow">VOTRE PREMIER PROJET</p><h2>Commencez avec une description simple.</h2><p>RegBridge vous accompagne ensuite pour préciser votre situation, vérifier les informations clés et construire votre roadmap.</p>${button('Créer mon premier projet', 'create-project')}</div><ol class="journey-rail"><li><b>01</b><span>Décrivez votre activité</span></li><li><b>02</b><span>Vérifiez les informations clés</span></li><li><b>03</b><span>Construisez votre roadmap</span></li></ol></section>`;
    }
    const stats = progress(roadmap);
    const next = roadmap?.items?.find((item) => !['completed', 'skipped'].includes(item.status));
    const pendingFacts = facts.filter((fact) => fact.status === 'pending_confirmation').length;
    const confirmedFacts = facts.filter((fact) => ['confirmed', 'corrected'].includes(fact.status)).length;
    const nextAction = next
      ? `<article class="surface primary-task"><div class="card-kicker"><span>PROCHAINE ACTION</span>${badge(next.item_type, next.item_type)}</div><h2>${escape(next.title)}</h2><p>${escape(next.justification)}</p><div class="card-actions">${button('Voir le détail', 'open-roadmap', 'secondary')}${next.status !== 'completed' ? button('Marquer comme terminé', 'complete-roadmap-item', 'primary', `data-item-id="${escape(next.id)}"`) : ''}</div></article>`
      : `<article class="surface primary-task"><div class="card-kicker"><span>PROCHAINE ACTION</span></div><h2>${roadmap ? 'Toutes les étapes actives sont traitées.' : 'Construisez votre parcours de lancement.'}</h2><p>${roadmap ? 'Consultez la roadmap pour vérifier les éléments ignorés ou terminés.' : 'Générez d’abord une évaluation réglementaire, puis votre roadmap.'}</p><div class="card-actions">${button(assessment ? 'Ouvrir la roadmap' : 'Ouvrir la réglementation', assessment ? 'open-roadmap' : 'open-regulatory')}</div></article>`;
    return `${pageHeader(lifecycle[project.project_type] || project.project_type, project.display_name || 'Projet sans nom', project.raw_description || 'Description non renseignée.', `${button(onboarding?.status === 'complete' ? 'Voir mon projet' : 'Continuer mon projet', onboarding?.status === 'complete' ? 'open-project' : 'open-onboarding')}${button('Voir la roadmap', 'open-roadmap', 'secondary')}`)}
      <section class="dashboard-grid">
        <article class="surface launch-progress"><div class="card-kicker"><span>PROGRESSION DU LANCEMENT</span></div>${stats.total ? `<strong>${stats.complete} / ${stats.total} étapes terminées</strong><div class="progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="${stats.total}" aria-valuenow="${stats.complete}"><span style="width:${stats.percent}%"></span></div><small>${next ? `Prochaine : ${escape(next.title)}` : 'Aucune prochaine étape active'}</small>` : `<strong>Roadmap non générée</strong><p>Une évaluation réglementaire est nécessaire avant la génération.</p>`}</article>
        ${nextAction}
      </section>
      <section class="secondary-grid" aria-label="État du projet">
        <button class="surface summary-card" data-action="open-facts"><span>PROJET</span><strong>Faits du projet</strong><p>${confirmedFacts} confirmé${confirmedFacts > 1 ? 's' : ''} · ${pendingFacts} en attente</p></button>
        <button class="surface summary-card" data-action="open-regulatory"><span>RÉGLEMENTATION</span><strong>Évaluation réglementaire</strong><p>${assessment ? `Version ${assessment.version} · ${escape(assessment.status)}` : 'Aucune évaluation'}</p></button>
        <button class="surface summary-card" data-action="open-documents"><span>DOCUMENTS</span><strong>Documents du projet</strong><p>Ouvrir le registre autorisé</p></button>
        <button class="surface summary-card" data-action="open-contracts"><span>CONTRATS</span><strong>Analyses contractuelles</strong><p>Sur versions exactes et immuables</p></button>
      </section>`;
  }

  function createProject() {
    const context = [
      ['01', 'Activité', 'Ce que votre projet propose réellement.'],
      ['02', 'Secteur', 'Le domaine économique ou réglementé concerné.'],
      ['03', 'Technologie', 'Les technologies qui peuvent créer des obligations particulières.'],
      ['04', 'Données', 'Les catégories de données utilisées ou traitées.'],
      ['05', 'Marché', 'Les utilisateurs, clients ou secteurs ciblés.'],
      ['06', 'Localisation', 'Le territoire dans lequel l’activité sera exercée.'],
    ];
    return `${pageHeader('NOUVEAU PROJET', 'Parlez-nous de votre projet.', 'Décrivez votre activité en quelques phrases. RegBridge vous posera ensuite uniquement les questions utiles pour préparer votre lancement en France.')}
      <section class="create-project-grid">
        <ol class="step-list create-steps" aria-label="Progression du parcours"><li class="active"><b>01</b><span><strong>Décrire</strong><small>Votre activité</small></span></li><li><b>02</b><span><strong>Préciser</strong><small>Les informations utiles à votre situation</small></span></li><li><b>03</b><span><strong>Vérifier</strong><small>Les faits qui serviront à l’analyse</small></span></li></ol>
        <form class="surface app-form create-form" data-form="create-project">
          <label for="project-name">Nom du projet<input id="project-name" name="display_name" maxlength="255" autocomplete="organization" placeholder="Ex. EcoTrack" aria-describedby="project-name-help" required></label><small id="project-name-help">Utilisez le nom que vous employez pour identifier votre projet. Vous pourrez le modifier plus tard.</small>
          <label for="project-description">Décrivez votre activité<textarea id="project-description" name="raw_description" rows="9" placeholder="Ex. Nous développons une plateforme SaaS destinée aux PME françaises pour suivre leurs consommations énergétiques. Le service analyse les données transmises par les entreprises et génère des indicateurs de suivi." aria-describedby="project-description-help project-guidance" required></textarea></label>
          <small id="project-description-help">Expliquez simplement ce que vous souhaitez proposer, à qui, et comment votre service ou produit fonctionne.</small>
          <div class="description-guidance" id="project-guidance"><span>Essayez de préciser, si vous les connaissez déjà :</span><ul><li>Activité</li><li>Clients ou utilisateurs</li><li>Technologie</li><li>Données traitées</li><li>Marché visé</li></ul></div>
          <div class="data-callout"><p class="eyebrow">POURQUOI CES QUESTIONS ?</p><p>RegBridge collecte uniquement les informations utiles pour contextualiser vos démarches et obligations.</p><small>Vous pourrez vérifier et corriger les informations retenues avant qu’elles soient utilisées pour une analyse.</small></div>
          <div class="form-error" data-form-error role="alert" hidden></div>${button('Créer le projet et continuer', 'submit-create')}<small class="resume-note">Vous pourrez interrompre le parcours et le reprendre plus tard.</small>
        </form>
        <details class="surface create-context" open><summary id="create-context-title">Ce que nous chercherons à comprendre</summary><ol aria-labelledby="create-context-title">${context.map(([number, title, copy]) => `<li><b>${number}</b><div><strong>${title}</strong><p>${copy}</p></div></li>`).join('')}</ol></details>
      </section>`;
  }

  function onboarding({ project, onboarding }) {
    const questions = onboarding?.next_questions || [];
    if (!questions.length) return `${pageHeader('ONBOARDING', 'Informations confirmées.', 'Vous avez répondu à toutes les questions utiles pour cette étape.')}${emptyState('Cette étape est terminée', 'Vous pouvez maintenant vérifier les informations retenues pour votre projet.', button('Vérifier les informations', 'open-facts'))}`;
    const fields = { activity: 'activity', sector: 'sector', technology: 'technology', data: 'data', market: 'target_market', location: 'location' };
    const question = questions[0];
    const field = fields[question.field];
    return `${pageHeader('PRÉCISER VOTRE PROJET', project.display_name || 'Votre projet', 'Répondez uniquement aux questions utiles à votre situation. Vos réponses sont enregistrées pour reprendre plus tard.')}
      <section class="split-workspace"><ol class="step-list" aria-label="Questions restantes">${questions.map((item, index) => `<li class="${index === 0 ? 'active' : ''}"><b>${String(index + 1).padStart(2, '0')}</b> ${escape(factDomains[item.field] || item.field)}</li>`).join('')}</ol>
      <form class="surface app-form" data-form="onboarding" data-field="${escape(question.field)}"><p class="form-step">QUESTION SUIVANTE</p><h2>${escape(question.question)}</h2><label>${escape(factDomains[question.field] || question.field)}<textarea name="value" rows="6" required>${escape(project[field] || '')}</textarea></label><label class="confirm-check"><input type="checkbox" name="confirm" required> Je confirme cette information</label><div class="form-error" data-form-error role="alert" hidden></div>${button('Enregistrer et continuer', 'submit-onboarding')}</form></section>`;
  }

  function factsSection(facts, project, editingFactId) {
    const active = facts.filter((fact) => fact.status !== 'deleted');
    const declaredValues = [
      ['activity', project.activity], ['sector', project.sector], ['technology', project.technology],
      ['data', project.data], ['market', project.target_market], ['location', project.location],
    ].filter(([domain, value]) => value && project.confirmed_fields?.includes(domain));
    const declared = [
      ...declaredValues.map(([domain, value]) => ({ id: `declared-${domain}`, domain, value, origin: 'user_declared', status: 'confirmed', provenance: { source_field: domain } })),
      ...active.filter((fact) => fact.origin === 'user_declared'),
    ];
    const inferred = active.filter((fact) => fact.origin === 'inferred');
    if (!declared.length && !inferred.length) return emptyState('Aucune information à vérifier', 'Demandez à RegBridge d’identifier les informations utiles à partir de vos réponses.', button('Identifier les informations', 'infer-facts'));
    const cards = (items, inferredGroup) => items.length ? `<div class="fact-list">${items.map((fact) => {
      const editing = inferredGroup && editingFactId === fact.id;
      const editor = editing ? `<form class="fact-editor" data-form="correct-fact" data-fact-id="${escape(fact.id)}"><label>Valeur corrigée<input name="value" value="${escape(fact.value)}" maxlength="2000" required></label><div class="form-error" data-form-error role="alert" hidden></div><div class="card-actions">${button('Enregistrer', 'submit-fact-correction')}${button('Annuler', 'cancel-fact-correction', 'text')}</div></form>` : '';
      const actions = inferredGroup && fact.status === 'pending_confirmation' && !editing ? `<div class="card-actions">${button('Confirmer', 'confirm-fact', 'primary', `data-fact-id="${escape(fact.id)}"`)}${button('Corriger', 'correct-fact', 'secondary', `data-fact-id="${escape(fact.id)}"`)}${button('Rejeter', 'reject-fact', 'text', `data-fact-id="${escape(fact.id)}"`)}</div>` : '';
      return `<article class="surface fact-card"><div class="card-kicker"><span>${escape(factDomains[fact.domain] || fact.domain)}</span>${badge(fact.status === 'pending_confirmation' ? 'À confirmer' : fact.status, fact.status)}</div><h3>${escape(fact.value)}</h3><dl><div><dt>Source</dt><dd>${escape(fact.provenance?.source_field || 'Information confirmée')}</dd></div>${fact.provenance?.excerpt ? `<div><dt>Extrait</dt><dd>“${escape(fact.provenance.excerpt)}”</dd></div>` : ''}${fact.uncertainty ? `<div><dt>Incertitude</dt><dd>${escape(fact.uncertainty)}</dd></div>` : ''}</dl>${editor}${actions}</article>`;
    }).join('')}</div>` : `<p class="quiet-empty">Aucun fait dans cette catégorie.</p>`;
    return `<section class="section-block"><div class="section-heading"><h2>Déclaré par vous</h2></div>${cards(declared, false)}</section><section class="section-block"><div class="section-heading"><h2>Déduit à partir de vos réponses</h2>${button('Actualiser les informations', 'infer-facts', 'secondary')}</div>${cards(inferred, true)}</section>`;
  }

  function project({ project, facts, history, editingFactId, tab = 'overview' }) {
    const tabs = `<nav class="tabs" aria-label="Sections du projet">${['overview', 'facts', 'history'].map((name) => `<button class="${tab === name ? 'active' : ''}" data-action="project-tab" data-tab="${name}">${{ overview: 'Vue d’ensemble', facts: 'Faits', history: 'Historique' }[name]}</button>`).join('')}</nav>`;
    let content;
    if (tab === 'facts') content = factsSection(facts, project, editingFactId);
    else if (tab === 'history') content = history?.length ? `<div class="timeline">${history.map((item) => `<article><time>${date(item.created_at)}</time><strong>${escape(lifecycle[item.from_type] || item.from_type)} → ${escape(lifecycle[item.to_type] || item.to_type)}</strong></article>`).join('')}</div>` : emptyState('Aucune transition', 'Le cycle de vie du projet n’a pas encore changé.');
    else content = `<section class="detail-grid">${[['Activité', project.activity], ['Secteur', project.sector], ['Technologie', project.technology], ['Données', project.data], ['Marché', project.target_market], ['Localisation', project.location]].map(([term, value]) => `<article class="surface detail-card"><span>${escape(term)}</span><strong>${escape(value || 'Non renseigné')}</strong></article>`).join('')}</section><section class="surface lifecycle-card"><div><p class="eyebrow">CYCLE DE VIE</p><h2>${escape(lifecycle[project.project_type] || project.project_type)}</h2><p>Vous décidez quand votre projet est prêt à passer à l’étape suivante.</p></div>${project.project_type === 'idea' ? button('Passer en startup en création', 'transition-project', 'secondary') : ''}</section>`;
    const header = tab === 'facts'
      ? pageHeader('VÉRIFICATION', 'Vérifiez ce que RegBridge a compris.', 'Avant toute analyse, confirmez ou corrigez les informations retenues à partir de vos réponses.')
      : pageHeader(lifecycle[project.project_type] || project.project_type, project.display_name || 'Projet sans nom', project.raw_description || 'Description non renseignée.');
    return `${header}${tabs}${content}`;
  }

  function conclusions(title, items, type) {
    return `<section class="section-block"><div class="section-heading"><h2>${escape(title)}</h2><span>${items.length}</span></div>${items.length ? `<div class="conclusion-list">${items.map((item) => `<article class="surface conclusion-card">${badge(type, type)}<h3>${escape(item.statement)}</h3>${item.explanation ? `<p>${escape(item.explanation)}</p>` : ''}${item.source_refs?.length ? `<div class="sources"><strong>Sources</strong>${item.source_refs.map((source) => `<span>${escape(source)}</span>`).join('')}</div>` : ''}</article>`).join('')}</div>` : '<p class="quiet-empty">Aucun élément dans cette catégorie.</p>'}</section>`;
  }

  function regulatory({ assessment, versions, facts = [] }) {
    const pending = facts.filter((fact) => fact.status === 'pending_confirmation').length;
    const actions = pending
      ? button('Vérifier les informations', 'open-facts', 'secondary')
      : (assessment ? button('Créer une nouvelle version', 'generate-assessment', 'secondary') : button('Générer l’évaluation', 'generate-assessment'));
    const gate = pending ? `<section class="surface analysis-gate"><strong>Certaines informations doivent encore être vérifiées.</strong><p>Confirmez, corrigez ou rejetez les faits en attente avant de lancer une analyse.</p>${button('Vérifier les informations', 'open-facts')}</section>` : '';
    if (!assessment) return `${pageHeader('RÉGLEMENTATION', 'Évaluation réglementaire', 'Les conclusions seront générées à partir des faits autorisés et confirmés.', actions)}${gate || emptyState('Aucune évaluation', 'Votre projet doit d’abord disposer de faits suffisamment renseignés et confirmés.', button('Examiner les faits', 'open-facts', 'secondary'))}`;
    return `${pageHeader('ÉVALUATION RÉGLEMENTAIRE', `Version ${assessment.version}`, `${date(assessment.created_at)} · ${assessment.status}`, actions)}${gate}
      <div class="version-strip" aria-label="Versions">${versions.map((item) => `<button class="${item.version === assessment.version ? 'active' : ''}" data-action="select-assessment" data-version="${item.version}">v${item.version}${item.version === assessment.version ? ' actuelle' : ''}</button>`).join('')}</div>
      <p class="trace-copy">Analyse basée sur un instantané immuable des informations confirmées pour cette version.</p>
      ${assessment.result.answer ? `<section class="surface assessment-summary"><p>${escape(assessment.result.answer)}</p>${assessment.result.sources?.length ? `<div class="sources"><strong>Sources</strong>${assessment.result.sources.map((source) => `<span>${escape(source)}</span>`).join('')}</div>` : ''}</section>` : ''}
      ${conclusions('Obligations', assessment.result.obligations || [], 'obligation')}${conclusions('Recommandations', assessment.result.recommendations || [], 'recommendation')}${conclusions('Incertitudes', assessment.result.uncertainties || [], 'uncertainty')}`;
  }

  function roadmap({ roadmap, assessment }) {
    if (!roadmap) return `${pageHeader('ROADMAP DE LANCEMENT', 'Préparez votre lancement.', 'Les étapes sont dérivées de la dernière évaluation réglementaire.', assessment ? button('Générer la roadmap', 'generate-roadmap') : '')}${emptyState('Roadmap non générée', assessment ? 'Générez une roadmap depuis l’évaluation réglementaire disponible.' : 'Générez d’abord une évaluation réglementaire pour construire votre roadmap.', button('Ouvrir la réglementation', 'open-regulatory', 'secondary'))}`;
    const stats = progress(roadmap);
    const filters = ['all', 'pending', 'in_progress', 'completed'];
    return `${pageHeader('ROADMAP DE LANCEMENT', `Version ${roadmap.version}`, 'Les étapes nécessaires ou recommandées pour préparer votre lancement en France.', button('Nouvelle version', 'generate-roadmap', 'secondary'))}
      <section class="surface roadmap-progress"><div><strong>${stats.complete} / ${stats.total} étapes terminées</strong><small>Votre progression est enregistrée</small></div><div class="progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="${stats.total}" aria-valuenow="${stats.complete}"><span style="width:${stats.percent}%"></span></div></section>
      <div class="filter-pills" data-roadmap-filters>${filters.map((filter) => `<button class="${filter === 'all' ? 'active' : ''}" data-action="filter-roadmap" data-filter="${filter}">${{ all: 'Tous', pending: 'À faire', in_progress: 'En cours', completed: 'Terminés' }[filter]}</button>`).join('')}</div>
      <div class="roadmap-list">${roadmap.items.map((item) => `<details class="surface roadmap-item" data-roadmap-status="${escape(item.status)}"><summary><span class="check-state" aria-hidden="true">${item.status === 'completed' ? '✓' : '○'}</span><span><strong>${escape(item.title)}</strong><small>${escape(item.item_type)}</small></span>${badge(statuses[item.status] || item.status, item.status)}</summary><div class="roadmap-detail"><p>${escape(item.justification)}</p><dl><div><dt>Évaluation</dt><dd>v${escape(assessment?.version || '—')}</dd></div><div><dt>Traçabilité</dt><dd>${item.source_conclusion_refs?.length ? item.source_conclusion_refs.map(escape).join(', ') : 'Référence non exposée'}</dd></div></dl><label>Statut<select data-roadmap-item="${escape(item.id)}"><option value="pending" ${item.status === 'pending' ? 'selected' : ''}>À faire</option><option value="in_progress" ${item.status === 'in_progress' ? 'selected' : ''}>En cours</option><option value="completed" ${item.status === 'completed' ? 'selected' : ''}>Terminé</option><option value="skipped" ${item.status === 'skipped' ? 'selected' : ''}>Ignoré</option></select></label></div></details>`).join('')}</div>`;
  }

  function documents({ documents }) {
    return `${pageHeader('DOCUMENTS', 'Documents du projet', 'Les fichiers restent versionnés et les versions originales ne sont jamais écrasées.', button('Importer un document', 'show-upload'))}
      <form class="surface upload-form" data-form="upload-document" hidden><label>Fichier PDF, DOCX ou TXT<input type="file" name="upload" accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain" required></label><label>Titre<input name="title" maxlength="255"></label><div class="form-row"><label>Classification<select name="classification"><option value="confidential">Confidentiel</option><option value="internal">Interne</option><option value="public">Public</option><option value="highly_confidential">Hautement confidentiel</option></select></label><label>Visibilité<select name="visibility"><option value="private">Privé</option><option value="project_members">Membres du projet</option><option value="shared">Partagé</option></select></label></div><div class="form-error" data-form-error role="alert" hidden></div>${button('Importer', 'submit-upload')}</form>
      <p class="contract-note">Cette vue affiche les documents importés depuis ce navigateur. Vos droits d’accès sont vérifiés à chaque ouverture.</p>
      ${documents.length ? `<div class="document-list">${documents.map(({ document, versions }) => `<article class="surface document-row"><div><span>${escape(document.document_type)}</span><h2>${escape(document.title)}</h2><p>${badge(document.classification)} ${badge(document.visibility)} ${badge(document.processing_status)}</p></div><div class="document-meta"><strong>${versions[0] ? `Version ${versions[0].version_number}` : 'Version courante non détaillée'}</strong><small>${versions[0] ? `${escape(versions[0].original_filename)} · ${date(versions[0].created_at)}` : 'Historique complet indisponible via le contrat actuel'}</small></div><div class="row-actions">${button('Nouvelle version', 'show-version-upload', 'secondary', `data-document-id="${escape(document.id)}"`)}${button('Contrats', 'document-contracts', 'text', `data-document-id="${escape(document.id)}"`)}</div></article>`).join('')}</div>` : emptyState('Aucun document importé', 'Importez un fichier pris en charge. Aucun document de démonstration n’est affiché.')}`;
  }

  function contracts({ documents }) {
    const rows = documents.flatMap(({ document, versions, analyses }) => (analyses || []).map((analysis) => ({ document, versions, analysis })));
    return `${pageHeader('CONTRATS', 'Analysez vos documents contractuels.', 'L’analyse assistée conserve le fichier original et ne remplace pas une validation juridique professionnelle.')}
      <section class="surface contract-picker"><div><h2>Analyser une version</h2><p>Sélectionnez une version exacte déjà importée.</p></div>${documents.length ? `<select data-contract-document aria-label="Document à analyser"><option value="">Choisir un document</option>${documents.map(({ document, versions }) => versions[0] ? `<option value="${escape(document.id)}|${escape(versions[0].id)}">${escape(document.title)} · v${versions[0].version_number}</option>` : '').join('')}</select>${button('Analyser', 'analyze-contract')}` : button('Importer un document', 'open-documents', 'secondary')}</section>
      <p class="contract-note">Analyse assistée — ne remplace pas une validation juridique professionnelle. Aucun changement automatique n’est appliqué au document.</p>
      ${rows.length ? `<div class="analysis-list">${rows.map(({ document, analysis }) => `<article class="surface analysis-card"><div class="card-kicker"><span>${escape(document.title)}</span>${badge(analysis.status)}</div><h2>Analyse du ${date(analysis.created_at)}</h2><p>Analyse conservée avec la version exacte du document utilisée au moment du lancement.</p>${analysis.observations?.length ? `<h3>Observations liées aux preuves</h3>${analysis.observations.map((item) => `<blockquote>“${escape(item.source_quote)}”<cite>${escape(item.suggested_category)}</cite></blockquote>`).join('')}` : '<p>Aucune observation explicite retournée.</p>'}<div class="limitations">${(analysis.limitations || []).map((item) => `<span>${escape(item)}</span>`).join('')}</div></article>`).join('')}</div>` : emptyState('Aucun contrat analysé', 'Importez un document puis choisissez sa version exacte pour lancer une analyse.')}`;
  }

  function access({ members }) {
    return `${pageHeader('ÉQUIPE & ACCÈS', 'Membres du projet', 'Les rôles de projet définissent ce que chaque membre peut faire dans cet espace.')}${members.length ? `<div class="member-list">${members.map((member) => { const name = [member.first_name, member.last_name].filter(Boolean).join(' ') || 'Membre du projet'; const initials = name === 'Membre du projet' ? 'MB' : name.slice(0, 2).toUpperCase(); return `<article class="surface member-row"><span class="member-avatar" aria-hidden="true">${escape(initials)}</span><div><strong>${escape(name)}</strong><small>${escape(member.status)}</small></div>${badge(member.member_role)}</article>`; }).join('')}</div>` : emptyState('Aucun membre visible', 'Aucun autre membre n’est actuellement associé à ce projet.')}`;
  }

  function compliance({ project, controls, score, error }) {
    if (project.project_type === 'idea') return `${pageHeader('CONFORMITÉ', 'Disponible aux étapes startup.', 'La conformité structurée s’active pour une startup en création ou existante.')}${emptyState('Non applicable à ce stade', 'Faites évoluer explicitement le projet lorsque les conditions métier sont réunies.')}`;
    if (error) return inlineError(error);
    return `${pageHeader('CONFORMITÉ', 'Contrôles et preuves', 'Les données ci-dessous proviennent du référentiel adopté pour ce projet.')}${score ? `<section class="surface score-card"><div><p class="eyebrow">INDICATEUR DE MATURITÉ REGBRIDGE</p><strong>${score.score == null ? 'Non calculable' : `${escape(score.score)} %`}</strong><p>Ce score n’est pas une certification officielle.</p></div><dl><div><dt>Méthode</dt><dd>${escape(score.method_key)} · ${escape(score.method_version)}</dd></div><div><dt>Calcul</dt><dd>${date(score.calculated_at)}</dd></div><div><dt>Contrôles</dt><dd>${escape(score.numerator)} / ${escape(score.denominator)}</dd></div></dl></section>` : '<p class="contract-note">Aucun score de maturité calculé.</p>'}${controls.length ? `<div class="control-list">${controls.map((control) => `<article class="surface control-card"><div class="card-kicker"><span>${escape(control.definition?.category || 'CONTRÔLE')}</span>${badge(control.status)}</div><h2>${escape(control.definition?.title || control.control_definition_id)}</h2><p>${escape(control.definition?.description || control.notes || 'Aucune description.')}</p></article>`).join('')}</div>` : emptyState('Aucun contrôle', 'Aucun référentiel actif ne fournit de contrôle pour ce projet.')}`;
  }

  function profile({ user, project, roadmap }) {
    const initials = user.email.slice(0, 2).toUpperCase();
    const next = roadmap?.items?.find((item) => !['completed', 'skipped'].includes(item.status));
    const roleLabels = { entrepreneur: 'Entrepreneur', investor: 'Investisseur', researcher: 'Chercheur' };
    const projectJourney = project
      ? `<article class="surface profile-journey"><p class="eyebrow">VOTRE PARCOURS</p><span class="status-badge">${escape(lifecycle[project.project_type] || project.project_type)}</span><h2>${escape(project.display_name || 'Projet sans nom')}</h2><p>${next ? `Prochaine étape : ${escape(next.title)}` : 'Ouvrez votre projet pour poursuivre les informations ou les démarches en cours.'}</p>${button('Ouvrir le projet', 'open-project')}</article>`
      : `<article class="surface profile-journey"><p class="eyebrow">VOTRE PARCOURS</p><h2>Votre premier projet commence ici.</h2><p>Décrivez votre activité pour construire un parcours adapté à votre lancement en France.</p>${button('Créer un projet', 'create-project')}<ul class="journey-points"><li>Projet structuré</li><li>Démarches adaptées</li><li>Historique conservé</li></ul></article>`;
    return `${pageHeader('PROFIL', 'Votre espace RegBridge.', 'Gérez votre identité, vos rôles et les espaces auxquels vous avez accès.')}
      <section class="profile-grid">
        <article class="surface profile-identity"><p class="eyebrow">IDENTITÉ</p><div class="identity-heading"><span class="profile-avatar" aria-hidden="true">${escape(initials)}</span><div><h2>${escape(user.email)}</h2><p>Votre identité de connexion RegBridge</p></div></div><div class="profile-roles"><h3>RÔLES REGBRIDGE</h3><p>Vos rôles déterminent les espaces de travail disponibles.</p><div>${user.roles.map((role) => badge(roleLabels[role] || role)).join('')}</div></div><a class="app-button app-button-secondary" href="/onboarding/roles/">Gérer mes rôles</a></article>
        ${projectJourney}
        <article class="surface profile-workspace"><p class="eyebrow">ESPACE ACTIF</p><h2>Entrepreneur</h2><p>Créez un projet, préparez votre lancement et suivez vos démarches.</p>${user.roles.length > 1 ? '<a class="text-action" href="/workspace/">Changer d’espace</a>' : ''}</article>
        <article class="surface profile-access"><p class="eyebrow">ACCÈS AU COMPTE</p><h2>Connexion sécurisée</h2><p>Votre accès est protégé par le service d’identité configuré pour RegBridge.</p>${button('Se déconnecter', 'profile-logout', 'secondary')}</article>
      </section>`;
  }

  window.RegBridgeEntrepreneurViews = Object.freeze({ labels, lifecycle, escape, date, badge, button, dashboard, createProject, onboarding, project, regulatory, roadmap, documents, contracts, access, compliance, profile, inlineError, progress });
})();
