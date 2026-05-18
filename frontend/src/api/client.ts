import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export const apiClient = axios.create({
  baseURL,
  timeout: 60_000,
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Logger til konsollen i utvikling; i produksjon vil dette gå til vår
    // sentrale logging-pipeline (kommer i Sprint 6).
    if (import.meta.env.DEV) {
      console.warn("API-feil", {
        url: error.config?.url,
        status: error.response?.status,
        data: error.response?.data,
      });
    }
    return Promise.reject(error);
  },
);
