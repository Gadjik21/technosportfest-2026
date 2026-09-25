import { useState, type FormEvent } from "react";
import { api, type Competition, type Document, type News, type Page, type Participant, type ResultDraft } from "./api";
import { ConfirmDialog, Empty, Link, LoadState, Notice, PageTitle, Status, date, errorMessage, go, useLoad } from "./ui";

async function allPages<T>(getPage: (page: number) => Promise<Page<T>>): Promise<T[]> {
  const first = await getPage(1);
  const items = [...first.items];
  for (let page = 2; (page - 1) * first.pageSize < first.total; page++) items.push(...(await getPage(page)).items);
  return items;
}

export function ManageCompetitions() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<"draft" | "published" | "completed">("draft");
  const items = useLoad(() => api.competitions({ page, status }), `manage-competitions-${page}-${status}`);
  return <><PageTitle eyebrow="ОРГАНИЗАТОР" title="Соревнования" description="Создавайте соревнования, принимайте участников и публикуйте результаты." action={<Link className="button" to="/manage/competitions/new">+ Новое соревнование</Link>} /><div className="tabs">{(["draft", "published", "completed"] as const).map(item => <button key={item} className={status === item ? "active" : ""} onClick={() => { setStatus(item); setPage(1); }}>{({ draft: "Черновики", published: "Опубликованные", completed: "Завершённые" })[item]}</button>)}</div><LoadState loading={items.loading} error={items.error}>{items.data?.items.length ? <><div className="card table-card"><div className="table-wrap"><table><thead><tr><th>Название</th><th>Дисциплина</th><th>Дата</th><th>Статус</th><th></th></tr></thead><tbody>{items.data.items.map(item => <tr key={item.id}><td><strong>{item.title}</strong></td><td>{item.discipline.name}</td><td>{date(item.startsAt)}</td><td><Status value={item.status} /></td><td><Link className="text-link" to={`/manage/competitions/${item.id}`}>Управлять →</Link></td></tr>)}</tbody></table></div></div>{items.data.total > items.data.pageSize && <div className="pager"><button disabled={page === 1} onClick={() => setPage(page - 1)}>← Назад</button><span>Страница {page}</span><button disabled={page * items.data.pageSize >= items.data.total} onClick={() => setPage(page + 1)}>Далее →</button></div>}</> : <Empty>В этом разделе соревнований нет. <Link to="/manage/competitions/new">Создать →</Link></Empty>}</LoadState></>;
}

type CompetitionFormState = { title: string; disciplineId: string; startsAt: string; endsAt: string; registrationDeadline: string; format: "online" | "offline"; description: string };
const asLocal = (iso: string) => {
  const value = new Date(iso);
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
};
const initial: CompetitionFormState = { title: "", disciplineId: "", startsAt: "", endsAt: "", registrationDeadline: "", format: "online", description: "" };

export function CompetitionForm({ competition, onSaved }: { competition?: Competition; onSaved?: () => void }) {
  const disciplines = useLoad(api.disciplines, "form-disciplines");
  const [state, setState] = useState<CompetitionFormState | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [success, setSuccess] = useState("");
  const value = state ?? (competition ? { title: competition.title, disciplineId: competition.discipline.id, startsAt: asLocal(competition.startsAt), endsAt: asLocal(competition.endsAt), registrationDeadline: asLocal(competition.registrationDeadline), format: competition.format, description: competition.description } : initial);
  const set = <K extends keyof CompetitionFormState>(key: K, item: CompetitionFormState[K]) => setState({ ...value, [key]: item });
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setSuccess("");
    const start = new Date(value.startsAt), end = new Date(value.endsAt), deadline = new Date(value.registrationDeadline);
    if (end <= start || deadline >= start) { setError("Окончание должно быть позже начала, а регистрация — закрыться до старта."); return; }
    setBusy(true);
    try {
      const body = { ...value, startsAt: start.toISOString(), endsAt: end.toISOString(), registrationDeadline: deadline.toISOString() };
      const saved = competition ? await api.updateCompetition(competition.id, body) : await api.createCompetition(body);
      setSuccess("Соревнование сохранено."); onSaved?.();
      if (!competition) go(`/manage/competitions/${saved.id}`);
    } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  }
  return <form className="card form-card" onSubmit={submit}><Notice error={error} success={success} /><label>Название <input required minLength={3} maxLength={200} value={value.title} onChange={event => set("title", event.target.value)} /></label><label>Дисциплина <select required value={value.disciplineId} onChange={event => set("disciplineId", event.target.value)}><option value="">Выберите дисциплину</option>{disciplines.data?.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label><div className="form-grid"><label>Начало <input required type="datetime-local" value={value.startsAt} onChange={event => set("startsAt", event.target.value)} /></label><label>Окончание <input required type="datetime-local" value={value.endsAt} onChange={event => set("endsAt", event.target.value)} /></label></div><label>Регистрация до <input required type="datetime-local" value={value.registrationDeadline} onChange={event => set("registrationDeadline", event.target.value)} /></label><label>Формат <select value={value.format} onChange={event => set("format", event.target.value as "online" | "offline")}><option value="online">Онлайн</option><option value="offline">Очно</option></select></label><label>Описание <textarea required rows={6} value={value.description} onChange={event => set("description", event.target.value)} /></label><button className="button" disabled={busy}>{busy ? "Сохраняем…" : "Сохранить соревнование"}</button></form>;
}

