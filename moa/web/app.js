'use strict';
const $ = id => document.getElementById(id);
let config, observation, observationRaw = null, running = false;
function node(tag, text, className) { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (className) el.className = className; return el; }
function error(message) { $('error').textContent = message || ''; $('error').hidden = !message; }
async function api(path, options) { const r = await fetch(path, options); const data = await r.json(); if (!r.ok) throw new Error(data.error || 'Request failed'); return data; }
function freshness() { if (!observation) return; const age = (Date.now() - Date.parse(observation.captured_at)) / 1000; const fresh = Number.isFinite(age) && age >= -2 && age <= 60; $('freshness').textContent = fresh ? 'Captured ' + Math.max(0, Math.floor(age)) + 's ago' : 'Expired / invalid'; $('freshness').className = 'badge ' + (fresh ? 'good' : 'warn'); }
function renderObservation(data) {
  observation = data; observationRaw = null;
  $('snapshot-id').textContent = data.snapshot_id || 'Invalid snapshot'; $('profile').textContent = data.profile || 'Unknown';
  $('coverage').textContent = data.alarm_coverage || 'Unknown'; $('raw').textContent = JSON.stringify(data, null, 2);
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
$('import').addEventListener('change', async event => {
  const file = event.target.files[0]; if (!file || running) return; error();
  try { if (file.size > 262144) throw new Error('Observation exceeds 256 KiB.'); const raw = await file.text(); const data = JSON.parse(raw); if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Expected an observation object.'); renderObservation(data); observationRaw = raw; } catch (e) { error(e.message); } finally { event.target.value = ''; }
});
$('assess').addEventListener('click', async () => {
  if (!observation || running) return; lock(true); error();
  try {
    const result = await api('/api/assess', {method:'POST', headers:{'Content-Type':'application/json','X-MOA-Token':config.token}, body:JSON.stringify({observation: observationRaw ?? observation})});
    const abstain = result.status === 'abstain'; $('result-status').textContent = abstain ? 'Withheld' : 'Supported'; $('result-status').className = 'badge ' + (abstain ? 'warn' : 'good');
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
