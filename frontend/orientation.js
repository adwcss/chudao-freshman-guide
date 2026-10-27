"use strict";
let orientation = null, orientationReady = false, rehearsalCase = "", orientationBusy = false, routeOnly = false;

function rehearsalSummary() {
  const cases = orientation.cases;
  const answered = cases.filter(item => Object.hasOwn(orientation.answers, item.id));
  const review = answered.filter(item => orientation.answers[item.id] !== item.recommended);
  return {answered, review, next: review[0] || cases.find(item => !Object.hasOwn(orientation.answers, item.id)) || cases[0]};
}
function selectRehearsal(identifier, push = true) {
  rehearsalCase = orientation.cases.some(item => item.id === identifier) ? identifier : rehearsalSummary().next.id;
  if (push) history.pushState(null, "", `/?view=arrival&case=${rehearsalCase}`);
  else if (state.view === "arrival") history.replaceState(null, "", `/?view=arrival&case=${rehearsalCase}`);
  renderRehearsal();
  if (push) $("#scenario-title").focus();
}
function renderRehearsal() {
  if (!orientationReady) return;
  const summary = rehearsalSummary();
  const current = orientation.cases.find(item => item.id === rehearsalCase) || summary.next;
  rehearsalCase = current.id;
  $("#rehearsal-progress").textContent = `已练习 ${summary.answered.length}/${orientation.cases.length} 个场景${summary.review.length ? `，${summary.review.length} 个建议再练` : ""}。这只记录练习进度，不代表完成报到。`;
  $("#rehearsal-stages").replaceChildren();
  for (const stage of [...new Set(orientation.cases.map(item => item.stage))]) {
    const cases = orientation.cases.filter(item => item.stage === stage);
    const count = cases.filter(item => Object.hasOwn(orientation.answers, item.id)).length;
    const tab = button(`${stage} ${count}/${cases.length}`, () => selectRehearsal((cases.find(item => !Object.hasOwn(orientation.answers, item.id)) || cases[0]).id), "");
    tab.classList.toggle("active", current.stage === stage); tab.setAttribute("aria-pressed", String(current.stage === stage));
    $("#rehearsal-stages").append(tab);
  }
  $("#rehearsal-list").replaceChildren();
  for (const item of orientation.cases.filter(item => item.stage === current.stage)) {
    const answered = Object.hasOwn(orientation.answers, item.id);
    const status = !answered ? "未练习" : orientation.answers[item.id] === item.recommended ? "已了解" : "建议再练";
    const entry = button("", () => selectRehearsal(item.id), "scenario-entry");
    entry.append(element("strong", "", item.title), element("span", "", status));
    entry.classList.toggle("active", current.id === item.id); entry.setAttribute("aria-pressed", String(current.id === item.id));
    $("#rehearsal-list").append(entry);
  }
  $("#scenario-title").textContent = current.title;
  $("#scenario-scene").textContent = current.scene;
  const selected = orientation.answers[current.id];
  $("#scenario-options").replaceChildren();
  current.options.forEach((text, index) => {
    const label = element("label", "scenario-option");
    const input = element("input"); input.type = "radio"; input.name = "scenario-choice"; input.value = String(index); input.required = true; input.checked = selected === index;
    label.append(input, element("span", "", text)); $("#scenario-options").append(label);
  });
  $("#scenario-submit").textContent = selected === undefined ? "确认选择，看解释" : "保存这次选择";
  $("#scenario-status").textContent = "";
  const feedback = $("#scenario-feedback"); feedback.hidden = selected === undefined;
  feedback.replaceChildren();
  if (selected !== undefined) {
    feedback.append(element("h3", "", selected === current.recommended ? "这个处理方式更稳妥" : "再想一步，会更稳妥"), element("p", "", current.explanations[selected]));
    if (selected !== current.recommended) feedback.append(element("p", "recommended-choice", `建议：${current.options[current.recommended]}。`));
    const actions = element("div", "scenario-followup");
    if (current.checklist) {
      const checked = Boolean(state.checked[current.checklist]);
      const link = element("a", "secondary", checked ? "查看已勾选的准备项" : "去清单检查准备项"); link.href = "/?view=checklist"; actions.append(link);
    }
    actions.append(button("继续问这个问题", () => ask(current.question), "text-button")); feedback.append(actions);
  }
  $("#scenario-references").replaceChildren();
  for (const filename of current.sources) {
    const source = state.sources.find(item => item.name === filename);
    if (!source) continue;
    const details = element("details", "scenario-reference");
    const heading = element("summary", "", filename.replace(/\.md$/, ""));
    details.append(heading, element("span", "badge", LABELS[source.source_type]), element("p", "", source.caveat));
    for (const chunk of source.chunks) details.append(element("h3", "", chunk.section), element("pre", "", chunk.text));
    $("#scenario-references").append(details);
  }
  const index = orientation.cases.indexOf(current);
  $("#scenario-next").disabled = index === orientation.cases.length - 1;
  $("#scenario-next").onclick = () => selectRehearsal(orientation.cases[index + 1].id);
  $("#scenario-review").disabled = !summary.review.length;
  $("#scenario-review").onclick = () => selectRehearsal(summary.review[0].id);
  const count = state.catalog.tasks.filter(item => state.checked[item.id]).length;
  $("#arrival-readiness").textContent = `${count}/${state.catalog.tasks.length} 项准备已勾选`;
  $("#arrival-route-status").textContent = orientation.itinerary.stops.length ? `行程已安排 ${orientation.itinerary.stops.length} 个地点，${orientation.itinerary.stops.filter(item => item.visited).length} 个已到访。` : "先选一条参考行程，再按自己的需要调整。";
}

