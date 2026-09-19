const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function load(file, window = {}) {
  vm.runInNewContext(fs.readFileSync(file, 'utf8'), { window, Intl, Date, URL, URLSearchParams });
  return window;
}

test('empty structured assessment does not block launch roadmap generation', () => {
  const views = load('frontend/entrepreneur/views.js').RegBridgeEntrepreneurViews;
  const project={project_type:'startup_in_creation',confirmed_fields:{activity:'confirmed',sector:'confirmed'}};
  const html = views.roadmap({roadmap:null,project,assessment:{status:'completed',verification_verdict:'pass',result:{obligations:[],recommendations:[],uncertainties:[]}}});
  assert.match(html, /data-action="generate-roadmap"/);
  assert.match(html, /Couverture réglementaire à compléter/);
  assert.match(html, /data-action="open-regulatory"/);
});

test('compliance without controls explains and disables calculation', () => {
  const views = load('frontend/entrepreneur/views.js').RegBridgeEntrepreneurViews;
  const html = views.compliance({project:{project_type:'startup_in_creation'},controls:[]});
  assert.doesNotMatch(html, /data-action="calculate-score"/);
  assert.match(html, /disabled aria-describedby="score-prerequisite"/);
  assert.match(html, /référentiel contenant des contrôles/);
});

test('startup views do not expose idea-only onboarding or fact-inference actions', () => {
  const views = load('frontend/entrepreneur/views.js').RegBridgeEntrepreneurViews;
  const project = {id:'p', display_name:'Synthetic startup', project_type:'startup_in_creation', confirmed_fields:[]};
  const dashboard = views.dashboard({project, onboarding:null, facts:[], assessment:null, roadmap:null});
  const facts = views.project({project, facts:[], history:[], tab:'facts'});
  assert.doesNotMatch(dashboard, /data-action="open-onboarding"/);
  assert.match(dashboard, /data-action="open-project"/);
  assert.doesNotMatch(facts, /data-action="infer-facts"/);
});

test('populated regulatory view consumes the actual assessments property', () => {
  const views = load('frontend/entrepreneur/views.js').RegBridgeEntrepreneurViews;
  const assessment = {version: 1, status: 'completed', result: {answer: 'Synthetic answer', obligations: [], recommendations: [], uncertainties: []}};
  const html = views.regulatory({assessment, assessments: [assessment], facts: []});
  assert.match(html, /Synthetic answer/);
  assert.match(html, /data-version="1"/);
});

test('provider rate limiting uses the safe demo-facing message', () => {
  const source = fs.readFileSync('frontend/entrepreneur/app.js', 'utf8');
  assert.match(source, /Le service IA a atteint sa limite temporaire\. Réessayez dans quelques instants\./);
  assert.doesNotMatch(source, /Copilot rate limit reached|RESOURCE_EXHAUSTED|provider_rate_limited/);
});

test('copilot maps the real fallback stages without exposing domain query text', () => {
  const source = fs.readFileSync('frontend/entrepreneur/app.js', 'utf8');
  assert.match(source, /RETRIEVING_MISSING_DOMAIN_EVIDENCE/);
  assert.match(source, /REASSESSING_EVIDENCE/);
  assert.match(source, /RETRIEVING_AUTHORITATIVE_EVIDENCE/);
  assert.match(source, /REASSESSING_AUTHORITATIVE_EVIDENCE/);
  assert.match(source, /Recherche complémentaire des sources/);
  assert.match(source, /Recherche des sources officielles/);
  assert.match(source, /Réévaluation des sources/);
  assert.match(source, /item\.status !== 'not_started'/);
  assert.doesNotMatch(source, /fallback_query|domain_query/i);
  assert.doesNotMatch(source, /authoritative_url|authoritative_query|page_body/i);
  assert.match(source, /Question scope/);
  assert.match(source, /Scope supported/);
});

test('project and populated roadmap render production response shapes', () => {
  const views = load('frontend/entrepreneur/views.js').RegBridgeEntrepreneurViews;
  const project = {display_name: 'Synthetic project', project_type: 'idea', activity: 'SaaS', data: 'D'.repeat(572)};
  assert.ok(views.project({project, facts: [], history: []}).includes(project.data));
  const roadmap = {id: 'r', version: 1, regulatory_coverage:'incomplete', items: [{id: 'i', title: 'Synthetic step', item_type: 'launch', origins:['BASELINE'], status: 'pending', justification: 'Synthetic evidence', source_conclusion_refs: ['BASELINE:test']}]};
  assert.match(views.roadmap({roadmap, assessment: {version: 1}}), /Synthetic step/);
});

test('roadmap boundary distinguishes null from malformed non-null payload', async () => {
  let payload = null;
  const api = load('frontend/entrepreneur/api.js', {RegBridgeAuthRuntime: {apiRequest: async () => payload}}).RegBridgeEntrepreneurApi;
  assert.equal(await api.latestRoadmap('p'), null);
  payload = {id: 'r', version: 1};
  await assert.rejects(api.latestRoadmap('p'), /format de la roadmap/);
  payload = {id: 'r', items: []};
  assert.equal((await api.latestRoadmap('p')).items.length, 0);
});

