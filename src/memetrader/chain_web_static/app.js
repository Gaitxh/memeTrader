const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const money = (value, fallback = '—') => value === null || value === undefined ? fallback : `${Number(value) < 0 ? '−' : ''}$${Math.abs(Number(value)).toFixed(2)}`;
const tokenPrice = (value, fallback = '—') => {
  if(value === null || value === undefined || !Number.isFinite(Number(value)))return fallback;
  const n=Math.abs(Number(value));
  if(n===0)return '$0';
  if(n>=0.01)return `${Number(value)<0?'−':''}$${n.toFixed(4)}`;
  return `${Number(value)<0?'−':''}$${n.toPrecision(6).replace(/(?:\.0+|(?:(\.\d*?[1-9]))0+)$/,'$1')}`;
};
const percent = (value, fallback = '—') => value === null || value === undefined ? fallback : `${Number(value) >= 0 ? '+' : '−'}${Math.abs(Number(value) * 100).toFixed(1)}%`;
const shortToken = (value) => { const v=String(value||''); const a=v.includes(':')?v.split(':')[1]:v; return a.length>12?`${a.slice(0,5)}…${a.slice(-5)}`:a; };
const chainLabelForToken = (value) => ({solana:'Solana',bsc:'BSC',robinhood:'Robinhood Chain'})[String(value||'').split(':')[0].toLowerCase()]||'其他链';
const time = (value, date=false) => value ? new Date(value).toLocaleString('zh-CN',date?{hour12:false}:{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}) : '—';
const ageSeconds = (value) => {
  if(!value)return null;
  const seconds=(Date.now()-new Date(value).getTime())/1000;
  return Number.isFinite(seconds)&&seconds>=0?seconds:null;
};
const ageText = (value) => { const n=ageSeconds(value); if(n===null)return '从未'; if(n<60)return `${Math.round(n)} 秒前`; if(n<3600)return `${Math.round(n/60)} 分钟前`; return `${Math.round(n/3600)} 小时前`; };
const durationText = (openedAt,closedAt=null) => {
  const start=new Date(openedAt||'').getTime(),end=closedAt?new Date(closedAt).getTime():Date.now();
  if(!Number.isFinite(start)||!Number.isFinite(end)||end<start)return '—';
  const seconds=Math.floor((end-start)/1000),minutes=Math.floor(seconds/60),hours=Math.floor(minutes/60),days=Math.floor(hours/24);
  if(days)return `${days}天 ${hours%24}小时`;
  if(hours)return `${hours}小时 ${minutes%60}分钟`;
  if(minutes)return `${minutes}分钟 ${seconds%60}秒`;
  return `${seconds}秒`;
};
const pnlClass = (value) => value === null || value === undefined ? 'unknown' : Number(value) >= 0 ? 'pnl-positive' : 'pnl-negative';
const forwardOrder = (live) => live?.status === 'ACTIVE_FORWARD' ? 0 : 1;
const evidenceOrder = (live) => Number(live?.terminal||0)>0 ? 0 : Number(live?.open||0)>0 ? 1 : 2;
const tokenLink = (token, label=shortToken(token)) => `<button class="token-link" data-token="${esc(token)}" title="${esc(token)}">${esc(label)}</button>`;
const strategyName = (arm) => {
  const family=(universe?.families||[]).find(f=>(f.active_arm_ids||[]).includes(arm));
  return family?strategyLabel(family):(state?.strategies||[]).find(s=>s.arm_id===arm)?.name||arm||'—';
};
const outcomeCount = (account={}) => Number(account.closed_position_count||0)+Number(account.written_off_position_count||0);
const isMature = (strategy) => outcomeCount(strategy.account) >= 30;
const maturityText = (value) => ({mature:'成熟样本',provisional:'暂定样本',early:'早期样本',waiting:'等待机会'})[value]||'等待样本';
const maturityRank = (value) => ({mature:3,provisional:2,early:1,waiting:0})[value]??0;
const elapsedText = (seconds) => {
  const n=Number(seconds);
  if(!Number.isFinite(n)||n<0)return '—';
  if(n<3600)return `${Math.floor(n/60)} 分钟`;
  if(n<86400)return `${(n/3600).toFixed(1)} 小时`;
  return `${(n/86400).toFixed(1)} 天`;
};
const entryLabels={shadow_momentum:'链上动量达到历史门槛',two_way_route:'买卖双向路线通过',economic_route:'交易经济性通过',rug_safety:'买前安全检查通过',solana_focus:'Solana 精确池条件通过',broad_launch:'新币宽口径',flow_burst:'交易突然放量',reawakening:'沉寂后重新活跃',market_visible:'有池且价格可见',dex_visible_successor:'DexScreener 池与成交可见'};
const exitLabels={fast_escape:'快速止损止盈',balanced:'均衡退出',balanced_harvest:'均衡分批止盈',peak_guard:'高点回撤保护',postbuy_research:'买后信息辅助',principal_lock_runner:'本金回收目标＋趋势仓',flash_tail_first_mover:'早期爆发分档兑现',mature_continuity_control:'成熟延续快速退出',dynamic:'动态退出',dynamic_backoff:'动态退出与退避',dynamic_with_15m_deadline:'动态退出，最晚 15 分钟',dynamic_with_horizon_fallback:'动态退出，超时按固定周期',fixed:'固定周期退出',fixed_15m:'15 分钟退出',fixed_horizons:'分阶段固定退出',risk:'风险优先退出',profit:'利润优先退出',liquidity:'流动性异常退出',activity:'活跃度衰减退出',runner:'强势延续退出',flow:'资金流退出',trailing:'移动止盈',composite:'综合退出'};
const readable = (value,labels) => labels[value]||String(value||'未说明').replaceAll('_',' ');
const strategyIndex = (family) => {
  const found=(universe?.families||[]).indexOf(family);
  if(found>=0)return found+1;
  const explicit=Number(family?.display_index||0);
  return explicit>0?explicit:0;
};
const strategyLabel = (family) => `策略 ${String(strategyIndex(family)||'—').padStart(3,'0')}`;
const strategyFamilyForArm = (arm) => (universe?.families||[]).find(f=>(f.active_arm_ids||[]).includes(arm));
const strategyLabelForArm = (arm) => {
  const family=strategyFamilyForArm(arm);
  return family?strategyLabel(family):'历史策略';
};
const sideText = (side) => ({BUY:'买入',SELL:'卖出',WRITEOFF:'剩余仓位核销（无成交）'})[side]||'状态更新';
const exitActionText = (action) => ({HARD_STOP:'止损',FLOW_EXIT:'买盘转弱退出',TAKE_PROFIT_1:'第一档止盈',TRAILING_EXIT:'高点回撤退出'})[action]||'策略退出';
const queueStatusText = (status) => ({filled:'已卖出',quoting:'等待下一帧确认',exhausted:'池持续消失，已全损'})[status]||'处理中';
const sellabilityText = (status) => ({MARK_SELLABLE:'池与价格可见'})[status]||'等待新行情';
const reasonText = (reason='') => {
  const value=String(reason);
  if(value.includes('take_profit'))return '达到分批止盈条件';
  if(value.includes('trailing'))return '从高点回撤，保护利润';
  if(value.includes('hard_stop'))return '触发止损';
  if(value.includes('buy_ratio'))return '买盘占比持续走弱';
  if(value.includes('liquidity'))return '池流动性异常';
  if(value.includes('missing_over_60'))return '池和价格连续消失超过 1 分钟';
  if(value.includes('max_hold')||value.includes('fixed_horizon')||value.includes('time_exit'))return '达到持有时间';
  if(value.includes('market_paper_fill')||value.includes('dex_mark'))return '按当时公开市场价格模拟成交';
  if(value.includes('entry')||value.includes('broad_launch'))return '策略入场条件成立';
  return value?'策略条件触发':'—';
};
const sourceText = (source='') => ({pumpportal:'Pump.fun 实时流','pumpportal:create':'Pump.fun 新币流','dexscreener':'DexScreener 行情','dexscreener_discovery':'DexScreener 发现'})[source]||String(source||'公开数据源');
const positionValuationText = (position={}) => {
  const status=position.valuation_status;
  if(status==='complete_exact_jupiter')return '新鲜 Jupiter 可执行报价';
  if(status==='stale_exact_quote')return `当前未知 · 最近可执行 ${money(position.last_known_executable_value_usd)} · ${Math.round(Number(position.quote_age_seconds||0))} 秒前`;
  if(status==='unknown_no_route')return '当前未知 · 暂无可卖路线';
  if(status==='unknown_future_quote')return '当前未知 · 已拒绝未来时间报价';
  if(status==='unknown_error')return '当前未知 · 报价错误或无效';
  if(status==='awaiting_exact_quote')return '待可执行报价';
  return status||'未知';
};
const localSurfaceText = (position={}) => {
  const status=position.local_surface_status;
  if(!status)return '等待本池快照';
  const isPool=String(position.local_surface_type||'').startsWith('pumpswap');
  const surface=isPool?'路由验证 PumpSwap 池':'Pump 发射曲线';
  const raw=position.local_surface_min_quote_raw;
  const mint=position.local_surface_quote_mint;
  const amount=raw==null?'':mint==='So11111111111111111111111111111111111111112'?`${(Number(raw)/1e9).toFixed(6)} SOL`:`${raw} raw`;
  const dd=position.local_surface_drawdown;
  const suffix=dd==null?'':` · 较同数量高点 ${percent(dd)}`;
  const usd=position.local_surface_direct_estimated_recovery_usd;
  const recovery=usd==null?'':` · 估算最低回收 ${money(usd)}`;
  if(status==='LOCAL_SURFACE_CURRENT')return `${surface}全仓最低 ${amount}${recovery}${suffix}`;
  if(status==='LOCAL_SURFACE_DEGRADED')return `${surface}恶化 ${amount}${recovery}${suffix}`;
  if(status==='LOCAL_SURFACE_CRITICAL')return `${surface}严重恶化 ${amount}${recovery}${suffix}`;
  if(status==='LOCAL_NO_DIRECT_CAPACITY')return `${surface}本身不足以全仓卖出；不等于整个市场无法卖出`;
  if(status==='LOCAL_SELL_DISABLED')return 'PumpSwap 当前禁售；已提高 Jupiter 复核优先级';
  return `本池未知 · ${position.local_surface_reason||status}`;
};
let state = null;
let universe = null;
let selectedCanonical = null;
let liveTimer = null;
let fullTimer = null;
let strategyHistories = new Map();
let activeEpochVersion = null;
let wallets = null;
let walletRefreshAt = 0;
let showAllStrategies = false;
let showAllStrategyPool = false;
let lastPage = 'overview';
let activeTokenId = null;
let tokenDetailLoading = null;
let tokenDetailRefreshedAt = 0;
let errorTimer = null;
let errors = [];
let activeDrawerKind = null;

const liveTradingEnabled = () => state?.system?.live_locked===false||state?.system?.locked_by_config===false;
const positionPnl = (position={}) => {
  const realized=position.realized_pnl_usd==null?null:Number(position.realized_pnl_usd);
  const unrealized=position.status==='open'&&position.indicative_unrealized_pnl_usd!=null?Number(position.indicative_unrealized_pnl_usd):null;
  const total=position.status==='open'?(unrealized==null?null:Number(realized||0)+unrealized):realized;
  return {realized,unrealized,total};
};

const pageMeta = {
  overview:['实时总览','纯链上前向交易台'],
  strategies:['策略账户','全部策略实时结果'],
  trading:['交易执行','交易、订单与当前持仓'],
  discovery:['发现流程','Token 发现与入场漏斗'],
  system:['运行状态','采集与执行系统'],
  wallets:['钱包与实盘','钱包、策略绑定与实盘'],
  errors:['错误监督','错误与修复记录'],
};

function route(){
  const raw=(location.hash||'#/overview').slice(2);
  if(raw.startsWith('token/')){openToken(decodeURIComponent(raw.slice(6)),false);return;}
  const page=pageMeta[raw]?raw:'overview'; lastPage=page;
  $$('.page').forEach(el=>el.classList.toggle('active',el.dataset.page===page));
  $$('nav a').forEach(el=>el.classList.toggle('active',el.dataset.route===page));
  $('#page-kicker').textContent=pageMeta[page][0]; $('#page-title').textContent=pageMeta[page][1];
  clearTimeout(errorTimer);
  if(page==='errors')refreshErrors();
  closeDrawer(false);
}

