const API_BASE = '/api';

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
  } catch (e) {
    throw new Error(`Network error: could not reach server (${e.message})`);
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `Server error ${res.status}: ${res.statusText}` }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export const api = {
  createJob: (data) => request('/jobs/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  createDownloadJob: (url) => request('/jobs/download', {
    method: 'POST',
    body: JSON.stringify({ url }),
  }),

  getJob: (jobId) => request(`/jobs/${jobId}`),

  getVideoUrl: (jobId) => `${API_BASE}/video/${jobId}`,

  getVideoDownloadUrl: (jobId) => `${API_BASE}/video/${jobId}?download=1`,

  getMp3Url: (jobId) => `${API_BASE}/video/${jobId}/mp3`,

  getSSEUrl: (jobId) => `${API_BASE}/jobs/${jobId}/stream`,
};
