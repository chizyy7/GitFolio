/**
 * Typed API client for the GitFolio FastAPI backend.
 *
 * Works in both Server Components (no token, `cache: "no-store"`) and Client
 * Components (bearer token pulled from localStorage).
 */

import type {
  AIHealth,
  AuthResponse,
  ChatResponse,
  ChatTurn,
  CommitDetail,
  CommitListResponse,
  DashboardResponse,
  FileContent,
  HeatmapResponse,
  IndexStatus,
  PushRequest,
  PushResponse,
  RepoDetail,
  RepoLanguages,
  RepoRead,
  ReviewResponse,
  SearchResponse,
  SkillProfile,
  StreakStats,
  UserMe,
  UserProfile,
  UserRead,
} from "@/lib/types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api").replace(/\/$/, "");
export const TOKEN_KEY = "gitfolio.token";

// --------------------------------------------------------------------------- //
// Errors
// --------------------------------------------------------------------------- //
export class ApiError extends Error {
  status: number;
  detail: string;
  fieldErrors: { field: string; message: string }[];

  constructor(status: number, detail: string, fieldErrors: { field: string; message: string }[] = []) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.fieldErrors = fieldErrors;
  }

  /** True when the backend is simply not reachable / still starting up. */
  get isNetworkError(): boolean {
    return this.status === 0;
  }
}

// --------------------------------------------------------------------------- //
// Token helpers (client-side only)
// --------------------------------------------------------------------------- //
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

// --------------------------------------------------------------------------- //
// Core request
// --------------------------------------------------------------------------- //
interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  token?: string | null;
  /** Server Components should pass `{ cache: "no-store" }` for live data. */
  cache?: RequestCache;
  next?: { revalidate?: number | false; tags?: string[] };
  signal?: AbortSignal;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, token, cache, next, signal } = options;

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  // Prefer an explicit token, otherwise fall back to localStorage (client only).
  const authToken = token ?? (typeof window !== "undefined" ? getToken() : null);
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: cache ?? (method === "GET" ? undefined : "no-store"),
      next,
      signal,
    });
  } catch (error) {
    throw new ApiError(
      0,
      `Cannot reach the GitFolio API at ${API_URL}. Is the backend running?`,
      [],
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  const payload = text ? safeJson(text) : null;

  if (!response.ok) {
    const detail =
      (payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : null) ?? `Request failed with status ${response.status}`;

    const rawErrors =
      payload && typeof payload === "object" && "errors" in payload
        ? ((payload as { errors: { field: string; message: string }[] }).errors ?? [])
        : [];

    throw new ApiError(response.status, detail, rawErrors);
  }

  return payload as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

// --------------------------------------------------------------------------- //
// Auth
// --------------------------------------------------------------------------- //
export const authApi = {
  register(input: {
    username: string;
    email: string;
    password: string;
    display_name?: string;
  }): Promise<AuthResponse> {
    return request<AuthResponse>("/auth/register", { method: "POST", body: input });
  },

  login(username: string, password: string): Promise<AuthResponse> {
    return request<AuthResponse>("/auth/login", {
      method: "POST",
      body: { username, password },
    });
  },

  me(token?: string | null): Promise<UserMe> {
    return request<UserMe>("/auth/me", { token, cache: "no-store" });
  },

  updateProfile(input: Partial<Pick<UserMe, "display_name" | "bio" | "location" | "company" | "website" | "avatar_url">>): Promise<UserMe> {
    return request<UserMe>("/auth/me", { method: "PATCH", body: input });
  },

  refresh(): Promise<AuthResponse> {
    return request<AuthResponse>("/auth/refresh", { method: "POST" });
  },

  checkUsername(username: string): Promise<{ username: string; available: boolean }> {
    return request(`/auth/check-username/${encodeURIComponent(username)}`, { cache: "no-store" });
  },
};

// --------------------------------------------------------------------------- //
// Profiles
// --------------------------------------------------------------------------- //
export const usersApi = {
  list(params: { q?: string; page?: number; per_page?: number } = {}, token?: string | null): Promise<UserRead[]> {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
    });
    const query = search.toString();
    return request<UserRead[]>(`/users${query ? `?${query}` : ""}`, { token, cache: "no-store" });
  },

  profile(username: string, token?: string | null): Promise<UserProfile> {
    return request<UserProfile>(`/users/${encodeURIComponent(username)}`, {
      token,
      cache: "no-store",
    });
  },

  languages(username: string): Promise<Record<string, number>> {
    return request(`/users/${encodeURIComponent(username)}/languages`, { cache: "no-store" });
  },
};

