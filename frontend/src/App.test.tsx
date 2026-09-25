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
const athlete = { id: "a1", email: "athlete@example.com", role: "athlete", createdAt: "2026-09-01T10:00:00Z" };
const organizer = { id: "o1", email: "org@example.com", role: "organizer", createdAt: "2026-09-01T10:00:00Z" };
const page = <T,>(items: T[]) => ({ items, page: 1, pageSize: 100, total: items.length });
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });

beforeEach(() => { window.history.replaceState({}, "", "/"); vi.stubGlobal("scrollTo", vi.fn()); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("основной путь MVP", () => {
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
      if (path === "/me") return json({ user: athlete, fullName: "Амина Алиева", education: null, locality: null, disciplineIds: [] });
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
    vi.stubGlobal("confirm", vi.fn(() => true));
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
    await waitFor(() => expect(published).toBe(true));
    expect(calls).toContainEqual({ path: "/competitions/c1/results/publish", method: "POST", body: undefined });
    expect(await screen.findByText("100")).toBeTruthy();
  });
});
