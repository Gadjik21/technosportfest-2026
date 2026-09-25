import { useState, type FormEvent } from "react";
import { api, type Competition, type Discipline, type Document, type News, type User } from "./api";
import { Empty, Link, LoadState, Notice, PageTitle, Pager, Status, date, dateTime, errorMessage, go, useLoad } from "./ui";

export function CompetitionCard({ competition }: { competition: Competition }) {
  return <article className="card competition-card">
    <div className="card-top"><span className="category">{competition.discipline.name}</span><Status value={competition.status} /></div>
    <h3><Link to={`/competitions/${competition.id}`}>{competition.title}</Link></h3>
    <p className="muted clamp">{competition.description}</p>
    <div className="card-meta"><span>◷ {date(competition.startsAt)}</span><span>◈ {competition.format === "online" ? "Онлайн" : "Очно"}</span></div>
    <Link className="text-link" to={`/competitions/${competition.id}`}>Подробнее <span aria-hidden>↗</span></Link>
  </article>;
}

export function Home() {
  const competitions = useLoad(() => api.competitions({ pageSize: 3, status: "published" }), "home-competitions");
  const news = useLoad(() => api.news(1), "home-news");
  return <>
    <section className="hero"><div className="hero-copy"><span className="hero-kicker">ТЕХНОСПОРТФЕСТ · 2026</span><h1>Твоя площадка для спортивного программирования</h1><p>Соревнования, результаты и рейтинг спортсменов Республики Дагестан в одном месте.</p><div className="hero-actions"><Link className="button button-light" to="/competitions">Найти соревнование →</Link><Link className="button button-outline-light" to="/ratings">Смотреть рейтинг</Link></div></div><div className="hero-mark" aria-hidden>01<span>/</span>26</div></section>
    <div className="section-heading"><div><span className="eyebrow">СТАРТУЙ ЗДЕСЬ</span><h2>Ближайшие соревнования</h2></div><Link className="text-link" to="/competitions">Все соревнования →</Link></div>
    <LoadState loading={competitions.loading} error={competitions.error}>{competitions.data?.items.length ? <div className="card-grid">{competitions.data.items.map(item => <CompetitionCard key={item.id} competition={item} />)}</div> : <Empty>Пока нет опубликованных соревнований.</Empty>}</LoadState>
    <div className="section-heading"><div><span className="eyebrow">СООБЩЕСТВО</span><h2>Новости</h2></div><Link className="text-link" to="/news">Все новости →</Link></div>
    <LoadState loading={news.loading} error={news.error}>{news.data?.items.length ? <div className="card-grid">{news.data.items.slice(0, 3).map(item => <NewsCard key={item.id} item={item} />)}</div> : <Empty>Новостей пока нет.</Empty>}</LoadState>
  </>;
}

