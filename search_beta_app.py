from flask import Flask, jsonify, request, Response
import os
from search_poc.beta_engine import search_all
from search_poc.beta_sources import SOURCES, CONDITION_LABELS
from search_poc.vehicle_catalog import CATALOG, BODY_STYLES, brands, models_for, variants_for, canonical_query

app=Flask(__name__)


HTML=r'''<!doctype html>
<html lang="pt">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DEBE Search Beta</title>
<style>
:root{--bg:#090d14;--panel:#111722;--panel2:#151d2a;--text:#f5f7fb;--muted:#96a4b8;--line:#273245;--accent:#79a7ff;--accent2:#dce8ff;--good:#4bd68b;--goodbg:#103322;--warn:#f4be5b}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top left,#111a2a 0,#090d14 42%);color:var(--text);font:15px/1.45 Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif}
.wrap{max-width:1180px;margin:auto;padding:30px 20px 72px}.hero{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.brand{font-size:31px;font-weight:850;letter-spacing:-1.2px}.brand em{font-style:normal;color:var(--accent)}.sub{color:var(--muted);max-width:690px;margin-top:6px}.beta{font-size:12px;background:#1c2740;border:1px solid #334568;padding:6px 10px;border-radius:999px;color:#dce7fb}
.searchbox{margin-top:25px;background:rgba(17,23,34,.95);border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:0 18px 50px rgba(0,0,0,.18)}
.searchtitle{font-size:18px;font-weight:800;margin-bottom:3px}.searchhint{color:var(--muted);font-size:13px;margin-bottom:16px}
.selectors{display:grid;grid-template-columns:1.05fr 1.2fr 1.25fr 1fr;gap:10px}.field label{display:block;font-size:12px;color:#aeb9c9;margin:0 0 6px 2px;font-weight:700}.field select,.advanced input,.condition select{width:100%;border:1px solid #303b4e;background:#0e141e;color:var(--text);border-radius:11px;padding:12px 12px;font-size:14px;outline:none}.field select:focus,.advanced input:focus,.condition select:focus{border-color:#5576ae;box-shadow:0 0 0 3px rgba(121,167,255,.1)}
.actions{display:grid;grid-template-columns:1fr 190px 150px;gap:10px;margin-top:12px;align-items:end}.condition label{display:block;font-size:12px;color:#aeb9c9;margin:0 0 6px 2px;font-weight:700}.searchbtn{height:44px;border:0;border-radius:11px;background:linear-gradient(135deg,#eef4ff,#cddcff);color:#101827;font-weight:850;font-size:14px;cursor:pointer}.searchbtn:hover{filter:brightness(1.04)}
.advanced details{margin-top:11px}.advanced summary{cursor:pointer;color:#a8b9d6;font-size:13px;user-select:none}.advanced .advrow{display:grid;grid-template-columns:1fr 150px;gap:10px;margin-top:9px}.advanced button{border:1px solid #36445b;background:#172033;color:#eaf0fa;border-radius:10px;font-weight:750;cursor:pointer}
.summarybar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:20px 0 10px}.querytitle{font-size:20px;font-weight:820}.querymeta{color:var(--muted);font-size:13px}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:10px 0 16px}.stat{padding:13px 14px;background:var(--panel);border:1px solid var(--line);border-radius:13px}.stat b{font-size:21px}.stat span{display:block;color:var(--muted);font-size:12px;margin-top:2px}
.searchSpinner{height:26px;width:26px;flex:0 0 26px;border-radius:50%;border:3px solid #304567;border-top-color:#98bfff;animation:debeSpin .75s linear infinite}
@keyframes debeSpin{to{transform:rotate(360deg)}}
@keyframes debeMove{from{background-position:100% 0}to{background-position:-100% 0}}
.loadingBox{display:flex;align-items:center;justify-content:center;gap:15px;max-width:570px;margin:auto;text-align:left}
.loadingBox strong{display:block;color:#edf4ff;font-size:15px}
.loadingBox span{display:block;color:#9eb1cb;font-size:12px}
.loadingTrack{height:5px;max-width:570px;margin:17px auto 0;border-radius:20px;background:linear-gradient(100deg,#253349 5%,#557ff6 42%,#80c1ff 50%,#253349 90%);background-size:250% 100%;animation:debeMove 1.8s ease-in-out infinite}
.searchbtn:disabled,.advanced button:disabled{opacity:.65;cursor:wait}
.sourceFallback{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}
.sourceFallback a{display:block;padding:11px 13px;border:1px solid #3d4f68;border-radius:10px;text-decoration:none;color:#e1ecff;background:#17253b;font-weight:700}
@media(max-width:620px){.sourceFallback{grid-template-columns:1fr}}
.notice{padding:11px 13px;border:1px solid #32425d;background:#111a29;border-radius:11px;color:#b6c5db;margin:12px 0;font-size:13px}.loader{padding:45px;text-align:center;color:var(--muted)}
.results{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.card{background:linear-gradient(180deg,#131a26,#101620);border:1px solid var(--line);border-radius:16px;padding:16px;display:flex;flex-direction:column;min-height:225px}.cardtop{display:flex;gap:12px;justify-content:space-between}.title{font-size:17px;font-weight:800;line-height:1.25}.source{font-size:12px;color:#9fb0c8;margin-top:4px}.pricebox{text-align:right;min-width:120px}.price{font-size:21px;font-weight:880;white-space:nowrap}.old{text-decoration:line-through;color:#7e8b9d;font-size:12px}.discount{display:inline-block;background:var(--goodbg);color:#62e6a0;padding:3px 7px;border-radius:7px;font-size:12px;font-weight:800;margin-top:3px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin:13px 0}.tag{font-size:12px;border:1px solid #334058;background:#121a27;color:#c5d0df;border-radius:999px;padding:4px 8px}.tag.primary{border-color:#3d5f90;background:#17253a;color:#cfe0ff}.snippet{color:var(--muted);font-size:13px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin-bottom:12px}.open{margin-top:auto;display:inline-flex;align-items:center;justify-content:center;text-decoration:none;background:#e9f0ff;color:#111827;border-radius:10px;padding:10px 12px;font-weight:850;width:max-content}
.analyseopen{background:linear-gradient(135deg,#7047ff,#2f7cff);color:#fff}
.sourcesbox{margin-top:18px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:0 14px}.sourcesbox summary{cursor:pointer;padding:13px 0;font-weight:750;color:#c8d3e4}.sources{display:grid;grid-template-columns:repeat(3,1fr);gap:0 16px;padding-bottom:12px}.src{display:flex;justify-content:space-between;border-top:1px solid #222d3d;padding:7px 0;font-size:12px}.ok{color:var(--good)}.empty{color:#77869b}.error{color:#ff8c8c}.foot{margin-top:18px;color:#718095;font-size:12px}.hidden{display:none}
@media(max-width:900px){.selectors{grid-template-columns:1fr 1fr}.results{grid-template-columns:1fr}.sources{grid-template-columns:1fr 1fr}.actions{grid-template-columns:1fr 180px 130px}}
@media(max-width:620px){.wrap{padding:20px 13px 55px}.hero{display:block}.beta{display:inline-block;margin-top:10px}.selectors,.actions,.advanced .advrow{grid-template-columns:1fr}.stats{grid-template-columns:1fr 1fr}.sources{grid-template-columns:1fr}.cardtop{display:block}.pricebox{text-align:left;margin-top:10px}.open{width:100%}}

/* 2026 DEBE Search experience — readable, responsive and task-focused */
:root{--bg:#080d18;--panel:#131e2d;--panel2:#17263b;--text:#f5f9ff;--muted:#a2b2c8;--line:#293a55;--accent:#73a7ff;--accent2:#dce8ff}
html{scroll-behavior:smooth}
body{background:radial-gradient(ellipse 90% 500px at 55% -110px,#18355d 0%,#0b1422 60%,#080d18 100%);font-size:15px}
.wrap{max-width:1200px;padding-top:15px}
.topbar{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:5px 2px 17px;border-bottom:1px solid #263750}
.brandmark{font-size:26px;font-weight:900;letter-spacing:-1.5px;color:#fff;text-decoration:none}.brandmark span{font-size:14px;color:#6da9ff;vertical-align:top;margin-left:3px}
.navlinks{display:flex;gap:8px;background:#101b2b;border:1px solid #293950;border-radius:12px;padding:4px}.navlinks a{color:#c2d0e3;text-decoration:none;border-radius:8px;font-size:13px;font-weight:700;padding:9px 14px}.navlinks a.active{background:#dce9ff;color:#0c1b35}.navlinks a:hover:not(.active){background:#1e3049}
.hero{align-items:center;padding:48px 0 16px}.hero-copy{flex:1;min-width:0}
.eyebrow{color:#91bafd;font-weight:800;letter-spacing:2px;font-size:11px;margin-bottom:15px}.hero h1{font-size:clamp(30px,4vw,49px);line-height:1.12;letter-spacing:-1.6px;margin:0;max-width:740px}.hero h1 span{color:#8db7ff}
.hero .sub{font-size:15px;max-width:600px;color:#bfccdd;line-height:1.65;margin-top:18px}
.hero-points{display:flex;gap:16px;flex-wrap:wrap;margin-top:20px;color:#acc3df;font-size:12px}
.steps{display:grid;gap:12px;min-width:260px;max-width:320px;flex:0 0 29%}
.step{display:flex;align-items:center;gap:11px;color:#e6eefb;text-decoration:none;border-radius:16px;background:#15243a;border:1px solid #304864;padding:15px;transition:transform .2s,border-color .2s}
.step:hover{transform:translateY(-2px);border-color:#779cf6}.step.active{border-color:#6388bd;background:linear-gradient(135deg,#1b385a,#15253d)}
.stepicon{display:grid;place-items:center;width:39px;height:39px;flex:0 0 39px;background:#274468;color:#dae9ff;border-radius:11px;font-weight:900}
.step span:nth-child(2){display:grid;gap:4px;flex:1}.step strong{font-size:14px}.step small{font-size:11px;color:#aabed9}.steparrow{font-size:20px;color:#a1bded}
.searchbox{margin-top:21px;background:#111d2d;border-color:#3b5572;border-radius:21px;padding:25px;box-shadow:0 12px 60px #03091260}
.searchtitle{display:flex;align-items:center;gap:11px;font-size:21px;letter-spacing:-.4px}
.sectionNumber{display:inline-grid;place-items:center;width:34px;height:34px;border-radius:10px;background:#233e64;border:1px solid #416292;color:#bad5ff;font-size:13px;letter-spacing:0;font-weight:900}
.searchhint{margin-top:10px;margin-bottom:20px;font-size:13px}
.optional{font-size:11px;font-weight:500;color:#7e94b2}
.selectors{grid-template-columns:1fr 1.12fr 1.12fr .85fr;gap:13px}
.field label,.condition label{font-size:12px;color:#becfe4}
.field select,.advanced input,.condition select,.sortBox select{border-radius:12px;border-color:#3a506d;background:#0c1727;min-height:49px;color:#f3f8ff}
.field select:focus,.advanced input:focus,.condition select:focus,.sortBox select:focus{border-color:#88b1f0;outline:2px solid #88b1f026}
.actions{grid-template-columns:1fr 200px 225px;gap:12px;margin-top:18px}
.searchbtn{height:49px;background:#a4c7ff;color:#07162c;font-size:15px;box-shadow:0 5px 20px #37588b42}
.searchbtn:hover{background:#c5dcff}
.shortcuts{margin-top:18px;display:flex;align-items:center;gap:9px;flex-wrap:wrap;font-size:12px;color:#a8bcd8}.quick{cursor:pointer;border-radius:999px;color:#dbe8fa;background:#1d2f48;border:1px solid #395675;padding:8px 12px;font-size:12px}.quick:hover{background:#2b486d;border-color:#85a9d5}
.summarybar{margin-top:29px}.querytitle{display:flex;align-items:center;gap:10px;font-size:21px}.querymeta{margin-top:8px}
.sortBox{display:flex;align-items:center;gap:9px;color:#a9b9cf;font-size:12px}.sortBox select{min-width:160px;min-height:40px;padding:7px 10px}
.stats{grid-template-columns:repeat(4,1fr);margin:14px 0 18px}.stat{border-radius:14px;background:#111e2e;border-color:#2c405a;padding:16px}.stat b{font-size:25px}.stat span{font-size:12px}
.results{gap:15px}.card{padding:22px;background:linear-gradient(165deg,#17263a,#111c2d);border-color:#344762;border-radius:18px;min-height:245px;box-shadow:0 8px 24px #02091033;transition:border-color .15s,transform .15s}.card:hover{border-color:#6d91c4;transform:translateY(-2px)}
.title{font-size:18px;line-height:1.32}.source{margin-top:8px;color:#9ec5ee}.sourceDot{display:inline-block;width:7px;height:7px;background:#72cfac;border-radius:50%}
.price{font-size:25px;letter-spacing:-.5px}.tags{margin:17px 0}.tag{background:#1a2a42;border-color:#3a5677}.tag.primary{background:#24436a}
.snippet{margin-bottom:16px}.open{padding:12px 15px;border-radius:11px;font-size:12px}
.analyseopen{background:#7eaaff;color:#0b1b31}.analyseopen:hover{background:#add0ff}.card .open:not(.analyseopen){background:#243a55;color:#e6f0ff;border:1px solid #47617e}
.notice{color:#c6d6e9;background:#13243a;border-color:#334e70;padding:14px 16px}
.foot{line-height:1.6}
@media(max-width:900px){.hero{flex-direction:column;align-items:stretch;padding-top:32px}.steps{max-width:none;grid-template-columns:1fr 1fr}.actions{grid-template-columns:1fr 180px 180px}.selectors{grid-template-columns:1fr 1fr}}
@media(max-width:620px){.wrap{padding:10px 13px 50px}.topbar{gap:9px;flex-wrap:wrap}.brandmark{font-size:23px}.topbar .beta{display:none}.navlinks{order:2;width:100%;justify-content:space-between}.navlinks a{flex:1;text-align:center;padding:9px 6px;font-size:11px}.hero{padding:28px 0 12px}.hero h1{font-size:31px;letter-spacing:-1.1px}.hero-points{gap:8px 12px}.steps{grid-template-columns:1fr 1fr;gap:8px}.step{padding:10px 8px;gap:7px}.stepicon{width:29px;height:29px;flex-basis:29px;font-size:11px}.step strong{font-size:12px}.step small{font-size:10px}.steparrow{display:none}.searchbox{padding:17px;margin-top:12px}.selectors{grid-template-columns:1fr 1fr;gap:12px}.field:nth-child(3),.field:nth-child(4){grid-column:span 2}.actions{grid-template-columns:1fr 1fr}.actions>div:first-child{display:none}.condition{grid-column:span 2}.searchbtn{grid-column:span 2}.summarybar{align-items:flex-start;gap:12px}.sortBox{align-self:flex-end}.sortBox select{min-width:132px}.stats{grid-template-columns:1fr 1fr}.card{padding:17px}.cardtop{display:flex;gap:9px}.pricebox{text-align:right;margin:0;min-width:105px}.price{font-size:20px}.card .open{width:100%}}
</style></head>
<body><div class="wrap">
<header class="topbar"><a class="brandmark" href="/" aria-label="DEBE">DEBE<span>●</span></a><nav class="navlinks" aria-label="Navegação DEBE"><a class="active" href="#search">Pesquisar carros</a><a href="https://debe-auto.onrender.com/" target="_blank" rel="noopener">Analisar anúncio ↗</a></nav><span class="beta">BETA · Portugal</span></header>
<div class="hero"><div class="hero-copy"><div class="eyebrow">O TEU PRÓXIMO CARRO COMEÇA AQUI</div><h1>Encontra o carro certo.<br><span>Confirma se é um bom negócio.</span></h1><p class="sub">Descobre anúncios em Portugal, compara preços e abre qualquer resultado na Análise DEBE.</p><div class="hero-points"><span>✓ Anúncios com fonte</span><span>✓ Preço e quilómetros</span><span>✓ Análise num clique</span></div></div><div class="steps"><a href="#search" class="step active"><span class="stepicon">01</span><span><strong>Pesquisar</strong><small>Encontra anúncios reais</small></span><span class="steparrow">↗</span></a><a href="https://debe-auto.onrender.com/" rel="noopener" target="_blank" class="step"><span class="stepicon">02</span><span><strong>Analisar</strong><small>Avalia riscos e pontos fortes</small></span><span class="steparrow">↗</span></a></div></div>

<section class="searchbox" id="search">
<div class="searchtitle"><span class="sectionNumber">01</span> Que carro procuras?</div>
<div class="searchhint">Escolhe marca e modelo. Os restantes filtros são opcionais e ajudam a encontrar a versão certa.</div>
<form id="form">
<div class="selectors">
  <div class="field"><label for="make">Marca</label><select id="make"></select></div>
  <div class="field"><label for="model">Modelo</label><select id="model"></select></div>
  <div class="field"><label for="variant">Motorização <span class="optional">opcional</span></label><select id="variant"></select></div>
  <div class="field"><label for="body">Carroçaria <span class="optional">opcional</span></label><select id="body"></select></div>
</div>
<div class="actions">
  <div></div>
  <div class="condition"><label for="cond">Estado do veículo</label><select id="cond"><option value="all">Todas</option><option value="new_stock">Novo / stock imediato</option><option value="demo_service">Serviço / demo</option><option value="km0">KM0 / seminovo</option><option value="used_certified">Usado certificado</option><option value="used">Usado</option></select></div>
  <button class="searchbtn" type="submit">⌕ &nbsp; Ver anúncios</button>
</div>
<div class="shortcuts"><span>Experimenta:</span><button type="button" class="quick" data-make="Audi" data-model="A5" data-variant="e-hybrid" data-body="all">Audi A5 e-hybrid ↗</button><button type="button" class="quick" data-make="BMW" data-model="Série 3" data-variant="330e" data-body="station">BMW 330e Touring ↗</button><button type="button" class="quick" data-make="Mercedes-Benz" data-model="GLC" data-variant="GLC 300 e" data-body="suv">Mercedes GLC 300 e ↗</button></div><div class="advanced"><details><summary>Pesquisa avançada por texto</summary><div class="advrow"><input id="q" placeholder="Ex.: BMW 330e Touring Pack M Pro"><button id="advbtn" type="button">Pesquisar texto</button></div></details></div>
</form>
</section>

<div class="summarybar"><div><div id="querytitle" class="querytitle"><span class="sectionNumber">02</span> Resultados</div><div id="querymeta" class="querymeta">Escolhe um modelo ou experimenta uma das pesquisas rápidas.</div></div><div class="sortBox"><label for="sort">Ordenar</label><select id="sort"><option value="relevance">Relevância</option><option value="price_asc">Menor preço</option><option value="price_desc">Maior preço</option><option value="year_desc">Mais recentes</option><option value="km_asc">Menos quilómetros</option></select></div></div>
<div id="notice" class="notice">Seleciona um carro para pesquisar simultaneamente nas fontes nacionais.</div>
<div id="stats" class="stats"></div>
<div id="loading" class="loader hidden" role="status" aria-live="polite"><div class="loadingBox"><div class="searchSpinner" aria-hidden="true"></div><div><strong id="loadingTitle">A pesquisar anúncios…</strong><span id="loadingDetail">A consultar concessionários, stock oficial e marketplaces · <span id="elapsed">0 s</span></span></div></div><div class="loadingTrack" aria-hidden="true"></div></div>
<div id="results" class="results"></div>
<details class="sourcesbox"><summary>Ver fontes consultadas</summary><div id="sources" class="sources"></div></details>
<div class="foot">Beta técnico: algumas fontes já usam conetor direto; outras dependem temporariamente de descoberta pública indexada. Preço e disponibilidade devem ser confirmados no anúncio original.</div>
</div>

<script>
let catalog=null,lastResult=null;
let elapsedTimer=null, startedAt=0, activeSearchId=0, searchController=null;
const eur=v=>v==null?'Preço sob consulta':new Intl.NumberFormat('pt-PT',{style:'currency',currency:'EUR',maximumFractionDigits:0}).format(v);
const esc=s=>String(s||'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const condLabel={new_stock:'Novo / stock imediato',demo_service:'Serviço / demo',km0:'KM0 / seminovo',used_certified:'Usado certificado',used:'Usado',unknown:'Por classificar'};

function fill(sel,items,placeholder,selected){
  sel.innerHTML='';
  if(placeholder!==null){const o=document.createElement('option');o.value='';o.textContent=placeholder;sel.appendChild(o)}
  for(const item of items){const v=Array.isArray(item)?item[0]:item, label=Array.isArray(item)?item[1]:item;const o=document.createElement('option');o.value=v;o.textContent=label;if(v===selected)o.selected=true;sel.appendChild(o)}
}
function recommendedBody(make,model){
  const m=(model||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
  if(!m)return 'all';
  // Reset the previous vehicle's body constraint when choosing a new car.
  // This prevents e.g. BMW Touring -> Audi Q4 / Mercedes GLC being silently
  // searched as Station Wagon, returning misleading zero-results pages.
  if(/^(?:q[2-9]|x[1-9]|ix[1-9]|xc\d{2}|ex\d{2}|ec\d{2}|glc|gle|gla|glb|gls|eq[abecs]|macan|cayenne|kodiaq|tiguan|touareg|t-roc|t-cross|id\.4|rav4|c-hr|bz4x|nx|rx|ux|rz|kuga|tucson|sportage|qashqai|x-trail|ari ya|ariya|captur|austral|3008|5008|c5 aircross|grandland|formentor|ateca|arona|model y)\b/.test(m))return 'suv';
  return 'all';
}
function updateBodyForModel(){
  const make=document.getElementById('make').value,model=document.getElementById('model').value;
  document.getElementById('body').value=recommendedBody(make,model);
}
function updateModels(selected){
  const make=document.getElementById('make').value;
  fill(document.getElementById('model'),(catalog.catalog[make]&&Object.keys(catalog.catalog[make].models).sort())||[],'Escolher modelo',selected);
  updateVariants();updateBodyForModel();
}
function updateVariants(selected){
  const make=document.getElementById('make').value,model=document.getElementById('model').value;
  const a=(catalog.catalog[make]&&catalog.catalog[make].models[model])||[];
  fill(document.getElementById('variant'),a,'Qualquer motorização',selected);
}

async function init(){
  const r=await fetch('/api/catalog');catalog=await r.json();
  fill(document.getElementById('make'),catalog.brands,'Escolher marca','BMW');
  updateModels('Série 3');updateVariants('330e');
  fill(document.getElementById('body'),catalog.body_styles,null,'station');
  document.getElementById('make').addEventListener('change',()=>updateModels());
  document.getElementById('model').addEventListener('change',()=>{updateVariants();updateBodyForModel()});
  document.getElementById('form').addEventListener('submit',runStructured);
  document.getElementById('advbtn').addEventListener('click',runAdvanced);
  document.getElementById('sort').addEventListener('change',()=>{if(lastResult)render(lastResult)});
  document.querySelectorAll('.quick').forEach(btn=>btn.addEventListener('click',()=>{
    document.getElementById('make').value=btn.dataset.make;
    updateModels(btn.dataset.model);
    updateVariants(btn.dataset.variant);
    document.getElementById('body').value=btn.dataset.body;
    document.getElementById('cond').value='all';
    runStructured();
    document.getElementById('search').scrollIntoView({behavior:'smooth',block:'start'});
  }));
  // Users start with a clear search form. No automatic HTTP request on load.
  document.getElementById('notice').textContent='Encontra anúncios verificados em Portugal. Escolhe os filtros e carrega em Ver anúncios.';
}
function setBusy(on){
  document.getElementById('loading').classList.toggle('hidden',!on);
  const primary=document.querySelector('.searchbtn'), advanced=document.getElementById('advbtn');
  primary.disabled=on;advanced.disabled=on;
  primary.textContent=on?'A pesquisar…':'⌕  Ver anúncios';
  advanced.textContent=on?'A pesquisar…':'Pesquisar texto';
  if(elapsedTimer!==null){clearInterval(elapsedTimer);elapsedTimer=null}
  if(on){
    startedAt=Date.now();
    document.getElementById('elapsed').textContent='0 s';
    elapsedTimer=setInterval(()=>{
      const seconds=Math.floor((Date.now()-startedAt)/1000);
      document.getElementById('elapsed').textContent=seconds+' s';
      if(seconds>=8) document.getElementById('loadingTitle').textContent='A validar anúncios e preços…';
    },1000);
    document.getElementById('loadingTitle').textContent='A pesquisar anúncios…';
    document.getElementById('notice').textContent='Pesquisa em curso. A aguardar resposta das fontes nacionais…';
    document.getElementById('results').innerHTML='';
    document.getElementById('sources').innerHTML='';
    document.getElementById('stats').innerHTML='';
  }
}
async function runStructured(e){
  if(e)e.preventDefault();
  const make=document.getElementById('make').value, model=document.getElementById('model').value, variant=document.getElementById('variant').value;
  if(!make||!model){document.getElementById('notice').textContent='Escolhe pelo menos a marca e o modelo.';return}
  document.getElementById('querytitle').textContent=[make,model,variant].filter(Boolean).join(' · ');
  document.getElementById('querymeta').textContent='A pesquisar…';
  const p=new URLSearchParams({make,model,variant,body:document.getElementById('body').value,condition:document.getElementById('cond').value});
  await fetchResults('/api/search?'+p.toString());
}
async function runAdvanced(){
  const q=document.getElementById('q').value.trim();if(!q)return;
  const p=new URLSearchParams({q,condition:document.getElementById('cond').value});
  await fetchResults('/api/search?'+p.toString());
}
async function fetchResults(url){
  const seq=++activeSearchId;
  if(searchController)searchController.abort();
  const controller=new AbortController();
  searchController=controller;
  setBusy(true);
  const timer=setTimeout(()=>controller.abort(),35000);
  try{
    const r=await fetch(url,{signal:controller.signal});
    if(seq!==activeSearchId)return;
    if(!r.ok) throw new Error('Pesquisa temporariamente indisponível ('+r.status+').');
    const d=await r.json();
    if(seq===activeSearchId)render(d);
  }catch(e){
    if(seq!==activeSearchId)return;
    const msg=e.name==='AbortError'?'A pesquisa excedeu 35 segundos. Experimenta reduzir os filtros.':String(e.message||e);
    document.getElementById('querymeta').textContent='Pesquisa não concluída';
    document.getElementById('notice').textContent='Não foi possível concluir a consulta às fontes.';
    document.getElementById('results').innerHTML='<div class="notice">'+esc(msg)+'</div>';
  }finally{
    clearTimeout(timer);
    if(seq===activeSearchId){searchController=null;setBusy(false)}
  }
}
function render(d){
  lastResult=d;
  const s=d.summary||{};
  document.getElementById('querytitle').textContent=d.display_query||d.query||'Resultados';
  document.getElementById('querymeta').textContent=(s.sources_checked||0)+' fontes relevantes consultadas · '+(s.catalog_sources||44)+' no catálogo nacional';
  document.getElementById('notice').textContent=(d.results||[]).length
    ? 'Anúncios encontrados. Confirma sempre o preço e a disponibilidade na fonte original.'
    : 'Sem anúncios exatos confirmados? Vê as alternativas e consulta as fontes originais.';
  const stat=[['total','Carros encontrados'],['new_stock','Novos / stock'],['used_certified','Certificados'],['explicit_discount','Com desconto explícito']];
  document.getElementById('stats').innerHTML=stat.map(x=>'<div class="stat"><b>'+(s[x[0]]||0)+'</b><span>'+x[1]+'</span></div>').join('');
  document.getElementById('sources').innerHTML=(d.sources||[]).map(x=>{
    const value=x.count
      ? ((x.candidate_count&&x.candidate_count>x.count)
          ? x.count+' exato'+(x.count===1?'':'s')+' · '+x.candidate_count+' no filtro amplo'
          : String(x.count))
      : (x.status==='empty'?'0 exatos':x.status);
    const tip=x.candidate_label?(' title="'+esc(x.candidate_label)+'"'):'';
    return '<div class="src"'+tip+'><span>'+esc(x.name)+'</span><span class="'+x.status+'">'+esc(value)+'</span></div>';
  }).join('');
  if(!(d.results||[]).length){
    const sourceLinks=(d.source_links||[]).filter(x=>x.url&&/^https:\/\//.test(x.url));
    const links=sourceLinks.slice(0,8).map(x=>'<a target="_blank" rel="noopener" href="'+esc(x.url)+'">Consultar '+esc(x.name)+' →</a>').join('');
    const alternativeRows=(d.alternatives||[]).slice(0,5).filter(x=>x.url&&/^https:\/\//.test(x.url));
    const alternatives=alternativeRows.map(x=>'<div class="card" style="min-height:0"><div class="title">'+esc(x.title)+'</div><div class="source">'+esc(x.source)+'</div><div class="price">'+eur(x.price_eur)+'</div><div class="querymeta">'+esc([x.year,x.mileage_km!=null?new Intl.NumberFormat('pt-PT').format(x.mileage_km)+' km':''].filter(Boolean).join(' · '))+'</div><a class="open" href="'+esc(x.url)+'" rel="noopener" target="_blank">Abrir este anúncio →</a></div>').join('');
    const headline='<strong>Nenhum anúncio confirmado para a motorização / versão selecionada.</strong>';
    const message=' O DEBE não encontrou um veículo que corresponda exatamente à pesquisa. Isto não significa que só esteja disponível por encomenda. Verifica na marca a possibilidade de encomendar novo e os prazos.';
    const extra=d.partial?'<p>Algumas fontes não responderam. A disponibilidade não pôde ser verificada em todo o mercado.</p>':'';
    document.getElementById('results').innerHTML='<div class="notice" style="grid-column:1/-1">'+headline+esc(message)+extra+(links?'<p>Consultar stock ou possibilidade de encomenda nas fontes:</p><div class="sourceFallback">'+links+'</div>':'')+'</div>'+(alternatives?'<div style="grid-column:1/-1" class="querytitle">Outras motorizações do mesmo modelo — não correspondem à versão pedida</div>'+alternatives:'');
    return;
  }
  const sorted=[...d.results];
  const sort=document.getElementById('sort').value;
  if(sort==='price_asc')sorted.sort((a,b)=>(a.price_eur??1e12)-(b.price_eur??1e12));
  if(sort==='price_desc')sorted.sort((a,b)=>(b.price_eur??-1)-(a.price_eur??-1));
  if(sort==='year_desc')sorted.sort((a,b)=>(b.year??0)-(a.year??0));
  if(sort==='km_asc')sorted.sort((a,b)=>(a.mileage_km??1e12)-(b.mileage_km??1e12));
  document.getElementById('results').innerHTML=sorted.map(x=>{
    const tags=[condLabel[x.condition]||x.condition,x.year,x.mileage_km!=null?new Intl.NumberFormat('pt-PT').format(x.mileage_km)+' km':'',x.observed_at?'Observado em '+new Date(x.observed_at).toLocaleDateString('pt-PT'):'',x.availability,x.dealer,(x.also_at&&x.also_at.length?'Também em '+x.also_at.join(', '):'')].filter(Boolean);
    const analyseHref='https://debe-auto.onrender.com/?analyse='+encodeURIComponent(x.url)+'#start';
    return '<article class="card"><div class="cardtop"><div><div class="title">'+esc(x.title)+'</div><div class="source"><span class="sourceDot"></span> '+esc(x.source)+(x.official?' · stock oficial':'')+'</div></div><div class="pricebox"><div class="price">'+eur(x.price_eur)+'</div>'+(x.list_price_eur?'<div class="old">'+eur(x.list_price_eur)+'</div>':'')+(x.discount_pct?'<span class="discount">-'+x.discount_pct+'% · '+eur(x.discount_eur)+'</span>':'')+'</div></div><div class="tags">'+tags.map((t,i)=>'<span class="tag '+(i===0?'primary':'')+'">'+esc(t)+'</span>').join('')+'</div><div class="snippet">'+esc(x.snippet||'')+'</div><div style="margin-top:auto;display:flex;gap:7px;flex-wrap:wrap"><a class="open analyseopen" href="'+esc(analyseHref)+'">Analisar negócio ↗</a><a class="open" href="'+esc(x.url)+'" target="_blank" rel="noopener">Ver anúncio original ↗</a>'+((x.alternate_links||[]).map(a=>'<a class="open" style="background:#17243a;color:#cfe0ff;border:1px solid #334a70" href="'+esc(a.url)+'" target="_blank" rel="noopener">Ver em '+esc(a.source)+' →</a>').join(''))+'</div></article>'
  }).join('');
}
init();
</script></body></html>'''





