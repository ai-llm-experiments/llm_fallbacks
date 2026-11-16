#!/usr/bin/env node
'use strict';
// Read-only MCP adapter for a bundled, point-in-time llm_fallbacks catalog.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const bytes = fs.readFileSync(path.join(__dirname, '..', 'data', 'free_models.json'));
const models = JSON.parse(bytes.toString('utf8'));
if (!Array.isArray(models)) throw new Error('Invalid bundled catalog');
const provenance = {repository:'https://github.com/ai-llm-experiments/llm_fallbacks', path:'configs/free_models.json', catalog_commit:'0e55327f508c2c09c1efe10650d9d8cbb8c462b9', catalog_commit_date:'2026-11-05T18:47:59Z', sha256:crypto.createHash('sha256').update(bytes).digest('hex'), live:false, caveat:'Historical capability metadata; neither zero price, eligibility, quality, privacy, nor availability is verified. Do not use directly for automatic routing.'};
const schema = {type:'object', properties:{query:{type:'string',maxLength:100,description:'Case-insensitive model ID or provider substring'},mode:{type:'string',maxLength:40,description:'Exact catalog mode'},requires_tools:{type:'boolean',description:'Only include records claiming function-calling support'},limit:{type:'integer',minimum:1,maximum:100,default:20}}, additionalProperties:false};
function reply(id, result) { process.stdout.write(JSON.stringify({jsonrpc:'2.0',id,result})+'\n'); }
function fail(id, code, message) { process.stdout.write(JSON.stringify({jsonrpc:'2.0',id,error:{code,message}})+'\n'); }
function call(args) {
  if (!args || typeof args !== 'object' || Array.isArray(args)) throw new TypeError('Arguments must be an object');
  if (Object.keys(args).some(k=>!['query','mode','requires_tools','limit'].includes(k))) throw new TypeError('Unknown argument');
  const {query='',mode='',requires_tools=false,limit=20}=args;
  if (typeof query!=='string'||query.length>100||typeof mode!=='string'||mode.length>40||typeof requires_tools!=='boolean'||!Number.isInteger(limit)||limit<1||limit>100) throw new TypeError('Invalid arguments');
  const q=query.toLowerCase();
  const found=models.filter(m=>m && typeof m.id==='string' && (m.id.toLowerCase().includes(q)||String(m.provider||'').toLowerCase().includes(q)) && (!mode||m.mode===mode) && (!requires_tools||m.supports_function_calling===true));
  return {provenance, total_matches:found.length, returned:Math.min(limit,found.length), models:found.slice(0,limit)};
}
function handleLine(line) {
  let req; try { req=JSON.parse(line); } catch { return fail(null,-32700,'Parse error'); }
  const validId = id => typeof id==='string' || (typeof id==='number' && Number.isSafeInteger(id));
  if (!req || typeof req!=='object' || Array.isArray(req) || req.jsonrpc!=='2.0' || typeof req.method!=='string') return fail(validId(req?.id)?req.id:null,-32600,'Invalid request');
  const hasId=Object.prototype.hasOwnProperty.call(req,'id');
  if (hasId && !validId(req.id)) return fail(null,-32600,'Invalid request ID');
  if (req.params!==undefined && (!req.params || typeof req.params!=='object' || Array.isArray(req.params))) return fail(hasId?req.id:null,-32602,'Invalid params');
  if (!hasId) return;
  switch(req.method) {
    case 'initialize': return reply(req.id,{protocolVersion: ['2025-06-18','2025-03-26','2024-11-05'].includes(req.params?.protocolVersion)?req.params.protocolVersion:'2025-06-18',capabilities:{tools:{}},serverInfo:{name:'llm-fallbacks-catalog',version:'0.1.0'}});
    case 'ping': return reply(req.id,{});
    case 'tools/list': return reply(req.id,{tools:[{name:'search_catalog',description:'Search the offline llm_fallbacks model catalog. Metadata is historical and not proof of price, availability, privacy, or entitlement.',inputSchema:schema,annotations:{readOnlyHint:true,destructiveHint:false,openWorldHint:false}}]});
    case 'tools/call': {
      if (!req.params || req.params.name!=='search_catalog') return fail(req.id,-32602,'Unknown tool or missing params');
      try { return reply(req.id,{content:[{type:'text',text:JSON.stringify(call(req.params.arguments===undefined?{}:req.params.arguments))}]}); }
      catch(e) { return fail(req.id,e instanceof TypeError?-32602:-32603,e instanceof TypeError?e.message:'Internal error'); }
    }
    default: return fail(req.id,-32601,'Method not found');
  }
}

// Bound bytes as they arrive, including a peer that never sends a newline.
const MAX_LINE=1048576;
let chunks=[], size=0, stopped=false;
process.stdin.on('data', chunk=>{
  if (stopped) return;
  let start=0;
  while (start<chunk.length) {
    const newline=chunk.indexOf(10,start);
    const end=newline<0?chunk.length:newline;
    const part=chunk.subarray(start,end);
    if (size+part.length>MAX_LINE) {
      stopped=true; chunks=[]; size=0;
      fail(null,-32600,'Request too large');
      process.stdin.destroy();
      return;
    }
    if (part.length) { chunks.push(part); size+=part.length; }
    if (newline<0) break;
    let line=Buffer.concat(chunks,size).toString('utf8');
    if (line.endsWith('\r')) line=line.slice(0,-1);
    chunks=[]; size=0; handleLine(line); start=newline+1;
  }
});
