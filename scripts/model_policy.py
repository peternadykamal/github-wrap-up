#!/usr/bin/env python3
"""Resolve stable workload policies from runtime-supplied models; no model IDs are shipped."""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, sys
from pathlib import Path
from urllib.parse import urlsplit
from build_facts import load,save,digest,instant
import runtime_adapter

# Classes and effort intents describe tasks, not model names or release generations.
PROFILES={
 'low':{'researcher':{'classes':['efficient'],'intent':'economical'},'coordinator':None,'challenge':None},
 'medium':{'researcher':{'classes':['balanced'],'intent':'moderate'},'coordinator':{'classes':['balanced','deep'],'intent':'deep'},'challenge':{'classes':['deep','balanced'],'intent':'deep'}},
 'high':{'researcher':{'classes':['balanced','deep'],'intent':'deep'},'coordinator':{'classes':['deep'],'intent':'deep'},'challenge':{'classes':['deep'],'intent':'deep'}}}
ROLES={'researcher','coordinator','challenge'}
MAX_CATALOG_AGE_HOURS=24

def utcnow():return dt.datetime.now(dt.timezone.utc)
def fingerprint(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def need(ok,message):
 if not ok:raise ValueError(message)
def inside(run,path):
 p=(run/path).resolve();need(p.is_relative_to(run)and p.is_file(),'Evidence file must exist inside the run');return p

def check_catalog(c,at=None,fresh=True):
 at=at or utcnow();need(c.get('schemaVersion')in [1,2],'Unsupported runtime catalog version');stamp=instant(c.get('capturedAt'));need(stamp is not None,'Runtime catalog needs capturedAt')
 if fresh:need(-300<=(at-stamp).total_seconds()<=MAX_CATALOG_AGE_HOURS*3600,'Capture a fresh runtime catalog before resolving models')
 source=c.get('source',{});need(source.get('kind')in ['tool-metadata','runtime-discovery']and source.get('identifier'),'Catalog must identify authoritative runtime availability; an API-wide model list is insufficient')
 controls=c.get('controls',{});need(all(isinstance(controls.get(k),bool)for k in ['modelOverride','effortOverride','freshContextRequired']),'Runtime override/context controls must be explicit')
 entries=c.get('models',[]);need(isinstance(entries,list),'Runtime models must be an array');seen=set()
 for m in entries:
  need(isinstance(m.get('id'),str)and m['id']and m['id']not in seen,'Duplicate/missing runtime model ID');seen.add(m['id']);need(isinstance(m.get('available'),bool)and isinstance(m.get('toolCalling'),bool),'Availability and tool support must be explicit')
  need(isinstance(m.get('supportedEfforts'),list)and all(isinstance(e,str)and e for e in m['supportedEfforts']),'Supported efforts must come from runtime metadata')
 if c['schemaVersion']==2:
  runtime_adapter.check(c)
  for m in entries:need(isinstance(m.get('effortValues',{}),dict)and set(m.get('effortValues',{}))<=set(m['supportedEfforts']),'Native effort mappings must use advertised effort labels')
 return {m['id']:m for m in entries}

def assessment_evidence(run,a,role,at,catalog_version=1):
 refs=a.get('guidance',[]);need(a.get('rationale')and refs,'Model assessment needs a rationale and dated guidance')
 for g in refs:
  checked=instant(g.get('checkedAt'));need(checked is not None and checked<=at+dt.timedelta(minutes=5),'Guidance needs a valid checkedAt')
  if g.get('kind')=='official-documentation':
   u=urlsplit(g.get('url',''));need(u.scheme=='https'and u.hostname and not u.username,'Use an actual fetched official documentation URL')
   if catalog_version==1:need(u.hostname in ['developers.openai.com','platform.openai.com','learn.chatgpt.com'],'Legacy catalogs require their original official OpenAI guidance')
   else:need(isinstance(g.get('publisher'),str)and g['publisher'].strip(),'Official guidance must name the model provider or harness publisher; verify the domain when reading')
  elif g.get('kind')=='runtime-metadata':need(g.get('identifier')and g.get('description'),'Runtime guidance must preserve the actual descriptor source')
  else:raise ValueError('Unknown model guidance source')
 status=a.get('validation',{}).get('status','guidance-only');need(status in ['validated','guidance-only'],'Unknown capability validation status')
 if status=='validated':
  proofs=a['validation'].get('evidence',[]);need(proofs,'Locally validated models need a recorded evaluation')
  passed=False
  for e in proofs:
   p=inside(run,e['path']);need(digest(p)==e.get('sha256'),'Model evaluation evidence changed');value=load(p)
   if value.get('modelId')==a['modelId']and value.get('passed')is True and role in value.get('roles',[]):passed=True
  need(passed,'No passing evaluation for this model and task role')
 return status

def inherited(c):
 parent=c.get('parent',{});confirmed=bool(parent.get('confirmedByRuntime',False))
 return {'status':'inherited-root','modelId':parent.get('modelId')if confirmed else None,'effort':parent.get('effort')if confirmed else None,'dispatch':{},'runtimeConfirmed':confirmed,'reason':('The current conversation retains harness-selected settings; this skill requests overrides only for child jobs.'if c.get('schemaVersion')==2 else'The current conversation retains app-selected settings; a skill cannot change its root model.')}

def resolve(run,mode,catalog_path=None,assessments_path=None):
 run=Path(run).resolve();need(mode in PROFILES,'Unknown research mode')
 cp=Path(catalog_path).resolve()if catalog_path else run/'analysis/runtime-models.json';ap=Path(assessments_path).resolve()if assessments_path else run/'analysis/model-assessments.json'
 if not cp.is_file()or not ap.is_file():return {'status':'pending','mode':mode,'reason':'Capture runtime-models.json and evidence-backed model-assessments.json; no model override is guessed.'}
 c=load(cp);models=check_catalog(c);assessment=load(ap);need(assessment.get('schemaVersion')==1,'Unsupported model assessment version');at=utcnow();by_id={}
 for a in assessment.get('models',[]):
  need(a.get('modelId')not in by_id,'Duplicate model assessment');by_id[a['modelId']]=a
 roles={'inspector':inherited(c)};disclosures=[]
 controls=c['controls'];can_override=controls['modelOverride']and(controls['effortOverride']or c['schemaVersion']==2)
 for role,policy in PROFILES[mode].items():
  if policy is None:roles[role]={'status':'not-used','reason':'This role is not used in the selected mode'};continue
  if not can_override:roles[role]={'status':'blocked','reason':('Runtime does not expose model overrides; use a disclosed fallback'if c['schemaVersion']==2 else'Runtime does not expose both model and effort overrides; no silent inheritance/cost claim')};continue
  eligible=[];rejected=[]
  for position,m in enumerate(c['models']):
   a=by_id.get(m['id'])
   if not(m['available']and m['toolCalling']and a):continue
   if a.get('selectionClass')not in policy['classes']or role not in a.get('roles',[]):continue
   try:
    status=assessment_evidence(run,a,role,at,c['schemaVersion']);effort=a.get('effortByIntent',{}).get(policy['intent'])if controls['effortOverride']else None
    if controls['effortOverride']:need(effort in m['supportedEfforts'],'Recommended effort is not advertised by this model/runtime')
   except(ValueError,KeyError,FileNotFoundError)as e:rejected.append({'modelId':m['id'],'reason':str(e)});continue
   # Validation before novelty; class order reflects task/cost policy, not ID spelling.
   key=(policy['classes'].index(a['selectionClass']),0 if status=='validated'else 1,0 if a.get('currentlyRecommended')is True else 1,position)
   eligible.append((key,m,a,effort,status))
  if not eligible:
   roles[role]={'status':'blocked','reason':'No available, tool-capable, evidence-backed model meets this role/effort policy','rejected':rejected};continue
  _,m,a,effort,status=min(eligible,key=lambda x:x[0]);dispatch=runtime_adapter.dispatch(c,m,effort)
  roles[role]={'status':'selected','modelId':m['id'],'effort':effort,'selectionClass':a['selectionClass'],'intent':policy['intent'],'basis':status,'provisional':status!='validated','guidance':a['guidance'],'rationale':a['rationale'],'dispatch':dispatch,'tieBreak':'Equal documented candidates use runtime order, not inferred version quality','runtimeConfirmed':False}
  if c['schemaVersion']==2:
   roles[role]['effortControl']='explicit'if controls['effortOverride']else'inherited'
   if not controls['effortOverride']:disclosures.append(role+': model selected; reasoning effort is inherited/unknown, so the requested effort profile is not achieved')
  if status!='validated':disclosures.append(role+': guidance-backed choice; not locally benchmarked')
 unresolved=[r for r in ['researcher']if roles[r]['status']=='blocked']
 # Coordinators/challenge are conditional by scope/review; check at job registration.
 value={'schemaVersion':c['schemaVersion'],'status':'resolved'if not unresolved else'blocked','mode':mode,'resolvedAt':at.isoformat(),'catalogCapturedAt':c['capturedAt'],'runtimeSource':c['source'],'rootAgentId':c.get('parent',{}).get('agentId'),'roles':roles,'disclosures':disclosures,'rootSettingsControlledByApp':True}
 if c['schemaVersion']==2:value['rootSettingsControlledByHarness']=value.pop('rootSettingsControlledByApp')
 rid=fingerprint({'mode':mode,'catalog':c,'assessments':assessment,'roles':roles});folder=run/'analysis/model-selections'/rid;save(folder/'runtime.json',c);save(folder/'assessments.json',assessment)
 value.update(id=rid,catalogPath=str((folder/'runtime.json').relative_to(run)),catalogSha256=digest(folder/'runtime.json'),assessmentsPath=str((folder/'assessments.json').relative_to(run)),assessmentsSha256=digest(folder/'assessments.json'))
 return value

def all_resolutions(plan):
 return {r['id']:r for r in [*plan.get('previousModelSelections',[]),plan.get('modelSelection',{})]if r.get('id')}

def validate_resolution(run,r):
 run=Path(run).resolve()
 if r.get('status')=='pending':return
 need(r.get('id')and r.get('mode')in PROFILES,'Invalid frozen model resolution')
 cp=inside(run,r['catalogPath']);ap=inside(run,r['assessmentsPath']);need(digest(cp)==r['catalogSha256']and digest(ap)==r['assessmentsSha256'],'Frozen model capability snapshot changed')
 c=load(cp);models=check_catalog(c,fresh=False);assessments={a['modelId']:a for a in load(ap).get('models',[])}
 for role,policy in PROFILES[r['mode']].items():
  choice=r['roles'][role]
  if choice['status']in ['blocked','not-used']:continue
  need(policy is not None and choice['status']=='selected','Unexpected model role selection');m=models.get(choice['modelId']);a=assessments.get(choice['modelId']);need(m and a and m['available']and m['toolCalling'],'Frozen selection is unavailable or unsupported')
  need(a['selectionClass']in policy['classes']and role in a['roles'],'Selected model differs from capability evidence')
  if c['controls']['effortOverride']:need(choice['effort']==a['effortByIntent'][policy['intent']]and choice['effort']in m['supportedEfforts'],'Selected model/effort differs from capability evidence')
  else:need(choice['effort']is None and choice.get('effortControl')=='inherited','Unsupported effort must remain inherited/unknown')
  expected=runtime_adapter.dispatch(c,m,choice['effort'])
  need(choice['dispatch']==expected,'Model launch request differs from resolved settings')
 need(r['roles']['inspector']==inherited(c),'Root model must remain inherited, not overridden')
 need(r['id']==fingerprint({'mode':r['mode'],'catalog':c,'assessments':load(ap),'roles':r['roles']}),'Frozen role resolution changed')
 for role,choice in r['roles'].items():
  if choice.get('status')=='selected':need(assessment_evidence(run,assessments[choice['modelId']],role,instant(r['resolvedAt']),c['schemaVersion'])==choice['basis'],'Model validation basis changed')

def request(plan,role,agent=None):
 r=plan.get('modelSelection')
 if plan.get('executionMode')=='sequential-fallback'and role!='inspector':
  root=(r or{}).get('roles',{}).get('inspector')or inherited({})
  return {'resolutionId':None,'role':role,**root,'status':'inherited-sequential','reason':'Runtime fallback uses the current conversation. Selected child model/effort and relative cost are not achieved.'}
 if role=='inspector':
  return {'resolutionId':r.get('id')if r else None,'role':role,**((r or{}).get('roles',{}).get('inspector')or{'status':'inherited-root','modelId':None,'effort':None,'dispatch':{},'runtimeConfirmed':False,'reason':'Root settings are controlled by the app'})}
 need(r and r.get('status')not in ['pending'],'Resolve runtime-backed model choices before starting research agents')
 choice=r.get('roles',{}).get(role,{});need(choice.get('status')=='selected','Selected role has no supported model profile: '+choice.get('reason','not configured'))
 if agent:need(agent not in {'root',r.get('rootAgentId')},'This role requires a fresh subagent; root settings cannot be overridden')
 return {'resolutionId':r['id'],'role':role,**choice}

def validate_job(run,plan,job):
 binding=job.get('modelRequest')
 # Jobs from an already-existing legacy plan remain transparently inherited.
 if not binding:
  need('modelSelection'not in plan or job['jobId']in plan.get('legacyModelJobIds',[]),'Research job is missing its pinned model request');return
 rid=binding.get('resolutionId');resolutions=all_resolutions(plan)
 if rid:
  need(rid in resolutions,'Unknown job model resolution');r=resolutions[rid];validate_resolution(run,r);expected={'resolutionId':rid,'role':job['role'],**r['roles'][job['role']]};need(binding==expected,'Job model request changed after selection')
 else:need((job['role']=='inspector'and binding['status']=='inherited-root')or(binding['status']=='inherited-sequential'and job.get('executionMode')=='sequential-fallback'),'Only root inspection or disclosed sequential fallback can inherit without a resolved profile')
 observed=job.get('runtimeReported')
 if observed:
  need(observed.get('source'),'Runtime model confirmation needs an actual source')
  for key in ['modelId','effort']:
   if observed.get(key)is not None and binding.get(key)is not None:need(observed[key]==binding[key],'Runtime reports different model/effort; disclose and resolve before treating this as the selected profile')

def distinct_agent(plan,job,previous):
 if not job.get('modelRequest'):return
 if job.get('executionMode')=='sequential-fallback':
  expected=job.get('executionRootAgentId')
  if expected:need(job['agent']==expected,'Sequential fallback must identify its actual root executor')
  return
 binding=job.get('modelRequest',{});r=all_resolutions(plan).get(binding.get('resolutionId'),{})
 if job['role']=='inspector':
  if r.get('rootAgentId'):need(job['agent']==r['rootAgentId'],'Inspector must identify the actual root agent')
  need(not any(j['agent']==job['agent']and j['role']!='inspector'and j.get('executionMode')=='agents'for j in previous),'Root inspector cannot be relabeled as a child researcher')
 else:
  need(not any(j['agent']==job['agent']for j in previous),'Fresh job requires a distinct actual agent context; resume the existing job instead of relabeling it')

def compatible(plan,job):
 expected=request(plan,job['role'],job['agent']);binding=job.get('modelRequest',{})
 need(not any(binding.get(k)!=expected.get(k)for k in ['modelId','effort','dispatch','status']),'Pinned model/effort changed; use a new context within this mode allowance instead of relabeling an existing agent')
 return expected

def action_binding(plan):
 return {'modelResolutionId':plan.get('modelSelection',{}).get('id'),'executionMode':plan['executionMode']}

def validate_action(plan,job,event):
 if not job.get('modelRequest'):return # Recorded before this policy existed.
 need('modelResolutionId'in event and event.get('executionMode')in ['agents','sequential-fallback'],'Reading/resume is missing model profile provenance')
 rid=event['modelResolutionId'];r=all_resolutions(plan).get(rid)if rid else None
 need(not rid or r is not None,'Unknown action model resolution')
 if r:need(r['mode']==event['mode'],'Reading mode differs from its model profile')
 active={**plan,'modelSelection':r,'executionMode':event['executionMode']}
 compatible(active,job)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True,type=Path);sub=p.add_subparsers(dest='action',required=True)
 s=sub.add_parser('resolve');s.add_argument('--catalog',type=Path);s.add_argument('--assessments',type=Path);s.add_argument('--authorization')
 s=sub.add_parser('launch-spec');s.add_argument('--role',required=True,choices=sorted(ROLES|{'inspector'}))
 sub.add_parser('show');a=p.parse_args()
 try:
  import research_mode
  plan=research_mode.current(a.run)
  if a.action=='resolve':
   old=plan.get('modelSelection',{})
   if old.get('id'):need(a.authorization,'Replacing a pinned selection requires an explicit availability/authorization reason')
   # Do not retroactively relabel existing contexts. Replacement choices affect new jobs only.
   new=resolve(a.run,plan['mode'],a.catalog,a.assessments)
   if old.get('id'):plan.setdefault('previousModelSelections',[]).append(old)
   if 'modelSelection'not in plan:plan['legacyModelJobIds']=[e['jobId']for e in research_mode.ledger(a.run)if e['kind']=='job'and not e.get('modelRequest')]
   plan['modelSelection']=new;plan['updatedAt']=research_mode.now();plan.setdefault('modelSelectionChanges',[]).append({'at':plan['updatedAt'],'reason':a.authorization or'Initial run selection','from':old.get('id'),'to':new.get('id')});save(Path(a.run)/'analysis/research-plan.json',plan);result=new
  elif a.action=='launch-spec':result=request(plan,a.role)
  else:result=plan.get('modelSelection',{'status':'pending'})
 except(ValueError,KeyError,TypeError,FileNotFoundError)as e:print(json.dumps({'error':str(e)}));return 1
 print(json.dumps(result,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
