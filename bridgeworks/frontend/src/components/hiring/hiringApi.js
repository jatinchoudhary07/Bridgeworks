/**
 * Hiring API client — centralises all hiring-related fetch calls.
 */
import { apiClient } from '../../apiClient';
import { BACKEND_URL } from '../../config/api';

const BASE = `${BACKEND_URL}/api/hiring`;
const WORKFORCE_BASE = `${BACKEND_URL}/api/workforce`;

// ---- Jobs ----
export const fetchJobs = (params = {}) => {
    const qs = new URLSearchParams(
        Object.entries(params).reduce((acc, [key, value]) => {
            if (value !== undefined && value !== null && value !== '') {
                acc[key] = value;
            }
            return acc;
        }, {})
    ).toString();
    return apiClient(`${BASE}/jobs/${qs ? `?${qs}` : ''}`).then(r => r.json());
};
export const fetchJob = (id) => apiClient(`${BASE}/jobs/${id}/`).then(r => r.json());
export const createJob = (data) => apiClient(`${BASE}/jobs/`, { method: 'POST', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());
export const updateJob = (id, data) => apiClient(`${BASE}/jobs/${id}/`, { method: 'PATCH', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());
export const deleteJob = (id) => apiClient(`${BASE}/jobs/${id}/`, { method: 'DELETE' });
export const publishJob = (id) => apiClient(`${BASE}/jobs/${id}/publish/`, { method: 'POST' }).then(r => r.json());
export const closeJob = (id) => apiClient(`${BASE}/jobs/${id}/close/`, { method: 'POST' }).then(r => r.json());

// ---- Departments ----
export const fetchDepartments = () => apiClient(`${WORKFORCE_BASE}/departments/`).then(async r => {
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Failed to fetch departments');
    return data;
});
export const createDepartment = (name) => apiClient(`${WORKFORCE_BASE}/departments/`, {
    method: 'POST',
    body: JSON.stringify({ name }),
    headers: { 'Content-Type': 'application/json' },
}).then(async r => {
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Failed to create department');
    return data;
});
export const deleteDepartment = (id) => apiClient(`${WORKFORCE_BASE}/departments/${id}/`, { method: 'DELETE' });

// ---- Stages ----
export const fetchStages = () => apiClient(`${BASE}/stages/`).then(r => r.json());
export const createStage = (data) => apiClient(`${BASE}/stages/`, { method: 'POST', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());
export const updateStage = (id, data) => apiClient(`${BASE}/stages/${id}/`, { method: 'PATCH', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());
export const deleteStage = (id) => apiClient(`${BASE}/stages/${id}/`, { method: 'DELETE' });

// ---- Candidates ----
export const fetchCandidates = (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return apiClient(`${BASE}/candidates/${qs ? `?${qs}` : ''}`).then(r => r.json());
};
export const fetchCandidate = (id) => apiClient(`${BASE}/candidates/${id}/`).then(r => r.json());
export const createCandidate = (data) => apiClient(`${BASE}/candidates/`, { method: 'POST', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());
export const updateCandidate = (id, data) => apiClient(`${BASE}/candidates/${id}/`, { method: 'PATCH', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());
export const fetchCandidateNotes = (id) => apiClient(`${BASE}/candidates/${id}/notes/`).then(r => r.json());
export const addCandidateNote = (id, data) => apiClient(`${BASE}/candidates/${id}/notes/`, { method: 'POST', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());

// ---- Applications ----
export const fetchApplications = (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return apiClient(`${BASE}/applications/${qs ? `?${qs}` : ''}`).then(r => r.json());
};
export const fetchApplication = (id) => apiClient(`${BASE}/applications/${id}/`).then(r => r.json());
export const createApplication = (data) => apiClient(`${BASE}/applications/`, { method: 'POST', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());
export const moveApplicationStage = (id, stageId, notes = '') => apiClient(`${BASE}/applications/${id}/move-stage/`, { method: 'POST', body: JSON.stringify({ stage_id: stageId, notes }), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());
export const acceptApplication = (id) => apiClient(`${BASE}/applications/${id}/accept/`, { method: 'POST' }).then(r => r.json());
export const rejectApplication = (id) => apiClient(`${BASE}/applications/${id}/reject/`, { method: 'POST' }).then(r => r.json());
export const toggleSaveApplication = (id) => apiClient(`${BASE}/applications/${id}/save/`, { method: 'POST' }).then(r => r.json());
export const setApplicationPipelineStage = (id, pipelineStageId) => apiClient(`${BASE}/applications/${id}/pipeline-stage/`, { method: 'PATCH', body: JSON.stringify({ pipeline_stage_id: pipelineStageId }), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());
export const convertToEmployee = (id) => apiClient(`${BASE}/applications/${id}/convert-to-employee/`, { method: 'POST' }).then(r => r.json());

// ---- Job Pipeline Stages ----
export const fetchJobPipelineStages = (jobId) => apiClient(`${BASE}/jobs/${jobId}/pipeline/`).then(r => r.json());
export const initJobPipeline = (jobId) => apiClient(`${BASE}/jobs/${jobId}/pipeline/`, { method: 'POST', body: JSON.stringify({ action: 'init' }), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());
export const createJobPipelineStage = (jobId, data) => apiClient(`${BASE}/jobs/${jobId}/pipeline/`, { method: 'POST', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());
export const updateJobPipelineStage = (jobId, stageId, data) => apiClient(`${BASE}/jobs/${jobId}/pipeline/${stageId}/`, { method: 'PATCH', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());
export const deleteJobPipelineStage = (jobId, stageId) => apiClient(`${BASE}/jobs/${jobId}/pipeline/${stageId}/`, { method: 'DELETE' })
    .then(async r => {
        if (!r.ok) {
            const data = await r.json().catch(() => ({}));
            throw new Error(data.error || 'Failed to delete column.');
        }
        return r;
    });
export const reorderJobPipelineStages = (jobId, orders) => apiClient(`${BASE}/jobs/${jobId}/pipeline/`, { method: 'POST', body: JSON.stringify({ action: 'reorder', orders }), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());

// ---- Interviews ----
export const fetchInterviews = (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return apiClient(`${BASE}/interviews/${qs ? `?${qs}` : ''}`).then(r => r.json());
};
export const createInterview = (data) => apiClient(`${BASE}/interviews/`, { method: 'POST', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());
export const updateInterview = (id, data) => apiClient(`${BASE}/interviews/${id}/`, { method: 'PATCH', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());
export const rescheduleInterview = (id, data) => apiClient(`${BASE}/interviews/${id}/reschedule/`, { method: 'POST', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());
export const fetchInterviewFeedback = (id) => apiClient(`${BASE}/interviews/${id}/feedback/`).then(r => r.json());
export const submitInterviewFeedback = (id, data) => apiClient(`${BASE}/interviews/${id}/feedback/`, { method: 'POST', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());

// ---- Offers ----
export const fetchOffers = (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return apiClient(`${BASE}/offers/${qs ? `?${qs}` : ''}`).then(r => r.json());
};
export const createOffer = (data) => apiClient(`${BASE}/offers/create/`, { method: 'POST', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());
export const updateOffer = (id, data) => apiClient(`${BASE}/offers/${id}/`, { method: 'PATCH', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());

// ---- Analytics ----
export const fetchHiringAnalytics = () => apiClient(`${BASE}/analytics/`).then(r => r.json());

// ---- Google Form Import ----
export const importFromGoogleForm = (data) => apiClient(`${BASE}/import/google-form/`, { method: 'POST', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }).then(r => r.json());

export const syncJobGoogleForm = (jobId) => apiClient(`${BASE}/jobs/${jobId}/sync-form/`, { method: 'POST' })
    .then(async r => {
        const data = await r.json();
        if (!r.ok) throw Object.assign(new Error(data.error || 'Sync failed'), data);
        return data;
    });

export const fetchJobApplications = (jobId) => {
    const qs = new URLSearchParams({ job_id: jobId }).toString();
    return apiClient(`${BASE}/applications/?${qs}`).then(r => r.json());
};
