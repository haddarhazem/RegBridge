const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function load(file, window = {}) {
  vm.runInNewContext(fs.readFileSync(file, 'utf8'), { window, Intl, Date, URL, URLSearchParams });
  return window;
}

test('empty structured assessment directs users back to regulatory generation', () => {
  const views = load('frontend/entrepreneur/views.js').RegBridgeEntrepreneurViews;
  const html = views.roadmap({roadmap:null,assessment:{status:'completed',verification_verdict:'pass',result:{obligations:[],recommendations:[],uncertainties:[]}}});
  assert.doesNotMatch(html, /data-action="generate-roadmap"/);
  assert.match(html, /aucune conclusion structurée/);
  assert.match(html, /data-action="open-regulatory"/);
});

test('compliance without controls explains and disables calculation', () => {
  const views = load('frontend/entrepreneur/views.js').RegBridgeEntrepreneurViews;
  const html = views.compliance({project:{project_type:'startup_in_creation'},controls:[]});
  assert.doesNotMatch(html, /data-action="calculate-score"/);
  assert.match(html, /disabled aria-describedby="score-prerequisite"/);
  assert.match(html, /référentiel contenant des contrôles/);
});

test('populated regulatory view consumes the actual assessments property', () => {
  const views = load('frontend/entrepreneur/views.js').RegBridgeEntrepreneurViews;
  const assessment = {version: 1, status: 'completed', result: {answer: 'Synthetic answer', obligations: [], recommendations: [], uncertainties: []}};
  const html = views.regulatory({assessment, assessments: [assessment], facts: []});
  assert.match(html, /Synthetic answer/);
  assert.match(html, /data-version="1"/);
});

test('project and populated roadmap render production response shapes', () => {
  const views = load('frontend/entrepreneur/views.js').RegBridgeEntrepreneurViews;
  const project = {display_name: 'Synthetic project', project_type: 'idea', activity: 'SaaS', data: 'D'.repeat(572)};
  assert.ok(views.project({project, facts: [], history: []}).includes(project.data));
  const roadmap = {id: 'r', version: 1, items: [{id: 'i', title: 'Synthetic step', item_type: 'obligation', status: 'pending', justification: 'Synthetic evidence', source_conclusion_refs: ['c1']}]};
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

test('roadmap eligibility and provenance use its linked assessment, not the latest', () => {
  const views = load('frontend/entrepreneur/views.js').RegBridgeEntrepreneurViews;
  assert.match(views.roadmap({roadmap:null, assessment:null}), /évaluation réglementaire est nécessaire/);
  assert.doesNotMatch(views.roadmap({roadmap:null, assessment:{status:'blocked'}}), /data-action="generate-roadmap"/);
  const linked={version:1, result:{obligations:[{conclusion_id:'internal-c1', statement:'Synthetic source conclusion',source_refs:['CNIL']}],recommendations:[],uncertainties:[]}};
  const roadmap={version:2, items:[{id:'i',title:'Synthetic action',item_type:'obligation',status:'skipped',priority_order:1,justification:'Synthetic reason',source_conclusion_refs:['internal-c1'],dependency_item_refs:[]}]};
  const html=views.roadmap({roadmap, assessment:{version:9,status:'completed'},roadmapAssessment:linked});
  assert.match(html,/Synthetic source conclusion/);
  assert.match(html,/CNIL/);
  assert.doesNotMatch(html,/internal-c1/);
  for (const status of ['pending','in_progress','completed','skipped']) assert.ok(html.includes(`value="${status}"`));
});

test('regulatory history, uncertainty and source URLs remain escaped and versioned', () => {
  const views=load('frontend/entrepreneur/views.js').RegBridgeEntrepreneurViews;
  const assessment={version:1,status:'blocked',verification_verdict:'block',result:{answer:'Synthetic blocked result',obligations:[],recommendations:[],uncertainties:[{statement:'Synthetic missing information',source_refs:[]}],sources:['CNIL','https://www.cnil.fr/example','javascript:alert(1)']}};
  const html=views.regulatory({assessment, assessments:[assessment,{version:2}],facts:[]});
  assert.match(html,/Synthetic missing information/);
  assert.match(html,/href="https:\/\/www.cnil.fr\/example"/);
  assert.doesNotMatch(html,/href="javascript:/);
  assert.match(html,/data-version="2"/);
  assert.match(html,/n’est pas utilisable pour générer une roadmap/);
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
