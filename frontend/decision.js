"use strict";
const KIND_NAMES = {bed: "床位参考", contest: "竞赛", club: "社团", union: "学生组织"};
const STATUS_NAMES = {planned: "准备了解", doing: "正在尝试", done: "已完成了解"};

function sourceFor(item) {
  changeView("sources");
  $("#source-filter").value = item.source;
  renderSources(item.source);
  $("#source-filter").focus();
}

function savedItem(id) { return state.saved.find(item => item.id === id); }

async function saveChoice(item, status, control) {
  const containerId = control?.closest("[id]")?.id;
  const wasProgress = control?.tagName === "SELECT";
  if (control) control.disabled = true;
  try {
    const result = await mutate("/api/saved", {item: item.id, status});
    state.saved = result.items;
    renderSaved(); renderIdealBeds(); renderRecommendations();
    renderContestList(); renderClubList(); renderUnionList();
    if (state.view === "dorm-bed") renderDormBeds(state.dormRoom);
    if (containerId) {
      const container = document.getElementById(containerId);
      const selector = wasProgress ? `[data-progress="${item.id}"]` : `[data-save="${item.id}"]`;
      container?.querySelector(selector)?.focus({preventScroll:true});
    }
    toast(status === "removed" ? "已移除收藏" : "计划已保存，刷新后可继续");
  } catch (error) { toast(error.message); }
  finally { if (control) control.disabled = false; }
}

function choiceActions(item) {
  const actions = element("div", "choice-actions");
  const save = button(savedItem(item.id) ? "已收藏 · 移除" : "收藏到我的计划", () => saveChoice(item, savedItem(item.id) ? "removed" : "planned", save));
  save.dataset.save = item.id;
  save.setAttribute("aria-label", `${item.name}：${savedItem(item.id) ? "移除收藏" : "收藏到我的计划"}`);
  const compare = button(state.compare.includes(item.id) ? "已加入对比" : "加入对比", () => toggleCompare(item, compare));
  compare.dataset.compare = item.id;
  compare.setAttribute("aria-pressed", String(state.compare.includes(item.id)));
  compare.setAttribute("aria-label", `${item.name}：加入或移出对比`);
  actions.append(save, compare, button("查看来源", () => sourceFor(item), "text-button"));
  return actions;
}

function decisionCard(item) {
  const card = element("article", "decision-card");
  const head = element("div", "decision-head");
  if (item.logo) {
    const logo = element("img", "club-logo");
    logo.src = item.logo; logo.alt = "交接示意徽章"; logo.width = 52; logo.height = 52; logo.loading = "lazy";
    head.append(logo);
  }
  const title = element("h3", "", item.name);
  head.append(title);
  card.append(head, element("p", "decision-category", item.kind === "contest" ? item.categories.join(" / ") : item.category));
  if (item.score !== undefined) card.append(element("p", "match-score", `参考排序分 ${item.score} · 同分并列`));
  const details = element("details", "decision-details");
  details.append(element("summary", "", "查看内容与适合人群"), element("p", "", item.intro));
  if (item.activities) details.append(element("p", "", `典型活动：${item.activities.join("、")}`));
  if (item.works) details.append(element("p", "", `典型工作：${item.works}`));
  if (item.audience || item.fit) details.append(element("p", "", `适合人群：${item.audience || item.fit}`));
  if (item.pros) details.append(element("p", "", `位置参考：${item.pros.join("；")}`));
  if (item.kind === "contest") details.append(element("p", "", `原指南参考标签：${item.level}。当届参赛条件、费用、赛程与本校认定待核对。`));
  card.append(details);
  if (item.reasons) {
    const reasons = element("ul", "match-reasons");
    item.reasons.forEach(reason => reasons.append(element("li", "", reason)));
    card.append(reasons);
  }
  const cautions = item.cautions || (item.cons ? [item.note, ...item.cons] : [item.note]);
  card.append(element("p", "decision-caution", cautions.join(" ")));
  if (item.official_url) {
    const link = safeLink(item.official_url);
    if (link) { link.textContent = "主办方入口（当届规则另核对）"; card.append(link); }
  }
  card.append(choiceActions(item));
  return card;
}

