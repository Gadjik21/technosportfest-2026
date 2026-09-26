import { useState, type FormEvent } from "react";
import { api, type AdminUser, type Competition, type Document, type News, type Page, type Participant, type PermissionGroup, type ResultDraft, type Role, type SubmissionForGrading, type Task } from "./api";
import { StandingsTable } from "./PublicPages";
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
  const tasks = useLoad(() => api.tasks(id), `manage-tasks-${id}`);
  const [tab, setTab] = useState<"participants" | "tasks" | "details">("participants");
  const [showPublishConfirm, setShowPublishConfirm] = useState(false);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [success, setSuccess] = useState("");
  const hasTasks = !!tasks.data?.length;
  async function publish() {
    setShowPublishConfirm(false);
    setBusy(true); setError("");
    try { await api.publishCompetition(id); setSuccess("Соревнование опубликовано."); competition.reload(); }
    catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  }
  return <LoadState loading={competition.loading} error={competition.error}>{competition.data && <><div className="breadcrumb"><Link to="/manage/competitions">Соревнования</Link><span>/</span>{competition.data.title}</div><PageTitle eyebrow="УПРАВЛЕНИЕ СОРЕВНОВАНИЕМ" title={competition.data.title} description={`${competition.data.discipline.name} · ${date(competition.data.startsAt)}`} action={<Status value={competition.data.status} />} /><Notice error={error} success={success} />{competition.data.status === "draft" && <div className="callout"><div><strong>Черновик виден только организаторам.</strong><p>Проверьте даты, дисциплину, описание и задания (если это контест) перед публикацией.</p></div><button className="button" disabled={busy} onClick={() => setShowPublishConfirm(true)}>Опубликовать</button></div>}{showPublishConfirm && <ConfirmDialog title="Опубликовать соревнование?" confirmLabel="Опубликовать" onCancel={() => setShowPublishConfirm(false)} onConfirm={publish}>Спортсмены увидят карточку и смогут подать заявку.</ConfirmDialog>}<div className="tabs"><button className={tab === "participants" ? "active" : ""} onClick={() => setTab("participants")}>Участники и результаты</button><button className={tab === "tasks" ? "active" : ""} onClick={() => setTab("tasks")}>Задания{hasTasks ? ` (${tasks.data!.length})` : ""}</button><button className={tab === "details" ? "active" : ""} onClick={() => setTab("details")}>Параметры</button></div>{tab === "details" ? competition.data.status === "draft" ? <CompetitionForm competition={competition.data} onSaved={() => { setSuccess("Соревнование сохранено."); competition.reload(); }} /> : <div className="card form-card"><p>После публикации параметры соревнования не редактируются.</p><Link className="button button-secondary" to={`/competitions/${id}`}>Открыть карточку</Link></div> : tab === "tasks" ? <ManageTasks competition={competition.data} tasks={tasks} /> : hasTasks ? <ContestGrading competition={competition.data} onFinished={() => { competition.reload(); tasks.reload(); }} /> : <ParticipantsAndResults competition={competition.data} onPublished={competition.reload} />}</>}</LoadState>;
}

