import { useEffect, useRef, useState } from 'react'
import { Archive, ArrowRight, BookOpen, BrainCircuit, ChevronRight, CirclePause, CirclePlay, Download, Flame, Github, GitBranch, History as HistoryIcon, Home, Lightbulb, LoaderCircle, Lock, MessageSquareQuote, Plus, RefreshCw, Scale, Search, Sparkles, Swords, Trophy, Unlock, Users, Wifi, WifiOff, X, Trash2 } from 'lucide-react'
import { api } from './api'
import type { Debate, DebateHistory, Evaluation, Project, ProjectHistory, Stance, Turn, Workspace } from './types'

type View='home'|'workspace'|'human'|'arena'
type ResumeTarget={id:string;mode:'human'|'arena'}|null
const stages=['立论','攻辩','自由辩论','总结']
const textValue=(value:unknown):string=>{
  if(value==null)return ''
  if(typeof value==='string'||typeof value==='number'||typeof value==='boolean')return String(value)
  if(Array.isArray(value))return value.map(textValue).filter(Boolean).join('；')
  if(typeof value==='object')return Object.entries(value as Record<string,unknown>).map(([key,item])=>`${key}：${textValue(item)}`).join('；')
  return String(value)
}

function App(){
  const [view,setView]=useState<View>('home')
  const [projects,setProjects]=useState<Project[]>([])
  const [project,setProject]=useState<Project|null>(null)
  const [workspace,setWorkspace]=useState<Workspace|null>(null)
  const [health,setHealth]=useState<any>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [resumeTarget,setResumeTarget]=useState<ResumeTarget>(null)

  const loadProjects=async()=>{try{setProjects(await api.projects());setHealth(await api.health())}catch(e:any){setError(e.message)}}
  useEffect(()=>{loadProjects()},[])
  const open=async(p:Project,next:View='workspace')=>{setBusy(true);setError('');try{const full=await api.project(p.id);setProject(full);setWorkspace(full.workspace);setView(next)}catch(e:any){setError(e.message)}finally{setBusy(false)}}
  const navigate=(next:View)=>{if(next!=='home'&&!project)return;setView(next)}
  const openHistoryDebate=(debate:DebateHistory)=>{setResumeTarget({id:debate.id,mode:debate.mode});setView(debate.mode==='human'?'human':'arena')}

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand" onClick={()=>setView('home')}><span className="brand-mark"><Flame size={21}/></span><span><b>观点火花</b><small>DEBATE SPARK</small></span></div>
      <nav>
        <Nav active={view==='home'} icon={<Home/>} label="项目首页" onClick={()=>navigate('home')}/>
        <p className="nav-label">辩论空间</p>
        <Nav active={view==='workspace'} icon={<BookOpen/>} label="备赛工作台" disabled={!project} onClick={()=>navigate('workspace')}/>
        <Nav active={view==='human'} icon={<Swords/>} label="人机对辩" disabled={!workspace} onClick={()=>{setResumeTarget(null);navigate('human')}}/>
        <Nav active={view==='arena'} icon={<Users/>} label="机器竞技场" disabled={!workspace} onClick={()=>{setResumeTarget(null);navigate('arena')}}/>
      </nav>
      <div className="side-bottom">
        <div className={`model-status ${health?.configured?'online':'demo'}`}>
          {health?.configured?<Wifi size={15}/>:<WifiOff size={15}/>}<span><b>{health?.configured?'模型服务已连接':'演示降级模式'}</b><small>{health?.model||'检查服务中'}</small></span>
        </div>
        <p>本地运行 · 数据留在本机</p>
      </div>
    </aside>
    <main>
      {error&&<div className="toast"><X size={16} onClick={()=>setError('')}/>{error}</div>}
      {busy&&<div className="loading-overlay"><LoaderCircle className="spin"/><span>正在编排 Agent…</span></div>}
      {view==='home'&&<HomeView projects={projects} onCreated={async p=>{await loadProjects();await open(p)}} onOpen={open} onDelete={async p=>{try{await api.deleteProject(p.id);await loadProjects()}catch(e:any){setError(e.message)}}}/>}
      {view==='workspace'&&project&&<WorkspaceView project={project} workspace={workspace} setWorkspace={setWorkspace} onPrepared={w=>{setWorkspace(w);setProject({...project,workspace:w,status:'ready'});loadProjects()}} setBusy={setBusy} setError={setError}/>}
      {view==='human'&&project&&workspace&&<HumanDebate project={project} workspace={workspace} resumeTarget={resumeTarget} onClearResume={()=>setResumeTarget(null)} onResume={openHistoryDebate} setError={setError}/>}
      {view==='arena'&&project&&workspace&&<Arena project={project} workspace={workspace} resumeTarget={resumeTarget} onClearResume={()=>setResumeTarget(null)} onResume={openHistoryDebate} setError={setError}/>}
    </main>
  </div>
}

