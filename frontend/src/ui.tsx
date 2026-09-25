import { useEffect, useState, type ReactNode } from "react";
import { ApiError } from "./api";

export function useRoute() {
  const [path, setPath] = useState(window.location.pathname);
  useEffect(() => {
    const sync = () => setPath(window.location.pathname);
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  return path;
}

export function go(path: string) {
  if (window.location.pathname !== path) window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
  window.scrollTo(0, 0);
}

export function Link({ to, children, className = "" }: { to: string; children: ReactNode; className?: string }) {
  return <a href={to} className={className} onClick={(event) => {
    if (event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
      event.preventDefault(); go(to);
    }
  }}>{children}</a>;
}

export function useLoad<T>(load: () => Promise<T>, key: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    load().then(value => { if (active) setData(value); }).catch(reason => { if (active) setError(errorMessage(reason)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
    // `key` is the stable identity of the request; reload increments revision.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, revision]);
  return { data, error, loading, reload: () => setRevision(value => value + 1) };
}

export function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    const fields = Object.entries(error.fields).map(([field, message]) => `${field.replace(/^body\./, "")}: ${message}`);
    return fields.length ? `${error.message} ${fields.join("; ")}` : error.message;
  }
  if (error instanceof Error && error.message === "Failed to fetch") return "Нет соединения с сервером. Проверьте, что API запущен.";
  return error instanceof Error ? error.message : "Не удалось выполнить запрос.";
}

export function Notice({ error, success }: { error?: string; success?: string }) {
  if (!error && !success) return null;
  return <div role={error ? "alert" : "status"} className={`notice ${error ? "notice-error" : "notice-success"}`}>{error || success}</div>;
}

export function LoadState({ loading, error, children }: { loading: boolean; error: string; children: ReactNode }) {
  if (loading) return <div className="card empty" role="status">Загружаем данные…</div>;
  if (error) return <Notice error={error} />;
  return <>{children}</>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="card empty">{children}</div>;
}

export function Pager({ page, total, pageSize, onChange }: { page: number; total: number; pageSize: number; onChange: (page: number) => void }) {
  if (total <= pageSize) return null;
  return <div className="pager"><button disabled={page <= 1} onClick={() => onChange(page - 1)}>← Назад</button><span>Страница {page} из {Math.ceil(total / pageSize)}</span><button disabled={page * pageSize >= total} onClick={() => onChange(page + 1)}>Далее →</button></div>;
}

export function date(value: string) {
  return new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", year: "numeric", timeZone: "Europe/Moscow" }).format(new Date(value));
}

export function dateTime(value: string) {
  return new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Moscow" }).format(new Date(value));
}

export function statusLabel(status: string) {
  return ({ draft: "Черновик", published: "Опубликовано", completed: "Завершено" } as Record<string, string>)[status] ?? status;
}

export function Status({ value }: { value: string }) {
  return <span className={`status status-${value}`}>{statusLabel(value)}</span>;
}

export function PageTitle({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: ReactNode }) {
  return <div className="page-title"><div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h1>{title}</h1>{description && <p>{description}</p>}</div>{action}</div>;
}