function renderRuntime(data){
  const s=data.system||{}; const running=s.runtime_status==='running'; const el=$('#runtime');
  el.className=`runtime ${running?'running':'stale'}`;
  el.innerHTML=`<span class="pulse"></span><strong>${running?'系统运行中':'运行态陈旧'}</strong><small>${s.heartbeat_age_seconds==null?'无心跳':`${Math.round(s.heartbeat_age_seconds)} 秒前心跳`}</small>`;
  $('#freshness').textContent=`页面 ${time(data.generated_at)} 更新 · 可见时 5 秒、隐藏时 30 秒 · 后台持仓行情与退出优先`;
}

function currentStrategyForFamily(family){
  const strategies=state?.strategies||[];
  return (family?.active_arm_ids||[]).map(arm=>strategies.find(s=>s.arm_id===arm)).find(Boolean)||null;
}

function selectedStrategyArm(){
  if(lastPage!=='strategies'||!selectedCanonical)return null;
  const family=(universe?.families||[]).find(item=>(item.canonical_id||item.behavior_contract_hash)===selectedCanonical);
  return currentStrategyForFamily(family)?.arm_id||(family?.active_arm_ids||[])[0]||null;
}

function liveMetricForFamily(family){
  const strategy=currentStrategyForFamily(family), account=strategy?.account||{};
  const open=Number(account.open_position_count||0);
  const pnl=account.capital_neutral_total_pnl_usd ?? account.indicative_total_pnl_usd ?? account.executable_total_pnl_usd;
  const unrealizedPnl=account.capital_neutral_unrealized_pnl_usd ?? account.indicative_unrealized_pnl_usd ?? account.executable_unrealized_pnl_usd;
  const terminal=outcomeCount(account), wins=Number(account.win_count||0);
  return {
    strategy,
    pnl,
    open,
    terminal,
    wins,
    winRate:terminal?wins/terminal:null,
    realizedPnl:(account.capital_neutral_realized_pnl_usd??account.realized_pnl_usd)==null?null:Number(account.capital_neutral_realized_pnl_usd??account.realized_pnl_usd),
    unrealizedPnl:unrealizedPnl==null?null:Number(unrealizedPnl),
    profitLossRatio:account.profit_loss_ratio,
    profitFactor:account.profit_factor,
    profitFactorStatus:account.profit_factor_status,
    expectancy:account.expectancy_usd,
    maxDrawdown:account.max_drawdown_usd,
    maxDrawdownFraction:account.max_drawdown_fraction,
    tailReturn:account.tail_return_usd,
    metricSampleCount:Number(account.metric_sample_count||0),
    metricSampleStatus:account.metric_sample_status,
    maturity:strategy?.maturity||(
      account.metric_sample_status==='sufficient_sample'?'mature':terminal?'early':'waiting'
    ),
    forwardAgeSeconds:Number(strategy?.forward_age_seconds||0),
    opportunityCount:Number(strategy?.eligible_opportunity_count||0),
    status:family?.realtime_state||(strategy?'ACTIVE_FORWARD':'FROZEN_HISTORY'),
    updatedAt:account.recorded_at||state?.generated_at||universe?.generated_at,
  };
}

function strategyMetrics(live){
  const value=(v,format=money)=>v==null?'—':format(v);
  const sample=live.metricSampleCount?`${live.metricSampleCount} 笔${live.metricSampleStatus==='insufficient_sample'?'，样本不足':''}`:'暂无闭仓样本';
  const factor=live.profitFactor==null?(live.profitFactorStatus==='no_losses'?'暂无亏损样本':'—'):Number(live.profitFactor).toFixed(2);
  const drawdown=live.maxDrawdown==null?'—':`${money(live.maxDrawdown)}${live.maxDrawdownFraction==null?'':` / ${(Number(live.maxDrawdownFraction)*100).toFixed(1)}%`}`;
  return `<small class="strategy-metrics">已实现 ${value(live.realizedPnl)} · 盈亏比 ${value(live.profitLossRatio, v=>Number(v).toFixed(2))} · 收益因子 ${factor} · 单笔期望 ${value(live.expectancy)} · 实时曲线最大回撤 ${drawdown} · 最差 10% 均值 ${value(live.tailReturn)}（${sample}）</small>`;
}

function fidelityLabel(family){
  const value=family?.fidelity_status||family?.realtime_state;
  return ({REPLICA_ELIGIBLE:'原历史规则',REPLICA_WITH_ENGINEERING_CORRECTION:'历史规则·统一成交口径',DEXSCREENER_SUCCESSOR:'DexScreener 新前向策略',ADDITIVE_FORWARD:'新增前向策略',COVERAGE_UNAVAILABLE:'缺少原始证据，未交易',ACTIVE_FORWARD:'前向运行',FROZEN_HISTORY:'仅历史记录'})[value]||'待核验';
}

function ingestStrategyHistory(data){
  const version=String(data?.version||'');
  if(activeEpochVersion!==null&&version&&version!==activeEpochVersion){
    strategyHistories=new Map();
  }
  if(version)activeEpochVersion=version;
  (data?.strategies||[]).forEach(strategy=>{
    const key=String(strategy.arm_id||'');
    if(!key)return;
    const history=strategyHistories.get(key)||[];
    (strategy.curve||[]).forEach(point=>{
      const value=point.capital_neutral_total_pnl_usd ?? point.total_pnl_usd ?? point.indicative_total_pnl_usd ?? point.executable_total_pnl_usd;
      const ts=new Date(point.recorded_at||'').getTime();
      if(value==null||!Number.isFinite(ts)||!Number.isFinite(Number(value)))return;
      if(!history.some(item=>item.ts===ts))history.push({ts,value:Number(value)});
    });
    history.sort((a,b)=>a.ts-b.ts);
    strategyHistories.set(key,history.slice(-600));
  });
}

function strategySparkline(strategy){
  const points=(strategyHistories.get(String(strategy?.arm_id||''))||[]).slice(-40);
  if(!points.length)return '<span class="curve-wait">等待曲线</span>';
  const values=points.map(point=>point.value),range=[0,...values],min=Math.min(...range),max=Math.max(...range),span=Math.max(1,max-min);
  const d=points.map((point,index)=>`${index?'L':'M'}${(index/Math.max(1,points.length-1)*104).toFixed(1)},${(30-(point.value-min)/span*28-1).toFixed(1)}`).join(' ');
  const pnl=points.at(-1).value;
  return `<svg class="strategy-sparkline ${pnlClass(pnl)}" viewBox="0 0 104 30" role="img" aria-label="策略账户实时曲线"><path d="${d}"/></svg>`;
}

function renderStrategyEquityChart(strategy){
  const svg=$('#strategy-equity-chart'),note=$('#strategy-equity-note');
  if(!svg||!note)return;
  const points=(strategyHistories.get(String(strategy?.arm_id||''))||[]).slice(-300);
  if(!points.length){svg.innerHTML='<text class="chart-label" x="180" y="82">等待首个 PNL 记录</text>';note.textContent='等待首个策略盈亏快照';return;}
  const W=720,H=180,pad={l:52,r:18,t:12,b:26},values=points.map(point=>point.value),range=[0,...values],min=Math.min(...range),max=Math.max(...range),span=Math.max(1,max-min),t0=points[0].ts,t1=Math.max(t0+1000,points.at(-1).ts);
  const x=ts=>pad.l+(ts-t0)/(t1-t0)*(W-pad.l-pad.r),y=value=>pad.t+(max-value)/span*(H-pad.t-pad.b);
  let html='';
  for(let i=0;i<4;i++){const value=min+span*i/3,yy=y(value);html+=`<line class="grid-line" x1="${pad.l}" y1="${yy}" x2="${W-pad.r}" y2="${yy}"/><text class="chart-label" x="2" y="${yy+4}">$${value.toFixed(0)}</text>`;}
  const d=points.map((point,index)=>`${index?'L':'M'}${x(point.ts).toFixed(1)},${y(point.value).toFixed(1)}`).join(' ');
  html+=`<line class="base-line" x1="${pad.l}" y1="${y(0)}" x2="${W-pad.r}" y2="${y(0)}"/>`;
  html+=`<path class="equity-line strategy-detail-line" d="${d}"/><circle class="chart-last" cx="${x(points.at(-1).ts)}" cy="${y(points.at(-1).value)}" r="4"/>`;
  svg.innerHTML=html;
  const latest=points.at(-1),pnl=latest.value;
  note.innerHTML=`累计总 PNL <strong class="${pnlClass(pnl)}">${money(pnl)}</strong> · 后端记录 ${time(latest.ts,true)}`;
}

function classificationLabel(value){
  return ({
    SUPERSEDED_REUSABLE:'可复用历史基线',
    RETIRED_ECONOMIC_FAILURE:'经济结果失败',
    RETIRED_ENGINEERING_FAILURE:'工程结果失败',
    INVALID_OR_UNCOMPARABLE:'不可比较',
    SHADOW_CANDIDATE:'Shadow 候选',
    PAPER:'Paper 候选',
  })[value]||value||'未分类';
}

function renderUniverseDetail(family){
  const target=$('#strategy-detail'); if(!target||!family)return;
  selectedCanonical=family.canonical_id||family.behavior_contract_hash;
  const live=liveMetricForFamily(family), members=family.members||[], strategy=live.strategy||{};
  const trades=(strategy.trades||[]).slice(0,30);
  const positions=(strategy.positions||[]).slice(0,30);
  const canRun=live.status==='ACTIVE_FORWARD',notional=state?.definition?.policy_notional_usd,slippageBps=state?.definition?.slippage_bps;
  const positionCards=positions.map(item=>{
    const pnl=positionPnl(item);
    const records=trades.filter(trade=>String(trade.shadow_cohort_id||'')===String(item.shadow_cohort_id||'')&&trade.token_id===item.token_id);
    return `<article class="position-record"><div class="position-record-head"><div><span class="status-pill ${esc(item.status)}">${item.status==='open'?'持有中':item.status==='closed'?'已卖出':'已核销'}</span>${tokenLink(item.token_id)}</div><small>${time(item.opened_at,true)} 开仓</small></div><div class="position-pnl-grid"><span>持仓时长<strong>${esc(durationText(item.opened_at,item.closed_at))}</strong></span><span>未实现 PNL<strong class="${pnlClass(pnl.unrealized)}">${pnl.unrealized==null?'—':money(pnl.unrealized)}</strong></span><span>已实现 PNL<strong class="${pnlClass(pnl.realized)}">${pnl.realized==null?'—':money(pnl.realized)}</strong></span><span>总 PNL<strong class="${pnlClass(pnl.total)}">${pnl.total==null?'价格待更新':money(pnl.total)}</strong></span></div><small class="position-note">${item.status==='open'?(item.indicative_value_usd==null?'当前没有有效价格，不按 0 计':`当前价值 ${money(item.indicative_value_usd)}`):esc(reasonText(item.close_reason))}</small><div class="position-transactions">${records.length?records.map(record=>`<p><time>${time(record.created_at)}</time><strong>${esc(sideText(record.side))}</strong><span>${record.side==='BUY'?`投入 ${money(Math.abs(Number(record.net_cash_flow_usd??record.gross_usd)))}`:`回收 ${money(record.gross_usd)} · PNL ${money(record.realized_pnl_usd)}`}</span></p>`).join(''):'<p class="empty">当前返回范围内没有该仓位的交易记录</p>'}</div></article>`;
  }).join('');
  target.innerHTML=`<div class="detail-title"><div><p class="eyebrow">独立策略账户</p><h2>${esc(strategyLabel(family))}</h2><small class="strategy-identity">唯一编号 #${String(strategyIndex(family)).padStart(3,'0')}</small></div><span class="contract-state ${canRun?'active_forward':'retry'}">${esc(fidelityLabel(family))}</span></div>
    <p>${esc(readable(family.entry_family,entryLabels))}入场，${esc(readable(family.exit_family,exitLabels))}。</p>
    <div class="detail-live-grid"><div><span>累计总 PNL</span><strong class="${pnlClass(live.pnl)}">${live.pnl==null?'价格待更新':money(live.pnl)}</strong></div><div><span>已实现 PNL</span><strong class="${pnlClass(live.realizedPnl)}">${live.realizedPnl==null?'—':money(live.realizedPnl)}</strong></div><div><span>未实现 PNL</span><strong class="${pnlClass(live.unrealizedPnl)}">${live.unrealizedPnl==null?'价格待更新':money(live.unrealizedPnl)}</strong></div><div><span>样本成熟度</span><strong>${esc(maturityText(live.maturity))}</strong><small>运行 ${esc(elapsedText(live.forwardAgeSeconds))}</small></div></div>
    <section class="contract-section"><h3>累计 PNL 实时曲线</h3><p id="strategy-equity-note">等待首个策略盈亏快照</p><svg id="strategy-equity-chart" class="strategy-equity-chart" viewBox="0 0 720 180" role="img" aria-label="当前策略累计盈亏实时曲线"></svg></section>
    <section class="contract-section"><h3>入场规则</h3><p>${esc(readable(strategy.source_entry_family||family.entry_family,entryLabels))}</p><small>只使用当时已经采集到的 Token、交易量、价格与池信息，不使用之后才出现的数据。</small></section>
    <section class="contract-section"><h3>复刻状态</h3><p>${esc(fidelityLabel(family))}</p><small>${esc(family.fidelity_note||'等待历史合同核验')}</small></section>
    <section class="contract-section"><h3>退出规则</h3><p>${esc(readable(family.exit_family,exitLabels))}</p><small>最长持有 ${Number(strategy.max_hold_minutes||240)} 分钟；${strategy.hard_stop_return==null?'无额外固定止损':`回撤到 ${percent(strategy.hard_stop_return)} 触发止损`}。池和价格连续不可见超过 1 分钟时，剩余仓位按全部亏损处理。</small></section>
    <section class="contract-section"><h3>当前结果</h3><p>已观察 ${live.opportunityCount} 个符合策略条件的机会，已完成 ${live.terminal} 笔，其中盈利 ${live.wins} 笔，胜率 ${live.winRate==null?'等待样本':percent(live.winRate)}；当前持仓 ${live.open} 笔。</p><small>研究资金不因虚拟现金不足阻断新机会；单笔仍为 ${notional==null?'—':`${money(notional)} USDC`}，买卖各按 ${slippageBps==null?'—':`${Number(slippageBps)/100}%`} 滑点。</small></section>
    <section class="contract-section"><h3>最近操作记录</h3><div class="strategy-log">${trades.length?trades.map(item=>`<button data-token="${esc(item.token_id)}"><time>${time(item.created_at)}</time><strong>${esc(sideText(item.side))}</strong><span>${esc(shortToken(item.token_id))}</span><em class="${pnlClass(item.realized_pnl_usd)}">${item.side==='BUY'?money(item.gross_usd):money(item.realized_pnl_usd)}</em><small>${esc(reasonText(item.reason))}</small></button>`).join(''):'<p class="empty">新前向版本尚无操作</p>'}</div></section>
    <section class="contract-section"><h3>仓位、持仓时长与交易记录</h3><div class="position-records">${positionCards||'<p class="empty">当前没有仓位记录</p>'}</div></section>
    <section class="contract-section"><h3>历史来源</h3><p>这个策略由 ${members.length} 个历史版本中的相同行为归纳而来。</p><small>历史总计 ${family.historical_terminal_projected_sum||0} 个完成样本，描述性 PNL ${money(family.historical_realized_pnl_projected_sum_usd)}；当前策略从真实部署时间开始累计，不回填部署前事件。</small></section>`;
  renderStrategyEquityChart(strategy);
  $$('#canonical-universe tbody tr').forEach(row=>row.classList.toggle('selected',row.dataset.canonical===selectedCanonical));
}

