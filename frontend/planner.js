"use strict";
const TASK_PROGRESS = {todo: "待办", doing: "进行中", done: "已完成", archived: "已归档"};
const TASK_PRIORITY = {high: "优先做", normal: "一般", low: "稍后做"};
let personalTasks = [], plannerReady = false, editingTask = null, taskDraftChanged = false, pendingTaskBackup = null;
const plannerFilters = {progress: "pending", query: "", priority: "", date: ""};
const dayFormatter = new Intl.DateTimeFormat("zh-CN", {month: "numeric", day: "numeric", weekday: "short"});

function localDay(day = new Date()) {
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
}
function dayOffset(amount) { const day = new Date(); day.setDate(day.getDate() + amount); return localDay(day); }
function dateLabel(value) {
  if (!value) return "尚未排期";
  const day = new Date(`${value}T12:00:00`);
  const formatter = day.getFullYear() === new Date().getFullYear() ? dayFormatter : new Intl.DateTimeFormat("zh-CN", {year: "numeric", month: "numeric", day: "numeric", weekday: "short"});
  return formatter.format(day);
}
function pendingTask(task) { return ["todo", "doing"].includes(task.status); }

function readTaskFilters() {
  const params = new URLSearchParams(location.search);
  plannerFilters.progress = ["pending", "doing", "done", "archived", "all"].includes(params.get("progress")) ? params.get("progress") : "pending";
  plannerFilters.query = (params.get("q") || "").slice(0, 100);
  plannerFilters.priority = Object.hasOwn(TASK_PRIORITY, params.get("priority")) ? params.get("priority") : "";
  plannerFilters.date = ["today", "week", "overdue", "undated"].includes(params.get("date")) ? params.get("date") : "";
  $("#task-query").value = plannerFilters.query;
  $("#task-priority-filter").value = plannerFilters.priority;
  $("#task-date-filter").value = plannerFilters.date;
}
function syncTaskUrl() {
  if (state.view !== "tasks") return;
  const params = new URLSearchParams({view: "tasks"});
  for (const [name, value] of [["progress", plannerFilters.progress], ["q", plannerFilters.query], ["priority", plannerFilters.priority], ["date", plannerFilters.date]]) {
    if (value && !(name === "progress" && value === "pending")) params.set(name, value);
  }
  history.replaceState(null, "", `/?${params}`);
}

