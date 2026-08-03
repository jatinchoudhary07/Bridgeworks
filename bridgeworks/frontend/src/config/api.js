// Use VITE_API_URL if set (e.g. staging/prod override), otherwise fall back to
// an empty string so every /api/... request is sent as a relative URL.
// Vite dev-server proxies /api → http://localhost:8000 in local dev;
// nginx proxies /api → http://backend:8000 in the deployed container.
export const BACKEND_URL = import.meta.env.VITE_API_URL || '';
