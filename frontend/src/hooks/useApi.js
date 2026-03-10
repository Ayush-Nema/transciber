const API_BASE = '/api';

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export const api = {
  fetchVideoInfo: (url) => request('/jobs/video-info', {
    method: 'POST',
    body: JSON.stringify({ url }),
  }),

  createJob: (data) => request('/jobs/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  getJob: (jobId) => request(`/jobs/${jobId}`),

  listJobs: (limit = 20) => request(`/jobs/?limit=${limit}`),

  deleteJob: (jobId) => request(`/jobs/${jobId}`, { method: 'DELETE' }),

  getVideoUrl: (jobId) => `${API_BASE}/video/${jobId}`,

  getSSEUrl: (jobId) => `${API_BASE}/jobs/${jobId}/stream`,
};
