#!/usr/bin/env python3
"""Check researched presentation provenance and bind inspector approval to exact bytes."""
import argparse, datetime as dt, decimal, hashlib, json, math, re, sys
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from build_facts import load,digest,save,instant,rows
from research_mode import validate_mode

class Invalid(ValueError):pass

def check(condition,message):
 if not condition:raise Invalid(message)
def getpath(value,path):
 for k in path.split('.'):
  if isinstance(value,list):value=value[int(k)]
  else:value=value[k]
 return value
def equivalent(a,b):
 try:return decimal.Decimal(str(a).replace(',','').strip())==decimal.Decimal(str(b).replace(',','').strip())
 except decimal.InvalidOperation:return str(a)==str(b)
def shape(data):
 def text(v):return isinstance(v,str)
 def strings(v):return isinstance(v,list)and all(text(x)for x in v)
 check(isinstance(data,dict),'Presentation must be an object')
 for k in ['people','timeline','stories','activity']:check(isinstance(data.get(k),list),'Presentation '+k+' must be an array')
 meta=data.get('meta',{});check(all(text(meta.get(k))for k in ['title','start','endExclusive','timezone','snapshotAt']),'Missing presentation metadata strings');check(strings(meta.get('coverageNotes')),'meta.coverageNotes must be a string array')
 cov=data.get('coverage',{});check(text(cov.get('summary'))and strings(cov.get('limitations')),'Invalid coverage display contract')
 for p in data['people']:check(all(text(p.get(k))and p[k]for k in ['id','name','color','headline']),'Incomplete person display fields')
 check(len(data['people'])==len({p['id']for p in data['people']}),'Duplicate display person')
 for st in data['stories']:
  check(all(text(st.get(k))and st[k]for k in ['personId','title','thesis','theme'])and isinstance(st.get('chapters'),list),'Incomplete story display fields')
  for c in st['chapters']:
   check(all(text(c.get(k))for k in ['id','title','kicker','body','layout']),'Incomplete chapter display strings')
   check(all(isinstance(c.get(k),list)for k in ['metrics','beats','evidence']),'Chapter metrics/beats/evidence must be arrays')
   for m in c['metrics']:check(all(text(m.get(k))for k in ['value','label','basis']),'Metric value/label/basis must be strings')
   for b in c['beats']:check(text(b.get('title'))and text(b.get('body')),'Beat title/body are required')
 for t in data['timeline']:check(all(text(t.get(k))for k in ['id','title','summary','date','repo','stage'])and strings(t.get('people')),'Incomplete timeline display fields')
 def walk(v):
  if isinstance(v,float):check(math.isfinite(v),'Nonfinite JSON numbers are not supported')
  elif isinstance(v,dict):
   for x in v.values():walk(x)
  elif isinstance(v,list):
   for x in v:walk(x)
 walk(data)

def candidates(run):
 found={}
 for file in sorted((run/'analysis/people').glob('*/insight-candidates.json'))+sorted((run/'analysis/team').glob('insight-candidates.json')):
  data=load(file);data=data.get('candidates',[])if isinstance(data,dict)else data
  for c in data:
   check(c.get('id')not in found,'Duplicate candidate ID');found[c['id']]=c
 return found

def inspection_digest(run):
    """Fingerprint the exact files consulted by the inspection gate."""
    log = run / 'analysis/inspection/read-log.jsonl'
    paths = {
        log,
        *(run / 'analysis/people').glob('*/insight-candidates.json'),
        *(run / 'analysis/team').glob('insight-candidates.json'),
        *(run / 'analysis/calculations').glob('*.json'),
    }
    if log.is_file():
        for entry in rows(log):
            location = entry.get('location', '')
            if location and not location.startswith('https://'):
                paths.add(run / location)
    items = []
    for path in sorted(paths):
        check(path.resolve().is_relative_to(run), 'Inspection input is outside the run')
        items.append((str(path.relative_to(run)), digest(path) if path.is_file() else None))
    return hashlib.sha256(json.dumps(items, separators=(',', ':')).encode()).hexdigest()


