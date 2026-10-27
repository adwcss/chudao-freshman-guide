"use strict";
const $ = (selector) => document.querySelector(selector);
const LABELS = {official_verified: "官方入口已核对", inherited_reference: "交接资料待核对", third_party: "第三方参考", map_reference: "交接地图参考"};
const state = {catalog: null, sources: [], checked: {}, messages: [], busy: false, faq: 0, zoom: 1, mapCategory: "", mapQuery: "", session: "", view: "chat", explore: null, saved: [], profile: null, recommendations: null, recommendKind: "bed", compare: [], dorm: null, dormRoom: null, idealBeds: [], contest: null, contestCat: "", contestLevel: "", contestKw: "", club: null, clubCat: "", clubKw: "", union: null, unionCat: "", unionKw: ""};
try {
  state.session = localStorage.getItem("freshman-session-v1") || crypto.randomUUID().replaceAll("-", "");
  localStorage.setItem("freshman-session-v1", state.session);

} catch {
  state.session = crypto.randomUUID().replaceAll("-", "");
}
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function button(text, callback, className = "secondary") {
  const node = element("button", className, text);
  node.type = "button";
  node.addEventListener("click", callback);
  return node;
}
let toastTimer;
function toast(text) {
  $("#toast").textContent = text;
  $("#toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $("#toast").hidden = true; }, 3500);
}
async function api(path, options = {}) {
  const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "请求失败，请重试。");
  return data;
}
function mutate(path, payload, method = "POST") {
  return api(path, {method, body: JSON.stringify({session: state.session, ...payload})});
}
function changeView(view, push = true) {
  state.view = ["arrival", "preparation", "chat", "map", "plan", "tasks", "dorm", "dorm-bed", "contest", "club", "union", "checklist", "sources"].includes(view) ? view : "arrival";
  document.querySelectorAll(".view").forEach(node => { node.hidden = node.id !== `view-${state.view}`; });
  Appearance.showView(state.view);
  document.querySelectorAll("nav a").forEach(node => {
    const active = node.dataset.view === state.view || (state.view === "dorm-bed" && node.dataset.view === "dorm");
    node.classList.toggle("active", active);
    if (active) node.setAttribute("aria-current", "page"); else node.removeAttribute("aria-current");
  });
  if (push) {
    history.pushState(null, "", `/?view=${state.view}${state.view === "dorm-bed" && state.dormRoom ? `&room=${state.dormRoom}` : ""}`);
    window.scrollTo({top:0, behavior:"instant"});
  }
  document.title = `${{arrival: "新生情景演练", chat: "新生问答", map: "校园探索行程", plan: "我的成长计划", tasks: "日程与任务", dorm: "宿舍选择", "dorm-bed": "床位选择", contest: "竞赛指南", club: "社团指南", union: "学生会", checklist: "报到清单", sources: "资料来源"}[state.view]} · 初到新生指南`;
  if (state.view === "arrival" && orientationReady) selectRehearsal(push ? rehearsalCase : new URLSearchParams(location.search).get("case"), false);
  if (state.view === "preparation") document.title = "出发准备台 · 初到新生指南";
  if (state.view === "map" && orientationReady) { if (!push) routeOnly = new URLSearchParams(location.search).get("route") === "1"; renderItinerary(); renderPlaces(); }
  if (state.view === "tasks" && plannerReady) { if (!push) readTaskFilters(); renderPlanner(); }
  if (state.view === "preparation" && preparationReady) loadPreparation(false).catch(error => { $("#prep-status").textContent = error.message; });
}
document.addEventListener("click", event => {
  const link = event.target.closest("a[href^='/?view=']");
  if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.button !== 0) return;
  event.preventDefault();
  changeView(new URL(link.href).searchParams.get("view"));
});
addEventListener("popstate", () => {
  const params = new URLSearchParams(location.search);
  const view = params.get("view");
  changeView(view, false);
  if (view === "dorm-bed" && state.dorm) {
    const roomType = ["siren", "liuren"].includes(params.get("room")) ? params.get("room") : "siren";
    state.dormRoom = roomType;
    renderDormBeds(roomType);
  }
});