function renderPlanner() {
  const today = localDay(), weekEnd = dayOffset(6), open = personalTasks.filter(pendingTask);
  const overdue = open.filter(task => task.due && task.due < today).length;
  const upcoming = open.filter(task => task.due >= today && task.due <= weekEnd).length;
  const summary = $("#task-summary"); summary.replaceChildren();
  for (const [count, text] of [[open.length, "项未完成"], [upcoming, "项在未来7天"], [overdue, "项已过计划日"]]) {
    const item = element("div"); item.append(element("strong", "", String(count)), element("span", "", text)); summary.append(item);
  }
  const tabs = $("#task-tabs"); tabs.replaceChildren();
  for (const [value, label] of [["pending", "未完成"], ["doing", "进行中"], ["done", "已完成"], ["archived", "已归档"], ["all", "全部"]]) {
    const tab = button(label, () => { plannerFilters.progress = value; renderPlanner(); $("#task-tabs").querySelector(`[data-progress-tab="${value}"]`)?.focus({preventScroll: true}); }, "");
    tab.dataset.progressTab = value; tab.classList.toggle("active", plannerFilters.progress === value); tab.setAttribute("aria-pressed", String(plannerFilters.progress === value)); tabs.append(tab);
  }
  const tasks = personalTasks.filter(task => {
    if (plannerFilters.progress === "pending" && !pendingTask(task)) return false;
    if (!["pending", "all"].includes(plannerFilters.progress) && task.status !== plannerFilters.progress) return false;
    if (plannerFilters.priority && task.priority !== plannerFilters.priority) return false;
    if (plannerFilters.query && !(task.title + task.notes + (state.explore.items.find(item => item.id === task.source_item)?.name || "")).includes(plannerFilters.query)) return false;
    if (plannerFilters.date === "today" && task.due !== today) return false;
    if (plannerFilters.date === "week" && !(task.due >= today && task.due <= weekEnd)) return false;
    if (plannerFilters.date === "overdue" && !(task.due && task.due < today && pendingTask(task))) return false;
    if (plannerFilters.date === "undated" && task.due) return false;
    return true;
  }).sort((a, b) => (a.due || "9999").localeCompare(b.due || "9999") || ["high", "normal", "low"].indexOf(a.priority) - ["high", "normal", "low"].indexOf(b.priority));
  $("#task-result-count").textContent = `当前显示 ${tasks.length} 项 · 已保存 ${personalTasks.length}/100 项（含归档）`;
  const root = $("#personal-task-list"); root.replaceChildren();
  if (!tasks.length) {
    const empty = element("div", "planner-empty");
    empty.append(element("h2", "", personalTasks.length ? "当前筛选没有任务" : "先安排一件小事"), element("p", "", personalTasks.length ? "清除日期或搜索条件，或切换进度筛选。" : "可以自己新增，也可以从成长计划的收藏中生成下一步待办。"));
    empty.append(button(personalTasks.length ? "清除筛选" : "去成长计划", () => {
      if (!personalTasks.length) return changeView("plan");
      Object.assign(plannerFilters, {progress: "all", query: "", priority: "", date: ""});
      $("#task-query").value = ""; $("#task-priority-filter").value = ""; $("#task-date-filter").value = ""; renderPlanner();
    })); root.append(empty);
  }
  tasks.forEach(task => {
    const row = element("article", `personal-task ${task.status === "done" ? "task-done" : ""}`); row.dataset.taskId = task.id;
    const info = element("div", "personal-task-info");
    info.append(element("h2", "", task.title));
    const expired = pendingTask(task) && task.due && task.due < today;
    const meta = element("div", "task-meta");
    meta.append(element("span", `badge ${expired ? "caution" : ""}`, `${dateLabel(task.due)}${expired ? " · 已过计划日" : ""}`), element("span", "", TASK_PRIORITY[task.priority]), element("span", "", TASK_PROGRESS[task.status])); info.append(meta);
    const source = state.explore.items.find(item => item.id === task.source_item);
    if (source) info.append(button(`关联：${source.name} · 查看来源`, () => sourceFor(source), "text-button"));
    if (task.notes) info.append(element("p", "task-notes", task.notes));
    const actions = element("div", "personal-task-actions"); actions.append(button("编辑", () => editPersonalTask(task)));
    if (pendingTask(task)) {
      const done = button("完成", () => updateTaskStatus(task, "done", done)); actions.append(done);
      if (task.status === "todo") { const start = button("开始", () => updateTaskStatus(task, "doing", start), "text-button"); actions.append(start); }
    } else { const restore = button("恢复为待办", () => updateTaskStatus(task, "todo", restore)); actions.append(restore); }
    if (task.status !== "archived") { const archive = button("归档", () => updateTaskStatus(task, "archived", archive), "text-button"); actions.append(archive); }
    actions.querySelectorAll("button").forEach(control => control.setAttribute("aria-label", `${task.title}：${control.textContent}`));
    row.append(info, actions); root.append(row);
  });
  const agenda = $("#task-agenda"); agenda.replaceChildren();
  $("#agenda-range").textContent = `${dateLabel(today)} 至 ${dateLabel(weekEnd)}`;
  for (let index = 0; index < 7; index++) {
    const day = dayOffset(index), entries = open.filter(task => task.due === day);
    const line = element("div", "agenda-day"); line.append(element("h3", "", `${dateLabel(day)}${index === 0 ? " · 今天" : ""}`));
    if (!entries.length) line.append(element("p", "", "暂无安排"));
    entries.slice(0, 3).forEach(task => line.append(button(task.title, () => editPersonalTask(task), "text-button")));
    if (entries.length > 3) line.append(element("p", "", `另有 ${entries.length - 3} 项，可用日期筛选查看。`));
    agenda.append(line);
  }
  $("#export-calendar").disabled = !open.some(task => task.due);
  syncTaskUrl();
}