function ManageTasks({ competition, tasks }: { competition: Competition; tasks: { data: Task[] | null; loading: boolean; error: string; reload: () => void } }) {
  const isDraft = competition.status === "draft";
  const [form, setForm] = useState<{ title: string; statement: string; maxScore: string } | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [success, setSuccess] = useState("");
  function startCreate() { setEditingId(null); setForm({ title: "", statement: "", maxScore: "100" }); setError(""); setSuccess(""); }
  function startEdit(task: Task) { setEditingId(task.id); setForm({ title: task.title, statement: task.statement, maxScore: String(task.maxScore) }); setError(""); setSuccess(""); }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!form) return;
    const maxScore = Number(form.maxScore);
    if (!Number.isInteger(maxScore) || maxScore < 1) { setError("Максимальный балл должен быть целым числом от 1."); return; }
    setBusy(true); setError(""); setSuccess("");
    try {
      if (editingId) await api.updateTask(competition.id, editingId, { title: form.title, statement: form.statement, maxScore });
      else await api.createTask(competition.id, { title: form.title, statement: form.statement, maxScore });
      setSuccess(editingId ? "Задание обновлено." : "Задание добавлено."); setForm(null); setEditingId(null); tasks.reload();
    } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  }
  async function remove(taskId: string) {
    setBusy(true); setError(""); setSuccess("");
    try { await api.deleteTask(competition.id, taskId); tasks.reload(); }
    catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  }
  return <>
    <div className="section-heading"><div><h2>Задания</h2><p className="muted">{isDraft ? "Пока черновик — задания можно добавлять, менять и удалять. Если добавить хотя бы одно, после публикации соревнование станет контестом с приёмом решений." : "После публикации задания менять нельзя."}</p></div>{isDraft && !form && <button className="button" onClick={startCreate}>+ Добавить задание</button>}</div>
    <Notice error={error} success={success} />
    {form && <form className="card form-card" onSubmit={submit}><label>Название <input required minLength={2} maxLength={200} value={form.title} onChange={event => setForm({ ...form, title: event.target.value })} /></label><label>Условие <textarea required rows={5} maxLength={10000} value={form.statement} onChange={event => setForm({ ...form, statement: event.target.value })} /></label><label>Максимальный балл <input required type="number" min="1" max="1000" value={form.maxScore} onChange={event => setForm({ ...form, maxScore: event.target.value })} /></label><div className="form-actions"><button className="button" disabled={busy}>{busy ? "Сохраняем…" : editingId ? "Сохранить" : "Добавить"}</button><button type="button" className="button button-secondary" onClick={() => { setForm(null); setEditingId(null); }}>Отмена</button></div></form>}
    <LoadState loading={tasks.loading} error={tasks.error}>{tasks.data?.length ? <div className="card list-card">{tasks.data.map(task => <div className="list-row" key={task.id}><div><strong>{task.title}</strong><small>Макс. балл: {task.maxScore}</small></div>{isDraft && <div className="form-actions"><button className="text-link" onClick={() => startEdit(task)}>Изменить</button><button className="text-link" onClick={() => remove(task.id)}>Удалить</button></div>}</div>)}</div> : <Empty>{isDraft ? "Заданий пока нет. Без заданий это обычное соревнование — результаты вносятся вручную." : "Заданий нет."}</Empty>}</LoadState>
  </>;
}