def source_date_matches(value, source_date, timezone):
    event = instant(source_date)
    if not event:
        return False
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return value == event.astimezone(ZoneInfo(timezone)).date().isoformat()
    return instant(value) == event


def artifact_hashes(record):
    data = record['data']
    values = []
    if record['kind'] == 'commit':
        values = [data.get('sha')]
    elif record['kind'] == 'pull_request':
        values = [data.get('mergeCommitSha'), data.get('headSha'), *data.get('commits', [])]
    return {value.lower() for value in values if isinstance(value, str) and re.fullmatch(r'[0-9a-fA-F]{40,64}', value)}


def release_dates(record):
    data = record['data']
    if record['kind'] == 'release' and data.get('draft') is False:
        return [data.get('publishedAt')]
    if record['kind'] == 'deployment':
        return [status.get('createdAt') for status in data.get('statuses', []) if status.get('state') == 'success']
    return []


def validate_beats(chapter):
    evidence = chapter['evidence']
    for beat in chapter['beats']:
        if 'sourceId' in beat:
            check(any(item['id'] == beat['sourceId'] for item in evidence), 'Beat source must be cited by its chapter')
        if 'url' in beat:
            check(any(item['url'] == beat['url'] and beat.get('sourceId', item['id']) == item['id'] for item in evidence),
                  'Beat URL must match canonical chapter evidence')