function renderUniverse(){
  if(!universe||universe.status!=='ok')return;
  const families=universe.families||[];
  const active=families.filter(f=>liveMetricForFamily(f).status==='ACTIVE_FORWARD').length;
  const replicas=families.filter(f=>f.fidelity_status==='REPLICA_WITH_ENGINEERING_CORRECTION').length;
  const successors=families.filter(f=>f.fidelity_status==='DEXSCREENER_SUCCESSOR').length;
  const inactive=Math.max(0,families.length-active);
  const unconstrained=state?.system?.capital_model==='unconstrained_research_notional'||state?.capital_model==='unconstrained_research_notional';
  $('#universe-summary').innerHTML=[
    ['策略',families.length,'每个策略独立决策、持仓和结果'],
    ['前向运行',active,inactive?`${inactive} 个当前未运行`:`${replicas} 个历史规则 · ${successors} 个 DexScreener 继承策略`],
    ['研究资金',unconstrained?'机会不受余额阻断':'原现金限制仍生效',unconstrained?'单笔规模和风险规则保持不变':'等待未来激活边界'],
    ['行情采集','共享一次',`同一个 Token 不会按 ${families.length} 个策略重复访问`],
  ].map(([k,v,n])=>`<article class="summary-card"><span>${esc(k)}</span><strong>${esc(v)}</strong><small>${esc(n)}</small></article>`).join('');
  const q=($('#universe-search')?.value||'').trim().toLowerCase(), sort=$('#universe-sort')?.value||'maturity';
  const rows=families.filter(f=>{
    const hay=[readable(f.entry_family,entryLabels),readable(f.exit_family,exitLabels)].join(' ').toLowerCase();
    return !q||hay.includes(q);
  }).sort((a,b)=>{
    const la=liveMetricForFamily(a),lb=liveMetricForFamily(b);
    if(sort==='maturity')return maturityRank(lb.maturity)-maturityRank(la.maturity)||Number(lb.expectancy??-Infinity)-Number(la.expectancy??-Infinity)||Number(lb.pnl??-Infinity)-Number(la.pnl??-Infinity)||strategyIndex(a)-strategyIndex(b);
    if(sort==='live_pnl')return Number(lb.pnl??-Infinity)-Number(la.pnl??-Infinity)||strategyIndex(a)-strategyIndex(b);
    if(sort==='realized_pnl')return Number(lb.realizedPnl??-Infinity)-Number(la.realizedPnl??-Infinity)||strategyIndex(a)-strategyIndex(b);
    if(sort==='terminal')return Number(lb.terminal)-Number(la.terminal)||strategyIndex(a)-strategyIndex(b);
    if(sort==='win_rate')return Number(lb.winRate??-1)-Number(la.winRate??-1)||strategyIndex(a)-strategyIndex(b);
    return strategyIndex(a)-strategyIndex(b);
  });
  $('#universe-count').textContent=`显示 ${rows.length} / ${families.length} · ${time(state?.generated_at||universe.generated_at)} 刷新`;
  $('#universe-refresh').textContent=`${active} 个前向运行 · ${replicas} 个历史规则 · ${successors} 个 DexScreener 继承策略`;
  $('#canonical-universe tbody').innerHTML=rows.map((f,index)=>{const live=liveMetricForFamily(f),id=f.canonical_id||f.behavior_contract_hash;return `<tr class="strategy-row ${selectedCanonical===id?'selected':''}" data-canonical="${esc(id)}"><td>${index+1}</td><td><strong>${esc(strategyLabel(f))}</strong><small>唯一编号 #${String(strategyIndex(f)).padStart(3,'0')}</small></td><td><span class="status-pill ${live.status==='ACTIVE_FORWARD'?'closed':'retry'}">${esc(fidelityLabel(f))}</span></td><td><span class="maturity ${esc(live.maturity)}">${esc(maturityText(live.maturity))}</span><small>运行 ${esc(elapsedText(live.forwardAgeSeconds))}</small></td><td>${esc(readable(f.entry_family,entryLabels))}</td><td>${esc(readable(f.exit_family,exitLabels))}</td><td class="${pnlClass(live.pnl)}">${live.pnl==null?'价格待更新':money(live.pnl)}${strategyMetrics(live)}</td><td class="${pnlClass(live.realizedPnl)}">${live.realizedPnl==null?'—':money(live.realizedPnl)}</td><td class="${pnlClass(live.unrealizedPnl)}">${live.unrealizedPnl==null?'价格待更新':money(live.unrealizedPnl)}</td><td>${strategySparkline(live.strategy)}</td><td>${live.open}</td><td>${live.terminal}</td><td>${live.winRate==null?'等待样本':percent(live.winRate)}</td><td>${time(live.updatedAt)}</td></tr>`;}).join('')||'<tr><td colspan="14" class="empty">没有符合当前筛选条件的策略</td></tr>';
  $$('#canonical-universe tbody tr[data-canonical]').forEach(row=>row.addEventListener('click',()=>{const family=families.find(f=>(f.canonical_id||`C-${f.behavior_contract_hash}`)===row.dataset.canonical);renderUniverseDetail(family);refreshLive();}));
  const selected=families.find(f=>(f.canonical_id||f.behavior_contract_hash)===selectedCanonical)||rows[0]||families[0];
  if(selected)renderUniverseDetail(selected);
}

function renderDiscoveryBeacon(data){
  const latest=data.discovery?.latest_at, age=ageSeconds(latest), active=age!==null&&age<=90;
  $('#discovery-beacon').classList.toggle('active',active);
  $('#discovery-state').textContent=active?'正在发现 Token':'等待下一轮发现';
  $('#discovery-age').textContent=latest?`最近发现 ${ageText(latest)}`:'尚无新币发现记录';
}

function renderSummary(data, strategies){
  const accounts=strategies.map(s=>s.account||{}), open=accounts.reduce((n,a)=>n+Number(a.open_position_count||0),0);
  const openTokens=Number(data.system?.unique_held_token_count??new Set(strategies.flatMap(s=>(s.positions||[]).filter(position=>position.status==='open').map(position=>position.token_id)).filter(Boolean)).size);
  const marked=accounts.reduce((n,a)=>n+Number(a.indicative_position_count||0),0), missing=Math.max(0,open-marked);
  const outcomes=accounts.reduce((n,a)=>n+outcomeCount(a),0), pending=Number(data.system?.pending_exit_quotes||0);
  const tokens=data.discovery?.tokens||[], fresh=tokens.filter(t=>ageSeconds(t.observed_at)<=300).length;
  const s=data.system||{},storage=s.storage||{},gb=n=>Number.isFinite(Number(n))?(Number(n)/1073741824).toFixed(1)+' GB':'—';
  const active=(universe?.families||[]).filter(f=>liveMetricForFamily(f).status==='ACTIVE_FORWARD').length;
  const replicas=(universe?.families||[]).filter(f=>f.fidelity_status==='REPLICA_WITH_ENGINEERING_CORRECTION').length;
  const successors=(universe?.families||[]).filter(f=>f.fidelity_status==='DEXSCREENER_SUCCESSOR').length;
  const walletsNow=wallets?.wallets||[],liveWallets=walletsNow.filter(item=>item.enabled).length;
  const errorSummary=data.error_summary||{},openErrors=Number(errorSummary.open||0),highErrors=Number(errorSummary.high||0);
  $('#summary-grid').innerHTML=[
    ['系统运行',s.runtime_status==='running'?'正常':'异常',s.heartbeat_at?`最近心跳 ${ageText(s.heartbeat_at)}`:'尚无运行心跳',s.runtime_status==='running'],
    ['Token 发现',fresh? '正常':'等待新币',`近 5 分钟 ${fresh} 个 · 最近 ${ageText(data.discovery?.latest_at)}`,Boolean(data.discovery?.latest_at)],
    ['策略账户',`${active} 个前向运行`,`${replicas} 个历史规则 · ${successors} 个 Dex 继承 · 开放仓位 ${open} · 已完成 ${outcomes}`,active>0],
    ['开放仓 / 不重复 Token',`${open} / ${openTokens}`,missing?`${marked} 个有价格 · ${missing} 个等待恢复`:'策略仓位数 / 去重后持币数',missing===0],
    ['卖出与核销',pending?`${pending} 笔待处理`:'队列正常',`连续无池/价格超过 1 分钟才全损`,pending===0],
    ['钱包实盘',walletsNow.length?`${liveWallets} / ${walletsNow.length} 运行`:'尚未接入','每个钱包独立绑定一个策略',true],
    ['错误监督',openErrors?`${openErrors} 项待处理`:'没有未结错误',highErrors?`${highErrors} 项严重错误`:'运行报错按时间归档',openErrors===0],
    ['本地数据',gb(storage.database_bytes),`E 盘剩余 ${gb(storage.free_bytes)}`,Number(storage.free_bytes||0)>10737418240],
  ].map(([k,v,n,ok])=>`<article class="summary-card status-summary ${ok?'ok':'attention'}"><span>${esc(k)}</span><strong>${esc(v)}</strong><small>${esc(n)}</small></article>`).join('');
}

