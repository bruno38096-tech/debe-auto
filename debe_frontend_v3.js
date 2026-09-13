(function () {
  'use strict';
  let generation = 0;
  const pending = new Set();
  const fieldLabels = {model:'Modelo / versão', year:'Ano', price:'Preço', km:'Quilometragem', fuel:'Combustível', vin:'VIN (opcional)'};

  function cancelPending() {
    generation++;
    pending.forEach(controller => controller.abort());
    pending.clear();
  }
  function safeUrl(value) {
    try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : ''; }
    catch (_) { return ''; }
  }
  function marketplaceFrom(value) {
    try { return new URL(value).hostname.replace(/^www\./, '').slice(0, 80); }
    catch (_) { return ''; }
  }
  function sessionId() {
    try {
      let id = sessionStorage.getItem('debe_beta_session');
      if (!id) {
        id = (typeof crypto !== 'undefined' && crypto.randomUUID) ? crypto.randomUUID() : 's-' + Date.now() + '-' + Math.random().toString(36).slice(2, 10);
        sessionStorage.setItem('debe_beta_session', id);
      }
      return id;
    } catch (_) { return 'anonymous'; }
  }
  function campaignData() {
    try {
      const q = new URLSearchParams(location.search);
      return {utm_source:q.get('utm_source') || '', utm_medium:q.get('utm_medium') || '', utm_campaign:q.get('utm_campaign') || ''};
    } catch (_) { return {}; }
  }
  function sendEvent(event, extra) {
    if (typeof navigator === 'undefined') return;
    try {
      const payload = Object.assign({event, session:sessionId()}, extra || {});
      const body = JSON.stringify(payload);
      if (navigator.sendBeacon && typeof Blob !== 'undefined') {
        navigator.sendBeacon('/api/event', new Blob([body], {type:'application/json'}));
      } else if (typeof fetch === 'function') {
        fetch('/api/event', {method:'POST', headers:{'Content-Type':'application/json'}, body, keepalive:true}).catch(() => {});
      }
    } catch (_) {}
  }
  function markFieldLabels(data) {
    Object.keys(fieldLabels).forEach(id => {
      const el = $(id);
      if (!el) return;
      const missing = id !== 'vin' && !(data[id === 'model' ? 'title' : id] || '').toString().trim();
      el.placeholder = fieldLabels[id] + (missing ? ' — preencher' : '');
      el.title = fieldLabels[id];
    });
  }

  function requestJson(url, timeoutMs) {
    const controller = new AbortController();
    pending.add(controller);
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    return fetch(url, {signal: controller.signal})
      .then(async response => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.ok === false) throw new Error(data.error || 'Resposta inválida do servidor');
        return data;
      })
      .finally(() => { clearTimeout(timer); pending.delete(controller); });
  }

  function bullets(values, emptyText) {
    return (values || []).map(value => '• ' + esc(value)).join('<br>') || '<span class="muted">' + esc(emptyText) + '</span>';
  }
  function renderResearch(data) {
    $('strengths').innerHTML = bullets(data.strengths, 'Não foi possível confirmar pontos fortes específicos.');
    $('issues').innerHTML = bullets(data.issues, 'Não foram encontrados problemas recorrentes com evidência suficiente.');
    $('checks').innerHTML = (data.checks || []).map(item => '<p><b>' + esc(item.title) + '</b><br>' + esc(item.detail) + '</p>').join('') || '<span class="muted">Recomenda-se uma inspeção independente e a confirmação do VIN.</span>';
    const sources = (data.sources || []).filter(item => safeUrl(item.url));
    if (sources.length) $('checks').innerHTML += '<p><b>Fontes da pesquisa</b></p>' + sources.map(item => '<p><a target="_blank" rel="noopener" href="' + esc(safeUrl(item.url)) + '">' + esc(item.title || 'Consultar fonte') + '</a></p>').join('');
  }
  function researchFailure(error) {
    const message = error && error.name === 'AbortError' ? 'A pesquisa demorou mais do que o esperado. Recomenda-se repetir a tentativa.' : 'Não foi possível concluir a pesquisa neste momento. Recomenda-se repetir a tentativa.';
    $('strengths').innerHTML = '<span class="muted">' + message + '</span>';
    $('issues').innerHTML = '<span class="muted">' + message + '</span>';
    $('checks').innerHTML = '<p><b>Inspeção e VIN</b><br>Recomenda-se confirmar o VIN e realizar uma inspeção independente antes da compra.</p>';
  }
  function dealCard(deal) {
    return '<div class="deal"><b>' + esc(deal.title) + '</b>' +
      '<span class="muted">' + esc([deal.year, deal.km, deal.fuel, deal.source].filter(Boolean).join(' · ')) + '</span>' +
      '<h3>' + esc(deal.price) + '</h3><span>Score ' + esc(deal.score) + '</span>' +
      '<div class="dealWhy">' + esc(deal.why || '') + '</div>' +
      '<a data-debe-event="comparable_click" data-source="' + esc(deal.source || '') + '" data-group="' + esc(deal.group || '') + '" target="_blank" rel="noopener" href="' + esc(safeUrl(deal.url)) + '">Ver anúncio →</a></div>';
  }
  function renderDeals(data) {
    const deals = (data.deals || []).filter(deal => safeUrl(deal.url));
    const modelDeals = deals.filter(deal => deal.group === 'model').slice(0, 2);
    const budgetDeals = deals.filter(deal => deal.group === 'budget').slice(0, 2);
    let html = '';
    if (modelDeals.length) html += '<div class="dealGroupTitle">Mesmo modelo</div>' + modelDeals.map(dealCard).join('');
    if (budgetDeals.length) html += '<div class="dealGroupTitle budget">Mesmo orçamento</div>' + budgetDeals.map(dealCard).join('');
    $('deals').innerHTML = html || '<div class="muted">Ainda não foram encontrados comparáveis suficientes.</div>';
    if (deals.length < 4) $('deals').innerHTML += (data.search_links || []).filter(item => safeUrl(item.url)).map(item => '<p><a target="_blank" rel="noopener" href="' + esc(safeUrl(item.url)) + '">' + esc(item.title) + ' →</a><br><small>Pesquisa no marketplace; não corresponde a um anúncio validado.</small></p>').join('');
    return deals.length;
  }
  function renderFeedback() {
    if (typeof document !== 'undefined' && document.getElementById && document.getElementById('debeFeedback')) return;
    $('deals').innerHTML += '<div id="debeFeedback" style="grid-column:1/-1;margin-top:16px;padding:18px;border:1px solid #e3e6ef;border-radius:14px;background:#fafaff">' +
      '<b>Ajude a validar o DEBE</b><p style="margin:8px 0">Este relatório foi útil para avaliar o anúncio?</p>' +
      '<div style="display:flex;gap:8px;flex-wrap:wrap"><button type="button" data-debe-feedback="useful" data-value="sim">Sim</button><button type="button" class="secondary" data-debe-feedback="useful" data-value="parcial">Em parte</button><button type="button" class="secondary" data-debe-feedback="useful" data-value="nao">Não</button></div>' +
      '<p style="margin:16px 0 8px">Voltaria a utilizar o DEBE para analisar outro carro?</p>' +
      '<div style="display:flex;gap:8px;flex-wrap:wrap"><button type="button" data-debe-feedback="reuse" data-value="sim">Sim</button><button type="button" class="secondary" data-debe-feedback="reuse" data-value="nao">Não</button></div>' +
      '<small class="muted" style="display:block;margin-top:12px">Feedback anónimo. Não são pedidos dados pessoais.</small></div>';
  }

  function resetApp() {
    cancelPending(); currentUrl = ''; listing = {}; $('url').value = '';
    ['model', 'year', 'price', 'km', 'fuel', 'vin'].forEach(id => { $(id).value = ''; $(id).placeholder = fieldLabels[id]; });
    $('confirm').classList.add('hidden'); $('report').classList.add('hidden'); $('score').textContent = '--'; $('rating').textContent = 'A analisar'; $('scoreText').textContent = '';
    ['strengths', 'issues', 'checks', 'deals'].forEach(id => { $(id).innerHTML = ''; });
    setListingPhoto(''); setBusy('listing', false); setBusy('report', false); $('start').scrollIntoView({behavior: 'smooth', block: 'center'}); setTimeout(() => $('url').focus(), 350);
  }

  Object.keys(fieldLabels).forEach(id => { if ($(id)) $(id).placeholder = fieldLabels[id]; });
  const resetButtons = document.querySelectorAll('.reset');
  resetButtons.forEach((button, index) => { button.onclick = resetApp; button.textContent = index === resetButtons.length - 1 ? 'Verificar novo anúncio →' : '↻ Verificar novo anúncio'; });

  if (typeof document !== 'undefined' && document.addEventListener) {
    document.addEventListener('click', event => {
      const target = event.target && event.target.closest ? event.target.closest('[data-debe-event],[data-debe-feedback]') : null;
      if (!target) return;
      if (target.getAttribute('data-debe-event') === 'comparable_click') {
        sendEvent('comparable_click', {source:target.getAttribute('data-source') || '', group:target.getAttribute('data-group') || '', model:$('model').value.trim(), year:$('year').value.trim()});
      }
      const feedback = target.getAttribute('data-debe-feedback');
      if (feedback) {
        const value = target.getAttribute('data-value') || '';
        sendEvent(feedback === 'useful' ? 'feedback_useful' : 'feedback_reuse', {value, model:$('model').value.trim(), year:$('year').value.trim()});
        target.parentElement.querySelectorAll('button').forEach(button => { button.disabled = true; });
        target.disabled = false; target.textContent = target.textContent + ' ✓';
      }
    });
  }

  sendEvent('page_view', campaignData());

  $('analyse').onclick = async () => {
    const url = safeUrl($('url').value.trim());
    if (!url) { alert('Deve ser introduzido um link válido do anúncio.'); return; }
    cancelPending(); const run = generation; currentUrl = url; $('report').classList.add('hidden'); $('confirm').classList.add('hidden'); setBusy('listing', true);
    sendEvent('listing_submitted', Object.assign({marketplace:marketplaceFrom(url)}, campaignData()));
    try {
      const data = await requestJson('/api/listing?url=' + encodeURIComponent(url), 45000);
      if (run !== generation) return;
      listing = data;
      ['model', 'year', 'price', 'km', 'fuel', 'vin'].forEach(id => { $(id).value = data[id === 'model' ? 'title' : id] || ''; });
      markFieldLabels(data);
      const missing = ['model','year','price','km','fuel'].filter(id => !(data[id === 'model' ? 'title' : id] || '').toString().trim());
      sendEvent('listing_loaded', {marketplace:marketplaceFrom(url), model:data.title || '', year:data.year || '', missing_fields:missing});
      $('confirm').classList.remove('hidden'); $('confirm').scrollIntoView({behavior:'smooth'});
    } catch (error) {
      sendEvent('listing_failed', {marketplace:marketplaceFrom(url)});
      if (run === generation) alert('Não foi possível ler este anúncio. Recomenda-se repetir a tentativa.');
    } finally { if (run === generation) setBusy('listing', false); }
  };

  $('reportBtn').onclick = async () => {
    cancelPending(); const run = generation;
    const model = $('model').value.trim(), year = $('year').value.trim(), price = $('price').value.trim(), km = $('km').value.trim(), fuel = $('fuel').value.trim(), vin = $('vin').value.trim();
    const y = parseInt(year, 10) || 0, k = parseInt(km.replace(/\D/g, ''), 10) || 0, age = Math.max(0, new Date().getFullYear() - y), annual = k / Math.max(1, age || 1);
    const ageScore = Math.max(25, Math.min(98, 100 - age * 2.4)), annualScore = Math.max(25, Math.min(98, 100 - (annual / 1000) * 2.2)), mileageScore = Math.max(20, Math.min(98, 100 - (k / 1000) * 0.18));
    const preliminaryScore = (!y || !k) ? (vin.length === 17 ? 68 : 64) : Math.max(25, Math.min(95, Math.round(ageScore * 0.35 + annualScore * 0.35 + mileageScore * 0.25 + (vin.length === 17 ? 5 : 0))));

    sendEvent('report_started', {marketplace:marketplaceFrom(currentUrl), model, year});
    setBusy('report', true); $('score').textContent = preliminaryScore;
    $('rating').textContent = preliminaryScore >= 80 ? 'Bom candidato' : preliminaryScore >= 65 ? 'Interessante, validar' : preliminaryScore >= 50 ? 'Cautela' : 'Risco elevado';
    $('scoreText').textContent = 'Score preliminar baseado no ano, quilometragem, utilização anual e dados disponíveis no anúncio.';
    $('carTitle').textContent = model + ' — ' + year; $('carMeta').textContent = [price, km, fuel, listing.engine].filter(Boolean).join(' · ');
    setListingPhoto(currentUrl.toLowerCase().includes('olx.pt') ? '' : (listing.image || '')); $('report').classList.remove('hidden');
    $('strengths').innerHTML = '<span class="muted">A pesquisar…</span>'; $('issues').innerHTML = '<span class="muted">A pesquisar…</span>'; $('checks').innerHTML = '<span class="muted">A pesquisar…</span>'; $('deals').innerHTML = '<span class="muted">A procurar negócios comparáveis…</span>'; $('report').scrollIntoView({behavior:'smooth'});

    const researchUrl = '/api/research?model=' + encodeURIComponent(model) + '&engine=' + encodeURIComponent(listing.engine || '') + '&year=' + encodeURIComponent(year) + '&fuel=' + encodeURIComponent(fuel);
    const marketUrl = '/api/comparables?model=' + encodeURIComponent(model) + '&fuel=' + encodeURIComponent(fuel) + '&price=' + encodeURIComponent(price) + '&year=' + encodeURIComponent(year) + '&url=' + encodeURIComponent(currentUrl);
    let researchOk = false, marketCount = 0;
    const researchTask = requestJson(researchUrl, 90000).then(data => { researchOk = true; if (run === generation) renderResearch(data); }).catch(error => { if (run === generation) researchFailure(error); });
    const marketTask = requestJson(marketUrl, 90000).then(data => { marketCount = (data.deals || []).length; if (run === generation) renderDeals(data); }).catch(() => { if (run === generation) $('deals').innerHTML = '<div class="muted">Não foi possível pesquisar comparáveis neste momento. Recomenda-se repetir a tentativa mais tarde.</div>'; });
    await Promise.allSettled([researchTask, marketTask]);
    if (run === generation) {
      renderFeedback(); setBusy('report', false);
      sendEvent('report_completed', {marketplace:marketplaceFrom(currentUrl), model, year, score:preliminaryScore, research_ok:researchOk, comparables:marketCount});
    }
  };
})();