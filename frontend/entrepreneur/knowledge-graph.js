(function createProjectKnowledgeGraph() {
  'use strict';

  const TYPE_LABELS = {
    PROJECT: 'Projet', SECTOR: 'Secteur', MARKET: 'Marché', GEOGRAPHY: 'Géographie',
    TECHNOLOGY: 'Technologie', DATA_CATEGORY: 'Données', PROVIDER: 'Fournisseur', BUSINESS_MODEL: 'Modèle économique', LIFECYCLE_STAGE: 'Cycle de vie', DOCUMENT: 'Document',
    REGULATORY_ASSESSMENT: 'Évaluation réglementaire', REGULATORY_DOMAIN: 'Réglementation', EVIDENCE: 'Source vérifiée',
  };
  // The API deliberately keeps canonical relation/status values for clients
  // and diagnostics.  Normal product UI uses this one presentation mapping.
  const RELATION_LABELS = {
    HAS_SECTOR: 'Secteur', TARGETS_MARKET: 'Marché cible', OPERATES_IN: 'Localisation / opère dans',
    USES_TECHNOLOGY: 'Utilise la technologie', PROCESSES_DATA: 'Traite les données',
    USES_PROVIDER: 'Utilise le fournisseur', HAS_BUSINESS_MODEL: 'Modèle économique', HAS_STAGE: 'Cycle de vie',
    HAS_DOCUMENT: 'Document', HAS_REGULATORY_ASSESSMENT: 'Évaluation réglementaire',
    AFFECTED_BY: 'Domaine concerné', SUPPORTED_BY: 'Étaye par', DERIVED_FROM: 'Dérivé de',
  };
  const STATUS_LABELS = { CONFIRMED: 'Confirmé', VERIFIED: 'Vérifié' };
  const VALUE_LABELS = {
    idea: 'Projet idée', startup_in_creation: 'Startup en création', existing_startup: 'Startup existante',
    mvp: 'MVP', pre_revenue: 'Pré-revenu', confirmed: 'Confirmé', pending_confirmation: 'À confirmer',
  };
  const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[c]);

  function pointFor(index, total) {
    const theta = index * 2.399963229728653;
    const y = 1 - ((index + 0.5) / Math.max(total, 1)) * 2;
    const radius = Math.sqrt(1 - y * y);
    return { x: Math.cos(theta) * radius, y, z: Math.sin(theta) * radius };
  }
  function rotate(point, yaw, pitch) {
    const x = point.x * Math.cos(yaw) - point.z * Math.sin(yaw);
    const z = point.x * Math.sin(yaw) + point.z * Math.cos(yaw);
    return { x, y: point.y * Math.cos(pitch) - z * Math.sin(pitch), z: point.y * Math.sin(pitch) + z * Math.cos(pitch) };
  }

  function mount(root, graph) {
    if (!root || !graph?.nodes?.length) return;
    const types = [...new Set(graph.nodes.map((node) => node.type))];
    root.innerHTML = `<div class="graph-toolbar"><button type="button" data-graph-reset>Réinitialiser la vue</button><span>Faites glisser pour orienter · molette pour zoomer</span></div><div class="graph-filter" role="group" aria-label="Filtrer le graphe">${types.map((type) => `<button type="button" data-graph-filter="${esc(type)}" aria-pressed="true">${esc(TYPE_LABELS[type] || type)}</button>`).join('')}</div><canvas class="project-graph-canvas" aria-label="Graphe de connaissances interactif du projet" tabindex="0"></canvas><div class="graph-details" data-graph-details role="status">Sélectionnez un nœud ou une relation pour consulter sa provenance.</div><div class="graph-relations" data-graph-relations aria-label="Relations du graphe"></div>`;
    const canvas = root.querySelector('canvas');
    const details = root.querySelector('[data-graph-details]');
    const relations = root.querySelector('[data-graph-relations]');
    const context = canvas.getContext('2d');
    const visible = new Set(types);
    const positions = new Map(graph.nodes.map((node, index) => [node.id, pointFor(index, graph.nodes.length)]));
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    let yaw = 0.42; let pitch = -0.18; let zoom = 1; let dragging = false; let last = null; let active = null;

    function resize() {
      const ratio = window.devicePixelRatio || 1;
      const box = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, Math.floor(box.width * ratio)); canvas.height = Math.max(1, Math.floor(box.height * ratio));
      context.setTransform(ratio, 0, 0, ratio, 0, 0); draw();
    }
    function projected(node) {
      const rotated = rotate(positions.get(node.id), yaw, pitch);
      const box = canvas.getBoundingClientRect(); const scale = Math.min(box.width, box.height) * 0.31 * zoom;
      return { x: box.width / 2 + rotated.x * scale, y: box.height / 2 + rotated.y * scale, z: rotated.z };
    }
    function nodeVisible(node) { return visible.has(node.type); }
    function showNode(node) {
      active = node.id;
      const provenance = node.provenance || {};
      const propertyLabels = { project_type: 'Type de projet', country_code: 'Pays', document_type: 'Type de document', classification: 'Classification', visibility: 'Visibilité', knowledge_kind: 'Représentation' };
      const properties = Object.entries(node.properties || {}).filter(([key]) => !['normalized_key', 'canonical_value'].includes(key)).map(([key, value]) => `<dt>${esc(propertyLabels[key] || key)}</dt><dd>${esc(VALUE_LABELS[value] || value)}</dd>`).join('');
      const related = graph.edges.filter((edge) => edge.source === node.id || edge.target === node.id).length;
      details.innerHTML = `<strong>${esc(node.label)}</strong><dl><dt>Type</dt><dd>${esc(TYPE_LABELS[node.type] || node.type)}</dd><dt>Statut</dt><dd>${esc(STATUS_LABELS[node.trust_status] || node.trust_status)}</dd><dt>Source</dt><dd>${esc(provenance.source_type || 'Information confirmée')}</dd><dt>Champ</dt><dd>${esc(provenance.source_field || '—')}</dd><dt>Relations</dt><dd>${related}</dd>${properties}</dl>`;
      draw();
    }
    function showEdge(edge) {
      active = edge.id;
      const source = graph.nodes.find((node) => node.id === edge.source); const target = graph.nodes.find((node) => node.id === edge.target);
      details.innerHTML = `<strong>${esc(RELATION_LABELS[edge.relation] || edge.relation)}</strong><dl><dt>Relation</dt><dd>${esc(source?.label || 'Projet')} → ${esc(target?.label || 'Contexte')}</dd><dt>Statut</dt><dd>${esc(STATUS_LABELS[edge.trust_status] || edge.trust_status)}</dd><dt>Source</dt><dd>${esc(edge.provenance?.source_type || 'Information confirmée')}</dd><dt>Champ</dt><dd>${esc(edge.provenance?.source_field || '—')}</dd></dl>`;
      draw();
    }
    function renderRelations() {
      relations.innerHTML = graph.edges.filter((edge) => graph.nodes.some((node) => node.id === edge.source && nodeVisible(node)) && graph.nodes.some((node) => node.id === edge.target && nodeVisible(node))).map((edge) => {
        const source = graph.nodes.find((node) => node.id === edge.source); const target = graph.nodes.find((node) => node.id === edge.target);
        return `<button type="button" data-graph-edge="${esc(edge.id)}">${esc(source?.label || 'Projet')} · ${esc(RELATION_LABELS[edge.relation] || edge.relation)} · ${esc(target?.label || '')}</button>`;
      }).join('');
    }
    function draw() {
      const box = canvas.getBoundingClientRect(); context.clearRect(0, 0, box.width, box.height);
      context.fillStyle = '#f8f8f8'; context.fillRect(0, 0, box.width, box.height);
      const nodes = graph.nodes.filter(nodeVisible).map((node) => ({ node, point: projected(node) })).sort((a, b) => a.point.z - b.point.z);
      const byId = new Map(nodes.map((item) => [item.node.id, item]));
      context.lineWidth = 1;
      graph.edges.forEach((edge) => {
        const a = byId.get(edge.source); const b = byId.get(edge.target); if (!a || !b) return;
        context.strokeStyle = active === edge.id ? '#050505' : '#b8b8b8'; context.beginPath(); context.moveTo(a.point.x, a.point.y); context.lineTo(b.point.x, b.point.y); context.stroke();
      });
      nodes.forEach(({ node, point }) => {
        const radius = node.type === 'PROJECT' ? 15 : Math.max(7, 11 + point.z * 3);
        context.fillStyle = node.type === 'PROJECT' ? '#050505' : '#fff'; context.strokeStyle = '#050505'; context.lineWidth = active === node.id ? 3 : 1;
        context.beginPath(); context.arc(point.x, point.y, radius, 0, Math.PI * 2); context.fill(); context.stroke();
        context.fillStyle = node.type === 'PROJECT' ? '#fff' : '#050505'; context.font = `${node.type === 'PROJECT' ? '700' : '600'} 11px Space Grotesk, sans-serif`; context.textAlign = 'center'; context.fillText(node.type === 'PROJECT' ? 'RB' : (TYPE_LABELS[node.type] || node.type).slice(0, 3), point.x, point.y + 4);
        const compactLabel = node.label.length > 22 ? `${node.label.slice(0, 21)}…` : node.label;
        context.fillStyle = '#050505'; context.font = '600 12px Space Grotesk, sans-serif'; context.fillText(compactLabel, point.x, point.y + radius + 17);
      });
    }
    canvas.addEventListener('pointerdown', (event) => { dragging = true; last = { x: event.clientX, y: event.clientY }; canvas.setPointerCapture(event.pointerId); });
    canvas.addEventListener('pointermove', (event) => { if (!dragging || !last) return; yaw += (event.clientX - last.x) / 180; pitch = Math.max(-1.1, Math.min(1.1, pitch + (event.clientY - last.y) / 180)); last = { x: event.clientX, y: event.clientY }; draw(); });
    canvas.addEventListener('pointerup', (event) => { dragging = false; canvas.releasePointerCapture?.(event.pointerId); });
    canvas.addEventListener('wheel', (event) => { event.preventDefault(); zoom = Math.max(0.65, Math.min(1.75, zoom + (event.deltaY < 0 ? 0.08 : -0.08))); draw(); }, { passive: false });
    canvas.addEventListener('click', (event) => { const rect = canvas.getBoundingClientRect(); const hit = graph.nodes.filter(nodeVisible).map((node) => ({ node, point: projected(node) })).find(({ point }) => Math.hypot(point.x - (event.clientX - rect.left), point.y - (event.clientY - rect.top)) < 20); if (hit) showNode(hit.node); });
    root.querySelector('[data-graph-reset]').addEventListener('click', () => { yaw = .42; pitch = -.18; zoom = 1; active = null; details.textContent = 'Sélectionnez un nœud ou une relation pour consulter sa provenance.'; draw(); });
    root.querySelectorAll('[data-graph-filter]').forEach((button) => button.addEventListener('click', () => { const type = button.dataset.graphFilter; if (visible.has(type)) visible.delete(type); else visible.add(type); button.setAttribute('aria-pressed', String(visible.has(type))); renderRelations(); draw(); }));
    relations.addEventListener('click', (event) => { const edge = graph.edges.find((item) => item.id === event.target.closest('[data-graph-edge]')?.dataset.graphEdge); if (edge) showEdge(edge); });
    window.addEventListener('resize', resize); renderRelations(); resize();
    if (!reducedMotion) { const tick = () => { if (!root.isConnected) return; if (!dragging) { yaw += 0.0012; draw(); } window.requestAnimationFrame(tick); }; window.requestAnimationFrame(tick); }
  }
  window.RegBridgeKnowledgeGraph = Object.freeze({ mount });
})();
