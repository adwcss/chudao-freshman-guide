// Local Edge verification using the already bundled Playwright, no downloads.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import os from 'node:os';
import {spawn} from 'node:child_process';
import assert from 'node:assert/strict';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const tmp=path.join(root,'tmp');fs.mkdirSync(tmp,{recursive:true});
const data=fs.mkdtempSync(path.join(tmp,'preparation-browser-'));
const edge=path.join(process.env['ProgramFiles(x86)'],'Microsoft','Edge','Application','msedge.exe');
assert.ok(fs.existsSync(edge),'Installed Edge required');
const playwrightPath=process.env.GUIDE_PLAYWRIGHT_PATH||path.join(os.homedir(),'.cache','codex-runtimes','codex-primary-runtime','dependencies','node','node_modules','playwright','index.mjs');
assert.ok(fs.existsSync(playwrightPath),'Bundled Playwright required for development verification');
const {chromium}=await import(pathToFileURL(playwrightPath).href);
const port=8769,url=`http://127.0.0.1:${port}/?view=preparation`;
const server=spawn('python',['-X','utf8','-S','run.py','--port',String(port)],{cwd:root,windowsHide:true,env:{...process.env,GUIDE_ALLOW_REMOTE_LLM:'false',GUIDE_LLM_API_KEY:'',GUIDE_DATA_DIR:data},stdio:'ignore'});
let browser,cdp,page;
const report={version:'1.4.0',date:'2026-10-14',environment:'Installed Edge headless, isolated profile and synthetic localhost:8769 data',checks:[],screenshots:[],errors:[],success:false};
async function until(test,label){for(let index=0;index<60;index++){try{if(await test())return;}catch{}await delay(200);}throw new Error('Wait failed: '+label);}
async function click(selector){await page.locator(selector).click();}
async function fill(selector,value){await cdp.eval(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});el.value=${JSON.stringify(value)};el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));})()`);}
async function saved(revision){await until(()=>cdp.eval(`preparation.state.revision>${revision}&&!preparationBusy`),'save');}
async function viewport(width,height){await cdp.send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<600});}
async function screenshot(name,height=null){await cdp.eval('window.scrollTo(0,0)');await until(()=>cdp.eval('document.querySelector("#toast").hidden'),'toast settled');const bounds=await cdp.send('Page.getLayoutMetrics');const size=bounds.cssContentSize;const result=await cdp.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width:size.width,height:height?Math.min(height,size.height):size.height,scale:1}});const folder=path.join(root,'output','screenshots');fs.mkdirSync(folder,{recursive:true});fs.writeFileSync(path.join(folder,name),Buffer.from(result.data,'base64'));report.screenshots.push(name);}
try{
  await until(async()=>{const response=await fetch(`http://127.0.0.1:${port}/api/health`);return response.ok;},'server');
  browser=await chromium.launch({executablePath:edge,headless:true});
  const context=await browser.newContext({viewport:{width:1280,height:900}});page=await context.newPage();
  page.on('pageerror',error=>report.errors.push(error.message));page.on('console',message=>{if(['error','warning'].includes(message.type()))report.errors.push(message.text());});
  const session=await context.newCDPSession(page);cdp={send:(method,params={})=>session.send(method,params),eval:expression=>page.evaluate(expression)};
  console.log('Connected to isolated Edge via bundled Playwright');await page.goto(url);
  await until(()=>cdp.eval('preparationReady&&plannerReady&&orientationReady&&!document.querySelector("#global-error").hidden===false'),'page boot');
  await fill('#prep-departure','2026-10-20');await fill('#prep-arrival','2026-10-21');await fill('#prep-time','09:30');await fill('#prep-mode','rail');await fill('#prep-dorm','qinyuan-1-9');await fill('#prep-room-note','测试：按分配通知确认楼号');
  await click('#departure-form button[type=submit]');await saved(0);assert.match(await cdp.eval('document.querySelector("#departure-countdown").textContent'),/6 天/);report.checks.push('Personal plan saved; six-day countdown from explicit date');
  await fill('[name=status-identity]','packed');await click('[data-prep-focus=save-identity]');await saved(1);
  assert.equal(await cdp.eval('document.activeElement.dataset.prepFocus'),'save-identity');report.checks.push('Packing save restores focus to same item control');
  await fill('[name=status-towel]','buy');await fill('[name=quantity-towel]','2');await click('[data-prep-focus=save-towel]');await saved(2);
  await fill('#packing-custom-title','眼镜盒');await click('#packing-add button');await saved(3);
  assert.equal(await cdp.eval('preparation.items.length'),16);report.checks.push('Identity packed, towel buy quantity 2, custom item added');
  await click('[data-packing-id=towel] .packing-row-actions button');assert.equal(await cdp.eval('document.querySelector("#personal-task-title").value'),'到校购买：毛巾');await click('#save-task');await until(()=>cdp.eval('!document.querySelector("#task-dialog").open'),'task save');report.checks.push('Packing item opens prefilled real task editor; user-confirmed task saved');
  await cdp.send('Page.reload');await until(()=>cdp.eval('preparationReady&&preparation.state.revision===4'),'refresh');assert.equal(await cdp.eval('document.querySelector("#prep-arrival").value'),'2026-10-21');assert.equal(await cdp.eval('preparation.items.find(i=>i.id==="towel").quantity'),2);report.checks.push('Refresh restores plan, quantity and packing state');
  await cdp.eval(`(async()=>{const value=await api('/api/preparation/backup?session='+state.session);const file=new File([JSON.stringify(value)],'synthetic-preparation.json',{type:'application/json'});const dt=new DataTransfer();dt.items.add(file);const input=document.querySelector('#prep-backup-file');input.files=dt.files;input.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  await until(()=>cdp.eval('document.querySelector("#prep-restore-dialog").open'),'restore preview');assert.equal(await cdp.eval('preparation.state.revision'),4);await click('#prep-restore-confirm');await until(()=>cdp.eval('preparation.state.revision===5&&!document.querySelector("#prep-restore-dialog").open'),'restore');report.checks.push('Real file-input backup preview is read-only; confirmed restoration succeeds');
  await click('#prep-print-memo');await until(()=>cdp.eval('document.querySelector("#prep-memo-dialog").open'),'memo');assert.match(await cdp.eval('document.querySelector("#prep-memo-preview").textContent'),/到校购买 · 毛巾 × 2/);
  await cdp.eval('document.body.classList.add("print-preparation")');await cdp.send('Emulation.setEmulatedMedia',{media:'print'});
  assert.equal(await cdp.eval('getComputedStyle(document.querySelector(".workspace")).display'),'none');assert.equal(await cdp.eval('getComputedStyle(document.querySelector("#prep-memo-dialog")).display'),'block');
  const pdf=await cdp.send('Page.printToPDF',{printBackground:true,paperWidth:8.27,paperHeight:11.69});fs.writeFileSync(path.join(tmp,'preparation-print-140.pdf'),Buffer.from(pdf.data,'base64'));report.checks.push('Memo print CSS and Edge-generated PDF verified; physical printer not tested');
  await cdp.send('Emulation.setEmulatedMedia',{media:''});await cdp.eval('document.body.classList.remove("print-preparation")');await click('#prep-memo-close');
  assert.ok(await cdp.eval('document.documentElement.scrollWidth<=innerWidth'));await screenshot('preparation-140.png');await screenshot('preparation-overview-140.png',1000);
  await click('#prep-dorm-map');assert.match(await cdp.eval('document.querySelector("#place-detail").textContent'),/沁园1-9/);report.checks.push('Saved dorm area opens correct map place');
  await cdp.send('Page.navigate',{url});await until(()=>cdp.eval('preparationReady'),'mobile boot');await viewport(390,844);await delay(150);assert.ok(await cdp.eval('document.documentElement.scrollWidth<=innerWidth'));await screenshot('mobile-preparation-140.png');await screenshot('mobile-preparation-overview-140.png',1100);
  await page.locator('[data-prep-focus=save-identity]').press('Enter');await saved(5);assert.equal(await cdp.eval('document.activeElement.dataset.prepFocus'),'save-identity');report.checks.push('Native Enter key saves packing item and retains focus on mobile viewport');
  assert.equal(report.errors.length,0);const health=await(await fetch(`http://127.0.0.1:${port}/api/health`)).json();assert.equal(health.remote_calls,0);report.remote_calls=0;report.success=true;
}catch(error){report.failure=error.message;throw error;}
finally{fs.writeFileSync(path.join(root,'docs','preparation-browser-verification.json'),JSON.stringify(report,null,2)+'\n');if(browser)await browser.close();server.kill();console.log(JSON.stringify(report,null,2));}