function renderFaq() {
  $("#faq-tabs").replaceChildren();
  state.catalog.faqs.forEach((category, index) => {
    const tab = button(category.category, () => { state.faq = index; renderFaq(); }, "");
    tab.classList.toggle("active", state.faq === index);
    tab.setAttribute("aria-pressed", String(state.faq === index));
    $("#faq-tabs").append(tab);
  });
  $("#faq-questions").replaceChildren(...state.catalog.faqs[state.faq].questions.map(question => button(question, () => ask(question), "")));
}
function safeLink(raw) {
  try {
    const url = new URL(raw);
    if (!["http:", "https:"].includes(url.protocol)) return null;
    const link = element("a", "", "查看来源网页");
    link.href = url.href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    return link;
  } catch { return null; }
}
function citations(sources) {
  const group = element("div", "citations");
  sources.forEach((source, index) => {
    const details = element("details", "citation");
    const summary = element("summary", "", `【${index + 1}】${source.source} · ${source.section}`);
    details.append(summary, element("span", `badge ${source.verified ? "verified" : source.source_type === "third_party" ? "caution" : ""}`, LABELS[source.source_type]));
    details.append(element("p", "", source.caveat));
    if (source.effective_year) details.append(element("p", "", `适用参考年份：${source.effective_year}；采集日期：${source.collected_at}`));
    details.append(element("pre", "", source.text));
    for (const raw of source.urls || []) { const link = safeLink(raw); if (link) details.append(link); }
    group.append(details);
  });
  return group;
}
function messageNode(message) {
  const wrapper = element("article", `message ${message.role}`);
  wrapper.append(element("span", "avatar", message.role === "user" ? "你" : "初"));
  const content = element("div", "message-content");
  const name = element("div", "message-name", message.role === "user" ? "你" : "初到资料助手");
  if (message.role === "assistant") {
    name.append(element("span", "badge", message.mode === "remote_llm" ? "AI 资料回答" : "本地资料回答"));
    if (message.web_used) name.append(element("span", "badge caution", "含网络搜索参考"));
  }
  const body = element("div", "message-body", message.content);
  content.append(name, body);
  if (message.sources?.length) content.append(citations(message.sources));
  if (message.check_links?.length) {
    const checks = element("details", "verification-links"); checks.append(element("summary", "", "核对最新公开通知"), element("p", "", "点击后打开外部网站。搜索只使用固定主题词，不发送完整问题；网页内容和当前安排需自行核对。"));
    message.check_links.forEach(item => { const link = safeLink(item.url); if (link) { link.textContent = item.label; checks.append(link); } }); content.append(checks);
  }
  if (message.web_results?.length) {
    const web = element("details", "web-results"); web.append(element("summary", "", `网络搜索参考（${message.web_results.length} 条 · 注意时效，非学校官方核对）`), element("p", "", "以下为联网搜索结果标题与摘要，点击可在新窗口打开原文核对。"));
    message.web_results.forEach(item => {
      const card = element("div", "web-result");
      const link = safeLink(item.url); if (link) { link.textContent = item.title; link.classList.add("web-title"); }
      card.append(element("strong", "web-rank", `#${item.rank}`), item.snippet ? element("p", "", item.snippet) : null);
      const row = element("div", "web-meta"); if (link) row.append(link); card.append(row);
      web.append(card);
    });
    content.append(web);
  }
  if (message.role === "assistant" && message.id) {
    const actions = element("div", "message-actions");
    actions.append(button("复制回答", async () => {
      try { await navigator.clipboard.writeText(message.content); toast("回答已复制"); }
      catch { toast("复制未成功，请选中回答文字复制。"); }
    }, ""));
    for (const [label, value] of [["有帮助", "helpful"], ["需要改进", "unhelpful"]]) {
      const feedback = button(label, async () => {
        try {
          await mutate("/api/feedback", {answer: message.id, value});
          actions.querySelectorAll("button").forEach(node => node.classList.remove("selected"));
          feedback.classList.add("selected");
          toast("反馈已保存");
        } catch (error) { toast(error.message); }
      }, "");
      actions.append(feedback);
    }
    content.append(actions);
  }
  wrapper.append(content);
  return {wrapper, body, content};
}
function renderMessages() {
  const conversation = $("#conversation");
  const welcome = $("#chat-welcome");
  welcome.hidden = state.messages.length > 0;
  conversation.querySelectorAll(".message").forEach(node => node.remove());
  for (const message of state.messages) conversation.append(messageNode(message).wrapper);
  conversation.scrollTop = conversation.scrollHeight;
}
async function ask(question) {
  if (state.busy) return;
  question = question.trim();
  if (!question || question.length > 500) { toast("请输入1–500字的问题。"); return; }
  changeView("chat");
  state.busy = true;
  $("#send").disabled = true;
  $("#send").textContent = "查找资料…";
  $("#clear-chat").disabled = true;
  $("#question").value = "";
  $("#request-status").textContent = "正在查找相关资料…";
  $("#chat-welcome").hidden = true;
  $("#conversation").append(messageNode({role: "user", content: question}).wrapper);
  const current = messageNode({role: "assistant", content: "正在查找相关资料…"});
  $("#conversation").append(current.wrapper);
  let text = "", pending = "", completed = false;
  let metadata = {};
  try {
    const response = await fetch("/api/ask", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({session: state.session, question})});
    if (!response.ok) { const error = await response.json(); throw new Error(error.error || "提问失败，请重试。"); }
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    function processFrame(frame) {
      const type = frame.split("\n").find(line => line.startsWith("event: "))?.slice(7);
      const raw = frame.split("\n").filter(line => line.startsWith("data: ")).map(line => line.slice(6)).join("\n");
      if (!raw) return;
      const data = JSON.parse(raw);
      if (type === "status") $("#request-status").textContent = data.source_count ? `找到 ${data.source_count} 条资料，正在整理回答…` : "资料不足，正在提供查询指引…";
      if (type === "sources") metadata = data;
      if (type === "delta") { text += data.text; current.body.textContent = text; }
      if (type === "done") completed = true;
    }
    for (;;) {
      const {value, done} = await reader.read();
      pending += decoder.decode(value || new Uint8Array(), {stream: !done});
      let split;
      while ((split = pending.indexOf("\n\n")) >= 0) { processFrame(pending.slice(0, split)); pending = pending.slice(split + 2); }
      if (done) break;
    }
    if (!completed) throw new Error("回答连接中断，请刷新查看已保存的回答，或重试。");
    state.messages = (await api(`/api/history?session=${state.session}`)).messages;
    renderMessages();
    $("#request-status").textContent = metadata.mode === "remote_llm" ? "AI 回答已完成，可查看来源" : metadata.remote_attempted ? "已尝试外部模型，当前回答已回退到本地资料" : metadata.web_used ? "本地资料回答已完成，并补充了网络搜索参考" : "本地资料回答已完成，未调用外部模型";

  } catch (error) {
    current.body.textContent = text ? `${text}\n\n${error.message}` : error.message;
    $("#request-status").textContent = "请求未完成，可重试";
  } finally {
    state.busy = false;
    $("#send").disabled = false;
    $("#send").textContent = "发送问题 ↑";
    $("#clear-chat").disabled = false;
    $("#conversation").scrollTop = $("#conversation").scrollHeight;
  }
}
$("#question-form").addEventListener("submit", event => { event.preventDefault(); ask($("#question").value); });
$("#question").addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); $("#question-form").requestSubmit(); }
});