function ContestGrading({ competition, onFinished }: { competition: Competition; onFinished: () => void }) {
  const id = competition.id;
  const participants = useLoad(() => allPages(page => api.participants(id, page)), `contest-participants-${id}`);
  const submissions = useLoad(() => api.submissionsForGrading(id), `contest-submissions-${id}-${competition.status}`);
  const results = useLoad(() => api.results(id), `contest-results-${id}-${competition.status}`);
  const [scores, setScores] = useState<Record<string, string>>({});
  const [showFinishConfirm, setShowFinishConfirm] = useState(false);
  const [busyId, setBusyId] = useState(""); const [error, setError] = useState(""); const [success, setSuccess] = useState("");
  const getScore = (submission: SubmissionForGrading) => scores[submission.id] ?? (submission.score ?? "").toString();
  async function grade(submission: SubmissionForGrading) {
    const value = getScore(submission);
    const score = Number(value);
    if (!Number.isInteger(score) || score < 0 || score > submission.taskMaxScore) { setError(`Балл должен быть от 0 до ${submission.taskMaxScore}.`); return; }
    setBusyId(submission.id); setError(""); setSuccess("");
    try { await api.gradeSubmission(id, submission.id, { score }); setSuccess("Оценка сохранена."); submissions.reload(); }
    catch (reason) { setError(errorMessage(reason)); } finally { setBusyId(""); }
  }
  async function finish() {
    setShowFinishConfirm(false); setBusyId("finish"); setError(""); setSuccess("");
    try { await api.finishContest(id); setSuccess("Контест завершён, результаты опубликованы."); onFinished(); }
    catch (reason) { setError(errorMessage(reason)); } finally { setBusyId(""); }
  }
  if (competition.status === "completed") return <>
    <div className="section-heading"><h2>Итог</h2></div>
    <LoadState loading={results.loading} error={results.error}>{results.data?.items.length ? <div className="card table-card"><div className="table-wrap"><table><thead><tr><th>Место</th><th>Участник</th><th>Результат</th><th>Очки рейтинга</th></tr></thead><tbody>{results.data.items.map(item => <tr key={item.id}><td>{item.place}</td><td>{item.fullName}</td><td>{item.scoreText || "—"}</td><td><strong>{item.points}</strong></td></tr>)}</tbody></table></div></div> : <Empty>Результатов нет.</Empty>}</LoadState>
    <div className="section-heading"><h2>Результаты по заданиям</h2></div>
    <StandingsTable competitionId={id} />
  </>;
  const ungraded = submissions.data?.filter(item => item.score === null).length ?? 0;
  return <>
    <div className="section-heading"><div><h2>Участники</h2><p className="muted">Все, кто подал заявку на это соревнование.</p></div></div>
    <LoadState loading={participants.loading} error={participants.error}>{participants.data?.length ? <div className="card table-card"><div className="table-wrap"><table><thead><tr><th>Участник</th><th>Город / учёба</th><th>Заявка подана</th><th></th></tr></thead><tbody>{participants.data.map(participant => <tr key={participant.registrationId}><td><strong>{participant.fullName}</strong></td><td>{participant.locality || "—"}<small>{participant.education || ""}</small></td><td>{date(participant.registeredAt)}</td><td><RemoveParticipantButton competitionId={id} registrationId={participant.registrationId} fullName={participant.fullName} onRemoved={() => { participants.reload(); submissions.reload(); }} /></td></tr>)}</tbody></table></div></div> : <Empty>Участников пока нет.</Empty>}</LoadState>
    <div className="section-heading"><div><h2>Проверка решений</h2><p className="muted">Выставите баллы по каждому решению, затем завершите контест — баллы просуммируются и опубликуются как результат.</p></div><button className="button" disabled={!submissions.data?.length || busyId === "finish"} onClick={() => setShowFinishConfirm(true)}>Завершить контест</button></div>
    {showFinishConfirm && <ConfirmDialog title="Завершить контест?" confirmLabel="Завершить" onCancel={() => setShowFinishConfirm(false)} onConfirm={finish}>{ungraded > 0 ? `Есть ${ungraded} непроверенных решений — сначала оцените их, иначе завершение не пройдёт.` : "Баллы по заданиям просуммируются в итоговый результат, соревнование завершится, рейтинг обновится."}</ConfirmDialog>}
    <Notice error={error || submissions.error} success={success} />
    <LoadState loading={submissions.loading} error="">{submissions.data?.length ? <div className="card table-card"><div className="table-wrap"><table><thead><tr><th>Участник</th><th>Задание</th><th>Решение</th><th>Балл</th><th></th></tr></thead><tbody>{submissions.data.map(submission => <tr key={submission.id}><td><strong>{submission.athleteFullName}</strong></td><td>{submission.taskTitle}<small>макс. {submission.taskMaxScore}</small></td><td>{submission.kind === "link" ? <a href={submission.content} target="_blank" rel="noopener noreferrer">Открыть ссылку</a> : <span className="clamp">{submission.content}</span>}</td><td><input aria-label={`Балл: ${submission.athleteFullName}, ${submission.taskTitle}`} className="place-input" type="number" min="0" max={submission.taskMaxScore} value={getScore(submission)} onChange={event => setScores({ ...scores, [submission.id]: event.target.value })} /></td><td><button className="button button-small button-secondary" disabled={!!busyId} onClick={() => grade(submission)}>{busyId === submission.id ? "…" : submission.score !== null ? "Обновить" : "Сохранить"}</button></td></tr>)}</tbody></table></div></div> : <Empty>Решений пока нет — они появятся, как только спортсмены начнут отправлять ответы.</Empty>}</LoadState>
  </>;
}