def validate(run,presentation,seal=False):
 run=Path(run).resolve();presentation=Path(presentation).resolve();manifest=load(run/'manifest.json');facts=load(run/'analysis/facts.json');data=load(presentation);dp=run/'analysis/inspection/decisions.json';judge=load(dp);shape(data)
 collection_status = 'complete' if facts.get('coverage', {}).get('complete') is True else 'partial'
 check(data['coverage'].get('status', collection_status) == collection_status, 'Coverage status disagrees with collected facts')
 check(facts['sourceManifestSha256']==digest(run/'manifest.json'),'Facts are stale: rebuild after manifest changes')
 check(judge.get('factCheck')=='passed'and judge.get('editorialCheck')=='passed','Both factual and editorial inspector reviews must pass')
 check(judge.get('reviewedBy')and judge.get('notes'),'Inspector identity and substantive notes are required')
 check(judge.get('status')in ['reviewed','approved'],'Inspector must explicitly mark content reviewed')
 hashes={'presentationSha256':digest(presentation),'factsSha256':digest(run/'analysis/facts.json'),'sourceManifestSha256':digest(run/'manifest.json')}
 mode_path=run/'analysis/research-plan.json';ledger_path=run/'analysis/research-ledger.jsonl'
 if mode_path.exists():
  check(ledger_path.is_file(),'Research usage ledger is missing');hashes.update(researchPlanSha256=digest(mode_path),researchLedgerSha256=digest(ledger_path))
 else:check(judge.get('status')=='approved','New inspections require a research mode plan; Medium is the default')
 hashes['inspectionInputsSha256'] = inspection_digest(run)
 if judge.get('status')=='approved':
  if 'inspectionInputsSha256' not in judge:
   check(not seal, 'Legacy approval needs renewed inspection before resealing')
   hashes.pop('inspectionInputsSha256')
  check(all(judge.get(k)==v for k,v in hashes.items()),'Approved material changed; renew inspection before resealing')
 source=facts['sourceIndex'];people={s['id']for s in manifest['subjects']};allowed=people|{'team'};host=manifest.get('host','github.com')
 def refs(refs):
  check(isinstance(refs,list)and refs,'Evidence must contain at least one real source')
  result=set()
  for e in refs:
   check(isinstance(e,dict)and isinstance(e.get('label'),str)and e['label'],'Evidence needs a display label');sid=e.get('id');check(sid in source,f'Unknown source ID: {sid}');url=e.get('url');u=urlsplit(url or'');check(u.scheme=='https'and u.netloc==host and not u.username and '\\'not in(url or''),'Unsafe or wrong-host source URL');check(url==source[sid]['url'],f'Source URL mismatch: {sid}');result.add(sid)
  return result
 log=[]
 lp=run/'analysis/inspection/read-log.jsonl'
 if lp.exists():log=list(rows(lp))
 readings={}
 for r in log:
  sid=r.get('sourceId');check(sid in source,'Read log references an unknown source');check(r.get('level')in ['metadata','diff','discussion','historical_source'],'Unknown evidence inspection level');check(r.get('agent')and r.get('notes')and instant(r.get('inspectedAt')),'Incomplete actual reading log')
  location=r.get('location','')
  if location.startswith('https://'):check(urlsplit(location).netloc==host,'Reading location has wrong host')
  else:
   resolved=(run/location).resolve();check(resolved.is_relative_to(run)and resolved.is_file(),'Reading location must be an existing file inside this run')
   if r['level']=='diff' and source[sid]['kind']=='commit' and source[sid]['data'].get('detail'):
    check(resolved==(run/source[sid]['data']['detail']).resolve(),'Commit diff read log points to a different source file')
  readings.setdefault(sid,set()).add(r['level'])
 try:mode_usage=validate_mode(run,judge,log)if mode_path.exists()else None
 except ValueError as e:raise Invalid(str(e))from e
 allc=candidates(run);accepted=set()
 for dec in judge.get('decisions',[]):
  cid=dec.get('candidateId');check(cid in allc,f'Unknown inspector candidate: {cid}');check(dec.get('decision')in ['accept','rewrite','combine','reject','needs-evidence'],'Unknown editorial decision');check(dec.get('reason'),'Decision requires a reason')
  if dec['decision']=='accept':accepted.add(cid)
 check(len(judge.get('decisions',[]))==len({d['candidateId']for d in judge.get('decisions',[])}),'Conflicting duplicate inspector decisions')
 def involved(sid):
  r=source[sid];d=r['data'];return set(filter(None,[r.get('actor'),d.get('author'),d.get('mergedBy'),*d.get('coauthors',[])]))
 for cid in accepted:
  c=allc[cid]
  for key in ['observation','interpretation','whyItMatters','coverage'] :check(c.get(key),f'{cid}: missing {key}')
  check(set(c.get('subjectIds',[]))and set(c['subjectIds'])<=allowed,f'{cid}: invalid subjects');check(c.get('confidence')in ['high','medium','low'],f'{cid}: missing confidence');check('alternatives'in c and isinstance(c['alternatives'],list),f'{cid}: alternative explanations not considered')
  ev=refs(c.get('evidence'));check(all(pid=='team'or any(pid in involved(i)for i in ev)for pid in c['subjectIds']),f'{cid}: evidence does not establish this subject’s involvement');inspected=set(c.get('inspectionIds',[]));check(inspected and inspected<=ev and inspected<=set(readings),f'{cid}: cited evidence has not actually been inspected')
  period=c.get('period',{});check(instant(period.get('start'))and instant(period.get('endExclusive')),f'{cid}: invalid period');check(instant(manifest['window']['start'])<=instant(period['start'])<instant(period['endExclusive'])<=instant(manifest['window']['endExclusive']),f'{cid}: period outside reporting scope')
 calculations={}
 for p in (run/'analysis/calculations').glob('*.json'):
  c=load(p);check(c.get('id')not in calculations,'Duplicate calculation ID');check(c.get('method')and c.get('unit')and c.get('inputs')and'result'in c,'Incomplete calculation');check(set(c['inputs'])<=set(source),'Unknown calculation inputs');calculations[c['id']]=c
 def metric(m):
  check(m.get('label')and m.get('basis'),'Displayed metrics require labels and counting rules');prov=m.get('provenance',{});check(bool(prov.get('factPath'))!=bool(prov.get('calculationId')),'Metric needs exactly one provenance reference')
  if prov.get('factPath'):
   try:actual=getpath(facts,prov['factPath'])
   except(KeyError,ValueError,IndexError,TypeError):raise Invalid('Invalid metric factPath: '+prov['factPath'])
  else:
   cid=prov['calculationId'];check(cid in calculations,'Unknown calculation');check(cid in judge.get('verifiedCalculations',[]),'Custom calculation lacks inspector verification');actual=calculations[cid]['result']
  check(equivalent(m.get('value'),actual),'Metric value disagrees with provenance: '+m['label'])
 meta=data.get('meta',{});window=manifest['window']
 check(instant(meta.get('start'))==instant(window['start'])and instant(meta.get('endExclusive'))==instant(window['endExclusive']),'Presentation reporting interval differs from collection');check(meta.get('timezone')==window['timezone'],'Timezone differs from collection');check(instant(meta.get('snapshotAt'))==instant(manifest.get('snapshotAt')),'Snapshot differs from collection')
 check({p.get('id')for p in data.get('people',[])}==people,'Presentation subject set differs from research');check(meta.get('totals')==facts['totals'],'Presentation totals must copy facts.totals');check(data.get('activity')==facts['activity'],'Presentation activity must copy facts.activity, including deduplicated team rows');check(data.get('coverage',{}).get('summary')and data['coverage'].get('limitations'),'Presentation needs actual coverage and limitations')
 timeline=data.get('timeline',[]);seen=set()
 for t in timeline:
  check(t.get('id')and t['id']not in seen,'Duplicate or missing timeline ID');seen.add(t['id']);check(t.get('candidateId')in accepted,'Timeline uses an unaccepted candidate');check(t.get('title')and t.get('summary'),'Timeline needs a substantive summary');check(t.get('people')and set(t['people'])<=people,'Timeline contains unknown people');check(t.get('contributionRole')in ['author','coauthor','pr-author','issue-author','reviewer','discussion','integrator','mixed'],'Timeline contribution role is required');ev=refs(t.get('evidence'));check(t.get('stage')in ['implemented','design','merged','released','unknown'],'Invalid development stage');check(instant(t['date']), 'Invalid timeline date')
  check(ev<=set(e['id']for e in allc[t['candidateId']]['evidence']),'Timeline support differs from accepted candidate')
  role=t['contributionRole']
  local_sources = {i for i in ev if source[i]['repo'] == t['repo']}
  check(local_sources, 'Timeline repository does not match its evidence')
  def supports(i, pid):
    r=source[i];d=r['data']
    if role=='author':return r['kind']=='commit'and r['actor']==pid
    if role=='pr-author':return r['kind']=='pull_request'and d.get('author',r['actor'])==pid
    if role=='issue-author':return r['kind']=='issue'and r['actor']==pid
    if role=='coauthor':return r['kind']=='commit'and pid in d.get('coauthors',[])
    if role=='reviewer':return r['kind']=='review'and r['actor']==pid
    if role=='discussion':return r['kind']in ['comment','issue','timeline']and r['actor']==pid
    if role=='integrator':return r['kind']=='pull_request'and d.get('mergedBy')==pid
    return pid in involved(i)
  for pid in t['people']:
   check(any(supports(i, pid) for i in local_sources), 'Timeline evidence does not support the credited person and contribution role')
  credited_sources = {i for i in local_sources if any(supports(i, pid) for pid in t['people'])}
  artifacts = set().union(*(artifact_hashes(source[i]) for i in credited_sources))
  stage = t['stage']
  if stage in ['implemented','design']:
   check(any(readings.get(i,set())&{'diff','historical_source'} for i in credited_sources),
         'Substantive implementation/design claim lacks source inspection')
  def matches(event):
   stamp = instant(event)
   return bool(stamp and instant(window['start']) <= stamp < instant(window['endExclusive'])
               and source_date_matches(t['date'], event, window['timezone']))
  if stage == 'merged':
   check(any(source[i]['kind'] == 'pull_request'
             and (i in credited_sources or artifact_hashes(source[i]) & artifacts)
             and matches(source[i]['data'].get('mergedAt')) for i in local_sources),
         'Merged stage lacks a matching in-window PR merge record and date')
  elif stage == 'released':
   linked_release = any(
       isinstance(source[i]['data'].get('targetSha'), str)
       and source[i]['data']['targetSha'].lower() in artifacts
       and any(matches(event) for event in release_dates(source[i]))
       for i in local_sources
   )
   check(linked_release, 'Released stage lacks matching published non-draft release/deployment evidence for the credited artifact and date')
  else:
   event_key = 'mergedAt' if role == 'integrator' else None
   check(any(matches(source[i]['data'].get(event_key) if event_key else source[i]['occurredAt']) for i in credited_sources),
         'Timeline date does not match a cited event in this repository')
 stories=data.get('stories',[]);check({s.get('personId')for s in stories}==allowed,'Need a distinct story for every person and the team');check(len(stories)==len(allowed),'Duplicate story subject')
 chapter_ids=set()
 for story in stories:
  check(story.get('title')and story.get('thesis')and story.get('chapters'),'Every story requires an editorial arc and chapters')
  available_totals=facts['totals'][story['personId']]
  empty=not any(available_totals.get(k,0)for k in ['commits','coauthoredCommits','prs','reviews','comments','issues','integrations','otherActivities','mergedAuthoredPRs'])
  availability=story.get('availability')
  if availability:check(empty and availability in ['no-observed-activity','unavailable'],'Coverage-only story is not supported by observed facts')
  for ch in story['chapters']:
   validate_beats(ch)
   if availability:
    check(ch.get('id')and ch['id']not in chapter_ids,'Duplicate coverage chapter ID');chapter_ids.add(ch['id']);check(ch.get('title')and ch.get('body')and not ch.get('evidence')and not ch.get('insightIds'),'Coverage-only chapters must state availability without fabricated insight/source links')
    for m in ch.get('metrics',[]):metric(m)
    continue
   check(ch.get('id')and ch['id']not in chapter_ids,'Duplicate/missing chapter ID');chapter_ids.add(ch['id']);check(ch.get('layout')in ['cover','journey','contrast','map','ledger','spotlight','finale'],'Unsupported chapter layout');check(ch.get('title')and ch.get('body'),'Chapter content is incomplete');cids=set(ch.get('insightIds',[]));check(cids and cids<=accepted,'Chapter lacks accepted insight support');ev=refs(ch.get('evidence'));check(ev<=set(e['id']for cid in cids for e in allc[cid]['evidence']),'Chapter cites support outside accepted candidates')
   for cid in cids:check(story['personId']=='team'or story['personId']in allc[cid]['subjectIds'],'Personal story reuses another person’s insight')
   for m in ch.get('metrics',[]):metric(m)
 # Check every exported string, including optional excerpts. Raw research remains private.
 text=json.dumps(data,ensure_ascii=False)
 check(not re.search(r'[\w.+%\-]+@[\w.\-]+\.[A-Za-z]{2,}',text),'Private/email-like strings remain in presentation')
 check(not re.search(r'(gh[pousr]_[A-Za-z0-9_]{12,}|github_pat_[A-Za-z0-9_]+|AIza[A-Za-z0-9_-]{25,}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|sk-[A-Za-z0-9_-]{20,})',text),'Recognizable credentials remain in presentation')
 check(not re.search(r'(?i)(?:password|client.?secret|api.?key|access.?token)\s*[\\"\x27]*\s*[:=]\s*[\\"\x27]+[A-Za-z0-9_+/=-]{8,}',text),'Credential-like assignment remains in presentation')
 if seal:
  if 'status' not in data['coverage']:
   data['coverage']['status'] = collection_status
   save(presentation, data)
   hashes['presentationSha256'] = digest(presentation)
  judge.update(researchMode=mode_usage['mode']if mode_usage else 'legacy-unmetered',researchUsage=mode_usage)
  judge.update(status='approved',**hashes,approvedAt=dt.datetime.now(dt.timezone.utc).isoformat());save(dp,judge)
 return {'passed':True,'sealed':seal,'acceptedInsights':len(accepted),'timelineEntries':len(timeline),'stories':len(stories),'chapters':len(chapter_ids),'researchMode':mode_usage['mode']if mode_usage else 'legacy-unmetered',**hashes}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True,type=Path);p.add_argument('--presentation',required=True,type=Path);p.add_argument('--seal',action='store_true');a=p.parse_args()
 try:r=validate(a.run,a.presentation,a.seal)
 except(Invalid,ValueError,KeyError,FileNotFoundError,TypeError)as e:print(json.dumps({'passed':False,'error':str(e)}));sys.exit(1)
 print(json.dumps(r,indent=2))
if __name__=='__main__':main()
