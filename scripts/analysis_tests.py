import argparse,copy,datetime as dt,json,tempfile,unittest
from pathlib import Path
import build_facts as facts
import validate_analysis as gate
import resolve_scope
import research_mode
import model_test_data

def fixture(root):
 root=Path(root);w={'start':'2026-01-01T00:00:00Z','endExclusive':'2026-02-01T00:00:00Z','timezone':'UTC','dateBasis':'authored','timezoneConfirmed':False}
 manifest={'schemaVersion':1,'snapshotAt':'2026-02-01T00:00:00Z','window':w,'subjects':[{'id':p,'login':p,'aliases':{'logins':['old-alice']if p=='alice'else[],'emails':[]}}for p in ['alice','bob']],'repos':['demo/one','demo/two'],'coverage':{'status':'complete','complete':True,'notes':[]}}
 facts.save(root/'manifest.json',manifest)
 def rec(repo,kind,key,actor,date,data):return {'id':f'github.com/{repo}#{kind}:{key}','repo':repo,'kind':kind,'actor':actor,'occurredAt':date,'url':f'https://github.com/{repo}/'+('commit/'+key if kind=='commit'else'pull/2'+('#pullrequestreview-'+key if kind=='review'else'')),'title':'A specific change','body':'Fixture source','data':data}
 a={'sha':'a'*40,'merge':False,'authoredAt':'2026-01-12T10:00:00Z','committedAt':'2027-03-01T10:00:00Z','paths':['src/service.cs','tests/service.Tests.cs','docs/decisions.md'],'detail':'repos/demo__one/changes/'+('a'*40)+'.json'}
 first=rec('demo/one','commit','a'*40,'old-alice',a['authoredAt'],a)
 mirrored=rec('demo/two','commit','a'*40,'alice',a['authoredAt'],a.copy())
 b=rec('demo/one','commit','b'*40,'bob','2026-01-14T08:00:00Z',{'sha':'b'*40,'merge':False,'authoredAt':'2026-01-14T08:00:00Z','committedAt':'2026-01-14T08:00:00Z','paths':['src/mobile.dart'],'detail':'repos/demo__one/changes/'+('b'*40)+'.json'})
 merge=rec('demo/one','commit','c'*40,'alice','2026-01-15T08:00:00Z',{'sha':'c'*40,'merge':True,'authoredAt':'2026-01-15T08:00:00Z','committedAt':'2026-01-15T08:00:00Z','paths':[]})
 pr=rec('demo/one','pull_request','2','bob','2025-12-20T09:00:00Z',{'number':2,'author':'bob','createdAt':'2025-12-20T09:00:00Z','mergedAt':'2026-01-23T11:00:00Z','mergedBy':'alice','state':'MERGED'})
 review=rec('demo/one','review','3','alice','2026-01-13T07:00:00Z',{'prNumber':2,'state':'APPROVED'})
 for repo,rs in [('demo__one',[first,b,merge,pr,review]),('demo__two',[mirrored])]:
  p=root/'repos'/repo/'records.jsonl';p.parent.mkdir(parents=True);p.write_text(''.join(json.dumps(r)+'\n'for r in rs))
 facts.save(root/a['detail'],{'patches':[{'path':'src/service.cs','patch':'+ corrected boundary'}]});facts.save(root/b['data']['detail'],{'patches':[{'path':'src/mobile.dart','patch':'+ preserve patient context'}]})
 f=facts.build(root);model_test_data.write(root);return manifest,f,first,b,review