function RemoveParticipantButton({ competitionId, registrationId, fullName, onRemoved }: { competitionId: string; registrationId: string; fullName: string; onRemoved: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function remove() {
    setBusy(true); setError("");
    try { await api.removeRegistration(competitionId, registrationId); setConfirming(false); onRemoved(); }
    catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  }
  return <>
    <button className="text-link" disabled={busy} onClick={() => setConfirming(true)}>Удалить</button>
    {confirming && <ConfirmDialog title="Убрать участника?" confirmLabel="Убрать" onCancel={() => setConfirming(false)} onConfirm={remove}>{fullName} исчезнет из списка участников, заявку придётся подавать заново.{error && <><br /><span className="notice notice-error">{error}</span></>}</ConfirmDialog>}
  </>;
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
    <LoadState loading={participants.loading || (competition.status === "published" && drafts.loading) || (competition.status === "completed" && results.loading)} error="">{competition.status === "completed" ? results.data?.items.length ? <div className="card table-card"><div className="table-wrap"><table><thead><tr><th>Место</th><th>Участник</th><th>Результат</th><th>Очки</th></tr></thead><tbody>{results.data.items.map(item => <tr key={item.id}><td>{item.place}</td><td>{item.fullName}</td><td>{item.scoreText || "—"}</td><td><strong>{item.points}</strong></td></tr>)}</tbody></table></div></div> : <Empty>Результатов нет.</Empty> : participants.data?.length ? <><div className="card table-card"><div className="table-wrap"><table><thead><tr><th>Участник</th><th>Город / учёба</th><th>Место</th><th>Результат</th><th></th><th></th></tr></thead><tbody>{participants.data.map(participant => { const value = getEdit(participant); return <tr key={participant.registrationId}><td><strong>{participant.fullName}</strong><small>{date(participant.registeredAt)}</small></td><td>{participant.locality || "—"}<small>{participant.education || ""}</small></td><td><input aria-label={`Место: ${participant.fullName}`} className="place-input" type="number" min="1" value={value.place} onChange={event => change(participant.registrationId, { place: event.target.value }, participant)} /></td><td><input aria-label={`Результат: ${participant.fullName}`} maxLength={500} value={value.scoreText} onChange={event => change(participant.registrationId, { scoreText: event.target.value }, participant)} placeholder="Например, 4 задачи" /></td><td><button className="button button-small button-secondary" disabled={!!busyId} onClick={() => save(participant)}>{busyId === participant.registrationId ? "…" : "Сохранить"}</button></td><td><RemoveParticipantButton competitionId={id} registrationId={participant.registrationId} fullName={participant.fullName} onRemoved={() => { participants.reload(); drafts.reload(); }} /></td></tr>; })}</tbody></table></div></div><p className="hint">Сохранено черновиков: {drafts.data?.length ?? 0} из {participants.data.length} участников. Публикация начислит 100 / 70 / 50 / 20 очков за 1 / 2 / 3 / остальные места.</p></> : <Empty>Участников пока нет.</Empty>}</LoadState>
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

const actionLabel = (code: string) => {
  const action = code.split(".").pop() ?? code;
  return ({ view: "Просмотр", create: "Создание", edit: "Редактирование", delete: "Удаление", publish: "Публикация", save: "Сохранение", tasks: "Задания", grade: "Проверка решений", manage: "Управление" } as Record<string, string>)[action] ?? action;
};

function PermissionCheckboxes({ groups, value, onChange }: { groups: PermissionGroup[]; value: Set<string>; onChange: (next: Set<string>) => void }) {
  const toggle = (code: string) => {
    const next = new Set(value);
    if (next.has(code)) next.delete(code); else next.add(code);
    onChange(next);
  };
  return <div className="permission-grid">{groups.map(group => <fieldset className="permission-group" key={group.section}><legend>{group.label}</legend>{group.codes.map(code => <label className="checkbox-row" key={code}><input type="checkbox" checked={value.has(code)} onChange={() => toggle(code)} /><span className="permission-action">{actionLabel(code)}</span><small>{code}</small></label>)}</fieldset>)}</div>;
}

type RoleForm = { name: string; description: string; permissions: Set<string> };

export function ManageRoles() {
  const roles = useLoad(api.roles, "admin-roles");
  const groups = useLoad(api.permissionCatalog, "admin-permissions");
  const [editingId, setEditingId] = useState<string | null>(null); // null = скрыта форма
  const [form, setForm] = useState<RoleForm | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [success, setSuccess] = useState("");
  const startCreate = () => { setEditingId(null); setForm({ name: "", description: "", permissions: new Set() }); setError(""); setSuccess(""); window.scrollTo(0, 0); };
  const startEdit = (role: Role) => { setEditingId(role.id); setForm({ name: role.name, description: role.description ?? "", permissions: new Set(role.permissions) }); setError(""); setSuccess(""); window.scrollTo(0, 0); };
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!form) return;
    setBusy(true); setError(""); setSuccess("");
    try {
      if (editingId) {
        await api.updateRole(editingId, { name: form.name, description: form.description || null });
        await api.setRolePermissions(editingId, [...form.permissions]);
        setSuccess("Роль сохранена.");
      } else {
        await api.createRole({ name: form.name, description: form.description || null, permissions: [...form.permissions] });
        setSuccess("Роль создана.");
      }
      setForm(null); setEditingId(null); roles.reload();
    } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  }
  async function remove(role: Role) {
    setBusy(true); setError(""); setSuccess("");
    try { await api.deleteRole(role.id); setSuccess(`Роль «${role.name}» удалена.`); roles.reload(); }
    catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  }
  const removeTargetState = useState<Role | null>(null);
  const removeTarget = removeTargetState[0];
  const setRemoveTarget = removeTargetState[1];
  return <><PageTitle eyebrow="MASTER ADMIN" title="Роли и права" description="Создавайте роли и назначайте им доступ к разделам. Системные роли менять нельзя." action={<button className="button" onClick={startCreate}>+ Новая роль</button>} />
    {form && <form className="card form-card" onSubmit={submit}><h2>{editingId ? "Изменить роль" : "Новая роль"}</h2><Notice error={error} success={success} /><label>Название <input required minLength={2} maxLength={50} value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} /></label><label>Описание <input maxLength={200} value={form.description} onChange={event => setForm({ ...form, description: event.target.value })} /></label><LoadState loading={groups.loading} error={groups.error}>{groups.data && <PermissionCheckboxes groups={groups.data} value={form.permissions} onChange={permissions => setForm({ ...form, permissions })} />}</LoadState><p className="hint">Изменения прав вступают в силу после повторного входа пользователя.</p><div className="form-actions"><button className="button" disabled={busy || groups.loading}>{busy ? "Сохраняем…" : editingId ? "Сохранить" : "Создать роль"}</button><button type="button" className="button button-secondary" onClick={() => { setForm(null); setEditingId(null); }}>Отмена</button></div></form>}
    <Notice error={error || roles.error} success={success} />
    <LoadState loading={roles.loading} error="">{roles.data?.length ? <div className="card list-card">{roles.data.map(role => <div className="list-row" key={role.id}><div><strong>{role.name} {role.isSystem && <span className="status status-completed">системная</span>}</strong><small>{role.description || "Без описания"} · прав: {role.permissions.length}</small></div><div className="form-actions">{!role.isSystem && <><button className="text-link" onClick={() => startEdit(role)}>Изменить</button><button className="text-link" onClick={() => setRemoveTarget(role)}>Удалить</button></>}</div></div>)}</div> : <Empty>Ролей пока нет. Создайте первую роль.</Empty>}</LoadState>
    {removeTarget && <ConfirmDialog title={`Удалить роль «${removeTarget.name}»?`} confirmLabel="Удалить" onCancel={() => setRemoveTarget(null)} onConfirm={() => { const role = removeTarget; setRemoveTarget(null); void remove(role); }}>Роль можно удалить, только если она не назначена ни одному пользователю.</ConfirmDialog>}
  </>;
}