export function NewCompetition() { return <><PageTitle eyebrow="ОРГАНИЗАТОР / СОРЕВНОВАНИЯ" title="Новое соревнование" description="После создания проверьте данные и опубликуйте карточку." /><CompetitionForm /></>; }

export function ManageCompetition({ id }: { id: string }) {
  const competition = useLoad(() => api.competition(id), `manage-competition-${id}`);
  const [tab, setTab] = useState<"participants" | "details">("participants");
  const [showPublishConfirm, setShowPublishConfirm] = useState(false);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [success, setSuccess] = useState("");
  async function publish() {
    setShowPublishConfirm(false);
    setBusy(true); setError("");
    try { await api.publishCompetition(id); setSuccess("Соревнование опубликовано."); competition.reload(); }
    catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  }
  return <LoadState loading={competition.loading} error={competition.error}>{competition.data && <><div className="breadcrumb"><Link to="/manage/competitions">Соревнования</Link><span>/</span>{competition.data.title}</div><PageTitle eyebrow="УПРАВЛЕНИЕ СОРЕВНОВАНИЕМ" title={competition.data.title} description={`${competition.data.discipline.name} · ${date(competition.data.startsAt)}`} action={<Status value={competition.data.status} />} /><Notice error={error} success={success} />{competition.data.status === "draft" && <div className="callout"><div><strong>Черновик виден только организаторам.</strong><p>Проверьте даты, дисциплину и описание перед публикацией.</p></div><button className="button" disabled={busy} onClick={() => setShowPublishConfirm(true)}>Опубликовать</button></div>}{showPublishConfirm && <ConfirmDialog title="Опубликовать соревнование?" confirmLabel="Опубликовать" onCancel={() => setShowPublishConfirm(false)} onConfirm={publish}>Спортсмены увидят карточку и смогут подать заявку.</ConfirmDialog>}<div className="tabs"><button className={tab === "participants" ? "active" : ""} onClick={() => setTab("participants")}>Участники и результаты</button><button className={tab === "details" ? "active" : ""} onClick={() => setTab("details")}>Параметры</button></div>{tab === "details" ? competition.data.status === "draft" ? <CompetitionForm competition={competition.data} onSaved={() => { setSuccess("Соревнование сохранено."); competition.reload(); }} /> : <div className="card form-card"><p>После публикации параметры соревнования не редактируются.</p><Link className="button button-secondary" to={`/competitions/${id}`}>Открыть карточку</Link></div> : <ParticipantsAndResults competition={competition.data} onPublished={competition.reload} />}</>}</LoadState>;
}

