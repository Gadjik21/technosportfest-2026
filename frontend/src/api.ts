import type { components } from "./api-types";

export type S = components["schemas"];
export type User = S["User"];
export type Competition = S["Competition"];
export type Discipline = S["Discipline"];
export type Profile = S["Profile"];
export type Registration = S["Registration"];
export type Participant = S["Participant"];
export type Result = S["Result"];
export type ResultDraft = S["ResultDraft"];
export type News = S["News"];
export type Document = S["Document"];
export type Rating = S["Rating"];
export type MyRating = S["MyRating"];
export type Page<T> = { items: T[]; page: number; pageSize: number; total: number };

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public fields: Record<string, string> = {}) {
    super(message);
  }
}

export async function request<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    method: options.method ?? "GET",
    headers: options.body === undefined ? undefined : { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  if (!response.ok) {
    let detail: { code?: string; message?: string; fields?: Record<string, string> } = {};
    try { detail = await response.json(); } catch { /* Proxy errors may be plain text. */ }
    throw new ApiError(response.status, detail.code ?? "HTTP_ERROR", detail.message ?? `Ошибка сервера (${response.status})`, detail.fields ?? {});
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

const query = (params: Record<string, string | number | undefined>) => {
  const value = new URLSearchParams();
  Object.entries(params).forEach(([key, item]) => { if (item !== undefined && item !== "") value.set(key, String(item)); });
  return value.size ? `?${value}` : "";
};

export const api = {
  me: () => request<User>("/auth/me"),
  login: (body: S["LoginRequest"]) => request<User>("/auth/login", { method: "POST", body }),
  register: (body: S["RegisterRequest"]) => request<User>("/auth/register", { method: "POST", body }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  profile: () => request<Profile>("/me"),
  updateProfile: (body: S["ProfilePatch"]) => request<Profile>("/me", { method: "PATCH", body }),
  disciplines: () => request<Discipline[]>("/disciplines"),
  competitions: (params: { page?: number; pageSize?: number; status?: string; disciplineId?: string } = {}) => request<Page<Competition>>(`/competitions${query(params)}`),
  competition: (id: string) => request<Competition>(`/competitions/${id}`),
  createCompetition: (body: S["CompetitionCreate"]) => request<Competition>("/competitions", { method: "POST", body }),
  updateCompetition: (id: string, body: S["CompetitionPatch"]) => request<Competition>(`/competitions/${id}`, { method: "PATCH", body }),
  publishCompetition: (id: string) => request<Competition>(`/competitions/${id}/publish`, { method: "POST" }),
  registerForCompetition: (id: string) => request<Registration>(`/competitions/${id}/registrations`, { method: "POST" }),
  myRegistrations: (page = 1) => request<Page<Registration>>(`/me/registrations${query({ page })}`),
  participants: (id: string, page = 1) => request<Page<Participant>>(`/competitions/${id}/participants${query({ page, pageSize: 100 })}`),
  drafts: (id: string, page = 1) => request<Page<ResultDraft>>(`/competitions/${id}/results/drafts${query({ page, pageSize: 100 })}`),
  saveDraft: (id: string, registrationId: string, body: S["ResultDraftRequest"]) => request<ResultDraft>(`/competitions/${id}/results/${registrationId}`, { method: "PUT", body }),
  publishResults: (id: string) => request<S["PublishResultsResponse"]>(`/competitions/${id}/results/publish`, { method: "POST" }),
  results: (id: string, page = 1) => request<Page<Result>>(`/competitions/${id}/results${query({ page })}`),
  myResults: (page = 1) => request<Page<Result>>(`/me/results${query({ page })}`),
  ratings: (page = 1, disciplineId?: string) => request<Rating>(`/ratings${query({ page, disciplineId })}`),
  myRating: (disciplineId?: string) => request<MyRating>(`/me/rating${query({ disciplineId })}`),
  news: (page = 1) => request<Page<News>>(`/news${query({ page })}`),
  newsItem: (id: string) => request<News>(`/news/${id}`),
  createNews: (body: S["NewsCreate"]) => request<News>("/news", { method: "POST", body }),
  updateNews: (id: string, body: S["NewsPatch"]) => request<News>(`/news/${id}`, { method: "PATCH", body }),
  documents: (page = 1, category?: string) => request<Page<Document>>(`/documents${query({ page, category })}`),
  createDocument: (body: S["DocumentCreate"]) => request<Document>("/documents", { method: "POST", body }),
  updateDocument: (id: string, body: S["DocumentPatch"]) => request<Document>(`/documents/${id}`, { method: "PATCH", body }),
};
