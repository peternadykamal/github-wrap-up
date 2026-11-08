import copy,json,tempfile,unittest
from pathlib import Path
import analysis_tests as fixtures
import build_facts as facts
import research_mode as mode
import validate_analysis as gate
import create_presentation as scaffold

class ModeTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.manifest,self.f,self.a,self.b,self.rv=fixtures.fixture(self.root)
 def tearDown(self):self.temp.cleanup()
 def start(self,depth='low'):
  mode.initialize(self.root,depth);mode.job(self.root,'alice','alice-worker','researcher',repos=['demo/one'],agent='alice-agent')
 def read(self,key='one',phase=0):
  if 'alice-worker'in mode.states(mode.ledger(self.root))and phase!=mode.states(mode.ledger(self.root))['alice-worker']['round']:
   mode.finish(self.root,'alice-worker','Initial findings ready for follow-up');mode.resume(self.root,'alice-worker','Bounded follow-up',phase)
  return mode.packet(self.root,'alice',[self.a['id']],key,phase,'diff',job_id='alice-worker')
 def test_default_is_medium_and_not_collection_identity(self):
  original=facts.digest(self.root/'manifest.json');p=mode.initialize(self.root);self.assertEqual(p['mode'],'medium');self.assertEqual(p['people']['alice']['initialBundles'],80);self.assertEqual(original,facts.digest(self.root/'manifest.json'))
 def test_low_initial_limit(self):
  self.start()
  for i in range(24):self.read(str(i))
  with self.assertRaisesRegex(ValueError,'exhausted'):self.read('beyond')
 def test_follow_up_limits(self):
  self.start()
  for i in range(6):self.read(str(i),1)
  with self.assertRaisesRegex(ValueError,'exhausted'):self.read('extra',1)
  with self.assertRaisesRegex(ValueError,'round'):self.read('second-round',2)
 def test_no_repo_children_in_low(self):
  self.start()
  with self.assertRaisesRegex(ValueError,'allowance'):mode.job(self.root,'alice','extra-worker','researcher',repos=['demo/two'])
  with self.assertRaisesRegex(ValueError,'allowance'):mode.job(self.root,'alice','parent','coordinator',agent='coordinator')
 def test_finished_low_researcher_resumes_without_new_context(self):
  self.start();self.read();mode.finish(self.root,'alice-worker','Initial findings')
  mode.resume(self.root,'alice-worker','Inspector requested a source clarification',1)
  self.read('follow-up',1);mode.finish(self.root,'alice-worker','Clarification inspected')
  self.assertEqual(mode.report(self.root)['subjects']['alice']['jobs'],1)
  self.assertEqual(mode.report(self.root)['subjects']['alice']['packetsByRound']['1'],1)
 def test_medium_batches_and_coordinator(self):
  mode.initialize(self.root,'medium');mode.job(self.root,'alice','parent','coordinator',agent='coordinator')
  for i in range(3):mode.job(self.root,'alice',str(i),'researcher',repos=['demo/one'],agent='batch-'+str(i))
  with self.assertRaisesRegex(ValueError,'allowance'):mode.job(self.root,'alice','four','researcher')
 def test_high_single_repo_contexts(self):
  mode.initialize(self.root,'high');mode.job(self.root,'alice','one','researcher',repos=['demo/one'],agent='one');mode.job(self.root,'alice','two','researcher',repos=['demo/two'],agent='two')
  with self.assertRaisesRegex(ValueError,'duplicating'):mode.job(self.root,'alice','duplicate','researcher',repos=['demo/one'])
  with self.assertRaisesRegex(ValueError,'one relevant'):mode.job(self.root,'bob','wide','researcher',repos=[])
 def test_upgrade_retains_usage_and_archive(self):
  self.start();self.read();before=facts.digest(self.root/'manifest.json')
  with self.assertRaisesRegex(ValueError,'authorization'):mode.initialize(self.root,'medium')
  mode.initialize(self.root,'medium',authorization='User explicitly requested Medium');self.assertEqual(mode.report(self.root)['subjects']['alice']['packetsByRound']['0'],1);self.assertEqual(before,facts.digest(self.root/'manifest.json'))
  with self.assertRaisesRegex(ValueError,'relabel'):mode.initialize(self.root,'low',authorization='Try cheaper label')
 def test_reopening_plan_is_idempotent(self):
  self.start();pp=self.root/'analysis/research-plan.json';before=pp.read_bytes();mode.initialize(self.root,'low');self.assertEqual(pp.read_bytes(),before)
 def test_unspecified_mode_on_resume_preserves_previous_choice(self):
  self.start();self.read();p=mode.initialize(self.root);self.assertEqual(p['mode'],'low')
 def test_broad_metadata_brief_stays_bounded_with_disclosure(self):
  f=facts.load(self.root/'analysis/facts.json');repos=['demo/'+('x'*90)+str(i)for i in range(400)];f['people']['alice']['observedRepositories']=repos
  for i,repo in enumerate(repos):f['sourceIndex'][str(i)]={'id':str(i),'kind':'commit','repo':repo,'actor':'alice','occurredAt':'2026-01-10T12:00:00Z','url':'https://github.com/'+repo+'/commit/'+('a'*40),'title':'A concrete source lead','data':{}}
  facts.save(self.root/'analysis/facts.json',f);mode.initialize(self.root,'low');mode.job(self.root,'alice','reader','researcher',agent='reader');r=mode.brief(self.root,'alice','reader');self.assertLessEqual(len(json.dumps(r,ensure_ascii=False)),12000);self.assertTrue(r['selectionLimited']);self.assertEqual(r['repositoriesAvailable'],400)
 def test_reading_requires_registered_context(self):
  mode.initialize(self.root)
  with self.assertRaisesRegex(ValueError,'active'):self.read()
 def test_bounded_actual_diff_not_just_file_list(self):
  self.start();p=self.root/self.a['data']['detail'];facts.save(p,{'sha':'a'*40,'paths':['path'+str(i)for i in range(10000)],'patches':[{'path':'src/service.cs','patch':'+ actual-code\n'*10000}]});result=self.read();self.assertIn('actual-code',result['items'][0]['excerpt']);self.assertNotIn('path9999',result['items'][0]['excerpt']);self.assertLessEqual(len(json.dumps(result,ensure_ascii=False)),12000);self.assertTrue(result['truncated']);self.assertEqual(mode.ledger(self.root)[-1]['characters'],len(json.dumps(result,ensure_ascii=False)))
 def test_missing_diff_is_not_fake_inspection(self):
  self.start();facts.save(self.root/self.a['data']['detail'],{'patches':[]})
  with self.assertRaisesRegex(ValueError,'No retained text diff'):self.read()
 def test_packet_is_not_read_log(self):
  self.start();self.read();self.assertFalse((self.root/'analysis/inspection/read-log.jsonl').exists())
 def test_re_read_has_cost_and_unique_id(self):
  self.start();self.read()
  with self.assertRaisesRegex(ValueError,'new bundle'):self.read()
  self.read('second-reading');self.assertEqual(mode.report(self.root)['subjects']['alice']['packetsByRound']['0'],2)
 def test_shared_allowance_is_not_per_member(self):
  self.start();mode.job(self.root,'team','inspection','inspector',agent='root')
  for i in range(12):mode.packet(self.root,'team',[self.a['id']],f'shared-{i}',level='diff',job_id='inspection')
  with self.assertRaisesRegex(ValueError,'exhausted'):mode.packet(self.root,'team',[self.b['id']],'extra',level='diff',job_id='inspection')
 def test_summary_bound(self):
  self.start()
  with self.assertRaisesRegex(ValueError,'concise'):mode.finish(self.root,'alice-worker','x'*10001)
  mode.finish(self.root,'alice-worker','A concise finding')
  with self.assertRaisesRegex(ValueError,'active'):self.read()
 def test_tokens_unknown_until_runtime_measurements(self):
  self.start();self.assertIsNone(mode.report(self.root)['actualTokens']);mode.record_tokens(self.root,'call-1',100,20,'runtime response',40);r=mode.report(self.root);self.assertEqual(r['actualTokens']['input'],100);self.assertFalse(r['exactTokenLimitEnforced'])
  with self.assertRaisesRegex(ValueError,'distinct'):mode.record_tokens(self.root,'call-1',100,20,'runtime response')
  with self.assertRaisesRegex(ValueError,'subset'):mode.record_tokens(self.root,'call-2',10,20,'runtime response',11)
 def test_optional_challenge_policy(self):
  self.start()
  with self.assertRaisesRegex(ValueError,'unavailable'):mode.job(self.root,'team','challenge','challenge',agent='other')
  mode.initialize(self.root,'medium',authorization='User selected Medium')
  with self.assertRaisesRegex(ValueError,'uncertainty'):mode.job(self.root,'team','challenge','challenge',agent='other')
  mode.job(self.root,'team','challenge','challenge',agent='other',reason='Conflicting source claims')
 def test_brief_has_bounded_metadata(self):
  self.start();r=mode.brief(self.root,'alice','alice-worker');self.assertEqual(r['totals']['commits'],1);self.assertLessEqual(len(json.dumps(r,ensure_ascii=False)),12000)
  mode.brief(self.root,'alice','alice-worker')
  with self.assertRaisesRegex(ValueError,'re-read'):mode.brief(self.root,'alice','alice-worker')
 def test_aliases(self):self.assertEqual(mode.mode_name('MEDUIM'),'medium');self.assertEqual(mode.mode_name('HIGH'),'high')

class ModeGateTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.pres,self.data=fixtures.reviewed(self.root)
 def tearDown(self):self.temp.cleanup()
 def judge(self):return facts.load(self.root/'analysis/inspection/decisions.json')
 def store(self,j):facts.save(self.root/'analysis/inspection/decisions.json',j)
 def test_medium_requires_separate_passes(self):
  j=self.judge();j['reviewPasses']=[{'type':'combined','status':'passed','reviewer':'root','notes':'Both reviewed'}];self.store(j)
  with self.assertRaisesRegex(gate.Invalid,'factual'):gate.validate(self.root,self.pres)
 def test_low_combined_pass_is_valid(self):
  # Fresh fixture avoids relabeling already spent Medium context.
  with tempfile.TemporaryDirectory()as d:
   root=Path(d);fixtures.fixture(root);mode.initialize(root,'low');mode.job(root,'team','inspector','inspector');mode.finish(root,'inspector','Combined factual/editorial inspection')
   judge={'reviewedBy':'root','reviewPasses':[{'type':'combined','status':'passed','reviewer':'root','notes':'Both criteria examined'}]};self.assertEqual(mode.validate_mode(root,judge,[])['mode'],'low')
 def test_high_needs_completed_distinct_challenge(self):
  mode.initialize(self.root,'high',authorization='User requested a deeper review');j=self.judge();self.store(j)
  with self.assertRaisesRegex(gate.Invalid,'challenge'):gate.validate(self.root,self.pres)
  j['reviewPasses'].append({'type':'challenge','status':'passed','reviewer':'independent-agent','notes':'Challenged interpretation and alternatives'});self.store(j)
  with self.assertRaisesRegex(gate.Invalid,'distinct'):gate.validate(self.root,self.pres)
  mode.job(self.root,'team','challenge','challenge',agent='independent-agent');mode.finish(self.root,'challenge','Sources and interpretations challenged');self.assertTrue(gate.validate(self.root,self.pres,True)['passed'])
 def test_high_independence_uses_registered_agents_not_display_name(self):
  mode.initialize(self.root,'high',authorization='User requested High');j=self.judge();j['reviewedBy']='Root Inspector';j['reviewPasses'].append({'type':'challenge','status':'passed','reviewer':'fixture-reviewer','notes':'Claimed challenge'});self.store(j)
  with self.assertRaisesRegex(ValueError,'fresh subagent'):mode.job(self.root,'team','fake-independent','challenge',agent='fixture-reviewer')
  with self.assertRaisesRegex(gate.Invalid,'distinct'):gate.validate(self.root,self.pres)
 def test_log_needs_delivered_packet_and_correct_reader(self):
  p=self.root/'analysis/inspection/read-log.jsonl';logs=list(facts.rows(p));logs[0]['budgetEntryId']='not-issued';p.write_text(''.join(json.dumps(x)+'\n'for x in logs))
  with self.assertRaisesRegex(gate.Invalid,'budgetEntryId'):gate.validate(self.root,self.pres)
 def test_scaffold_rejects_changed_ledger_after_approval(self):
  gate.validate(self.root,self.pres,True);mode.record_tokens(self.root,'last-call',2,3,'runtime response')
  with self.assertRaisesRegex(ValueError,'researchLedger'):scaffold.create(self.pres,self.root/'analysis/inspection/decisions.json',self.root/'app')
 def test_incomplete_jobs_cannot_seal(self):
  mode.job(self.root,'bob','extra','researcher',agent='worker')
  with self.assertRaisesRegex(gate.Invalid,'Complete registered'):gate.validate(self.root,self.pres)
 def test_sequential_high_discloses_no_independence(self):
  mode.initialize(self.root,'high',authorization='User requested High; runtime has no subagents',execution='sequential-fallback');j=self.judge();j['reviewPasses'].append({'type':'challenge','status':'passed','reviewer':'fixture-reviewer','notes':'Separate challenge pass; no independent agent available'});self.store(j);self.assertEqual(gate.validate(self.root,self.pres,True)['researchMode'],'high')
if __name__=='__main__':unittest.main()
