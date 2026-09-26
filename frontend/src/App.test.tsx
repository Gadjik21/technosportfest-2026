import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";

const competition = {
  id: "c1", title: "Кубок Дагестана", discipline: { id: "d1", name: "Программирование" },
  startsAt: "2026-10-20T10:00:00Z", endsAt: "2026-10-20T17:00:00Z", registrationDeadline: "2026-10-19T18:00:00Z",
  format: "online", description: "Открытый турнир", status: "published", registrationOpen: true, viewerRegistrationId: null,
  createdAt: "2026-09-01T10:00:00Z",
};
const athlete = { id: "a1", email: "athlete@example.com", role: "athlete", permissions: [], createdAt: "2026-09-01T10:00:00Z" };
const organizer = { id: "o1", email: "org@example.com", role: "organizer", permissions: ["competitions.view", "competitions.create", "competitions.edit", "competitions.publish", "contests.tasks", "contests.grade", "results.view", "results.save", "results.publish", "news.view", "documents.view"], createdAt: "2026-09-01T10:00:00Z" };
const copywriter = { id: "o2", email: "copy@example.com", role: "Копирайтер", permissions: ["news.view", "news.create", "news.edit"], createdAt: "2026-09-01T10:00:00Z" };
const page = <T,>(items: T[]) => ({ items, page: 1, pageSize: 100, total: items.length });
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });

beforeEach(() => { window.history.replaceState({}, "", "/"); vi.stubGlobal("scrollTo", vi.fn()); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("основной путь MVP", () => {
  it("очищает ошибку входа при переходе к регистрации", async () => {
    window.history.replaceState({}, "", "/login");
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/auth/me")
      ? json({ code: "UNAUTHENTICATED", message: "Войдите" }, 401)
      : json({ code: "INVALID_CREDENTIALS", message: "Неверный email или пароль." }, 401)));
    const user = userEvent.setup(); render(<App />);
    await user.type(screen.getByLabelText("Email"), "absent@example.com");
    await user.type(screen.getByLabelText("Пароль"), "wrong-password-123");
    await user.click(screen.getByRole("button", { name: "Войти" }));
    expect(await screen.findByText("Неверный email или пароль.")).toBeTruthy();
    await user.click(screen.getByRole("link", { name: "Зарегистрироваться" }));
    expect(screen.getByRole("heading", { name: "Создать аккаунт" })).toBeTruthy();
    expect(screen.queryByText("Неверный email или пароль.")).toBeNull();
  });

  it("возвращает спортсмена к соревнованию после входа", async () => {
    window.history.replaceState({}, "", "/login?next=%2Fcompetitions%2Fc1");
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.endsWith("/auth/me")) return json({ code: "UNAUTHENTICATED", message: "Войдите" }, 401);
      if (url.endsWith("/auth/login")) return json(athlete);
      if (url.endsWith("/competitions/c1")) return json(competition);
      if (url.endsWith("/competitions/c1/results?page=1")) return json(page([]));
      throw new Error(`Unexpected ${url}`);
    }));
    const user = userEvent.setup(); render(<App />);
    await user.type(screen.getByLabelText("Email"), "athlete@example.com");
    await user.type(screen.getByLabelText("Пароль"), "long-demo-password");
    await user.click(screen.getByRole("button", { name: "Войти" }));
    expect(await screen.findByRole("button", { name: "Подать заявку" })).toBeTruthy();
    expect(window.location.pathname).toBe("/competitions/c1");
  });

  it("не открывает кабинет спортсмена без входа", async () => {
    window.history.replaceState({}, "", "/cabinet");
    const fetchMock = vi.fn(async (_url: string) => json({ code: "UNAUTHENTICATED", message: "Войдите" }, 401));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    expect(await screen.findByText("Доступ закрыт")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/auth/me");
  });

  it("входит спортсменом, показывает кабинет и отправляет заявку", async () => {
    const calls: { path: string; method: string }[] = [];
    let loggedIn = false;
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      const path = url.replace("/api/v1", ""); const method = init?.method ?? "GET";
      calls.push({ path, method });
      if (path === "/auth/me") return loggedIn ? json(athlete) : json({ code: "UNAUTHENTICATED", message: "Войдите" }, 401);
      if (path === "/auth/login") { loggedIn = true; return json(athlete); }
      if (path === "/me") return json({ user: { ...athlete, permissions: [] }, fullName: "Амина Алиева", education: null, locality: null, disciplineIds: [] });
      if (path.startsWith("/me/registrations")) return json(page([]));
      if (path.startsWith("/me/results")) return json(page([]));
      if (path.startsWith("/me/rating")) return json({ athleteId: "a1", disciplineId: null, points: 0, rank: null, resultsCount: 0 });
      if (path === "/competitions/c1") return json(competition);
      if (path === "/competitions/c1/registrations") return json({ id: "r1", competition, athleteId: "a1", createdAt: "2026-09-01T10:00:00Z" }, 201);
      if (path.startsWith("/competitions/c1/results")) return json(page([]));
      throw new Error(`Unexpected ${method} ${path}`);
    }));
    window.history.replaceState({}, "", "/login");
    const user = userEvent.setup(); render(<App />);
    await user.type(screen.getByLabelText("Email"), "athlete@example.com");
    await user.type(screen.getByLabelText("Пароль"), "long-demo-password");
    await user.click(screen.getByRole("button", { name: "Войти" }));
    expect(await screen.findByText("Привет, Амина!")).toBeTruthy();
    window.history.pushState({}, "", "/competitions/c1"); window.dispatchEvent(new PopStateEvent("popstate"));
    const register = await screen.findByRole("button", { name: "Подать заявку" });
    await user.click(register);
    expect(await screen.findByText(/Заявка подана/)).toBeTruthy();
    expect(calls).toContainEqual({ path: "/competitions/c1/registrations", method: "POST" });
  });

  it("сохраняет черновик и публикует результаты организатором", async () => {
    let saved = false; let published = false;
    const calls: { path: string; method: string; body?: unknown }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      const path = url.replace("/api/v1", ""); const method = init?.method ?? "GET";
      calls.push({ path, method, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      if (path === "/auth/me") return json(organizer);
      if (path === "/competitions/c1") return json({ ...competition, status: published ? "completed" : "published" });
      if (path.startsWith("/competitions/c1/participants")) return json(page([{ registrationId: "r1", athleteId: "a1", fullName: "Амина Алиева", education: null, locality: "Махачкала", registeredAt: "2026-09-01T10:00:00Z" }]));
      if (path.startsWith("/competitions/c1/results/drafts")) return json(page(saved ? [{ id: "res1", registrationId: "r1", competitionId: "c1", athleteId: "a1", fullName: "Амина Алиева", place: 1, scoreText: "4 задачи", status: "draft", updatedAt: "2026-10-20T18:00:00Z" }] : []));
      if (path === "/competitions/c1/results/r1" && method === "PUT") { saved = true; return json({ id: "res1", registrationId: "r1", competitionId: "c1", athleteId: "a1", fullName: "Амина Алиева", place: 1, scoreText: "4 задачи", status: "draft", updatedAt: "2026-10-20T18:00:00Z" }); }
      if (path === "/competitions/c1/results/publish" && method === "POST") { published = true; return json({ competitionId: "c1", status: "completed", publishedCount: 1, publishedAt: "2026-10-20T18:00:00Z" }); }
      if (path.startsWith("/competitions/c1/results")) return json(page(published ? [{ id: "res1", registrationId: "r1", competitionId: "c1", athleteId: "a1", fullName: "Амина Алиева", place: 1, scoreText: "4 задачи", points: 100, publishedAt: "2026-10-20T18:00:00Z" }] : []));
      throw new Error(`Unexpected ${method} ${path}`);
    }));
    window.history.replaceState({}, "", "/manage/competitions/c1");
    const user = userEvent.setup(); render(<App />);
    const place = await screen.findByLabelText("Место: Амина Алиева");
    await user.type(place, "1");
    await user.type(screen.getByLabelText("Результат: Амина Алиева"), "4 задачи");
    await user.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() => expect(saved).toBe(true));
    const saveCall = calls.find(call => call.method === "PUT");
    expect(saveCall?.body).toEqual({ place: 1, scoreText: "4 задачи" });
    await waitFor(() => expect(screen.getByText(/Сохранено черновиков: 1/)).toBeTruthy());
    await user.click(screen.getByRole("button", { name: "Опубликовать результаты" }));
    await user.click(within(screen.getByRole("dialog", { name: "Опубликовать результаты?" })).getByRole("button", { name: "Опубликовать" }));
    await waitFor(() => expect(published).toBe(true));
    expect(calls).toContainEqual({ path: "/competitions/c1/results/publish", method: "POST", body: undefined });
    expect(await screen.findByText("100")).toBeTruthy();
  });
});