export function ManageUsers() {
  const users = useLoad(() => allPages(page => api.users(page)), "admin-users");
  const roles = useLoad(api.roles, "admin-users-roles");
  const [busyId, setBusyId] = useState(""); const [error, setError] = useState(""); const [success, setSuccess] = useState("");
  async function assign(user: AdminUser, roleId: string) {
    setBusyId(user.id); setError(""); setSuccess("");
    try { await api.assignRole(user.id, roleId); setSuccess(`Роль пользователя ${user.email} изменена — вступит в силу после его входа.`); users.reload(); }
    catch (reason) { setError(errorMessage(reason)); } finally { setBusyId(""); }
  }
  return <><PageTitle eyebrow="MASTER ADMIN" title="Пользователи" description="Назначайте роли — доступ к разделам появится после следующего входа пользователя." />
    <Notice error={error || users.error || roles.error} success={success} />
    <LoadState loading={users.loading || roles.loading} error="">{users.data?.length ? <div className="card table-card"><div className="table-wrap"><table><thead><tr><th>Пользователь</th><th>Роль</th></tr></thead><tbody>{users.data.map(user => <tr key={user.id}><td><strong>{user.fullName || user.email}</strong><small>{user.email}</small></td><td><select aria-label={`Роль: ${user.email}`} value={user.roleId} disabled={busyId === user.id} onChange={event => assign(user, event.target.value)}>{roles.data?.map(role => <option key={role.id} value={role.id}>{role.name}{role.isSystem ? " (системная)" : ""}</option>)}</select></td></tr>)}</tbody></table></div></div> : <Empty>Пользователей пока нет.</Empty>}</LoadState>
  </>;
}
