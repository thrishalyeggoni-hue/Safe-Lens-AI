// Display points summarize observed warning signs; they are not calibrated probabilities.
export function summarizeResult(data) {
  const unique = new Map();
  for (const f of data.findings || []) {
    if (!['High Risk', 'Caution'].includes(f.risk_level)) continue;
    const key = String(f.observation || f.source || '').trim().toLowerCase().replace(/\s+/g, ' ');
    if (!key) continue;
    if (!unique.has(key) || f.risk_level === 'High Risk') unique.set(key, f);
  }
  const findings = [...unique.values()].sort((a,b) => Number(b.risk_level === 'High Risk') - Number(a.risk_level === 'High Risk'));
  const checks = new Map();
  for (const c of [...(data.checks_performed || []), ...(data.unavailable_checks || [])]) {
    const key = String(c.name || '').toLowerCase();
    const done = ['passed', 'flagged', 'completed'].includes(c.status);
    checks.set(key, (checks.get(key) ?? true) && done);
  }
  const completed = [...checks.values()].filter(Boolean).length;
  const missing = checks.size - completed;
  const detailed = !data.demo && Boolean(data.submitted_text != null || data.image || data.file || data.normalized_url || data.decoder);
  const incomplete = missing > 0 || data.risk_category === 'Unable to Assess' || !detailed;
  const listed = data.reputation?.status === 'listed' || data.provider_info?.link_analysis?.reputation?.status === 'listed';
  const infected = data.malware?.status === 'infected' || data.document_analysis?.malware?.status === 'infected';
  const weights = findings.map(f => f.risk_level === 'High Risk' ? 85 : 30).sort((a,b) => b-a);
  let score = weights.length ? Math.min(99, Math.round(weights[0] + weights.slice(1).reduce((a,b) => a + b * .15, 0))) : 0;
  if (listed) score = Math.max(score, 95);
  if (infected) score = 100;
  if (!detailed || data.demo) score = null;
  const danger = data.risk_category === 'High Risk' || listed || infected;
  const caution = data.risk_category === 'Caution';
  const title = danger ? 'Stop and verify before you act' : caution ? 'Be careful. Check the source first.' : incomplete ? 'We could not finish every check' : 'Few warning signs found';
  const description = danger ? 'Strong warning signs were found. Avoid paying, sharing private codes, or opening linked content until you verify the source.' : caution ? 'Something needs a closer look. Contact the person or organisation through details you find independently.' : incomplete ? 'The checks that ran did not establish safety. Some information or tools were unavailable.' : 'The completed checks found no strong warning signs. Verify the source before you trust it.';
  const tone = danger ? 'danger' : caution ? 'caution' : incomplete ? 'unknown' : 'calm';
  return { findings, score, completed, missing, total: checks.size, incomplete, title, description, tone,
    nextStep: danger ? 'Do not pay or share passwords / OTPs.' : caution ? 'Verify the source before continuing.' : 'Use a trusted contact to confirm the content.' };
}

export function plainSignal(f) {
  const text = String(f.source || '').toLowerCase();
  if (/credential|otp|seed phrase|private key|password/.test(text)) return {icon:'lock', title:'Private information requested', detail:'Keep passwords, OTPs and wallet recovery words private.'};
  if (/malware|reputation|listed threat/.test(text)) return {icon:'shield', title:'Dangerous destination or file', detail:'A threat warning needs your attention before you open anything.'};
  if (/urgency|pressure|limited.time/.test(text)) return {icon:'clock', title:'Pressure to act quickly', detail:'Slow down. Urgency can stop you from checking the details.'};
  if (/advance|payment|fee|deposit/.test(text)) return {icon:'money', title:'Payment deserves a closer look', detail:'Verify the request independently before sending money.'};
  if (/guarantee|return|discount/.test(text)) return {icon:'money', title:'A promise needs verification', detail:'Large rewards or guaranteed returns are warning signs, not proof.'};
  if (/identity|imperson|domain|redirect|hyperlink/.test(text)) return {icon:'shield', title:'Source or destination needs checking', detail:'Confirm who sent it and where the link really leads.'};
  return {icon:'shield', title:'A warning sign was found', detail:'Review the highlighted evidence before you act.'};
}