function renderOverviewStrategies(){
  const target=$('#overview-strategies tbody');
  if(!target||!universe)return;
  const ranked=(universe.families||[]).map(f=>({family:f,live:liveMetricForFamily(f)})).sort((a,b)=>maturityRank(b.live.maturity)-maturityRank(a.live.maturity)||Number(b.live.expectancy??-Infinity)-Number(a.live.expectancy??-Infinity)||Number(b.live.pnl??-Infinity)-Number(a.live.pnl??-Infinity)||strategyIndex(a.family)-strategyIndex(b.family));
  target.innerHTML=ranked.map((item,index)=>`<tr class="strategy-row" data-overview-strategy="${esc(item.family.canonical_id||item.family.behavior_contract_hash)}"><td>${index+1}</td><td><strong>${esc(strategyLabel(item.family))}</strong><small>唯一编号 #${String(strategyIndex(item.family)).padStart(3,'0')} · ${esc(readable(item.family.entry_family,entryLabels))} → ${esc(readable(item.family.exit_family,exitLabels))}</small></td><td><span class="status-pill ${item.live.status==='ACTIVE_FORWARD'?'closed':'retry'}">${esc(fidelityLabel(item.family))}</span></td><td><span class="maturity ${esc(item.live.maturity)}">${esc(maturityText(item.live.maturity))}</span><small>运行 ${esc(elapsedText(item.live.forwardAgeSeconds))}</small></td><td class="${pnlClass(item.live.pnl)}">${item.live.pnl==null?'价格待更新':money(item.live.pnl)}</td><td class="${pnlClass(item.live.realizedPnl)}">${item.live.realizedPnl==null?'—':money(item.live.realizedPnl)}</td><td class="${pnlClass(item.live.unrealizedPnl)}">${item.live.unrealizedPnl==null?'价格待更新':money(item.live.unrealizedPnl)}</td><td>${strategySparkline(item.live.strategy)}</td><td>${item.live.open}</td><td>${item.live.terminal}</td><td>${item.live.winRate==null?'等待样本':percent(item.live.winRate)}</td><td>${time(item.live.updatedAt)}</td></tr>`).join('');
  $$('[data-overview-strategy]').forEach(row=>row.addEventListener('click',()=>{
    selectedCanonical=row.dataset.overviewStrategy;
    location.hash='#/strategies';
    renderUniverse();
  }));
}

function renderLeaders(data){
  const ranked=(universe?.families||[]).map(f=>({family:f,live:liveMetricForFamily(f)})).filter(x=>x.live.status==='ACTIVE_FORWARD'&&x.live.terminal>0&&x.live.pnl!=null).sort((a,b)=>maturityRank(b.live.maturity)-maturityRank(a.live.maturity)||Number(b.live.expectancy??-Infinity)-Number(a.live.expectancy??-Infinity)||Number(b.live.pnl)-Number(a.live.pnl)).slice(0,3);
  $('#leaders').innerHTML=ranked.length?ranked.map((x,index)=>`<article class="leader-card"><div><span class="stage-no">第 ${index+1} 名</span><span class="maturity ${esc(x.live.maturity)}">${esc(maturityText(x.live.maturity))}</span></div><h3>${esc(strategyLabel(x.family))}</h3><strong class="leader-equity ${pnlClass(x.live.pnl)}">${money(x.live.pnl)}</strong><p>累计总 PNL · ${x.live.open} 个持仓 · 胜率 ${x.live.winRate==null?'等待样本':percent(x.live.winRate)}</p><small>${esc(readable(x.family.entry_family,entryLabels))} → ${esc(readable(x.family.exit_family,exitLabels))}</small></article>`).join(''):'<div class="empty">等待策略终局样本</div>';
}

function renderStrategyRegistry(data){
  const all=data.strategy_groups||data.strategy_registry||[], stats=data.strategy_registry_stats||{}, items=showAllStrategies?all:all.filter(s=>s.default_visible!==false);
  $('#strategy-registry tbody').innerHTML=items.length?items.map(s=>`<tr><td>${esc(s.lineage_role)}<small>族 ${esc(s.family_hash||'—')}</small></td><td>${esc(s.status)}</td><td>${esc(s.name)}${Number(s.member_count||1)>1?`<small>合并展示 ${s.member_count} 个完全等价历史策略</small>`:''}</td><td>${esc(s.definition_version)}${Number(s.member_count||1)>1?`<small>${esc((s.member_versions||[]).join(' · '))}</small>`:''}</td><td>${s.admitted||0} / ${s.rejected||0}</td><td>${s.terminal_count||0}</td><td class="${pnlClass(s.realized_pnl_usd)}">${money(s.realized_pnl_usd)}</td><td>${s.rank_eligible?esc(s.evidence_status):'保留但不排名'}</td></tr>`).join(''):'<tr><td colspan="8" class="empty">策略注册表尚未产生记录</td></tr>';
  const note=$('#strategy-registry-note'); if(note)note.textContent=`原始 ${stats.raw_strategy_count||all.length} 条 · 行为等价归并后 ${stats.display_strategy_count||all.length} 条 · 默认保留 ${stats.retained_count||0} 条 · 退役 ${stats.retired_count||0} 条 · 无终局结果 ${stats.unscored_count||0} 条`;
  const toggle=$('#toggle-strategies'); if(toggle)toggle.textContent=showAllStrategies?'仅显示保留策略':'显示全部历史';
}

function renderStrategyPool(data){
  const all=data.strategy_groups||data.strategy_registry||[], stats=data.strategy_registry_stats||{};
  const items=showAllStrategyPool?all:all.filter(s=>s.default_visible!==false);
  const current=all.filter(s=>s.current).length;
  $('#strategy-pool-summary').innerHTML=[
    ['历史策略原始记录',stats.raw_strategy_count||all.length,'所有已注册学习版本均保留'],
    ['行为归并后',stats.display_strategy_count||all.length,'完全相同行为只展示一个代表策略'],
    ['默认保留',stats.retained_count||0,'运行中、历史盈利或仍在学习'],
    ['当前前向运行',current,'只是完整策略池中的当前实验批次'],
  ].map(([k,v,n])=>`<article class="summary-card"><span>${esc(k)}</span><strong>${esc(v)}</strong><small>${esc(n)}</small></article>`).join('');
  $('#strategy-pool tbody').innerHTML=items.length?items.map(s=>`<tr><td><span class="status-pill ${s.current?'closed':s.status==='RETIRED_UNDERPERFORMER'?'written_off':'retry'}">${s.current?'当前运行':esc(s.status)}</span></td><td><strong>${esc(s.name)}</strong><small>${esc(s.description||'')}</small></td><td>${esc(s.lineage_role)}<small>行为 ${esc(s.behavior_hash||'—')} · 族 ${esc(s.family_hash||'—')}</small></td><td>${esc(s.entry_family||'—')}<small>${esc(s.exit_family||'—')}</small></td><td>${s.member_count||1} 条<small>${esc((s.member_versions||[s.definition_version]).join(' · '))}</small></td><td>${s.open_count||0} / ${s.terminal_count||0}<small>${s.written_off_count||0} 笔核销</small></td><td>${s.win_count||0} / ${s.terminal_count||0}</td><td class="${pnlClass(s.realized_pnl_usd)}">${money(s.realized_pnl_usd)}</td><td class="${pnlClass(s.realized_pnl_per_terminal_usd)}">${s.realized_pnl_per_terminal_usd==null?'暂无终局':money(s.realized_pnl_per_terminal_usd)}</td></tr>`).join(''):'<tr><td colspan="9" class="empty">策略池尚无记录</td></tr>';
  $('#strategy-pool-note').textContent=`当前显示 ${items.length} / ${all.length} 个归并策略组；原始历史 ${stats.raw_strategy_count||all.length} 条`;
  $('#toggle-strategy-pool').textContent=showAllStrategyPool?'仅显示保留策略':'显示全部历史';
}

function renderTrading(data,strategies){
  const t=data.trading||{},counts=t.intent_counts||{},capacity=t.execution_capacity||{},positions=(data.open_positions||strategies.flatMap(s=>(s.positions||[]).filter(p=>p.status==='open'))).map(p=>({...p,strategy_name:strategyLabelForArm(p.arm_id)}));
  const participation=strategies.reduce((a,s)=>{const x=s.entry_participation||{};a.projected+=Number(x.projected||0);a.skipped+=Number(x.skipped_cash_unavailable_at_fill||0);return a;},{projected:0,skipped:0});
  $('#trading-summary').innerHTML=[
    ['READY 买入',capacity.ready_buy_count||0,capacity.oldest_ready_buy_age_seconds==null?'队列为空':`最老 ${Math.round(capacity.oldest_ready_buy_age_seconds)} 秒 · SLA ${Math.round(capacity.signal_to_execution_sla_seconds||0)} 秒`],
    ['正在提交',counts.submitted||0,'提交不等于已经成交'],
    ['已经成交',counts.filled||0,`${(t.fills||[]).length} 个最近成交`],
    ['零尝试失败',capacity.zero_attempt_failed_buy_count||0,`仍在等首次尝试 ${capacity.zero_attempt_waiting_buy_count||0} · P95 ${capacity.buy_queue_delay_p95_seconds==null?'—':Math.round(capacity.buy_queue_delay_p95_seconds)+' 秒'}`],
    ['实际参与 / 历史现金门跳过',`${participation.projected} / ${participation.skipped}`,'资金模式激活后不再因 Paper 余额阻断新机会'],
  ].map(([k,v,n])=>`<article class="summary-card"><span>${esc(k)}</span><strong>${esc(v)}</strong><small>${esc(n)}</small></article>`).join('');
  const lastIntent=(t.intents||[])[0],lastAttempt=(t.attempts||[])[0],lastFill=(t.fills||[])[0];
  $('#lifecycle').innerHTML=[
    ['形成交易信号',(data.recent_decisions||[])[0]?.decided_at,(data.recent_decisions||[])[0]?.status],
    ['生成买卖任务',lastIntent?.created_at,lastIntent?`${lastIntent.side} · ${lastIntent.status}`:'等待'],
    ['提交交易',lastAttempt?.requested_at,lastAttempt?`${lastAttempt.side} · ${lastAttempt.terminal_status||'等待'}`:'等待'],
    ['成交并形成仓位',lastFill?.filled_at,lastFill?`${lastFill.side} · ${money(lastFill.gross_usd)}`:'等待'],
  ].map(([k,at,v],i)=>`<article class="lifecycle-step"><span>${i+1}</span><div><strong>${esc(k)}</strong><p>${esc(v||'—')}</p><small>${time(at,true)}</small></div></article>`).join('');
  $('#open-positions tbody').innerHTML=positions.length?positions.map(p=>`<tr><td><strong>${esc(p.strategy_name)}</strong></td><td>${tokenLink(p.token_id)}</td><td>${esc(durationText(p.opened_at))}</td><td>${money(p.stake_usd)}</td><td>${esc(p.amount_raw)}</td><td class="${pnlClass(p.indicative_unrealized_pnl_usd)}">${p.indicative_unrealized_pnl_usd==null?'价格待更新':money(p.indicative_unrealized_pnl_usd)}<small>${p.indicative_source==='dex_price_mark_4pct_haircut'?'公开池价格，已扣 4% 卖出滑点':p.indicative_source==='route_verified_pumpswap_minimum_estimate'?'PumpSwap 本池估算':p.indicative_source==='pump_curve_full_position_minimum_estimate'?'Pump 曲线估算':'暂无价格，不按 0 计'}</small></td><td>${money(p.indicative_price_usd)}</td><td>${money(p.indicative_liquidity_usd)}</td><td><span class="status-pill ${p.indicative_sellability==='MARK_SELLABLE'?'closed':'retry'}">${esc(sellabilityText(p.indicative_sellability))}</span></td><td>${esc(localSurfaceText(p))}</td><td>${time(p.indicative_mark_at||p.local_surface_at||p.latest_quote_at||p.mark_as_of)}</td></tr>`).join(''):'<tr><td colspan="11" class="empty">当前没有开放仓位</td></tr>';
  $('#exit-queue tbody').innerHTML=(t.exit_queue||[]).length?t.exit_queue.map(x=>`<tr><td>${time(x.recorded_at)}</td><td>${esc(strategyName(x.arm_id))}</td><td>${tokenLink(x.token_id)}</td><td>${esc(exitActionText(x.action))}</td><td><span class="status-pill ${esc(x.status)}">${esc(queueStatusText(x.status))}</span></td><td>${x.attempt_count||0}</td><td>${time(x.next_attempt_at)}</td><td class="reason">${esc(reasonText(x.reason))}</td></tr>`).join(''):'<tr><td colspan="8" class="empty">当前没有退出队列</td></tr>';
}

