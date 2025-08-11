// Use same-origin requests through Next.js rewrites
export function apiBase(): string {
  return typeof window !== 'undefined' ? '' : 'http://localhost:8001';
}

export async function apiFetch(path: string, opts: RequestInit = {}) {
  const headers = new Headers(opts.headers || {});
  if (typeof window !== 'undefined') {
    const t = localStorage.getItem('access_token');
    if (t && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${t}`);
  }
  const isFD = typeof FormData !== 'undefined' && (opts.body instanceof FormData);
  if (!isFD && !headers.has('Content-Type') && typeof opts.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }
  return fetch(`${apiBase()}${path}`, { ...opts, headers, cache: 'no-store' });
}

// Upload API that properly handles FormData
export async function uploadClips(file: File, clips: any[]) {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('clips', JSON.stringify(clips));
  
  const res = await apiFetch('/api/v1/video/upload-and-clip', { 
    method: 'POST', 
    body: fd 
  });
  
  if (!res.ok) {
    throw new Error(`Upload ${res.status}`);
  }
  
  return res.json();
}

// Auth API methods
export async function loginUser(email: string, password: string) {
  // FastAPI OAuth2 expects form data with 'username' field
  const formData = new URLSearchParams();
  formData.append('username', email);
  formData.append('password', password);
  
  const res = await fetch(`${apiBase()}/api/v1/auth/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: formData
  });
  
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Login failed: ${res.status}`);
  }
  
  const data = await res.json();
  
  // Store the access token in localStorage
  if (typeof window !== 'undefined' && data.access_token) {
    localStorage.setItem('access_token', data.access_token);
  }
  
  // Return user data in expected format
  return {
    user: {
      email: data.user_email,
      id: 0,
      username: data.user_email.split('@')[0],
      credits: 0,
      subscription_plan: 'free',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    },
    access_token: data.access_token,
    token_type: data.token_type
  };
}

export async function getCurrentUser() {
  const res = await apiFetch('/api/v1/auth/me');
  
  if (!res.ok) {
    throw new Error(`Auth check failed: ${res.status}`);
  }
  
  return res.json();
}

export async function registerUser(email: string, username: string, password: string) {
  const res = await apiFetch('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, username, password })
  });
  
  if (!res.ok) {
    throw new Error(`Registration failed: ${res.status}`);
  }
  
  return res.json();
}

export async function logoutUser() {
  const res = await apiFetch('/api/v1/auth/logout', {
    method: 'POST'
  });
  
  if (!res.ok) {
    throw new Error(`Logout failed: ${res.status}`);
  }
  
  // Clear the token from localStorage
  if (typeof window !== 'undefined') {
    localStorage.removeItem('access_token');
  }
  
  return res.json();
}

export async function getJobs() {
  const res = await apiFetch('/api/v1/jobs/history');
  
  if (!res.ok) {
    throw new Error(`Failed to fetch jobs: ${res.status}`);
  }
  
  return res.json();
}

export async function getJob(jobId: string) {
  const res = await apiFetch(`/api/v1/jobs/${jobId}`);
  
  if (!res.ok) {
    throw new Error(`Failed to fetch job: ${res.status}`);
  }
  
  return res.json();
}