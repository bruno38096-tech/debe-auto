(function () {
  'use strict';
  let generation = 0;
  const pending = new Set();
  function cancelPending() {
    generation++;
    pending.forEach(controller => controller.abort());
    pending.clear();
  }
  function safeUrl(value) {
    try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : ''; }
    catch (_) { return ''; }
  }

  function requestJson(url, timeoutMs) {
    const controller = new AbortController();
    pending.add(controller);
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    return fetch(url, {signal: controller.signal})
      .then(async response => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.ok === false) {
          throw new Error(data.error || 'Resposta inválida do servidor');
        }
        return data;
      })
      .finally(() => { clearTimeout(timer); pending.delete(controller); });
  }

  function bullets(values, emptyText) {
    return (values || []).map(value => '• ' + esc(value)).join('<br>') ||
      '<span class="muted">' + esc(emptyText) + '</span>';
  }

  function renderResearch(data) {
    $('strengths').innerHTML = bullets(data.strengths, 'Não foi possível confirmar pontos fortes específicos.');
    $('issues').innerHTML = bullets(data.issues, 'Não foram encontrados problemas recorrentes com evidência suficiente.');
    $('checks').innerHTML = (data.checks || []).map(item =>
      '<p><b>' + esc(item.title) + '</b><br>' + esc(item.detail) + '</p>'
    ).join('') || '<span class="muted">Faz uma inspeção independente e confirma o VIN.</span>';
    const sources = (data.sources || []).filter(item => safeUrl(item.url));
    if (sources.length) $('checks').innerHTML += '<p><b>Fontes da pesquisa</b></p>' + sources.map(item =>
      '<p><a target="_blank" rel="noopener" href="' + esc(safeUrl(item.url)) + '">' + esc(item.title || 'Consultar fonte') + '</a></p>'
    ).join('');
  }

  function researchFailure(error) {
    const message = error && error.name === 'AbortError'
      ? 'A pesquisa demorou mais do que o esperado. Tenta novamente.'
      : 'Não foi possível concluir a pesquisa agora. Tenta novamente.';
    $('strengths').innerHTML = '<span class="muted">' + message + '</span>';
    $('issues').innerHTML = '<span class="muted">' + message + '</span>';
    $('checks').innerHTML = '<p><b>Inspeção e VIN</b><br>Confirma o VIN e faz uma inspeção independente antes da compra.</p>';
  }

  function dealCard(deal) {
    return '<div class="deal"><b>' + esc(deal.title) + '</b>' +
      '<span class="muted">' + esc([deal.year, deal.km, deal.fuel, deal.source].filter(Boolean).join(' · ')) + '</span>' +
      '<h3>' + esc(deal.price) + '</h3><span>Score ' + esc(deal.score) + '</span>' +
      '<div class="dealWhy">' + esc(deal.why || '') + '</div>' +
      '<a target="_blank" rel="noopener" href="' + esc(safeUrl(deal.url)) + '">Ver anúncio →</a></div>';
  }

  function renderDeals(data) {
    const deals = (data.deals || []).filter(deal => safeUrl(deal.url));
    const modelDeals = deals.filter(deal => deal.group === 'model').slice(0, 2);
    const budgetDeals = deals.filter(deal => deal.group === 'budget').slice(0, 2);
    let html = '';
    if (modelDeals.length) html += '<div class="dealGroupTitle">Mesmo modelo</div>' + modelDeals.map(dealCard).join('');
    if (budgetDeals.length) html += '<div class="dealGroupTitle budget">Mesmo orçamento</div>' + budgetDeals.map(dealCard).join('');
    $('deals').innerHTML = html || '<div class="muted">Ainda não encontrei comparáveis suficientes.</div>';
    if (deals.length < 4) $('deals').innerHTML += (data.search_links || []).filter(item => safeUrl(item.url)).map(item =>
      '<p><a target="_blank" rel="noopener" href="' + esc(safeUrl(item.url)) + '">' + esc(item.title) + ' →</a><br><small>Pesquisa no marketplace; não é um anúncio validado.</small></p>'
    ).join('');
  }

  function resetApp() {
    cancelPending();
    currentUrl = '';
    listing = {};
    $('url').value = '';
    ['model', 'year', 'price', 'km', 'fuel', 'vin'].forEach(id => { $(id).value = ''; });
    $('confirm').classList.add('hidden');
    $('report').classList.add('hidden');
    $('score').textContent = '--';
    $('rating').textContent = 'A analisar';
    $('scoreText').textContent = '';
    ['strengths', 'issues', 'checks', 'deals'].forEach(id => { $(id).innerHTML = ''; });
    setListingPhoto('');
    setBusy('listing', false);
    setBusy('report', false);
    $('start').scrollIntoView({behavior: 'smooth', block: 'center'});
    setTimeout(() => $('url').focus(), 350);
  }

  const resetButtons = document.querySelectorAll('.reset');
  resetButtons.forEach((button, index) => {
    button.onclick = resetApp;
    button.textContent = index === resetButtons.length - 1 ? 'Verificar novo anúncio →' : '↻ Verificar novo anúncio';
  });

  $('analyse').onclick = async () => {
    const url = safeUrl($('url').value.trim());
    if (!url) { alert('Introduz um link válido do anúncio.'); return; }
    cancelPending();
    const run = generation;
    currentUrl = url;
    $('report').classList.add('hidden');
    $('confirm').classList.add('hidden');
    setBusy('listing', true);
    try {
      const data = await requestJson('/api/listing?url=' + encodeURIComponent(url), 45000);
      if (run !== generation) return;
      listing = data;
      ['model', 'year', 'price', 'km', 'fuel', 'vin'].forEach(id => { $(id).value = data[id === 'model' ? 'title' : id] || ''; });
      $('confirm').classList.remove('hidden');
      $('confirm').scrollIntoView({behavior: 'smooth'});
    } catch (error) {
      if (run === generation) alert('Não foi possível ler este anúncio. Tenta novamente.');
    } finally { if (run === generation) setBusy('listing', false); }
  };

  $('reportBtn').onclick = async () => {
    cancelPending();
    const run = generation;
    const model = $('model').value.trim();
    const year = $('year').value.trim();
    const price = $('price').value.trim();
    const km = $('km').value.trim();
    const fuel = $('fuel').value.trim();
    const vin = $('vin').value.trim();
    const y = parseInt(year, 10) || 0;
    const k = parseInt(km.replace(/\D/g, ''), 10) || 0;
    const age = Math.max(0, new Date().getFullYear() - y);
    const annual = k / Math.max(1, age || 1);
    const preliminaryScore = (!y || !k) ? 64 : Math.max(35, Math.min(95, Math.round(
      Math.max(35, 98 - age * 4.7) * 0.52 + Math.max(35, 98 - (annual / 1000) * 2.15) * 0.43 +
      (vin.length === 17 ? 5 : 0) - Math.min(12, (k / 100000) * 6)
    )));

    setBusy('report', true);
    $('score').textContent = preliminaryScore;
    $('rating').textContent = preliminaryScore >= 80 ? 'Bom candidato' : preliminaryScore >= 65 ? 'Interessante, validar' : preliminaryScore >= 50 ? 'Cautela' : 'Risco elevado';
    $('scoreText').textContent = 'Score preliminar baseado no ano, quilometragem, utilização anual e dados disponíveis no anúncio.';
    $('carTitle').textContent = model + ' — ' + year;
    $('carMeta').textContent = [price, km, fuel, listing.engine].filter(Boolean).join(' · ');
    setListingPhoto(currentUrl.toLowerCase().includes('olx.pt') ? '' : (listing.image || ''));
    $('report').classList.remove('hidden');
    $('strengths').innerHTML = '<span class="muted">A pesquisar…</span>';
    $('issues').innerHTML = '<span class="muted">A pesquisar…</span>';
    $('checks').innerHTML = '<span class="muted">A pesquisar…</span>';
    $('deals').innerHTML = '<span class="muted">A procurar negócios comparáveis…</span>';
    $('report').scrollIntoView({behavior: 'smooth'});

    const researchUrl = '/api/research?model=' + encodeURIComponent(model) + '&engine=' + encodeURIComponent(listing.engine || '') +
      '&year=' + encodeURIComponent(year) + '&fuel=' + encodeURIComponent(fuel);
    const marketUrl = '/api/comparables?model=' + encodeURIComponent(model) + '&fuel=' + encodeURIComponent(fuel) +
      '&price=' + encodeURIComponent(price) + '&year=' + encodeURIComponent(year) + '&url=' + encodeURIComponent(currentUrl);

    // Render independently: a slow marketplace search must never leave the
    // strengths and issues stuck on "A pesquisar…".
    const researchTask = requestJson(researchUrl, 90000).then(data => { if (run === generation) renderResearch(data); }).catch(error => { if (run === generation) researchFailure(error); });
    const marketTask = requestJson(marketUrl, 90000).then(data => { if (run === generation) renderDeals(data); }).catch(() => {
      if (run !== generation) return;
      $('deals').innerHTML = '<div class="muted">Não foi possível pesquisar comparáveis agora. Tenta novamente dentro de instantes.</div>';
    });
    await Promise.allSettled([researchTask, marketTask]);
    if (run === generation) setBusy('report', false);
  };
})();
