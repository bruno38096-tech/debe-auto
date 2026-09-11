const fs = require('fs'), vm = require('vm'), assert = require('assert');
const elements = {};
const element = () => ({value:'',textContent:'',innerHTML:'',disabled:false,
  classList:{add(){},remove(){},toggle(){}},scrollIntoView(){},focus(){}});
const get = id => elements[id] ||= element();
const resets = [element(),element()];
let requests = [], busy = [];
const context = {
  document:{getElementById:get,querySelectorAll:()=>resets},
  $:get,esc:s=>String(s??''),currentUrl:'https://example.com/car',listing:{engine:'2.0 TDI 170cv'},
  setListingPhoto(){},setBusy:(kind,on)=>busy.push([kind,on]),alert(){},
  URL,AbortController,console,setTimeout,clearTimeout,
  fetch:(url,options)=>new Promise((resolve,reject)=>{
    requests.push({url,resolve:data=>resolve({ok:true,json:async()=>data}),reject});
    options.signal.addEventListener('abort',()=>reject(Object.assign(new Error('aborted'),{name:'AbortError'})));
  })
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('debe_frontend_v3.js','utf8'),context);
const tick = ()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  Object.entries({model:'Audi A4',year:'2006',km:'284398',price:'4500',fuel:'Diesel'}).forEach(([k,v])=>get(k).value=v);
  const report = get('reportBtn').onclick();
  requests[0].resolve({strengths:['Conforto verificado'],issues:[],checks:[]});
  await tick();
  assert(get('strengths').innerHTML.includes('Conforto verificado'));
  assert(get('deals').innerHTML.includes('A procurar'));
  resets[0].onclick();
  await report;
  assert.strictEqual(get('strengths').innerHTML,'');
  assert.strictEqual(context.currentUrl,'');
  // Even a transport that completes after reset may not render an old report.
  requests[1].resolve({deals:[]});
  await tick();
  assert.strictEqual(get('deals').innerHTML,'');
  console.log('PASS: independent rendering and cancellation on restart');
})().catch(error=>{console.error(error);process.exitCode=1});