def reviewed(root):
 m,f,a,b,rv=fixture(root);catalog=facts.load(root/'analysis/runtime-models.json');catalog['parent']['agentId']='fixture-reviewer';facts.save(root/'analysis/runtime-models.json',catalog);research_mode.initialize(root);research_mode.job(root,'team','inspector','inspector',agent='fixture-reviewer');e=lambda r:{'id':r['id'],'url':r['url'],'label':r['title']};cands=[];logs=[]
 for pid,r in [('alice',a),('bob',b),('team',a)]:
  if pid!='team':research_mode.job(root,pid,pid+'-research','researcher',agent=pid+'-agent')
  delivered=research_mode.packet(root,pid,[r['id']],pid+'-initial',level='diff')
  cands.append({'id':pid+'-insight','subjectIds':[pid],'observation':'A concrete source change','interpretation':'An evidence-backed connection','whyItMatters':'A specific boundary in this work','period':{'start':m['window']['start'],'endExclusive':m['window']['endExclusive']},'evidence':[e(r)],'inspectionIds':[r['id']],'metricRefs':[],'alternatives':[],'coverage':'Fixture recovered source','confidence':'high'})
  logs.append({'budgetEntryId':delivered['budgetEntryId'],'sourceId':r['id'],'level':'diff','location':r['data']['detail'],'agent':pid+'-agent'if pid!='team'else'fixture-reviewer','notes':'Read fixture patch showing corrected boundary','inspectedAt':m['snapshotAt']})
  facts.save(root/('analysis/team/insight-candidates.json'if pid=='team'else f'analysis/people/{pid}/insight-candidates.json'),[cands[-1]])
 for jid in ['alice-research','bob-research','inspector']:research_mode.finish(root,jid,'Fixture inspection completed')
 lp=root/'analysis/inspection/read-log.jsonl';lp.parent.mkdir(parents=True,exist_ok=True);lp.write_text(''.join(json.dumps(x)+'\n'for x in logs))
 data={'meta':{'title':'A fixture year','coverageNotes':[],'start':m['window']['start'],'endExclusive':m['window']['endExclusive'],'timezone':'UTC','snapshotAt':m['snapshotAt'],'totals':f['totals']},'people':[{'id':p,'name':p.title(),'color':'#d4ed68','headline':'A distinctive trail'}for p in ['alice','bob']],'timeline':[{'id':'one','candidateId':'alice-insight','contributionRole':'author','title':'A corrected boundary','summary':'The source change corrects the boundary.','date':a['occurredAt'],'people':['alice'],'repo':a['repo'],'evidence':[e(a)],'stage':'implemented'}],'stories':[{'personId':pid,'title':pid+' story','thesis':'A specific connection','theme':'ensemble','chapters':[{'id':pid+'-cover','insightIds':[pid+'-insight'],'layout':'cover','kicker':'FIXTURE RESEARCH','title':pid+' specific chapter','body':'Substantive fixture content','metrics':[{'value':str(f['totals'][pid]['commits']),'label':'Distinct nonmerge changes','basis':'Unique authored SHAs within the frozen window','provenance':{'factPath':f'totals.{pid}.commits'}}],'beats':[],'evidence':c['evidence']}]}for pid,c in zip(['alice','bob','team'],cands)],'activity':f['activity'],'coverage':{'summary':'Offline fixture','limitations':['No real GitHub work represented']}}
 pres=root/'analysis/presentation.json';facts.save(pres,data);facts.save(root/'analysis/inspection/decisions.json',{'status':'reviewed','reviewPasses':[{'type':t,'status':'passed','reviewer':'fixture-reviewer','notes':'Fixture review complete'}for t in ['factual','editorial']],'factCheck':'passed','editorialCheck':'passed','reviewedBy':'fixture-reviewer','notes':'Fixture calculations and cited content inspected','decisions':[{'candidateId':c['id'],'decision':'accept','reason':'Specific fixture evidence'}for c in cands]});return pres,data

class FactsTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def test_global_dedup_alias_and_rebased_dates(self):
  _,f,_,_,_=fixture(self.root);self.assertEqual(f['totals']['alice']['commits'],1);self.assertEqual(f['totals']['team']['commits'],2);self.assertEqual(f['people']['alice']['repositoryCommitMemberships'],{'demo/one':1,'demo/two':1});self.assertEqual(f['people']['alice']['changedPathCategories']['tests'],1);self.assertFalse(f['people']['alice']['timeInterpretationAllowed'])
 def test_old_pr_current_review_and_merge(self):
  _,f,_,_,_=fixture(self.root);self.assertEqual(f['totals']['team']['prs'],0);self.assertEqual(f['totals']['bob']['mergedAuthoredPRs'],1);self.assertEqual(f['totals']['alice']['mergedAuthoredPRs'],0);self.assertEqual(f['totals']['alice']['reviews'],1);self.assertEqual(f['totals']['alice']['integrations'],1);self.assertEqual(f['reviewInteractions'][0]['author'],'bob')
 def test_manifest_excludes_stale_repository_files(self):
  manifest, _, _, _, _ = fixture(self.root)
  manifest['repos'] = ['demo/one']
  facts.save(self.root / 'manifest.json', manifest)
  result = facts.build(self.root)
  self.assertEqual({record['repo'] for record in result['sourceIndex'].values()}, {'demo/one'})
 def test_committed_basis(self):
  m,*_=fixture(self.root);m['window']['dateBasis']='committed';facts.save(self.root/'manifest.json',m);f=facts.build(self.root);self.assertEqual(f['totals']['alice']['commits'],0);self.assertEqual(f['totals']['team']['commits'],1)
 def test_conflicting_sha_authors(self):
  fixture(self.root);p=self.root/'repos/demo__two/records.jsonl';r=json.loads(p.read_text());r['actor']='bob';p.write_text(json.dumps(r)+'\n');f=facts.build(self.root);self.assertEqual(f['totals']['team']['commits'],1);self.assertTrue(f['conflicts'])
 def test_integration_only_is_observed(self):
  fixture(self.root);p=self.root/'repos/demo__one/records.jsonl';pr=next(r for r in facts.rows(p)if r['kind']=='pull_request');pr['data'].update(author='alice',mergedBy='bob');pr['actor']='alice';p.write_text(json.dumps(pr)+'\n');(self.root/'repos/demo__two/records.jsonl').write_text('');f=facts.build(self.root);self.assertEqual(f['totals']['bob']['integrations'],1);self.assertEqual(f['totals']['bob']['repositories'],1);self.assertEqual(f['people']['bob']['monthly'][0]['observation'],'observed')
 def test_coauthor_only_deduplicated(self):
  _,_,a,_,_=fixture(self.root)
  for repo in ['demo__one','demo__two']:
   r=copy.deepcopy(a);r.update(actor=None,repo=repo.replace('__','/'),id=repo+'#commit:a');r['data']['coauthors']=['alice','bob'];(self.root/'repos'/repo/'records.jsonl').write_text(json.dumps(r)+'\n')
  f=facts.build(self.root);self.assertEqual(f['totals']['team']['commits'],0);self.assertEqual(f['totals']['team']['coauthoredCommits'],1);self.assertEqual(f['people']['bob']['monthly'][0]['coauthoredCommits'],1);self.assertIn('bob',next(iter(f['sourceIndex'].values()))['data']['coauthors'])
 def test_calendar_timezone(self):
  m,*_=fixture(self.root);m['window']['timezone']='Africa/Cairo';facts.save(self.root/'manifest.json',m);f=facts.build(self.root);self.assertEqual(f['people']['alice']['commitHours'][12],1)

class GateTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.pres,self.data=reviewed(self.root)
 def tearDown(self):self.temp.cleanup()
 def mutate(self):facts.save(self.pres,self.data)
 def test_seal_and_stale_approval(self):
  self.assertTrue(gate.validate(self.root,self.pres,True)['sealed']);self.data['stories'][0]['title']='Changed after review';self.mutate()
  with self.assertRaisesRegex(gate.Invalid,'changed'):gate.validate(self.root,self.pres,True)
 def test_total_mismatch(self):
  self.data['meta']['totals']['team']['commits']=99;self.mutate()
  with self.assertRaisesRegex(gate.Invalid,'totals'):gate.validate(self.root,self.pres)
 def test_metric_mismatch(self):
  self.data['stories'][0]['chapters'][0]['metrics'][0]['value']='999';self.mutate()
  with self.assertRaisesRegex(gate.Invalid,'Metric value'):gate.validate(self.root,self.pres)
 def test_reading_required(self):
  (self.root/'analysis/inspection/read-log.jsonl').write_text('')
  with self.assertRaisesRegex(gate.Invalid,'inspected'):gate.validate(self.root,self.pres)
 def test_wrong_person_credit_rejected(self):
  self.data['timeline'][0]['people']=['bob'];self.mutate()
  with self.assertRaisesRegex(gate.Invalid,'credited person'):gate.validate(self.root,self.pres)
 def test_missing_ui_fields_rejected(self):
  del self.data['meta']['coverageNotes'];self.mutate()
  with self.assertRaisesRegex(gate.Invalid,'coverageNotes'):gate.validate(self.root,self.pres)
 def test_wrong_diff_file_rejected(self):
  lp=self.root/'analysis/inspection/read-log.jsonl';rs=list(facts.rows(lp));rs[1]['location']=rs[0]['location'];lp.write_text(''.join(json.dumps(x)+'\n'for x in rs))
  with self.assertRaisesRegex(gate.Invalid,'different source'):gate.validate(self.root,self.pres)
 def test_private_email_rejected(self):
  self.data['stories'][0]['thesis']='Contact person@example.test';self.mutate()
  with self.assertRaisesRegex(gate.Invalid,'email'):gate.validate(self.root,self.pres)
 def test_draft_release_rejected(self):
  records=self.root/'repos/demo__one/records.jsonl';release={'id':'github.com/demo/one#release:9','repo':'demo/one','kind':'release','actor':'alice','occurredAt':'2026-01-20T10:00:00Z','url':'https://github.com/demo/one/releases/tag/v1','title':'Draft release','body':'Fixture','data':{'draft':True,'publishedAt':None,'tag':'v1'}}
  with records.open('a')as f:f.write(json.dumps(release)+'\n')
  f=facts.build(self.root);plan=facts.load(self.root/'analysis/research-plan.json');plan['factsSha256']=facts.digest(self.root/'analysis/facts.json');facts.save(self.root/'analysis/research-plan.json',plan);self.data['meta']['totals']=f['totals'];ev={'id':release['id'],'url':release['url'],'label':'Draft release'};self.data['timeline'][0].update(stage='released',evidence=[*self.data['timeline'][0]['evidence'],ev]);cp=self.root/'analysis/people/alice/insight-candidates.json';cs=facts.load(cp);cs[0]['evidence'].append(ev);facts.save(cp,cs);self.mutate()
  with self.assertRaisesRegex(gate.Invalid,'non-draft'):gate.validate(self.root,self.pres)
 def test_fake_release_rejected(self):
  self.data['timeline'][0]['stage']='released';self.mutate()
  with self.assertRaisesRegex(gate.Invalid,'release'):gate.validate(self.root,self.pres)
 def test_wrong_evidence_url_rejected(self):
  self.data['stories'][0]['chapters'][0]['evidence'][0]['url']='https://github.com/demo/other/commit/'+('a'*40);self.mutate()
  with self.assertRaisesRegex(gate.Invalid,'mismatch'):gate.validate(self.root,self.pres)
 def test_milestone_date_and_repository_match_evidence(self):
  milestone = self.data['timeline'][0]
  original = copy.deepcopy(milestone)
  for field, value, error in [
      ('repo', 'demo/two', 'repository'),
      ('date', '2026-01-29T00:00:00Z', 'Timeline date'),
  ]:
   with self.subTest(field=field):
    milestone.update(original)
    milestone[field] = value
    self.mutate()
    with self.assertRaisesRegex(gate.Invalid, error):
     gate.validate(self.root, self.pres)

 def test_in_window_local_date_can_precede_start_in_utc(self):
  manifest_path = self.root / 'manifest.json'
  manifest = facts.load(manifest_path)
  manifest['window'].update(start='2026-01-12T09:00:00Z', timezone='Pacific/Auckland')
  facts.save(manifest_path, manifest)
  updated = facts.build(self.root)
  plan_path = self.root / 'analysis/research-plan.json'
  plan = facts.load(plan_path)
  plan.update(factsSha256=facts.digest(self.root / 'analysis/facts.json'), sourceManifestSha256=facts.digest(manifest_path))
  facts.save(plan_path, plan)
  self.data['meta'].update(start=manifest['window']['start'], timezone=manifest['window']['timezone'], totals=updated['totals'])
  self.data['activity'] = updated['activity']
  self.data['timeline'][0]['date'] = '2026-01-12'
  for path in self.root.glob('analysis/**/insight-candidates.json'):
   candidates = facts.load(path)
   candidates[0]['period']['start'] = manifest['window']['start']
   facts.save(path, candidates)
  self.mutate()
  self.assertTrue(gate.validate(self.root, self.pres)['passed'])

 def test_unbound_beat_url_is_rejected(self):
  chapter = self.data['stories'][0]['chapters'][0]
  chapter['beats'] = [{'title': 'Change', 'body': 'Source', 'url': 'https://example.com/unrelated'}]
  self.mutate()
  with self.assertRaisesRegex(gate.Invalid, 'Beat URL'):
   gate.validate(self.root, self.pres)
  chapter['beats'][0] = {'title': 'Change', 'body': 'Source', 'sourceId': chapter['evidence'][0]['id']}
  self.mutate()
  self.assertTrue(gate.validate(self.root, self.pres)['passed'])

 def test_seal_rechecks_required_inspection_files(self):
  from create_presentation import create
  gate.validate(self.root, self.pres, True)
  decisions = self.root / 'analysis/inspection/decisions.json'
  log = self.root / 'analysis/inspection/read-log.jsonl'
  log.unlink()
  with self.assertRaisesRegex(ValueError, 'Inspection inputs changed'):
   create(self.pres, decisions, self.root / 'app')

 def test_release_requires_the_credited_artifact_and_success_date(self):
  milestone = self.data['timeline'][0]
  release = {
      'id': 'github.com/demo/one#deployment:7', 'repo': 'demo/one', 'kind': 'deployment',
      'actor': 'alice', 'occurredAt': '2025-12-31T00:00:00Z',
      'title': 'Deploy', 'url': 'https://github.com/demo/one/deployments',
      'data': {'environment': 'staging', 'targetSha': 'b' * 40,
               'statuses': [{'state': 'success', 'createdAt': '2026-01-20T10:00:00Z'}]},
  }
  evidence = {key: release[key] for key in ['id', 'url']}
  evidence['label'] = release['title']
  milestone.update(stage='released', date='2026-01-20T10:00:00Z')
  milestone['evidence'].append(evidence)
  candidates_path = self.root / 'analysis/people/alice/insight-candidates.json'
  candidates = facts.load(candidates_path)
  candidates[0]['evidence'].append(evidence)
  facts.save(candidates_path, candidates)
  records_path = self.root / 'repos/demo__one/records.jsonl'
  records = list(facts.rows(records_path))
  for sha, date, accepted in [
      ('b' * 40, '2026-01-20T10:00:00Z', False),
      ('a' * 40, '2026-02-01T10:00:00Z', False),
      ('a' * 40, '2026-01-20T10:00:00Z', True),
  ]:
   with self.subTest(sha=sha, date=date):
    release['data']['targetSha'] = sha
    release['data']['statuses'][0]['createdAt'] = date
    records_path.write_text(''.join(json.dumps(record) + '\n' for record in [*records, release]))
    updated = facts.build(self.root)
    plan_path = self.root / 'analysis/research-plan.json'
    plan = facts.load(plan_path)
    plan['factsSha256'] = facts.digest(self.root / 'analysis/facts.json')
    facts.save(plan_path, plan)
    self.data['meta']['totals'] = updated['totals']
    self.data['activity'] = updated['activity']
    self.mutate()
    if accepted:
     self.assertTrue(gate.validate(self.root, self.pres)['passed'])
    else:
     with self.assertRaisesRegex(gate.Invalid, 'Released stage'):
      gate.validate(self.root, self.pres)

 def test_manifest_changed_requires_new_facts(self):
  m=facts.load(self.root/'manifest.json');m['coverage']['status']='partial';facts.save(self.root/'manifest.json',m)
  with self.assertRaisesRegex(gate.Invalid,'stale'):gate.validate(self.root,self.pres)