async function routeOperation(operation) {
  if (orientationBusy) return;
  const previousFocus = document.activeElement;
  const focusLabel = previousFocus?.getAttribute("aria-label");
  const focusName = previousFocus?.name;
  const rowIndex = [...$("#itinerary-list").children].indexOf(previousFocus?.closest(".itinerary-stop"));
  const rowPlace = orientation.itinerary.stops[rowIndex]?.id;
  orientationBusy = true; $("#itinerary-status").textContent = "正在保存行程…";
  $("#itinerary-panel").setAttribute("aria-busy", "true");
  $("#itinerary-panel").querySelectorAll("button, input, select").forEach(node => { node.disabled = true; });
  try {
    orientation.itinerary = (await mutate("/api/orientation/route", {operation: {...operation, revision: orientation.itinerary.revision}})).itinerary;
    $("#itinerary-status").textContent = "行程已保存到本机当前会话。";
  } catch (error) {
    $("#itinerary-status").textContent = error.message;
    try { orientation.itinerary = (await api(`/api/orientation?session=${state.session}`)).itinerary; } catch { /* Keep current display; saving will be retried explicitly. */ }
  } finally {
    orientationBusy = false; $("#itinerary-panel").setAttribute("aria-busy", "false");
    $("#itinerary-panel").querySelectorAll("button, input, select").forEach(node => { node.disabled = false; });
    renderItinerary(); renderPlaces(); renderRehearsal();
    const controls = [...$("#itinerary-panel").querySelectorAll("button, input, select")];
    let focusTarget = previousFocus?.isConnected && !previousFocus.disabled ? previousFocus : controls.find(node => !node.disabled && (focusLabel ? node.getAttribute("aria-label") === focusLabel : focusName && node.name === focusName));
    if (!focusTarget && rowPlace) focusTarget = controls.find(node => node.name === `visited-${rowPlace}`);
    if (!focusTarget && rowIndex !== -1) focusTarget = $("#itinerary-list").querySelectorAll("input[type=checkbox]")[Math.min(rowIndex, orientation.itinerary.stops.length - 1)];
    if (!focusTarget) focusTarget = $("#itinerary-place");
    if (state.view === "map") focusTarget.focus({preventScroll: true});
  }
}
function addPlaceToItinerary(identifier) {
  if (!orientationReady) return;
  routeOperation({action: "add", place: identifier});
}
function renderItinerary() {
  if (!orientationReady) return;
  const route = orientation.itinerary;
  $("#itinerary-count").textContent = `${route.stops.length}/${orientation.route_limit} 个地点，${route.stops.filter(item => item.visited).length} 个已到访`;
  $("#itinerary-list").replaceChildren();
  if (!route.stops.length) $("#itinerary-list").append(element("p", "empty-choices", "选一条参考行程，或在地图上点选地点加入。"));
  route.stops.forEach((stop, index) => {
    const place = state.catalog.places.find(item => item.id === stop.id);
    const row = element("li", "itinerary-stop"); row.classList.toggle("visited", stop.visited);
    const label = element("label"); const check = element("input"); check.type = "checkbox"; check.checked = stop.visited; check.name = `visited-${stop.id}`;
    check.addEventListener("change", () => routeOperation({action: "visit", place: stop.id, visited: check.checked}));
    label.append(check, element("span", "", `${index + 1}. ${place.name}`));
    const controls = element("div", "itinerary-actions");
    const locate = button("定位", () => { routeOnly = true; state.mapCategory = ""; state.mapQuery = ""; $("#map-search").value = ""; $("#map-category").value = ""; renderItinerary(); renderPlaces(); selectPlace(place); }, "text-button"); locate.setAttribute("aria-label", `定位${place.name}`);
    const up = button("上移", () => routeOperation({action: "move", place: stop.id, delta: -1}), "text-button"); up.disabled = index === 0; up.setAttribute("aria-label", `上移${place.name}`);
    const down = button("下移", () => routeOperation({action: "move", place: stop.id, delta: 1}), "text-button"); down.disabled = index === route.stops.length - 1; down.setAttribute("aria-label", `下移${place.name}`);
    const remove = button("移除", () => routeOperation({action: "remove", place: stop.id}), "text-button"); remove.setAttribute("aria-label", `移除${place.name}`);
    controls.append(locate, up, down, remove); row.append(label, controls); $("#itinerary-list").append(row);
  });
  $("#route-only").textContent = routeOnly ? "显示全部地点" : "仅显示行程地点";
  $("#route-only").setAttribute("aria-pressed", String(routeOnly));
  $("#view-map").classList.toggle("route-view", routeOnly);
  if (state.view === "map") {
    const url = new URL(location.href); if (routeOnly) url.searchParams.set("route", "1"); else url.searchParams.delete("route");
    history.replaceState(null, "", url.pathname + url.search);
  }
  $("#export-itinerary").disabled = !route.stops.length; $("#clear-itinerary").disabled = !route.stops.length;
  const svg = $("#map-route-lines"); svg.replaceChildren();
  const points = route.stops.map(stop => state.catalog.places.find(item => item.id === stop.id));
  if (points.length > 1) {
    const line = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    line.setAttribute("points", points.map(place => `${place.x},${place.y}`).join(" "));
    svg.append(line);
  }
}
async function initializeOrientation() {
  orientation = await api(`/api/orientation?session=${state.session}`);
  orientationReady = true;
  routeOnly = new URLSearchParams(location.search).get("route") === "1";
  $("#view-map .map-detail").prepend($("#itinerary-panel"));
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg"); svg.id = "map-route-lines"; svg.setAttribute("viewBox", "0 0 100 100"); svg.setAttribute("preserveAspectRatio", "none"); svg.setAttribute("aria-hidden", "true"); $("#map-canvas").prepend(svg);
  const routeSelect = $("#itinerary-place");
  for (const place of state.catalog.places) { const option = element("option", "", `${place.category} · ${place.name}`); option.value = place.id; routeSelect.append(option); }
  $("#itinerary-presets").replaceChildren(...orientation.presets.map(preset => {
    const node = button(preset.name, () => {
      if (orientation.itinerary.stops.length && !confirm("改用这条参考行程？共同地点的到访状态会保留，其他地点将移出当前行程。")) return;
      routeOperation({action: "preset", preset: preset.id});
    }, "secondary"); node.title = preset.detail; return node;
  }));
  $("#itinerary-add").addEventListener("submit", event => { event.preventDefault(); addPlaceToItinerary(routeSelect.value); });
  $("#route-only").addEventListener("click", () => { routeOnly = !routeOnly; renderItinerary(); renderPlaces(); });
  $("#clear-itinerary").addEventListener("click", () => { if (confirm("清空当前探索行程和到访勾选？演练与报到准备清单会保留。")) routeOperation({action: "clear"}); });
  $("#export-itinerary").addEventListener("click", async () => {
    try {
      const response = await fetch(`/api/orientation/route.txt?session=${state.session}`);
      if (!response.ok) throw new Error("行程导出未成功，请重试。");
      downloadPlan(await response.text(), "text/plain;charset=utf-8", "初到-校园探索行程.txt"); toast("探索行程已导出");
    } catch (error) { $("#itinerary-status").textContent = error.message; }
  });
  $("#scenario-form").addEventListener("submit", async event => {
    event.preventDefault(); if (orientationBusy) return;
    const selected = new FormData(event.currentTarget).get("scenario-choice"); if (selected === null) return;
    orientationBusy = true; $("#scenario-submit").disabled = true; $("#scenario-status").textContent = "正在保存这次选择…";
    try {
      orientation.answers = (await mutate("/api/orientation/answer", {scenario: rehearsalCase, choice: Number(selected)})).answers;
      renderRehearsal(); $("#scenario-feedback").focus();
    } catch (error) { $("#scenario-status").textContent = error.message; }
    finally { orientationBusy = false; $("#scenario-submit").disabled = false; }
  });
  selectRehearsal(new URLSearchParams(location.search).get("case"), false);
  renderItinerary();
}