function Nav({active,icon,label,onClick,disabled=false}:{active:boolean;icon:any;label:string;onClick:()=>void;disabled?:boolean}){
  return <button className={`nav-item ${active?'active':''}`} disabled={disabled} onClick={onClick}>{icon}<span>{label}</span>{active&&<ChevronRight className="nav-arrow"/>}</button>
}

function HomeView({projects,onCreated,onOpen,onDelete}:{projects:Project[];onCreated:(p:Project)=>void;onOpen:(p:Project)=>void;onDelete:(p:Project)=>void}){
  const [show,setShow]=useState(false),[topic,setTopic]=useState(''),[stance,setStance]=useState<Stance>('正方'),[creating,setCreating]=useState(false),[confirmId,setConfirmId]=useState<string|null>(null)
  const create=async()=>{if(topic.trim().length<4)return;setCreating(true);try{onCreated(await api.createProject({topic,stance,config:{preset:'中文标准赛制'}}));setShow(false)}finally{setCreating(false)}}
  return <div className="page home-page">
    <a className="page-github" href="https://github.com/Kyle-Yu16/Debate-Spark" target="_blank" rel="noreferrer" title="GitHub"><Github size={20}/></a>
    <header className="hero">
      <div className="eyebrow"><Sparkles size={15}/> 不只争输赢，更要看见新的可能</div>
      <h1>让观点交锋，<em>让思想发光。</em></h1>
      <p>从资料研究到临场攻防，一套兼具逻辑、证据与洞见的中文辩论工作台。</p>
      <button className="primary big" onClick={()=>setShow(true)}><Plus/>创建辩题项目</button>
      <div className="feature-strip">
        <div><Search/><span><b>深度备赛</b><small>双边研究 · 证据审计</small></span></div>
        <div><Swords/><span><b>人机陪练</b><small>针对攻防 · 教练复盘</small></span></div>
        <div><BrainCircuit/><span><b>Agent 竞技</b><small>自行辩论 · 策略进化</small></span></div>
      </div>
    </header>
    <section className="recent"><div className="section-title"><div><span>最近项目</span><h2>继续你的思辨现场</h2></div><span className="count">{projects.length} 个项目</span></div>
      {projects.length===0?<div className="empty"><MessageSquareQuote/><h3>还没有辩题</h3><p>从一个真正让你好奇的问题开始。</p><button className="text-button" onClick={()=>setShow(true)}>创建第一个项目 <ArrowRight/></button></div>:
      <div className="project-grid">{projects.map((p,i)=><div className="project-card-wrap" key={p.id}><button className="project-card" onClick={()=>onOpen(p)}><div className={`project-index tone-${i%3}`}>0{i+1}</div><div className="project-copy"><span className="tag">{p.stance} · {p.status==='ready'?'备赛完成':'待准备'}</span><h3>{p.topic}</h3><small>{new Date(p.updated_at).toLocaleDateString('zh-CN')}</small></div><ArrowRight className="card-arrow"/></button><button className={`card-delete ${confirmId===p.id?'confirm':''}`} onClick={()=>{if(confirmId===p.id){setConfirmId(null);onDelete(p)}else{setConfirmId(p.id)}}}>{confirmId===p.id?'确认删除？':<Trash2 size={14}/>}</button></div>)}</div>}
    </section>
    {show&&<div className="modal-backdrop"><div className="modal"><button className="modal-close" onClick={()=>setShow(false)}><X/></button><div className="modal-icon"><Flame/></div><h2>开启一个辩题</h2><p>一个好辩题，应该让双方都有值得捍卫的价值。</p><label>辩题</label><textarea autoFocus value={topic} onChange={e=>setTopic(e.target.value)} placeholder="例如：当代年轻人更应该追求稳定，还是拥抱不确定性？"/><label>我的持方</label><div className="stance-switch"><button className={stance==='正方'?'selected':''} onClick={()=>setStance('正方')}>正方</button><button className={stance==='反方'?'selected':''} onClick={()=>setStance('反方')}>反方</button></div><button className="primary modal-submit" disabled={topic.trim().length<4||creating} onClick={create}>{creating?<LoaderCircle className="spin"/>:<Sparkles/>}创建并进入工作台</button></div></div>}
  </div>
}

