(() => {
  'use strict';

  const API = '/api';
  const PAGES = {
    overview: ['Overview', 'SYSTEM & RISK', 10000],
    events: ['Live Event Feed', 'ATTENTION & EVIDENCE', 12000],
    tokens: ['Token Discovery', 'ON-CHAIN / NARRATIVE', 15000],
    decisions: ['Candidates / Decisions', 'DETERMINISTIC RANKING', 15000],
    portfolio: ['Paper Portfolio', 'SIMULATED POSITIONS', 15000],
    agents: ['Agent Operations', 'BOUNDED AUTONOMY', 20000],
    sources: ['Sources', 'COLLECTOR HEALTH', 20000],
    audit: ['Audit', 'FORWARD-ONLY EVIDENCE', 30000],
    settings: ['Settings', 'SAFE LOCAL CONTROLS', 60000],
  };
  const S = {
    page: 'overview', cache: new Map(), synced: new Map(), errors: new Map(),
    controller: null, timer: null, detail: false, dirty: false, changes: {}, consoleChanges: null, opener: null,
    filters: { events: { q: '', role: 'all', eligible: 'all' }, tokens: { q: '', chain: 'all' }, decisions: { action: 'all' } },
  };
  const E = Object.fromEntries(['page-content','page-title','primary-nav','runtime-pill','mode-pill','last-sync','system-notice','refresh-button','sidebar','sidebar-scrim','mobile-menu','detail-drawer','drawer-scrim','drawer-title','drawer-eyebrow','drawer-content','drawer-close','toast-stack'].map(id => [id, document.getElementById(id)]));

  const esc = value => String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll(String.fromCharCode(34),'&quot;').replaceAll(String.fromCharCode(39),'&#039;');
  const get = (object, ...paths) => {
    for (const path of paths) {
      let value = object;
      for (const part of String(path).split('.')) value = value?.[part];
      if (value !== undefined && value !== null) return value;
    }
  };
  const list = (payload, ...keys) => {
    if (Array.isArray(payload)) return payload;
    for (const key of [...keys, 'items']) { const value = get(payload, key); if (Array.isArray(value)) return value; }
    return [];
  };
  const numeric = value => value===null||value===undefined||value==='' ? null : Number.isFinite(Number(value)) ? Number(value) : null;
  const clamp = (value, min = 0, max = 100) => Math.max(min, Math.min(max, Number(value) || 0));
  const score = value => { const n = numeric(value); return n === null ? null : clamp(n > 0 && n <= 1 ? n * 100 : n); };
  const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 });
  const normal = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
  const num = (value, suffix = '') => { const n = numeric(value); return n === null ? '—' : `${Math.abs(n) >= 10000 ? compact.format(n) : normal.format(n)}${suffix}`; };
  const money = (value, short = false) => { const n = numeric(value); if (n === null) return '—'; return `${n < 0 ? '−' : ''}$${short || Math.abs(n) >= 10000 ? compact.format(Math.abs(n)) : normal.format(Math.abs(n))}`; };
  const price = value => { const n = numeric(value); if (n === null) return '—'; if (!n) return '$0'; return Math.abs(n) < .0001 ? `$${n.toExponential(3)}` : `$${n.toLocaleString('en-US', { maximumFractionDigits: n < 1 ? 8 : 4 })}`; };
  const percent = (value, signed = false) => { const n = numeric(value); if (n === null) return '—'; const p = Math.abs(n) <= 1 && n !== 0 ? n * 100 : n; return `${signed && p > 0 ? '+' : ''}${p.toFixed(1)}%`; };
  const dt = value => { const date = value ? new Date(value) : null; return date && !Number.isNaN(date.getTime()) ? date : null; };
  const dateTime = value => dt(value)?.toLocaleString('zh-CN', { hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }) || '—';
  const age = value => { const d = value instanceof Date ? value : dt(value); if (!d) return '未知'; const delta=Math.floor((Date.now()-d.getTime())/1000),future=delta<0,seconds=Math.abs(delta),suffix=future?'后':'前'; if(seconds<60)return `${seconds}秒${suffix}`;if(seconds<3600)return `${Math.floor(seconds/60)}分钟${suffix}`;if(seconds<86400)return `${Math.floor(seconds/3600)}小时${suffix}`;return `${Math.floor(seconds/86400)}天${suffix}`; };
  const until = value => { const d=dt(value);if(!d)return '未计划';const delta=d.getTime()-Date.now();return delta>0?`还有 ${age(d).replace(/后$/,'')}`:`已到期 · ${age(d)}`; };
  const shortAddress = value => { const text = String(value || ''); return text.length > 15 ? `${text.slice(0,7)}…${text.slice(-5)}` : text || '—'; };
  const safeUrl = value => { try { const url = new URL(String(value || ''), location.origin); return ['http:','https:'].includes(url.protocol) ? url.href : ''; } catch { return ''; } };
  const scoreText = value => score(value) === null ? '—' : score(value).toFixed(0);

  function tone(value) {
    const text = String(value ?? '').toLowerCase();
    if (value === true || ['ok','healthy','running','active','ready','connected','online','pass','passed'].includes(text)) return 'ok';
    if (['warn','warning','degraded','paused','stale','limited'].includes(text)) return 'warn';
    if (value === false || ['error','failed','down','stopped','offline','unhealthy'].includes(text)) return 'error';
    return 'unknown';
  }
  const statusPill = (value, label = value || '未知') => `<span class='status-pill status-pill--${tone(value)}'><i></i>${esc(label)}</span>`;
  const pageHead = (title, subtitle, actions = '') => `<div class='page-head'><div><span class='eyebrow'>${esc(PAGES[S.page][1])}</span><h2>${esc(title)}</h2><p>${esc(subtitle)}</p></div>${actions ? `<div class='page-actions'>${actions}</div>` : ''}</div>`;
  const empty = (title, message, glyph = '∅') => `<div class='empty-state' data-testid='empty-state'><div><span class='empty-glyph'>${esc(glyph)}</span><h3>${esc(title)}</h3><p>${esc(message)}</p></div></div>`;
  const panel = (title, body, note = '', flush = false) => `<section class='panel'><header class='panel-head'><div class='panel-title'><h3>${esc(title)}</h3>${note ? `<small>${esc(note)}</small>` : ''}</div></header><div class='panel-body${flush ? ' panel-body--flush' : ''}'>${body}</div></section>`;
  const roleTag = role => { const r = String(role || 'unknown').toLowerCase(); return `<span class='role-tag role-tag--${['feature','confirmation','identity','promotion'].includes(r) ? r : 'unknown'}'>${esc(r)}</span>`; };
  function eligibilityTag(item) {
    const eligible = get(item,'decision_eligible','eligible','is_eligible');
    const rawReason = get(item,'rejection_reasons','exclusion_reason','ineligible_reason','rejection_reason','eligibility_reason');
    const reason = Array.isArray(rawReason) ? rawReason.join(' · ') : rawReason;
    if (eligible === true) return `<span class='role-tag role-tag--feature'>decision eligible</span>`;
    if (eligible === false) return `<span class='result-badge result-badge--rejected' title='${esc(reason || '不可用于该决策')}'>excluded${reason ? ` · ${esc(reason)}` : ''}</span>`;
    return `<span class='tag'>eligibility unknown</span>`;
  }
  function resultInfo(action) {
    const value = String(action || 'WAIT').toUpperCase();
    if (value === 'WAIT') return ['wait','WAIT｜未形成交易信号'];
    if (value === 'CANDIDATE') return ['candidate','CANDIDATE｜通过候选门槛'];
    if (value === 'BUY') return ['buy','PAPER BUY｜模拟成交'];
    if (value === 'SELL') return ['sell','PAPER SELL｜模拟成交'];
    if (['REJECT','REJECTED'].includes(value)) return ['rejected','REJECTED'];
    return ['rejected',value];
  }
  function roleCounts(item) {
    const roles = get(item,'role_counts','roles','role_composition') || {};
    return Object.fromEntries(['feature','confirmation','identity','promotion'].map(name => [name, Math.max(0, Number(roles[name]) || 0)]));
  }
  function roles(item) {
    const counts = roleCounts(item), total = Object.values(counts).reduce((a,b) => a + b, 0);
    if (!total) return `<div class='role-composition'><div class='role-bar'></div><div class='role-legend'><span>角色数据待采集</span></div></div>`;
    return `<div class='role-composition'><div class='role-bar' aria-label='evidence role composition'>${Object.entries(counts).filter(x => x[1]).map(([name,count]) => `<i class='${name}' style='width:${count / total * 100}%'></i>`).join('')}</div><div class='role-legend'>${Object.entries(counts).filter(x => x[1]).map(([name,count]) => `<span class='${name}'>${esc(name)} ${count}</span>`).join('')}</div></div>`;
  }
  const heat = value => `<div class='heat-score' aria-label='attention ${scoreText(value)}'><span class='heat-track' style='--value:${score(value) ?? 0}%'><i></i></span><strong>${scoreText(value)}</strong></div>`;
  function spark(values, className = '') {
    const pointsRaw = Array.isArray(values) ? values.map(numeric).filter(v => v !== null).slice(-24) : [];
    if (pointsRaw.length < 2) return '';
    const min = Math.min(...pointsRaw), max = Math.max(...pointsRaw), span = max - min || 1;
    const points = pointsRaw.map((v,i) => `${(i/(pointsRaw.length-1)*58).toFixed(1)},${(20-(v-min)/span*17).toFixed(1)}`).join(' ');
    return `<svg class='sparkline ${esc(className)}' viewBox='0 0 58 22' aria-hidden='true'><polyline points='${points}'></polyline></svg>`;
  }
  function freshness(item) {
    if(numeric(item?.eligible_source_count)===0)return null;
    const explicit = score(get(item,'freshness','freshness_score')); if (explicit !== null) return explicit;
    const seen = dt(get(item,'last_seen_at','observed_at','ingested_at')); return seen ? clamp(100 - (Date.now() - seen.getTime()) / 60000 * 1.5) : null;
  }
  function breadth(item) { const eligible=numeric(item?.eligible_source_count);if(eligible===0)return null;const explicit=score(get(item,'eligible_source_breadth','source_breadth','source_breadth_score'));if(explicit!==null)return explicit;const count=eligible??numeric(get(item,'source_count','sources_count','independent_sources'));return count===null?null:clamp(count*20); }

  async function api(path, options = {}) {
    const local = new AbortController();
    const timer = setTimeout(() => local.abort(), 9000);
    try {
      const response = await fetch(`${API}${path}`, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}) }, ...options, signal: options.signal || local.signal });
      if (!response.ok) { let detail='';try{detail=(await response.json())?.error||'';}catch{}throw new Error(detail||`HTTP ${response.status}`); }
      if (!(response.headers.get('content-type') || '').includes('json')) throw new Error('服务返回了非 JSON 数据');
      return await response.json();
    } finally { clearTimeout(timer); }
  }
  function notice(message = '') { E['system-notice'].hidden = !message; E['system-notice'].textContent = message; }
  function toast(message, kind = '') { const node = document.createElement('div'); node.className = `toast ${kind}`; node.textContent = message; E['toast-stack'].append(node); setTimeout(() => node.remove(), 4200); }
  function globalStatus(data) {
    const raw = get(data,'runtime.status','runtime.running','bot.status','status','running');
    const status = raw === true ? 'running' : raw === false ? 'stopped' : raw;
    E['runtime-pill'].className = `status-pill status-pill--${tone(status)}`;
    E['runtime-pill'].innerHTML = `<i></i><span>${esc(status === 'running' ? 'BOT RUNNING' : status === 'stopped' ? 'BOT STOPPED' : String(status || '状态未知').toUpperCase())}</span>`;
    const mode = String(get(data,'runtime.mode','mode','trading_mode') || 'paper').toUpperCase();
    const access = get(data,'access','runtime.access','network_access');
    E['mode-pill'].textContent = `${mode === 'SHADOW' ? 'SHADOW' : 'PAPER'} / SIMULATED${access ? ` · ${String(access).toUpperCase()}` : ''}`;
  }
  function loading() { E['page-content'].innerHTML = `<div class='initial-loader' aria-label='加载中'><i></i><i></i><i></i></div>`; }
  function errorPage(error) { E['page-content'].innerHTML = `<div class='error-state' data-testid='api-error'><div><span class='empty-glyph'>!</span><h3>暂时无法读取此模块</h3><p>${esc(error?.message || '本地 Web API 未响应。机器人采集不会因此中断。')}</p><button class='button' data-action='retry' style='margin-top:14px'>重试</button></div></div>`; bind(S.page); }
  function schedule() { clearTimeout(S.timer); S.timer = setTimeout(() => { if (document.visibilityState === 'visible' && !S.dirty) loadPage(true); else schedule(); }, PAGES[S.page][2]); }
  async function loadPage(preserve = false) {
    const page = S.page, cached = S.cache.get(page);
    S.controller?.abort(); S.controller = new AbortController();
    if (!cached) loading(); E['refresh-button'].classList.add('is-spinning');
    try {
      const healthPromise = page === 'overview' ? null : api('/health').catch(() => null);
      const data = await api(`/${page}`, { signal: S.controller.signal });
      S.cache.set(page,data); S.errors.delete(page); S.synced.set(page,new Date()); notice('');
      E['last-sync'].textContent = `刷新 ${age(S.synced.get(page))}`;
      if (page === 'overview') globalStatus(data);
      else { const health=await healthPromise;if(health)globalStatus({runtime:{running:get(health,'system.inferred_running'),mode:health.mode}}); }
      render(page,data,{ preserve });
    } catch (err) {
      if (err.name === 'AbortError') return;
      S.errors.set(page,err);
      if (cached) { notice(`更新失败，正在显示 ${age(S.synced.get(page))} 的缓存数据（STALE）。${err.message || ''}`); render(page,cached,{ stale:true,preserve }); }
      else errorPage(err);
    } finally { E['refresh-button'].classList.remove('is-spinning'); schedule(); }
  }
  function render(page,data,meta={}) {
    const renderers = { overview: overview, events, tokens, decisions, portfolio, agents, sources, audit, settings };
    const focusId = meta.preserve ? document.activeElement?.id : '';
    E['page-content'].innerHTML = `${meta.stale ? `<div class='status-pill status-pill--warn' style='margin-bottom:9px'>STALE SNAPSHOT · 自动重试中</div>` : ''}${renderers[page](data)}`;
    bind(page); if (focusId) document.getElementById(focusId)?.focus({preventScroll:true});
  }

  function metric(label,value,sub='当前快照',trend=[],cls='') { return `<article class='metric-card'><div class='metric-top'><span class='metric-label'>${esc(label)}</span>${spark(trend,cls.includes('positive') ? 'sparkline--green' : '')}</div><div class='metric-value ${esc(cls)}'>${esc(value)}</div><div class='metric-sub'><span>${esc(sub)}</span></div></article>`; }
  function healthList(data) { const raw = get(data,'health','services','components') || {}; return Array.isArray(raw) ? raw : Object.entries(raw).map(([name,value]) => typeof value === 'object' ? {name,...value} : {name,status:value}); }
  function healthGrid(items) {
    if (!items.length) return empty('暂无健康数据','Web API 已连接，但尚未返回组件健康状态。','○');
    return `<div class='health-grid'>${items.map(item => { const status = get(item,'status','state','healthy','ok','reachable'); const note = get(item,'detail','message','path','last_error','note','url','task_name') || ''; return `<div class='health-item'><div class='health-name'><span>${esc(get(item,'label','name','component','service') || '组件')}</span><i class='health-orb ${tone(status)}'></i></div><div class='health-value'>${esc(status === true ? 'HEALTHY' : status === false ? 'UNHEALTHY' : String(status || 'UNKNOWN').toUpperCase())}</div><div class='health-note' title='${esc(note)}'>${esc(note || '无附加信息')}</div></div>`; }).join('')}</div>`;
  }
  function overview(data) {
    const runtime = get(data,'runtime','bot') || {}, account = get(data,'account','portfolio.summary','paper_account') || {}, counts = get(data,'metrics','counts') || {};
    const positions = list(get(data,'positions','open_positions') || [],'positions'), recent = list(get(data,'recent_events','events') || [],'events');
    const access = get(data,'access','runtime.access','network_access') || 'local';
    const running = get(runtime,'running','status');
    const eventsBody = recent.length ? `<div class='table-wrap'><table class='data-table'><thead><tr><th>Event</th><th>Attention</th><th>Eligible origins</th><th>Freshness</th><th>Role composition</th></tr></thead><tbody>${recent.slice(0,7).map(item => {const eligible=numeric(item.eligible_source_count),total=get(item,'source_count','sources_count');const contextOnly=eligible===0||item.decision_eligible===false;return `<tr data-open='event' data-id='${esc(item.id)}' tabindex='0'><td><div class='primary-cell'><div><strong>${esc(item.title || '未命名事件')}</strong><small>#${esc(item.id ?? '—')} · ${esc(age(get(item,'last_seen_at','observed_at')))}${contextOnly?' · CONTEXT ONLY':''}</small></div></div></td><td>${contextOnly?`<span class='tag'>CONTEXT ONLY</span>`:heat(item.attention)}</td><td class='mono'>${esc(eligible===null?num(total):`${eligible} / ${num(total)}`)}</td><td class='mono'>${contextOnly?'—':esc(age(get(item,'last_seen_at','observed_at')))}</td><td>${roles(item)}</td></tr>`;}).join('')}</tbody></table></div>` : empty('尚无事件','数据库为空是正常状态。不会生成演示热点。','◉');
    const positionBody = positions.length ? `<div class='table-wrap'><table class='data-table'><thead><tr><th>Position</th><th>Cost</th><th>Current</th><th>PNL</th></tr></thead><tbody>${positions.slice(0,7).map(p => { const pnl=numeric(get(p,'pnl_pct','unrealized_pnl_pct')); return `<tr><td><div class='primary-cell'><div><strong>${esc(p.symbol || p.token_id || '—')}</strong><small>${esc(p.chain || '')} · PAPER</small></div></div></td><td class='mono'>${esc(money(get(p,'cost_usd','remaining_cost_usd')))}</td><td class='mono'>${esc(price(get(p,'current_price','price_usd')))}</td><td class='mono ${pnl !== null && pnl >= 0 ? 'positive':'negative'}'>${esc(percent(pnl,true))}</td></tr>`; }).join('')}</tbody></table></div>` : empty('没有开放仓位','Paper 账户当前没有模拟持仓。','▤');
    return `${pageHead('System overview','风险状态优先；所有资金与盈亏均为 Paper 模拟数据。')}<section class='risk-strip' data-testid='risk-state'><div class='risk-primary'><span class='risk-icon'>▣</span><div><strong>${esc(String(get(runtime,'mode') || get(data,'mode') || 'paper').toUpperCase())} / SIMULATED EXECUTION</strong><p>确定性风控由后端执行；控制台不能解锁真实交易。</p></div></div><div class='risk-cell'><span>BOT RUNTIME</span><strong><i class='health-orb ${tone(running)}'></i>${esc(running===true?'RUNNING':running===false?'STOPPED':String(running||'UNKNOWN').toUpperCase())}</strong></div><div class='risk-cell'><span>LIVE TRADING</span><strong class='negative'>${get(data,'live_locked','runtime.live_locked') === false ? 'STATE ERROR':'LOCKED / UNAVAILABLE'}</strong></div><div class='risk-cell'><span>ACCESS</span><strong>${esc(String(access).toUpperCase())}${String(access).toLowerCase().includes('public')?' · PROTECTED':' · LOOPBACK'}</strong></div></section>
      <div class='metric-grid' data-testid='overview-metrics'>${metric('Paper cash',money(get(account,'cash_usd','cash'),true),'可用模拟现金',get(account,'cash_history'), 'paper-value')}${metric('Paper equity',money(get(account,'equity_usd','equity'),true),'模拟账户权益',get(account,'equity_history'),'paper-value')}${metric('Daily exposure',money(get(account,'exposure_usd','daily_exposure_usd'),true),'当日模拟风险暴露')}${metric('Open positions',num(get(counts,'open_positions','position_count') ?? positions.length),'Paper 持仓')}${metric('Decisions',num(get(counts,'decisions','decision_count','total_decisions')),'确定性结论总数')}${metric('Paper trades',num(get(counts,'trades','trade_count','total_trades')),'模拟成交总数')}</div>
      <div class='dashboard-grid'><div class='stack'>${panel('Live event activity',eventsBody,recent.length?`${recent.length} recent`:'empty',true)}${panel('Paper open positions',positionBody,`${positions.length} open`,true)}</div><div class='stack'>${panel('Runtime health',healthGrid(healthList(data)),'current snapshot',true)}${panel('Safety plane',healthGrid([{name:'SQLite',...get(data,'health.sqlite','health.database')},{name:'Browser bridge',...get(data,'health.browser_bridge','browser_bridge')},{name:'Scheduler / task',...get(data,'health.scheduler','scheduler')},{name:'Web console',status:'ok',detail:'loopback control plane'}]),'local dependencies',true)}</div></div>`;
  }
  function events(data) {
    let items=list(data,'events');
    const f=S.filters.events,q=f.q.trim().toLowerCase();
    items=items.filter(item=>{if(q&&!`${item.title||''} ${(item.aliases||[]).join(' ')}`.toLowerCase().includes(q))return false;const rc=roleCounts(item);if(f.role!=='all'&&!(rc[f.role]>0||item.role===f.role))return false;const eligible=get(item,'decision_eligible','eligible');return !(f.eligible==='eligible'&&eligible!==true||f.eligible==='context'&&eligible!==false);});
    const actions=`<input id='event-query' class='control' type='search' placeholder='搜索事件或别名' value='${esc(f.q)}' aria-label='搜索事件'><select id='event-role' class='control' aria-label='证据角色'><option value='all'>全部角色</option>${['feature','confirmation','identity','promotion'].map(v=>`<option value='${v}' ${f.role===v?'selected':''}>${v}</option>`).join('')}</select><select id='event-eligibility' class='control' aria-label='决策资格'><option value='all'>全部资格</option><option value='eligible' ${f.eligible==='eligible'?'selected':''}>可用于决策</option><option value='context' ${f.eligible==='context'?'selected':''}>仅上下文</option></select>`;
    const body=items.length?`<div class='event-list' data-testid='event-list'>${items.map(item=>{
      const eligible=numeric(item.eligible_source_count),total=numeric(get(item,'source_count','sources_count','independent_sources'));
      const contextOnly=eligible===0||item.decision_eligible===false;
      const attention=contextOnly?null:score(item.attention),fresh=freshness(item),wide=breadth(item);
      const originLabel=eligible===null?`${num(total)} total origins`:`${num(eligible)} eligible / ${num(total)} total origins`;
      return `<article class='event-card' data-open='event' data-id='${esc(item.id)}' tabindex='0' aria-label='打开事件：${esc(item.title||'未命名事件')}'><div><div class='event-title-row'><h3>${esc(item.title||'未命名事件')}</h3>${contextOnly?`<span class='tag'>CONTEXT ONLY</span>`:eligibilityTag(item)}</div><div class='event-meta'><span>◷ ${esc(age(get(item,'last_seen_at','observed_at')))}</span><span>⌘ ${esc(originLabel)}</span><span>#${esc(item.id??'—')}</span></div>${roles(item)}</div><div class='event-dimensions'>${[['Attention',attention,''],['Freshness',fresh,'fresh'],['Eligible breadth',wide,'sources']].map(([label,value,cls])=>`<div class='dimension ${cls}'><small>${label}</small><strong>${value===null?'—':value.toFixed(0)}</strong><div class='micro-track' style='--value:${value??0}%'><i></i></div></div>`).join('')}</div><div class='event-score'><strong>${attention===null?'—':attention.toFixed(0)}</strong><small>${contextOnly?'CONTEXT ONLY':'ATTENTION'}</small>${contextOnly?'':spark(get(item,'attention_history','trend'))}</div></article>`;
    }).join('')}</div>`:empty('没有匹配事件',list(data,'events').length?'调整筛选条件查看其他真实观察。':'采集器尚未形成事件。空库不会填充演示热点。','◉');
    return `${pageHead('Live event feed','热度拆分展示，不将 identity 或 promotion 伪装为决策证据。',actions)}${body}`;
  }
  function tokens(data) {
    let items=list(data,'tokens');
    const f=S.filters.tokens,q=f.q.trim().toLowerCase();
    const chains=[...new Set(items.map(x=>String(x.chain||'').toLowerCase()).filter(Boolean))];
    items=items.filter(x=>(f.chain==='all'||String(x.chain||'').toLowerCase()===f.chain)&&(!q||`${x.name||''} ${x.symbol||''} ${x.address||''}`.toLowerCase().includes(q)));
    const actions=`<input id='token-query' class='control' type='search' placeholder='名称、symbol 或 CA' value='${esc(f.q)}' aria-label='搜索 Token'><select id='token-chain' class='control' aria-label='筛选链'><option value='all'>全部链</option>${chains.map(chain=>`<option value='${esc(chain)}' ${f.chain===chain?'selected':''}>${esc(chain.toUpperCase())}</option>`).join('')}</select>`;
    const body=items.length?`<div class='token-grid' data-testid='token-list'>${items.map(token=>{
      const snap=get(token,'snapshot','latest_snapshot')||token;
      const buys=numeric(get(snap,'buys_5m','buys')),sells=numeric(get(snap,'sells_5m','sells'));
      const total=buys===null||sells===null?null:buys+sells;
      const id=token.token_id||token.id||`${token.chain||''}:${token.address||''}`;
      return `<article class='token-card' data-open='token' data-id='${esc(id)}' tabindex='0' aria-label='打开 Token：${esc(token.symbol||token.name||token.address)}'>
        <div class='token-segment'><div class='token-identity'><span class='token-glyph'>${esc(String(token.symbol||token.name||'?').slice(0,2).toUpperCase())}</span><div class='token-name'><h3>${esc(token.name||'未命名 Token')}</h3><small>${esc(token.symbol||'—')} · ${esc(age(get(token,'created_at','first_seen_at')))}</small></div></div><div class='address-line'><span class='chain-tag'>${esc(String(token.chain||'unknown').toUpperCase())}</span><span title='${esc(token.address||'')}'>${esc(shortAddress(token.address))}</span></div></div>
        <div class='token-segment'><div class='segment-label'>ON-CHAIN MOMENTUM · 不等同叙事证据</div><div class='stat-matrix'><div class='stat-cell'><small>Liquidity</small><strong>${esc(money(get(snap,'liquidity_usd','liquidity'),true))}</strong></div><div class='stat-cell'><small>5m volume</small><strong>${esc(money(get(snap,'volume_5m_usd','volume_5m'),true))}</strong></div><div class='stat-cell'><small>Momentum</small><strong>${esc(scoreText(get(token,'momentum','momentum_score','snapshot.momentum_score')))}</strong></div><div class='stat-cell'><small>Price</small><strong>${esc(price(get(snap,'price_usd','price')))}</strong></div><div class='stat-cell'><small>Buys / sells</small><strong><span class='positive'>${esc(num(buys))}</span> / <span class='negative'>${esc(num(sells))}</span></strong><div class='flow-ratio'><i class='buys' style='width:${total&&buys!==null?buys/total*100:0}%'></i><i class='sells' style='width:${total&&sells!==null?sells/total*100:0}%'></i></div></div><div class='stat-cell'><small>Snapshot</small><strong>${esc(age(get(snap,'observed_at','updated_at')))}</strong></div></div></div>
        <div class='token-segment'><div class='segment-label'>NARRATIVE EVIDENCE · 独立呈现</div><div class='evidence-summary'><div class='evidence-row'><span>Linked event</span><strong>${esc(get(token,'event.title','event_title','linked_event.title')||'尚未关联')}</strong></div><div class='evidence-row'><span>Event → Token</span><strong>${esc(get(token,'event_to_token','evidence.event_to_token','event_match_reason')||'无可用证据')}</strong></div><div class='evidence-row'><span>Token → Event</span><strong>${esc(get(token,'token_to_event','evidence.token_to_event','context_result')||'尚未完成反查')}</strong></div><div class='evidence-row'><span>Evidence</span><strong>${esc(num(get(token,'evidence_count','source_count','evidence.source_count')))} sources · ${esc(get(token,'evidence_role','role')||'role unknown')}</strong></div></div></div><div class='token-open'>›</div></article>`;
    }).join('')}</div>`:empty('没有匹配 Token',list(data,'tokens').length?'调整链或关键词筛选。':'新池或新 Token 尚未进入本地数据库。','◇');
    return `${pageHead('Token discovery','链上动量与事件叙事严格分栏，避免把成交活跃误当成现实热点。',actions)}${body}`;
  }

  function decisions(data) {
    let items=list(data,'decisions'); const selected=S.filters.decisions.action;
    if(selected!=='all') items=items.filter(x=>{const action=String(x.action||'WAIT').toLowerCase();return selected==='rejected'?['reject','rejected'].includes(action):action===selected;});
    const actions=`<select id='decision-action' class='control' aria-label='筛选结论'><option value='all'>全部结论</option>${['wait','candidate','buy','rejected'].map(v=>`<option value='${v}' ${selected===v?'selected':''}>${v.toUpperCase()}</option>`).join('')}</select>`;
    const body=items.length?`<section class='panel'><div class='panel-body panel-body--flush' data-testid='decision-list'>${items.map(item=>{
      const [cls,label]=resultInfo(item.action),reasons=Array.isArray(item.reasons)?item.reasons:[],rejected=get(item,'rejected_reasons','rejection_reasons')||[],rankingMissing=item.ranking_available===false;
      const rankText=rankingMissing?'ranking not persisted':`rank ${get(item,'rank','candidate_rank')??'—'}`;
      return `<article class='decision-card'><div class='decision-top'><div><h3>${esc(get(item,'event_title','event.title')||`Event #${item.event_id??'—'}`)} · ${esc(get(item,'token_symbol','token.symbol','token_id')||'未关联 Token')}</h3><p>${esc(dateTime(get(item,'created_at','decided_at')))} · ${esc(rankText)}</p></div><span class='result-badge result-badge--${cls}' data-testid='decision-result'>${esc(label)}</span></div>${rankingMissing?`<div class='persistence-gap'><strong>RANKING UNAVAILABLE</strong><span>${esc(item.persistence_gap||'candidate ranking was not persisted')}</span></div>`:''}<div class='score-grid'><div class='score-box'><small>MATCH SCORE</small><strong>${esc(scoreText(item.match_score))}</strong></div><div class='score-box'><small>CANDIDATE SCORE</small><strong>${esc(scoreText(get(item,'candidate_score','score')))}</strong></div><div class='score-box'><small>CANONICAL MARGIN</small><strong>${esc(num(item.canonical_margin))}</strong></div><div class='score-box'><small>PAPER SIZE</small><strong>${esc(money(item.position_usd))}</strong></div></div><div class='reason-list'>${rejected.map(reason=>`<span class='reason rejected'>拒绝：${esc(reason)}</span>`).join('')}${reasons.map(reason=>`<span class='reason'>${esc(reason)}</span>`).join('')}${!reasons.length&&!rejected.length?`<span class='reason'>后端未返回解释</span>`:''}</div></article>`;
    }).join('')}</div></section>`:panel('Decision ledger',empty('尚无决策','WAIT、CANDIDATE 或 Paper 模拟成交会按真实后端结果显示。','⌁'),'empty');
    return `${pageHead('Candidate ranking & decisions','WAIT 是保守结论，不是隐藏的买入信号；CANDIDATE 也仅表示通过候选门槛。',actions)}<div class='decision-layout'><div>${body}</div><aside class='stack'><div class='wait-principle'><strong>WAIT｜未形成交易信号</strong><p>候选匹配、canonical margin、安全门或证据时间任一不足时保持等待。这里不会使用绿色、上涨箭头或“机会”措辞美化 WAIT。</p></div><div class='safety-box'><h3>Decision boundary</h3><p>控制台只读取策略结果；排名、position size 和拒绝原因仍由 memeTrader 的确定性策略计算。</p><ul><li>future / stale evidence 不参与决策</li><li>identity / promotion 不替代 feature</li><li>Live trading 永久不可在网页开启</li></ul></div></aside></div>`;
  }

  function portfolio(data) {
    const summary=get(data,'summary','account')||{},positions=list(data,'positions','open_positions'),trades=list(get(data,'trades','history')||[],'trades'),pnl=numeric(get(summary,'unrealized_pnl_usd','pnl_usd'));
    const metrics=`<div class='portfolio-grid' data-testid='paper-summary'>${metric('Paper cash',money(get(summary,'cash_usd','cash'),true),'SIMULATED',[],'paper-value')}${metric('Paper equity',money(get(summary,'equity_usd','equity'),true),'SIMULATED',get(summary,'equity_history'),'paper-value')}${metric('Unrealized PNL',money(pnl,true),'SIMULATED',[],pnl!==null?(pnl>=0?'positive':'negative'):'')}${metric('Realized PNL',money(summary.realized_pnl_usd,true),'SIMULATED')}${metric('Exposure',money(get(summary,'exposure_usd','daily_exposure_usd'),true),'PAPER RISK')}</div>`;
    const open=positions.length?`<div class='token-grid' data-testid='paper-positions'>${positions.map(p=>{const positionPnl=numeric(get(p,'pnl_pct','unrealized_pnl_pct'));const gauges=[['Stop',get(p,'stop_price','stop_loss_price')],['Trailing',get(p,'trailing_price','trailing_stop_price')],['Narrative decay',get(p,'narrative_decay','narrative_decay_score')]];return `<article class='position-card'><div class='position-head'><div><h3>${esc(p.symbol||p.token_id||'—')}</h3><div class='address-line'><span class='chain-tag'>${esc(String(p.chain||'').toUpperCase())}</span><span>PAPER · ${esc(age(p.opened_at))}</span></div></div><span class='result-badge result-badge--open'>OPEN / SIMULATED</span></div><div class='position-prices'><div><small>ENTRY</small><strong>${esc(price(p.entry_price))}</strong></div><div><small>CURRENT</small><strong>${esc(price(get(p,'current_price','price_usd')))}</strong></div><div><small>HIGHEST</small><strong>${esc(price(p.highest_price))}</strong></div><div><small>COST</small><strong>${esc(money(p.cost_usd))}</strong></div><div><small>PNL</small><strong class='${positionPnl!==null&&positionPnl>=0?'positive':'negative'}'>${esc(percent(positionPnl,true))}</strong></div><div><small>TP STAGE</small><strong>${esc(get(p,'take_profit_index','tp_stage')??'—')}</strong></div></div><div class='position-footer'>${gauges.map(([label,value])=>`<div class='risk-line'><span>${esc(label)}</span>${label==='Narrative decay'?`<div class='budget-track'><i style='--value:${score(value)??0}%;background:var(--amber)'></i></div>`:`<div class='threshold-rule'>price threshold</div>`}<strong>${label==='Narrative decay'?esc(scoreText(value)):esc(price(value))}</strong></div>`).join('')}</div></article>`;}).join('')}</div>`:panel('Open Paper positions',empty('没有开放仓位','这是正常状态，不会填充模拟持仓来装饰页面。','▤'),'0 open');
    const history=trades.length?`<div class='table-wrap'><table class='data-table' data-testid='paper-trades'><thead><tr><th>Time</th><th>Token</th><th>Side</th><th>Quantity</th><th>Price</th><th>Gross</th><th>Fee</th><th>Reason</th></tr></thead><tbody>${trades.map(trade=>{const side=String(trade.side||'').toLowerCase();return `<tr><td class='mono nowrap'>${esc(dateTime(get(trade,'created_at','executed_at')))}</td><td><strong>${esc(get(trade,'symbol','token_id')||'—')}</strong></td><td><span class='result-badge result-badge--${side==='buy'?'buy':'sell'}'>PAPER ${esc(side.toUpperCase()||'TRADE')}</span></td><td class='mono'>${esc(num(trade.quantity))}</td><td class='mono'>${esc(price(trade.price))}</td><td class='mono'>${esc(money(trade.gross_usd))}</td><td class='mono'>${esc(money(trade.fee_usd))}</td><td class='muted'>${esc(trade.reason||'—')}</td></tr>`;}).join('')}</tbody></table></div>`:empty('没有历史成交','Paper 策略尚未产生模拟买卖。','·');
    return `${pageHead('Paper portfolio','所有仓位、盈亏与交易均为模拟执行，不代表真实利润。')}${metrics}<div class='stack'>${open}${panel('Paper trade history',history,`${trades.length} simulated trades`,true)}</div>`;
  }

  function agents(data) {
    const items=list(data,'agents','operations');
    const provider=`<div class='agent-provider'><div><span>AGENT PROVIDER</span><strong>${esc(data.provider||'Local Codex CLI')}</strong></div><div><span>CREDENTIAL</span><strong>${esc(data.credential_mode||'signed_in_local_session')}</strong></div><div><span>USES API KEY</span><strong>${data.uses_api_key===false?'NO':data.uses_api_key===true?'YES':'UNKNOWN'}</strong></div><div><span>CONCURRENCY</span><strong>${esc(num(data.max_concurrent_agents))} / 2</strong></div></div>`;
    const body=items.length?`<div class='agent-grid' data-testid='agent-operations'>${items.map(agent=>{const status=get(agent,'status','state')||'unknown',calls=numeric(get(agent,'calls_today','usage.calls')),callBudget=numeric(get(agent,'daily_call_budget','budget.calls')),tokensUsed=numeric(get(agent,'tokens_today','usage.tokens')),tokenBudget=numeric(get(agent,'daily_token_budget','budget.tokens')),fallback=get(agent,'fallback','fallback_used','last_fallback');return `<article class='agent-card'><div class='agent-top'><div><h3>${esc(get(agent,'label','name','task')||'Agent')}</h3><div class='agent-model'>${esc(get(agent,'model','current_model')||'model unknown')} · ${esc(get(agent,'reasoning','reasoning_effort')||'reasoning unknown')}</div></div>${statusPill(status,String(status).toUpperCase())}</div><div class='agent-stats'><div><small>NEXT RUN</small><strong>${esc(until(agent.next_run_at))}</strong></div><div><small>LAST RUN</small><strong>${esc(age(agent.last_run_at))}</strong></div><div><small>FALLBACK</small><strong>${esc(fallback===true?'USED':fallback===false?'NO':fallback||'—')}</strong></div></div><div class='budget-row'><div class='budget-label'><span>CALLS</span><span>${esc(num(calls))} / ${esc(num(callBudget))}</span></div><div class='budget-track'><i style='--value:${callBudget?clamp(calls/callBudget*100):0}%'></i></div></div><div class='budget-row'><div class='budget-label'><span>TOKENS</span><span>${esc(num(tokensUsed))} / ${esc(num(tokenBudget))}</span></div><div class='budget-track'><i style='--value:${tokenBudget?clamp(tokensUsed/tokenBudget*100):0}%'></i></div></div><div class='agent-result'><small>LAST RESULT</small><p>${esc(get(agent,'last_result','result_summary','last_error')||'尚无结果')}</p></div></article>`;}).join('')}</div>`:empty('暂无 Agent 运行记录','Agent 未运行或后端尚未记录使用量；本地采集器仍可独立工作。','✣');
    return `${pageHead('Agent operations','Agent 仅承担热点侦察、搜源和 Token 语境调查；调用使用本机已登录的 ChatGPT/Codex 额度。')}${provider}${body}`;
  }

  function collectionFrom(data) { return get(data,'console','collection_preferences','watchlist') || get(data,'values.collection_preferences','values.collection') || {}; }
  function sources(data) {
    const items=list(data,'sources'),summary=get(data,'summary','counts')||{},collection=collectionFrom(data),platforms=collection.platforms||[],accounts=collection.watch_accounts||collection.accounts||[];
    const platformCount=Array.isArray(platforms)?platforms.filter(x=>x.enabled!==false).length:Object.values(platforms).filter(Boolean).length;
    const accountCount=Array.isArray(accounts)?accounts.filter(x=>x.enabled!==false).length:0;
    const active=numeric(get(summary,'active','healthy'))??items.filter(x=>tone(get(x,'status','healthy'))==='ok').length,paused=numeric(summary.paused)??items.filter(x=>String(get(x,'status','state')||'').toLowerCase()==='paused').length,errors=numeric(get(summary,'errors','failed'))??items.filter(x=>tone(get(x,'status','healthy'))==='error').length;
    const cards=`<div class='source-summary'><div class='source-group'><div><strong class='positive'>${esc(num(active))}</strong><small>ACTIVE / HEALTHY</small></div><span class='source-kind'>sources</span></div><div class='source-group'><div><strong>${esc(num(paused))}</strong><small>PAUSED</small></div><span class='source-kind'>sources</span></div><div class='source-group'><div><strong class='negative'>${esc(num(errors))}</strong><small>ERRORS</small></div><span class='source-kind'>sources</span></div><div class='source-group'><div><strong>${esc(num(platformCount))} / ${esc(num(accountCount))}</strong><small>PLATFORMS / ACCOUNTS</small></div><span class='source-kind'>watchlist</span></div></div>`;
    const body=items.length?`<div class='table-wrap'><table class='data-table' data-testid='source-health'><thead><tr><th>Source</th><th>Kind</th><th>State</th><th>Last OK</th><th>Last item</th><th>Pause / error reason</th></tr></thead><tbody>${items.map(source=>{const status=get(source,'status','state','healthy'),label=status===true?'ACTIVE':status===false?'ERROR':String(status||(source.paused?'PAUSED':'UNKNOWN')).toUpperCase(),stateTone=source.paused?'warn':tone(status);return `<tr><td><div class='primary-cell'><div><strong>${esc(get(source,'label','name','source')||'未命名来源')}</strong><small>${esc(get(source,'url','endpoint')||'local collector')}</small></div></div></td><td><span class='tag'>${esc(get(source,'kind','source_kind','type')||'unknown')}</span></td><td><span class='status-pill status-pill--${stateTone}'><i></i>${esc(label)}</span></td><td class='mono nowrap' title='${esc(dateTime(source.last_ok_at))}'>${esc(age(source.last_ok_at))}</td><td class='mono nowrap' title='${esc(dateTime(source.last_item_at))}'>${esc(age(source.last_item_at))}</td><td class='source-error'>${esc(get(source,'pause_reason','last_error','error')||'—')}</td></tr>`;}).join('')}</tbody></table></div>`:empty('尚无来源健康记录','采集器首次心跳后会分别记录 last_ok_at 与 last_item_at。','⌘');
    return `${pageHead('Source health','静态/动态 RSS、链上源、浏览器桥与安全服务的真实运行状态。')}${cards}${panel('Collectors',body,`${items.length} registered`,true)}`;
  }

  function audit(data) {
    const cases=list(data,'cases','audits','items'),recent=list(data,'recent_decision_evidence'),status=get(data,'status','overall_status','result')||'unknown',future=get(data,'future_data_rejected','summary.future_rejected','future_rejections');
    const body=cases.length?`<div class='audit-cases' data-testid='audit-cases'>${cases.map(item=>{
      const result=get(item,'status','result')||'unknown',runtime=item.runtime_evidence||{},roleSummary=Object.entries(runtime.roles||{}).map(([role,count])=>`${role} ${count}`).join(' · ');
      return `<article class='audit-case'>${statusPill(result,String(result).toUpperCase())}<h3>${esc(get(item,'title','name','case')||'Audit case')}</h3><p>${esc(get(item,'summary','description','detail')||'后端未返回说明')}</p><div class='audit-detail'><div><span>DATASET</span><strong>${esc(get(item,'dataset','database','version')||data.release||'—')}</strong></div><div><span>OUTCOME</span><strong>${esc(get(item,'outcome','decision','status')||'—')}</strong></div>${Object.keys(runtime).length?`<div><span>RUNTIME ELIGIBILITY</span><strong>${runtime.decision_eligible?'ELIGIBLE':'EXCLUDED'}</strong></div><div><span>ROLES</span><strong>${esc(roleSummary||'—')}</strong></div><div><span>ATTEMPTS</span><strong>${esc(num(runtime.attempt_count))}</strong></div><div><span>NEXT CHECK</span><strong>${esc(runtime.next_check_at?age(runtime.next_check_at):'—')}</strong></div>`:''}${item.observed_rejection_count!==undefined?`<div><span>OBSERVED REJECTIONS</span><strong>${esc(num(item.observed_rejection_count))}</strong></div>`:''}</div></article>`;
    }).join('')}</div>`:empty('尚无审计结果','审计 API 未返回案例；这不代表审计已通过。','✓');
    const decisionBody=recent.length?`<div class='table-wrap'><table class='data-table' data-testid='audit-decision-evidence'><thead><tr><th>Decision</th><th>Result</th><th>Eligible evidence</th><th>Independent origins</th><th>Persistence</th></tr></thead><tbody>${recent.map(item=>{const [cls,label]=resultInfo(item.action),evidence=Array.isArray(item.evidence)?item.evidence:[],eligible=evidence.filter(row=>row.decision_eligible===true),origins=new Set(eligible.map(row=>row.origin).filter(Boolean));return `<tr data-open='event' data-id='${esc(item.event_id)}' tabindex='0'><td><div class='primary-cell'><div><strong>${esc(item.event_title||`Event #${item.event_id}`)}</strong><small>${esc(dateTime(item.created_at))}</small></div></div></td><td><span class='result-badge result-badge--${cls}'>${esc(label)}</span></td><td class='mono'>${esc(num(eligible.length))} / ${esc(num(evidence.length))}</td><td class='mono'>${esc(num(origins.size))}</td><td>${item.ranking_available===false?`<span class='result-badge result-badge--rejected'>${esc(item.persistence_gap||'ranking unavailable')}</span>`:`<span class='tag'>available</span>`}</td></tr>`;}).join('')}</tbody></table></div>`:empty('没有近期决策证据','尚无可展示的 forward-only 决策证据。','·');
    return `${pageHead('Forward-only audit','证据必须在决策时已被本机观察；未来、陈旧、身份和推广数据不得倒灌。')}<section class='audit-banner'><span class='audit-shield'>✓</span><div><h3>Audit status: ${esc(String(status).toUpperCase())}</h3><p>r5 false-positive、r6/r0.6.3 stale reverse evidence、Starlink 与 future-data rejection 应由后端真实结果证明。</p></div>${statusPill(status,future===true?'FUTURE DATA REJECTED':future===false?'REVIEW REQUIRED':'STATUS UNKNOWN')}</section><div class='stack'>${body}${panel('Recent decision evidence',decisionBody,`${recent.length} decisions`,true)}</div>`;
  }

  function inferredField(path,data) {
    const seconds={poll_seconds:[10,3600],reverse_news_seconds:[15,3600],event_scan_seconds:[1,600],position_scan_seconds:[5,600],source_health_seconds:[10,3600]};
    let min,max,unit='';
    if(seconds[path]){[min,max]=seconds[path];unit='秒';}
    else if(path==='autonomous_search.max_concurrent_agents'){min=1;max=2;unit='个';}
    else if(/trend_scout_.*_interval_minutes$/.test(path)){min=1;max=1440;unit='分钟';}
    else if(path==='autonomous_search.source_discovery_interval_hours'){min=1;max=720;unit='小时';}
    else if(path==='autonomous_search.context_global_cooldown_minutes'){min=1;max=1440;unit='分钟';}
    else if(path==='autonomous_search.context_token_cooldown_minutes'){min=1;max=10080;unit='分钟';}
    else if(/_seconds$/.test(path))unit='秒';else if(/_minutes$/.test(path))unit='分钟';else if(/_hours$/.test(path))unit='小时';else if(/_usd$/.test(path))unit='USD';else if(/_pct$/.test(path))unit='比例';else if(/token_budget|token_reserve/.test(path))unit='tokens';else if(/daily_limit/.test(path))unit='次/日';
    const current=get(data.editable||{},path);
    const group=path.includes('.')?path.split('.')[0].replaceAll('_',' '):'Runtime polling';
    return {path,label:path.split('.').pop().replaceAll('_',' '),description:`安全运行参数 · ${path}${min!==undefined?` · 范围 ${min}–${max} ${unit}`:''}`,group,type:typeof current==='number'?'number':typeof current==='boolean'?'boolean':'string',safe:true,min,max,unit};
  }
  function schemaFields(data) {
    const schema=data?.schema;
    if(Array.isArray(schema))return schema;
    if(Array.isArray(schema?.fields))return schema.fields;
    const result=[];
    for(const [group,value] of Object.entries(schema||{})){
      if(['collection_preferences','collection','platforms','accounts','topics'].includes(group))continue;
      const fields=Array.isArray(value)?value:value?.fields;
      if(Array.isArray(fields))fields.forEach(field=>result.push({group,...field}));
      else if(value&&typeof value==='object'&&('type' in value||'path' in value))result.push({group:value.group||'Runtime',path:value.path||group,...value});
    }
    if(result.length)return result;
    return Array.isArray(data?.editable_paths)?data.editable_paths.map(path=>inferredField(path,data)):[];
  }
  function safeSetting(field) {
    const path=String(field.path||field.key||'');
    if(!path||field.sensitive===true||field.editable===false||field.mutable===false)return false;
    if(/(^|\.)(live|secrets?|password|passwd|cookie|private_key|wallet|seed|mnemonic|credential|bearer|api_key|api_secret|bridge_token|auth_token)(\.|$)/i.test(path))return false;
    if(field.safe===true||field.editable===true||field.mutable===true)return true;
    return /(interval|frequency|poll|cooldown|budget|threshold|freshness|lookback|daily_call_limit|daily_token_budget|max_concurrent_agents|min_|max_items|limit$)/i.test(path);
  }
  function setPath(object,path,value){const parts=String(path).split('.');let cursor=object;parts.forEach((part,index)=>{if(index===parts.length-1)cursor[part]=value;else cursor=cursor[part]||=( {} );});}
  function fieldValue(data,field){const path=field.path||field.key;return get(S.changes,path)??get(get(data,'editable','values','settings')||{},path)??field.value??field.default;}
  function fieldInput(field,value){
    const path=field.path||field.key,type=String(field.type||(typeof value==='boolean'?'boolean':typeof value==='number'?'number':'string')).toLowerCase(),options=field.options||field.enum;
    if(Array.isArray(options))return `<select class='control' data-setting-path='${esc(path)}'>${options.map(option=>{const optionValue=typeof option==='object'?option.value:option,label=typeof option==='object'?option.label:option;return `<option value='${esc(optionValue)}' ${String(value)===String(optionValue)?'selected':''}>${esc(label)}</option>`;}).join('')}</select>`;
    if(['boolean','bool'].includes(type))return `<select class='control' data-setting-path='${esc(path)}' data-value-type='boolean'><option value='true' ${value===true?'selected':''}>启用</option><option value='false' ${value===false?'selected':''}>停用</option></select>`;
    let min=field.min,max=field.max;if(/max_concurrent_agents$/i.test(path)){min=1;max=2;}
    const isNumber=['number','integer','float'].includes(type)||typeof value==='number';
    return `<div style='display:flex;align-items:center;gap:7px'><input class='control' data-setting-path='${esc(path)}' data-value-type='${isNumber?'number':'string'}' type='${isNumber?'number':'text'}' value='${esc(value??'')}' ${min!==undefined?`min='${esc(min)}'`:''} ${max!==undefined?`max='${esc(max)}'`:''} ${field.step!==undefined?`step='${esc(field.step)}'`:isNumber?`step='any'`:''}><span class='dim mono' style='font-size:8px'>${esc(field.unit||'')}</span></div>`;
  }
  function collectionSchema(data){return get(data,'schema.collection_preferences','schema.collection')||{};}
  function platformRows(data){
    const collection=collectionFrom(data),raw=collection.platforms||[],options=get(collectionSchema(data),'platforms.options','platform_options')||[];
    let rows=Array.isArray(raw)?raw.map(item=>typeof item==='object'?item:{id:item,label:item,enabled:true}):Object.entries(raw).map(([id,enabled])=>({id,label:id,enabled}));
    if(!rows.length&&Array.isArray(options))rows=options.map(item=>typeof item==='object'?{id:item.value||item.id,label:item.label||item.value||item.id,enabled:false}:{id:item,label:item,enabled:false});
    return rows;
  }
  function collectionDraft(){
    if(!S.consoleChanges)S.consoleChanges=structuredClone(collectionFrom(S.cache.get('settings')));
    const draft=S.consoleChanges;draft.platforms||=[];draft.watch_accounts||=[];draft.topics||=[];return draft;
  }
  function collectionUI(data){
    const collection=S.consoleChanges||collectionFrom(data),platforms=platformRows({...data,console:collection}),accounts=Array.isArray(collection.watch_accounts)?collection.watch_accounts:[],topics=Array.isArray(collection.topics)?collection.topics:[],choices=platforms.map(item=>item.id||item.platform||item.value).filter(Boolean);
    return `<section class='settings-section'><h3>采集偏好 · WATCHLIST ONLY</h3><div class='setting-row' style='grid-template-columns:1fr'><div class='wait-principle'><strong>Open page required / 未自动驱动采集</strong><p>这里保存的是关注清单，不是平台 API。只有本机浏览器已登录并打开相应公开页面时，浏览器桥才能观察页面内容。</p></div></div><div class='setting-row'><div class='setting-copy'><strong>平台开关</strong><small>仅控制公开页面/本机已登录浏览器的采集偏好，不申请 API 权限。</small></div><div style='display:flex;flex-wrap:wrap;gap:6px'>${platforms.length?platforms.map(item=>{const id=item.id||item.platform||item.value;return `<label class='tag' style='cursor:pointer'><input type='checkbox' data-platform-key='${esc(id)}' ${item.enabled!==false?'checked':''}> ${esc(item.label||item.name||id)}</label>`;}).join(''):`<span class='dim'>后端尚未提供平台选项</span>`}</div></div>
      <div class='setting-row' style='grid-template-columns:1fr'><div class='setting-copy'><strong>关注名人 / 公开账号</strong><small>保存平台、display name、handle 与公开主页 URL；绝不保存密码、Cookie 或验证码。</small></div><div class='table-wrap'><table class='data-table'><thead><tr><th>启用</th><th>平台</th><th>显示名称</th><th>Handle</th><th>公开主页 URL</th><th></th></tr></thead><tbody>${accounts.length?accounts.map((account,index)=>`<tr><td><input type='checkbox' data-account-index='${index}' data-account-field='enabled' ${account.enabled!==false?'checked':''}></td><td>${choices.length?`<select class='control' data-account-index='${index}' data-account-field='platform'><option value=''>选择平台</option>${choices.map(name=>`<option value='${esc(name)}' ${String(account.platform)===String(name)?'selected':''}>${esc(name)}</option>`).join('')}</select>`:`<input class='control' data-account-index='${index}' data-account-field='platform' value='${esc(account.platform||'')}'>`}</td><td><input class='control' data-account-index='${index}' data-account-field='display_name' value='${esc(account.display_name||'')}' placeholder='公开名称'></td><td><input class='control' data-account-index='${index}' data-account-field='handle' value='${esc(account.handle||'')}' placeholder='@handle'></td><td><input class='control' data-account-index='${index}' data-account-field='url' value='${esc(account.url||'')}' placeholder='https://...'></td><td><button class='button' type='button' data-remove-account='${index}' aria-label='删除账号'>×</button></td></tr>`).join(''):`<tr><td colspan='6' class='dim'>尚未设置公开账号。不会自动填入演示账号。</td></tr>`}</tbody></table></div><div><button class='button' type='button' data-add-account>+ 添加公开账号</button></div></div>
      <div class='setting-row'><div class='setting-copy'><strong>主题词</strong><small>用于浏览器搜索与已采集内容筛选。避免输入密码、Token 或私人信息。</small></div><div><div style='display:grid;gap:6px'>${topics.length?topics.map((topic,index)=>`<div style='display:flex;gap:6px'><input class='control' data-topic-index='${index}' value='${esc(typeof topic==='object'?topic.value||topic.name:topic)}'><button class='button' type='button' data-remove-topic='${index}' aria-label='删除主题词'>×</button></div>`).join(''):`<span class='dim'>尚未设置主题词</span>`}</div><button class='button' type='button' data-add-topic style='margin-top:8px'>+ 添加主题词</button></div></div></section>`;
  }
  function settings(data){
    const fields=schemaFields(data).filter(safeSetting),groups=new Map();fields.forEach(field=>{const group=field.group||field.section||'Runtime';if(!groups.has(group))groups.set(group,[]);groups.get(group).push(field);});
    const sections=[...groups.entries()].map(([group,items])=>`<section class='settings-section'><h3>${esc(group)}</h3>${items.map(field=>{const path=field.path||field.key,value=fieldValue(data,field),description=field.description||field.help||(/max_concurrent_agents$/i.test(path)?'个人电脑安全范围 1–2；默认建议 2。':path),defaultValue=field.default===null?'继承上级设置':field.default,meta=[field.default!==undefined?`默认 ${defaultValue}${field.default!==null&&field.unit?` ${field.unit}`:''}`:'',field.min!==undefined||field.max!==undefined?`范围 ${field.min??'—'}–${field.max??'—'}${field.unit?` ${field.unit}`:''}`:'',field.restart_required?'需受监督重启':''].filter(Boolean).join(' · ');return `<label class='setting-row'><span class='setting-copy'><strong>${esc(field.label||field.name||path)}</strong><small>${esc(description)}</small>${meta?`<span class='setting-meta'>${esc(meta)}</span>`:''}</span>${fieldInput(field,value)}</label>`;}).join('')}</section>`).join('');
    const locked=data.live_locked===true||get(data,'locked.live.available')===false||get(data,'locked.live.enabled')===false,auth=data.authentication||{},agent=data.agent_runtime||{};
    const access=auth.required?'PUBLIC / PROTECTED':'LOCAL / LOOPBACK';
    const publicUrl=safeUrl(auth.public_url);
    return `${pageHead('Safe settings','只修改后端明确允许的轮询、预算、阈值与采集偏好；敏感字段不会呈现。')}<div class='settings-layout'><form id='settings-form'><div>${collectionUI(data)}${sections||empty('没有可编辑运行参数','后端设置 schema 未声明任何安全字段。','⚙')}</div><div class='settings-foot'><span id='settings-dirty-label'>${S.dirty?'有未保存更改':'没有未保存更改'}</span><button class='button button--primary' type='submit' ${S.dirty?'':'disabled'}>保存安全设置</button></div></form><aside class='stack'><div class='safety-box'><h3>${locked?'LIVE LOCKED / UNAVAILABLE':'LIVE LOCK STATE ERROR'}</h3><p>网页没有启用真实交易的字段或按钮。Live 必须经过独立审查，不属于本控制台。</p><ul><li>不显示 bridge token</li><li>不显示钱包、私钥或 seed</li><li>不保存账号密码与 Cookie</li><li>登录由你在本机浏览器完成</li></ul></div>${panel('Access & storage',`<div class='audit-detail'><div><span>ACCESS</span><strong>${esc(access)}</strong></div><div><span>AUTH MODE</span><strong>${esc(auth.mode||'loopback')}</strong></div><div><span>PUBLIC URL</span><strong>${publicUrl?`<a href='${esc(publicUrl)}' target='_blank' rel='noopener noreferrer'>打开受保护地址 ↗</a>`:'尚未创建'}</strong></div><div><span>CONSOLE STORAGE</span><strong>${esc(data.console_settings_storage||'local file')}</strong></div><div><span>AGENT PROVIDER</span><strong>${esc(agent.provider||'Local Codex CLI')}</strong></div><div><span>AGENT CREDENTIAL</span><strong>${esc(agent.credential_mode||'local signed-in session')}</strong></div><div><span>USES API KEY</span><strong>${agent.uses_api_key===false?'NO':agent.uses_api_key===true?'YES':'UNKNOWN'}</strong></div></div>`,'local control plane')}<div class='wait-principle'><strong>频率与并发边界</strong><p>频率使用后端给出的分钟/秒单位与安全范围。Agent 并发前端强制限制在 1–2，默认建议 2。运行参数更改需要受监督重启，Watchlist 更改不启动重复机器人。</p></div></aside></div>`;
  }
  function markDirty(){S.dirty=true;document.getElementById('settings-dirty-label')&&(document.getElementById('settings-dirty-label').textContent='有未保存更改');document.querySelector(`#settings-form button[type='submit']`)?.removeAttribute('disabled');schedule();}
  async function saveSettings(event){event.preventDefault();const button=event.submitter||event.target.querySelector(`button[type='submit']`);button.disabled=true;button.textContent='保存中…';const payload={updates:S.changes};if(S.consoleChanges)payload.console=S.consoleChanges;try{const result=await api('/settings',{method:'PATCH',body:JSON.stringify(payload)});S.changes={};S.consoleChanges=null;S.dirty=false;toast(result.restart_required?'设置已保存 · 运行参数需受监督重启':'采集偏好已保存','success');await loadPage();}catch(error){toast(`保存失败：${error.message||'未知错误'}`,'error');button.disabled=false;button.textContent='保存安全设置';}}

  const evidenceOf=detail=>list(get(detail,'evidence_timeline','observations','evidence','sources')||[],'evidence_timeline','observations','evidence');
  function evidenceTimeline(items){
    if(!items.length)return empty('没有证据明细','事件已存在，但 API 未返回 Observation 时间线。','·');
    return `<div class='evidence-chain' data-testid='evidence-timeline'>${items.map(item=>{
      const url=safeUrl(item.url),rawReasons=get(item,'rejection_reasons','exclusion_reason','ineligible_reason','rejection_reason'),reasons=Array.isArray(rawReasons)?rawReasons:rawReasons?[rawReasons]:[];
      const currentRole=item.role||'unknown',originalRole=get(item,'original_role','metadata.original_role');
      return `<article class='evidence-item'><div class='evidence-time'>observed<br>${esc(dateTime(item.observed_at))}</div><i class='evidence-node'></i><div class='evidence-body'><h4>${esc(get(item,'title','name','text')||'未命名观察')}</h4><div class='evidence-meta'>${originalRole&&originalRole!==currentRole?`${roleTag(originalRole)}<span class='dim'>→</span>`:''}${roleTag(currentRole)}${eligibilityTag(item)}<span class='tag'>${esc(get(item,'origin','source','source_kind')||'unknown origin')}</span>${item.freshness?`<span class='tag'>${esc(item.freshness)}</span>`:''}</div><p>published ${esc(dateTime(item.published_at))}<br>observed ${esc(dateTime(item.observed_at))}<br>ingested ${esc(dateTime(item.ingested_at))}${numeric(item.source_age_minutes)!==null?`<br>source age ${esc(num(item.source_age_minutes,' min'))}`:''}${reasons.length?`<br><span class='negative'>excluded: ${reasons.map(esc).join(' · ')}</span>`:''}</p>${url?`<a class='evidence-link' href='${esc(url)}' target='_blank' rel='noopener noreferrer'>打开原始来源 ↗</a>`:''}</div></article>`;
    }).join('')}</div>`;
  }
  function renderDetail(type,detail){
    if(type==='event'){
      const observations=evidenceOf(detail),items=list(get(detail,'decisions','candidates')||[],'decisions','candidates'),eligible=numeric(detail.eligible_source_count),total=numeric(get(detail,'source_count','sources_count')),contextOnly=eligible===0||detail.decision_eligible===false;
      if(contextOnly)detail={...detail,attention:null,source_count:null};E['drawer-title'].textContent=detail.title||`Event #${detail.id||'—'}`;
      E['drawer-content'].innerHTML=`<section class='detail-section'><h3>Signal dimensions</h3><div class='detail-summary'><div class='detail-stat'><small>ATTENTION</small><strong>${esc(scoreText(detail.attention))}</strong></div><div class='detail-stat'><small>FRESHNESS</small><strong>${esc(freshness(detail)===null?'—':freshness(detail).toFixed(0))}</strong></div><div class='detail-stat'><small>SOURCE BREADTH</small><strong>${esc(num(get(detail,'source_count','sources_count','independent_sources')))}</strong></div></div>${roles(detail)}</section><section class='detail-section'><h3>Decision eligibility</h3><div class='explain-box'>${esc(get(detail,'explanation','why','decision_explanation')||'后端未返回事件级解释。请逐条查看 evidence role 与 eligibility。')}</div></section><section class='detail-section'><h3>Observation timeline · published / observed / ingested</h3>${evidenceTimeline(observations)}</section><section class='detail-section'><h3>Candidate / decision chain</h3>${items.length?items.map(item=>{const [cls,label]=resultInfo(item.action),rejected=get(item,'rejected_reasons','rejection_reasons')||[];return `<div class='decision-card'><div class='decision-top'><h3>${esc(get(item,'token_symbol','token.symbol','token_id')||'Token')}</h3><span class='result-badge result-badge--${cls}'>${esc(label)}</span></div><div class='reason-list' style='margin-top:10px'>${rejected.map(reason=>`<span class='reason rejected'>${esc(reason)}</span>`).join('')||`<span class='reason'>无拒绝原因数据</span>`}</div></div>`;}).join(''):empty('尚无候选结论','策略还没有为此事件记录排名。','⌁')}</section>`;
      if(contextOnly)E['drawer-content'].querySelector('.detail-section')?.insertAdjacentHTML('afterbegin',`<div class='persistence-gap'><strong>CONTEXT ONLY</strong><span>${esc(num(eligible))} eligible / ${esc(num(total))} total origins · attention and freshness excluded</span></div>`);
    }else{
      const snap=get(detail,'snapshot','latest_snapshot')||detail;E['drawer-title'].textContent=`${detail.symbol||''} ${detail.name||'Token'}`.trim();E['drawer-content'].innerHTML=`<section class='detail-section'><h3>Token identity</h3><div class='detail-summary'><div class='detail-stat'><small>CHAIN</small><strong>${esc(String(detail.chain||'—').toUpperCase())}</strong></div><div class='detail-stat'><small>CONTRACT</small><strong title='${esc(detail.address||'')}'>${esc(shortAddress(detail.address))}</strong></div><div class='detail-stat'><small>CREATED</small><strong>${esc(dateTime(detail.created_at))}</strong></div></div></section><section class='detail-section'><h3>On-chain momentum · independent lane</h3><div class='detail-summary'><div class='detail-stat'><small>LIQUIDITY</small><strong>${esc(money(snap.liquidity_usd,true))}</strong></div><div class='detail-stat'><small>5M VOLUME</small><strong>${esc(money(snap.volume_5m_usd,true))}</strong></div><div class='detail-stat'><small>BUYS / SELLS</small><strong>${esc(num(snap.buys_5m))} / ${esc(num(snap.sells_5m))}</strong></div><div class='detail-stat'><small>MOMENTUM</small><strong>${esc(scoreText(get(detail,'momentum','momentum_score')))}</strong></div><div class='detail-stat'><small>PRICE</small><strong>${esc(price(snap.price_usd))}</strong></div><div class='detail-stat'><small>OBSERVED</small><strong>${esc(age(snap.observed_at))}</strong></div></div></section><section class='detail-section'><h3>Narrative evidence · two-way chain</h3><div class='explain-box'>Event → Token: ${esc(get(detail,'event_to_token','evidence.event_to_token','event_match_reason')||'无可用证据')}\n\nToken → Event: ${esc(get(detail,'token_to_event','evidence.token_to_event','context_result')||'尚未完成反查')}</div></section><section class='detail-section'><h3>Evidence timeline</h3>${evidenceTimeline(evidenceOf(detail))}</section>`;
    }
  }
  async function openDetail(type,id,push=false){
    if(!id)return;if(push){S.opener=document.activeElement;const target=`#/${S.page}/${type}/${encodeURIComponent(id)}`;if(location.hash!==target)history.pushState({detail:true},'',target);}S.detail=true;document.querySelector('.app-shell').inert=true;E['detail-drawer'].classList.add('is-open');E['detail-drawer'].setAttribute('aria-hidden','false');E['drawer-scrim'].hidden=false;E['drawer-eyebrow'].textContent=type==='event'?'EVENT EVIDENCE CHAIN':'TOKEN CONTEXT CHAIN';E['drawer-title'].textContent='加载详情…';E['drawer-content'].innerHTML=`<div class='initial-loader'><i></i><i></i><i></i></div>`;E['drawer-close'].focus({preventScroll:true});
    try{renderDetail(type,await api(`/${type==='event'?'events':'tokens'}/${encodeURIComponent(id)}`));}catch(error){const items=list(S.cache.get(type==='event'?'events':'tokens'),type==='event'?'events':'tokens'),fallback=items.find(item=>String(item.id||item.token_id||`${item.chain||''}:${item.address||''}`)===String(id));if(fallback){renderDetail(type,fallback);E['drawer-content'].insertAdjacentHTML('afterbegin',`<div class='status-pill status-pill--warn' style='margin-bottom:12px'>详情接口不可用 · 正在显示列表快照</div>`);}else E['drawer-content'].innerHTML=`<div class='error-state'><div><span class='empty-glyph'>!</span><h3>详情读取失败</h3><p>${esc(error.message)}</p></div></div>`;}
  }
  function closeDetail(historyAction=true){if(!S.detail)return;S.detail=false;document.querySelector('.app-shell').inert=false;E['detail-drawer'].classList.remove('is-open');E['detail-drawer'].setAttribute('aria-hidden','true');E['drawer-scrim'].hidden=true;const opener=S.opener;S.opener=null;if(opener?.isConnected)setTimeout(()=>opener.focus({preventScroll:true}),0);if(historyAction){if(history.state?.detail)history.back();else history.replaceState({},'',`#/${S.page}`);}}

  function bindSettings(){
    document.querySelectorAll('[data-setting-path]').forEach(input=>input.addEventListener('change',()=>{let value=input.value;if(input.dataset.valueType==='number')value=Number(value);if(input.dataset.valueType==='boolean')value=value==='true';if(/max_concurrent_agents$/i.test(input.dataset.settingPath))value=clamp(Math.round(Number(value)||2),1,2);setPath(S.changes,input.dataset.settingPath,value);markDirty();}));
    document.querySelectorAll('[data-platform-key]').forEach(input=>input.addEventListener('change',()=>{const draft=collectionDraft(),key=input.dataset.platformKey;if(Array.isArray(draft.platforms)){let item=draft.platforms.find(x=>String(x.id||x.platform||x.value||x)===key);if(item&&typeof item==='object')item.enabled=input.checked;else if(item!==undefined)draft.platforms[draft.platforms.indexOf(item)]={id:key,label:key,enabled:input.checked};else draft.platforms.push({id:key,label:key,enabled:input.checked});}else draft.platforms[key]=input.checked;markDirty();}));
    document.querySelectorAll('[data-account-index]').forEach(input=>input.addEventListener('change',()=>{const account=collectionDraft().watch_accounts[Number(input.dataset.accountIndex)];account[input.dataset.accountField]=input.type==='checkbox'?input.checked:input.value;markDirty();}));
    document.querySelectorAll('[data-topic-index]').forEach(input=>input.addEventListener('change',()=>{collectionDraft().topics[Number(input.dataset.topicIndex)]=input.value;markDirty();}));
    document.querySelectorAll('[data-remove-account]').forEach(button=>button.addEventListener('click',()=>{collectionDraft().watch_accounts.splice(Number(button.dataset.removeAccount),1);markDirty();render('settings',S.cache.get('settings'));}));
    document.querySelectorAll('[data-remove-topic]').forEach(button=>button.addEventListener('click',()=>{collectionDraft().topics.splice(Number(button.dataset.removeTopic),1);markDirty();render('settings',S.cache.get('settings'));}));
    document.querySelector('[data-add-account]')?.addEventListener('click',()=>{collectionDraft().watch_accounts.push({platform:'',handle:'',display_name:'',url:'',enabled:true});markDirty();render('settings',S.cache.get('settings'));});
    document.querySelector('[data-add-topic]')?.addEventListener('click',()=>{collectionDraft().topics.push('');markDirty();render('settings',S.cache.get('settings'));});
    document.getElementById('settings-form')?.addEventListener('submit',saveSettings);
  }
  function bind(page){
    E['page-content'].querySelectorAll('[data-open]').forEach(node=>{node.setAttribute('role','button');const activate=()=>openDetail(node.dataset.open,node.dataset.id,true);node.addEventListener('click',activate);node.addEventListener('keydown',event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();activate();}});});
    E['page-content'].querySelector(`[data-action='retry']`)?.addEventListener('click',()=>loadPage());
    if(page==='events'){const q=document.getElementById('event-query'),role=document.getElementById('event-role'),eligible=document.getElementById('event-eligibility');q?.addEventListener('input',()=>{S.filters.events.q=q.value;render(page,S.cache.get(page));});role?.addEventListener('change',()=>{S.filters.events.role=role.value;render(page,S.cache.get(page));});eligible?.addEventListener('change',()=>{S.filters.events.eligible=eligible.value;render(page,S.cache.get(page));});}
    if(page==='tokens'){const q=document.getElementById('token-query'),chain=document.getElementById('token-chain');q?.addEventListener('input',()=>{S.filters.tokens.q=q.value;render(page,S.cache.get(page));});chain?.addEventListener('change',()=>{S.filters.tokens.chain=chain.value;render(page,S.cache.get(page));});}
    if(page==='decisions')document.getElementById('decision-action')?.addEventListener('change',event=>{S.filters.decisions.action=event.target.value;render(page,S.cache.get(page));});
    if(page==='settings')bindSettings();
  }
  const parseRoute=()=>{const parts=location.hash.replace(/^#\/?/,'').split('/').filter(Boolean).map(decodeURIComponent);return {page:PAGES[parts[0]]?parts[0]:'overview',type:['event','token'].includes(parts[1])?parts[1]:null,id:parts[2]||null};};
  function activeNav(page){document.querySelectorAll('.nav-item[data-page]').forEach(button=>{const active=button.dataset.page===page;button.classList.toggle('is-active',active);active?button.setAttribute('aria-current','page'):button.removeAttribute('aria-current');});}
  function closeNav(){E.sidebar.classList.remove('is-open');E['sidebar-scrim'].classList.remove('is-open');E['mobile-menu'].setAttribute('aria-expanded','false');}
  async function route(){const parsed=parseRoute(),changed=S.page!==parsed.page;S.page=parsed.page;E['page-title'].textContent=PAGES[S.page][0];activeNav(S.page);closeNav();if(changed||!S.cache.has(S.page))await loadPage();else render(S.page,S.cache.get(S.page),{stale:S.errors.has(S.page)});if(parsed.type&&parsed.id)await openDetail(parsed.type,parsed.id);else closeDetail(false);}
  function navigate(page){if(page==='settings'||!S.dirty||confirm('放弃尚未保存的设置更改？')){if(page!=='settings'){S.dirty=false;S.changes={};S.consoleChanges=null;}location.hash=`#/${page}`;}}

  E['primary-nav'].addEventListener('click',event=>{const button=event.target.closest('[data-page]');if(button)navigate(button.dataset.page);});
  E['refresh-button'].addEventListener('click',()=>loadPage());
  E['mobile-menu'].addEventListener('click',()=>{E.sidebar.classList.add('is-open');E['sidebar-scrim'].classList.add('is-open');E['mobile-menu'].setAttribute('aria-expanded','true');});
  E['sidebar-scrim'].addEventListener('click',closeNav);E['drawer-close'].addEventListener('click',()=>closeDetail());E['drawer-scrim'].addEventListener('click',()=>closeDetail());
  window.addEventListener('hashchange',route);window.addEventListener('popstate',route);document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'&&!S.dirty)loadPage(true);});
  document.addEventListener('keydown',event=>{if(S.detail&&event.key==='Tab'){const focusable=[...E['detail-drawer'].querySelectorAll('button,a[href],input,select,textarea,[tabindex]:not([tabindex="-1"])')].filter(node=>!node.disabled);if(focusable.length){const first=focusable[0],last=focusable.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}return;}const editing=['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName);if(event.key==='Escape'){S.detail?closeDetail():closeNav();return;}if(editing||event.ctrlKey||event.metaKey||event.altKey)return;if(/^[1-9]$/.test(event.key)){const page=Object.keys(PAGES)[Number(event.key)-1];if(page)navigate(page);}if(event.key.toLowerCase()==='r')loadPage();});
  if(!location.hash)history.replaceState({},'','#/overview');route();
})();
