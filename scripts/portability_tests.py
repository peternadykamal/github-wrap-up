import copy,json,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
import analysis_tests as fixtures
import build_facts as files
import install_skill,package_skill,model_policy as policy,research_mode as mode


def runtime_v2(run):
 catalog=files.load(run/'analysis/runtime-models.json');catalog['schemaVersion']=2
 catalog['adapter']={'kind':'tool-arguments','interface':'native-agent-tool','modelPath':['model'],'effortPath':['effort'],'freshContext':{'strategy':'native'}}
 return catalog

class AdapterTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);fixtures.fixture(self.root)
 def tearDown(self):self.tmp.cleanup()
 def store(self,c):files.save(self.root/'analysis/runtime-models.json',c)
 def test_native_effort_parameter_avoids_codex_fields(self):
  c=runtime_v2(self.root);self.store(c);p=mode.initialize(self.root);j=mode.job(self.root,'alice','new','researcher',agent='native-child');d=j['modelRequest']['dispatch'];self.assertEqual(d['arguments'],{'model':'fictional-future-balanced','effort':'normal'});self.assertEqual(d['context'],'fresh-native');policy.validate_job(self.root,p,j)
 def test_nested_numeric_effort_is_rendered_from_runtime_mapping(self):
  c=runtime_v2(self.root);c['adapter'].update(effortPath=['thinking','budget_tokens'],fixedArguments={'thinking':{'type':'enabled'}})
  c['models'][1]['effortValues']={'normal':4096,'deliberate':8192};self.store(c);r=policy.resolve(self.root,'medium');self.assertEqual(r['roles']['researcher']['dispatch']['arguments']['thinking'],{'type':'enabled','budget_tokens':4096});self.assertEqual(r['roles']['researcher']['effort'],'normal');policy.validate_resolution(self.root,r)
 def test_custom_fresh_context_parameter_and_model_field(self):
  c=runtime_v2(self.root);c['adapter'].update(modelPath=['agent','model'],effortPath=['options','reasoning'],freshContext={'strategy':'parameter','path':['inheritHistory'],'value':False});self.store(c);r=policy.resolve(self.root,'medium');d=r['roles']['researcher']['dispatch']['arguments'];self.assertEqual(d['agent']['model'],'fictional-future-balanced');self.assertFalse(d['inheritHistory']);self.assertEqual(d['options']['reasoning'],'normal')
 def test_configuration_adapter_generates_data_without_writing_harness_config(self):
  c=runtime_v2(self.root);c['adapter']['kind']='agent-configuration';c['adapter']['interface']='custom-agent-definition';self.store(c);before=list(self.root.glob('.*/**/*'));r=policy.resolve(self.root,'high');self.assertEqual(r['roles']['challenge']['dispatch']['kind'],'agent-configuration');self.assertEqual(list(self.root.glob('.*/**/*')),before)
 def test_non_openai_official_guidance_accepted_with_publisher(self):
  c=runtime_v2(self.root);self.store(c);a=files.load(self.root/'analysis/model-assessments.json');a['models'][1]['guidance']=[{'kind':'official-documentation','publisher':'Anthropic','url':'https://code.claude.com/docs/en/sub-agents','checkedAt':c['capturedAt']}];files.save(self.root/'analysis/model-assessments.json',a);r=policy.resolve(self.root,'medium');self.assertEqual(r['status'],'resolved');policy.validate_resolution(self.root,r)
 def test_guidance_does_not_claim_official_without_publisher(self):
  c=runtime_v2(self.root);self.store(c);a=files.load(self.root/'analysis/model-assessments.json');a['models'][0]['guidance']=[{'kind':'official-documentation','url':'https://vendor.example/docs','checkedAt':c['capturedAt']}];files.save(self.root/'analysis/model-assessments.json',a);self.assertEqual(policy.resolve(self.root,'low')['status'],'blocked')
 def test_model_only_harness_keeps_effort_unknown(self):
  c=runtime_v2(self.root);c['controls']['effortOverride']=False;c['adapter'].pop('effortPath');self.store(c);p=mode.initialize(self.root,'high');r=p['modelSelection'];choice=r['roles']['researcher'];self.assertIsNone(choice['effort']);self.assertEqual(choice['effortControl'],'inherited');self.assertEqual(choice['dispatch']['arguments'],{'model':'fictional-future-balanced'});self.assertTrue(any('not achieved'in x for x in r['disclosures']));policy.validate_resolution(self.root,r);mode.job(self.root,'alice','job','researcher',repos=['demo/one'],agent='native-child')
 def test_no_agent_controls_still_allow_recorded_sequential_work(self):
  c=runtime_v2(self.root);c['controls'].update(modelOverride=False,effortOverride=False);c['models']=[];self.store(c);mode.initialize(self.root,'low',execution='sequential-fallback',authorization='Native harness exposes no worker/model controls');j=mode.job(self.root,'alice','research','researcher',agent='root');packet=mode.brief(self.root,'alice','research');mode.finish(self.root,'research','Focused sequential research complete');self.assertEqual(j['modelRequest']['status'],'inherited-sequential');self.assertIsNone(mode.report(self.root)['actualTokens']);self.assertIn('budgetEntryId',packet);report=mode.report(self.root);self.assertEqual(report['executionReason'],'Native harness exposes no worker/model controls');self.assertIn('unavailable',report['reviewIndependence'])
 def test_initial_fallback_requires_an_actual_runtime_reason(self):
  with self.assertRaisesRegex(ValueError,'runtime reason'):mode.initialize(self.root,'low',execution='sequential-fallback')
 def test_sequential_fallback_enforces_known_root(self):
  c=runtime_v2(self.root);self.store(c);mode.initialize(self.root,'low',execution='sequential-fallback',authorization='No usable worker control')
  with self.assertRaisesRegex(ValueError,'actual root'):mode.job(self.root,'alice','fake','researcher',agent='invented-child')
  mode.job(self.root,'alice','real','researcher',agent='root')
 def test_unknown_root_fallback_uses_one_consistent_executor(self):
  (self.root/'analysis/runtime-models.json').unlink();mode.initialize(self.root,'medium',execution='sequential-fallback',authorization='No agent discovery');mode.job(self.root,'alice','first','researcher',agent='actual-session')
  with self.assertRaisesRegex(ValueError,'actual root'):mode.job(self.root,'bob','second','researcher',agent='invented-session')
 def test_no_catalog_sequential_inspector_can_seal_and_scaffold(self):
  import validate_analysis,create_presentation
  run=self.root/'no-catalog';pres,_=fixtures.reviewed(run)
  for file in ['research-plan.json','research-ledger.jsonl','runtime-models.json','model-assessments.json']:(run/'analysis'/file).unlink()
  mode.initialize(run,'medium',execution='sequential-fallback',authorization='Host has no model discovery or subagent interfaces');logs=list(files.rows(run/'analysis/inspection/read-log.jsonl'));mode.job(run,'team','inspector','inspector',agent='root')
  for pid,log in zip(['alice','bob','team'],logs):
   jid='inspector'if pid=='team'else pid+'-research'
   if pid!='team':mode.job(run,pid,jid,'researcher',agent='root')
   packet=mode.packet(run,pid,[log['sourceId']],pid+'-sequential',level='diff',job_id=jid);log.update(agent='root',budgetEntryId=packet['budgetEntryId']);mode.finish(run,jid,'Sequential fixture source read and reviewed')
  (run/'analysis/inspection/read-log.jsonl').write_text(''.join(json.dumps(x)+'\n'for x in logs));self.assertTrue(validate_analysis.validate(run,pres,True)['passed']);create_presentation.create(pres,run/'analysis/inspection/decisions.json',run/'app');provenance=files.load(run/'app/research-provenance.json');self.assertIn('unavailable',provenance['modelProfiles']['reviewIndependence'])
 def test_adapter_collision_fails_instead_of_overriding_selected_model(self):
  c=runtime_v2(self.root);c['adapter']['fixedArguments']={'model':'unrequested'};self.store(c)
  with self.assertRaisesRegex(ValueError,'overlaps'):policy.resolve(self.root,'medium')
 def test_missing_fresh_context_contract_fails(self):
  c=runtime_v2(self.root);c['adapter'].pop('freshContext');self.store(c)
  with self.assertRaisesRegex(ValueError,'fresh context'):policy.resolve(self.root,'medium')
 def test_legacy_frozen_run_still_valid_after_v2_upgrade(self):
  p=mode.initialize(self.root,'medium');j=mode.job(self.root,'alice','old','researcher',agent='old-child');mode.finish(self.root,'old','Prior findings');self.store(runtime_v2(self.root));new=mode.initialize(self.root,'high',authorization='User requested High');policy.validate_job(self.root,new,j);self.assertEqual(new['previousModelSelections'][0]['schemaVersion'],1)
  with self.assertRaisesRegex(ValueError,'new context'):mode.resume(self.root,'old','Use a new harness',0)

class DistributionTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.source=Path(__file__).resolve().parent.parent
 def tearDown(self):self.tmp.cleanup()
 def test_copy_is_relocatable_and_runs_without_original_install(self):
  result=install_skill.install(self.source,self.root/'skills');target=Path(result['target']);self.assertTrue((target/'SKILL.md').is_file());self.assertFalse((target/'.git').exists());self.assertFalse(any(target.rglob('*.pyc')))
  process=subprocess.run([sys.executable,str(target/'scripts/model_policy.py'),'--help'],cwd=self.root,capture_output=True,text=True);self.assertEqual(process.returncode,0,process.stderr)
  process=subprocess.run([sys.executable,str(target/'scripts/resolve_scope.py'),'--help'],cwd=self.root,capture_output=True,text=True);self.assertEqual(process.returncode,0,process.stderr)
 def test_agent_install_instructions_survive_copy_and_packaging(self):
  result=install_skill.install(self.source,self.root/'skills');target=Path(result['target']);self.assertEqual((target/'INSTALL.md').read_bytes(),(self.source/'INSTALL.md').read_bytes());archive=self.root/'portable.zip';package_skill.package(target,archive)
  with zipfile.ZipFile(archive)as z:self.assertIn('github-year-in-review/INSTALL.md',z.namelist());self.assertEqual(z.read('github-year-in-review/INSTALL.md'),(self.source/'INSTALL.md').read_bytes())
 def test_install_does_not_overwrite_existing_skill(self):
  install_skill.install(self.source,self.root/'skills')
  with self.assertRaisesRegex(ValueError,'already exists'):install_skill.install(self.source,self.root/'skills')
 def test_live_link_is_idempotent(self):
  a=install_skill.install(self.source,self.root/'skills',link=True);b=install_skill.install(self.source,self.root/'skills',link=True);self.assertEqual(b['status'],'already-linked');self.assertTrue(Path(a['target']).is_symlink())
 def test_dry_run_creates_nothing(self):
  install_skill.install(self.source,self.root/'skills',dry_run=True);self.assertFalse((self.root/'skills').exists())
 def test_install_inside_source_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'outside'):install_skill.install(self.source,self.source/'nested-install',dry_run=True)
 def test_package_excludes_run_data_and_git(self):
  fake=self.root/'source';fake.mkdir();(fake/'SKILL.md').write_text('Skill');(fake/'scripts').mkdir();(fake/'scripts/helper.py').write_text('pass');(fake/'runs').mkdir();(fake/'runs/identity-emails.json').write_text('private');(fake/'.git').mkdir();(fake/'.git/config').write_text('private');package_skill.package(fake,self.root/'portable.zip')
  with zipfile.ZipFile(self.root/'portable.zip')as z:self.assertEqual(set(z.namelist()),{'github-year-in-review/SKILL.md','github-year-in-review/scripts/helper.py'})

if __name__=='__main__':unittest.main()