function renderReverseability(data){
  const x=data.immediate_reverseability||{}, horizons=x.horizons||[];
  const h=n=>horizons.find(item=>Number(item.seconds)===n)||{};
  const statusCount=(row,key)=>Number((row.counts||{})[key]||0);
  const known=row=>statusCount(row,'REVERSE_QUOTED')+statusCount(row,'TRANSIENT_ROUTE_GAP');
  $('#reverseability-summary').innerHTML=[
    ['前向买入记录',x.eligible_entry_fills||0,x.registered_at?`注册于 ${time(x.registered_at,true)}`:'等待注册'],
    ['15 秒可卖',known(h(15)),`${h(15).observed||0}/${h(15).matured||0} 已形成不可变结果`],
    ['30 秒可卖',known(h(30)),`${statusCount(h(30),'TRANSIENT_ROUTE_GAP')} 个先断后恢复`],
    ['60 秒仍无路由',statusCount(h(60),'REVERSE_NO_ROUTE'),`${statusCount(h(60),'AGGREGATOR_COVERAGE_GAP')} 个本地池反证`],
  ].map(([k,v,n])=>`<article class="summary-card"><span>${esc(k)}</span><strong>${esc(v)}</strong><small>${esc(n)}</small></article>`).join('');
  $('#reverseability-table tbody').innerHTML=horizons.length?horizons.map(row=>{
    const unknown=['UNKNOWN_PROTOCOL','UNKNOWN_ERROR','UNKNOWN_STALE','UNKNOWN_NO_SAMPLE'].reduce((n,key)=>n+statusCount(row,key),0);
    return `<tr><td>${esc(row.seconds)} 秒</td><td>${esc(row.matured||0)} / ${esc(row.observed||0)}<small>${row.pending||0} 待写入 · ${row.not_yet_due||0} 未到时点</small></td><td>${statusCount(row,'REVERSE_QUOTED')}</td><td>${statusCount(row,'TRANSIENT_ROUTE_GAP')}</td><td>${statusCount(row,'REVERSE_NO_ROUTE')}</td><td>${statusCount(row,'AGGREGATOR_COVERAGE_GAP')}</td><td>${unknown}</td><td>${row.minimum_recovery_ratio_p50==null?'暂无样本':percent(row.minimum_recovery_ratio_p50)}</td></tr>`;
  }).join(''):'<tr><td colspan="8" class="empty">观察器已按新注册点启动，历史 Fill 不回填；等待新的自然前向入场。</td></tr>';
}

function renderFunnel(strategies){
  const max=Math.max(1,...strategies.map(s=>(s.entry_decisions||{}).admitted||0));
  $('#funnel').innerHTML=strategies.map(s=>{const d=s.entry_decisions||{},n=d.admitted||0;return `<div class="funnel-row"><span class="funnel-label">${esc(strategyLabelForArm(s.arm_id))}</span><span class="bar"><i style="width:${Math.max(n?3:0,n/max*100)}%"></i></span><span class="funnel-count">${n} / ${n+(d.rejected||0)}</span></div>`}).join('');
}

function renderChart(strategies){
  const svg=$('#equity-chart'),W=1200,H=340,pad={l:58,r:38,t:20,b:42};
  const series=[];
  strategies.forEach((s,idx)=>{
    const reference=(s.curve||[]).filter(p=>Number.isFinite(Number(p.indicative_total_pnl_usd))).map(p=>({value:Number(p.indicative_total_pnl_usd),ts:new Date(p.recorded_at).getTime()}));
    if(reference.length)series.push({stage:s.stage,idx,kind:'market',points:reference});
  });
  const points=series.flatMap(s=>s.points),values=points.map(p=>p.value),times=points.map(p=>p.ts).filter(Number.isFinite);
  const min=Math.min(-20,...values),max=Math.max(20,...values),span=Math.max(1,max-min),t0=Math.min(Date.now(),...times),t1=Math.max(t0+1000,...times);
  const colors=['#7ef2c4','#c8ff68','#76bfff','#ffcf70','#e68cff','#6ee7ff','#9cffab','#f8a4d8','#ff9975','#d2bdff','#99b6ff','#f1f5d0'];
  const x=ts=>pad.l+(ts-t0)/(t1-t0)*(W-pad.l-pad.r),y=v=>pad.t+(max-v)/span*(H-pad.t-pad.b);let html='';
  for(let i=0;i<5;i++){const v=min+span*i/4,yy=y(v);html+=`<line class="grid-line" x1="${pad.l}" y1="${yy}" x2="${W-pad.r}" y2="${yy}"/><text class="chart-label" x="2" y="${yy+4}">$${v.toFixed(0)}</text>`;}
  html+=`<line class="base-line" x1="${pad.l}" y1="${y(0)}" x2="${W-pad.r}" y2="${y(0)}"/>`;
  series.forEach(s=>{const d=s.points.map((p,i)=>`${i?'L':'M'}${x(p.ts).toFixed(1)},${y(p.value).toFixed(1)}`).join(' '),last=s.points.at(-1);html+=`<path class="equity-line" stroke="${colors[s.idx%colors.length]}" d="${d}"/><text class="chart-label" fill="${colors[s.idx%colors.length]}" x="${Math.min(W-pad.r-24,x(last.ts)+4)}" y="${y(last.value)-4}">S${s.stage}</text>`;});
  svg.innerHTML=html||'<text class="chart-label" x="430" y="170">等待首个市场价格 PNL；缺失不会按 0 绘制</text>';
}

function renderRisk(items){
  $('#risk-list').innerHTML=items.length?items.slice(0,8).map(r=>`<div class="risk-item"><span class="risk-state">${esc(r.risk_state)}</span><div>${tokenLink(r.token_id)}<br><small>${esc(r.risk_reason)}</small></div><span class="risk-time">${time(r.observed_at)}</span></div>`).join(''):'<div class="empty">当前已激活策略暂无精确池风险告警</div>';
}

function positionCell(position){
  if(!position)return '<span class="status-pill missing">未入场</span>';
  if(position.status==='open'){
    const pnl=position.indicative_unrealized_pnl_usd;
    return `<span class="status-pill open">open</span><br><small class="${pnlClass(pnl)}">${pnl==null?'UNKNOWN':money(pnl)}</small>`;
  }
  const pnl=position.realized_pnl_usd;
  return `<span class="status-pill ${esc(position.status)}">${esc(position.status)}</span>${pnl!==null&&pnl!==undefined?`<br><small class="${pnlClass(pnl)}">${money(pnl)}</small>`:''}`;
}
function renderMatrix(strategies){
  const tokens=new Map();strategies.forEach(s=>(s.positions||[]).forEach(p=>{if(!tokens.has(p.token_id))tokens.set(p.token_id,{});tokens.get(p.token_id)[s.stage]=p;}));
  const rows=[...tokens.entries()].slice(0,40),table=$('#token-matrix');table.querySelector('thead').innerHTML=`<tr><th>Token</th>${strategies.map(s=>`<th>S${s.stage}</th>`).join('')}</tr>`;
  table.querySelector('tbody').innerHTML=rows.length?rows.map(([token,states])=>`<tr><td>${tokenLink(token)}</td>${strategies.map(s=>`<td>${positionCell(states[s.stage])}</td>`).join('')}</tr>`).join(''):'<tr><td colspan="13" class="empty">等待当前版本自然前向入场</td></tr>';
}

function renderActivity(items,strategies){
  $('#activity tbody').innerHTML=items.length?items.map(a=>`<tr><td>${time(a.created_at)}</td><td>${esc(strategyLabelForArm(a.arm_id))}</td><td>${tokenLink(a.token_id)}</td><td><span class="status-pill ${a.side==='WRITEOFF'?'written_off':a.side==='SELL'?'closed':''}">${esc(sideText(a.side))}</span></td><td>${money(a.gross_usd)}</td><td class="${pnlClass(a.realized_pnl_usd)}">${money(a.realized_pnl_usd)}</td><td class="reason">${esc(reasonText(a.reason))}</td></tr>`).join(''):'<tr><td colspan="7" class="empty">新前向版本尚无交易，系统正在持续发现 Token</td></tr>';
}

function renderDiscoveries(data){
  const items=data.discovery?.tokens||[];
  $('#token-stream').innerHTML=items.length?items.slice(0,10).map(t=>`<div class="token-row"><span class="new-dot ${ageSeconds(t.observed_at)<=90?'active':''}"></span><div>${tokenLink(t.token_id,t.symbol||t.name||shortToken(t.token_id))}<small>${esc(chainLabelForToken(t.token_id))} · ${esc(shortToken(t.token_id))} · ${esc(sourceText(t.source))}</small></div><time>${ageText(t.observed_at)}</time></div>`).join(''):'<div class="empty">等待新 Token</div>';
  $('#discovery-table tbody').innerHTML=items.length?items.map(t=>`<tr><td>${time(t.observed_at,true)}</td><td>${esc(chainLabelForToken(t.token_id))}</td><td>${tokenLink(t.token_id)}</td><td>${esc(t.symbol||t.name||'—')}</td><td>${esc(sourceText(t.source))}</td><td>${t.new_token?'新币':t.first_local_discovery?'首次发现':'再次活跃'}</td><td>${t.snapshot_count||0}</td><td><span class="status-pill ${t.no_pair?'written_off':'closed'}">${t.no_pair?'暂无池':'有行情'}</span></td></tr>`).join(''):'<tr><td colspan="8" class="empty">尚无发现记录</td></tr>';
  const rounds=data.discovery?.rounds||[], totals=rounds.reduce((a,r)=>{a.returned+=Number(r.returned_count||0);a.exposed+=Number(r.exposed_token_count||0);a.fresh+=Number(r.first_local_discovery_count||0);a.errors+=r.status==='error'?1:0;return a;},{returned:0,exposed:0,fresh:0,errors:0});
  $('#round-summary').innerHTML=`<div class="round-metrics"><div><span>轮次</span><strong>${rounds.length}</strong></div><div><span>返回 / 暴露</span><strong>${totals.returned} / ${totals.exposed}</strong></div><div><span>首次发现</span><strong>${totals.fresh}</strong></div><div><span>错误</span><strong class="${totals.errors?'pnl-negative':''}">${totals.errors}</strong></div></div>${rounds.slice(0,5).map(r=>`<p><span>${time(r.started_at)}</span><strong>${esc(r.provider)}</strong><small>${esc(r.status)} · ${r.exposed_token_count||0} tokens</small></p>`).join('')}`;
}

function renderVersions(items){
  $('#version-list').innerHTML=items.length?items.map((v,i)=>`<article class="version-card ${v.current?'current':''}"><div class="version-node">${String(i+1).padStart(2,'0')}</div><div><div class="version-title"><strong>${esc(v.definition_version)}</strong>${v.current?'<span>当前前向版本</span>':'<span>只读历史</span>'}</div><p>${time(v.registered_at,true)} · 激活点 ${v.activation_exploration_buy_trade_id}</p><div class="version-metrics"><span>${v.decision_count} 个决策</span><span>${v.position_count} 个仓位</span><span>${v.closed_count} 已卖</span><span>${v.written_off_count} 核销</span></div></div></article>`).join(''):'<div class="empty">尚无 ChainMemeTrader 版本</div>';
}

function renderPostbuyResearch(data){
  const r=data.postbuy_research||{}, items=r.items||[];
  $('#postbuy-research-summary').innerHTML=[
    ['前向注册',r.registered_at?time(r.registered_at,true):'未注册',`激活 BUY Fill ${r.activation_buy_fill_id??'—'}`],
    ['研究案例',r.cases||0,`${r.completed||0} 已完成 · ${r.pending||0} 待结果`],
    ['覆盖缺口',r.coverage_gaps||0,'错过 30–60 秒窗口或缺少因果快照'],
    ['交易权限','无','Agent 结果不会修改 12 个现有账户'],
  ].map(([k,v,n])=>`<article class="summary-card"><span>${esc(k)}</span><strong>${esc(v)}</strong><small>${esc(n)}</small></article>`).join('');
  $('#postbuy-research-table tbody').innerHTML=items.length?items.map(x=>{
    const latency=x.completed_at&&x.research_cutoff_at?Math.max(0,(new Date(x.completed_at)-new Date(x.research_cutoff_at))/1000):null;
    const result=x.assessment_status||x.admission_outcome||x.terminal_status||'等待';
    return `<tr><td>${time(x.research_cutoff_at,true)}</td><td>${tokenLink(x.token_id)}</td><td>#${esc(x.shadow_cohort_id)}</td><td><span class="status-pill ${x.status==='triggered'?'closed':'written_off'}">${esc(x.status)}</span><small class="reason">${esc(x.reason_code||'—')}</small></td><td>${esc(result)}${x.admission_reason?`<small class="reason">${esc(x.admission_reason)}</small>`:''}</td><td>${latency===null?'—':`${latency.toFixed(1)}s`}</td><td>观察专用</td></tr>`;
  }).join(''):'<tr><td colspan="7" class="empty">已注册严格前向研究；等待下一笔自然 BUY Fill 后 30–60 秒内生成首个案例</td></tr>';
}

