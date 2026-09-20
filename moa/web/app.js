'use strict';
const $ = id => document.getElementById(id);
let config, observation, observationRaw = null, lastResult = null, running = false;
function node(tag, text, className) { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (className) el.className = className; return el; }
function error(message) { $('error').textContent = message || ''; $('error').hidden = !message; }
async function api(path, options) { const r = await fetch(path, options); const data = await r.json(); if (!r.ok) throw new Error(data.error || 'Request failed'); return data; }
function freshness() { if (!observation) return; const age = (Date.now() - Date.parse(observation.captured_at)) / 1000; const fresh = Number.isFinite(age) && age >= -2 && age <= 60; $('freshness').textContent = fresh ? 'Captured ' + Math.max(0, Math.floor(age)) + 's ago' : 'Expired / invalid'; $('freshness').className = 'badge ' + (fresh ? 'good' : 'warn'); if (!fresh && lastResult?.status === 'advisory') { $('result-status').textContent = 'Recorded / expired'; $('result-status').className = 'badge warn'; } }
function svgNode(tag, attrs, text) { const el = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value); if (text !== undefined) el.textContent = text; return el; }
function renderHistory() {
  const history = observation?.history, tag = $('history-tag').value;
  $('history-chart').replaceChildren();
  if (!history || !Array.isArray(history.samples) || !tag) return;
  const samples = history.samples;
  const usable = samples.filter(s => Number.isFinite(s.elapsed_s) && Number.isFinite(s.values?.[tag]) && s.quality?.[tag] === 'good');
  const times = samples.map(s => s.elapsed_s).filter(Number.isFinite);
  if (!usable.length || !times.length) { $('history-note').textContent = 'No reliable samples to plot.'; return; }
  const t0 = Math.min(...times), t1 = Math.max(...times);
  const values = usable.map(s => s.values[tag]);
  const low = Math.min(...values), high = Math.max(...values), padding = Math.max((high - low) * .12, .5);
  const min = low - padding, max = high + padding;
  const x = t => 48 + (t - t0) / (t1 - t0 || 1) * 360;
  const y = v => 20 + (max - v) / (max - min) * 105;
  const unit = (observation.tags || []).find(t => t.id === tag)?.unit || '';
  const chart = svgNode('svg', {viewBox:'0 0 440 160', role:'img', 'aria-label':tag + ' history, ' + low + ' to ' + high + ' ' + unit + ', simulation seconds ' + t0 + ' to ' + t1});
  for (const value of [low, high]) { chart.append(svgNode('line', {x1:48,x2:410,y1:y(value),y2:y(value),stroke:'#2a363b'}), svgNode('text', {x:40,y:y(value)+4,'text-anchor':'end',fill:'#9daeb4','font-size':10},value)); }
  chart.append(svgNode('text',{x:48,y:150,fill:'#9daeb4','font-size':10},t0+' s'),svgNode('text',{x:408,y:150,'text-anchor':'end',fill:'#9daeb4','font-size':10},t1+' s'));
  let segment = [], previous = null, gaps = false;
  function flush() { if (segment.length) chart.append(svgNode('polyline',{points:segment.join(' '),fill:'none',stroke:'#c6ed9a','stroke-width':2})); segment = []; }
  for (const sample of samples) {
    const valid = Number.isFinite(sample.elapsed_s) && Number.isFinite(sample.values?.[tag]) && sample.quality?.[tag] === 'good';
    if (previous && (sample.sequence !== previous.sequence + 1 || sample.elapsed_s - previous.elapsed_s !== history.sample_period_s)) { flush(); gaps = true; }
    if (!valid) { flush(); gaps = true; } else { segment.push(x(sample.elapsed_s)+','+y(sample.values[tag])); chart.append(svgNode('circle',{cx:x(sample.elapsed_s),cy:y(sample.values[tag]),r:2.5,fill:'#c6ed9a'})); }
    previous = sample;
  }
  flush(); $('history-chart').append(chart);
  $('history-span').textContent = samples.length + ' samples / ' + (t1-t0) + ' s';
  $('history-note').textContent = unit + ' · Simulation time. ' + (gaps ? 'Gaps are not interpolated.' : 'Sampled indications, not a continuous measurement.');
}
function renderObservation(data) {
  observation = data; observationRaw = null; lastResult = null;
  $('snapshot-id').textContent = data.snapshot_id || 'Invalid snapshot'; $('profile').textContent = data.profile || 'Unknown';
  $('coverage').textContent = data.alarm_coverage || 'Unknown'; $('raw').textContent = JSON.stringify(data, null, 2);
  $('source-label').textContent = data.source?.model_id?.startsWith('authored-') ? 'AUTHORED DEMONSTRATION / SYNTHETIC' : 'SOURCE REVISION / ' + (data.source?.revision || 'Unknown');
  $('history-panel').hidden = !data.history; $('history-tag').replaceChildren();
  if (data.history) { for (const tag of (data.tags || [])) { const option = node('option', tag.id); option.value = tag.id; $('history-tag').append(option); } renderHistory(); }
  $('tags').replaceChildren();
  for (const tag of (Array.isArray(data.tags) ? data.tags : [])) {
    const tr = node('tr'); tr.append(node('td', tag.id));
    const value = node('td', String(tag.value)); value.append(node('small', tag.unit)); tr.append(value);
    const quality = node('td'); quality.append(node('span', tag.quality, 'quality' + (tag.quality === 'good' ? '' : ' bad'))); tr.append(quality); $('tags').append(tr);
  }
  $('alarms').replaceChildren();
  for (const alarm of (Array.isArray(data.alarms) ? data.alarms : [])) { const el = node('div', alarm.tag + ' / ' + alarm.condition, 'alarm'); el.append(node('span', alarm.priority + ' · ' + alarm.state)); $('alarms').append(el); }
  if (!data.alarms?.length) $('alarms').append(node('p', 'No alarm records in this observation.', 'muted'));
  $('result-status').textContent = 'Ready'; $('result-status').className = 'badge';
  $('result').replaceChildren(); const empty = node('div', undefined, 'empty'); empty.append(node('div', '◎', 'empty-icon'), node('h3', 'Observation ready.'), node('p', 'Assess this snapshot to inspect supported findings, review checks, and their evidence.'), node('span', 'Assessment never executes a control action.')); $('result').append(empty);
  $('receipt-details').hidden = true; freshness();
}
async function loadScenario() { error(); try { renderObservation(await api('/api/scenario?name=' + encodeURIComponent($('scenario').value))); } catch (e) { error(e.message); } }
function lock(state) { running = state; for (const id of ['assess', 'refresh', 'scenario', 'import']) $(id).disabled = state; $('assess').textContent = state ? 'Assessing…' : 'Assess observation ↗'; }
$('scenario').addEventListener('change', loadScenario); $('refresh').addEventListener('click', loadScenario);
$('history-tag').addEventListener('change', renderHistory);
$('import').addEventListener('change', async event => {
  const file = event.target.files[0]; if (!file || running) return; error();
  try { if (file.size > 262144) throw new Error('Observation exceeds 256 KiB.'); const raw = await file.text(); const data = JSON.parse(raw); if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Expected an observation object.'); renderObservation(data); observationRaw = raw; } catch (e) { error(e.message); } finally { event.target.value = ''; }
});
$('assess').addEventListener('click', async () => {
  if (!observation || running) return; lock(true); error();
  try {
    const result = await api('/api/assess', {method:'POST', headers:{'Content-Type':'application/json','X-MOA-Token':config.token}, body:JSON.stringify({observation: observationRaw ?? observation})});
    lastResult = result;
    const abstain = result.status === 'abstain', limited = result.findings.some(f => f.id === 'history_quality_gap'); $('result-status').textContent = abstain ? 'Withheld' : limited ? 'Limited' : 'Supported'; $('result-status').className = 'badge ' + (abstain || limited ? 'warn' : 'good');
    const body = node('div', undefined, 'result-body'); body.append(node('p', result.summary, 'outcome'));
    if (abstain) { body.append(node('p', 'Reason: ' + result.reason, 'muted'), node('p', 'Resolve the evidence or provider issue, capture a fresh observation, and reassess.', 'muted')); }
    for (const finding of result.findings) { const card = node('div', undefined, 'finding'); card.append(node('span', finding.id.replaceAll('_', ' ').toUpperCase(), 'label'), node('p', finding.text)); body.append(card); }
    if (result.checks.length) { body.append(node('p', 'REVIEW CHECKS / NO EXECUTION', 'label')); const ul = node('ul', undefined, 'checks'); for (const check of result.checks) ul.append(node('li', check.text)); body.append(ul); }
    const citations = node('div', undefined, 'citations'); for (const item of result.evidence) citations.append(node('span', item.ref, 'citation')); body.append(citations);
    body.append(node('div', 'Run ' + result.run_id + ' · ' + result.elapsed_ms + ' ms\nReceipt #' + result.receipt.seq + ' · ' + result.receipt.hash, 'result-receipt')); $('result').replaceChildren(body);
    $('receipt-note').textContent = 'Recorded through event ' + result.receipt.seq + '. Hash links detect edits; retain an external anchor to detect a replaced history.';
    $('receipt').textContent = JSON.stringify(result, null, 2); $('receipt-details').hidden = false;
  } catch (e) { error(e.message); $('result-status').textContent = 'Unavailable'; $('result-status').className = 'badge warn'; } finally { lock(false); }
});
$('export').addEventListener('click', async () => {
  error(); try { const data = await api('/api/evidence'); const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type:'application/json'})); const a = node('a'); a.href = url; a.download = 'moa-evidence.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); } catch (e) { error(e.message); }
});
(async () => { lock(true); try { config = await api('/api/config'); $('provider').textContent = config.provider; for (const [id, label] of Object.entries(config.scenarios)) { const option = node('option', label); option.value = id; $('scenario').append(option); } $('scenario').value = 'cooling'; await loadScenario(); } catch (e) { error(e.message); } finally { lock(false); } })();
setInterval(freshness, 1000);