function updateProgress() {
  const total = state.catalog.tasks.length;
  const completed = state.catalog.tasks.filter(task => state.checked[task.id]).length;
  $("#checklist-count").textContent = `${completed} / ${total}`;
  $("#nav-count").textContent = `${completed}/${total}`;
  for (const id of ["#mini-progress", "#checklist-progress"]) $(id).style.width = `${completed / total * 100}%`;
  $("#mini-progress-label").textContent = `已完成 ${completed} 项，共 ${total} 项准备`;
  if (orientationReady) renderRehearsal();
}
function renderTasks() {
  $("#task-groups").replaceChildren();
  for (const stage of [...new Set(state.catalog.tasks.map(task => task.stage))]) {
    const group = element("section", "task-group");
    group.append(element("h2", "", stage));
    for (const task of state.catalog.tasks.filter(task => task.stage === stage)) {
      const row = element("div", "task-row");
      row.classList.toggle("checked", Boolean(state.checked[task.id]));
      const label = element("label");
      const check = element("input");
      check.type = "checkbox";
      check.name = task.id;
      check.checked = Boolean(state.checked[task.id]);
      const words = element("span");
      words.append(element("strong", "", task.title), element("p", "", task.detail));
      label.append(check, words);
      row.append(label, button("查看依据", () => ask(task.question), ""));
      check.addEventListener("change", async () => {
        check.disabled = true;
        try {
          state.checked = (await mutate("/api/checklist", {task: task.id, checked: check.checked})).checked;
          row.classList.toggle("checked", check.checked);
          updateProgress();
        } catch (error) { check.checked = Boolean(state.checked[task.id]); toast(error.message); }
        finally { check.disabled = false; }
      });
      group.append(row);
    }
    $("#task-groups").append(group);
  }
  updateProgress();
}
function selectPlace(place) {
  $("#place-detail").replaceChildren(element("h3", "", place.name), element("p", "", place.note), button("查看相关资料", () => ask(place.question), "primary"), element("small", "", "图上定位仅供参考，请以建筑标识及现场引导为准。"));
  if (orientationReady) {
    const exists = orientation.itinerary.stops.some(stop => stop.id === place.id);
    const add = button(exists ? "已在探索行程中" : "加入探索行程", () => addPlaceToItinerary(place.id), "secondary");
    add.disabled = exists || orientationBusy; $("#place-detail").append(add);
  }
  document.querySelectorAll("[data-place]").forEach(node => {
    const active = node.dataset.place === place.id;
    node.classList.toggle("active", active);
    node.setAttribute("aria-pressed", String(active));
  });
}
function renderPlaces() {
  const list = $("#place-list"); list.replaceChildren(); $("#map-pins").replaceChildren();
  let currentCategory = "";
  const places = state.catalog.places.filter(place => (!state.mapCategory || place.category === state.mapCategory) && (!state.mapQuery || `${place.name} ${place.note}`.includes(state.mapQuery)) && (!routeOnly || orientation?.itinerary.stops.some(stop => stop.id === place.id)));
  $("#map-results").textContent = `显示 ${places.length}/${state.catalog.places.length} 个地点`;
  state.catalog.places.forEach((place, index) => {
    if (!places.includes(place)) return;
    if (place.category !== currentCategory) {
      currentCategory = place.category; list.append(element("h3", "place-group-title", currentCategory));
    }
    const pin = button(String(index + 1), () => selectPlace(place), "map-pin");
    const stopIndex = orientationReady ? orientation.itinerary.stops.findIndex(stop => stop.id === place.id) : -1;
    if (stopIndex !== -1) { pin.textContent = `行${stopIndex + 1}`; pin.classList.add("route-stop-pin"); pin.classList.toggle("route-visited-pin", orientation.itinerary.stops[stopIndex].visited); }
    pin.style.left = `${place.x}%`; pin.style.top = `${place.y}%`;
    pin.dataset.place = place.id; pin.dataset.name = place.name;
    pin.setAttribute("aria-label", `查看${place.name}图上位置`); pin.title = place.name; $("#map-pins").append(pin);
    const listItem = button(`${index + 1}. ${place.name}`, () => selectPlace(place), ""); listItem.dataset.place = place.id; list.append(listItem);
  });
  if (places.length) selectPlace(places[0]);
  else { list.append(element("p", "empty-choices", "未找到地点，试试建筑名称或清除筛选。")); $("#place-detail").replaceChildren(); }
}
// ---- 宿舍选择模块 ----
function bedKey(roomType, bedId) { return `${roomType}:${bedId}`; }
function isIdealBed(roomType, bedId) {
  return state.saved.some(b => b.id === `bed-${roomType}-${bedId}`);
}
function toggleIdealBed(roomType, bed) {
  const item = state.explore.items.find(x => x.id === `bed-${roomType}-${bed.id}`);
  if (!item) return;
  return saveChoice(item, savedItem(item.id) ? "removed" : "planned");
}
function renderIdealBeds() {
  if (!state.explore) return;
  state.idealBeds = state.saved.filter(x => x.kind === "bed").map(x => ({roomType:x.room, bedId:x.bed_id, roomName:state.dorm.rooms[x.room].name, bedName:`${x.bed_id}号床`, tags:x.tags}));
  const box = $("#ideal-beds"); box.replaceChildren();
  box.append(element("p", "decision-category", "仅保存偏好，不代表预订。可在成长计划中对比。"));
  if (!state.idealBeds.length) box.append(element("p", "ideal-empty", "点击图上床位了解取舍，或按偏好查看推荐。"));
  state.idealBeds.forEach(b => {
    const item = state.explore.items.find(x => x.id === `bed-${b.roomType}-${b.bedId}`);
    const row = element("article", "ideal-item");
    const info = element("div", "ideal-info"); info.append(element("strong", "", item.name), choiceActions(item)); row.append(info); box.append(row);
  });
  const link = element("a", "inline-link", "按偏好匹配床位 / 查看我的计划"); link.href = "/?view=plan"; box.append(link);
}
function showBedDialog(roomType, bed) {
  if (!bed) return;
  $("#bed-dialog-title").textContent = `${state.dorm.rooms[roomType].name} · ${bed.name}`;
  const body = $("#bed-dialog-body");
  body.replaceChildren();
  const tags = element("div", "bed-tags");
  bed.tags.forEach(t => tags.append(element("span", "tag", t)));
  body.append(tags);
  const pros = element("div", "bed-pros");
  pros.append(element("h3", "", "优点"));
  const prosList = element("ul", "");
  bed.pros.forEach(p => prosList.append(element("li", "", p)));
  pros.append(prosList);
  const cons = element("div", "bed-cons");
  cons.append(element("h3", "", "注意点"));
  const consList = element("ul", "");
  bed.cons.forEach(c => consList.append(element("li", "", c)));
  cons.append(consList);
  body.append(pros, cons);
  if (bed.fit) body.append(element("p", "bed-fit", `适合人群：${bed.fit}`));
  const added = isIdealBed(roomType, bed.id);
  const act = button(added ? "从理想床位移除" : "加入我的理想床位", () => { toggleIdealBed(roomType, bed); $("#bed-dialog").close(); }, added ? "secondary" : "primary");
  const actions = element("div", "bed-dialog-actions");
  actions.append(act);
  body.append(actions);
  $("#bed-dialog").showModal();
}
function renderDormEnv() {
  const env = $("#dorm-env");
  env.replaceChildren();
  Object.entries(state.dorm.rooms).forEach(([type, room]) => {
    const card = element("figure", "dorm-env-card");
    const img = element("img");
    img.width = 1440; img.height = type === "siren" ? 1920 : 2559;
    img.src = room.env_img; img.alt = `${room.name}交接环境参考照片`;
    const figcap = element("figcaption", "");
    figcap.append(element("strong", "", room.name), element("p", "", room.env_desc));
    figcap.append(button("宿舍床位选择", () => openDormBeds(type), "primary"));
    card.append(img, figcap);
    env.append(card);
  });
  const gallery = $("#dorm-gallery");
  gallery.replaceChildren();
  state.dorm.gallery.forEach(item => {
    const card = element("figure", "dorm-gallery-item");
    const img = element("img");
    const sizes = {toilet:[1080,1440],washstand:[1440,1920],bathroom:[1080,810],laundry:[1080,608]};
    [img.width,img.height] = sizes[item.id];
    img.src = item.img; img.alt = item.title; img.loading = "lazy";
    const link = element("a"); link.href = item.img; link.target = "_blank"; link.rel = "noopener noreferrer"; link.setAttribute("aria-label", `放大${item.title}`); link.append(img);
    const figcap = element("figcaption", "");
    figcap.append(element("strong", "", item.title), element("p", "", item.desc));
    card.append(link, figcap);
    gallery.append(card);
  });
}
function openDormBeds(roomType) {
  state.dormRoom = roomType;
  renderDormBeds(roomType);
  changeView("dorm-bed");
}
function renderDormBeds(roomType) {
  const room = state.dorm.rooms[roomType];
  $("#dorm-bed-title").textContent = `${room.name} · 床位选择`;
  $("#dorm-bed-room-name").textContent = `${room.name} · ${room.layout}`;
  $("#dorm-bed-subtitle").textContent = "序号标在俯视图的床铺位上（下方书桌不标号），点击序号查看优缺点。";
  $("#dorm-bed-tip").textContent = room.tip;
  const img = $("#dorm-bed-image");
  [img.width,img.height] = roomType === "siren" ? [300,754] : [675,1366];
  img.src = room.select_img;
  img.alt = `${room.name}俯视图`;
  const pins = $("#dorm-bed-pins");
  pins.replaceChildren();
  room.beds.forEach(bed => {
    const pin = button(bed.id, () => showBedDialog(roomType, bed), "bed-pin");
    pin.style.left = `${bed.x}%`;
    pin.style.top = `${bed.y}%`;
    pin.dataset.bed = bed.id;
    pin.dataset.name = bed.name;
    pin.title = bed.name;
    pin.setAttribute("aria-label", `查看${bed.name}详情`);
    if (isIdealBed(roomType, bed.id)) pin.classList.add("ideal");
    pins.append(pin);
  });
  renderIdealBeds();
}
// ---- 宿舍选择模块结束 ----
// ---- 竞赛指南模块 ----
// 竞赛名称 → 官网 URL 映射；未收录的保持文字占位（官网待核实）
function renderContest() {
  const data = state.contest;
  const levels = $("#contest-levels");
  levels.replaceChildren();
  data.level_info.forEach(item => {
    const card = element("div", `contest-level level-${item.level.toLowerCase()}`);
    card.append(element("span", "level-badge", item.level), element("strong", "", item.name), element("p", "", item.desc));
    levels.append(card);
  });
  $("#contest-grad-note").textContent = data.grad_note;
  const usage = $("#contest-usage");
  usage.replaceChildren();
  Object.entries(data.usage_note).forEach(([key, desc]) => {
    const item = element("div", "usage-item");
    item.append(element("strong", "", key), element("p", "", desc));
    usage.append(item);
  });
  const cats = $("#contest-cats");
  cats.replaceChildren();
  ["", ...data.categories].forEach(cat => {
    const short = cat ? cat.split("（")[0] : "全部";
    const tab = button(short, () => { state.contestCat = cat; renderContestFilters(); renderContestList(); }, "");
    tab.dataset.cat = cat;
    tab.title = cat || "全部类别";
    cats.append(tab);
  });
  const levelFilter = $("#contest-level-filter");
  levelFilter.replaceChildren();
  ["", "A", "B", "C"].forEach(level => {
    const tab = button(level || "全部等级", () => { state.contestLevel = level; renderContestFilters(); renderContestList(); }, "");
    tab.dataset.level = level;
    levelFilter.append(tab);
  });
  renderContestFilters();
  renderContestList();
  const tips = $("#contest-tips");
  tips.replaceChildren();
  data.tips.forEach(tip => tips.append(element("li", "", tip)));
}
function renderContestFilters() {
  document.querySelectorAll("#contest-cats button").forEach(tab => tab.classList.toggle("active", tab.dataset.cat === state.contestCat));
  document.querySelectorAll("#contest-level-filter button").forEach(tab => tab.classList.toggle("active", tab.dataset.level === state.contestLevel));
}
function renderContestList() {
  if (!state.explore) return;
  const kw = state.contestKw.trim().toLowerCase();
  const entries = state.explore.items.filter(item => item.kind === "contest" && (!state.contestCat || item.categories.includes(state.contestCat)) && (!state.contestLevel || item.level === state.contestLevel) && (!kw || `${item.name} ${item.intro}`.toLowerCase().includes(kw)));
  renderDecisionList($("#contest-list"), entries);
  $("#contest-results").textContent = `共 ${entries.length} 项（已合并重复赛事）`;
}
// ---- 竞赛指南模块结束 ----
// ---- 社团指南模块 ----
function renderClub() {
  const data = state.club;
  const tipsList = $("#club-tips-list");
  tipsList.replaceChildren();
  data.tips.forEach(tip => tipsList.append(element("li", "", tip)));
  $("#club-note").textContent = data.note;
  const cats = $("#club-cats");
  cats.replaceChildren();
  ["", ...data.categories].forEach(cat => {
    const tab = button(cat || "全部", () => { state.clubCat = cat; renderClubFilters(); renderClubList(); }, "");
    tab.dataset.cat = cat;
    cats.append(tab);
  });
  renderClubFilters();
  renderClubList();
}
function renderClubFilters() {
  document.querySelectorAll("#club-cats button").forEach(tab => tab.classList.toggle("active", tab.dataset.cat === state.clubCat));
}
function renderClubList() {
  if (!state.explore) return;
  const kw = state.clubKw.trim().toLowerCase();
  const entries = state.explore.items.filter(item => item.kind === "club" && (!state.clubCat || item.category === state.clubCat) && (!kw || `${item.name} ${item.intro} ${item.audience} ${item.activities}`.toLowerCase().includes(kw)));
  renderDecisionList($("#club-list"), entries);
  $("#club-results").textContent = `共 ${entries.length} 个参考社团`;
}
// ---- 社团指南模块结束 ----
// ---- 学生会与学生组织模块 ----
function renderUnion() {
  const data = state.union;
  $("#union-intro").textContent = data.intro;
  const tipsList = $("#union-tips-list");
  tipsList.replaceChildren();
  data.tips.forEach(tip => tipsList.append(element("li", "", tip)));
  $("#union-note").textContent = data.note.join(" ");
  const cats = $("#union-cats");
  cats.replaceChildren();
  ["", ...data.categories].forEach(cat => {
    const tab = button(cat || "全部", () => { state.unionCat = cat; renderUnionFilters(); renderUnionList(); }, "");
    tab.dataset.cat = cat;
    cats.append(tab);
  });
  renderUnionFilters();
  renderUnionList();
}
function renderUnionFilters() {
  document.querySelectorAll("#union-cats button").forEach(tab => tab.classList.toggle("active", tab.dataset.cat === state.unionCat));
}
function renderUnionList() {
  if (!state.explore) return;
  const kw = state.unionKw.trim().toLowerCase();
  const entries = state.explore.items.filter(item => item.kind === "union" && (!state.unionCat || item.category === state.unionCat) && (!kw || `${item.name} ${item.intro} ${item.works} ${item.fit}`.toLowerCase().includes(kw)));
  renderDecisionList($("#union-list"), entries);
  $("#union-results").textContent = `共 ${entries.length} 个参考部门或组织`;
}
function setZoom(value) {
  state.zoom = Math.max(1, Math.min(2.5, value));
  $("#map-canvas").style.width = `${state.zoom * 100}%`;
  $("#zoom-label").textContent = `${Math.round(state.zoom * 100)}%`;
  $("#zoom-out").disabled = state.zoom <= 1;
  $("#zoom-in").disabled = state.zoom >= 2.5;
}
$("#zoom-in").addEventListener("click", () => setZoom(state.zoom + .25));
$("#zoom-out").addEventListener("click", () => setZoom(state.zoom - .25));
$("#zoom-reset").addEventListener("click", () => setZoom(1));
$("#map-full").addEventListener("click", () => $("#map-dialog").showModal());
$("#close-map").addEventListener("click", () => $("#map-dialog").close());
$("#campus-image").addEventListener("error", () => toast("地图加载失败，请确认项目目录内的学校地图.jpg存在。"));
$("#print-checklist").addEventListener("click", () => window.print());