function ParticipantsAndResults({ competition, onPublished }: { competition: Competition; onPublished: () => void }) {
  const id = competition.id;
  const participants = useLoad(() => allPages(page => api.participants(id, page)), `participants-${id}`);
  const drafts = useLoad(() => allPages(page => api.drafts(id, page)), `drafts-${id}`);
  const results = useLoad(() => api.results(id), `published-results-${id}-${competition.status}`);
  const [edits, setEdits] = useState<Record<string, { place: string; scoreText: string }>>({});
  const [showResultsConfirm, setShowResultsConfirm] = useState(false);
  const [busyId, setBusyId] = useState(""); const [error, setError] = useState(""); const [success, setSuccess] = useState("");
  const draftByRegistration = new Map(drafts.data?.map(item => [item.registrationId, item]));
  const getEdit = (participant: Participant) => edits[participant.registrationId] ?? { place: draftByRegistration.get(participant.registrationId)?.place.toString() ?? "", scoreText: draftByRegistration.get(participant.registrationId)?.scoreText ?? "" };
  const change = (id: string, patch: Partial<{ place: string; scoreText: string }>, participant: Participant) => setEdits(previous => ({ ...previous, [id]: { ...getEdit(participant), ...patch } }));
  async function save(participant: Participant) {
    const value = getEdit(participant);
    const place = Number(value.place);
    if (!Number.isInteger(place) || place < 1) { setError("Укажите место целым положительным числом."); return; }
    setBusyId(participant.registrationId); setError(""); setSuccess("");
    try { await api.saveDraft(id, participant.registrationId, { place, scoreText: value.scoreText || null }); setSuccess(`Результат ${participant.fullName} сохранён как черновик.`); drafts.reload(); }
    catch (reason) { setError(errorMessage(reason)); } finally { setBusyId(""); }
  }
  async function publish() {
    setShowResultsConfirm(false);
    setBusyId("publish"); setError(""); setSuccess("");
    try { await api.publishResults(id); setSuccess("Результаты опубликованы. Соревнование завершено."); onPublished(); }
    catch (reason) { setError(errorMessage(reason)); } finally { setBusyId(""); }
  }
  if (competition.status === "draft") return <Empty>Опубликуйте соревнование, чтобы принимать заявки и результаты.</Empty>;
  return <><div className="section-heading"><div><h2>Участники</h2><p className="muted">Места и результаты сохраняются как черновики до публикации.</p></div>{competition.status === "published" && <button className="button" disabled={busyId === "publish" || !drafts.data?.length} onClick={() => setShowResultsConfirm(true)}>Опубликовать результаты</button>}</div>{showResultsConfirm && <ConfirmDialog title="Опубликовать результаты?" confirmLabel="Опубликовать" onCancel={() => setShowResultsConfirm(false)} onConfirm={publish}>Будет опубликовано {drafts.data?.length ?? 0} результатов. Рейтинг обновится, редактирование станет недоступно.</ConfirmDialog>}<Notice error={error || participants.error || drafts.error} success={success} />
    <LoadState loading={participants.loading || (competition.status === "published" && drafts.loading) || (competition.status === "completed" && results.loading)} error="">{competition.status === "completed" ? results.data?.items.length ? <div className="card table-card"><div className="table-wrap"><table><thead><tr><th>Место</th><th>Участник</th><th>Результат</th><th>Очки</th></tr></thead><tbody>{results.data.items.map(item => <tr key={item.id}><td>{item.place}</td><td>{item.fullName}</td><td>{item.scoreText || "—"}</td><td><strong>{item.points}</strong></td></tr>)}</tbody></table></div></div> : <Empty>Результатов нет.</Empty> : participants.data?.length ? <><div className="card table-card"><div className="table-wrap"><table><thead><tr><th>Участник</th><th>Город / учёба</th><th>Место</th><th>Результат</th><th></th></tr></thead><tbody>{participants.data.map(participant => { const value = getEdit(participant); return <tr key={participant.registrationId}><td><strong>{participant.fullName}</strong><small>{date(participant.registeredAt)}</small></td><td>{participant.locality || "—"}<small>{participant.education || ""}</small></td><td><input aria-label={`Место: ${participant.fullName}`} className="place-input" type="number" min="1" value={value.place} onChange={event => change(participant.registrationId, { place: event.target.value }, participant)} /></td><td><input aria-label={`Результат: ${participant.fullName}`} maxLength={500} value={value.scoreText} onChange={event => change(participant.registrationId, { scoreText: event.target.value }, participant)} placeholder="Например, 4 задачи" /></td><td><button className="button button-small button-secondary" disabled={!!busyId} onClick={() => save(participant)}>{busyId === participant.registrationId ? "…" : "Сохранить"}</button></td></tr>; })}</tbody></table></div></div><p className="hint">Сохранено черновиков: {drafts.data?.length ?? 0} из {participants.data.length} участников. Публикация начислит 100 / 70 / 50 / 20 очков за 1 / 2 / 3 / остальные места.</p></> : <Empty>Участников пока нет.</Empty>}</LoadState>
  </>;
}

