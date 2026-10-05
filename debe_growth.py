"""Organic growth helpers for the DEBE public beta.

Adds SEO metadata, crawlable explanatory copy, referral sharing and basic
robots/sitemap endpoints without adding third-party trackers or cookies.
"""
from flask import Response

BASE_URL='https://debe-auto.onrender.com'
INDEXNOW_KEY='9bfddbc4b0e831cd9e58c894a2cfeb54'


def patch_index(path='index.html'):
    marker='debe-growth-v1'
    try:
        txt=open(path,encoding='utf-8').read()
        if marker in txt:
            return
        txt=txt.replace('<title>DEBE Auto</title>','<title>DEBE — Analisar anúncios de carros usados</title>')

        meta='''\n<!-- debe-growth-v1 -->
<meta name="description" content="Analise anúncios de carros usados em Portugal com score DEBE, pontos fortes, problemas reportados, verificações antes da compra e negócios comparáveis.">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="https://debe-auto.onrender.com/">
<meta property="og:type" content="website">
<meta property="og:locale" content="pt_PT">
<meta property="og:title" content="DEBE — Análise de carros usados">
<meta property="og:description" content="Cole o link de um anúncio e receba uma análise independente com score, riscos, verificações e comparáveis.">
<meta property="og:url" content="https://debe-auto.onrender.com/">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebApplication","name":"DEBE Auto","url":"https://debe-auto.onrender.com/","applicationCategory":"AutomotiveApplication","operatingSystem":"Web","description":"Ferramenta online para analisar anúncios de carros usados, comparar risco e valor e apoiar a decisão de compra."}</script>
<style>
.debeSeo{margin:22px 0;background:white;border:1px solid #e3e6ef;border-radius:20px;padding:24px;line-height:1.65}.debeSeo h2{margin-top:0}.debeSeoGrid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}.debeSeo h3{margin-bottom:6px}.debeShare{margin:18px 0;background:#f8f7ff;border:1px solid #ddd8ff;border-radius:18px;padding:20px}.debeShareActions{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}.debeShareActions a,.debeShareActions button{display:inline-block;text-decoration:none;border:0;border-radius:12px;padding:12px 16px;font-weight:800;cursor:pointer}.debeShareActions a{color:white;background:linear-gradient(90deg,#7047ff,#2f7cff)}.debeShareActions button{background:white;color:#111827;border:1px solid #dfe3eb}@media(max-width:850px){.debeSeoGrid{grid-template-columns:1fr}}
</style>
'''
        txt=txt.replace('</head>',meta+'</head>')

        seo='''<section class="debeSeo" id="como-funciona-debe"><h2>Como usar o DEBE</h2><p>O DEBE tem duas formas de ajudar: pesquisar carros no mercado e analisar um anúncio específico. Usa o Search para descobrir oportunidades e a Análise para validar um carro que já tens em vista.</p><div class="debeSeoGrid"><div><h3>1. Pesquise carros</h3><p>Use o DEBE Search para encontrar stock oficial, concessionários e marketplaces num só local. Filtre por marca, modelo e versão para descobrir opções relevantes mais depressa.</p></div><div><h3>2. Analise um anúncio</h3><p>Se já encontrou um carro, cole o link do anúncio na área de análise. O DEBE extrai os dados principais e prepara a avaliação do negócio.</p></div><div><h3>3. Compare e decida melhor</h3><p>Veja riscos, verificações recomendadas e anúncios comparáveis para perceber se o preço, a quilometragem e o contexto do carro fazem sentido.</p></div></div><p class="muted"><strong>Nota:</strong> o DEBE é uma ferramenta de apoio à decisão e não substitui inspeção mecânica, diagnóstico eletrónico ou validação documental.</p></section>'''
        txt=txt.replace('<footer class="footer">',seo+'<footer class="footer">')

        js='''<script id="debe-growth-script">(function(){
function event(name,source){try{var body=JSON.stringify({event:name,session:(sessionStorage.getItem('debe_beta_session')||'anonymous'),source:source||''});fetch('/api/event',{method:'POST',headers:{'Content-Type':'application/json'},body:body,keepalive:true}).catch(function(){})}catch(e){}}
function shareUrl(source){return location.origin+'/?utm_source='+encodeURIComponent(source)+'&utm_medium=referral&utm_campaign=beta_share'}
function ensureShare(){var report=document.getElementById('report');if(!report||report.classList.contains('hidden')||document.getElementById('debeShare'))return;var box=document.createElement('div');box.id='debeShare';box.className='debeShare';box.innerHTML='<b>Partilhe o DEBE com alguém que esteja a procurar um carro</b><p class="muted">A versão beta é gratuita. Mais utilizações ajudam a perceber se este serviço deve continuar a evoluir.</p><div class="debeShareActions"><a id="debeWhats" target="_blank" rel="noopener">Partilhar por WhatsApp</a><button type="button" id="debeCopy">Copiar ligação</button></div>';var anchor=report.querySelector('div[style*="text-align:right"]');if(anchor)anchor.parentNode.insertBefore(box,anchor);else report.appendChild(box);var wa=document.getElementById('debeWhats');wa.href='https://wa.me/?text='+encodeURIComponent('Experimente o DEBE para analisar um anúncio de carro usado: '+shareUrl('whatsapp_share'));wa.onclick=function(){event('share_click','whatsapp')};document.getElementById('debeCopy').onclick=function(){var u=shareUrl('copy_share');if(navigator.clipboard){navigator.clipboard.writeText(u).catch(function(){})}event('share_click','copy');this.textContent='Ligação copiada ✓'};}
function watch(){ensureShare();var r=document.getElementById('report');if(r)new MutationObserver(ensureShare).observe(r,{attributes:true,attributeFilter:['class']})}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',watch);else watch();
})();</script>'''
        txt=txt.replace('</body>',js+'</body>')
        open(path,'w',encoding='utf-8').write(txt)
        print('DEBE growth: SEO and referral layer applied',flush=True)
    except Exception as e:
        print('DEBE growth patch failed:',e,flush=True)


def install(appmod):
    app=appmod.app
    if 'debe_robots' not in app.view_functions:
        app.add_url_rule('/robots.txt',endpoint='debe_robots',view_func=lambda:Response('User-agent: *\nAllow: /\nSitemap: '+BASE_URL+'/sitemap.xml\n',mimetype='text/plain'))
    if 'debe_sitemap' not in app.view_functions:
        xml='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>'+BASE_URL+'/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url></urlset>'
        app.add_url_rule('/sitemap.xml',endpoint='debe_sitemap',view_func=lambda:Response(xml,mimetype='application/xml'))
    if 'debe_indexnow_key' not in app.view_functions:
        app.add_url_rule('/'+INDEXNOW_KEY+'.txt',endpoint='debe_indexnow_key',view_func=lambda:Response(INDEXNOW_KEY,mimetype='text/plain'))
