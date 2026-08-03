import { BACKEND_URL } from "./config/api";
import { getMockData } from "./mockData";

/**
 * Creates a fake Response object wrapping mock data.
 * Used when the backend is unreachable (e.g. Netlify demo deployment).
 */
function mockResponse(data) {
  const body = JSON.stringify(data);
  return new Response(body, {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Central API client.
 * On network failure (backend unavailable), automatically falls back to
 * realistic mock data so the app works fully in demo / offline mode.
 */
export async function apiClient(endpoint, options = {}) {
  const headers = new Headers(options.headers || {});

  const config = {
    ...options,
    headers,
  };

  let url = endpoint;
  if (endpoint.startsWith("/")) {
    url = `${BACKEND_URL}${endpoint}`;
  }

  try {
    const response = await fetch(url, config);

    // If server responds with 4xx/5xx, fall through to mock for GET requests
    // so the UI still renders meaningful data instead of an empty/error state.
    if (!response.ok && (options.method || "GET") === "GET") {
      const data = getMockData(url || endpoint);
      return mockResponse(data);
    }

    return response;
  } catch {
    // Network error — backend is completely unreachable (typical on Netlify).
    // For mutations (POST/PATCH/PUT/DELETE) return a fake 200 so forms don't crash.
    const data = getMockData(url || endpoint);
    return mockResponse(data);
  }
}

// No-op stubs kept for any components that still import these
export const setToken = () => {};
export const getToken = () => null;
export const clearToken = () => {};
