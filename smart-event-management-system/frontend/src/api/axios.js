import axios from "axios";

export const API_BASE_URL = (() => {
  if (typeof window === "undefined") return "/api";
  const raw = (import.meta.env.VITE_API_URL || "").trim();
  const isLocal = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";

  // In local development or through Vite, always route via relative "/api" through Vite's proxy.
  // This avoids Windows IPv6 (::1) socket hangs, eliminates CORS preflight latency,
  // and allows seamless connections whether using localhost, 127.0.0.1, LAN IP, or Cloudflare Tunnel.
  if (isLocal) {
    if (raw && !raw.includes("localhost") && !raw.includes("127.0.0.1")) {
      const clean = raw.replace(/\/+$/, "");
      return clean.endsWith("/api") ? clean : `${clean}/api`;
    }
    return "/api";
  }

  // When accessed via external URL or production domain
  if (raw) {
    if (raw.includes("localhost") || raw.includes("127.0.0.1")) {
      return "/api";
    }
    const clean = raw.replace(/\/+$/, "");
    return clean.endsWith("/api") ? clean : `${clean}/api`;
  }

  return "/api";
})();

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("sems-access-token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let isRefreshing = false;
let pendingQueue = [];

const processQueue = (error, token = null) => {
  pendingQueue.forEach((p) => (error ? p.reject(error) : p.resolve(token)));
  pendingQueue = [];
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry && !originalRequest.url.includes("/auth/")) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          pendingQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return api(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshToken = localStorage.getItem("sems-refresh-token");
        if (!refreshToken) throw new Error("No refresh token");

        const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, { refresh_token: refreshToken });
        localStorage.setItem("sems-access-token", data.access_token);
        localStorage.setItem("sems-refresh-token", data.refresh_token);

        processQueue(null, data.access_token);
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        localStorage.removeItem("sems-access-token");
        localStorage.removeItem("sems-refresh-token");
        localStorage.removeItem("sems-user");
        window.location.href = "/login";
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default api;
