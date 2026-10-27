"use strict";
const Appearance = (() => {
  const KEY = "freshman-appearance-v1", SEEN = "freshman-intro-campus-v2";
  const DEFAULTS = {mode:"light",source:"preset",shade:55,blur:4,position:"center"};
  const PAGE_ART = Object.freeze({
    arrival:"mascot-wave", preparation:"chibi-ready", chat:"chibi-think",
    map:"mascot-point", plan:"mascot-reading", tasks:"chibi-read",
    dorm:"creative-rest", "dorm-bed":"creative-rest", contest:"creative-laugh",
    club:"chibi-cheer", union:"chibi-wave", checklist:"chibi-guide", sources:"creative-side"
  });
  const ART_SIZES = {"mascot-wave":[1024,1536],"creative-rest":[1154,1363]};
  const query = selector => document.querySelector(selector);
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  let settings, imageUrl="", imageName="", imageBusy=false, introTimer, introColorTimer, introRevision=0, imageRevision=0;
  let mascotReady, mascotAssetRevision=0, introReturnFocus;
  function normalize(value={}) {
    if (!value || typeof value!=="object" || Array.isArray(value)) value={};
    const number=(key,min,max)=>typeof value[key]==="number"&&Number.isFinite(value[key])?Math.round(Math.max(min,Math.min(max,value[key]))):DEFAULTS[key];
    return {mode:["light","dark","custom"].includes(value.mode)?value.mode:"light",source:value.source==="image"?"image":"preset",shade:number("shade",35,85),blur:number("blur",0,12),position:["top","center","bottom"].includes(value.position)?value.position:"center"};
  }
  function message(text) { query("#appearance-status").textContent=text; }
  function read() {
    try { const raw=localStorage.getItem(KEY); return normalize(raw?JSON.parse(raw):{mode:localStorage.getItem("freshman-theme")}); }
    catch { return {...DEFAULTS}; }
  }
  function persist() {
    try { localStorage.setItem(KEY,JSON.stringify(settings)); localStorage.setItem("freshman-theme",settings.mode); return true; }
    catch { message("外观已临时应用。浏览器未允许保存，重新打开后可能恢复默认。" ); return false; }
  }
  function refreshControls() {
    query("#theme-toggle").textContent="外观与背景";
    query("#appearance-open").textContent="外观";
    queryAll("[name=appearance-mode]").forEach(node=>{node.checked=node.value===settings.mode;node.disabled=imageBusy;});
    query("#appearance-custom-panel").hidden=settings.mode!=="custom";
    for (const key of ["shade","blur","position"]) query(`#appearance-${key}`).value=settings[key];
    query("#appearance-shade-value").textContent=`${settings.shade}%`;
    query("#appearance-blur-value").textContent=`${settings.blur} 像素`;
    query("#appearance-motion-note").hidden=!reduced.matches;
    query("#appearance-image-name").textContent=imageUrl?`已选择：${imageName}`:"正在使用校园背景，尚未选择自己的图片。";
    query("#appearance-remove-image").disabled=!imageUrl||imageBusy;
    query("#appearance-use-image").disabled=!imageUrl||imageBusy;
    query("#appearance-use-preset").setAttribute("aria-pressed",String(settings.source==="preset"));
    query("#appearance-use-image").setAttribute("aria-pressed",String(settings.source==="image"));
  }
  function queryAll(selector) { return [...document.querySelectorAll(selector)]; }
  function setIllustration(image, asset) {
    if(!image||image.dataset.asset===asset)return;
    image.dataset.asset=asset;
    image.hidden=true;
    [image.width,image.height]=ART_SIZES[asset]||[1122,1402];
    image.classList.toggle("is-chibi",asset.startsWith("chibi-"));
    image.src=`/assets/${asset}.png`;
    image.decode().then(()=>{
      // Navigation can change while a previous illustration is still decoding.
      if(image.dataset.asset===asset)image.hidden=false;
    }).catch(()=>{ /* Keep optional art hidden if unavailable; page content remains usable. */ });
  }
  function showView(view) {
    const safeView=Object.hasOwn(PAGE_ART,view)?view:"arrival";
    setIllustration(query(`#view-${safeView} .campus-heading-figure`),PAGE_ART[safeView]);
    setIllustration(query("#campus-character-watermark"),safeView==="map"?"creative-back-v2":PAGE_ART[safeView]);
  }
  function apply() {
    const root=document.documentElement;
    root.classList.toggle("dark",settings.mode!=="light");
    root.classList.toggle("custom-theme",settings.mode==="custom");
    root.style.setProperty("--wallpaper-shade",String(settings.shade/100));
    root.style.setProperty("--wallpaper-blur",`${settings.blur}px`);
    root.style.setProperty("--wallpaper-position",settings.position);
    query("#appearance-wallpaper").hidden=!(settings.source==="image"&&imageUrl);
    root.classList.toggle("has-wallpaper",settings.mode==="custom"&&settings.source==="image"&&Boolean(imageUrl));
    query('meta[name="theme-color"]').content=settings.mode!=="light"?"#101d36":"#f4f8fe";
    refreshControls();
  }
  function update(changes) {
    settings=normalize({...settings,...changes}); apply();
    if(persist()) message("外观已保存，下次打开继续使用。" );
  }
  function database() {
    return new Promise((resolve,reject)=>{
      const request=indexedDB.open("freshman-appearance",1);
      request.onupgradeneeded=()=>{request.result.createObjectStore("images");};
      request.onerror=()=>reject(new Error("浏览器未允许保存背景图片。"));
      request.onblocked=()=>reject(new Error("背景存储被占用，请关闭其他外观设置页面后重试。"));
      request.onsuccess=()=>resolve(request.result);
    });
  }
  async function imageRecord(action,record) {
    const db=await database();
    try { return await new Promise((resolve,reject)=>{
      const transaction=db.transaction("images",action==="get"?"readonly":"readwrite"), store=transaction.objectStore("images");
      const request=action==="get"?store.get("wallpaper"):action==="put"?store.put(record,"wallpaper"):store.delete("wallpaper");
      transaction.oncomplete=()=>resolve(request.result);
      transaction.onerror=transaction.onabort=()=>reject(new Error("背景图片未能保存，请检查浏览器存储设置。"));
    }); } finally { db.close(); }
  }
  function showImage(record) {
    const old=imageUrl; imageUrl=record?URL.createObjectURL(record.blob):""; imageName=record?.name||"";
    const image=query("#appearance-wallpaper");
    if(imageUrl) image.src=imageUrl; else image.removeAttribute("src");
    if(old) URL.revokeObjectURL(old);
    apply();
  }
  async function upload(file) {
    if(imageBusy||!file) return;
    imageBusy=true;query("#appearance-image-file").disabled=true;refreshControls();message("正在处理并保存图片…");
    let bitmap;
    try {
      if(!["image/jpeg","image/png","image/webp"].includes(file.type)) throw new Error("请选择JPG、PNG或WebP图片。" );
      if(file.size>10*1024*1024) throw new Error("图片超过10MB，请选择较小的图片。" );
      bitmap=await createImageBitmap(file);
      if(bitmap.width*bitmap.height>36000000) throw new Error("图片分辨率过大，请缩小到3600万像素以内。" );
      const scale=Math.min(1,2560/Math.max(bitmap.width,bitmap.height)), canvas=document.createElement("canvas");
      canvas.width=Math.max(1,Math.round(bitmap.width*scale));canvas.height=Math.max(1,Math.round(bitmap.height*scale));
      const context=canvas.getContext("2d");context.fillStyle="#071321";context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(bitmap,0,0,canvas.width,canvas.height);
      const blob=await new Promise(resolve=>canvas.toBlob(resolve,"image/jpeg",0.85));
      if(!blob) throw new Error("图片处理未完成，请换一张图片。" );
      const record={blob,name:file.name.slice(0,100)};await imageRecord("put",record);
      imageRevision++;
      settings=normalize({...settings,mode:"custom",source:"image"});showImage(record);
      if(persist()) message("背景已保存在当前浏览器，不会上传。" );
    } catch(error) { message(`${error instanceof DOMException?"这张图片无法读取或保存，请换一张图片。":error.message} 原背景已保留。`); }
    finally { bitmap?.close();imageBusy=false;query("#appearance-image-file").disabled=false;query("#appearance-image-file").value="";refreshControls(); }
  }
  function finishIntro() {
    introRevision++;clearTimeout(introTimer);clearTimeout(introColorTimer);query("#intro-dialog").classList.remove("intro-playing","intro-settled");query("#intro-dialog").close();
    (introReturnFocus?.isConnected&&introReturnFocus!==document.body?introReturnFocus:query("#appearance-open")).focus({preventScroll:true});
    try { sessionStorage.setItem(SEEN,"1"); } catch { /* Animation preference is optional. */ }
  }
  function prepareMascot() {
    if(mascotReady) return mascotReady;
    const dialog=query("#intro-dialog"), svg=query("#intro-lines"), portrait=query("#intro-portrait");
    const revision=++mascotAssetRevision;
    svg.replaceChildren();dialog.classList.remove("mascot-loaded","intro-no-lines","intro-no-portrait");
    portrait.src="/assets/school-mascot.png";
    mascotReady=Promise.allSettled([
      fetch("/assets/mascot-lines.json").then(response=>{if(!response.ok)throw new Error("Outline unavailable");return response.json();}).then(data=>{
        if(revision!==mascotAssetRevision)return;
        if(!Array.isArray(data.viewBox)||data.viewBox.length!==4||!data.viewBox.every(Number.isFinite)||!Array.isArray(data.paths)||data.paths.length>1600) throw new Error("Invalid outline");
        svg.setAttribute("viewBox",data.viewBox.join(" "));
        const strokes=document.createDocumentFragment();
        data.paths.forEach((d,index)=>{
          if(typeof d!=="string"||d.length>20000||!/^[MLZ0-9., \-]+$/.test(d))throw new Error("Invalid stroke");
          const path=document.createElementNS("http://www.w3.org/2000/svg","path");
          path.setAttribute("d",d);path.setAttribute("pathLength","1");path.classList.add("mascot-stroke");
          path.style.setProperty("--draw-delay",`${Math.round(index/data.paths.length*500)}ms`);strokes.append(path);
        });
        svg.append(strokes);
      }),
      portrait.decode().then(()=>{if(revision===mascotAssetRevision)dialog.classList.add("mascot-loaded");})
    ]).then(results=>{
      if(revision!==mascotAssetRevision)return;
      if(results[0].status!=="fulfilled"){svg.replaceChildren();dialog.classList.add("intro-no-lines");}
      if(results[1].status!=="fulfilled")dialog.classList.add("intro-no-portrait");
    });
    return mascotReady;
  }
  function startIntro(force=false) {
    if(query("#intro-dialog").open) return;
    let seen=false;try { seen=sessionStorage.getItem(SEEN)==="1"; } catch { /* Use one bounded entrance when storage is unavailable. */ }
    if(!force&&(reduced.matches||seen)) return;
    const dialog=query("#intro-dialog"), revision=++introRevision;
    dialog.classList.toggle("intro-static",reduced.matches);
    introReturnFocus=document.activeElement;
    dialog.showModal();query("#intro-skip").focus({preventScroll:true});
    // Always allow immediate skip, including while local illustration assets load.
    introTimer=setTimeout(finishIntro,4200);
    Promise.race([prepareMascot(),new Promise(resolve=>setTimeout(resolve,400))]).then(()=>{
      if(revision!==introRevision||!dialog.open)return;
      dialog.classList.add("intro-playing");clearTimeout(introTimer);introTimer=setTimeout(finishIntro,3600);
      // Some embedded browsers throttle CSS timelines. Always reveal a complete welcome.
      introColorTimer=setTimeout(()=>{if(revision===introRevision&&dialog.open)dialog.classList.add("intro-settled");},2500);
    });
  }
  function open() { refreshControls();query("#appearance-dialog").showModal(); }
  function init() {
    settings=read();apply();
    queryAll(".page-heading").forEach(heading=>heading.prepend(query("#campus-heading-template").content.cloneNode(true)));
    query("#appearance-open").addEventListener("click",open);
    query("#appearance-close").addEventListener("click",()=>query("#appearance-dialog").close());
    queryAll("[name=appearance-mode]").forEach(node=>node.addEventListener("change",()=>{if(node.checked)update({mode:node.value});}));
    for(const key of ["shade","blur","position"]) query(`#appearance-${key}`).addEventListener(key==="shade"||key==="blur"?"input":"change",event=>update({[key]:key==="shade"||key==="blur"?Number(event.target.value):event.target.value}));
    query("#appearance-preview-intro").addEventListener("click",()=>startIntro(true));
    query("#intro-skip").addEventListener("click",finishIntro);
    query("#intro-dialog").addEventListener("cancel",event=>{event.preventDefault();finishIntro();});
    query("#appearance-use-preset").addEventListener("click",()=>update({source:"preset"}));
    query("#appearance-use-image").addEventListener("click",()=>{if(imageUrl)update({source:"image"});});
    query("#appearance-image-file").addEventListener("change",event=>upload(event.target.files[0]));
    query("#appearance-remove-image").addEventListener("click",async()=>{
      if(imageBusy||!confirm("移除这张自选背景？指南里的记录会保留。"))return;
      try { await imageRecord("delete");imageRevision++;settings=normalize({...settings,source:"preset"});showImage(null);if(persist())message("已移除自选图片，恢复校园背景。" ); }
      catch(error){message(error.message);}
    });
    reduced.addEventListener("change",()=>{refreshControls();if(reduced.matches&&query("#intro-dialog").open)finishIntro();});
    imageRecord("get").then(record=>{if(imageRevision!==0)return;if(record?.blob instanceof Blob&&["image/jpeg","image/png","image/webp"].includes(record.blob.type))showImage(record);else if(settings.source==="image")message("找不到已保存的图片，先使用内置背景，请重新选择图片。" );}).catch(error=>message(error.message));
    startIntro();
  }
  return {init,open,showView,refreshControls,normalize,getSettings:()=>({...settings})};
})();
Appearance.init();