export function ManageNews() {
  const list = useLoad(() => allPages(page => api.news(page)), "manage-news");
  const [editing, setEditing] = useState<News | null>(null); const [title, setTitle] = useState(""); const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [success, setSuccess] = useState("");
  function edit(item: News) { setEditing(item); setTitle(item.title); setBody(item.body); setError(""); setSuccess(""); window.scrollTo(0, 0); }
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setSuccess("");
    try { if (editing) await api.updateNews(editing.id, { title, body }); else await api.createNews({ title, body }); setSuccess(editing ? "Новость обновлена." : "Новость опубликована."); setEditing(null); setTitle(""); setBody(""); list.reload(); }
    catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  }
  return <><PageTitle eyebrow="ОРГАНИЗАТОР" title="Новости" description="Публикуйте объявления для участников." /><form className="card form-card" onSubmit={submit}><h2>{editing ? "Редактировать новость" : "Новая новость"}</h2><Notice error={error} success={success} /><label>Заголовок <input required minLength={3} maxLength={200} value={title} onChange={event => setTitle(event.target.value)} /></label><label>Текст <textarea required rows={7} maxLength={20000} value={body} onChange={event => setBody(event.target.value)} /></label><div className="form-actions"><button className="button" disabled={busy}>{busy ? "Сохраняем…" : editing ? "Сохранить" : "Опубликовать"}</button>{editing && <button type="button" className="button button-secondary" onClick={() => { setEditing(null); setTitle(""); setBody(""); }}>Отмена</button>}</div></form><div className="section-heading"><h2>Опубликованные новости</h2></div><LoadState loading={list.loading} error={list.error}>{list.data?.length ? <div className="card list-card">{list.data.map(item => <div className="list-row" key={item.id}><div><strong>{item.title}</strong><small>{date(item.publishedAt)}</small></div><button className="text-link" onClick={() => edit(item)}>Изменить</button></div>)}</div> : <Empty>Новостей пока нет.</Empty>}</LoadState></>;
}

export function ManageDocuments() {
  const list = useLoad(() => allPages(page => api.documents(page)), "manage-documents");
  const [editing, setEditing] = useState<Document | null>(null); const [title, setTitle] = useState(""); const [category, setCategory] = useState(""); const [fileUrl, setFileUrl] = useState("");
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [success, setSuccess] = useState("");
  function edit(item: Document) { setEditing(item); setTitle(item.title); setCategory(item.category); setFileUrl(item.fileUrl); setError(""); setSuccess(""); window.scrollTo(0, 0); }
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setSuccess("");
    try { if (editing) await api.updateDocument(editing.id, { title, category, fileUrl }); else await api.createDocument({ title, category, fileUrl }); setSuccess(editing ? "Документ обновлён." : "Документ добавлен."); setEditing(null); setTitle(""); setCategory(""); setFileUrl(""); list.reload(); }
    catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  }
  return <><PageTitle eyebrow="ОРГАНИЗАТОР" title="Документы" description="Добавляйте ссылки на положения и правила." /><form className="card form-card" onSubmit={submit}><h2>{editing ? "Редактировать документ" : "Новый документ"}</h2><Notice error={error} success={success} /><label>Название <input required minLength={3} maxLength={200} value={title} onChange={event => setTitle(event.target.value)} /></label><label>Категория <input required maxLength={80} value={category} onChange={event => setCategory(event.target.value)} placeholder="Положение" /></label><label>Ссылка на файл (HTTPS) <input required type="url" pattern="https://.*" value={fileUrl} onChange={event => setFileUrl(event.target.value)} placeholder="https://..." /></label><p className="hint">MVP хранит ссылку на файл. Загрузку файла добавим отдельным этапом.</p><div className="form-actions"><button className="button" disabled={busy}>{busy ? "Сохраняем…" : editing ? "Сохранить" : "Добавить"}</button>{editing && <button type="button" className="button button-secondary" onClick={() => { setEditing(null); setTitle(""); setCategory(""); setFileUrl(""); }}>Отмена</button>}</div></form><div className="section-heading"><h2>Документы</h2></div><LoadState loading={list.loading} error={list.error}>{list.data?.length ? <div className="card list-card">{list.data.map(item => <div className="list-row" key={item.id}><div><strong>{item.title}</strong><small>{item.category} · {date(item.publishedAt)}</small></div><button className="text-link" onClick={() => edit(item)}>Изменить</button></div>)}</div> : <Empty>Документов пока нет.</Empty>}</LoadState></>;
}