test('roadmap shows grouped launch categories and origin labels without technical ids', () => {
  const views = load('frontend/entrepreneur/views.js').RegBridgeEntrepreneurViews;
  const project={project_type:'startup_in_creation',confirmed_fields:{activity:'confirmed',sector:'confirmed'}};
  assert.match(views.roadmap({roadmap:null, project, assessment:null}), /data-action="generate-roadmap"/);
  const linked={version:1, result:{obligations:[{conclusion_id:'internal-c1', statement:'Synthetic source conclusion',source_refs:['CNIL']}],recommendations:[],uncertainties:[]}};
  const roadmap={version:2,regulatory_assessment_id:'assessment-id',regulatory_coverage:'enriched',items:[{id:'i',title:'Synthetic action',item_type:'regulatory',origins:['REGULATORY_ASSESSMENT'],status:'skipped',priority_order:1,justification:'Synthetic reason',source_conclusion_refs:['REGULATORY_ASSESSMENT:internal-c1'],dependency_item_refs:[]}]};
  const html=views.roadmap({roadmap, project, assessment:{version:9,status:'completed'},roadmapAssessment:linked});
  assert.match(html,/Avant le lancement/);
  assert.match(html,/Évaluation réglementaire/);
  assert.doesNotMatch(html,/internal-c1/);
  for (const status of ['pending','in_progress','completed','skipped']) assert.ok(html.includes(`value="${status}"`));
});

test('roadmap transparently reuses the latest verified structured assessment after a blocked attempt', () => {
  const views = load('frontend/entrepreneur/views.js').RegBridgeEntrepreneurViews;
  const verified = {id:'verified', version:3, status:'completed', verification_verdict:'pass', result:{obligations:[], recommendations:[{statement:'Synthetic action'}], uncertainties:[]}};
  const blocked = {id:'blocked', version:4, status:'blocked', verification_verdict:'block', result:{obligations:[], recommendations:[], uncertainties:[{statement:'Provider unavailable'}]}};
  const project={project_type:'startup_in_creation',confirmed_fields:{activity:'confirmed',sector:'confirmed'}};
  const html = views.roadmap({roadmap:null, project, assessment:verified, latestAssessment:blocked});
  assert.match(html, /data-action="generate-roadmap"/);
  assert.doesNotMatch(html, /Provider unavailable/);
});

test('regulatory history, uncertainty and source URLs remain escaped and versioned', () => {
  const views=load('frontend/entrepreneur/views.js').RegBridgeEntrepreneurViews;
  const assessment={version:1,status:'blocked',verification_verdict:'block',result:{answer:'Synthetic blocked result',obligations:[],recommendations:[],uncertainties:[{statement:'Synthetic missing information',source_refs:[]}],sources:['CNIL','https://www.cnil.fr/example','javascript:alert(1)']}};
  const html=views.regulatory({assessment, assessments:[assessment,{version:2}],facts:[]});
  assert.match(html,/Synthetic missing information/);
  assert.match(html,/href="https:\/\/www.cnil.fr\/example"/);
  assert.doesNotMatch(html,/href="javascript:/);
  assert.match(html,/data-version="2"/);
  assert.match(html,/ne peut pas enrichir la roadmap/);
});

test('contracts show only completed same-version observations, never semantic advice', () => {
  const views=load('frontend/entrepreneur/views.js').RegBridgeEntrepreneurViews;
  assert.match(views.contracts({documents:[]}),/Aucun contrat analysé/);
  const entry={document:{id:'d',title:'Synthetic contract'},versions:[{id:'v',version_number:3,malware_scan_status:'clean',extraction_status:'ready'}],analyses:[{id:'a',status:'completed',document_version_id:'v',observations:[{document_version_id:'v',source_quote:'Exact synthetic excerpt',suggested_category:'duration',observation_index:0,start_char:0,end_char:23},{document_version_id:'wrong',source_quote:'WRONG VERSION',start_char:0,end_char:13}],recommendations:[{statement:'UNSAFE advice'}]}]};
  let html=views.contracts({documents:[entry]});
  assert.match(html,/Exact synthetic excerpt/);
  assert.match(html,/v3/);
  assert.doesNotMatch(html,/WRONG VERSION|UNSAFE advice/);
  entry.analyses[0].status='failed';
  html=views.contracts({documents:[entry]});
  assert.match(html,/Analyse échouée/);
  assert.doesNotMatch(html,/Exact synthetic excerpt|data-action="copilot-analysis"/);
  entry.versions[0].extraction_status='failed';
  html=views.contracts({documents:[entry],selectedVersionId:'missing'});
  assert.match(html,/Extraction échouée/);
  assert.match(html,/version sélectionnée ne correspond pas/);
  assert.doesNotMatch(html,/data-action="analyze-contract"/);
});
