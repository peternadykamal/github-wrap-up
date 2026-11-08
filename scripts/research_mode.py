#!/usr/bin/env python3
"""Plan and account for bounded model-facing research, independently of collection."""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, math, re, sys
from pathlib import Path
from build_facts import digest, load, rows, save
import model_policy

POLICIES={
 'low':{'initialBundles':24,'followUpRounds':1,'followUpBundlesPerRound':6,'researchJobs':1,'coordinators':0,'review':'combined','sharedBundles':12,'presentation':'reuse-personalized-layouts'},
 'medium':{'initialBundles':80,'followUpRounds':2,'followUpBundlesPerRound':20,'researchJobs':3,'coordinators':1,'review':'separate-factual-editorial','sharedBundles':32,'presentation':'selected-custom-diagrams'},
 'high':{'initialBundles':240,'followUpRounds':3,'followUpBundlesPerRound':60,'researchJobs':'per-relevant-repository','coordinators':1,'review':'independent-challenge','sharedBundles':64,'presentation':'extensive-evidence-led-customization'}}
ORDER={'low':0,'medium':1,'high':2}
PACKET_CHARS=12000
SUMMARY_CHARS=10000

def mode_name(value):
 value=str(value).strip().lower();value={'med':'medium','meduim':'medium'}.get(value,value)
 if value not in POLICIES:raise ValueError('Mode must be low, medium, or high')
 return value

def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def paths(run):
 run=Path(run).resolve();return run,run/'analysis/research-plan.json',run/'analysis/research-ledger.jsonl'
def ledger(run):
 _,_,lp=paths(run);return list(rows(lp))if lp.exists()else[]
def append(run,entry):
 _,_,lp=paths(run);entries=ledger(run);entry={'id':f'usage-{len(entries)+1:06d}','at':now(),**entry}
 if any(e['id']==entry['id']for e in entries):raise ValueError('Duplicate ledger ID')
 lp.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 # Single coordinator owns this file; workers must request packets/jobs through it.
 temp=lp.with_suffix('.tmp');temp.write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n'for e in [*entries,entry]));temp.chmod(0o600);temp.replace(lp);return entry

def scoped_repos(facts,pid):
 return facts['people'][pid].get('observedRepositories',[])

