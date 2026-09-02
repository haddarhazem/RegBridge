(function createInvestorApi() {
  'use strict';

  const request = (...args) => window.RegBridgeAuthRuntime.apiRequest(...args);
  const json = (method, body) => ({ method, body: JSON.stringify(body) });

  window.RegBridgeInvestorApi = Object.freeze({
    me: () => window.RegBridgeAuthRuntime.currentUser(),
    profile: () => request('/investor/profile'),
    createProfile: (data) => request('/investor/profile', json('POST', data)),
    updateProfile: (data) => request('/investor/profile', json('PATCH', data)),
    profileVersions: () => request('/investor/profile/versions'),
    searchStartups: (filters = {}) => {
      const query = new URLSearchParams();
      Object.entries(filters).forEach(([key, value]) => {
        if (value != null && value !== '') query.set(key, value);
      });
      return request(`/startups/search?${query}`);
    },
    publicStartupProfile: (projectId) => request(`/projects/${projectId}/public-profile`),
    createMatch: (startupProjectId, thesisVersionId = null) => request('/investment-matches', json('POST', { startup_project_id: startupProjectId, investor_thesis_version_id: thesisVersionId })),
    matchingRun: (runId) => request(`/investment-matches/${runId}`),
    matchingRuns: ({ limit = 50, offset = 0 } = {}) => request(`/investor/matches?limit=${limit}&offset=${offset}`),
    createBrief: (startupProjectId, thesisVersionId = null, matchingRunId = null) => request('/investment-briefs', json('POST', { startup_project_id: startupProjectId, investor_thesis_version_id: thesisVersionId, matching_run_id: matchingRunId })),
    brief: (runId) => request(`/investment-briefs/${runId}`),
    verifyBrief: (runId, versionId = null) => request(`/investment-briefs/${runId}${versionId ? `/versions/${versionId}` : ''}/verify`, { method: 'POST' }),
    briefVersions: (runId) => request(`/investment-briefs/${runId}/versions`),
    briefs: ({ limit = 50, offset = 0 } = {}) => request(`/investor/briefs?limit=${limit}&offset=${offset}`),
    briefVersion: (runId, versionId) => request(`/investment-briefs/${runId}/versions/${versionId}`),
    approveBrief: (runId, versionId) => request(`/investment-briefs/${runId}/versions/${versionId}/approve`, { method: 'POST' }),
    exportBrief: (runId, versionId) => window.RegBridgeAuthRuntime.download(`/investment-briefs/${runId}/versions/${versionId}/export.pdf`),
    sharedBriefs: () => request('/investment-briefs/shared-with-me'),
    opportunities: () => request('/investment-opportunities'),
    opportunity: (opportunityId) => request(`/investment-opportunities/${opportunityId}`),
    createOpportunity: (data) => request('/investment-opportunities', json('POST', data)),
    updateOpportunity: (opportunityId, data) => request(`/investment-opportunities/${opportunityId}`, json('PATCH', data)),
    closeOpportunity: (opportunityId) => request(`/investment-opportunities/${opportunityId}/close`, { method: 'POST' }),
    events: () => request('/events'),
    createEvent: (data) => request('/events', json('POST', data)),
    updateEvent: (eventId, data) => request(`/events/${eventId}`, json('PATCH', data)),
    cancelEvent: (eventId) => request(`/events/${eventId}/cancel`, { method: 'POST' }),
    eventParticipation: (eventId) => request(`/events/${eventId}/participation`),
    expressInterest: (eventId) => request(`/events/${eventId}/interest`, { method: 'POST' }),
    registerEvent: (eventId) => request(`/events/${eventId}/register`, { method: 'POST' }),
    withdrawEvent: (eventId) => request(`/events/${eventId}/withdraw`, { method: 'POST' }),
    contactRequests: () => request('/contact-requests'),
    requestContact: (targetId, message = '') => request('/contact-requests', json('POST', { target_type: 'project', target_id: targetId, message: message || null })),
    contactDisclosure: (requestId) => request(`/contact-requests/${requestId}/contacts`),
  });
})();
