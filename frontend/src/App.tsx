import { useEffect, useState } from "react";
import { api, ApiError, type User } from "./api";
import { AthleteDashboard, CabinetCompetitions, MyProfile, MyResults } from "./AthletePages";
import { ManageCompetition, ManageCompetitions, ManageDocuments, ManageNews, NewCompetition } from "./OrganizerPages";
import { AuthPage, CompetitionDetail, Competitions, Documents, Home, NewsDetail, NewsList, Ratings } from "./PublicPages";
import { Empty, Link, Notice, go, useRoute } from "./ui";

const publicNav = [{ to: "/competitions", label: "Соревнования" }, { to: "/ratings", label: "Рейтинг" }, { to: "/news", label: "Новости" }, { to: "/documents", label: "Документы" }];
const athleteNav = [{ to: "/cabinet", label: "Обзор" }, { to: "/cabinet/competitions", label: "Соревнования" }, { to: "/cabinet/results", label: "Мои результаты" }, { to: "/cabinet/profile", label: "Профиль" }];
const organizerNav = [{ to: "/manage/competitions", label: "Соревнования" }, { to: "/manage/news", label: "Новости" }, { to: "/manage/documents", label: "Документы" }];

function Nav({ path, items }: { path: string; items: { to: string; label: string }[] }) {
  return <>{items.map(item => <Link key={item.to} className={`nav-link ${path === item.to || (item.to === "/manage/competitions" && path.startsWith(item.to + "/")) ? "nav-active" : ""}`} to={item.to}>{item.label}</Link>)}</>;
}

export function App() {
  const path = useRoute();
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [authError, setAuthError] = useState("");
  useEffect(() => {
    let active = true;
    api.me().then(value => { if (active) setUser(value); }).catch(reason => {
      if (!active) return;
      setUser(null);
      if (!(reason instanceof ApiError && reason.status === 401)) setAuthError("Не удалось проверить вход. Сервер может быть недоступен.");
    });
    return () => { active = false; };
  }, []);
  async function logout() {
    try { await api.logout(); setUser(null); go("/"); }
    catch { setAuthError("Не удалось выйти. Попробуйте ещё раз."); }
  }

  let content;
  const competitionId = path.match(/^\/competitions\/([^/]+)$/)?.[1];
  const newsId = path.match(/^\/news\/([^/]+)$/)?.[1];
  const manageId = path.match(/^\/manage\/competitions\/([^/]+)$/)?.[1];
  const protectedAthlete = path.startsWith("/cabinet");
  const protectedOrganizer = path.startsWith("/manage");
  if (user === undefined && (protectedAthlete || protectedOrganizer)) content = <Empty>Проверяем вход…</Empty>;
  else if (protectedAthlete && user?.role !== "athlete" || protectedOrganizer && user?.role !== "organizer") content = <div className="card access-card"><h1>Доступ закрыт</h1><p>Войдите в аккаунт с нужной ролью.</p><Link className="button" to="/login">Войти</Link></div>;
  else if (path === "/") content = <Home />;
  else if (path === "/login" || path === "/register") content = <AuthPage key={path} mode={path === "/login" ? "login" : "register"} onAuth={value => { setUser(value); setAuthError(""); }} />;
  else if (path === "/competitions") content = <Competitions />;
  else if (competitionId) content = <CompetitionDetail id={competitionId} user={user ?? null} />;
  else if (path === "/ratings") content = <Ratings />;
  else if (path === "/news") content = <NewsList />;
  else if (newsId) content = <NewsDetail id={newsId} />;
  else if (path === "/documents") content = <Documents />;
  else if (path === "/cabinet") content = <AthleteDashboard user={user!} />;
  else if (path === "/cabinet/competitions") content = <CabinetCompetitions />;
  else if (path === "/cabinet/results") content = <MyResults />;
  else if (path === "/cabinet/profile") content = <MyProfile user={user!} />;
  else if (path === "/manage/competitions") content = <ManageCompetitions />;
  else if (path === "/manage/competitions/new") content = <NewCompetition />;
  else if (manageId) content = <ManageCompetition id={manageId} />;
  else if (path === "/manage/news") content = <ManageNews />;
  else if (path === "/manage/documents") content = <ManageDocuments />;
  else content = <div className="card access-card"><h1>Страница не найдена</h1><Link className="button" to="/">На главную</Link></div>;

  return <div className="app-shell"><header className="site-header"><div className="header-inner"><Link to="/" className="brand"><span className="brand-icon">◈</span><span>Техно<span>Спорт</span>Фест<small>ДАГЕСТАН · 2026</small></span></Link><nav className="desktop-nav" aria-label="Основная навигация"><Nav path={path} items={publicNav} /></nav><div className="header-actions">{user ? <><Link className="header-account" to={user.role === "organizer" ? "/manage/competitions" : "/cabinet"}>{user.role === "organizer" ? "Кабинет организатора" : "Мой кабинет"}</Link><button className="header-logout" onClick={logout}>Выйти</button></> : <><Link className="header-account" to="/login">Войти</Link><Link className="button button-small" to="/register">Регистрация</Link></>}</div></div></header>
    <div className={`layout ${user && (protectedAthlete || protectedOrganizer) ? "layout-with-sidebar" : ""}`}>
      {user && (protectedAthlete || protectedOrganizer) && <aside className="sidebar"><div className="sidebar-heading">{user.role === "organizer" ? "ОРГАНИЗАТОР" : "СПОРТСМЕН"}</div><nav aria-label="Личный кабинет"><Nav path={path} items={user.role === "organizer" ? organizerNav : athleteNav} /></nav><div className="sidebar-foot">{user.email}</div></aside>}
      <main className="content" id="main"><Notice error={authError} />{content}</main>
    </div><nav className="mobile-nav" aria-label="Мобильная навигация">{user?.role === "organizer" ? <><Link to="/manage/competitions">Соревнования</Link><Link to="/manage/news">Новости</Link><Link to="/manage/documents">Документы</Link><Link to="/ratings">Рейтинг</Link></> : <><Link to={user?.role === "athlete" ? "/cabinet/competitions" : "/competitions"}>Соревнования</Link><Link to="/ratings">Рейтинг</Link><Link to="/news">Новости</Link><Link to="/documents">Документы</Link><Link to={user ? "/cabinet" : "/login"}>Кабинет</Link></>}</nav>
    <footer className="site-footer"><span>© ТехноСпортФест 2026</span><span>Спортивное программирование · Республика Дагестан</span></footer></div>;
}