// --------------------------------------------------------------------------- //
// Repositories
// --------------------------------------------------------------------------- //
export const reposApi = {
  create(input: {
    name: string;
    description?: string | null;
    visibility?: "Public" | "Private";
    primary_language?: string | null;
    topics?: string[];
    auto_index?: boolean;
  }): Promise<RepoRead> {
    return request<RepoRead>("/repos", { method: "POST", body: input });
  },

  list(
    username: string,
    params: {
      q?: string;
      language?: string;
      pinned_only?: boolean;
      sort?: "updated" | "created" | "name" | "stars" | "commits";
      page?: number;
      per_page?: number;
    } = {},
    token?: string | null,
  ): Promise<RepoRead[]> {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
    });
    const query = search.toString();
    return request<RepoRead[]>(`/repos/${encodeURIComponent(username)}${query ? `?${query}` : ""}`, {
      token,
      cache: "no-store",
    });
  },

  detail(username: string, repoName: string, token?: string | null): Promise<RepoDetail> {
    return request<RepoDetail>(
      `/repos/${encodeURIComponent(username)}/${encodeURIComponent(repoName)}`,
      { token, cache: "no-store" },
    );
  },

  file(
    username: string,
    repoName: string,
    path: string,
    ref?: string | null,
    token?: string | null,
  ): Promise<FileContent> {
    const search = new URLSearchParams({ path });
    if (ref) search.set("ref", ref);
    return request<FileContent>(
      `/repos/${encodeURIComponent(username)}/${encodeURIComponent(repoName)}/blob?${search}`,
      { token, cache: "no-store" },
    );
  },

  languages(username: string, repoName: string): Promise<RepoLanguages> {
    return request<RepoLanguages>(
      `/repos/${encodeURIComponent(username)}/${encodeURIComponent(repoName)}/languages`,
      { cache: "no-store" },
    );
  },

  update(repoId: string, input: Partial<RepoRead>): Promise<RepoRead> {
    return request<RepoRead>(`/repos/${repoId}`, { method: "PATCH", body: input });
  },

  remove(repoId: string): Promise<void> {
    return request<void>(`/repos/${repoId}`, { method: "DELETE" });
  },

  status(repoId: string): Promise<Record<string, unknown>> {
    return request(`/repos/${repoId}/status`, { cache: "no-store" });
  },
};

// --------------------------------------------------------------------------- //
// Version control
// --------------------------------------------------------------------------- //
export const vcsApi = {
  push(repoId: string, payload: PushRequest): Promise<PushResponse> {
    return request<PushResponse>(`/repos/${repoId}/push`, { method: "POST", body: payload });
  },

  commits(
    repoId: string,
    params: { page?: number; per_page?: number; author?: string } = {},
  ): Promise<CommitListResponse> {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
    });
    const query = search.toString();
    return request<CommitListResponse>(`/repos/${repoId}/commits${query ? `?${query}` : ""}`, {
      cache: "no-store",
    });
  },

  commit(repoId: string, hash: string): Promise<CommitDetail> {
    return request<CommitDetail>(`/repos/${repoId}/commits/${hash}`, { cache: "no-store" });
  },

  reindex(repoId: string, force = true): Promise<{ status: string }> {
    return request(`/repos/${repoId}/reindex?force=${force}`, { method: "POST" });
  },
};

// --------------------------------------------------------------------------- //
// AI
// --------------------------------------------------------------------------- //
export const aiApi = {
  chat(input: {
    repo_id: string;
    question: string;
    top_k?: number;
    history?: ChatTurn[];
    file_filter?: string | null;
  }): Promise<ChatResponse> {
    const history = (input.history ?? []).map((turn) => ({
      role: turn.role,
      content: turn.content,
    }));
    return request<ChatResponse>("/ai/chat", {
      method: "POST",
      body: { ...input, history },
    });
  },

  search(input: {
    repo_id: string;
    query: string;
    top_k?: number;
    summarise?: boolean;
  }): Promise<SearchResponse> {
    return request<SearchResponse>("/ai/search", { method: "POST", body: input });
  },

  reviews(commitId: string): Promise<ReviewResponse> {
    return request<ReviewResponse>(`/ai/reviews/${commitId}`, { cache: "no-store" });
  },

  rerunReview(commitId: string, sync = false): Promise<ReviewResponse> {
    return request<ReviewResponse>(`/ai/reviews/${commitId}?sync=${sync}`, { method: "POST" });
  },

  index(repoId: string, options: { sync?: boolean; force?: boolean } = {}): Promise<IndexStatus> {
    const search = new URLSearchParams({
      sync: String(options.sync ?? false),
      force: String(options.force ?? true),
    });
    return request<IndexStatus>(`/ai/index/${repoId}?${search}`, { method: "POST" });
  },

  dropIndex(repoId: string): Promise<void> {
    return request<void>(`/ai/index/${repoId}`, { method: "DELETE" });
  },

  refreshSkills(sync = true): Promise<SkillProfile> {
    return request<SkillProfile>(`/ai/skills/refresh?sync=${sync}`, { method: "POST" });
  },

  health(): Promise<AIHealth> {
    return request<AIHealth>("/ai/health", { cache: "no-store" });
  },
};

// --------------------------------------------------------------------------- //
// Dashboard
// --------------------------------------------------------------------------- //
export const dashboardApi = {
  get(username: string, token?: string | null): Promise<DashboardResponse> {
    return request<DashboardResponse>(`/dashboard/${encodeURIComponent(username)}`, {
      token,
      cache: "no-store",
    });
  },

  heatmap(username: string, weeks = 53): Promise<HeatmapResponse> {
    return request<HeatmapResponse>(
      `/dashboard/${encodeURIComponent(username)}/heatmap?weeks=${weeks}`,
      { cache: "no-store" },
    );
  },

  stats(username: string): Promise<StreakStats> {
    return request<StreakStats>(`/dashboard/${encodeURIComponent(username)}/stats`, {
      cache: "no-store",
    });
  },
};

export const systemApi = {
  health(): Promise<{ status: string; version: string; environment: string }> {
    return request("/health", { cache: "no-store" });
  },
};