export function Competitions() {
  const [page, setPage] = useState(1);
  const [disciplineId, setDisciplineId] = useState("");
  const disciplines = useLoad(api.disciplines, "disciplines-filter");
  const competitions = useLoad(() => api.competitions({ page, disciplineId: disciplineId || undefined }), `competitions-${page}-${disciplineId}`);
  return <><PageTitle eyebrow="СОРЕВНОВАНИЯ" title="Найди свой старт" description="Выбери дисциплину и подай заявку на открытое соревнование." />
    <div className="filter-bar"><label>Дисциплина <select value={disciplineId} onChange={event => { setDisciplineId(event.target.value); setPage(1); }}><option value="">Все дисциплины</option>{disciplines.data?.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div>
    <LoadState loading={competitions.loading} error={competitions.error}>{competitions.data?.items.length ? <><div className="card-grid">{competitions.data.items.map(item => <CompetitionCard key={item.id} competition={item} />)}</div><Pager page={page} total={competitions.data.total} pageSize={competitions.data.pageSize} onChange={setPage} /></> : <Empty>По этому фильтру соревнований нет.</Empty>}</LoadState>
  </>;
}

export function CompetitionDetail({ id, user }: { id: string; user: User | null }) {
  const competition = useLoad(() => api.competition(id), `competition-${id}`);
  const results = useLoad(() => api.results(id), `competition-results-${id}-${competition.data?.status}`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  async function register() {
    setBusy(true); setError("");
    try { await api.registerForCompetition(id); setSuccess("Заявка подана. Соревнование появилось в вашем кабинете."); competition.reload(); }
    catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  }
  return <LoadState loading={competition.loading} error={competition.error}>{competition.data && <>
    <div className="breadcrumb"><Link to="/competitions">Соревнования</Link><span>/</span>{competition.data.title}</div>
    <div className="detail-grid"><div><div className="card detail-main"><div className="card-top"><span className="category">{competition.data.discipline.name}</span><Status value={competition.data.status} /></div><h1>{competition.data.title}</h1><p className="lead">{competition.data.description}</p><div className="info-grid"><div><small>Дата начала</small><strong>{dateTime(competition.data.startsAt)}</strong></div><div><small>Дата окончания</small><strong>{dateTime(competition.data.endsAt)}</strong></div><div><small>Формат</small><strong>{competition.data.format === "online" ? "Онлайн" : "Очно"}</strong></div><div><small>Регистрация до</small><strong>{dateTime(competition.data.registrationDeadline)}</strong></div></div></div>
    {competition.data.status === "completed" && <section className="card"><h2>Результаты</h2><LoadState loading={results.loading} error={results.error}>{results.data?.items.length ? <div className="table-wrap"><table><thead><tr><th>Место</th><th>Спортсмен</th><th>Результат</th><th>Очки</th></tr></thead><tbody>{results.data.items.map(item => <tr key={item.id}><td>{item.place}</td><td>{item.fullName}</td><td>{item.scoreText || "—"}</td><td><strong>{item.points}</strong></td></tr>)}</tbody></table></div> : <Empty>Опубликованных результатов пока нет.</Empty>}</LoadState></section>}</div>
    <aside className="card action-card"><span className="eyebrow">УЧАСТИЕ</span><h2>Готов к старту?</h2><p>Подай заявку и отслеживай результат в личном кабинете.</p><Notice error={error} success={success} />{competition.data.viewerRegistrationId ? <div className="notice notice-success">Вы уже зарегистрированы</div> : user?.role === "athlete" && competition.data.registrationOpen ? <button className="button" disabled={busy} onClick={register}>{busy ? "Отправляем…" : "Подать заявку"}</button> : !user && competition.data.registrationOpen ? <Link className="button" to="/login">Войти для регистрации</Link> : <div className="muted">{competition.data.registrationOpen ? "Регистрация доступна спортсменам." : "Регистрация закрыта."}</div>}</aside></div>
  </>}</LoadState>;
}

export function Ratings() {
  const [page, setPage] = useState(1);
  const [disciplineId, setDisciplineId] = useState("");
  const disciplines = useLoad(api.disciplines, "rating-disciplines");
  const rating = useLoad(() => api.ratings(page, disciplineId || undefined), `rating-${page}-${disciplineId}`);
  return <><PageTitle eyebrow="РЕЙТИНГ" title="Таблица лидеров" description="Очки начисляются за опубликованные результаты соревнований." /><div className="filter-bar"><label>Дисциплина <select value={disciplineId} onChange={event => { setDisciplineId(event.target.value); setPage(1); }}><option value="">Все дисциплины</option>{disciplines.data?.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label></div>
    <LoadState loading={rating.loading} error={rating.error}>{rating.data && <><div className="card table-card"><div className="table-wrap"><table><thead><tr><th>Место</th><th>Спортсмен</th><th>Соревнований</th><th>Очки</th></tr></thead><tbody>{rating.data.items.map(row => <tr key={row.athleteId}><td><span className="rank">{row.rank}</span></td><td><strong>{row.fullName}</strong></td><td>{row.resultsCount}</td><td><strong>{row.points}</strong></td></tr>)}</tbody></table></div>{!rating.data.items.length && <Empty>Опубликованных результатов пока нет.</Empty>}</div><p className="hint">{rating.data.formula}</p><Pager page={page} total={rating.data.total} pageSize={rating.data.pageSize} onChange={setPage} /></>}</LoadState>
  </>;
}

function NewsCard({ item }: { item: News }) { return <article className="card news-card"><span className="eyebrow">{date(item.publishedAt)}</span><h3><Link to={`/news/${item.id}`}>{item.title}</Link></h3><p className="muted clamp">{item.body}</p><Link className="text-link" to={`/news/${item.id}`}>Читать →</Link></article>; }

export function NewsList() {
  const [page, setPage] = useState(1);
  const news = useLoad(() => api.news(page), `news-${page}`);
  return <><PageTitle eyebrow="НОВОСТИ" title="Что происходит" description="События и объявления федерации." /><LoadState loading={news.loading} error={news.error}>{news.data?.items.length ? <><div className="card-grid">{news.data.items.map(item => <NewsCard key={item.id} item={item} />)}</div><Pager page={page} total={news.data.total} pageSize={news.data.pageSize} onChange={setPage} /></> : <Empty>Новостей пока нет.</Empty>}</LoadState></>;
}

export function NewsDetail({ id }: { id: string }) {
  const news = useLoad(() => api.newsItem(id), `news-${id}`);
  return <LoadState loading={news.loading} error={news.error}>{news.data && <article className="article card"><div className="breadcrumb"><Link to="/news">Новости</Link><span>/</span>{news.data.title}</div><span className="eyebrow">{date(news.data.publishedAt)}</span><h1>{news.data.title}</h1><div className="article-body">{news.data.body}</div></article>}</LoadState>;
}

export function Documents() {
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState("");
  const docs = useLoad(() => api.documents(page, category || undefined), `documents-${page}-${category}`);
  return <><PageTitle eyebrow="ДОКУМЕНТЫ" title="Библиотека документов" description="Положения, правила и материалы соревнований." /><div className="filter-bar"><label>Категория <input value={category} onChange={event => { setCategory(event.target.value); setPage(1); }} placeholder="Все категории" /></label></div><LoadState loading={docs.loading} error={docs.error}>{docs.data?.items.length ? <><div className="document-list">{docs.data.items.map((item: Document) => <div className="card document-row" key={item.id}><div className="document-icon">↗</div><div><span className="eyebrow">{item.category} · {date(item.publishedAt)}</span><h3>{item.title}</h3></div><a className="button button-secondary" href={item.fileUrl} target="_blank" rel="noopener noreferrer">Открыть</a></div>)}</div><Pager page={page} total={docs.data.total} pageSize={docs.data.pageSize} onChange={setPage} /></> : <Empty>Документов пока нет.</Empty>}</LoadState></>;
}

export function AuthPage({ mode, onAuth }: { mode: "login" | "register"; onAuth: (user: User) => void }) {
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [fullName, setFullName] = useState("");
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { const user = mode === "login" ? await api.login({ email, password }) : await api.register({ email, password, fullName }); onAuth(user); go(user.role === "organizer" ? "/manage/competitions" : "/cabinet"); }
    catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  }
  return <div className="auth-layout"><div className="auth-intro"><span className="eyebrow">ТЕХНОСПОРТФЕСТ · 2026</span><h1>Участвуй. Соревнуйся. Расти.</h1><p>Единая площадка для спортивного программирования Дагестана.</p></div><form className="card auth-card" onSubmit={submit}><span className="eyebrow">ЛИЧНЫЙ КАБИНЕТ</span><h2>{mode === "login" ? "С возвращением" : "Создать аккаунт"}</h2><p className="muted">{mode === "login" ? "Войдите, чтобы продолжить." : "Регистрация спортсмена займёт пару минут."}</p><Notice error={error} />{mode === "register" && <label>Имя и фамилия <input required minLength={2} maxLength={150} autoComplete="name" value={fullName} onChange={event => setFullName(event.target.value)} /></label>}<label>Email <input required type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} /></label><label>Пароль <input required type="password" minLength={mode === "register" ? 12 : undefined} autoComplete={mode === "login" ? "current-password" : "new-password"} value={password} onChange={event => setPassword(event.target.value)} /></label>{mode === "register" && <small className="muted">Не менее 12 символов.</small>}<button className="button" disabled={busy}>{busy ? "Подождите…" : mode === "login" ? "Войти" : "Зарегистрироваться"}</button><p className="auth-switch">{mode === "login" ? <>Нет аккаунта? <Link to="/register">Зарегистрироваться</Link></> : <>Уже есть аккаунт? <Link to="/login">Войти</Link></>}</p></form></div>;
}
