const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json", ...init?.headers },
    ...init,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export interface HealthResponse {
  status: string;
  timestamp: string;
  service: string;
}

export interface MessageResponse {
  message: string;
}

export const api = {
  getHealth: () => request<HealthResponse>("/health"),
  getHello: (name?: string) =>
    request<MessageResponse>(`/hello${name ? `?name=${encodeURIComponent(name)}` : ""}`),
};