function editPersonalTask(task = null) {
  editingTask = task; taskDraftChanged = false;
  $("#task-dialog-title").textContent = task ? "编辑任务" : "新增任务";
  const source = task && state.explore.items.find(item => item.id === task.source_item);
  $("#task-source-note").textContent = source ? `来自「${source.name}」的下一步建议。日期请自行核对。` : "自己安排的小任务，可留空日期。";
  $("#personal-task-title").value = task?.title || ""; $("#personal-task-due").value = task?.due || "";
  $("#personal-task-priority").value = task?.priority || "normal"; $("#personal-task-status").value = task?.status || "todo";
  $("#personal-task-notes").value = task?.notes || ""; $("#task-form-status").textContent = "";
  $("#task-dialog").showModal(); $("#personal-task-title").focus();
}
function closePersonalTask() {
  if (taskDraftChanged && !confirm("有未保存的任务内容，放弃这些修改？")) return;
  taskDraftChanged = false; $("#task-dialog").close();
}
async function updateTaskStatus(task, status, control) {
  control.disabled = true;
  try {
    const result = await mutate("/api/tasks", {task: {...task, status}}); personalTasks = result.tasks; renderPlanner();
    const row = document.querySelector(`[data-task-id="${task.id}"]`);
    (row?.querySelector("button") || $("#task-tabs").querySelector(".active"))?.focus({preventScroll: true});
    toast(status === "archived" ? "已归档，可在“已归档”中恢复" : "任务进度已保存");
  } catch (error) { toast(error.message); }
  finally { control.disabled = false; }
}
async function tasksFromChoice(item, control) {
  control.disabled = true;
  try {
    const result = await mutate("/api/tasks/from-choice", {item: item.id}); personalTasks = result.tasks;
    Object.assign(plannerFilters, {progress: "all", query: "", priority: "", date: ""});
    $("#task-query").value = ""; $("#task-priority-filter").value = ""; $("#task-date-filter").value = "";
    changeView("tasks"); toast(result.added ? `已生成 ${result.added} 项待办，日期由你安排` : "这3项建议已在任务中，已保留原进度");
  } catch (error) { toast(error.message); }
  finally { control.disabled = false; }
}
function downloadPlan(content, type, filename) {
  const url = URL.createObjectURL(new Blob([content], {type})); const link = element("a"); link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function initializePlanner() {
  personalTasks = (await api(`/api/tasks?session=${state.session}`)).tasks; plannerReady = true;
  readTaskFilters(); renderPlanner();
  $("#new-task").addEventListener("click", () => editPersonalTask());
  $("#cancel-task").addEventListener("click", closePersonalTask);
  $("#task-dialog").addEventListener("cancel", event => { event.preventDefault(); closePersonalTask(); });
  $("#personal-task-form").addEventListener("input", () => { taskDraftChanged = true; });
  addEventListener("beforeunload", event => { if (taskDraftChanged) { event.preventDefault(); event.returnValue = ""; } });
  $("#personal-task-form").addEventListener("submit", async event => {
    event.preventDefault(); const submit = $("#save-task"); submit.disabled = true; submit.textContent = "正在保存…";
    try {
      const task = {...(editingTask || {}), title: $("#personal-task-title").value, due: $("#personal-task-due").value, priority: $("#personal-task-priority").value, status: $("#personal-task-status").value, notes: $("#personal-task-notes").value};
      const result = await mutate("/api/tasks", {task}); personalTasks = result.tasks; taskDraftChanged = false; $("#task-dialog").close(); renderPlanner(); toast("任务已保存");
    } catch (error) { $("#task-form-status").textContent = error.message; $("#task-form-status").focus(); }
    finally { submit.disabled = false; submit.textContent = "保存任务"; }
  });
  $("#task-query").addEventListener("input", event => { plannerFilters.query = event.target.value.trim(); renderPlanner(); });
  $("#task-priority-filter").addEventListener("change", event => { plannerFilters.priority = event.target.value; renderPlanner(); });
  $("#task-date-filter").addEventListener("change", event => { plannerFilters.date = event.target.value; renderPlanner(); });
  $("#export-calendar").addEventListener("click", async () => {
    try {
      const response = await fetch(`/api/tasks/calendar?session=${state.session}`);
      if (!response.ok) throw new Error("日历导出未完成，请重试。");
      downloadPlan(await response.text(), "text/calendar;charset=utf-8", "初到-个人计划.ics"); toast("已导出个人计划日历");
    } catch (error) { toast(error.message); }
  });
  $("#export-task-backup").addEventListener("click", async () => {
    try { const data = await api(`/api/tasks/backup?session=${state.session}`); downloadPlan(JSON.stringify(data, null, 2), "application/json", "初到-任务备份.json"); toast("任务备份已导出"); }
    catch (error) { toast(error.message); }
  });
  $("#task-backup-file").addEventListener("change", async event => {
    const file = event.target.files[0]; if (!file) return;
    $("#backup-status").textContent = "正在校验备份…";
    try {
      if (file.size > 500000) throw new Error("请选择500KB以内的任务备份。");
      const data = JSON.parse(await file.text());
      const preview = await mutate("/api/tasks/import-preview", {backup: data}); pendingTaskBackup = data;
      $("#task-import-summary").textContent = `将新增 ${preview.added} 项，跳过 ${preview.skipped} 项重复任务。`;
      $("#task-import-titles").replaceChildren(...preview.titles.map(text => element("li", "", text)));
      $("#task-import-error").textContent = ""; $("#task-import-dialog").showModal(); $("#backup-status").textContent = "已校验，请检查导入预览。";
    } catch (error) { $("#backup-status").textContent = error instanceof SyntaxError ? "文件不是有效JSON，请选择原始任务备份。" : error.message; }
    finally { event.target.value = ""; }
  });
  $("#cancel-task-import").addEventListener("click", () => { pendingTaskBackup = null; $("#task-import-dialog").close(); $("#backup-status").textContent = "已取消导入，现有任务保留。"; });
  $("#task-import-dialog").addEventListener("cancel", () => { pendingTaskBackup = null; $("#backup-status").textContent = "已取消导入，现有任务保留。"; });
  $("#confirm-task-import").addEventListener("click", async () => {
    const submit = $("#confirm-task-import"); submit.disabled = true;
    try {
      const result = await mutate("/api/tasks/import", {backup: pendingTaskBackup}); personalTasks = result.tasks; pendingTaskBackup = null;
      $("#task-import-dialog").close(); renderPlanner(); $("#backup-status").textContent = `已新增 ${result.added} 项，跳过 ${result.skipped} 项重复任务；原有进度保留。`;
    } catch (error) { $("#task-import-error").textContent = error.message; }
    finally { submit.disabled = false; }
  });
}