function renderDecisionList(target, entries) {
  target.replaceChildren();
  if (!entries.length) target.append(element("p", "empty-choices", "没有匹配项。试试清除筛选，或换一个兴趣方向。"));
  entries.forEach(item => target.append(decisionCard(item)));
}

function toggleCompare(item, control) {
  const exists = state.compare.includes(item.id);
  if (exists) state.compare = state.compare.filter(id => id !== item.id);
  else {
    if (state.compare.length && state.explore.items.find(x => x.id === state.compare[0]).kind !== item.kind) {
      toast("请先清空当前对比，再选择另一类选项。"); return;
    }
    if (state.compare.length >= 3) { toast("一次最多对比 3 项，请先移出一项。"); return; }
    state.compare.push(item.id);
  }
  document.querySelectorAll("[data-compare]").forEach(node => {
    const selected = state.compare.includes(node.dataset.compare);
    node.textContent = selected ? "已加入对比" : "加入对比";
    node.setAttribute("aria-pressed", String(selected));
  });
  renderCompareBar();
}

function renderCompareBar() {
  $("#compare-bar").hidden = !state.compare.length;
  document.body.classList.toggle("compare-open", !!state.compare.length);
  $("#compare-count").textContent = `已选 ${state.compare.length}/3 项：${state.compare.map(id => state.explore.items.find(x => x.id === id).name).join("、")}`;
  $("#open-compare").disabled = state.compare.length < 2;
}

function showComparison() {
  const items = state.compare.map(id => state.explore.items.find(x => x.id === id));
  if (items.length < 2) return;
  const table = element("table", "comparison-table");
  const caption = element("caption", "", `${KIND_NAMES[items[0].kind]}对比 · ${items.length}项`);
  table.append(caption);
  const header = element("tr");
  header.append(element("th", "", "比较维度"));
  items.forEach(item => header.append(element("th", "", item.name)));
  header.querySelectorAll("th").forEach(node => node.scope = "col");
  const thead = element("thead"); thead.append(header); table.append(thead);
  const rows = [["分类 / 位置", i => i.category], ["内容", i => i.intro]];
  if (items[0].kind === "bed") {
    Object.entries(state.explore.priorities).forEach(([key, label]) => rows.push([`${label}参考 0–3`, i => `${i.metrics[key]}/3`]));
    rows.push(["注意点", i => i.cons.join("；")]);
  } else {
    rows.push(["活动 / 工作", i => (i.activities || []).join("、") || i.works || "当届内容待核对"], ["适合人群", i => i.audience || i.fit || "请先了解准备基础"]);
  }
  rows.push(["资料与限制", i => `${i.source}。${i.note}`]);
  const body = element("tbody");
  rows.forEach(([label, get]) => {
    const row = element("tr"); const th = element("th", "", label); th.scope = "row"; row.append(th);
    items.forEach(item => row.append(element("td", "", get(item)))); body.append(row);
  });
  table.append(body);
  $("#comparison-body").replaceChildren(table);
  $("#comparison-dialog").showModal();
}

function readPreferences() {
  return {
    interests: Array.from(document.querySelectorAll("#interest-options input:checked"), node => node.value),
    college: $("#preferred-college").value, hours: $("#weekly-hours").value, room: $("#preferred-room").value,
    priorities: Object.fromEntries(Object.keys(state.explore.priorities).map(key => [key, Number($(`#priority-${key}`).value)]))
  };
}