@app.get("/")
def home():
    return Response(HTML,mimetype="text/html")

@app.get("/api/catalog")
def api_catalog():
    return jsonify({
        "brands":brands(),
        "catalog":CATALOG,
        "body_styles":BODY_STYLES,
        "conditions":CONDITION_LABELS,
    })

@app.get("/api/search")
def api_search():
    q=(request.args.get("q") or "").strip()
    make=(request.args.get("make") or "").strip()
    model=(request.args.get("model") or "").strip()
    variant=(request.args.get("variant") or "").strip()
    body=(request.args.get("body") or "all").strip()
    condition=(request.args.get("condition") or "all").strip()
    if condition not in set(CONDITION_LABELS)|{"all"}: condition="all"
    if not q and make and model:
        q=canonical_query(make,model,variant,body)
    payload=search_all(q,condition=condition,max_per_source=3,make=make,model=model,variant=variant,body=body)
    payload["display_query"]=" · ".join(x for x in (make,model,variant) if x) if make else q
    payload["selectors"]={"make":make,"model":model,"variant":variant,"body":body}
    return jsonify(payload)


@app.get("/api/sources")
def api_sources():
    return jsonify({"count":len(SOURCES),"sources":SOURCES})

@app.get("/social/<slug>.png")
def social_card(slug):
    from search_poc.social_cards import render_png
    try:
        image=render_png(slug)
    except KeyError:
        return ("Not found",404)
    response=Response(image,mimetype="image/png")
    response.headers["Cache-Control"]="public, max-age=86400"
    return response


@app.get("/health")
def health():
    return jsonify({"ok":True,"service":"debe-search-beta","sources":len(SOURCES)})

def _env_truthy(name):
    return str(os.getenv(name, "")).strip().lower() in {"1","true","yes","on","enabled"}


# Render beta can run the complete DEBE application without changing its
# existing start command (gunicorn search_beta_app:app). Production remains
# unaffected because this switch is only enabled on debe-search-beta.
if _env_truthy("DEBE_SEARCH_INTEGRATED_BETA"):
    from app import app as integrated_app
    app = integrated_app
    # Social media assets remain accessible when Render uses integrated mode.
    app.add_url_rule("/social/<slug>.png",
                     endpoint="debe_social_card",view_func=social_card)


if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000,debug=True)