function WorkspaceView({project,workspace,setWorkspace,onPrepared,setBusy,setError}:{project:Project;workspace:Workspace|null;setWorkspace:(w:Workspace)=>void;onPrepared:(w:Workspace)=>void;setBusy:(x:boolean)=>void;setError:(x:string)=>void}){
  const [tab,setTab]=useState('全景'),[dirty,setDirty]=useState(false),[evolving,setEvolving]=useState(false),[evo,setEvo]=useState<any>(null)
  const prepare=async()=>{setBusy(true);try{onPrepared(await api.prepare(project.id))}catch(e:any){setError(e.message)}finally{setBusy(false)}}
  const save=async()=>{if(!workspace)return;setBusy(true);try{await api.saveWorkspace(project.id,workspace);setDirty(false)}catch(e:any){setError(e.message)}finally{setBusy(false)}}
  const editDraft=(key:string,value:string)=>{if(!workspace)return;setWorkspace({...workspace,drafts:{...workspace.drafts,[key]:value}});setDirty(true)}
  const toggleLock=(id:string)=>{if(!workspace)return;setWorkspace({...workspace,arguments:workspace.arguments.map(a=>a.id===id?{...a,locked:!a.locked}:a)});setDirty(true)}
  const evolve=async()=>{setEvolving(true);try{setEvo(await api.evolve(project.id))}catch(e:any){setError(e.message)}finally{setEvolving(false)}}
  if(!workspace)return <div className="page prepare-empty"><div className="topic-chip">{project.stance}</div><h1>{project.topic}</h1><div className="prepare-orbit"><span className="orbit-center"><BrainCircuit/></span>{['辩题分析','双边检索','证据审计','论证设计','洞见探索'].map((x,i)=><span key={x} className={`orbit-node n${i}`}>{x}</span>)}</div><h2>让 Agent 团队开始备赛</h2><p>系统将检索双边资料、审计证据并构建完整攻防地图。通常需要几十秒。</p><button className="primary big" onClick={prepare}><Sparkles/>开始深度备赛</button></div>
  const tabs=[['全景',GitBranch],['证据库',Archive],['攻防矩阵',Scale],['洞见',Lightbulb],['发言稿',MessageSquareQuote]] as const
  return <div className="page workspace-page">
    <header className="work-header"><div><div className="eyebrow">{project.stance} · 备赛工作台</div><h1>{project.topic}</h1></div><div className="header-actions"><button className="secondary" onClick={()=>window.open(`/api/projects/${project.id}/export`)}><Download/>导出 Markdown</button><button className="secondary" onClick={()=>window.print()}><Download/>打印 PDF</button>{dirty&&<button className="primary" onClick={save}>保存修改</button>}</div></header>
    <div className="tabs">{tabs.map(([name,Icon])=><button key={name} className={tab===name?'active':''} onClick={()=>setTab(name)}><Icon/>{name}</button>)}</div>
    {tab==='全景'&&<Overview workspace={workspace} toggleLock={toggleLock}/>}
    {tab==='证据库'&&<EvidenceView workspace={workspace}/>}
    {tab==='攻防矩阵'&&<MatrixView workspace={workspace}/>}
    {tab==='洞见'&&<InsightsView workspace={workspace}/>}
    {tab==='发言稿'&&<DraftsView workspace={workspace} edit={editDraft}/>}
    <section className="evolve-card"><div className="evolve-icon"><RefreshCw/></div><div><span className="tag">策略实验室</span><h3>让策略从对抗中成长</h3><p>{evo?`${evo.message} 累计 ${evo.aggregate_games} 场 / ${evo.unique_topics} 个辩题，候选胜率 ${(evo.aggregate_win_rate*100).toFixed(0)}%。`:'运行小规模双向自博弈；只有跨至少 5 个辩题、累计 20 场并达到 55% 胜率才会自动晋级。'}</p></div><button className="secondary" onClick={evolve} disabled={evolving}>{evolving?<LoaderCircle className="spin"/>:<BrainCircuit/>}{evolving?'评测中':'运行进化评测'}</button></section>
    {evo?.skill&&<SkillView result={evo}/>}
  </div>
}

