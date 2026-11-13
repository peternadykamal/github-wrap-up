#!/usr/bin/env python3
"""Reproduce descriptive facts from collected records; never generate editorial insights."""
import argparse, calendar, collections, datetime as dt, hashlib, json, os, re, statistics
from pathlib import Path
from zoneinfo import ZoneInfo
UTC=dt.timezone.utc

def load(p):return json.loads(Path(p).read_text())
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True,mode=0o700);temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(v,ensure_ascii=False,indent=2));temp.chmod(0o600);temp.replace(p)
def instant(s):
 if not s:return None
 try:
  d=dt.datetime.fromisoformat(s.replace('Z','+00:00'));return d.replace(tzinfo=UTC)if d.tzinfo is None else d.astimezone(UTC)
 except(ValueError,TypeError):return None
def within(s,w):
 d=instant(s);return bool(d and instant(w['start'])<=d<instant(w['endExclusive']))
def rows(p):
 for n,line in enumerate(Path(p).read_text().splitlines(),1):
  if line.strip():
   try:yield json.loads(line)
   except json.JSONDecodeError as e:raise ValueError(f'{p}:{n}: invalid JSON')from e

def build(run):
 run=Path(run);m=load(run/'manifest.json');w=m['window'];zone=ZoneInfo(w['timezone']);start=instant(w['start']);end=instant(w['endExclusive'])
 if not start or not end or start>=end:raise ValueError('Invalid frozen interval')
 subjects=m['subjects'];ids=[s['id']for s in subjects]
 if 'team'in ids or len(ids)!=len(set(ids)):raise ValueError('Subject IDs must be unique; team is reserved')
 aliases={x.casefold():s['id']for s in subjects for x in [s['id'],s.get('login',s['id']),*s.get('aliases',{}).get('logins',[])]}
 def canonical(a):return aliases.get(str(a).casefold(),a)
 records={};conflicts=[]
 for repository in sorted(set(m['repos'])):
  file = run / 'repos' / repository.replace('/', '__') / 'records.jsonl'
  for r in rows(file):
   for k in ['id','kind','repo','occurredAt','data']:
    if k not in r:raise ValueError(f'{file}: missing {k}')
   if r['repo'] != repository:
    raise ValueError(f'{file}: record repository does not match the manifest')
   r['actor']=canonical(r.get('actor'));data=r['data'];data['author']=canonical(data.get('author',r['actor']));data['mergedBy']=canonical(data.get('mergedBy'))
   prior=records.get(r['id'])
   if prior and prior!=r:conflicts.append(r['id'])
   records[r['id']]=r
 # Repository membership and original IDs remain traceable even when SHAs repeat.
 commits={};source_index={};prs={};source_by_sha=collections.defaultdict(list)
 for r in records.values():
  d=r['data'];idx={k:r.get(k)for k in ['id','kind','repo','actor','occurredAt','url','title']};idx['data']={k:d.get(k)for k in ['sha','merge','detail','coauthors','number','prNumber','state','createdAt','mergedAt','closedAt','author','mergedBy','status','conclusion','environment','targetSha','headSha','mergeCommitSha','commits','statuses','authoredAt','committedAt','draft','publishedAt','tag','prerelease']if k in d};source_index[r['id']]=idx
  if r['kind']=='pull_request':prs[(r['repo'],d.get('number'))]=r
  if r['kind']!='commit':continue
  sha=d.get('sha');stamp=d.get('committedAt'if w.get('dateBasis')=='committed'else'authoredAt')or r['occurredAt']
  if not sha or not within(stamp,w):continue
  source_by_sha[sha].append(r['id'])
  c=commits.setdefault(sha,{'sha':sha,'actor':r['actor'],'date':stamp,'merge':bool(d.get('merge')),'repos':set(),'paths':set(),'sourceIds':[],'authors':set(),'coauthors':set()})
  c['repos'].add(r['repo']);c['paths'].update(d.get('paths')or[]);c['sourceIds'].append(r['id']);c['authors'].add(r['actor']);c['coauthors'].update(canonical(a)for a in d.get('coauthors',[]))
 for c in commits.values():
  known=c['authors']&set(ids)
  if len(known)>1:conflicts.append('conflicting-sha-author:'+c['sha']);c['actor']=None
  elif len(known)==1:c['actor']=next(iter(known))
 # Enumerate local calendar bins even when no records were observed. Coverage is separate.
 days=[];date=start.astimezone(zone).date();last=(end-dt.timedelta(microseconds=1)).astimezone(zone).date()
 while date<=last:days.append(date.isoformat());date+=dt.timedelta(days=1)
 month_keys=list(dict.fromkeys(d[:7]for d in days));week_keys=list(dict.fromkeys((dt.date.fromisoformat(d)-dt.timedelta(days=dt.date.fromisoformat(d).weekday())).isoformat()for d in days))
 activity={(pid,d):{'date':d,'personId':pid,'commits':0,'prs':0,'reviews':0}for pid in [*ids,'team']for d in days}
 totals={pid:{'commits':0,'coauthoredCommits':0,'integrations':0,'otherActivities':0,'prs':0,'reviews':0,'comments':0,'issues':0,'mergedAuthoredPRs':0,'repositories':0}for pid in [*ids,'team']};repo_sets=collections.defaultdict(set)
 months={pid:{k:{'month':k,'commits':0,'prs':0,'reviews':0,'comments':0,'issues':0,'coauthoredCommits':0,'integrations':0,'otherActivities':0,'mergedAuthoredPRs':0}for k in month_keys}for pid in [*ids,'team']}
 weeks={pid:{k:{'weekStart':k,'commits':0,'prs':0,'reviews':0,'comments':0,'issues':0,'coauthoredCommits':0,'integrations':0,'otherActivities':0,'mergedAuthoredPRs':0}for k in week_keys}for pid in [*ids,'team']}
 hours={p:[0]*24 for p in [*ids,'team']};weekdays={p:[0]*7 for p in [*ids,'team']};categories={p:collections.Counter()for p in [*ids,'team']};repo_counts={p:collections.Counter()for p in [*ids,'team']}
 patterns={'tests':r'(^|/)(__tests__|tests?)(/|\.)|\.(test|spec)\.[cm]?[jt]sx?$|Tests?\.cs$','documentation':r'(^|/)(docs?|runbooks?)/|\.md$','delivery':r'^\.github/workflows/|(^|/)(Dockerfile[^/]*|docker-compose[^/]*|[^/]+\.tf)$'}
 def add(pid,key,stamp,repos,include_team=True):
  if(pid not in ids and pid!='team')or not within(stamp,w):return
  local=instant(stamp).astimezone(zone);day=local.date().isoformat();week=(local.date()-dt.timedelta(days=local.weekday())).isoformat()
  for p in([pid,'team']if include_team and pid!='team'else[pid]):
   totals[p][key]+=1;months[p][day[:7]][key]+=1;weeks[p][week][key]+=1;repo_sets[p].update(repos)
   if key in activity[(p,day)]:activity[(p,day)][key]+=1
  return local
 for c in commits.values():
  if c['merge']:continue
  selected_coauthors=c['coauthors']&set(ids)
  for coauthor in selected_coauthors:
   add(coauthor,'coauthoredCommits',c['date'],c['repos'],False)
  if selected_coauthors:add('team','coauthoredCommits',c['date'],c['repos'],False)
  local=add(c['actor'],'commits',c['date'],c['repos'])
  if not local:continue
  for pid in [c['actor'],'team']:
   hours[pid][local.hour]+=1;weekdays[pid][local.weekday()]+=1;repo_counts[pid].update(c['repos'])
   for k,pat in patterns.items():
    if any(re.search(pat,p,re.I)for p in c['paths']):categories[pid][k]+=1
 for r in records.values():
  d=r['data'];kind=r['kind'];a=r['actor']
  if kind=='pull_request':
   add(d.get('author',a),'prs',d.get('createdAt')or r['occurredAt'],[r['repo']]);add(d.get('author',a),'mergedAuthoredPRs',d.get('mergedAt'),[r['repo']]);add(d.get('mergedBy'),'integrations',d.get('mergedAt'),[r['repo']])
  elif kind in ['timeline','workflow','release','deployment']:add(a,'otherActivities',r['occurredAt'],[r['repo']])
  elif kind in ['review','comment','issue']:add(a,{'review':'reviews','comment':'comments','issue':'issues'}[kind],r['occurredAt'],[r['repo']])
 # Interactions are recorded review edges, not an inferred social graph.
 interactions=collections.Counter();elapsed=collections.defaultdict(list)
 for r in records.values():
  if r['kind']=='review'and within(r['occurredAt'],w):
   pr=prs.get((r['repo'],r['data'].get('prNumber')));author=pr['data'].get('author',pr['actor'])if pr else None
   if r['actor']in ids and author and author!=r['actor']:interactions[(r['actor'],author,r['repo'])]+=1
 for pr in prs.values():
  d=pr['data'];a=d.get('author',pr['actor']);created=instant(d.get('createdAt')or pr['occurredAt']);merged=instant(d.get('mergedAt'))
  if a in ids and created and merged and within(d.get('mergedAt'),w)and merged>=created:elapsed[a].append((merged-created).total_seconds()/86400)
 limits=['Only recovered and accessible evidence is represented. Empty bins mean no observed records, not verified inactivity.','Commit timestamps are editable; counts and elapsed intervals do not measure hours, productivity, quality or business impact.','File categories overlap and describe changed paths, not test execution or coverage. Primary-authored commits and coauthoredCommits are separate potentially overlapping measures; never add them as a unique total.','PR open-to-merge intervals are elapsed calendar days; ready-for-review time is not substituted.']
 if conflicts:limits.append(f'{len(conflicts)} conflicting record/author observations require inspection; conflicting selected SHA authors are excluded from personal/team totals.')
 people={}
 for pid in [*ids,'team']:
  totals[pid]['repositories']=len(repo_sets[pid]);counts=[x['commits']for x in months[pid].values()];peak=max(counts,default=0)
  value={'totals':totals[pid],'monthly':list(months[pid].values()),'weekly':list(weeks[pid].values()),'commitHours':hours[pid],'commitWeekdays':weekdays[pid],'changedPathCategories':dict(categories[pid]),'repositoryCommitMemberships':dict(repo_counts[pid]),'peakMonths':[x['month']for x in months[pid].values()if peak and x['commits']==peak],'peakMonthCommits':peak,'mergedPRElapsedCalendarDays':{'startBasis':'createdAt','sampleSize':len(elapsed[pid]),'median':statistics.median(elapsed[pid])if elapsed[pid]else None},'timeInterpretationAllowed':bool(w.get('timezoneConfirmed',False)),'observedRepositories':sorted(repo_sets[pid])}
  for x in value['monthly']:
   x['coverage']='unknown'if m.get('coverage',{}).get('complete')is not True else'collected';x['observation']='observed'if any(x[k]for k in ['commits','coauthoredCommits','prs','reviews','comments','issues','integrations','otherActivities','mergedAuthoredPRs'])else'no-observed-activity'
  people[pid]=value
 team_durations=[v for p in ids for v in elapsed[p]];people['team']['mergedPRElapsedCalendarDays'].update(sampleSize=len(team_durations),median=statistics.median(team_durations)if team_durations else None)
 result={'schemaVersion':1,'sourceManifestSha256':digest(run/'manifest.json'),'window':w,'subjects':[{'id':s['id'],'login':s.get('login',s['id'])}for s in subjects],'totals':totals,'people':{p:people[p]for p in ids},'team':people['team'],'activity':list(activity.values()),'sourceIndex':source_index,'reviewInteractions':[{'reviewer':a,'author':b,'repo':r,'submittedReviews':n}for(a,b,r),n in interactions.items()],'coverage':m.get('coverage',{}),'limitations':limits,'conflicts':conflicts}
 save(run/'analysis/facts.json',result)
 for pid in ids:
  save(run/f'analysis/people/{pid}/monthly-facts.json',people[pid]['monthly'])
 save(run/'analysis/coverage.json',{'collection':m.get('coverage',{}),'limitations':limits,'conflicts':conflicts})
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True,type=Path);args=p.parse_args();r=build(args.run);print(json.dumps({'subjects':len(r['subjects']),'teamTotals':r['totals']['team'],'sources':len(r['sourceIndex']),'conflicts':len(r['conflicts'])}))
if __name__=='__main__':main()
