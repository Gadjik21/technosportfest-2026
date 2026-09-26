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
export type Task = S["Task"];
export type Submission = S["Submission"];
export type SubmissionForGrading = S["SubmissionForGrading"];
export type Standings = S["Standings"];
export type Role = S["Role"];
export type AdminUser = S["AdminUser"];
export type MailingRecipient = { id: string; email: string; fullName: string | null; roleName: string; locality: string | null; education: string | null; disciplineIds: string[] };
export type PermissionGroup = S["PermissionGroup"];
export type Page<T> = { items: T[]; page: number; pageSize: number; total: number };

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public fields: Record<string, string> = {}) {
    super(message);
  }
}

// Базовый URL API строим от origin, а не относительным путём: если страница открыта по адресу
// вида http://user:pass@host/, браузер отклоняет относительные fetch-пути ошибкой
// "Request cannot be constructed from a URL that includes credentials" (origin всегда без логина/пароля).
const API_BASE = `${window.location.origin}/api/v1`;

export async function request<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
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
  removeRegistration: (competitionId: string, registrationId: string) => request<void>(`/competitions/${competitionId}/registrations/${registrationId}`, { method: "DELETE" }),
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
  tasks: (competitionId: string) => request<Task[]>(`/competitions/${competitionId}/tasks`),
  createTask: (competitionId: string, body: S["TaskCreateRequest"]) => request<Task>(`/competitions/${competitionId}/tasks`, { method: "POST", body }),
  updateTask: (competitionId: string, taskId: string, body: S["TaskPatchRequest"]) => request<Task>(`/competitions/${competitionId}/tasks/${taskId}`, { method: "PATCH", body }),
  deleteTask: (competitionId: string, taskId: string) => request<void>(`/competitions/${competitionId}/tasks/${taskId}`, { method: "DELETE" }),
  submitSolution: (competitionId: string, taskId: string, body: S["SubmissionRequest"]) => request<Submission>(`/competitions/${competitionId}/tasks/${taskId}/submission`, { method: "PUT", body }),
  mySubmissions: (competitionId: string) => request<Submission[]>(`/competitions/${competitionId}/my-submissions`),
  submissionsForGrading: (competitionId: string) => request<SubmissionForGrading[]>(`/competitions/${competitionId}/submissions`),
  gradeSubmission: (competitionId: string, submissionId: string, body: S["GradeRequest"]) => request<Submission>(`/competitions/${competitionId}/submissions/${submissionId}`, { method: "PATCH", body }),
  finishContest: (competitionId: string) => request<S["FinishContestResponse"]>(`/competitions/${competitionId}/finish-contest`, { method: "POST" }),
  standings: (competitionId: string) => request<Standings>(`/competitions/${competitionId}/standings`),
  permissionCatalog: () => request<PermissionGroup[]>("/admin/permissions"),
  roles: () => request<Role[]>("/admin/roles"),
  createRole: (body: S["RoleCreate"]) => request<Role>("/admin/roles", { method: "POST", body }),
  updateRole: (id: string, body: S["RolePatch"]) => request<Role>(`/admin/roles/${id}`, { method: "PATCH", body }),
  deleteRole: (id: string) => request<void>(`/admin/roles/${id}`, { method: "DELETE" }),
  setRolePermissions: (id: string, permissions: string[]) => request<Role>(`/admin/roles/${id}/permissions`, { method: "PUT", body: { permissions } }),
  users: (page = 1, pageSize = 100) => request<Page<AdminUser>>(`/admin/users${query({ page, pageSize })}`),
  mailingRecipients: () => request<MailingRecipient[]>("/admin/mailing-recipients"),
  assignRole: (userId: string, roleId: string) => request<AdminUser>(`/admin/users/${userId}/role`, { method: "PUT", body: { roleId } }),
};