function renderExitChallenger(data){
  const x=data.exit_challenger||{},items=x.positions||[],account=x.account||{};
  const settled=items.filter(p=>p.status==='closed'||p.status==='written_off').length;
  const runLabel=x.status==='running'?'严格前向运行中':x.status==='enrollment_stopped'?'LEGACY FROZEN':'未注册';
  const runNote=x.status==='enrollment_stopped'?'旧仓继续退出；不再新增，结果不可作为干净单变量对照':x.registered_at?`注册于 ${time(x.registered_at,true)}`:'等待注册';
  $('#exit-challenger-summary').innerHTML=[
    ['运行状态',runLabel,runNote],
    ['自然配对',items.length,`${items.length-settled} 开放 · ${settled} 终局`],
    ['挑战策略累计 PNL',money(account.executable_total_pnl_usd),account.valuation_status||'等待精确报价'],
    ['冻结规则',`+${Math.round(Number(x.arm_executable_return||0)*100)}% / −${Math.round(Number(x.exit_drawdown||0)*100)}%`,'启动收益 / 可执行高点回撤'],
  ].map(([k,v,n])=>`<article class="summary-card"><span>${esc(k)}</span><strong>${esc(v)}</strong><small>${esc(n)}</small></article>`).join('');
  $('#exit-challenger-table tbody').innerHTML=items.length?items.map(p=>`<tr><td>${time(p.opened_at,true)}</td><td>${tokenLink(p.token_id)}</td><td><span class="status-pill ${esc(p.status)}">${esc(p.status)}</span></td><td>${money(p.current_executable_usd)}</td><td>${money(p.executable_high_water_usd)}</td><td>${p.armed?'<span class="status-pill retry">ARMED</span>':'等待 +40%'}</td><td class="${pnlClass(p.drawdown_from_high)}">${percent(p.drawdown_from_high)}</td><td>${esc(p.control_status||'—')} / <span class="${pnlClass(p.paired_realized_pnl_delta_usd)}">${money(p.paired_realized_pnl_delta_usd)}</span></td></tr>`).join(''):'<tr><td colspan="8" class="empty">已冻结注册点；等待下一笔自然 Stage 4 BUY Fill，不回填旧交易。</td></tr>';
}

function renderHealth(items,data){
  const s=data.system||{};
  const capacity=data.trading?.execution_capacity||{};
  const storage=s.storage||{},gb=n=>Number.isFinite(Number(n))?(Number(n)/1073741824).toFixed(2)+' GB':'—';
  const monitorOk=Number(s.held_account_states||0)>0&&Number(s.held_account_alerts||0)===0;
  const queueOk=Number(capacity.zero_attempt_failed_buy_count||0)===0;
  const labels={'chain-meme-trader':'策略与账户','pumpportal':'Pump.fun 新币发现','dexscreener_discovery':'DexScreener Token 发现','multichain_meme_data':'三链新币与行情采集','chain-meme-market-marks':'持仓价格与池监控','onchain_only_jupiter_quote':'真实成交报价','solana-held-accounts':'链上账户监控','chain-meme-postbuy-research':'买后信息调查'};
  $('#health-grid').innerHTML=items.map(h=>{const latest=h.last_item_at||h.last_ok_at,ok=!h.last_error_at||new Date(h.last_error_at)<=new Date(h.last_ok_at||0);return `<article class="health-card ${ok?'ok':'bad'}"><span class="health-dot"></span><div><strong>${esc(labels[h.source]||'后台服务')}</strong><p>${latest?`最后活动 ${ageText(latest)}`:'尚无活动'}</p><small>${h.last_error?'最近一次运行出现错误':'运行正常'}</small></div></article>`}).join('')+`<article class="health-card ${queueOk?'ok':'bad'}"><span class="health-dot"></span><div><strong>交易队列</strong><p>${capacity.ready_buy_count||0} 笔待买</p><small>${capacity.zero_attempt_failed_buy_count||0} 笔尚未成功开始处理</small></div></article><article class="health-card ${monitorOk?'ok':'bad'}"><span class="health-dot"></span><div><strong>池与持仓监控</strong><p>${s.held_account_states||0} 已观测 · ${s.held_account_alerts||0} 告警</p><small>${s.held_account_latest_at?`最近状态 ${ageText(s.held_account_latest_at)}`:'等待首个持仓'}</small></div></article><article class="health-card ok"><span class="health-dot"></span><div><strong>模拟交易</strong><p>正在运行</p><small>公开市场价格与统一策略流程</small></div></article><article class="health-card ok"><span class="health-dot"></span><div><strong>实盘接口</strong><p>按钱包单独启用</p><small>未启用的钱包不会发送交易</small></div></article><article class="health-card ${(Number(storage.wal_bytes||0)<1073741824&&Number(storage.free_bytes||0)>10737418240)?'ok':'bad'}"><span class="health-dot"></span><div><strong>本地存储</strong><p>数据库 ${gb(storage.database_bytes)} · 临时数据 ${gb(storage.wal_bytes)}</p><small>E盘剩余 ${gb(storage.free_bytes)}</small></div></article><article class="health-card ok"><span class="health-dot"></span><div><strong>网页刷新</strong><p>可见 5 秒 · 隐藏 30 秒</p><small>Token 详情 10 秒 · 后台持仓行情优先 · 待退出 ${s.pending_exit_quotes||0}</small></div></article>`;
}