function renderSources(filter = "") {
  const library = $("#source-library");
  library.replaceChildren();
  const documents = state.sources.filter(source => (source.name + source.chunks.map(c => c.text).join(" ")).includes(filter));
  if (!documents.length) { library.append(element("p", "", "没有找到相关资料，试试其他关键词。")); return; }
  for (const source of documents) {
    const doc = element("details", "source-document");
    const summary = element("summary", "", source.name);
    summary.append(element("span", `badge ${source.verified ? "verified" : source.source_type === "third_party" ? "caution" : ""}`, LABELS[source.source_type]));
    doc.append(summary, element("p", "", source.caveat));
    for (const raw of source.urls) { const link = safeLink(raw); if (link) doc.append(link); }
    for (const chunk of source.chunks) {
      const section = element("div", "source-chunk");
      section.append(element("h3", "", chunk.section), element("pre", "", chunk.text));
      doc.append(section);
    }
    library.append(doc);
  }
}
$("#source-filter").addEventListener("input", event => renderSources(event.target.value.trim()));
$("#clear-chat").addEventListener("click", () => $("#clear-dialog").showModal());
$("#cancel-clear").addEventListener("click", () => $("#clear-dialog").close());
$("#confirm-clear").addEventListener("click", async () => {
  const confirm = $("#confirm-clear");
  confirm.disabled = true;
  try { await mutate("/api/history", {}, "DELETE"); state.messages = []; renderMessages(); $("#clear-dialog").close(); toast("对话已清空，报到清单已保留。"); }
  catch (error) { toast(error.message); }
  finally { confirm.disabled = false; }
});
$("#export").addEventListener("click", async () => {
  try {
    const data = await api(`/api/export?session=${state.session}`);
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: "application/json"}));
    const link = element("a");
    link.href = url;
    link.download = "初到-我的完整记录.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("记录已导出");
  } catch (error) { toast(error.message); }
});
$("#theme-toggle").addEventListener("click", () => Appearance.open());
$("#dorm-back").addEventListener("click", () => changeView("dorm"));
$("#close-bed").addEventListener("click", () => $("#bed-dialog").close());
$("#bed-dialog").addEventListener("click", event => { if (event.target === $("#bed-dialog")) $("#bed-dialog").close(); });
$("#contest-back").addEventListener("click", () => changeView("chat"));
$("#contest-search").addEventListener("input", event => { state.contestKw = event.target.value; renderContestList(); });
$("#club-back").addEventListener("click", () => changeView("chat"));
$("#club-search").addEventListener("input", event => { state.clubKw = event.target.value; renderClubList(); });
$("#union-back").addEventListener("click", () => changeView("chat"));
$("#union-search").addEventListener("input", event => { state.unionKw = event.target.value; renderUnionList(); });