function SkillView({result}:{result:any}){
  const skill=result.skill
  return <section className="skill-view"><div className="panel-heading"><div><span className="kicker">EVOLVED DEBATE SKILL</span><h2>{skill.name} <small>{skill.version}</small></h2></div><span className={`skill-status ${result.promoted?'active':'candidate'}`}>{result.promoted?'已晋级':'候选版'}</span></div><p className="skill-purpose">{skill.purpose}</p><div className="skill-columns"><div><h3>决策流程</h3><ol>{skill.decision_steps.map((item:string)=><li key={item}>{item}</li>)}</ol></div><div><h3>本轮沉淀经验</h3>{skill.lessons.length?<ul>{skill.lessons.map((item:any,index:number)=><li key={`${index}-${item.trigger}`}><b>{item.trigger}</b><span>{item.action}</span><small>{Math.round(item.confidence*100)}% 置信度</small></li>)}</ul>:<p className="muted">本轮尚未形成可跨辩题复用的经验。</p>}</div></div><details><summary>查看完整 Skill 文本</summary><pre>{result.skill_markdown}</pre></details></section>
}

function DebateHistory({debates,onOpen,onDelete,empty}:{debates:DebateHistory[];onOpen:(d:DebateHistory)=>void;onDelete:(d:DebateHistory)=>void;empty:string}){
  const [confirmId,setConfirmId]=useState<string|null>(null)
  return <section className="history-panel mode-history"><div className="panel-heading"><div><span className="kicker">DEBATE SESSIONS</span><h2>历史对辩</h2></div></div>{debates.length===0?<p className="muted">{empty}</p>:<div className="history-list">{debates.map(debate=><article className="history-item" key={debate.id}><div><b>{debate.status==='finished'?'已完成':debate.status==='paused'?'已暂停':'进行中'}</b><small>{new Date(debate.updated_at).toLocaleString('zh-CN')} · {debate.turn_count} 条发言 · {debate.difficulty}</small></div><div className="history-actions"><button className="secondary" onClick={()=>onOpen(debate)}><HistoryIcon/>{debate.status==='finished'?'查看对话':'继续查看'}</button><button className={`history-delete ${confirmId===debate.id?'confirm':''}`} onClick={()=>{if(confirmId===debate.id){setConfirmId(null);onDelete(debate)}else{setConfirmId(debate.id)}}}>{confirmId===debate.id?'确认删除？':<Trash2 size={14}/>}</button></div></article>)}</div>}</section>
}

