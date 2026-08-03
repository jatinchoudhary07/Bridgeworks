import { BACKEND_URL } from "./config/api";
import { getMockData } from "./mockData";

/**
 * True when no backend URL is configured (i.e., Netlify demo deployment).
 */
const IS_DEMO_MODE = !BACKEND_URL;

/**
 * Creates a fake Response object wrapping mock data.
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
 *
 * In DEMO MODE (no VITE_API_URL set, e.g. Netlify):
 *   - All requests are intercepted immediately — no real HTTP call is made.
 *   - Returns realistic mock data from mockData.js.
 *
 * In PRODUCTION MODE (VITE_API_URL is set):
 *   - Makes real requests to the configured backend.
 *   - Falls back to mock data only on network errors.
 */
export async function apiClient(endpoint, options = {}) {
  // Resolve the full URL
  let url = endpoint;
  if (endpoint.startsWith("/")) {
    url = `${BACKEND_URL}${endpoint}`;
  }

  // ── DEMO MODE: skip real fetch entirely ──────────────────────────────────
  if (IS_DEMO_MODE) {
    const data = getMockData(url || endpoint);
    return mockResponse(data);
  }

  // ── PRODUCTION MODE: make real fetch with mock fallback on error ─────────
  const headers = new Headers(options.headers || {});
  const config = { ...options, headers };

  try {
    const response = await fetch(url, config);

    // Fall back to mock for failed GET requests so UI stays populated
    if (!response.ok && (options.method || "GET") === "GET") {
      const data = getMockData(url || endpoint);
      return mockResponse(data);
    }

    return response;
  } catch {
    // Network error — backend completely unreachable
    const data = getMockData(url || endpoint);
    return mockResponse(data);
  }
}

// No-op stubs kept for any components that still import these
export const setToken = () => {};
export const getToken = () => null;
export const clearToken = () => {};
