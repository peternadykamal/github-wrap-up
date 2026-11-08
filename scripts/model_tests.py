import copy,datetime as dt,tempfile,unittest
from pathlib import Path
import analysis_tests as fixtures
import build_facts as files
import model_policy as policy
import research_mode as mode
import validate_analysis as gate
import create_presentation as scaffold

class ModelPolicyTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);fixtures.fixture(self.root)
 def tearDown(self):self.temp.cleanup()
 def catalog(self):return files.load(self.root/'analysis/runtime-models.json')
 def assessments(self):return files.load(self.root/'analysis/model-assessments.json')
 def write_catalog(self,c):files.save(self.root/'analysis/runtime-models.json',c)
 def write_assessments(self,a):files.save(self.root/'analysis/model-assessments.json',a)
 def test_profiles_resolve_future_models_and_runtime_efforts(self):
  for depth,mid,effort in [('low','efficient','quick'),('medium','balanced','normal'),('high','balanced','deliberate')]:
   r=policy.resolve(self.root,depth);policy.validate_resolution(self.root,r);choice=r['roles']['researcher'];self.assertEqual(choice['modelId'],'fictional-future-'+mid);self.assertEqual(choice['effort'],effort);self.assertEqual(choice['dispatch']['fork_turns'],'none');self.assertTrue(choice['provisional']);self.assertFalse(choice['runtimeConfirmed'])
  self.assertEqual(r['roles']['challenge']['modelId'],'fictional-future-deep')
 def test_no_catalog_does_not_guess_or_inherit(self):
  (self.root/'analysis/runtime-models.json').unlink();p=mode.initialize(self.root);self.assertEqual(p['modelSelection']['status'],'pending')
  with self.assertRaisesRegex(ValueError,'Resolve'):mode.job(self.root,'alice','job','researcher',agent='worker')
  inspector=mode.job(self.root,'team','inspect','inspector',agent='root');self.assertIsNone(inspector['modelRequest']['modelId'])
 def test_stale_catalog_requires_refresh_at_resolution_only(self):
  c=self.catalog();c['capturedAt']=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=2)).isoformat();self.write_catalog(c)
  with self.assertRaisesRegex(ValueError,'fresh runtime'):policy.resolve(self.root,'low')
 def test_effort_not_supported_is_blocked(self):
  a=self.assessments();a['models'][0]['effortByIntent']['economical']='invented-effort';self.write_assessments(a);r=policy.resolve(self.root,'low');self.assertEqual(r['status'],'blocked');self.assertIn('not advertised',r['roles']['researcher']['rejected'][0]['reason'])
 def test_unavailable_or_toolless_model_is_not_selected(self):
  c=self.catalog();c['models'][0]['available']=False;self.write_catalog(c);self.assertEqual(policy.resolve(self.root,'low')['status'],'blocked')
  c['models'][0].update(available=True,toolCalling=False);self.write_catalog(c);self.assertEqual(policy.resolve(self.root,'low')['status'],'blocked')
 def test_override_failure_has_explicit_sequential_fallback(self):
  c=self.catalog();c['controls']['effortOverride']=False;self.write_catalog(c);mode.initialize(self.root,'low')
  with self.assertRaisesRegex(ValueError,'no supported model'):mode.job(self.root,'alice','job','researcher',agent='worker')
  mode.initialize(self.root,authorization='Runtime cannot override effort; disclose inherited settings',execution='sequential-fallback');j=mode.job(self.root,'alice','fallback','researcher',agent='root');self.assertEqual(j['modelRequest']['status'],'inherited-sequential');self.assertIsNone(j['modelRequest']['modelId']);policy.validate_job(self.root,mode.current(self.root),j)
 def test_validated_candidate_wins_over_new_guidance_only_peer(self):
  c=self.catalog();a=self.assessments();new=copy.deepcopy(c['models'][1]);new['id']='fictional-new-release';c['models'].insert(0,new);v=copy.deepcopy(a['models'][1]);v['modelId']=new['id'];v['currentlyRecommended']=True;a['models'].insert(0,v)
  proof=self.root/'analysis/evaluation.json';files.save(proof,{'modelId':'fictional-future-balanced','passed':True,'roles':['researcher','coordinator']});a['models'][2]['validation']={'status':'validated','evidence':[{'path':'analysis/evaluation.json','sha256':files.digest(proof)}]};self.write_catalog(c);self.write_assessments(a)
  r=policy.resolve(self.root,'medium');self.assertEqual(r['roles']['researcher']['modelId'],'fictional-future-balanced');self.assertFalse(r['roles']['researcher']['provisional']);policy.validate_resolution(self.root,r)
  files.save(proof,{'modelId':'fictional-future-balanced','passed':False,'roles':['researcher']})
  with self.assertRaisesRegex(ValueError,'evidence changed'):policy.validate_resolution(self.root,r)
 def test_failed_evaluation_cannot_claim_validated(self):
  a=self.assessments();proof=self.root/'analysis/evaluation.json';files.save(proof,{'modelId':'fictional-future-efficient','passed':False,'roles':['researcher']});a['models'][0]['validation']={'status':'validated','evidence':[{'path':'analysis/evaluation.json','sha256':files.digest(proof)}]};self.write_assessments(a);self.assertEqual(policy.resolve(self.root,'low')['status'],'blocked')
 def test_resume_is_frozen_despite_new_live_catalog(self):
  p=mode.initialize(self.root,'medium');original=p['modelSelection'];c=self.catalog();c['models'][1]['available']=False;self.write_catalog(c);self.assertEqual(mode.initialize(self.root)['modelSelection'],original);self.assertEqual(mode.job(self.root,'alice','job','researcher',agent='worker')['modelRequest']['modelId'],'fictional-future-balanced')
 def test_upgrade_preserves_prior_binding_and_refuses_relabeling(self):
  mode.initialize(self.root,'low');j=mode.job(self.root,'alice','job','researcher',agent='worker');mode.finish(self.root,'job','Finished Low work');p=mode.initialize(self.root,'medium',authorization='User asked for Medium');self.assertEqual(len(p['previousModelSelections']),1);policy.validate_job(self.root,p,j)
  with self.assertRaisesRegex(ValueError,'new context'):mode.resume(self.root,'job','Deeper work',0)
  next_job=mode.job(self.root,'alice','new-job','researcher',agent='new-worker');self.assertNotEqual(j['modelRequest']['modelId'],next_job['modelRequest']['modelId'])
 def test_active_old_context_cannot_take_new_profile_packets(self):
  mode.initialize(self.root,'medium');mode.job(self.root,'alice','job','researcher',agent='worker');mode.initialize(self.root,'high',authorization='User asked for High')
  with self.assertRaisesRegex(ValueError,'new context'):mode.brief(self.root,'alice','job')
  source=next(iter(files.load(self.root/'analysis/facts.json')['sourceIndex']))
  with self.assertRaisesRegex(ValueError,'new context'):mode.packet(self.root,'alice',[source],'wrong-profile',job_id='job')
 def test_new_job_id_cannot_relabel_existing_actual_context(self):
  mode.initialize(self.root,'medium');mode.job(self.root,'alice','job','researcher',agent='same-agent');mode.finish(self.root,'job','Initial work');mode.initialize(self.root,'high',authorization='User requested High')
  with self.assertRaisesRegex(ValueError,'distinct actual'):mode.job(self.root,'alice','new-job','researcher',repos=['demo/one'],agent='same-agent')
 def test_root_cannot_be_relabelled_as_selected_child(self):
  mode.initialize(self.root,'low')
  with self.assertRaisesRegex(ValueError,'fresh subagent'):mode.job(self.root,'alice','job','researcher',agent='root')
 def test_runtime_requested_is_not_runtime_confirmed(self):
  mode.initialize(self.root,'low');j=mode.job(self.root,'alice','job','researcher',agent='worker');self.assertNotIn('runtimeReported',j);self.assertFalse(j['modelRequest']['runtimeConfirmed'])
  with self.assertRaisesRegex(ValueError,'different model'):mode.job(self.root,'bob','wrong','researcher',agent='other',runtime_reported={'source':'test runtime reply','modelId':'unexpected'})
 def test_preview_checks_capacity_without_spending_a_job(self):
  mode.initialize(self.root,'low');before=mode.ledger(self.root);r=mode.job(self.root,'alice','job','researcher',preview=True);self.assertEqual(mode.ledger(self.root),before);self.assertEqual(r['launch']['fork_turns'],'none');self.assertEqual(r['launch']['model'],'fictional-future-efficient')
 def test_snapshot_and_role_tampering_rejected(self):
  p=mode.initialize(self.root,'medium');r=p['modelSelection'];p['modelSelection']['roles']['researcher']['effort']='quick';files.save(self.root/'analysis/research-plan.json',p)
  with self.assertRaisesRegex(ValueError,'differs'):mode.current(self.root)
  files.save(self.root/r['catalogPath'],{})
  with self.assertRaisesRegex(ValueError,'snapshot changed'):mode.current(self.root)
 def test_parent_settings_only_known_if_runtime_confirms(self):
  c=self.catalog();c['parent'].update(modelId='fictional-parent',effort='app-effort');self.write_catalog(c);self.assertIsNone(policy.resolve(self.root,'low')['roles']['inspector']['modelId']);c['parent']['confirmedByRuntime']=True;self.write_catalog(c);r=policy.resolve(self.root,'low');self.assertEqual(r['roles']['inspector']['modelId'],'fictional-parent');self.assertEqual(r['roles']['inspector']['dispatch'],{})
 def test_missing_job_binding_is_not_silently_accepted(self):
  p=mode.initialize(self.root,'low');j=mode.job(self.root,'alice','job','researcher',agent='worker');del j['modelRequest']
  with self.assertRaisesRegex(ValueError,'missing'):policy.validate_job(self.root,p,j)
 def test_scaffold_rechecks_frozen_snapshot_after_sealing(self):
  with tempfile.TemporaryDirectory()as folder:
   run=Path(folder);pres,_=fixtures.reviewed(run);gate.validate(run,pres,True);p=mode.current(run);files.save(run/p['modelSelection']['catalogPath'],{})
   with self.assertRaisesRegex(ValueError,'snapshot changed'):scaffold.create(pres,run/'analysis/inspection/decisions.json',run/'app')
 def test_api_wide_catalog_cannot_impersonate_runtime_availability(self):
  c=self.catalog();c['source']['kind']='api-model-list';self.write_catalog(c)
  with self.assertRaisesRegex(ValueError,'runtime availability'):policy.resolve(self.root,'medium')

if __name__=='__main__':unittest.main()
