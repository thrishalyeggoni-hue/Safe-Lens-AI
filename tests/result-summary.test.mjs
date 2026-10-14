import test from 'node:test';
import assert from 'node:assert/strict';
import {summarizeResult} from '../result-summary.js';
const input={module_type:'message',submitted_text:'Send your OTP',risk_category:'High Risk',findings:[{observation:'Send your OTP',risk_level:'High Risk'}],checks_performed:[{name:'Rules',status:'passed'}],unavailable_checks:[]};
test('repeated observations do not inflate the score',()=>assert.equal(summarizeResult({...input,findings:[...input.findings,...input.findings]}).score,85));
test('missing tools never turn a high-risk warning into a low score',()=>{const r=summarizeResult({...input,unavailable_checks:[{name:'AI',status:'unavailable'}]});assert.equal(r.score,85);assert.equal(r.incomplete,true);});
test('zero observed warnings does not imply safety with missing checks',()=>{const r=summarizeResult({...input,risk_category:'Unable to Assess',findings:[],unavailable_checks:[{name:'AI',status:'unavailable'}]});assert.equal(r.score,0);assert.equal(r.tone,'unknown');});
test('metadata and demo results never receive invented live points',()=>{assert.equal(summarizeResult({risk_category:'High Risk',findings:input.findings}).score,null);assert.equal(summarizeResult({...input,demo:true}).score,null);});
test('known signatures and reputation are explicit strongest signals',()=>{assert.equal(summarizeResult({...input,malware:{status:'infected'}}).score,100);assert.equal(summarizeResult({...input,reputation:{status:'listed'}}).score,95);});
test('inconclusive checks and duplicated missing checks count once',()=>{const r=summarizeResult({...input,checks_performed:[{name:'Rules',status:'passed'},{name:'AI',status:'inconclusive'}],unavailable_checks:[{name:'AI',status:'unavailable'}]});assert.equal(r.completed,1);assert.equal(r.total,2);});
test('all seven real module responses produce bounded display points',async()=>{
 const {readFile}=await import('node:fs/promises');
 const report=JSON.parse(await readFile(new URL('../docs/current-recheck.json',import.meta.url),'utf8'));
 const seen=new Set();
 for(const row of report.cases){const r=summarizeResult(row.result);seen.add(row.module);assert.equal(typeof r.score,'number',row.module);assert.ok(r.score>=0&&r.score<=100);}
 assert.equal(seen.size,7);
});
test('identity descriptions mentioning pressure do not mislabel the source',async()=>{
 const {plainSignal}=await import('../result-summary.js');
 assert.equal(plainSignal({source:'deterministic · identity_claim',interpretation:'Pressure or an identity claim accompanying an observed request'}).title,'Source or destination needs checking');
});
test('strongest evidence comes before minor warnings',()=>{const r=summarizeResult({...input,findings:[{observation:'today',risk_level:'Caution'},...input.findings]});assert.equal(r.findings[0].risk_level,'High Risk');});
test('visual summaries preserve original verdicts, evidence and provider observations',async()=>{
 const {readFile}=await import('node:fs/promises');
 const report=JSON.parse(await readFile(new URL('../docs/current-recheck.json',import.meta.url),'utf8'));
 for(const row of report.cases){
  const original=JSON.stringify(row.result);const r=summarizeResult(row.result);
  assert.equal(JSON.stringify(row.result),original,`${row.module}: original result mutated`);
  assert.equal(r.tone,row.result.risk_category==='High Risk'?'danger':row.result.risk_category==='Caution'?'caution':row.result.risk_category==='Unable to Assess'?'unknown':'calm',row.module);
  for(const f of r.findings)assert.ok(row.result.findings.some(x=>x.observation===f.observation&&x.risk_level===f.risk_level));
  if(row.result.unavailable_checks.length)assert.ok(r.incomplete,`${row.module}: hidden incomplete status`);
 }
});