function Overview({workspace,toggleLock}:{workspace:Workspace;toggleLock:(id:string)=>void}){
  return <div className="overview-grid"><section className="panel span-2"><div className="panel-heading"><div><span className="kicker">ARGUMENT MAP</span><h2>双边论证地图</h2></div><span className="legend"><i className="pro-dot"/>正方 <i className="con-dot"/>反方</span></div><div className="argument-columns">{(['正方','反方'] as Stance[]).map(s=><div key={s} className={`argument-side ${s==='正方'?'pro':'con'}`}><h3>{s}的核心论证</h3>{workspace.arguments.filter(a=>a.stance===s).map(a=><article className="argument-card" key={a.id}><button className="lock" onClick={()=>toggleLock(a.id)} title="锁定论点">{a.locked?<Lock/>:<Unlock/>}</button><span>{textValue(a.title)}</span><h4>{textValue(a.claim)}</h4><p>{textValue(a.warrant)}</p><small>{textValue(a.status)}</small></article>)}</div>)}</div></section>
    <section className="panel"><span className="kicker">DEBATE CORE</span><h2>辩题拆解</h2><Info label="判断标准" text={workspace.analysis.criterion}/><Info label="核心冲突" text={workspace.analysis.conflicts.map(textValue).join(' · ')}/><Info label="正方责任" text={workspace.analysis.burdens?.正方}/><Info label="反方责任" text={workspace.analysis.burdens?.反方}/></section>
  </div>
}
function Info({label,text}:{label:string;text:unknown}){return <div className="info-row"><span>{label}</span><p>{textValue(text)}</p></div>}
function EvidenceView({workspace}:{workspace:Workspace}){return <div><div className="evidence-grid">{workspace.evidence.map((e,i)=><article className="evidence-card" key={e.id}><div className="evidence-top"><span className="number">{String(i+1).padStart(2,'0')}</span><span className={`cred ${textValue(e.credibility).includes('高')?'high':''}`}>{textValue(e.credibility)||'待审计'}</span></div><h3>{textValue(e.title)}</h3><p>{textValue(e.claim)}</p><div className="scope"><b>适用边界</b>{textValue(e.scope)}</div>{e.url?<a href={e.url} target="_blank">{textValue(e.domain)||'查看来源'} <ArrowRight/></a>:<span className="muted">无可用来源</span>}</article>)}</div>{workspace.warnings?.length?<div className="evidence-warnings">{workspace.warnings.map((w,i)=><div className="warning" key={i}>资料提示：{textValue(w)}</div>)}</div>:null}</div>}
function MatrixView({workspace}:{workspace:Workspace}){return <div className="matrix"><div className="matrix-head"><span>我方论点</span><span>预判攻击</span><span>回应路径</span></div>{workspace.matrix.map((m,i)=><div className="matrix-row" key={i}><div><b>{i+1}</b>{textValue(m.our)}</div><div>{textValue(m.attack)}</div><div>{textValue(m.response)}</div></div>)}</div>}
function InsightsView({workspace}:{workspace:Workspace}){return <div className="insight-list">{workspace.insights.map((x,i)=><article key={i}><div className="score">{Math.round((Number(x.score)||0)*100)}<small>/100</small></div><div><span>{textValue(x.lens)}</span><h3>{textValue(x.idea)}</h3><p>{textValue(x.support)}</p></div></article>)}</div>}
function DraftsView({workspace,edit}:{workspace:Workspace;edit:(k:string,v:string)=>void}){return <div className="drafts">{Object.entries(workspace.drafts).map(([k,v])=><section className="draft-card" key={k}><div><span className="draft-stage">{k}</span><small>{Array.isArray(v)?`${v.length} 组弹药`:`${String(v).length} 字`}</small></div><textarea value={Array.isArray(v)?v.join('\n'):v} onChange={e=>edit(k,e.target.value)}/></section>)}</div>}

