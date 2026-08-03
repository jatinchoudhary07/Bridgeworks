import { BACKEND_URL } from "./config/api";

export async function apiClient(endpoint, options = {}) {
  const headers = new Headers(options.headers || {});

  const config = {
    ...options,
    headers,
  };

  let url = endpoint;
  if (endpoint.startsWith('/')) {
    url = `${BACKEND_URL}${endpoint}`;
  }

  const response = await fetch(url, config);
  return response;
}

// No-op stubs kept for any components that still import these
export const setToken = () => {};
export const getToken = () => null;
export const clearToken = () => {};