async function openToken(tokenId,changeHash=true){
  const sameToken=activeDrawerKind==='token'&&activeTokenId===tokenId&&$('#token-drawer').classList.contains('open');
  if(changeHash&&location.hash!==`#/token/${encodeURIComponent(tokenId)}`)location.hash=`#/token/${encodeURIComponent(tokenId)}`;
  activeTokenId=tokenId;
  activeDrawerKind='token';
  $('#token-drawer').classList.add('open');$('#scrim').classList.add('open');$('#token-drawer').setAttribute('aria-hidden','false');
  $('#drawer-kicker').textContent='Token 信息';
  if(!sameToken){$('#drawer-title').textContent=shortToken(tokenId);$('#drawer-body').innerHTML='<div class="empty">读取证据链…</div>';}
  if(tokenDetailLoading===tokenId)return;
  tokenDetailLoading=tokenId;
  try{const response=await fetch(`/api/token?token_id=${encodeURIComponent(tokenId)}`,{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);const payload=await response.json();if(activeTokenId===tokenId){renderTokenDetail(payload);tokenDetailRefreshedAt=Date.now();}}catch(error){if(activeTokenId===tokenId)$('#drawer-body').innerHTML=`<div class="empty">读取失败：${esc(error.message)}</div>`;}finally{if(tokenDetailLoading===tokenId)tokenDetailLoading=null;}
}
function closeDrawer(changeHash=true){activeTokenId=null;activeDrawerKind=null;$('#token-drawer').classList.remove('open');$('#scrim').classList.remove('open');$('#token-drawer').setAttribute('aria-hidden','true');if(changeHash&&location.hash.startsWith('#/token/'))location.hash=`#/${lastPage}`;}
function tokenTransactions(fills=[],trades=[]){
  const rows=[
    ...fills.map(item=>({side:item.side,at:item.filled_at,eventId:item.id,cohort:item.shadow_cohort_id,source:0})),
    ...trades.map(item=>({side:item.side,at:item.created_at,eventId:item.execution_fill_id??item.source_entry_fill_id??item.entry_fill_id,cohort:item.shadow_cohort_id,source:1})),
  ].filter(item=>['BUY','SELL','WRITEOFF'].includes(item.side)&&item.at).sort((a,b)=>new Date(a.at)-new Date(b.at)||a.source-b.source);
  const seen=new Set();
  return rows.filter(item=>{const ts=new Date(item.at).getTime(),key=item.eventId!=null?`${item.side}|fill|${item.eventId}`:`${item.side}|${item.cohort||''}|${Math.round(ts/1000)}`;if(seen.has(key))return false;seen.add(key);return true;});
}
function miniSeriesChart(points,key,label,lineClass,transactions=[],formatter=money){
  const valid=points.filter(p=>Number.isFinite(new Date(p.observed_at).getTime())&&Number.isFinite(Number(p[key]))&&Number(p[key])>=0);
  if(!valid.length)return `<div class="empty">尚无${esc(label)}快照</div>`;
  const W=760,H=150,pad=10,vals=valid.map(p=>Number(p[key])),min=Math.min(...vals),max=Math.max(...vals),span=Math.max(max-min,max*.001,1e-12),times=valid.map(p=>new Date(p.observed_at).getTime()),t0=Math.min(...times),t1=Math.max(t0+1000,...times);
  const x=ts=>pad+(ts-t0)/(t1-t0)*(W-pad*2),y=value=>H-pad-(value-min)/span*(H-pad*2);
  const path=valid.map((p,i)=>`${i?'L':'M'}${x(new Date(p.observed_at).getTime()).toFixed(1)},${y(Number(p[key])).toFixed(1)}`).join(' ');
  const markers=transactions.map(item=>{
    const ts=new Date(item.at).getTime();if(!Number.isFinite(ts)||ts<t0||ts>t1)return '';
    const nearest=valid.reduce((best,p)=>Math.abs(new Date(p.observed_at)-ts)<Math.abs(new Date(best.observed_at)-ts)?p:best,valid[0]),cx=x(ts).toFixed(1),cy=y(Number(nearest[key])).toFixed(1),title=`${sideText(item.side)} · ${time(item.at,true)}`;
    if(item.side==='WRITEOFF')return `<g class="writeoff-mark"><line x1="${Number(cx)-5}" y1="${Number(cy)-5}" x2="${Number(cx)+5}" y2="${Number(cy)+5}"/><line x1="${Number(cx)+5}" y1="${Number(cy)-5}" x2="${Number(cx)-5}" y2="${Number(cy)+5}"/><title>${esc(title)}</title></g>`;
    return `<circle class="trade-marker ${item.side==='BUY'?'buy':'sell'}" cx="${cx}" cy="${cy}" r="5"><title>${esc(title)}</title></circle>`;
  }).join('');
  const last=valid.at(-1),lastX=x(new Date(last.observed_at).getTime()).toFixed(1),lastY=y(Number(last[key])).toFixed(1);
  return `<svg class="mini-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Token ${esc(label)}变化"><path class="${esc(lineClass)}" d="${path}"/><circle class="series-last ${esc(lineClass)}" cx="${lastX}" cy="${lastY}" r="4"/>${markers}</svg><div class="chart-range"><span>最低 ${formatter(min)}</span><span>${valid.length} 个后端快照点</span><span>最高 ${formatter(max)}</span></div>`;
}
function miniPriceChart(points,transactions=[]){
  return `<div class="market-charts"><section><h4>价格曲线</h4>${miniSeriesChart(points,'price_usd','价格','price-line',transactions,tokenPrice)}<p class="trade-legend"><i class="legend-buy"></i>BUY　<i class="legend-sell"></i>SELL　<i class="legend-writeoff">×</i>WRITEOFF · 标记已按成交/事件去重</p></section><section><h4>流动性曲线</h4>${miniSeriesChart(points,'liquidity_usd','流动性','liquidity-line')}</section></div>`;
}
function renderTokenDetail(d){
  const t=d.token||{},latest=d.snapshots?.at(-1)||{},positions=d.positions||[],trades=d.trades||[],risk=d.risk||[],decisions=d.decisions||[],routes=d.routes||[],intents=d.intents||[],fills=d.fills||[],reverse=d.immediate_reverseability||[];
  const transactions=tokenTransactions(fills,trades);
  const links=(t.links||[]).map(link=>`<a href="${esc(link.url)}" target="_blank" rel="noopener noreferrer">${esc(link.label)} ↗</a>`).join('');
  $('#drawer-title').textContent=t.symbol||t.name||shortToken(t.token_id);
  $('#drawer-body').innerHTML=`<section class="detail-identity"><p>${esc(t.address||shortToken(t.token_id))}</p><h3>${esc(t.name||t.symbol||'未命名 Token')}</h3><p class="token-description">${esc(t.description||`由 ${sourceText(t.source)} 发现；下方数据来自公开 API 的最新价格、池流动性与成交活动。`)}</p><div><span>首次发现 ${time(t.first_seen_at,true)}</span><span>来源 ${esc(sourceText(t.source))}</span><span>最新价格 ${tokenPrice(latest.price_usd)}</span><span>池流动性 ${money(latest.liquidity_usd)}</span><span>5 分钟成交量 ${money(latest.volume_5m_usd)}</span><span>5 分钟买 / 卖 ${latest.buys_5m||0} / ${latest.sells_5m||0}</span></div><nav class="token-links">${links||'<span>暂无外部链接</span>'}</nav></section><section class="detail-section"><h3>价格、流动性与策略买卖点</h3>${miniPriceChart(d.snapshots||[],transactions)}</section><section class="detail-section"><h3>策略操作</h3>${trades.map(x=>`<p class="detail-line"><time>${time(x.created_at)}</time><strong>${esc(strategyLabelForArm(x.arm_id))} · ${esc(sideText(x.side))}</strong><small>${esc(reasonText(x.reason))} · ${money(x.realized_pnl_usd)}</small></p>`).join('')||'<div class="empty">当前版本暂无操作</div>'}</section><section class="detail-section"><h3>策略仓位</h3><div class="detail-stage-grid">${positions.map(p=>{const pnl=positionPnl(p);return `<div><strong>${esc(strategyLabelForArm(p.arm_id))}</strong><span class="status-pill ${esc(p.status)}">${p.status==='open'?'持有中':p.status==='closed'?'已卖出':'已核销'}</span><small>持仓 ${esc(durationText(p.opened_at,p.closed_at))}</small><small class="${pnlClass(pnl.total)}">未实现 ${pnl.unrealized==null?'—':money(pnl.unrealized)} · 已实现 ${pnl.realized==null?'—':money(pnl.realized)} · 总 PNL ${pnl.total==null?'价格待更新':money(pnl.total)}</small></div>`;}).join('')||'<div class="empty">当前没有仓位</div>'}</div></section><section class="detail-section"><h3>池与风险状态</h3>${risk.map(x=>`<p class="detail-line"><time>${time(x.observed_at)}</time><strong>${esc(x.risk_state==='HEALTHY'?'正常':'需要注意')}</strong><small>${esc(reasonText(x.risk_reason))}</small></p>`).join('')||`<div class="empty">当前没有池风险告警</div>`}</section>`;
}

function drawerOpen(kind,kicker,title,body){
  activeDrawerKind=kind;activeTokenId=null;
  $('#drawer-kicker').textContent=kicker;$('#drawer-title').textContent=title;$('#drawer-body').innerHTML=body;
  $('#token-drawer').classList.add('open');$('#scrim').classList.add('open');$('#token-drawer').setAttribute('aria-hidden','false');
}
const listValue=(payload,...keys)=>{for(const key of keys){if(payload&&payload[key]!=null)return payload[key];}return null;};
const errorRows=(payload)=>{const rows=listValue(payload,'errors','cases','items','data');return Array.isArray(rows)?rows:Array.isArray(payload)?payload:[];};
function errorField(item,keys,fallback='—'){const value=listValue(item,...keys);return value==null||value===''?fallback:value;}
function renderErrors(items){
  const body=$('#errors-table tbody');if(!body)return;
  body.innerHTML=items.length?items.map(item=>{
    const id=errorField(item,['id','error_id','key'],'');
    const status=String(errorField(item,['status','state'],'new'));
    const severity=String(errorField(item,['severity','level'],'medium'));
    const statusText={new:'待处理',in_progress:'处理中',fixed:'已修复',ignored:'已忽略'}[status]||status;
    const severityText={high:'严重',medium:'一般',low:'轻微'}[severity]||severity;
    return `<tr><td><span class="status-pill ${status==='fixed'||status==='ignored'?'closed':severity==='high'?'written_off':'retry'}">${esc(statusText)}</span></td><td>${esc(severityText)}</td><td>${esc(errorField(item,['component','source','service']))}</td><td class="reason">${esc(errorField(item,['message_safe','summary','message','error','detail']))}</td><td>${esc(time(errorField(item,['first_at','first_seen_at','first_occurrence_at'],null),true))}</td><td>${esc(time(errorField(item,['last_at','last_seen_at','last_occurrence_at'],null),true))}</td><td>${esc(errorField(item,['count','occurrence_count','times'],0))}</td><td><button class="table-action" data-error-detail="${esc(id)}">查看详情</button></td></tr>`;
  }).join(''):'<tr><td colspan="8" class="empty">当前没有错误记录</td></tr>';
  $('#errors-refresh').textContent=`${items.length} 条记录 · ${time(new Date(),true)} 更新`;
}
async function refreshErrors(){
  clearTimeout(errorTimer);if(lastPage!=='errors')return;
  try{const response=await fetch('/api/errors',{cache:'no-store'});const payload=await response.json();if(!response.ok)throw new Error(payload.error||`HTTP ${response.status}`);errors=errorRows(payload);renderErrors(errors);}
  catch(error){errors=[];const body=$('#errors-table tbody');if(body)body.innerHTML=`<tr><td colspan="8" class="empty">错误记录读取失败：${esc(error.message)}</td></tr>`;}
  errorTimer=setTimeout(()=>{if(lastPage==='errors')refreshErrors();},10000);
}
function detailList(items,label,fields){
  if(!Array.isArray(items)||!items.length)return `<p class="empty">暂无${label}</p>`;
  return items.slice(0,30).map(item=>`<p class="detail-line"><time>${esc(time(errorField(item,['at','timestamp','created_at','recorded_at','observed_at'],null),true))}</time><strong>${esc(errorField(item,fields,'—'))}</strong><small>${esc(errorField(item,['summary','message_safe','message','detail','note']))}</small></p>`).join('');
}
function repairList(items){
  if(!Array.isArray(items)||!items.length)return '<p class="empty">暂无修复记录</p>';
  return items.slice(0,30).map(item=>{
    const summary=errorField(item,['summary','note'],'—');
    const evidence=errorField(item,['evidence_safe','evidence'],'');
    const reportPath=errorField(item,['report_path'],'');
    const extra=[evidence&&`验证：${evidence}`,reportPath&&`解决报告：${reportPath}`].filter(Boolean).join(' · ');
    return `<p class="detail-line"><time>${esc(time(errorField(item,['recorded_at','at'],null),true))}</time><strong>${esc(errorField(item,['action','status','actor']))}</strong><small>${esc(summary)}</small>${extra?`<small>${esc(extra)}</small>`:''}</p>`;
  }).join('');
}
async function openError(errorId){
  drawerOpen('error','错误详情','读取中…','<div class="empty">读取错误发生记录…</div>');
  try{
    const response=await fetch(`/api/error?id=${encodeURIComponent(errorId)}`,{cache:'no-store'});
    const payload=await response.json();if(!response.ok)throw new Error(payload.error||`HTTP ${response.status}`);
    const item=payload.error||payload.case||payload.item||payload;
    const occurrences=payload.occurrences||payload.occurrence||[];
    const repairs=payload.repair_reports||payload.repairs||payload.repair||[];
    const id=errorField(item,['id','error_id'],errorId);
    const status=String(errorField(item,['status','state'],'new'));
    $('#drawer-title').textContent=errorField(item,['message_safe','summary','message','error'],'错误详情');
    $('#drawer-body').innerHTML=`<section class="detail-identity"><p>${esc(errorField(item,['component','source','service']))}</p><h3>${esc(errorField(item,['severity','level'],'错误'))}</h3><div><span>首次 ${esc(time(errorField(item,['first_at','first_seen_at'],null),true))}</span><span>最近 ${esc(time(errorField(item,['last_at','last_seen_at'],null),true))}</span><span>次数 ${esc(errorField(item,['count','occurrence_count'],0))}</span><span>状态 ${esc(status)}</span></div>${item.resolution_note?`<p>${esc(item.resolution_note)}</p>`:''}</section><section class="detail-section"><h3>发生记录</h3>${detailList(occurrences,'发生记录',['component','source','severity'])}</section><section class="detail-section"><h3>修复记录</h3>${repairList(repairs)}</section><section class="detail-section"><h3>更新处理状态</h3><form class="error-form" data-error-form="${esc(id)}"><select name="status"><option value="new" ${status==='new'?'selected':''}>待处理</option><option value="in_progress" ${status==='in_progress'?'selected':''}>处理中</option><option value="fixed" ${status==='fixed'?'selected':''}>已修复</option><option value="ignored" ${status==='ignored'?'selected':''}>已忽略</option></select><textarea name="note" rows="3" placeholder="可选备注"></textarea><button type="submit">保存状态</button><p class="form-note">只保存处理状态和备注，不显示内部密钥或代码。</p></form></section>`;
  }
  catch(error){$('#drawer-title').textContent='错误详情';$('#drawer-body').innerHTML=`<div class="empty">读取失败：${esc(error.message)}</div>`;}
}
async function openWalletDetail(walletId){
  drawerOpen('wallet','钱包详情','读取中…','<div class="empty">读取钱包与策略记录…</div>');
  try{const response=await fetch(`/api/wallet?id=${encodeURIComponent(walletId)}`,{cache:'no-store'});const payload=await response.json();if(!response.ok)throw new Error(payload.error||`HTTP ${response.status}`);const item=payload.wallet||payload.item||payload;const strategy=payload.strategy||{};const account=payload.account||item.account||{};const positions=payload.positions||payload.open_positions||[];const trades=payload.trades||payload.executions||[];const safe=payload.security||payload.whitelist||payload.live_executions||[];const realized=listValue(account,'capital_neutral_realized_pnl_usd','realized_pnl_usd');const unrealized=listValue(account,'capital_neutral_unrealized_pnl_usd','indicative_unrealized_pnl_usd');const pnl=listValue(item,'strategy_pnl_usd','pnl_usd')??listValue(account,'capital_neutral_total_pnl_usd','indicative_total_pnl_usd');$('#drawer-title').textContent=errorField(item,['alias','name','address_display'],'钱包详情');$('#drawer-body').innerHTML=`<section class="detail-identity"><p>${esc(errorField(item,['address_display','address'],'地址不可用'))}</p><h3>${esc(walletStrategyLabel(errorField(item,['strategy_id'],'')||''))}</h3><div><span>SOL ${esc(errorField(item,['sol','sol_balance'],listValue(item.balance||{},'sol','sol_balance')??'暂不可用'))}</span><span>USDC ${esc(errorField(item,['usdc','usdc_balance'],listValue(item.balance||{},'usdc','usdc_balance')??'暂不可用'))}</span><span>累计总 PNL ${pnl==null?'价格待更新':money(pnl)}</span><span>已实现 ${realized==null?'—':money(realized)}</span><span>未实现 ${unrealized==null?'价格待更新':money(unrealized)}</span><span>${esc(maturityText(strategy.maturity))}</span><span>运行状态 ${esc(item.enabled?'运行中':'已停止')}</span></div></section><section class="detail-section"><h3>Paper 持仓</h3>${detailList(positions,'持仓',['token_id','symbol','status'])}</section><section class="detail-section"><h3>买卖记录</h3>${detailList(trades,'交易',['side','action','status'])}</section><section class="detail-section"><h3>安全白名单实盘记录</h3>${detailList(safe,'实盘记录',['status','side','action'])}</section>`;}
  catch(error){$('#drawer-title').textContent='钱包详情';$('#drawer-body').innerHTML=`<div class="empty">读取失败：${esc(error.message)}</div>`;}
}

function populateWalletStrategies(){
  const select=$('#wallet-strategy');
  if(!select||select.dataset.loaded==='1'||!universe?.families?.length)return;
  select.innerHTML='<option value="">选择一个策略</option>'+universe.families.map(f=>`<option value="${esc((f.active_arm_ids||[])[0])}">${esc(strategyLabel(f))} · ${esc(readable(f.entry_family,entryLabels))} · ${esc(readable(f.exit_family,exitLabels))}</option>`).join('');
  select.dataset.loaded='1';
}

function walletStrategyLabel(strategyId){
  const family=(universe?.families||[]).find(item=>(item.active_arm_ids||[]).includes(strategyId));
  return family?strategyLabel(family):'绑定策略不可用';
}
function walletStrategyAccount(item){
  const armId=String(item?.strategy_id||'');
  const strategy=(state?.strategies||[]).find(candidate=>String(candidate.arm_id||'')===armId);
  const account=strategy?.account||{};
  const attached=item?.strategy||{};
  const balance=item?.balance||{};
  const pnl=listValue(item,'strategy_pnl_usd','pnl_usd')??attached.total_pnl_usd??account.capital_neutral_total_pnl_usd??account.indicative_total_pnl_usd??account.executable_total_pnl_usd;
  return {pnl,maturity:attached.maturity||strategy?.maturity||'waiting',open:Number(listValue(item,'open_position_count','positions_count')??attached.open_position_count??account.open_position_count??0),sol:listValue(item,'sol','sol_balance')??listValue(balance,'sol','sol_balance'),usdc:listValue(item,'usdc','usdc_balance')??listValue(balance,'usdc','usdc_balance')};
}

function renderWallets(){
  const summary=$('#wallet-summary'),body=$('#wallet-table tbody');
  if(!summary||!body)return;
  const items=wallets?.wallets||[];
  const running=items.filter(item=>item.enabled).length;
  const pending=items.filter(item=>item.pending_transaction).length;
  const masterEnabled=liveTradingEnabled(),masterState=$('#live-master-state');
  if(masterState){masterState.className=`contract-state ${masterEnabled?'active_forward':'retry'}`;masterState.textContent=masterEnabled?'实盘总开关已开启':'实盘总开关已关闭';}
  summary.innerHTML=[
    ['已连接钱包',items.length,'密钥只保存在本机加密文件中'],
    ['实盘总开关',masterEnabled?'已开启':'已关闭',masterEnabled?'钱包可单独启动':'开始实盘按钮已禁用'],
    ['实盘运行中',running,'每个钱包独立启停'],
    ['已绑定策略',items.filter(item=>item.strategy_id).length,'一个钱包对应一个策略'],
    ['待链上确认',pending,pending?'请等待确认，不会重复发送':'当前没有待确认交易'],
  ].map(([k,v,n])=>`<article class="summary-card"><span>${esc(k)}</span><strong>${esc(v)}</strong><small>${esc(n)}</small></article>`).join('');
  body.innerHTML=items.length?items.map(item=>{
    const balance=item.balance||{},balanceError=balance.status==='error'?balance.error:null;
    const startDisabled=!item.enabled&&!masterEnabled;
    const metric=walletStrategyAccount(item);
    return `<tr><td><button class="table-link" data-wallet-detail="${esc(item.id)}">${esc(item.alias||'未命名钱包')}</button><small>${esc(item.address_display||'地址不可用')}</small></td><td>${esc(walletStrategyLabel(item.strategy_id))}</td><td>${metric.sol==null?'暂不可用':Number(metric.sol).toFixed(4)} SOL / ${metric.usdc==null?'暂不可用':Number(metric.usdc).toFixed(2)} USDC</td><td class="${pnlClass(metric.pnl)}">${metric.pnl==null?'价格待更新':money(metric.pnl)}</td><td>${esc(maturityText(metric.maturity))}</td><td>${metric.open}</td><td><span class="status-pill ${item.enabled?'closed':item.error?'written_off':'retry'}">${esc(item.error?'需要处理':item.status||'已停止')}</span>${item.pending_transaction?'<small>链上确认中</small>':''}</td><td><button class="wallet-live-button ${item.enabled?'stop':''}" data-wallet-live="${esc(item.id)}" data-enabled="${item.enabled?'1':'0'}" ${startDisabled?'disabled title="实盘总开关已关闭"':''}>${item.enabled?'停止实盘':'开始实盘'}</button></td></tr>`;
  }).join(''):'<tr><td colspan="8" class="empty">尚未连接钱包。</td></tr>';
}

async function refreshWallets(force=false){
  if(!force&&Date.now()-walletRefreshAt<5000)return;
  try{
    const response=await fetch(`/api/wallets${force?'?refresh=1':''}`,{cache:'no-store'});
    const payload=await response.json();
    if(!response.ok||payload.status!=='ok')throw new Error(payload.error||`HTTP ${response.status}`);
    wallets=payload;walletRefreshAt=Date.now();renderWallets();
    if(state)renderSummary(state,state.strategies||[]);
  }catch(error){
    const body=$('#wallet-table tbody');
    if(body)body.innerHTML=`<tr><td colspan="8" class="empty">钱包状态读取失败：${esc(error.message)}</td></tr>`;
  }
}

function bindTokenLinks(){document.body.addEventListener('click',e=>{const button=e.target.closest('[data-token]');if(button)openToken(button.dataset.token);});}
function render(data){ingestStrategyHistory(data);state=data;const strategies=data.strategies||[];renderRuntime(data);renderDiscoveryBeacon(data);renderSummary(data,strategies);renderLeaders(data);renderUniverse();renderOverviewStrategies();renderTrading(data,strategies);renderReverseability(data);renderFunnel(strategies);renderRisk(data.recent_risk||[]);renderActivity(data.recent_activity||[],strategies);renderDiscoveries(data);renderHealth(data.source_health||[],data);populateWalletStrategies();renderWallets();refreshWallets();}

function renderLive(data,focusedArm=null){
  ingestStrategyHistory(data);
  const previous=new Map((state?.strategies||[]).map(strategy=>[strategy.arm_id,strategy]));
  const hasFocusedPositions=Boolean(focusedArm)&&Array.isArray(data.open_positions);
  const mergedStrategies=(data.strategies||[]).map(strategy=>{
    const prior=previous.get(strategy.arm_id)||{},merged={...prior,...strategy};
    if(hasFocusedPositions&&strategy.arm_id===focusedArm&&!Array.isArray(strategy.positions)){
      const terminal=(prior.positions||[]).filter(position=>position.status==='closed'||position.status==='written_off');
      const open=data.open_positions.filter(position=>position.arm_id===focusedArm).map(position=>({...position,status:'open'}));
      const unique=new Map([...open,...terminal].map(position=>[`${position.shadow_cohort_id}|${position.token_id}`,position]));
      merged.positions=[...unique.values()];
    }
    return merged;
  });
  state={...state,...data,system:{...(state?.system||{}),...(data.system||{})},discovery:{...(state?.discovery||{}),...(data.discovery||{})},trading:{...(state?.trading||{}),...(data.trading||{})},strategies:mergedStrategies}; const strategies=mergedStrategies;
  if(universe&&Number(universe.families?.length||0)!==strategies.length)refreshUniverse();
  renderRuntime(state);renderDiscoveryBeacon(state);renderSummary(state,strategies);renderLeaders(state);renderUniverse();renderOverviewStrategies();renderRisk(state.recent_risk||[]);renderActivity(state.recent_activity||[],strategies);renderDiscoveries(state);renderHealth(state.source_health||[],state);populateWalletStrategies();renderWallets();if(lastPage==='wallets')refreshWallets();if(activeTokenId&&Date.now()-tokenDetailRefreshedAt>=10000)openToken(activeTokenId,false);
}

async function refreshUniverse(){
  try{const response=await fetch('/api/strategy-universe',{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);universe=await response.json();renderUniverse();renderOverviewStrategies();if(state)renderSummary(state,state.strategies||[]);}
  catch(error){const el=$('#universe-refresh');if(el)el.textContent=`合同加载失败 · ${error.message}`;}
}

async function refreshFull(){
  clearTimeout(fullTimer);
  clearTimeout(liveTimer);
  try{const response=await fetch('/api/live',{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);render(await response.json());}
  catch(error){const el=$('#runtime');el.className='runtime stale';el.innerHTML=`<span class="pulse"></span><strong>读取失败</strong><small>${esc(error.message)}</small>`;}
  liveTimer=setTimeout(refreshLive,document.visibilityState==='visible'?5000:30000);
}
async function refreshLive(){
  clearTimeout(liveTimer);
  try{const focusedArm=selectedStrategyArm(),query=focusedArm?`?arm_id=${encodeURIComponent(focusedArm)}`:'';const response=await fetch(`/api/live${query}`,{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);renderLive(await response.json(),focusedArm);}
  catch(error){const el=$('#runtime');el.className='runtime stale';el.innerHTML=`<span class="pulse"></span><strong>实时读取失败</strong><small>${esc(error.message)}</small>`;}
  liveTimer=setTimeout(refreshLive,document.visibilityState==='visible'?5000:30000);
}

window.addEventListener('hashchange',()=>{route();if(lastPage==='wallets')refreshWallets(true);});document.addEventListener('visibilitychange',()=>{clearTimeout(liveTimer);if(!state){refreshFull();return;}refreshLive();});
$('#drawer-close').addEventListener('click',()=>closeDrawer());$('#scrim').addEventListener('click',()=>closeDrawer());
document.body.addEventListener('click',event=>{
  const wallet=event.target.closest('[data-wallet-detail]');if(wallet){openWalletDetail(wallet.dataset.walletDetail);return;}
  const error=event.target.closest('[data-error-detail]');if(error){openError(error.dataset.errorDetail);}
});
document.body.addEventListener('submit',async event=>{
  const form=event.target.closest('[data-error-form]');if(!form)return;event.preventDefault();
  const button=form.querySelector('button'),note=form.querySelector('[name="note"]');button.disabled=true;
  try{const response=await fetch('/api/errors/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:form.dataset.errorForm,status:form.querySelector('[name="status"]').value,note:note?.value||''})});const payload=await response.json();if(!response.ok||payload.status==='error')throw new Error(payload.error||`HTTP ${response.status}`);await refreshErrors();openError(form.dataset.errorForm);}
  catch(error){if(note)note.value=`保存失败：${error.message}`;}
  finally{button.disabled=false;}
});
$('#wallet-connect-form')?.addEventListener('submit',async event=>{
  event.preventDefault();
  const secret=$('#wallet-secret'),status=$('#wallet-form-status'),button=$('#wallet-connect');
  button.disabled=true;status.textContent='正在验证钱包并保存到本机加密存储…';
  try{
    const response=await fetch('/api/wallets/connect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({private_key:secret.value,alias:$('#wallet-name').value,strategy_id:$('#wallet-strategy').value})});
    const payload=await response.json();
    if(!response.ok||payload.status!=='ok')throw new Error(payload.error||`HTTP ${response.status}`);
    wallets=payload;walletRefreshAt=Date.now();renderWallets();status.textContent='钱包已连接并绑定策略。实盘默认停止，可在下方单独启动。';
  }catch(error){status.textContent=`连接失败：${error.message}`;}
  finally{secret.value='';button.disabled=false;}
});
document.body.addEventListener('click',async event=>{
  const button=event.target.closest('[data-wallet-live]');if(!button)return;
  const enable=button.dataset.enabled!=='1';
  if(enable&&!liveTradingEnabled()){$('#wallet-form-status').textContent='实盘总开关已关闭，不能启动钱包实盘。';return;}
  button.disabled=true;
  try{
    const response=await fetch('/api/wallets/live',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({wallet_id:button.dataset.walletLive,enabled:enable})});
    const payload=await response.json();
    if(!response.ok||payload.status!=='ok')throw new Error(payload.error||`HTTP ${response.status}`);
    wallets=payload;walletRefreshAt=Date.now();renderWallets();$('#wallet-form-status').textContent=enable?'实盘已启动，只跟随此后产生的新信号。':'实盘已停止。';
  }catch(error){$('#wallet-form-status').textContent=`操作失败：${error.message}`;}
  finally{button.disabled=false;}
});
$('#toggle-strategies')?.addEventListener('click',()=>{showAllStrategies=!showAllStrategies;if(state)renderStrategyRegistry(state);});
$('#toggle-strategy-pool')?.addEventListener('click',()=>{showAllStrategyPool=!showAllStrategyPool;if(state)renderStrategyPool(state);});
['#universe-search','#universe-state','#universe-class','#universe-version','#universe-sort'].forEach(selector=>$(selector)?.addEventListener(selector==='#universe-search'?'input':'change',renderUniverse));
bindTokenLinks();route();refreshUniverse();refreshFull();