describe("динамические роли", () => {
  it("показывает только разрешённые разделы в меню организатора", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      const path = url.replace("/api/v1", ""); const method = init?.method ?? "GET";
      if (path === "/auth/me") return json(copywriter);
      if (path.startsWith("/news")) return json(page([]));
      throw new Error(`Unexpected ${method} ${path}`);
    }));
    window.history.replaceState({}, "", "/manage/news");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Новости" })).toBeTruthy();
    // Копирайтер в кабинете видит только раздел новостей.
    const cabinet = screen.getByLabelText("Личный кабинет");
    expect(within(cabinet).queryByText("Соревнования")).toBeNull();
    expect(within(cabinet).queryByText("Роли и права")).toBeNull();
    // Прямой заход в чужой раздел закрыт.
    window.history.pushState({}, "", "/manage/competitions"); window.dispatchEvent(new PopStateEvent("popstate"));
    expect(await screen.findByText("Доступ закрыт")).toBeTruthy();
  });

  it("master admin видит управление ролями и пользователями", async () => {
    const masterAdmin = { id: "a9", email: "admin@example.com", role: "master-admin", permissions: ["competitions.view", "news.view", "documents.view", "roles.manage", "users.manage"], createdAt: "2026-09-01T10:00:00Z" };
    const roles = [{ id: "r1", name: "Копирайтер", description: null, isSystem: false, permissions: ["news.create"], createdAt: "2026-09-01T10:00:00Z" }];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      const path = url.replace("/api/v1", ""); const method = init?.method ?? "GET";
      if (path === "/auth/me") return json(masterAdmin);
      if (path === "/admin/roles") return json(roles);
      if (path === "/admin/permissions") return json([{ section: "news", label: "Новости", codes: ["news.view", "news.create"] }]);
      if (path.startsWith("/admin/users")) return json(page([]));
      throw new Error(`Unexpected ${method} ${path}`);
    }));
    window.history.replaceState({}, "", "/manage/roles");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Роли и права" })).toBeTruthy();
    expect(await screen.findByText("Копирайтер")).toBeTruthy();
    expect(within(screen.getByLabelText("Личный кабинет")).getByRole("link", { name: "Пользователи" })).toBeTruthy();
  });
});