def initialize(run,mode=None,authorization=None,execution=None):
 run,pp,lp=paths(run);facts=load(run/'analysis/facts.json');manifest=load(run/'manifest.json')
 if facts['sourceManifestSha256']!=digest(run/'manifest.json'):raise ValueError('Rebuild stale facts before planning')
 old=load(pp)if pp.exists()else None;entries=ledger(run);mode=mode_name(mode or(old['mode']if old else'medium'));execution=execution or(old.get('executionMode','agents')if old else'agents');policy=POLICIES[mode]
 if execution not in ['agents','sequential-fallback']:raise ValueError('Unknown execution mode')
 if not old and execution=='sequential-fallback'and not(authorization and authorization.strip()):raise ValueError('Initial sequential fallback needs the actual runtime reason via --reason')
 if old:
  if old['factsSha256']!=digest(run/'analysis/facts.json')or old['sourceManifestSha256']!=digest(run/'manifest.json'):raise ValueError('Research inputs changed; use a new run rather than resetting used allowances')
  if old['mode']==mode and old.get('executionMode')==execution:return current(run)
  if not authorization or not authorization.strip():raise ValueError('Changing mode needs an explicit user authorization note; execution-only changes need the runtime reason')
  if ORDER[mode]<ORDER[old['mode']]and entries:raise ValueError('Cannot relabel spent higher-mode research as a cheaper run')
 people={}
 for subject in facts['subjects']:
  pid=subject['id'];repos=scoped_repos(facts,pid)
  people[pid]={'repositories':repos,'activeMonths':[x['month']for x in facts['people'][pid]['monthly']if x.get('observation')=='observed'],'initialBundles':policy['initialBundles'],'followUpRounds':policy['followUpRounds'],'followUpBundlesPerRound':policy['followUpBundlesPerRound'],'researchJobs':len(repos)if mode=='high'else policy['researchJobs'],'coordinators':policy['coordinators']if len(facts['subjects'])>1 else 0}
 value={'schemaVersion':1,'mode':mode,'executionMode':execution,'createdAt':old['createdAt']if old else now(),'updatedAt':now(),'factsSha256':digest(run/'analysis/facts.json'),'sourceManifestSha256':digest(run/'manifest.json'),'people':people,'shared':{'initialBundles':policy['sharedBundles'],'followUpRounds':policy['followUpRounds'],'followUpBundlesPerRound':max(1,policy['sharedBundles']//4)},'limits':{'packetChars':PACKET_CHARS,'returnedSummaryChars':SUMMARY_CHARS,'briefReadsPerSubject':2},'review':policy['review'],'presentation':policy['presentation'],'history':list(old.get('history',[]))if old else[],'tokenBudget':{'kind':'bounded-work-units','exactTokenLimitEnforced':False,'note':'Characters, packets and jobs bound declared research. Actual model, reasoning, cached and orchestration token consumption requires runtime measurements; never infer billed tokens from character counts.'}}
 value['executionReason']=(old.get('executionReason')if old and old.get('executionMode')==execution else authorization)if execution=='sequential-fallback'else None
 value['modelSelection']=old.get('modelSelection',{'status':'pending','mode':mode})if old and old['mode']==mode else model_policy.resolve(run,mode)
 value['legacyModelJobIds']=list(old.get('legacyModelJobIds',[]))if old and 'modelSelection'in old else[e['jobId']for e in entries if e['kind']=='job'and not e.get('modelRequest')]
 value['previousModelSelections']=list(old.get('previousModelSelections',[]))if old else[]
 value['modelSelectionChanges']=list(old.get('modelSelectionChanges',[]))if old else[]
 if old and old['mode']!=mode and old.get('modelSelection',{}).get('id'):value['previousModelSelections'].append(old['modelSelection'])
 if old:value['history'].append({'from':old['mode'],'to':mode,'executionFrom':old.get('executionMode'),'executionTo':execution,'at':now(),'authorization':authorization})
 save(pp,value)
 if not lp.exists():lp.touch(mode=0o600)
 return value

def current(run):
 run,pp,_=paths(run)
 if not pp.exists():raise ValueError('Create a research plan before model-facing research')
 plan=load(pp)
 if 'executionReason'in plan and plan.get('executionMode')=='sequential-fallback'and not plan.get('executionReason'):raise ValueError('Sequential fallback is missing its runtime reason')
 mode=mode_name(plan['mode']);policy=POLICIES[mode]
 if plan.get('limits')!={'packetChars':PACKET_CHARS,'returnedSummaryChars':SUMMARY_CHARS,'briefReadsPerSubject':2}:raise ValueError('Research limits were altered outside the planner')
 expected_shared={'initialBundles':policy['sharedBundles'],'followUpRounds':policy['followUpRounds'],'followUpBundlesPerRound':max(1,policy['sharedBundles']//4)}
 if plan.get('shared')!=expected_shared:raise ValueError('Shared mode allowance was altered outside the planner')
 for pid,caps in plan['people'].items():
  if any(caps.get(k)!=policy[k]for k in ['initialBundles','followUpRounds','followUpBundlesPerRound']):raise ValueError('Mode allowances were altered outside the planner')
 if plan['factsSha256']!=digest(run/'analysis/facts.json')or plan['sourceManifestSha256']!=digest(run/'manifest.json'):raise ValueError('Research plan inputs changed')
 if plan.get('modelSelection'):model_policy.need(plan['modelSelection']['mode']==mode,'Active model profile differs from the selected mode')
 for r in model_policy.all_resolutions(plan).values():model_policy.validate_resolution(run,r)
 return plan

def redact(text):
 text=str(text)
 text=re.sub(r'[\w.+%\-]+@[\w.\-]+\.[A-Za-z]{2,}','[email redacted]',text)
 text=re.sub(r'(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|AIza[A-Za-z0-9_-]{25,}|sk-[A-Za-z0-9_-]{20,})','[credential redacted]',text)
 if re.search(r'BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY',text):return '[Private key material omitted]'
 return text

def bound_packet(value,limit):
 # Explicit truncation, not dropping entire repos/months silently.
 text=json.dumps(value,ensure_ascii=False)
 if len(text)<=limit:return value
 items=value.get('items',[])
 for item in items:item['truncated']=True
 empty={**value,'items':[{**i,'excerpt':''}for i in items]};room=limit-len(json.dumps(empty,ensure_ascii=False))-128
 if room<0:raise ValueError('Too many source identifiers in one packet; request fewer sources')
 cap=max(0,room//max(1,len(items)))
 for i in items:i['excerpt']=i.get('excerpt','')[:cap]
 while len(json.dumps(value,ensure_ascii=False))>limit:
  longest=max(items,key=lambda i:len(i.get('excerpt','')))
  if not longest.get('excerpt'):raise ValueError('Packet envelope exceeds limit')
  longest['excerpt']=longest['excerpt'][:-max(1,len(longest['excerpt'])//10)]
 value['truncated']=True
 # Reserve accounted bytes for the final truncation marker.
 if len(json.dumps(value,ensure_ascii=False))>limit:return bound_packet(value,limit-32)
 return value

def allowance(plan,pid):
 if pid=='team':return plan['shared']
 if pid not in plan['people']:raise ValueError('Unknown subject')
 return plan['people'][pid]

def states(entries):
 result={}
 for e in entries:
  if e['kind']=='job':result[e['jobId']]={'active':True,'round':0}
  elif e['kind']=='job-finished':result[e['jobId']]['active']=False
  elif e['kind']=='job-resumed':result[e['jobId']]={'active':True,'round':e['round']}
 return result

def reader(run,pid,job_id=None):
 entries=ledger(run);status=states(entries);jobs=[e for e in entries if e['kind']=='job'and e.get('subjectId')==pid and status[e['jobId']]['active']and(job_id is None or e['jobId']==job_id)]
 if len(jobs)!=1:raise ValueError('Specify an active --job-id registered for this subject; resume its existing context for follow-up')
 model_policy.validate_job(run,current(run),jobs[0]);model_policy.compatible(current(run),jobs[0])
 return {**jobs[0],'activeRound':status[jobs[0]['jobId']]['round']}

def packet(run,pid,source_ids,bundle_id,phase=0,level='metadata',file=None,job_id=None):
 run,_,_=paths(run);plan=current(run);caps=allowance(plan,pid);used=ledger(run);reading_job=reader(run,pid,job_id)
 if phase!=reading_job['activeRound']:raise ValueError('Packet round must match the registered context round; resume for follow-up')
 if not isinstance(phase,int)or isinstance(phase,bool)or phase<0 or phase>caps['followUpRounds']:raise ValueError('Follow-up round exceeds this mode')
 maximum=caps['initialBundles']if phase==0 else caps['followUpBundlesPerRound']
 if sum(e.get('kind')=='packet'and e.get('subjectId')==pid and e.get('round')==phase for e in used)>=maximum:raise ValueError('Evidence allowance exhausted; qualify/omit the claim or obtain a user-authorized upgrade')
 if not bundle_id or any(e.get('bundleId')==bundle_id for e in used):raise ValueError('Every reading/re-reading needs a new bundle ID')
 if level not in ['metadata','diff','discussion','historical_source']:raise ValueError('Unknown packet level')
 source_ids=list(dict.fromkeys(source_ids));facts=load(run/'analysis/facts.json');sources=facts['sourceIndex']
 if not source_ids or len(source_ids)>80 or any(s not in sources for s in source_ids):raise ValueError('Supply 1–80 collected source IDs')
 if file and len(source_ids)!=1:raise ValueError('A custom historical file must have one supporting source ID')
 items=[]
 for sid in source_ids:
  s=sources[sid];location='';content=''
  if file or(level=='diff'and s.get('data',{}).get('detail')):
   location=file or s['data']['detail'];p=(run/location).resolve()
   if not p.is_relative_to(run)or not p.is_file():raise ValueError('Packet file must exist inside this run')
   content=p.read_text(errors='replace')
   if level=='diff' and not file:
    detail=json.loads(content);patches=[x for x in detail.get('patches',detail.get('files',[]))if x.get('patch')]
    if not patches:raise ValueError('No retained text diff is available; inspect metadata or collect source before claiming a diff reading')
    content=json.dumps({'sha':detail.get('sha'),'patches':patches,'limits':detail.get('limits'),'truncated':detail.get('truncated')},ensure_ascii=False)
  else:
   if level in ['diff','historical_source']:raise ValueError('No retained source excerpt; collect an excerpt and provide --file rather than labeling metadata as code')
   if level=='discussion'and s['kind']not in ['review','comment','pull_request','issue','timeline']:raise ValueError('Selected record is not discussion evidence')
   rp=run/'repos'/s['repo'].replace('/','__')/'records.jsonl';location=str(rp.relative_to(run));record=next((r for r in rows(rp)if r['id']==sid),None)
   if not record:raise ValueError('Original source record is missing')
   d=record.get('data',{});safe_data={k:v for k,v in d.items()if k not in ['authorEmail','committerEmail','authorName','committerName']}
   content=json.dumps({'title':record.get('title'),'body':record.get('body'),'data':safe_data},ensure_ascii=False)
  items.append({'sourceId':sid,'url':s['url'],'location':location,'level':level,'excerpt':redact(content),'truncated':False})
 result=bound_packet({'budgetEntryId':f'usage-{len(used)+1:06d}','subjectId':pid,'bundleId':bundle_id,'round':phase,'level':level,'items':items,'note':'Delivered context only. Log actual inspection separately after reading.'},plan['limits']['packetChars'])
 entry=append(run,{'kind':'packet',**model_policy.action_binding(plan),'subjectId':pid,'jobId':reading_job['jobId'],'agent':reading_job['agent'],'mode':plan['mode'],'bundleId':bundle_id,'round':phase,'level':level,'sourceIds':source_ids,'characters':len(json.dumps(result,ensure_ascii=False)),'truncated':result.get('truncated',False)or any(i['truncated']for i in result['items'])})
 assert result['budgetEntryId']==entry['id'];return result

def brief(run,pid,job_id=None):
 run,_,_=paths(run);plan=current(run);allowance(plan,pid);reading_job=reader(run,pid,job_id)
 if sum(e.get('kind')=='brief'and e.get('subjectId')==pid for e in ledger(run))>=plan['limits']['briefReadsPerSubject']:raise ValueError('Brief re-read allowance exhausted; reuse the existing context')
 f=load(run/'analysis/facts.json');subject=f['team']if pid=='team'else f['people'][pid];items=[]
 # Round-robin across month/repo/role, not top activity. Counts stay exhaustive on disk.
 buckets={}
 for sid,s in f['sourceIndex'].items():
  d=s.get('data',{});involved={s.get('actor'),d.get('author'),d.get('mergedBy'),*d.get('coauthors',[])}
  if pid!='team'and pid not in involved:continue
  if pid=='team'and not(set(plan['people'])&involved):continue
  stamp=s.get('occurredAt')or'';key=(stamp[:7],s['repo'],s['kind']);buckets.setdefault(key,[]).append((sid,s))
 for key,values in sorted(buckets.items()):
  sid,s=values[0];items.append({'sourceId':sid,'repo':s['repo'],'month':key[0],'kind':s['kind'],'excerpt':redact(s.get('title')or'')[:180],'url':s['url']})
 group_count=len(items);month_groups={}
 for item in items:month_groups.setdefault(item['month'],[]).append(item)
 selected=[]
 while len(selected)<12 and any(month_groups.values()):
  for month in sorted(month_groups):
   if month_groups[month] and len(selected)<12:selected.append(month_groups[month].pop(0))
 value={'budgetEntryId':f'usage-{len(ledger(run))+1:06d}','subjectId':pid,'totals':subject['totals'],'monthly':subject['monthly'][:36],'monthlyRowsAvailable':len(subject['monthly']),'repositories':subject['observedRepositories'][:32],'repositoriesAvailable':len(subject['observedRepositories']),'items':selected,'availableSourceGroups':group_count,'selectionLimited':len(selected)<group_count or len(subject['monthly'])>36 or len(subject['observedRepositories'])>32,'coverage':f['coverage'].get('status'),'note':'Scripted metadata briefing; selected titles are leads. Full inventory/facts remain on disk; unrepresented groups are not inspected.'}
 while True:
  try:result=bound_packet(json.loads(json.dumps(value)),plan['limits']['packetChars']);break
  except ValueError:
   value['selectionLimited']=True
   if len(value['items'])>1:value['items'].pop()
   elif len(value['repositories'])>8:value['repositories']=value['repositories'][:len(value['repositories'])//2]
   elif len(value['monthly'])>12:value['monthly']=value['monthly'][:12]
   else:raise
 entry=append(run,{'kind':'brief',**model_policy.action_binding(plan),'subjectId':pid,'jobId':reading_job['jobId'],'agent':reading_job['agent'],'mode':plan['mode'],'characters':len(json.dumps(result,ensure_ascii=False)),'sourceIds':[x['sourceId']for x in result['items']],'truncated':result.get('truncated',False)})
 assert result['budgetEntryId']==entry['id'];return result

def job(run,pid,job_id,role,repos=None,agent='root',reason='',runtime_reported=None,preview=False):
 plan=current(run);caps=allowance(plan,pid);entries=ledger(run);roles=['researcher','coordinator','inspector','challenge']
 if role not in roles or not job_id or not agent:raise ValueError('Job ID, execution agent and valid role required')
 if any(e.get('jobId')==job_id for e in entries):raise ValueError('Fresh contexts require distinct job IDs; resume an existing agent without registering it again')
 repos=sorted(set(repos or[]))
 if role in ['inspector','challenge']:
  if pid!='team':raise ValueError('Inspection/challenge jobs use the shared team allowance')
  maximum=1
  if role=='challenge'and(plan['mode']=='low'or(plan['mode']=='medium'and not reason)):raise ValueError('Challenge review is unavailable in Low and requires material uncertainty in Medium')
 else:
  if pid=='team':raise ValueError('Research jobs must name a person')
  if not set(repos)<=set(caps['repositories']):raise ValueError('Research job contains an unrelated repository')
  maximum=caps['coordinators']if role=='coordinator'else caps['researchJobs']
  if plan['mode']=='high'and role=='researcher'and len(repos)!=1:raise ValueError('High uses one relevant repository per researcher')
  if plan['mode']=='high'and role=='researcher'and any(e.get('kind')=='job'and e.get('mode')=='high'and e.get('subjectId')==pid and e.get('role')==role and e.get('repos')==repos for e in entries):raise ValueError('Resume the repository researcher instead of duplicating its context')
 if sum(e.get('kind')=='job'and e.get('mode')==plan['mode']and e.get('subjectId')==pid and e.get('role')==role for e in entries)>=maximum:raise ValueError('Agent/job allowance exhausted for this mode')
 binding=model_policy.request(plan,role,None if preview else agent)
 value={'kind':'job','jobId':job_id,'mode':plan['mode'],'executionMode':plan['executionMode'],'subjectId':pid,'role':role,'repos':repos,'agent':agent,'reason':reason,'modelRequest':binding}
 if plan['executionMode']=='sequential-fallback':
  prior=next((j for j in entries if j['kind']=='job'and j.get('executionMode')=='sequential-fallback'),None)
  value['executionRootAgentId']=plan.get('modelSelection',{}).get('rootAgentId')or(prior['agent']if prior else agent)
 if runtime_reported is not None:value['runtimeReported']=runtime_reported
 model_policy.validate_job(run,plan,value)
 if not preview:model_policy.distinct_agent(plan,value,[e for e in entries if e['kind']=='job'])
 if preview:return {'job':value,'launch':binding['dispatch'],'note':'Check passed without registering a job. Launch through the runtime, then register its actual agent ID.'}
 return append(run,value)

def resume(run,job_id,reason,phase=1):
 plan=current(run);entries=ledger(run);j=next((e for e in entries if e['kind']=='job'and e['jobId']==job_id),None)
 if not j:raise ValueError('Unknown job')
 model_policy.validate_job(run,plan,j)
 model_policy.compatible(plan,j)
 if states(entries)[job_id]['active']:raise ValueError('Job is already active')
 if not reason or not reason.strip():raise ValueError('Record the follow-up reason')
 caps=allowance(plan,j['subjectId'])
 if not isinstance(phase,int)or isinstance(phase,bool)or phase<0 or phase>caps['followUpRounds']:raise ValueError('Follow-up round exceeds this mode')
 if phase==0 and j['mode']==plan['mode']:raise ValueError('Initial round can only resume an existing context after an authorized mode upgrade')
 return append(run,{'kind':'job-resumed',**model_policy.action_binding(plan),'jobId':job_id,'mode':plan['mode'],'round':phase,'reason':reason})

def finish(run,job_id,summary):
 plan=current(run);entries=ledger(run)
 if not any(e.get('kind')=='job'and e.get('jobId')==job_id for e in entries):raise ValueError('Unknown job')
 if not states(entries)[job_id]['active']:raise ValueError('Job already completed; resume it before another follow-up')
 if not summary or len(summary)>plan['limits']['returnedSummaryChars']:raise ValueError('Return a concise job summary within the mode context limit')
 return append(run,{'kind':'job-finished','jobId':job_id,'round':states(entries)[job_id]['round'],'characters':len(summary),'summarySha256':hashlib.sha256(summary.encode()).hexdigest()})

def record_tokens(run,measurement_id,input_tokens,output_tokens,source,cached_input_tokens=None):
 current(run)
 if not source or not measurement_id or any(e.get('measurementId')==measurement_id for e in ledger(run)):raise ValueError('Runtime measurement needs a distinct ID and actual measurement source')
 values=[input_tokens,output_tokens]+([]if cached_input_tokens is None else[cached_input_tokens])
 if any(not isinstance(v,int)or isinstance(v,bool)or v<0 for v in values):raise ValueError('Token counts must be measured nonnegative integers')
 if cached_input_tokens is not None and cached_input_tokens>input_tokens:raise ValueError('Cached input is a subset of input tokens')
 return append(run,{'kind':'tokens','measurementId':measurement_id,'inputTokens':input_tokens,'outputTokens':output_tokens,'cachedInputTokens':cached_input_tokens,'measurementSource':source,'coverage':'recorded call only; not guaranteed full run'})

def report(run):
 plan=current(run);entries=ledger(run);subjects={}
 for pid in [*plan['people'],'team']:
  allow=allowance(plan,pid);subjects[pid]={'packetsByRound':{str(n):sum(e.get('kind')=='packet'and e.get('subjectId')==pid and e.get('round')==n for e in entries)for n in range(allow['followUpRounds']+1)},'deliveredCharacters':sum(e.get('characters',0)for e in entries if e.get('subjectId')==pid and e['kind']in ['packet','brief']),'jobs':sum(e['kind']=='job'and e.get('subjectId')==pid for e in entries)}
 measured=[e for e in entries if e['kind']=='tokens'];return {'mode':plan['mode'],'executionMode':plan['executionMode'],'executionReason':plan.get('executionReason'),'reviewIndependence':'unavailable in sequential fallback'if plan['executionMode']=='sequential-fallback'else'requires distinct completed registered agents','childProfileDispatch':'requested settings require runtime confirmation'if plan['executionMode']=='agents'else'not applied; inherited root settings','modelSelection':plan.get('modelSelection',{'status':'legacy-inherited'}),'jobModels':[{'jobId':e['jobId'],'agent':e['agent'],'requested':e.get('modelRequest'),'runtimeReported':e.get('runtimeReported')}for e in entries if e['kind']=='job'],'subjects':subjects,'actualTokens':{'input':sum(e['inputTokens']for e in measured),'output':sum(e['outputTokens']for e in measured),'scope':'measured calls only','measurements':len(measured)}if measured else None,'exactTokenLimitEnforced':False,'note':'Work-unit limits are enforced for registered jobs/packets. They do not meter unreported runtime context, reasoning or orchestration tokens.'}

def validate_mode(run,judge,read_log):
 plan=current(run);entries=ledger(run);ids={};jobs={};finished=set();active_rounds={}
 authorized_modes={plan['mode']}
 for change in plan.get('history',[]):
  if not change.get('authorization'):raise ValueError('Mode history is missing authorization/reason')
  authorized_modes.update([change['from'],change['to']])
 for e in entries:
  if e.get('mode')and e['mode']not in authorized_modes:raise ValueError('Ledger contains an unauthorized research mode')
  if e.get('id')in ids:raise ValueError('Duplicate mode ledger entry')
  ids[e.get('id')]=e
  if e['kind']=='job':
   if e['jobId']in jobs:raise ValueError('Duplicate research job ID')
   model_policy.validate_job(run,plan,e);model_policy.distinct_agent(plan,e,list(jobs.values()))
   jobs[e['jobId']]=e;active_rounds[e['jobId']]=0
  elif e['kind']=='job-finished':
   if e['jobId']not in jobs or e['jobId']in finished or e.get('round',0)!=active_rounds[e['jobId']]or e['characters']>plan['limits']['returnedSummaryChars']:raise ValueError('Invalid job completion')
   finished.add(e['jobId'])
  elif e['kind']=='job-resumed':
   if e['jobId']not in jobs or e['jobId']not in finished or not e.get('reason'):raise ValueError('Invalid research context resume')
   model_policy.validate_action(plan,jobs[e['jobId']],e)
   caps=allowance(plan,jobs[e['jobId']]['subjectId'])
   if not isinstance(e.get('round'),int)or isinstance(e.get('round'),bool)or e['round']not in range(caps['followUpRounds']+1):raise ValueError('Invalid resumed round')
   if e['round']==0 and jobs[e['jobId']]['mode']==e['mode']:raise ValueError('Unauthorized initial-round resume')
   finished.remove(e['jobId']);active_rounds[e['jobId']]=e['round']
  elif e['kind']in ['packet','brief']:
   allowance(plan,e['subjectId'])
   if e.get('jobId')in finished:raise ValueError('Packet delivered to a finished context without resuming')
   if e.get('jobId')not in jobs or jobs[e['jobId']]['subjectId']!=e['subjectId']or jobs[e['jobId']]['agent']!=e.get('agent'):raise ValueError('Packet is not bound to its registered reader')
   model_policy.validate_action(plan,jobs[e['jobId']],e)
   if e['kind']=='packet'and e.get('round')!=active_rounds[e['jobId']]:raise ValueError('Packet round differs from active context round')
   if not isinstance(e.get('characters'),int)or not 0<=e['characters']<=plan['limits']['packetChars']:raise ValueError('Mode packet exceeds context limit')
  elif e['kind']!='tokens':raise ValueError('Unknown mode ledger entry')
 for pid in [*plan['people'],'team']:
  caps=allowance(plan,pid)
  if sum(e['kind']=='brief'and e.get('subjectId')==pid for e in entries)>plan['limits']['briefReadsPerSubject']:raise ValueError('Brief reading limit exceeded')
  for phase in range(caps['followUpRounds']+1):
   count=sum(e['kind']=='packet'and e.get('subjectId')==pid and e.get('round')==phase for e in entries);maximum=caps['initialBundles']if phase==0 else caps['followUpBundlesPerRound']
   if count>maximum:raise ValueError('Evidence bundle allowance exceeded')
  if any(e['kind']=='packet'and e.get('subjectId')==pid and e.get('round')not in range(caps['followUpRounds']+1)for e in entries):raise ValueError('Unauthorized follow-up round')
 # Recheck job limits at sealing as well as at registration; ledgers may be hand-edited.
 for mode in {e.get('mode')for e in entries if e['kind']=='job'}:
  if mode not in POLICIES:raise ValueError('Unknown mode in job ledger')
  for pid in [*plan['people'],'team']:
   for role in ['researcher','coordinator','inspector','challenge']:
    group=[j for j in jobs.values()if j['mode']==mode and j['subjectId']==pid and j['role']==role]
    if pid=='team':maximum=1 if role in ['inspector','challenge'] else 0
    elif role=='researcher':maximum=len(plan['people'][pid]['repositories'])if mode=='high'else POLICIES[mode]['researchJobs']
    elif role=='coordinator':maximum=POLICIES[mode]['coordinators']if len(plan['people'])>1 else 0
    else:maximum=0
    if len(group)>maximum:raise ValueError('Research job limit exceeded')
    if role=='challenge'and group and(mode=='low'or(mode=='medium'and not all(j.get('reason')for j in group))):raise ValueError('Unauthorized challenge review')
    if mode=='high'and role=='researcher'and(len({tuple(j['repos'])for j in group})!=len(group)or any(len(j['repos'])!=1 for j in group)):raise ValueError('Duplicate or unscoped High repository job')
    if any(not set(j.get('repos',[]))<=set(plan['people'][pid]['repositories'])for j in group if pid!='team'):raise ValueError('Unrelated repository job')
 for pid in plan['people']:
  if any(e['kind']in ['brief','packet']and e.get('subjectId')==pid for e in entries)and not any(j['subjectId']==pid and j['role']=='researcher'for j in jobs.values()):raise ValueError('Register the person’s research job before consuming context')
 if read_log and not any(j['role']=='inspector'for j in jobs.values()):raise ValueError('Register the root inspector job')
 for r in read_log:
  e=ids.get(r.get('budgetEntryId'));sid=r.get('sourceId')
  if not e or e['kind']not in ['packet','brief']or sid not in e.get('sourceIds',[]):raise ValueError('Reading log must cite its delivered research budgetEntryId')
  if r.get('agent')!=e.get('agent'):raise ValueError('Reading log agent differs from the delivered packet reader')
  if e['kind']=='brief'and r['level']!='metadata':raise ValueError('Metadata brief does not establish source inspection')
  if e['kind']=='packet'and r['level']!=e['level']:raise ValueError('Reading level differs from delivered packet')
 # Empty runs can avoid gratuitous research contexts, but coverage still receives factual/editorial review.
 passes=judge.get('reviewPasses',[]);needed=['combined']if plan['mode']=='low'else['factual','editorial']
 for kind in needed:
  if not any(p.get('type')==kind and p.get('status')=='passed'and p.get('reviewer')and p.get('notes')for p in passes):raise ValueError('Missing mode review pass: '+kind)
 if plan['mode']=='high':
  challenges=[p for p in passes if p.get('type')=='challenge'and p.get('status')=='passed'and p.get('reviewer')and p.get('notes')]
  if not challenges:raise ValueError('High requires a challenge review')
  if plan['executionMode']=='agents':
   other_agents={j['agent']for j in jobs.values()if j['role']!='challenge'}
   valid=[j for j in jobs.values()if j['role']=='challenge'and j['mode']=='high'and j['jobId']in finished and j['agent']not in other_agents]
   if not any(j['role']=='inspector'for j in jobs.values()):raise ValueError('Register the actual root inspector agent')
   if not any(p['reviewer']==j['agent']for p in challenges for j in valid):raise ValueError('High challenge must be completed by a distinct registered reviewer')
 if any(jid not in finished for jid in jobs):raise ValueError('Complete registered research/review jobs before sealing')
 return report(run)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True,type=Path);sub=p.add_subparsers(dest='action',required=True)
 s=sub.add_parser('plan');s.add_argument('--mode',type=mode_name);s.add_argument('--authorization','--reason',dest='authorization');s.add_argument('--execution',choices=['agents','sequential-fallback'])
 s=sub.add_parser('brief');s.add_argument('--subject',required=True);s.add_argument('--job-id')
 s=sub.add_parser('packet');s.add_argument('--subject',required=True);s.add_argument('--bundle-id',required=True);s.add_argument('--sources',nargs='+',required=True);s.add_argument('--round',type=int,default=0);s.add_argument('--level',choices=['metadata','diff','discussion','historical_source'],default='metadata');s.add_argument('--file');s.add_argument('--job-id')
 s=sub.add_parser('job');s.add_argument('--subject',required=True);s.add_argument('--job-id',required=True);s.add_argument('--role',required=True);s.add_argument('--repos',nargs='*');s.add_argument('--agent',default='root');s.add_argument('--reason',default='');s.add_argument('--runtime-reported',type=Path);s.add_argument('--preview',action='store_true')
 s=sub.add_parser('resume');s.add_argument('--job-id',required=True);s.add_argument('--reason',required=True);s.add_argument('--round',type=int,default=1)
 s=sub.add_parser('finish');s.add_argument('--job-id',required=True);s.add_argument('--summary-file',type=Path,required=True)
 s=sub.add_parser('tokens');s.add_argument('--measurement-id',required=True);s.add_argument('--input',type=int,required=True);s.add_argument('--output',type=int,required=True);s.add_argument('--cached-input',type=int);s.add_argument('--source',required=True)
 sub.add_parser('report');a=p.parse_args()
 try:
  if a.action=='plan':
   v=initialize(a.run,a.mode,a.authorization,a.execution);result={'mode':v['mode'],'subjects':len(v['people']),'plan':str(paths(a.run)[1]),'limits':v['limits'],'policy':POLICIES[v['mode']],'modelSelection':v.get('modelSelection'),'note':'The archive and facts are unchanged; existing packet usage is retained.'}
  elif a.action=='brief':result=brief(a.run,a.subject,a.job_id)
  elif a.action=='packet':result=packet(a.run,a.subject,a.sources,a.bundle_id,a.round,a.level,a.file,a.job_id)
  elif a.action=='job':result=job(a.run,a.subject,a.job_id,a.role,a.repos,a.agent,a.reason,load(a.runtime_reported)if a.runtime_reported else None,a.preview)
  elif a.action=='resume':result=resume(a.run,a.job_id,a.reason,a.round)
  elif a.action=='finish':result=finish(a.run,a.job_id,a.summary_file.read_text())
  elif a.action=='tokens':result=record_tokens(a.run,a.measurement_id,a.input,a.output,a.source,a.cached_input)
  else:result=report(a.run)
 except(ValueError,KeyError,FileNotFoundError,TypeError)as e:print(json.dumps({'error':str(e)}));return 1
 print(json.dumps(result,ensure_ascii=False,indent=None));return 0
if __name__=='__main__':raise SystemExit(main())
