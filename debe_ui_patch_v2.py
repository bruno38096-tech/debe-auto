"""Small runtime UI patch for DEBE beta market comparison groups."""

def patch_market_ui(path='index.html'):
    marker='debe-market-groups-v2'
    try:
        txt=open(path,encoding='utf-8').read()
        if marker in txt:return

        # Every confirmation field must remain identifiable when automatic
        # extraction fails. Required empty fields are highlighted; VIN remains
        # explicitly optional.
        placeholders={
            '<input id="model">':'<input id="model" placeholder="Modelo / versão">',
            '<input id="year">':'<input id="year" placeholder="Ano">',
            '<input id="price">':'<input id="price" placeholder="Preço">',
            '<input id="km">':'<input id="km" placeholder="Quilometragem">',
            '<input id="fuel">':'<input id="fuel" placeholder="Combustível">',
            '<input id="vin" placeholder="VIN (opcional)">':'<input id="vin" placeholder="VIN (opcional)">'
        }
        for old,new in placeholders.items():txt=txt.replace(old,new)
        grid_end='<input id="vin" placeholder="VIN (opcional)"></div>'
        if grid_end in txt:
            txt=txt.replace(grid_end,grid_end+'<div class="missingFieldHint">Se algum dado não for detetado automaticamente, o respetivo campo fica identificado para preenchimento manual.</div>',1)

        txt=txt.replace('Mesmo modelo e mesma família de motorização primeiro.','Duas alternativas do mesmo modelo e duas alternativas na mesma faixa de preço.')
        old="fetch('/api/comparables?model='+encodeURIComponent(model)+'&fuel='+encodeURIComponent(fuel)+'&url='+encodeURIComponent(currentUrl))"
        new="fetch('/api/comparables?model='+encodeURIComponent(model)+'&fuel='+encodeURIComponent(fuel)+'&price='+encodeURIComponent(price)+'&year='+encodeURIComponent(year)+'&url='+encodeURIComponent(currentUrl))"
        txt=txt.replace(old,new)
        old_render="let deals=cd.deals||[];$('deals').innerHTML=deals.length?deals.map(d=>'<div class=\"deal\"><b>'+esc(d.title)+'</b><span class=\"muted\">'+esc([d.year,d.km,d.fuel,d.source].filter(Boolean).join(' · '))+'</span><h3>'+esc(d.price)+'</h3><span>Score '+esc(d.score)+'</span><br><a target=\"_blank\" rel=\"noopener\" href=\"'+esc(d.url)+'\">Ver anúncio →</a></div>').join(''):'<div class=\"muted\">Ainda não encontrei comparáveis suficientes.</div>'"
        new_render="let deals=cd.deals||[],modelDeals=deals.filter(d=>d.group==='model').slice(0,2),budgetDeals=deals.filter(d=>d.group==='budget').slice(0,2);function dealCard(d){return '<div class=\"deal\"><b>'+esc(d.title)+'</b><span class=\"muted\">'+esc([d.year,d.km,d.fuel,d.source].filter(Boolean).join(' · '))+'</span><h3>'+esc(d.price)+'</h3><span>Score '+esc(d.score)+'</span><div class=\"dealWhy\">'+esc(d.why||'')+'</div><a target=\"_blank\" rel=\"noopener\" href=\"'+esc(d.url)+'\">Ver anúncio →</a></div>'}let marketHtml='';if(modelDeals.length)marketHtml+='<div class=\"dealGroupTitle\">Mesmo modelo</div>'+modelDeals.map(dealCard).join('');if(budgetDeals.length)marketHtml+='<div class=\"dealGroupTitle budget\">Mesmo orçamento</div>'+budgetDeals.map(dealCard).join('');$('deals').innerHTML=marketHtml||'<div class=\"muted\">Ainda não foram encontrados comparáveis suficientes.</div>'"
        txt=txt.replace(old_render,new_render)
        css='''<style id="debe-market-groups-v2">.dealGroupTitle{grid-column:1/-1;font-size:12px;font-weight:900;color:#4b3cc4;text-transform:uppercase;letter-spacing:.07em;margin-top:4px}.dealGroupTitle.budget{margin-top:10px;color:#9a4f24}.dealWhy{font-size:11px;color:#747b88;margin:7px 0 6px}.deal h3{margin:12px 0 8px}.missingFieldHint{grid-column:1/-1;font-size:11px;color:#737886;margin:-2px 2px 2px}.grid input:not(#vin):placeholder-shown{border-color:#e9a15b;background:#fffaf4}.grid input:not(#vin):placeholder-shown::placeholder{color:#9a5b20;font-weight:700}</style>'''
        txt=txt.replace('</head>',css+'</head>')
        open(path,'w',encoding='utf-8').write(txt)
        print('DEBE runtime: market groups and confirmation field labels injected',flush=True)
    except Exception as e:
        print('DEBE market UI patch failed:',e,flush=True)