class ScopeTests(unittest.TestCase):
 def test_defaults_calendar_year_without_assuming_me(self):
  a=argparse.Namespace(timezone=None,year=None,start=None,end_exclusive=None,targets=['someone'],host='github.com',org=None,repo=None,date_basis='authored',weekend_days=[5,6]);lookup=lambda host,path,paginate=False:{'login':'someone','type':'User'};c=resolve_scope.make(a,lookup,dt.datetime(2026,11,8,tzinfo=dt.timezone.utc));self.assertEqual(c['window']['start'],'2026-01-01T00:00:00+00:00');self.assertEqual(c['subjects'][0]['id'],'someone');self.assertFalse(c['window']['timezoneConfirmed'])
 def test_profile_url_host(self):
  self.assertEqual(resolve_scope.target('https://github.com/someone/','github.com'),'someone')
  with self.assertRaises(ValueError):resolve_scope.target('https://other.test/someone','github.com')

class CoverageOnlyTests(unittest.TestCase):
 def test_empty_history_has_honest_coverage_story(self):
  with tempfile.TemporaryDirectory()as folder:
   root=Path(folder);m={'schemaVersion':1,'snapshotAt':'2026-02-01T00:00:00Z','window':{'start':'2026-01-01T00:00:00Z','endExclusive':'2026-02-01T00:00:00Z','timezone':'UTC'},'subjects':[{'id':'alice','login':'alice'}],'repos':[],'coverage':{'status':'partial','complete':False}}
   facts.save(root/'manifest.json',m);f=facts.build(root);research_mode.initialize(root)
   data={'meta':{'title':'Unavailable history','coverageNotes':['Repository permissions limited recovery'],'start':m['window']['start'],'endExclusive':m['window']['endExclusive'],'timezone':'UTC','snapshotAt':m['snapshotAt'],'totals':f['totals']},'people':[{'id':'alice','name':'Alice Example','color':'#d4ed68','headline':'No recoverable activity in this snapshot'}],'timeline':[],'activity':f['activity'],'coverage':{'summary':'No activity could be recovered','limitations':['This does not establish inactivity']},'stories':[{'personId':pid,'availability':'unavailable','title':'An incomplete record','thesis':'No conclusions from missing history','theme':'ensemble','chapters':[{'id':pid+'-availability','title':'The evidence is unavailable','kicker':'COVERAGE','body':'The accessible snapshot contains no recorded activity; this is not evidence of no work.','layout':'cover','metrics':[],'beats':[],'evidence':[],'insightIds':[]}]}for pid in ['alice','team']]}
   pres=root/'analysis/presentation.json';facts.save(pres,data);facts.save(root/'analysis/inspection/decisions.json',{'status':'reviewed','reviewPasses':[{'type':t,'status':'passed','reviewer':'fixture-reviewer','notes':'Fixture review complete'}for t in ['factual','editorial']],'factCheck':'passed','editorialCheck':'passed','reviewedBy':'fixture inspector','notes':'No fabricated story for inaccessible evidence','decisions':[]});self.assertTrue(gate.validate(root,pres,True)['passed'])

if __name__=='__main__':unittest.main()
