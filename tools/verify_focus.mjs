// Exercise the shipped focus transitions with a small DOM fixture; no browser required.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = fs.readFileSync(path.join(root, 'frontend/orientation.js'), 'utf8');
const checks = [];
function fixture(ids, selected) {
  let controls = [], rows = [];
  const document = {activeElement: null};
  const node = (name = '', label = '', row = null) => ({name, disabled:false, isConnected:true,
    getAttribute(key) {return key === 'aria-label' ? label || null : null;},
    closest() {return row;}, focus() {document.activeElement = this;}});
  const select = node('itinerary-place');
  const title = node('scenario-title');
  const status = {textContent:''};
  const list = {get children() {return rows;}, querySelectorAll() {return controls.filter(item => item.name.startsWith('visited-'));}};
  const panel = {setAttribute(){}, querySelectorAll(){return controls;}};
  const rebuild = (stops) => {
    controls.forEach(item => {if (item !== select) item.isConnected = false;});
    rows = stops.map(stop => ({id:stop.id})); controls = [select];
    stops.forEach((stop, index) => {
      const check = node(`visited-${stop.id}`, '', rows[index]);
      const up = node('', `上移${stop.id}`, rows[index]); up.disabled = index === 0;
      const down = node('', `下移${stop.id}`, rows[index]); down.disabled = index === stops.length - 1;
      controls.push(check, up, down, node('', `移除${stop.id}`, rows[index]));
    });
  };
  const initial = ids.map(id => ({id,visited:false})); rebuild(initial);
  document.activeElement = controls.find(item => item.getAttribute('aria-label') === selected) || select;
  const context = vm.createContext({document, history:{pushState(){},replaceState(){}}, state:{view:'map'},
    URL, URLSearchParams, location:{search:''}, console,
    $:selector => ({'#itinerary-list':list,'#itinerary-panel':panel,'#itinerary-status':status,'#itinerary-place':select,'#scenario-title':title})[selector],
    mutate:async (endpoint,payload) => {
      assert.equal(endpoint,'/api/orientation/route');
      const op = payload.operation;
      let stops = context.stops.map(item => ({...item}));
      const index = stops.findIndex(item => item.id === op.place);
      if (op.action === 'remove') stops.splice(index,1);
      if (op.action === 'move') [stops[index],stops[index+op.delta]] = [stops[index+op.delta],stops[index]];
      context.stops = stops;
      return {itinerary:{revision:op.revision+1,stops}};
    }
  });
  vm.runInContext(source,context);
  context.stops = initial;
  context.rebuild = () => rebuild(context.stops);
  vm.runInContext(`orientationReady=true; orientation={cases:[{id:'one'},{id:'two'}], answers:{},itinerary:{revision:0,stops}}; renderItinerary=rebuild; renderPlaces=()=>{}; renderRehearsal=()=>{};`,context);
  return {context,document,title,select};
}
{
  const f = fixture([], '');
  vm.runInContext(`selectRehearsal('two',false)`,f.context);
  assert.equal(f.document.activeElement,f.select,'initialization must not steal focus');
  vm.runInContext(`selectRehearsal('one',true)`,f.context);
  assert.equal(f.document.activeElement,f.title,'user navigation should focus new scenario heading');
  checks.push('scenario navigation focuses heading; initialization preserves focus');
}
for (const example of [
  {ids:['a','b'],selected:'上移b',operation:{action:'move',place:'b',delta:-1},expected:'visited-b'},
  {ids:['a','b'],selected:'下移a',operation:{action:'move',place:'a',delta:1},expected:'visited-a'},
  {ids:['a','b','c'],selected:'移除b',operation:{action:'remove',place:'b'},expected:'visited-c'},
  {ids:['a'],selected:'移除a',operation:{action:'remove',place:'a'},expected:'itinerary-place'}
]) {
  const f = fixture(example.ids,example.selected);
  await vm.runInContext(`routeOperation(${JSON.stringify(example.operation)})`,f.context);
  assert.equal(f.document.activeElement.name,example.expected);
  assert.ok(f.document.activeElement.isConnected && !f.document.activeElement.disabled);
  checks.push(`${example.selected}: focus preserved at ${example.expected}`);
}
const report = {version:'1.3.0',date:'2026-10-14',success:true,checks,
  scope:'Shipped JavaScript in Node VM with controlled DOM fixture; not a native browser keyboard test'};
fs.writeFileSync(path.join(root,'docs/focus-verification.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