function HumanDebate({project,workspace,resumeTarget,onClearResume,onResume,setError}:{project:Project;workspace:Workspace;resumeTarget:ResumeTarget;onClearResume:()=>void;onResume:(debate:DebateHistory)=>void;setError:(x:string)=>void}){
  const [debate,setDebate]=useState<Debate|null>(null),[difficulty,setDifficulty]=useState('标准'),[stage,setStage]=useState('自由辩论'),[text,setText]=useState(''),[turns,setTurns]=useState<Turn[]>([]),[sending,setSending]=useState(false),[pendingTurn,setPendingTurn]=useState<Turn|null>(null),[evaluation,setEvaluation]=useState<Evaluation|null>(null),[showEval,setShowEval]=useState(false),[liveFinished,setLiveFinished]=useState(false),[history,setHistory]=useState<ProjectHistory|null>(null)
  useEffect(()=>{let active=true;if(!resumeTarget||resumeTarget.mode!=='human')return;api.debate(resumeTarget.id).then((loaded:Debate)=>{if(!active)return;setDebate(loaded);setTurns(loaded.turns||[]);setDifficulty(loaded.difficulty);setStage(loaded.state?.stage||'自由辩论');setEvaluation(loaded.evaluation||null);setShowEval(false);setLiveFinished(false);setPendingTurn(null)}).catch((e:any)=>setError(e.message));return()=>{active=false}},[resumeTarget])
  useEffect(()=>{if(debate)return;let active=true;api.history(project.id).then((h:ProjectHistory)=>{if(active)setHistory(h)}).catch((e:any)=>setError(e.message));return()=>{active=false}},[debate,project.id,setError])
  const start=async()=>{onClearResume();try{const d=await api.createDebate({project_id:project.id,mode:'human',user_stance:project.stance,difficulty,rounds:8});setDebate(d);setTurns([]);setEvaluation(null);setShowEval(false);setLiveFinished(false)}catch(e:any){setError(e.message)}}
  const deleteHistory=async(debate:DebateHistory)=>{try{await api.deleteDebate(debate.id);setHistory(await api.history(project.id))}catch(e:any){setError(e.message)}}
  const send=async()=>{if(!debate||!text.trim()||sending)return;const content=text.trim();const optimistic:Turn={id:`pending-${Date.now()}`,speaker:'用户',stance:project.stance,stage,content,meta:{},created_at:new Date().toISOString()};setPendingTurn(optimistic);setText('');setSending(true);try{const r=await api.turn(debate.id,{content,stage});setTurns(x=>[...x,r.user_turn,r.ai_turn]);setPendingTurn(null)}catch(e:any){setPendingTurn(null);setText(content);setError(`发送未完成：${e.message}`)}finally{setSending(false)}}
  const finish=async()=>{if(!debate||sending)return;setSending(true);try{setEvaluation(await api.finish(debate.id));setShowEval(true);setLiveFinished(true)}catch(e:any){setError(e.message)}finally{setSending(false)}}
  if(!debate)return <ModeStart icon={<Swords/>} eyebrow="HUMAN VS AGENT" title="把赛场交给真正的交锋" desc="选择训练强度。AI 会针对你刚刚说的内容回应，而不是机械背稿。"><div className="difficulty">{['陪练','标准','赛事'].map(d=><button key={d} className={difficulty===d?'selected':''} onClick={()=>setDifficulty(d)}><b>{d}</b><small>{d==='陪练'?'适度提示遗漏':d==='标准'?'完整正常攻防':'严格规则与计时'}</small></button>)}</div><button className="primary big" onClick={start}>进入辩论室 <ArrowRight/></button><div className="mode-history"><DebateHistory debates={(history?.debates||[]).filter(d=>d.mode==='human')} onOpen={onResume} onDelete={deleteHistory} empty="还没有人机对辩记录，完成第一场后可以在这里继续复盘。"/></div></ModeStart>
  if(showEval&&evaluation)return <EvaluationView evaluation={evaluation} backLabel={liveFinished?'再来一场':'返回对话'} onBack={()=>{if(liveFinished){onClearResume();setDebate(null);setEvaluation(null);setShowEval(false)}else{setShowEval(false)}}}/>
  return <div className="debate-layout"><header className="debate-header"><div><span className="live-dot"/> 人机对辩 · {difficulty}</div><h2>{project.topic}</h2>{evaluation?<button className="secondary" onClick={()=>setShowEval(true)}><Trophy/>查看复盘</button>:<button className="secondary" onClick={finish} disabled={sending}>结束并复盘</button>}</header><div className="stage-bar">{stages.map(s=><button disabled={sending} className={stage===s?'active':''} onClick={()=>setStage(s)} key={s}>{s}</button>)}</div><div className="conversation">{turns.length===0&&!pendingTurn&&<div className="conversation-empty"><MessageSquareQuote/><h3>请发表你的第一轮观点</h3><p>你持{project.stance}，AI 持{project.stance==='正方'?'反方':'正方'}。</p></div>}{turns.map(t=><TurnBubble key={t.id} turn={t} userStance={project.stance}/>)}{pendingTurn&&<TurnBubble turn={pendingTurn} userStance={project.stance}/>} {sending&&<div className="agent-thinking"><span className="thinking-avatar">AI</span><div><b>对方 Agent 正在思考</b><small>正在梳理你的论证、核对证据并选择最值得回应的争点</small><span className="thinking-dots"><i/><i/><i/></span></div></div>}</div><div className="composer"><textarea disabled={sending||!!evaluation} value={text} onChange={e=>setText(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&(e.metaKey||e.ctrlKey))send()}} placeholder={evaluation?'本场对辩已结束，可查看复盘。':sending?'已发送，对方 Agent 正在思考…':`以${project.stance}身份发言…（Ctrl/⌘ + Enter 发送）`}/><div><span>{sending?'已发送，等待对方回应…':evaluation?'已结束':`${text.length} 字`}</span><button className={`primary ${sending?'thinking-button':''}`} onClick={send} disabled={!text.trim()||sending||!!evaluation}>{sending?<><LoaderCircle className="spin"/><span>思考中</span></>:<ArrowRight/>}</button></div></div><DebateSidebar workspace={workspace} turns={turns}/></div>
}
function TurnBubble({turn,userStance}:{turn:Turn;userStance:Stance}){const mine=turn.stance===userStance;return <article className={`turn ${mine?'mine':'theirs'}`}><div className="turn-meta"><span>{turn.stance}</span><b>{turn.speaker}</b><small>{turn.stage}</small></div><p>{turn.content}</p>{turn.meta?.spark&&<blockquote><Flame/>{turn.meta.spark}</blockquote>}{turn.meta?.explanation&&<details><summary>为什么这样回应？</summary><p><b>回应策略：</b>{turn.meta.explanation}</p>{turn.meta?.lens&&<p><b>本轮视角：</b>{turn.meta.lens}</p>}{turn.meta?.topic_link&&<p><b>回扣原题：</b>{turn.meta.topic_link}</p>}{turn.meta?.new_ground&&<p><b>新增内容：</b>{turn.meta.new_ground}</p>}</details>}</article>}
function DebateSidebar({workspace,turns}:{workspace:Workspace;turns:Turn[]}){return <aside className="debate-side"><span className="kicker">LIVE CONTEXT</span><h3>当前争点</h3>{workspace.analysis.conflicts.map((x,i)=><div className="focus" key={`${i}-${textValue(x)}`}><i/>{textValue(x)}</div>)}<h3>已公开证据</h3><p className="muted">{turns.some(t=>t.meta?.evidence_ids?.length)?'本轮已有证据卡被调用':'尚未调用证据卡'}</p><h3>训练提醒</h3><p>回应对方最强的论点，比攻击最弱的措辞更有价值。</p></aside>}