async function boot() {
  const params = new URLSearchParams(location.search);
  changeView(params.get("view"), false);
  try {
    const [stats, catalog, historyData, checklist, sources, dorm, contest, club, union, explore, saved, profile] = await Promise.all([
      api("/api/stats"), api("/api/catalog"), api(`/api/history?session=${state.session}`), api(`/api/checklist?session=${state.session}`), api("/api/sources"), api("/api/dorm"), api("/api/contest"), api("/api/club"), api("/api/studentorg"), api("/api/explore"), api(`/api/saved?session=${state.session}`), api(`/api/profile?session=${state.session}`)
    ]);
    state.catalog = catalog;
    state.messages = historyData.messages;
    state.checked = checklist.checked;
    state.sources = sources.documents;
    state.dorm = dorm;
    state.contest = contest;
    state.club = club;
    state.union = union;
    state.explore = explore; state.saved = saved.items; state.profile = profile.profile;
    if (state.profile) state.recommendations = await mutate("/api/recommend", {profile: state.profile});
    initializeDecision();
    await initializePlanner();
    await initializeOrientation();
    await initializePreparation();
    const mapCategory = $("#map-category");
    ["", ...new Set(catalog.places.map(p => p.category))].forEach(value => { const option = element("option", "", value || "所有区域"); option.value = value; mapCategory.append(option); });
    mapCategory.addEventListener("change", event => { state.mapCategory = event.target.value; renderPlaces(); });
    $("#map-search").addEventListener("input", event => { state.mapQuery = event.target.value.trim(); renderPlaces(); });
    $("#knowledge-meta").textContent = `${stats.remote_enabled ? "AI 资料" : "本地资料"}${stats.web_enabled ? "＋联网搜索" : ""} · ${stats.document_count} 份 · ${stats.chunk_count} 条`;
    $("#mode-label").textContent = stats.remote_enabled ? "AI 资料模式" : stats.web_enabled ? "本地资料＋联网" : "本地资料模式";
    $("#mode-detail").textContent = stats.remote_enabled ? "已显式启用外部模型，可能产生费用。" : stats.web_enabled ? "本地检索为主；本地不足或涉时效问题时补充网络搜索。" : "无需 API 额度，所有资料在本机检索。";
    renderFaq(); renderMessages(); renderTasks(); renderPlaces(); renderDormEnv(); renderContest(); renderClub(); renderUnion(); renderSources(); setZoom(1);
    if (state.view === "dorm-bed") {
      const roomType = ["siren", "liuren"].includes(params.get("room")) ? params.get("room") : "siren";
      state.dormRoom = roomType; renderDormBeds(roomType);
    }
    for (const step of catalog.route) {
      const item = element("li");
      item.append(element("strong", "", step.title), element("p", "", step.detail), button("问清楚这一步", () => ask(step.question), ""));
      $("#arrival-route").append(item);
    }
    Appearance.refreshControls();
  } catch {
    $("#global-error").textContent = "未能连接本地服务。请确认 python run.py 正在运行，然后刷新页面。";
    $("#global-error").hidden = false;
    $("#mode-label").textContent = "服务暂未连接";
    $("#knowledge-meta").textContent = "资料暂不可用";
    $("#send").disabled = true;
  }
}
boot();
