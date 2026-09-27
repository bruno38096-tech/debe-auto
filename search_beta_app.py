from flask import Flask, jsonify, request, Response
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
.notice{padding:11px 13px;border:1px solid #32425d;background:#111a29;border-radius:11px;color:#b6c5db;margin:12px 0;font-size:13px}.loader{padding:45px;text-align:center;color:var(--muted)}
.results{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.card{background:linear-gradient(180deg,#131a26,#101620);border:1px solid var(--line);border-radius:16px;padding:16px;display:flex;flex-direction:column;min-height:225px}.cardtop{display:flex;gap:12px;justify-content:space-between}.title{font-size:17px;font-weight:800;line-height:1.25}.source{font-size:12px;color:#9fb0c8;margin-top:4px}.pricebox{text-align:right;min-width:120px}.price{font-size:21px;font-weight:880;white-space:nowrap}.old{text-decoration:line-through;color:#7e8b9d;font-size:12px}.discount{display:inline-block;background:var(--goodbg);color:#62e6a0;padding:3px 7px;border-radius:7px;font-size:12px;font-weight:800;margin-top:3px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin:13px 0}.tag{font-size:12px;border:1px solid #334058;background:#121a27;color:#c5d0df;border-radius:999px;padding:4px 8px}.tag.primary{border-color:#3d5f90;background:#17253a;color:#cfe0ff}.snippet{color:var(--muted);font-size:13px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin-bottom:12px}.open{margin-top:auto;display:inline-flex;align-items:center;justify-content:center;text-decoration:none;background:#e9f0ff;color:#111827;border-radius:10px;padding:10px 12px;font-weight:850;width:max-content}
.sourcesbox{margin-top:18px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:0 14px}.sourcesbox summary{cursor:pointer;padding:13px 0;font-weight:750;color:#c8d3e4}.sources{display:grid;grid-template-columns:repeat(3,1fr);gap:0 16px;padding-bottom:12px}.src{display:flex;justify-content:space-between;border-top:1px solid #222d3d;padding:7px 0;font-size:12px}.ok{color:var(--good)}.empty{color:#77869b}.error{color:#ff8c8c}.foot{margin-top:18px;color:#718095;font-size:12px}.hidden{display:none}
@media(max-width:900px){.selectors{grid-template-columns:1fr 1fr}.results{grid-template-columns:1fr}.sources{grid-template-columns:1fr 1fr}.actions{grid-template-columns:1fr 180px 130px}}
@media(max-width:620px){.wrap{padding:20px 13px 55px}.hero{display:block}.beta{display:inline-block;margin-top:10px}.selectors,.actions,.advanced .advrow{grid-template-columns:1fr}.stats{grid-template-columns:1fr 1fr}.sources{grid-template-columns:1fr}.cardtop{display:block}.pricebox{text-align:left;margin-top:10px}.open{width:100%}}
</style></head>
<body><div class="wrap">
<div class="hero"><div><div class="brand">DEBE Search <em>Beta</em></div><div class="sub">Encontra carros disponíveis em Portugal sem teres de procurar site a site. Cruzamos stock oficial, concessionários e marketplaces.</div></div><span class="beta">BETA · Portugal</span></div>

<section class="searchbox">
<div class="searchtitle">Que carro procuras?</div>
<div class="searchhint">Escolhe os filtros. O DEBE traduz automaticamente a carroçaria para a designação usada por cada marca.</div>
<form id="form">
<div class="selectors">
  <div class="field"><label>Marca</label><select id="make"></select></div>
  <div class="field"><label>Modelo</label><select id="model"></select></div>
  <div class="field"><label>Motorização / versão</label><select id="variant"></select></div>
  <div class="field"><label>Carroçaria</label><select id="body"></select></div>
</div>
<div class="actions">
  <div></div>
  <div class="condition"><label>Condição</label><select id="cond"><option value="all">Todas</option><option value="new_stock">Novo / stock imediato</option><option value="demo_service">Serviço / demo</option><option value="km0">KM0 / seminovo</option><option value="used_certified">Usado certificado</option><option value="used">Usado</option></select></div>
  <button class="searchbtn" type="submit">Pesquisar</button>
</div>
<div class="advanced"><details><summary>Pesquisa avançada por texto</summary><div class="advrow"><input id="q" placeholder="Ex.: BMW 330e Touring Pack M Pro"><button id="advbtn" type="button">Pesquisar texto</button></div></details></div>
</form>
</section>

<div class="summarybar"><div><div id="querytitle" class="querytitle">Resultados</div><div id="querymeta" class="querymeta"></div></div></div>
<div id="notice" class="notice">Seleciona um carro para pesquisar simultaneamente nas fontes nacionais.</div>
<div id="stats" class="stats"></div>
<div id="loading" class="loader hidden">A pesquisar stock oficial e concessionários…</div>
<div id="results" class="results"></div>
<details class="sourcesbox"><summary>Ver fontes consultadas</summary><div id="sources" class="sources"></div></details>
<div class="foot">Beta técnico: algumas fontes já usam conetor direto; outras dependem temporariamente de descoberta pública indexada. Preço e disponibilidade devem ser confirmados no anúncio original.</div>
</div>

<script>
let catalog=null;
const eur=v=>v==null?'Preço sob consulta':new Intl.NumberFormat('pt-PT',{style:'currency',currency:'EUR',maximumFractionDigits:0}).format(v);
const esc=s=>String(s||'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const condLabel={new_stock:'Novo / stock imediato',demo_service:'Serviço / demo',km0:'KM0 / seminovo',used_certified:'Usado certificado',used:'Usado',unknown:'Por classificar'};

function fill(sel,items,placeholder,selected){
  sel.innerHTML='';
  if(placeholder!==null){const o=document.createElement('option');o.value='';o.textContent=placeholder;sel.appendChild(o)}
  for(const item of items){const v=Array.isArray(item)?item[0]:item, label=Array.isArray(item)?item[1]:item;const o=document.createElement('option');o.value=v;o.textContent=label;if(v===selected)o.selected=true;sel.appendChild(o)}
}
function updateModels(selected){const make=document.getElementById('make').value;fill(document.getElementById('model'),(catalog.catalog[make]&&Object.keys(catalog.catalog[make].models).sort())||[],'Escolher modelo',selected);updateVariants()}
function updateVariants(selected){const make=document.getElementById('make').value,model=document.getElementById('model').value;const a=(catalog.catalog[make]&&catalog.catalog[make].models[model])||[];fill(document.getElementById('variant'),a,'Qualquer motorização',selected)}

async function init(){
  const r=await fetch('/api/catalog');catalog=await r.json();
  fill(document.getElementById('make'),catalog.brands,'Escolher marca','BMW');
  updateModels('Série 3');updateVariants('330e');
  fill(document.getElementById('body'),catalog.body_styles,null,'station');
  document.getElementById('make').addEventListener('change',()=>updateModels());
  document.getElementById('model').addEventListener('change',()=>updateVariants());
  document.getElementById('form').addEventListener('submit',runStructured);
  document.getElementById('advbtn').addEventListener('click',runAdvanced);
  runStructured();
}
function setBusy(on){document.getElementById('loading').classList.toggle('hidden',!on);if(on){document.getElementById('results').innerHTML='';document.getElementById('sources').innerHTML='';document.getElementById('stats').innerHTML=''}}
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
  setBusy(true);
  try{
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),22000);
    const r=await fetch(url,{signal:controller.signal});
    clearTimeout(timer);
    if(!r.ok) throw new Error('Pesquisa temporariamente indisponível ('+r.status+').');
    const text=await r.text();
    if(!text) throw new Error('A pesquisa terminou sem resposta. Tenta novamente.');
    const d=JSON.parse(text);render(d);
  }catch(e){
    const msg=e.name==='AbortError'?'A pesquisa demorou demasiado. Tenta novamente.':String(e.message||e);
    document.getElementById('querymeta').textContent='Pesquisa não concluída';
    document.getElementById('results').innerHTML='<div class="notice">'+esc(msg)+'</div>';
  }finally{setBusy(false)}
}
function render(d){
  const s=d.summary||{};
  document.getElementById('querytitle').textContent=d.display_query||d.query||'Resultados';
  document.getElementById('querymeta').textContent=(s.sources_checked||0)+' fontes relevantes consultadas · '+(s.catalog_sources||44)+' no catálogo nacional';
  document.getElementById('notice').textContent=d.beta_note||'';
  const stat=[['total','Carros encontrados'],['new_stock','Novos / stock'],['used_certified','Certificados'],['explicit_discount','Com desconto explícito']];
  document.getElementById('stats').innerHTML=stat.map(x=>'<div class="stat"><b>'+(s[x[0]]||0)+'</b><span>'+x[1]+'</span></div>').join('');
  document.getElementById('sources').innerHTML=(d.sources||[]).map(x=>'<div class="src"><span>'+esc(x.name)+'</span><span class="'+x.status+'">'+(x.count?x.count:(x.status==='empty'?'0 exatos':x.status))+'</span></div>').join('');
  if(!(d.results||[]).length){document.getElementById('results').innerHTML='<div class="notice">Não encontrei resultados nesta passagem. Em fontes ainda sem conetor direto, isto pode significar apenas que o stock não está indexado.</div>';return}
  document.getElementById('results').innerHTML=d.results.map(x=>{
    const tags=[condLabel[x.condition]||x.condition,x.year,x.mileage_km!=null?new Intl.NumberFormat('pt-PT').format(x.mileage_km)+' km':'',x.availability,x.dealer,(x.also_at&&x.also_at.length?'Também em '+x.also_at.join(', '):'')].filter(Boolean);
    return '<article class="card"><div class="cardtop"><div><div class="title">'+esc(x.title)+'</div><div class="source">'+esc(x.source)+(x.discovery==='direct_connector'?' · ligação direta':'')+'</div></div><div class="pricebox"><div class="price">'+eur(x.price_eur)+'</div>'+(x.list_price_eur?'<div class="old">'+eur(x.list_price_eur)+'</div>':'')+(x.discount_pct?'<span class="discount">-'+x.discount_pct+'% · '+eur(x.discount_eur)+'</span>':'')+'</div></div><div class="tags">'+tags.map((t,i)=>'<span class="tag '+(i===0?'primary':'')+'">'+esc(t)+'</span>').join('')+'</div><div class="snippet">'+esc(x.snippet||'')+'</div><div style="margin-top:auto;display:flex;gap:7px;flex-wrap:wrap"><a class="open" href="'+esc(x.url)+'" target="_blank" rel="noopener">Ver em '+esc(x.source)+' →</a>'+((x.alternate_links||[]).map(a=>'<a class="open" style="background:#17243a;color:#cfe0ff;border:1px solid #334a70" href="'+esc(a.url)+'" target="_blank" rel="noopener">Ver em '+esc(a.source)+' →</a>').join(''))+'</div></article>'
  }).join('');
}
init();
</script></body></html>'''


def _startup_bmcar_diag():
    try:
        import requests,re
        from bs4 import BeautifulSoup
        url="https://www.bmcar.pt/veiculos?brandIds%5B%5D=c427305a-a22d-433f-99dd-2198ccf858da&engineTypeIds%5B%5D=9&brandSegmentIds%5B%5D=9f2b387a-fa3a-4e24-554f-08d7d3ff7f58"
        headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept-Language":"pt-PT,pt;q=0.9"}
        r=requests.get(url,headers=headers,timeout=8)
        soup=BeautifulSoup(r.text,"html.parser")
        scripts=[s.get("src") for s in soup.find_all("script") if s.get("src")]
        preload_chunks=[x.get("href") for x in soup.find_all("link",href=True) if "/_next/static/chunks/" in x.get("href","")]
        scripts=list(dict.fromkeys(scripts+preload_chunks))
        inline="\n".join(s.get_text("\n",strip=True) for s in soup.find_all("script") if not s.get("src"))
        links=[a.get("href") for a in soup.find_all("a",href=True) if "/veiculos/" in a.get("href","")]
        interesting=[]
        scan=r.text+"\n"+inline
        for p in [r'https?://[^"\'\s<>]+',r'/(?:api|graphql|vehicles|veiculos)[^"\'\s<>]+',r'[^"\'\s<>]{0,90}(?:brandIds|engineTypeIds|brandSegmentIds)[^"\'\s<>]{0,140}']:
            for x in re.findall(p,scan,re.I):
                if any(k in x.lower() for k in ("api","graphql","vehicle","veiculo","brandid","enginetype","brandsegment")) and x not in interesting:
                    interesting.append(x[:500])
        print("BMCAR_DIAG_STATUS",r.status_code,"LEN",len(r.text),"HAS_NEXT",("__NEXT_DATA__" in r.text),flush=True)
        print("BMCAR_DIAG_SCRIPTS",scripts[:80],flush=True)
        print("BMCAR_DIAG_LINKS",links[:40],flush=True)
        print("BMCAR_DIAG_INTERESTING",interesting[:80],flush=True)
        try:
            rsc_url=url+("&" if "?" in url else "?")+"_rsc=1"
            rsc_headers=dict(headers)
            rsc_headers.update({"RSC":"1","Next-Url":"/veiculos","Accept":"text/x-component,*/*;q=0.8"})
            rr=requests.get(rsc_url,headers=rsc_headers,timeout=8)
            lowr=rr.text.lower()
            samples=[]
            for needle in ["330e","touring","31700","46900","vehicle","price"]:
                p=lowr.find(needle)
                if p>=0:samples.append((needle,re.sub(r"\s+"," ",rr.text[max(0,p-700):p+1800])[:2500]))
            print("BMCAR_DIAG_RSC",rr.status_code,"LEN",len(rr.text),"CT",rr.headers.get("content-type"),"COUNTS",{"330e":lowr.count("330e"),"touring":lowr.count("touring")},"SAMPLES",samples,flush=True)
        except Exception as e:
            print("BMCAR_DIAG_RSC_ERROR",repr(e),flush=True)
        low=r.text.lower()
        for needle in ["330e","31700","46900","vehicleid","stockid","pvp","flash sale","bmw premium selection"]:
            poss=[m.start() for m in re.finditer(re.escape(needle),low)]
            samples=[]
            for p in poss[:12]:
                samples.append(re.sub(r"\\s+"," ",r.text[max(0,p-350):p+700])[:1100])
            print("BMCAR_DIAG_NEEDLE",needle,"COUNT",len(poss),"SAMPLES",samples,flush=True)
        # Scan all Next.js chunks concurrently for the vehicle-filter transport.
        from concurrent.futures import ThreadPoolExecutor, as_completed
        def scan_chunk(src):
            try:
                js=requests.get("https://www.bmcar.pt"+src,headers=headers,timeout=5).text
                lowjs=js.lower()
                needles=["brandsegmentids","enginetypeids","vehicleconditionids","totalvehicles","showonlyavailable","getvehicles","/vehicles","/veiculos","graphql","api"]
                found=[]
                for needle in needles:
                    pos=0; count=0
                    while True:
                        p=lowjs.find(needle,pos)
                        if p<0 or count>=5:break
                        snippet=re.sub(r"\s+"," ",js[max(0,p-1000):p+1800])
                        found.append((needle,snippet[:2800]))
                        pos=p+len(needle); count+=1
                return src,found
            except Exception:
                return src,[]
        with ThreadPoolExecutor(max_workers=10) as ex:
            futs=[ex.submit(scan_chunk,src) for src in scripts]
            for fut in as_completed(futs):
                src,found=fut.result()
                if found:
                    print("BMCAR_DIAG_CHUNK",src,"FOUND",found[:20],flush=True)
    except Exception as e:
        print("BMCAR_DIAG_ERROR",repr(e),flush=True)

_startup_bmcar_diag()

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
    payload=search_all(q,condition=condition,max_per_source=3)
    payload["display_query"]=" · ".join(x for x in (make,model,variant) if x) if make else q
    payload["selectors"]={"make":make,"model":model,"variant":variant,"body":body}
    return jsonify(payload)

@app.get("/api/debug-bmcar")
def debug_bmcar():
    import requests,re
    from bs4 import BeautifulSoup
    url="https://www.bmcar.pt/veiculos?brandIds%5B%5D=c427305a-a22d-433f-99dd-2198ccf858da&engineTypeIds%5B%5D=9&brandSegmentIds%5B%5D=9f2b387a-fa3a-4e24-554f-08d7d3ff7f58"
    headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept-Language":"pt-PT,pt;q=0.9"}
    try:
        r=requests.get(url,headers=headers,timeout=8)
        html=r.text
        soup=BeautifulSoup(html,"html.parser")
        scripts=[s.get("src") for s in soup.find_all("script") if s.get("src")]
        inline="\n".join(s.get_text("\n",strip=True) for s in soup.find_all("script") if not s.get("src"))
        links=[a.get("href") for a in soup.find_all("a",href=True) if "/veiculos/" in a.get("href","")]
        pats=[]
        scan=html+"\n"+inline
        for p in [r'https?://[^"\'\s<>]+',r'/(?:api|graphql|vehicles|veiculos)[^"\'\s<>]+',r'[^"\'\s<>]{0,80}(?:brandIds|engineTypeIds|brandSegmentIds)[^"\'\s<>]{0,120}']:
            pats.extend(re.findall(p,scan,re.I))
        interesting=[]
        for x in pats:
            if any(k in x.lower() for k in ("api","graphql","vehicle","veiculo","brandid","enginetype","brandsegment")) and x not in interesting:
                interesting.append(x[:500])
        return jsonify({"status":r.status_code,"length":len(html),"scripts":scripts[:80],"vehicle_links":links[:80],"interesting":interesting[:120],"has_next_data":"__NEXT_DATA__" in html,"html_head":html[:1200]})
    except Exception as e:
        return jsonify({"error":repr(e)}),500

@app.get("/api/sources")
def api_sources():
    return jsonify({"count":len(SOURCES),"sources":SOURCES})

@app.get("/health")
def health():
    return jsonify({"ok":True,"service":"debe-search-beta","sources":len(SOURCES)})

if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000,debug=True)
