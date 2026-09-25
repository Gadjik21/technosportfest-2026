import { useState, type FormEvent } from "react";
import { api, type User } from "./api";
import { CompetitionCard } from "./PublicPages";
import { Empty, Link, LoadState, Notice, PageTitle, Pager, date, errorMessage, useLoad } from "./ui";

export function AthleteDashboard({ user }: { user: User }) {
  const profile = useLoad(api.profile, `dashboard-profile-${user.id}`);
  const registrations = useLoad(() => api.myRegistrations(), `dashboard-registrations-${user.id}`);
  const results = useLoad(() => api.myResults(), `dashboard-results-${user.id}`);
  const rating = useLoad(() => api.myRating(), `dashboard-rating-${user.id}`);
  return <><PageTitle eyebrow="ЛИЧНЫЙ КАБИНЕТ" title={`Привет, ${profile.data?.fullName?.split(" ")[0] || "спортсмен"}!`} description="Всё о твоём участии и прогрессе." action={<Link className="button button-secondary" to="/cabinet/profile">Мой профиль</Link>} />
    <div className="stat-grid"><div className="card stat"><span>Очки рейтинга</span><strong>{rating.data?.points ?? "—"}</strong><small>За опубликованные результаты</small></div><div className="card stat"><span>Место в рейтинге</span><strong>{rating.data?.rank ?? "—"}</strong><small>Среди всех спортсменов</small></div><div className="card stat"><span>Соревнований</span><strong>{registrations.data?.total ?? "—"}</strong><small>Заявок подано</small></div><div className="card stat"><span>Результатов</span><strong>{results.data?.total ?? "—"}</strong><small>Опубликовано</small></div></div>
    <div className="section-heading"><h2>Мои соревнования</h2><Link className="text-link" to="/cabinet/registrations">Все заявки →</Link></div>
    <LoadState loading={registrations.loading} error={registrations.error}>{registrations.data?.items.length ? <div className="card-grid">{registrations.data.items.slice(0, 3).map(item => <CompetitionCard key={item.id} competition={item.competition} />)}</div> : <Empty>Вы пока не записались ни на одно соревнование. <Link to="/competitions">Найти соревнование →</Link></Empty>}</LoadState>
    <div className="section-heading"><h2>Последние результаты</h2><Link className="text-link" to="/cabinet/results">Все результаты →</Link></div>
    <LoadState loading={results.loading} error={results.error}>{results.data?.items.length ? <div className="card table-card"><div className="table-wrap"><table><thead><tr><th>Место</th><th>Соревнование</th><th>Результат</th><th>Очки</th></tr></thead><tbody>{results.data.items.slice(0, 5).map(item => <tr key={item.id}><td>{item.place}</td><td><Link to={`/competitions/${item.competitionId}`}>Открыть соревнование</Link></td><td>{item.scoreText || "—"}</td><td><strong>{item.points}</strong></td></tr>)}</tbody></table></div></div> : <Empty>Результаты появятся после публикации организатором.</Empty>}</LoadState>
    {profile.error && <Notice error={profile.error} />}
  </>;
}

export function MyRegistrations() {
  const [page, setPage] = useState(1);
  const items = useLoad(() => api.myRegistrations(page), `my-registrations-${page}`);
  return <><PageTitle eyebrow="ЛИЧНЫЙ КАБИНЕТ" title="Мои соревнования" description="Заявки и даты предстоящих стартов." /><LoadState loading={items.loading} error={items.error}>{items.data?.items.length ? <><div className="card-grid">{items.data.items.map(item => <CompetitionCard key={item.id} competition={item.competition} />)}</div><Pager page={page} total={items.data.total} pageSize={items.data.pageSize} onChange={setPage} /></> : <Empty>Заявок пока нет. <Link to="/competitions">Выбрать соревнование →</Link></Empty>}</LoadState></>;
}

export function MyResults() {
  const [page, setPage] = useState(1);
  const items = useLoad(() => api.myResults(page), `my-results-${page}`);
  return <><PageTitle eyebrow="ЛИЧНЫЙ КАБИНЕТ" title="Мои результаты" description="Здесь только опубликованные результаты." /><LoadState loading={items.loading} error={items.error}>{items.data?.items.length ? <><div className="card table-card"><div className="table-wrap"><table><thead><tr><th>Дата</th><th>Соревнование</th><th>Место</th><th>Результат</th><th>Очки</th></tr></thead><tbody>{items.data.items.map(item => <tr key={item.id}><td>{date(item.publishedAt)}</td><td><Link to={`/competitions/${item.competitionId}`}>Смотреть соревнование</Link></td><td>{item.place}</td><td>{item.scoreText || "—"}</td><td><strong>{item.points}</strong></td></tr>)}</tbody></table></div></div><Pager page={page} total={items.data.total} pageSize={items.data.pageSize} onChange={setPage} /></> : <Empty>Пока нет опубликованных результатов.</Empty>}</LoadState></>;
}

export function MyProfile({ user }: { user: User }) {
  const profile = useLoad(api.profile, `profile-${user.id}`);
  const disciplines = useLoad(api.disciplines, "profile-disciplines");
  const [form, setForm] = useState<{ fullName: string; education: string; locality: string; disciplineIds: string[] } | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [success, setSuccess] = useState("");
  const value = form ?? (profile.data ? { fullName: profile.data.fullName, education: profile.data.education || "", locality: profile.data.locality || "", disciplineIds: profile.data.disciplineIds } : null);
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!value) return; setBusy(true); setError(""); setSuccess("");
    try { await api.updateProfile({ ...value, education: value.education || null, locality: value.locality || null }); setSuccess("Профиль сохранён."); profile.reload(); }
    catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  }
  return <><PageTitle eyebrow="ЛИЧНЫЙ КАБИНЕТ" title="Мой профиль" description="Эти данные увидит организатор в списке участников." /><LoadState loading={profile.loading} error={profile.error}>{value && <form className="card form-card" onSubmit={submit}><Notice error={error} success={success} /><label>Имя и фамилия <input required minLength={2} maxLength={150} value={value.fullName} onChange={event => setForm({ ...value, fullName: event.target.value })} /></label><label>Email <input disabled value={user.email} /></label><label>Учебное заведение <input maxLength={200} value={value.education} onChange={event => setForm({ ...value, education: event.target.value })} /></label><label>Населённый пункт <input maxLength={150} value={value.locality} onChange={event => setForm({ ...value, locality: event.target.value })} /></label><fieldset><legend>Дисциплины</legend><div className="check-list">{disciplines.data?.map(item => <label className="check" key={item.id}><input type="checkbox" checked={value.disciplineIds.includes(item.id)} onChange={event => setForm({ ...value, disciplineIds: event.target.checked ? [...value.disciplineIds, item.id] : value.disciplineIds.filter(id => id !== item.id) })} />{item.name}</label>)}</div></fieldset><button className="button" disabled={busy}>{busy ? "Сохраняем…" : "Сохранить изменения"}</button></form>}</LoadState></>;
}