function Arena({project,workspace,resumeTarget,onClearResume,onResume,setError}:{project:Project;workspace:Workspace;resumeTarget:ResumeTarget;onClearResume:()=>void;onResume:(debate:DebateHistory)=>void;setError:(x:string)=>void}){
  const [debate,setDebate]=useState<Debate|null>(null),[turns,setTurns]=useState<Turn[]>([]),[status,setStatus]=useState('idle'),[evaluation,setEvaluation]=useState<Evaluation|null>(null),[history,setHistory]=useState<ProjectHistory|null>(null)
  const source=useRef<EventSource|null>(null)
  const startStream=(id:string)=>{source.current?.close();const es=new EventSource(`/api/debates/${id}/stream`);source.current=es;setStatus('running');es.addEventListener('turn',(ev:any)=>{const data=JSON.parse(ev.data);setTurns(x=>[...x,data.turn])});es.addEventListener('status',(ev:any)=>setStatus(JSON.parse(ev.data).status));es.addEventListener('finished',(ev:any)=>{const data=JSON.parse(ev.data);setEvaluation(data.evaluation);setStatus('finished');es.close()});es.onerror=()=>{if(status!=='paused')setError('竞技场连接暂时中断，可刷新后继续。')}}
  useEffect(()=>()=>source.current?.close(),[])
  useEffect(()=>{let active=true;if(!resumeTarget||resumeTarget.mode!=='arena')return;api.debate(resumeTarget.id).then((loaded:Debate)=>{if(!active)return;setDebate(loaded);setTurns(loaded.turns||[]);setStatus(loaded.status);setEvaluation(loaded.evaluation||null);if(loaded.status==='ready'||loaded.status==='running')startStream(loaded.id)}).catch((e:any)=>setError(e.message));return()=>{active=false;source.current?.close()}},[resumeTarget])
  useEffect(()=>{if(debate)return;let active=true;api.history(project.id).then((h:ProjectHistory)=>{if(active)setHistory(h)}).catch((e:any)=>setError(e.message));return()=>{active=false}},[debate,project.id,setError])
  const start=async()=>{onClearResume();try{const d=await api.createDebate({project_id:project.id,mode:'arena',user_stance:'正方',difficulty:'赛事',rounds:8});setDebate(d);setTurns([]);setEvaluation(null);startStream(d.id)}catch(e:any){setError(e.message)}}
  const toggle=async()=>{if(!debate)return;try{if(status==='paused'){await api.resume(debate.id);startStream(debate.id)}else{await api.pause(debate.id);setStatus('paused')}}catch(e:any){setError(e.message)}}
  const deleteHistory=async(debate:DebateHistory)=>{try{await api.deleteDebate(debate.id);setHistory(await api.history(project.id))}catch(e:any){setError(e.message)}}
  if(!debate)return <ModeStart icon={<BrainCircuit/>} eyebrow="AGENT VS AGENT" title="坐上思想竞技场的第一排" desc="正反 Agent 隔离思考、逐轮交锋。你可以随时暂停，审视此刻真正决定胜负的东西。"><div className="arena-preview"><div className="fighter pro"><span>正</span><b>建构者</b><small>机制 · 价值 · 可行性</small></div><div className="versus">VS</div><div className="fighter con"><span>反</span><b>破局者</b><small>边界 · 代价 · 反事实</small></div></div><button className="primary big" onClick={start}><CirclePlay/>开始机器辩论</button><div className="mode-history"><DebateHistory debates={(history?.debates||[]).filter(d=>d.mode==='arena')} onOpen={onResume} onDelete={deleteHistory} empty="还没有机器竞技记录，完成第一场后可以在这里继续复盘。"/></div></ModeStart>
  return <div className="arena-page"><header className="arena-header"><div><span className="live-dot"/> AGENT ARENA</div><h1>{project.topic}</h1><div className="arena-controls">{status!=='finished'&&<button className="secondary" onClick={toggle}>{status==='paused'?<CirclePlay/>:<CirclePause/>}{status==='paused'?'继续':'暂停'}</button>}</div></header><div className="arena-stage"><div className="arena-column pro-col"><h3><span>正</span>正方 Agent</h3>{turns.filter(t=>t.stance==='正方').map(t=><ArenaTurn key={t.id} turn={t}/>)}</div><div className="center-line"><span>{turns.length||0}</span><small>回合事件</small></div><div className="arena-column con-col"><h3><span>反</span>反方 Agent</h3>{turns.filter(t=>t.stance==='反方').map(t=><ArenaTurn key={t.id} turn={t}/>)}</div></div>{status==='paused'&&<div className="paused-banner"><CirclePause/><div><b>竞技场已暂停</b><span>此刻可以检查论证地图与证据，再继续观战。</span></div></div>}{evaluation&&<EvaluationView evaluation={evaluation} compact onBack={()=>{onClearResume();setDebate(null);setEvaluation(null)}}/>}</div>
}
function ArenaTurn({turn}:{turn:Turn}){return <article className="arena-turn"><span>{turn.stage}</span><p>{turn.content}</p>{turn.meta?.spark&&<blockquote>{turn.meta.spark}</blockquote>}<small>{turn.meta?.tactic} · {turn.meta?.issue}</small></article>}
function ModeStart({icon,eyebrow,title,desc,children}:{icon:any;eyebrow:string;title:string;desc:string;children:any}){return <div className="page mode-start"><div className="mode-icon">{icon}</div><span className="kicker">{eyebrow}</span><h1>{title}</h1><p>{desc}</p>{children}</div>}

