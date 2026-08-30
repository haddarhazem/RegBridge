(function createEntrepreneurApi() {
  'use strict';

  const request = (...args) => window.RegBridgeAuthRuntime.apiRequest(...args);
  const json = (method, body) => ({ method, body: JSON.stringify(body) });

  window.RegBridgeEntrepreneurApi = Object.freeze({
    me: () => window.RegBridgeAuthRuntime.currentUser(),
    projects: () => request('/projects'),
    getProject: (projectId) => request(`/projects/${projectId}`),
    createProject: (data) => request('/projects', json('POST', data)),
    updateProject: (projectId, data) => request(`/projects/${projectId}`, json('PATCH', data)),
    getOnboarding: (projectId) => request(`/projects/${projectId}/onboarding`),
    updateOnboarding: (projectId, data) => request(`/projects/${projectId}/onboarding`, json('PATCH', data)),
    transitionProject: (projectId, targetType) => request(`/projects/${projectId}/transition`, json('POST', { target_type: targetType })),
    lifecycleHistory: (projectId) => request(`/projects/${projectId}/lifecycle-history`),
    inferFacts: (projectId) => request(`/projects/${projectId}/facts/infer`, { method: 'POST' }),
    facts: (projectId) => request(`/projects/${projectId}/facts`),
    confirmFact: (projectId, factId) => request(`/projects/${projectId}/facts/${factId}/confirm`, { method: 'POST' }),
    correctFact: (projectId, factId, value) => request(`/projects/${projectId}/facts/${factId}`, json('PATCH', { value })),
    rejectFact: (projectId, factId) => request(`/projects/${projectId}/facts/${factId}`, { method: 'DELETE' }),
    latestAssessment: (projectId) => request(`/projects/${projectId}/assessments/latest`),
    assessments: (projectId) => request(`/projects/${projectId}/assessments`),
    assessment: (projectId, version) => request(`/projects/${projectId}/assessments/${version}`),
    generateAssessment: (projectId, question) => request(`/projects/${projectId}/assessments`, json('POST', { question })),
    latestRoadmap: (projectId) => request(`/projects/${projectId}/roadmaps/latest`),
    roadmaps: (projectId) => request(`/projects/${projectId}/roadmaps`),
    roadmap: (projectId, version) => request(`/projects/${projectId}/roadmaps/${version}`),
    generateRoadmap: (projectId, assessmentId) => request(`/projects/${projectId}/roadmaps`, json('POST', { regulatory_assessment_id: assessmentId })),
    updateRoadmapItem: (projectId, version, itemId, status) => request(`/projects/${projectId}/roadmaps/${version}/items/${itemId}`, json('PATCH', { status })),
    uploadDocument: (projectId, file, options = {}) => {
      const form = new FormData();
      form.append('upload', file);
      const query = new URLSearchParams();
      if (options.title) query.set('title', options.title);
      query.set('classification', options.classification || 'confidential');
      query.set('visibility', options.visibility || 'private');
      return request(`/projects/${projectId}/documents?${query}`, { method: 'POST', body: form });
    },
    uploadDocumentVersion: (documentId, file) => {
      const form = new FormData();
      form.append('upload', file);
      return request(`/documents/${documentId}/versions`, { method: 'POST', body: form });
    },
    projectDocuments: (projectId) => request(`/projects/${projectId}/documents`),
    getDocument: (documentId) => request(`/documents/${documentId}`),
    documentVersions: (documentId) => request(`/documents/${documentId}/versions`),
    documentVersion: (documentId, versionId) => request(`/documents/${documentId}/versions/${versionId}`),
    retryDocumentExtraction: (documentId, versionId) => request(`/documents/${documentId}/versions/${versionId}/processing-jobs/retry`, { method: 'POST' }),
    downloadDocumentVersion: (documentId, versionId) => window.RegBridgeAuthRuntime.download(`/documents/${documentId}/versions/${versionId}/download`),
    documentAnalyses: (documentId) => request(`/documents/${documentId}/analyses`),
    analyzeContract: (documentId, versionId) => request(`/documents/${documentId}/versions/${versionId}/analyses`, { method: 'POST' }),
    members: (projectId) => request(`/projects/${projectId}/members`),
    inviteMember: (projectId, data) => request(`/projects/${projectId}/members`, json('POST', data)),
    updateMember: (projectId, userId, role) => request(`/projects/${projectId}/members/${userId}`, json('PATCH', { member_role: role })),
    revokeMember: (projectId, userId) => request(`/projects/${projectId}/members/${userId}`, { method: 'DELETE' }),
    frameworks: () => request('/compliance/frameworks'),
    controls: (projectId) => request(`/projects/${projectId}/compliance/controls`),
    adoptFramework: (projectId, frameworkVersionId) => request(`/projects/${projectId}/compliance/adoptions`, json('POST', { framework_version_id: frameworkVersionId })),
    updateControl: (projectId, controlId, data) => request(`/projects/${projectId}/compliance/controls/${controlId}`, json('PATCH', data)),
    controlEvidence: (projectId, controlId) => request(`/projects/${projectId}/compliance/controls/${controlId}/evidence`),
    attachEvidence: (projectId, data) => request(`/projects/${projectId}/compliance/evidence`, json('POST', data)),
    revokeEvidence: (projectId, evidenceId, reason = '') => request(`/projects/${projectId}/compliance/evidence/${evidenceId}/revoke`, json('POST', { reason: reason || null })),
    calculateScore: (projectId, frameworkVersionId = null) => request(`/projects/${projectId}/compliance/scores`, json('POST', { framework_version_id: frameworkVersionId })),
    latestScore: (projectId, frameworkVersionId = null) => request(`/projects/${projectId}/compliance/scores/latest${frameworkVersionId ? `?framework_version_id=${encodeURIComponent(frameworkVersionId)}` : ''}`),
    scoreHistory: (projectId, frameworkVersionId = null) => request(`/projects/${projectId}/compliance/scores/history${frameworkVersionId ? `?framework_version_id=${encodeURIComponent(frameworkVersionId)}` : ''}`),
    conversations: () => request('/conversations'),
    conversation: (conversationId) => request(`/conversations/${conversationId}`),
    createConversation: (projectId, title) => request('/conversations', json('POST', { title, subject_type: 'project', subject_id: projectId })),
    askCopilot: (conversationId, content, signal, context = {}) => request(`/conversations/${conversationId}/responses`, { ...json('POST', { content, ...context }), signal }),
  });
})();
