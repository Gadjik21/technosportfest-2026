import { useEffect, useState } from "react";
import { api, ApiError, type User } from "./api";
import { AthleteDashboard, CabinetCompetitions, MyProfile, MyResults } from "./AthletePages";
import { ManageCompetition, ManageCompetitions, ManageDocuments, ManageMailings, ManageNews, ManageRoles, ManageUsers, NewCompetition } from "./OrganizerPages";
import { AuthPage, CompetitionDetail, Competitions, Documents, Home, NewsDetail, NewsList, Ratings } from "./PublicPages";
import { Empty, Link, Notice, go, useRoute } from "./ui";

type NavItem = { to: string; label: string; perm?: string };
const publicNav: NavItem[] = [{ to: "/competitions", label: "Соревнования" }, { to: "/ratings", label: "Рейтинг" }, { to: "/news", label: "Новости" }, { to: "/documents", label: "Документы" }];
// Спортсменский кабинет + быстрые ссылки на публичные разделы (рейтинг/новости/документы).
const athleteNav: NavItem[] = [{ to: "/cabinet", label: "Обзор" }, { to: "/cabinet/competitions", label: "Соревнования" }, { to: "/cabinet/results", label: "Мои результаты" }, { to: "/ratings", label: "Рейтинг" }, { to: "/news", label: "Новости" }, { to: "/documents", label: "Документы" }, { to: "/cabinet/profile", label: "Профиль" }];
// Каждый раздел кабинета организатора привязан к праву: нет права — пункт скрыт и маршрут закрыт.
const manageNav: NavItem[] = [
  { to: "/manage/competitions", label: "Соревнования", perm: "competitions.view" },
  { to: "/manage/news", label: "Новости", perm: "news.view" },
  { to: "/manage/documents", label: "Документы", perm: "documents.view" },
  { to: "/manage/mailings", label: "Рассылки", perm: "mailings.manage" },
  { to: "/manage/roles", label: "Роли и права", perm: "roles.manage" },
  { to: "/manage/users", label: "Пользователи", perm: "users.manage" },
];

const can = (user: User | null | undefined, perm?: string) => (perm ? !!user?.permissions.includes(perm) : true);
const visibleManage = (user: User) => manageNav.filter(item => can(user, item.perm));

/** Промежуточная страница после входа: ведёт в первый доступный раздел кабинета. */
function ManageHome({ user }: { user: User }) {
  const first = visibleManage(user)[0];
  useEffect(() => { if (first) go(first.to); }, [first]);
  if (!first) return <Empty>У вашей роли нет разделов кабинета.</Empty>;
  return <Empty>Переходим в ваш раздел…</Empty>;
}

function Nav({ path, items }: { path: string; items: NavItem[] }) {
  return <>{items.map(item => <Link key={item.to} className={`nav-link ${path === item.to || (item.to !== "/" && path.startsWith(item.to + "/")) ? "nav-active" : ""}`} to={item.to}>{item.label}</Link>)}</>;
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
  const isManagePath = path.startsWith("/manage");
  const manageSection = manageNav.find(item => path === item.to || path.startsWith(item.to + "/"));
  const accessDenied = <div className="card access-card"><h1>Доступ закрыт</h1><p>У вашей роли нет прав на этот раздел.</p><Link className="button" to={user?.role === "athlete" ? "/cabinet" : "/"}>На главную</Link></div>;
  if (user === undefined && (protectedAthlete || isManagePath)) content = <Empty>Проверяем вход…</Empty>;
  else if (protectedAthlete && user?.role !== "athlete") content = accessDenied;
  else if (isManagePath && (!user || (manageSection && !can(user, manageSection.perm)))) content = accessDenied;
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
  else if (path === "/manage") content = <ManageHome user={user!} />;
  else if (path === "/manage/competitions") content = <ManageCompetitions />;
  else if (path === "/manage/competitions/new") content = <NewCompetition />;
  else if (manageId) content = <ManageCompetition id={manageId} />;
  else if (path === "/manage/news") content = <ManageNews />;
  else if (path === "/manage/documents") content = <ManageDocuments />;
  else if (path === "/manage/mailings") content = <ManageMailings userId={user!.id} />;
  else if (path === "/manage/roles") content = <ManageRoles />;
  else if (path === "/manage/users") content = <ManageUsers />;
  else content = <div className="card access-card"><h1>Страница не найдена</h1><Link className="button" to="/">На главную</Link></div>;

  const isLanding = path === "/";
  const manageHome = user ? (visibleManage(user)[0]?.to ?? "/") : "/";
  const accountLabel = user?.role === "athlete" ? "Мой кабинет" : "Кабинет";
  const showSidebar = !!user && !isLanding;
  return <div className="app-shell"><header className="site-header"><div className="header-inner"><Link to="/" className="brand"><span className="brand-icon">◈</span><span>Arena<span>Code</span><small>ТЕХНОСПОРТФЕСТ · 2026</small></span></Link><nav className="desktop-nav" aria-label="Основная навигация">{(!user || isLanding) && <Nav path={path} items={publicNav} />}</nav><div className="header-actions">{user ? <><Link className="header-account" to={user.role === "athlete" ? "/cabinet" : manageHome}>{accountLabel}</Link><button className="header-logout" onClick={logout}>Выйти</button></> : <><Link className="header-account" to="/login">Войти</Link><Link className="button button-small" to="/register">Регистрация</Link></>}</div></div></header>
    <div className={`layout ${showSidebar ? "layout-with-sidebar" : ""}`}>
      {showSidebar && <aside className="sidebar"><div className="sidebar-heading">{user!.role === "athlete" ? "СПОРТСМЕН" : user!.role.toUpperCase()}</div><nav aria-label="Личный кабинет"><Nav path={path} items={user!.role === "athlete" ? athleteNav : visibleManage(user!)} /></nav><div className="sidebar-foot">{user!.email}</div></aside>}
      <main className="content" id="main"><Notice error={authError} />{content}</main>
    </div><nav className="mobile-nav" aria-label="Мобильная навигация">{user && user.role !== "athlete" ? <><Link to={manageHome}>Кабинет</Link>{visibleManage(user).map(item => <Link key={item.to} to={item.to}>{item.label}</Link>)}<Link to="/ratings">Рейтинг</Link></> : <><Link to={user?.role === "athlete" ? "/cabinet/competitions" : "/competitions"}>Соревнования</Link><Link to="/ratings">Рейтинг</Link><Link to="/news">Новости</Link><Link to="/documents">Документы</Link><Link to={user ? "/cabinet" : "/login"}>Кабинет</Link></>}</nav>
    <footer className="site-footer"><span>© ТехноСпортФест 2026</span><span>Спортивное программирование · Республика Дагестан</span></footer></div>;
}