function EvaluationView({evaluation,onBack,compact=false,backLabel='再来一场'}:{evaluation:Evaluation;onBack:()=>void;compact?:boolean;backLabel?:string}){
  const dims=['persuasion','response','logic','evidence','insight'];const labels:Record<string,string>={persuasion:'说服力',response:'回应度',logic:'逻辑',evidence:'证据',insight:'洞见'}
  return <section className={`evaluation ${compact?'compact':''}`}><div className="eval-title"><Trophy/><div><span className="kicker">DEBATE REVIEW</span><h2>{evaluation.winner==='平局'?'势均力敌':`${evaluation.winner}占优`}</h2><p>{evaluation.summary}</p></div></div><div className="score-table"><div/><b>正方</b><b>反方</b>{dims.map(d=><div className="score-row" key={d}><span>{labels[d]}</span><strong>{evaluation.scores?.正方?.[d]??'—'}</strong><strong>{evaluation.scores?.反方?.[d]??'—'}</strong></div>)}</div><div className="eval-notes"><div><h3>关键转折</h3>{evaluation.turning_points?.map((x,i)=><p key={i}>{x}</p>)}</div><div><h3>下一步训练</h3>{evaluation.exercises?.map((x,i)=><p key={i}>{x}</p>)}</div></div><button className="secondary" onClick={onBack}><RefreshCw/>{backLabel}</button></section>
}

export default App
