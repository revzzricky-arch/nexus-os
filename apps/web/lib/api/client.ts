"use client";

// Scaffold API client - typed fetch wrapper with Zod validation placeholder
// No real LLM calls yet

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FetchOptions extends RequestInit {
  params?: Record<string, string>;
}

export async function apiFetch<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const url = new URL(`${API_URL}${endpoint}`);
  if (options.params) {
    Object.entries(options.params).forEach(([k, v]) => url.searchParams.append(k, v));
  }

  // For scaffold, include dev token via header, NOT URL query
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  // In scaffold, we don't enforce auth for health/version
  // For future protected routes: Authorization: Bearer <token> or X-Nexus-Token header
  // NEVER ?token= in URL per security requirement

  const res = await fetch(url.toString(), {
    ...options,
    headers,
  });

  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }

  return res.json() as Promise<T>;
}

export const api = {
  health: () => apiFetch<{ status: string; service: string }>("/health"),
  version: () => apiFetch<any>("/version"),
  missions: {
    list: () => apiFetch<any>("/api/v1/missions"),
    get: (id: string) => apiFetch<any>(`/api/v1/missions/${id}`),
  },
  tools: {
    list: () => apiFetch<any>("/api/v1/tools"),
  },
};