function renderPreferences() {
  const profile = state.profile || {interests: [], priorities: {}, college: "", hours: "medium", room: "liuren"};
  const interests = $("#interest-options"); interests.replaceChildren();
  state.explore.interests.forEach(item => {
    const label = element("label", "interest-option"); const input = element("input");
    input.type = "checkbox"; input.name = "interests"; input.value = item.id; input.checked = profile.interests.includes(item.id);
    label.append(input, document.createTextNode(item.label)); interests.append(label);
  });
  const college = $("#preferred-college"); college.replaceChildren();
  ["", ...state.explore.colleges].forEach(value => { const option = element("option", "", value || "暂不限制专业方向"); option.value = value; college.append(option); });
  college.value = profile.college;
  $("#weekly-hours").value = profile.hours; $("#preferred-room").value = profile.room;
  const priorities = $("#bed-priorities"); priorities.replaceChildren();
  Object.entries(state.explore.priorities).forEach(([key, text]) => {
    const label = element("label", "preference-field", text); const select = element("select");
    select.id = `priority-${key}`; select.name = key;
    ["不在意", "一般", "比较在意", "非常在意"].forEach((text, value) => { const option = element("option", "", text); option.value = String(value); select.append(option); });
    select.value = String(profile.priorities[key] ?? 1); label.append(select); priorities.append(label);
  });
}

function renderRecommendations() {
  const tabs = $("#recommend-tabs"); tabs.replaceChildren();
  Object.entries(KIND_NAMES).forEach(([kind, text]) => {
    const tab = button(text, () => { state.recommendKind = kind; renderRecommendations(); });
    tab.classList.toggle("active", state.recommendKind === kind); tab.setAttribute("aria-pressed", String(state.recommendKind === kind)); tabs.append(tab);
  });
  const list = $("#recommend-list");
  if (!state.recommendations) { list.replaceChildren(element("p", "empty-choices", "选择兴趣和床位偏好，再点击「保存偏好并匹配」。")); return; }
  $("#recommend-method").textContent = state.recommendations.method;
  renderDecisionList(list, state.recommendations.groups[state.recommendKind]);
}

function renderSaved() {
  const root = $("#saved-list"); root.replaceChildren();
  $("#saved-count").textContent = `${state.saved.length}/30 项收藏 · ${state.saved.filter(x => x.status === "done").length} 项已完成了解`;
  if (!state.saved.length) { root.append(element("p", "empty-choices", "从推荐、竞赛或社团中收藏选项，这里会列出下一步建议。")); return; }
  state.saved.forEach(item => {
    const row = element("article", "saved-row");
    const info = element("div"); info.append(element("h3", "", item.name), element("p", "decision-category", `${KIND_NAMES[item.kind]} · ${STATUS_NAMES[item.status]}`));
    const steps = element("ol"); item.actions.forEach(action => steps.append(element("li", "", action))); info.append(steps);
    row.append(info);
    const controls = element("div", "saved-controls");
    const label = element("label", "preference-field", "了解进度"); const select = element("select"); select.name = "progress"; select.dataset.progress = item.id;
    Object.entries(STATUS_NAMES).forEach(([value, name]) => { const option = element("option", "", name); option.value = value; select.append(option); }); select.value = item.status;
    select.addEventListener("change", () => saveChoice(item, select.value, select)); label.append(select);
    controls.append(label, button("查看来源", () => sourceFor(item), "text-button"));
    const create = button("生成3项下一步待办", () => tasksFromChoice(item, create), "secondary"); controls.append(create);
    const remove = button("移除收藏", () => saveChoice(item, "removed", remove), "text-button"); controls.append(remove); row.append(controls); root.append(row);
  });
}

function initializeDecision() {
  renderPreferences(); renderRecommendations(); renderSaved(); renderCompareBar();
  $("#preferences-form").addEventListener("submit", async event => {
    event.preventDefault(); const submit = $("#match-preferences"); submit.disabled = true; submit.textContent = "正在匹配…";
    try {
      const result = await mutate("/api/profile", {profile: readPreferences()});
      state.profile = result.profile; state.recommendations = result;
      renderRecommendations(); $("#preference-status").textContent = "偏好已保存。已按你的选择更新推荐。";
    } catch (error) { $("#preference-status").textContent = error.message; }
    finally { submit.disabled = false; submit.textContent = "保存偏好并匹配"; }
  });
  $("#open-compare").addEventListener("click", showComparison);
  $("#clear-compare").addEventListener("click", () => { state.compare = []; document.querySelectorAll("[data-compare]").forEach(node => { node.textContent = "加入对比"; node.setAttribute("aria-pressed", "false"); }); renderCompareBar(); });
  $("#close-comparison").addEventListener("click", () => $("#comparison-dialog").close());
}
