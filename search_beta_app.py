from flask import Flask, jsonify, request, Response
from search_poc.beta_engine import search_all
from search_poc.beta_sources import SOURCES, CONDITION_LABELS

app=Flask(__name__)

HTML=r'''<!doctype html>
<html lang="pt">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DEBE Search Beta</title>
<style>
:root{--bg:#090b10;--card:#121620;--soft:#1a2030;--text:#f3f5f7;--muted:#9aa5b5;--line:#242c3a;--good:#43d17a;--warn:#f0b44b;--accent:#7aa7ff}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,#080a0e,#0c1018);color:var(--text);font:15px/1.45 Inter,system-ui,Segoe UI,Arial,sans-serif}
.wrap{max-width:1180px;margin:auto;padding:28px 18px 70px}.top{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.brand{font-size:30px;font-weight:850;letter-spacing:-1px}.beta{font-size:12px;background:#232b3b;border:1px solid #35405a;padding:5px 9px;border-radius:999px;color:#c8d5eb}.sub{color:var(--muted);max-width:760px;margin-top:6px}
.search{display:grid;grid-template-columns:1fr 190px 120px;gap:10px;margin:25px 0 16px}.search input,.search select,.search button{border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:11px;padding:13px 14px;font-size:15px}.search button{background:#e9eef7;color:#111827;font-weight:800;cursor:pointer}
.stats{display:grid;grid-template-columns:repeat(6,1fr);gap:9px;margin:15px 0}.stat{padding:12px;background:var(--card);border:1px solid var(--line);border-radius:12px}.stat b{display:block;font-size:20px}.stat span{color:var(--muted);font-size:12px}
.notice{padding:11px 13px;border:1px solid #36425a;background:#121925;border-radius:10px;color:#b9c5d8;margin:12px 0}
.grid{display:grid;grid-template-columns:1fr 300px;gap:18px}.results{display:grid;gap:10px}.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:15px}.row{display:flex;gap:10px;justify-content:space-between}.title{font-size:17px;font-weight:760}.source{font-size:12px;color:#b8c4d8;margin-top:3px}.price{font-size:20px;font-weight:850;white-space:nowrap}.old{text-decoration:line-through;color:var(--muted);font-size:12px}.discount{display:inline-block;background:#123522;color:#64df98;padding:3px 7px;border-radius:7px;font-size:12px;font-weight:750}.tags{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}.tag{font-size:12px;border:1px solid #313a4a;color:#c2cada;border-radius:999px;padding:3px 7px}.snippet{color:var(--muted);font-size:13px}.open{display:inline-block;margin-top:10px;color:#a9c5ff;text-decoration:none;font-weight:700}
.side{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;height:max-content;position:sticky;top:12px}.side h3{margin:0 0 10px}.src{display:flex;justify-content:space-between;border-top:1px solid var(--line);padding:8px 0;font-size:12px}.ok{color:var(--good)}.empty{color:var(--muted)}.error{color:#ff8a8a}
.loader{padding:35px;text-align:center;color:var(--muted)}.hidden{display:none}.foot{margin-top:22px;color:var(--muted);font-size:12px}
@media(max-width:820px){.search{grid-template-columns:1fr}.stats{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}.side{position:static}.top{display:block}.beta{display:inline-block;margin-top:8px}}
</style></head>
<body><div class="wrap">
<div class="top"><div><div class="brand">DEBE Search <span style="color:#7aa7ff">Beta</span></div><div class="sub">Pesquisa simultânea em stock oficial, usados certificados, grandes grupos de concessionários e Standvirtual como benchmark. O DEBE principal continua separado.</div></div><span class="beta">BETA · Portugal</span></div>
<form class="search" id="form"><input id="q" value="BMW 330e Touring" placeholder="Ex.: BMW 330e Touring, Mercedes GLC 300e, Volvo EX30"><select id="cond"><option value="all">Todas as condições</option><option value="new_stock">Novo / stock imediato</option><option value="demo_service">Serviço / demo</option><option value="km0">KM0 / seminovo</option><option value="used_certified">Usado certificado</option><option value="used">Usado</option></select><button>Pesquisar</button></form>
<div id="notice" class="notice">A pesquisa beta pode demorar alguns segundos porque consulta várias fontes públicas em paralelo.</div>
<div id="stats" class="stats"></div>
<div class="grid"><div><div id="loading" class="loader hidden">A pesquisar fontes nacionais…</div><div id="results" class="results"></div></div><aside class="side"><h3>Fontes consultadas</h3><div id="sources"></div></aside></div>
<div class="foot">Beta técnico: os conetores diretos têm maior cobertura; algumas fontes usam descoberta pública indexada e podem omitir stock não indexado. Preços e disponibilidade devem ser confirmados na fonte original.</div>
</div>
<script>
const eur=v=>v==null?'Preço sob consulta':new Intl.NumberFormat('pt-PT',{style:'currency',currency:'EUR',maximumFractionDigits:0}).format(v);
const esc=s=>(s||'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const condLabel={new_stock:'Novo / stock imediato',demo_service:'Serviço / demo',km0:'KM0 / seminovo',used_certified:'Usado certificado',used:'Usado',unknown:'Por classificar'};
async function run(e){if(e)e.preventDefault();const q=document.getElementById('q').value.trim();if(!q)return;
document.getElementById('loading').classList.remove('hidden');document.getElementById('results').innerHTML='';document.getElementById('sources').innerHTML='';document.getElementById('stats').innerHTML='';
try{const r=await fetch('/api/search?q='+encodeURIComponent(q)+'&condition='+encodeURIComponent(document.getElementById('cond').value));const d=await r.json();render(d)}
catch(e){document.getElementById('results').innerHTML='<div class="notice">Erro na pesquisa beta: '+esc(String(e))+'</div>'}
finally{document.getElementById('loading').classList.add('hidden')}}
function render(d){const s=d.summary||{};const stat=[['total','Resultados'],['sources_with_hits','Fontes c/ resultados'],['new_stock','Novos'],['used_certified','Certificados'],['used','Usados'],['explicit_discount','Desconto explícito']];
document.getElementById('stats').innerHTML=stat.map(x=>'<div class="stat"><b>'+(s[x[0]]||0)+'</b><span>'+x[1]+'</span></div>').join('');
document.getElementById('notice').textContent=d.beta_note||'';
document.getElementById('sources').innerHTML=(d.sources||[]).map(x=>'<div class="src"><span>'+esc(x.name)+'</span><span class="'+x.status+'">'+(x.count?x.count:x.status)+'</span></div>').join('');
if(!(d.results||[]).length){document.getElementById('results').innerHTML='<div class="notice">Sem resultados descobertos nesta passagem. Isto não prova ausência de stock — algumas fontes podem não estar indexadas.</div>';return}
document.getElementById('results').innerHTML=d.results.map(x=>{let tags=[condLabel[x.condition]||x.condition,x.year,x.mileage_km!=null?new Intl.NumberFormat('pt-PT').format(x.mileage_km)+' km':'',x.availability,x.dealer,(x.also_at&&x.also_at.length?'Também: '+x.also_at.join(', '):'')].filter(Boolean);
return '<div class="card"><div class="row"><div><div class="title">'+esc(x.title)+'</div><div class="source">'+esc(x.source)+(x.official?' · fonte oficial/rede':' · benchmark')+(x.discovery==='direct_connector'?' · conetor direto':'')+'</div></div><div style="text-align:right"><div class="price">'+eur(x.price_eur)+'</div>'+(x.list_price_eur?'<div class="old">'+eur(x.list_price_eur)+'</div>':'')+(x.discount_pct?'<span class="discount">-'+x.discount_pct+'% · '+eur(x.discount_eur)+'</span>':'')+'</div></div><div class="tags">'+tags.map(t=>'<span class="tag">'+esc(String(t))+'</span>').join('')+'</div><div class="snippet">'+esc(x.snippet||'')+'</div><a class="open" href="'+esc(x.url)+'" target="_blank" rel="noopener">Abrir fonte original →</a></div>'}).join('')}
document.getElementById('form').addEventListener('submit',run);run();
</script></body></html>'''

@app.get("/")
def home():
    return Response(HTML,mimetype="text/html")

@app.get("/api/search")
def api_search():
    q=(request.args.get("q") or "").strip()
    condition=(request.args.get("condition") or "all").strip()
    if condition not in set(CONDITION_LABELS)|{"all"}: condition="all"
    return jsonify(search_all(q,condition=condition,max_per_source=3))

@app.get("/api/sources")
def api_sources():
    return jsonify({"count":len(SOURCES),"sources":SOURCES})

@app.get("/health")
def health():
    return jsonify({"ok":True,"service":"debe-search-beta","sources":len(SOURCES)})

if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000,debug=True)
