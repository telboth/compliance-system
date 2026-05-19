import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
const DEV_ROLE_KEY = "xlent_dev_role";

const ROLE_TO_NAME: Record<string, string> = {
  admin: "Ada Admin",
  c_level: "Sigurd Sjef",
  compliance_officer: "Carl Compliance",
  controller: "Kari Controller",
  readonly: "Roy Readonly",
};

export const apiClient = axios.create({
  baseURL,
  timeout: 60_000,
});

apiClient.interceptors.request.use((config) => {
  try {
    const role = (localStorage.getItem(DEV_ROLE_KEY) || "admin").trim().toLowerCase();
    if (role) {
      config.headers = config.headers ?? {};
      config.headers["X-Actor-Role"] = role;
      config.headers["X-Actor-Name"] = ROLE_TO_NAME[role] ?? role;
    }
  } catch {
    // Ignorer localStorage-feil; backend vil eventuelt returnere 401/403.
  }
  return config;
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
