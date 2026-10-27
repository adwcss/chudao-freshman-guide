"use strict";
let preparation = null, preparationReady = false, preparationBusy = false, preparationDraft = false, preparationFilter = "all", preparationImport = null;
const packingDrafts = new Map();
const PREP_FIELDS = {departure:"prep-departure",arrival:"prep-arrival",time:"prep-time",mode:"prep-mode",dorm:"prep-dorm",room_note:"prep-room-note",notes:"prep-notes"};
function prepDirty() { return preparationDraft || packingDrafts.size > 0 || Boolean($("#packing-custom-title")?.value.trim()); }
function prepReadForm() { return Object.fromEntries(Object.entries(PREP_FIELDS).map(([key,id]) => [key,$(`#${id}`).value])); }
function prepFillForm() { for (const [key,id] of Object.entries(PREP_FIELDS)) $(`#${id}`).value = preparation.state.plan[key]; }
async function loadPreparation(fill=false) {
  const result = await api(`/api/preparation?session=${state.session}`);
  if (!preparation || result.state.revision >= preparation.state.revision) preparation = result;
  if (fill) { preparationDraft=false; packingDrafts.clear(); prepFillForm(); }
  if(state.view==="preparation") { const value=new URLSearchParams(location.search).get("packing");preparationFilter=Object.hasOwn(preparation.statuses,value)?value:"all"; }
  renderPreparation();
}
async function preparationOperation(operation) {
  if (preparationBusy) return false;
  const focus=document.activeElement, key=focus?.name || focus?.dataset.prepFocus, rowIndex=[...$("#packing-list").querySelectorAll("article")].indexOf(focus?.closest("article"));
  preparationBusy=true; $("#view-preparation").setAttribute("aria-busy","true");
  $("#view-preparation").querySelectorAll("button,input,select,textarea").forEach(node=>{node.disabled=true;});
  $("#prep-status").textContent="正在保存…"; let success=false;
  try {
    preparation=await mutate("/api/preparation",{operation:{...operation,revision:preparation.state.revision}});
    if (["plan","restore"].includes(operation.action)) { preparationDraft=false; prepFillForm(); }
    if (["item","remove"].includes(operation.action)) packingDrafts.delete(operation.id);
    if (operation.action==="restore") packingDrafts.clear();
    $("#prep-status").textContent="已保存到本机。"; success=true;
  } catch(error) {
    $("#prep-status").textContent=error.message+" 未保存的填写内容已保留，可以检查后重试。";
    try { await loadPreparation(false); } catch { /* Preserve drafts when the service is unavailable. */ }
  } finally {
    preparationBusy=false; $("#view-preparation").setAttribute("aria-busy","false");
    $("#view-preparation").querySelectorAll("button,input,select,textarea").forEach(node=>{node.disabled=false;}); renderPreparation();
    const controls=[...$("#view-preparation").querySelectorAll("button,input,select")];
    const target=focus?.isConnected&&!focus.disabled?focus:controls.find(node=>!node.disabled&&key&&(node.name===key||node.dataset.prepFocus===key))||$("#packing-list").querySelectorAll("input[type=number]")[Math.max(0,Math.min(rowIndex,$("#packing-list").querySelectorAll("article").length-1))]||$("#packing-custom-title");
    if(state.view==="preparation") { if(success) target.focus({preventScroll:true}); else { $("#prep-status").tabIndex=-1; $("#prep-status").focus(); $("#prep-status").scrollIntoView({block:"center"}); } }
  }
  return success;
}
function prepTask(title,notes,priority="normal",due=title.startsWith("到校购买：")?preparation.state.plan.arrival:preparation.state.plan.departure) {
  const existing=personalTasks.find(task=>task.title===title); editPersonalTask(existing||null);
  if(!existing) { $("#personal-task-title").value=title; $("#personal-task-due").value=due; $("#personal-task-notes").value=notes; $("#personal-task-priority").value=priority; taskDraftChanged=true; }
}
function renderPreparation() {
  if(!preparationReady) return;
  const audit=preparation.readiness, days=audit.days_until_departure;
  $("#departure-countdown").textContent=days===null?"还未填写出发日期。":days>0?`距自己计划的出发日还有 ${days} 天`:days===0?"今天是自己计划的出发日":`自己计划的出发日已过 ${-days} 天，请核对是否需要调整。`;
  $("#prep-draft-status").textContent=preparationDraft?"出行安排有未保存的修改":"";
  $("#prep-dorm-map").disabled=!preparation.state.plan.dorm||preparationBusy;
  $("#packing-count").textContent=`已装好 ${audit.packed}/${audit.total} 种`;
  const filters=$("#packing-filters"); filters.replaceChildren();
  for(const [value,title] of [["all","全部"],...Object.entries(preparation.statuses)]) {
    const control=button(title,()=>{preparationFilter=value;renderPreparation();filters.querySelector(`[data-filter="${value}"]`)?.focus({preventScroll:true});},"");
    control.dataset.filter=value;control.classList.toggle("active",value===preparationFilter);control.setAttribute("aria-pressed",String(value===preparationFilter));filters.append(control);
  }
  if(state.view==="preparation") { const url=new URL(location.href);if(preparationFilter!=="all")url.searchParams.set("packing",preparationFilter);else url.searchParams.delete("packing");history.replaceState(null,"",url.pathname+url.search); }
  const list=$("#packing-list");list.replaceChildren();let group="",count=0;
  for(const item of preparation.items.filter(item=>preparationFilter==="all"||item.status===preparationFilter)) {
    count++;if(group!==item.group){group=item.group;list.append(element("h3","packing-group",group));}
    const row=element("article","packing-row");row.dataset.packingId=item.id;
    const info=element("div","packing-info");info.append(element("h4","",item.title),element("p","",item.note));if(item.essential)info.append(element("span","badge caution","重要证件，随身确认"));
    const form=element("form","packing-item-form"),draft=packingDrafts.get(item.id)||item;
    const qtyLabel=element("label","","数量"),qty=element("input");qty.type="number";qty.min="1";qty.max="99";qty.step="1";qty.required=true;qty.value=draft.quantity;qty.name=`quantity-${item.id}`;qtyLabel.append(qty);
    const statusLabel=element("label","","准备状态"),status=element("select");status.name=`status-${item.id}`;
    for(const [value,title]of Object.entries(preparation.statuses)){if(item.essential&&!["todo","packed"].includes(value))continue;const option=element("option","",title);option.value=value;status.append(option);}status.value=draft.status;statusLabel.append(status);
    const save=element("button","secondary",packingDrafts.has(item.id)?"保存修改":"保存这一项");save.type="submit";save.dataset.prepFocus=`save-${item.id}`;save.setAttribute("aria-label",`保存${item.title}`);
    const mark=()=>{packingDrafts.set(item.id,{quantity:qty.value,status:status.value});save.textContent="保存修改";};form.addEventListener("input",mark);form.addEventListener("change",mark);
    form.addEventListener("submit",async event=>{event.preventDefault();await preparationOperation({action:"item",id:item.id,item:{quantity:Number(qty.value),status:status.value}});});form.append(qtyLabel,statusLabel,save);
    const actions=element("div","packing-row-actions");
    if(["todo","buy"].includes(item.status)){const todo=button(item.status==="buy"?"安排到校购买":"安排准备任务",()=>prepTask(`${item.status==="buy"?"到校购买":"准备"}：${item.title}`,item.note,item.essential?"high":"normal"),"text-button");todo.setAttribute("aria-label",`${item.title}：${todo.textContent}`);actions.append(todo);}
    if(item.custom){const remove=button("移除",async()=>{if(confirm(`移除“${item.title}”？这项物品的记录也会移除。`))await preparationOperation({action:"remove",id:item.id});},"text-button");remove.dataset.prepFocus=`remove-${item.id}`;remove.setAttribute("aria-label",`移除${item.title}`);actions.append(remove);}
    row.append(info,form,actions);list.append(row);
  }
  if(!count)list.append(element("p","planner-empty","这个状态下暂时没有物品，可切换到“全部”。"));
  $("#packing-custom-count").textContent=`已补充 ${preparation.state.custom.length}/${preparation.custom_limit} 种物品`;
  const root=$("#preparation-audit");root.replaceChildren();
  const important=element("section");important.append(element("h3","","重要证件"),element("p","",audit.important_missing.length?`还未标记装好：${audit.important_missing.map(item=>item.title).join("、")}`:"两项重要证件已标记装好，临走前仍请亲自检查。"));root.append(important);
  const checks=element("section");checks.append(element("h3","",`准备清单仍有 ${audit.pending_checks.length} 项待确认`));for(const item of audit.pending_checks.slice(0,3))checks.append(button(item.title+"：安排任务",()=>prepTask(`核对：${item.title}`,item.detail,"high"),"text-button"));
  const link=element("a","inline-link","查看完整报到清单");link.href="/?view=checklist";checks.append(link);root.append(checks);
  const review=element("section");review.append(element("h3","",`已练场景有 ${audit.review_cases.length} 项待复习`),element("p","","未练习的场景不计为已了解。"));const learn=element("a","inline-link","回到情景演练");learn.href="/?view=arrival";review.append(learn);root.append(review);
}
async function prepMemo(){const response=await fetch(`/api/preparation/memo.txt?session=${state.session}`);if(!response.ok)throw new Error("备忘卡导出未完成，请重试。");return response.text();}
async function initializePreparation(){
  preparation=await api(`/api/preparation?session=${state.session}`);preparationReady=true;
  for(const [value,title]of Object.entries(preparation.modes)){const option=element("option","",title);option.value=value;$("#prep-mode").append(option);}
  const none=element("option","","待学校分配后填写");none.value="";$("#prep-dorm").append(none);for(const dorm of preparation.dorms){const option=element("option","",dorm.name);option.value=dorm.id;$("#prep-dorm").append(option);}
  preparationFilter=new URLSearchParams(location.search).get("packing")||"all";if(!Object.hasOwn(preparation.statuses,preparationFilter))preparationFilter="all";prepFillForm();renderPreparation();
  $("#departure-form").addEventListener("input",()=>{preparationDraft=true;$("#prep-draft-status").textContent="出行安排有未保存的修改";});
  $("#departure-form").addEventListener("submit",async event=>{event.preventDefault();await preparationOperation({action:"plan",plan:prepReadForm()});});
  $("#packing-add").addEventListener("submit",async event=>{event.preventDefault();if(await preparationOperation({action:"add",title:$("#packing-custom-title").value,quantity:Number($("#packing-custom-quantity").value)})){$("#packing-custom-title").value="";$("#packing-custom-quantity").value="1";}});
  $("#prep-reload").addEventListener("click",async()=>{if(prepDirty()&&!confirm("重新读取会放弃准备台未保存的修改，继续？"))return;try{await loadPreparation(true);$("#prep-status").textContent="已读取最新保存记录。";}catch(error){$("#prep-status").textContent=error.message;}});
  addEventListener("beforeunload",event=>{if(prepDirty()){event.preventDefault();event.returnValue="";}});
  $("#prep-dorm-map").addEventListener("click",()=>{const place=state.catalog.places.find(item=>item.id===preparation.state.plan.dorm);if(!place)return;routeOnly=false;state.mapCategory="";state.mapQuery="";$("#map-search").value="";$("#map-category").value="";changeView("map");renderPlaces();selectPlace(place);});
  $("#packing-source").addEventListener("click",()=>{changeView("sources");$("#source-filter").value="入学准备清单";renderSources("入学准备清单");});
  $("#prep-export-memo").addEventListener("click",async()=>{try{downloadPlan(await prepMemo(),"text/plain;charset=utf-8","初到-出发备忘卡.txt");toast("出发备忘卡已导出");}catch(error){$("#prep-status").textContent=error.message;}});
  $("#prep-print-memo").addEventListener("click",async()=>{try{$("#prep-memo-preview").textContent=await prepMemo();$("#prep-memo-dialog").showModal();}catch(error){$("#prep-status").textContent=error.message;}});
  $("#prep-memo-close").addEventListener("click",()=>$("#prep-memo-dialog").close());$("#prep-memo-print").addEventListener("click",()=>{document.body.classList.add("print-preparation");window.print();});
  addEventListener("afterprint",()=>document.body.classList.remove("print-preparation"));$("#prep-memo-dialog").addEventListener("close",()=>document.body.classList.remove("print-preparation"));
  $("#prep-export-backup").addEventListener("click",async()=>{try{downloadPlan(JSON.stringify(await api(`/api/preparation/backup?session=${state.session}`),null,2),"application/json","初到-准备台备份.json");toast("准备台备份已导出");}catch(error){$("#prep-status").textContent=error.message;}});
  $("#prep-backup-file").addEventListener("change",async event=>{
    const file=event.target.files[0];if(!file)return;
    try{if(file.size>16384)throw new Error("备份超过16KiB，请选择准备台导出的文件。");const candidate=JSON.parse(await file.text());const preview=await mutate("/api/preparation/preview",{backup:candidate});preparationImport={backup:candidate,revision:preparation.state.revision};$("#prep-restore-summary").textContent=`出发：${preview.plan.departure||"未填写"}；预计到校：${preview.plan.arrival||"未填写"}；共 ${preview.items.length} 种物品。`;$("#prep-restore-items").replaceChildren(...preview.items.map(item=>element("li","",`${item.title} × ${item.quantity} · ${preparation.statuses[item.status]}`)));$("#prep-restore-error").textContent="";$("#prep-restore-dialog").showModal();}
    catch(error){$("#prep-status").textContent=error instanceof SyntaxError?"备份JSON格式无效，请重新选择导出的文件。":error.message;}finally{event.target.value="";}
  });
  $("#prep-restore-cancel").addEventListener("click",()=>{preparationImport=null;$("#prep-restore-dialog").close();});
  $("#prep-restore-confirm").addEventListener("click",async()=>{if(!preparationImport||preparationBusy)return;const control=$("#prep-restore-confirm");control.disabled=true;
    try{preparation=await mutate("/api/preparation",{operation:{action:"restore",backup:preparationImport.backup,revision:preparationImport.revision}});preparationDraft=false;packingDrafts.clear();prepFillForm();renderPreparation();preparationImport=null;$("#prep-restore-dialog").close();toast("准备台记录已恢复，其他模块已保留。");}
    catch(error){$("#prep-restore-error").textContent=error.message+" 请取消预览、重新读取后再恢复。";}finally{control.disabled=false;}
  });
}
