#!/usr/bin/env python3
"""Offline collector checks; all Git state lives in temporary directories."""
import datetime as dt
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('collect',Path(__file__).with_name('collect.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


def cfg(**extra):
    value={'schemaVersion':1,'window':{'start':'2026-01-01T00:00:00Z','endExclusive':'2026-11-08T00:00:00Z','timezone':'UTC','dateBasis':'authored'},'subjects':[{'id':'Alice','login':'Alice','aliases':{'logins':['OldAlice'],'emails':['alice@fixture.invalid']}}],'repos':['sample/product'],'orgs':[]}
    value.update(extra)
    return value


class TestCollector(unittest.TestCase):
    def test_identity_uses_account_before_email_and_never_display_name(self):
        with tempfile.TemporaryDirectory()as root:
            co=c.Collector(cfg(),root)
            self.assertEqual(co.identity('oldalice',None)[0],'Alice')
            self.assertEqual(co.identity(None,'Alice@fixture.invalid')[0],'Alice')
            self.assertEqual(co.identity('OtherUser','alice@fixture.invalid')[0],'OtherUser')
            self.assertIsNone(co.identity(None,'unknown@fixture.invalid')[0])

    def test_duplicate_alias_rejected(self):
        data=cfg();data['subjects'].append({'id':'Bob','login':'Bob','aliases':{'logins':['OldAlice'],'emails':[]}})
        with self.assertRaises(ValueError):c.normalize_config(data)

    def test_half_open_interval_timezone_and_future_months(self):
        with tempfile.TemporaryDirectory()as root:
            co=c.Collector(cfg(),root)
            self.assertTrue(co.inside('2026-01-01T02:00:00+02:00'))
            self.assertFalse(co.inside('2026-11-08T00:00:00Z'))
            self.assertFalse(co.inside('2025-12-31T23:59:59Z'))
            self.assertEqual(len(c.months_in_window(co.window)),12)

    def test_previous_frozen_window_preserved_for_resume(self):
        data={'subjects':cfg()['subjects'],'repos':['sample/product']}
        previous={'inputConfigHash':c.digest(data),'window':cfg()['window']}
        self.assertEqual(c.normalize_config(data,previous)['window']['endExclusive'],'2026-11-08T00:00:00Z')

    def test_cache_and_pagination_replay_without_network(self):
        with tempfile.TemporaryDirectory()as root:
            api=c.API(root)
            responses=[json.dumps(list(range(100))),json.dumps([100,101])]
            with patch.object(c,'command',side_effect=responses)as invoke:
                self.assertEqual(len(api.paginate('repos/sample/product/issues')),102)
                self.assertEqual(invoke.call_count,2)
            with patch.object(c,'command',side_effect=AssertionError('network called')):
                self.assertEqual(len(api.paginate('repos/sample/product/issues')),102)
                self.assertEqual(api.hits,2)

    def test_capped_search_subdivides_instead_of_silent_truncation(self):
        with tempfile.TemporaryDirectory()as root:
            api=c.API(root);calls=[]
            def get(endpoint,params=None):
                calls.append(params['q'])
                if len(calls)==1:return {'total_count':1001,'items':[]}
                return {'total_count':1,'items':[{'id':len(calls)}]}
            api.get=get
            rows=api.search('search/issues','author:Alice',c.instant('2026-01-01T00:00:00Z'),c.instant('2026-02-01T00:00:00Z'))
            self.assertEqual(len(rows),2);self.assertEqual(len(calls),3)

    def test_incomplete_search_is_error(self):
        with tempfile.TemporaryDirectory()as root:
            api=c.API(root);api.get=lambda *a,**k:{'incomplete_results':True,'items':[],'total_count':10}
            with self.assertRaises(c.CommandError):api.search('search/issues','author:Alice',c.instant('2026-01-01T00:00:00Z'),c.instant('2026-02-01T00:00:00Z'))

    def test_authored_date_traverses_committer_outside_window(self):
        with tempfile.TemporaryDirectory()as root:
            repo=Path(root)/'repo';repo.mkdir()
            c.command(['git','init','-q',str(repo)])
            (repo/'sample.txt').write_text('one\n')
            c.command(['git','-C',str(repo),'add','sample.txt'])
            env={'GIT_AUTHOR_NAME':'Local Alice','GIT_AUTHOR_EMAIL':'alice@fixture.invalid','GIT_AUTHOR_DATE':'2026-03-01T03:00:00+02:00','GIT_COMMITTER_NAME':'Rebaser','GIT_COMMITTER_EMAIL':'rebaser@fixture.invalid','GIT_COMMITTER_DATE':'2027-02-01T00:00:00Z'}
            c.command(['git','-C',str(repo),'commit','-q','-m','Preserve author date'],env=env)
            co=c.Collector(cfg(),Path(root)/'output')
            rows=co.git_commits(repo)
            self.assertEqual(len(rows),1);self.assertTrue(rows[0]['committedAt'].startswith('2027'))
            self.assertEqual(co.footprint(repo,rows[0]['sha'])[0]['path'],'sample.txt')
            change=co.changes('sample/product',repo,rows[0]['sha'],Path(root)/'change.json')
            self.assertFalse(change['inspected']);self.assertEqual(change['paths'],['sample.txt'])
            other=cfg();other['window']['dateBasis']='committed'
            committed=c.Collector(other,Path(root)/'committed')
            self.assertEqual(committed.git_commits(repo),[])

    def test_old_pr_merge_in_year_and_merger_does_not_receive_opening_date(self):
        with tempfile.TemporaryDirectory()as root:
            co=c.Collector(cfg(),root)
            pr=co.record('sample/product','pull_request',1,'OtherUser','2026-02-01T00:00:00Z',data={'number':1,'mergedAt':'2026-05-01T00:00:00Z','closedAt':'2026-05-01T00:00:00Z','mergedBy':'Alice'})
            roles=co.roles(pr,'Alice');self.assertEqual(roles,['merger'])
            self.assertEqual(co.perspective_dates(pr,roles),['2026-05-01T00:00:00Z'])
            old=co.record('sample/product','pull_request',2,'OldAlice','2025-12-01T00:00:00Z',data={'number':2,'mergedAt':'2026-01-02T00:00:00Z','closedAt':'2026-01-02T00:00:00Z'})
            self.assertEqual(co.roles(old,'Alice'),['pr-author'])
            self.assertEqual(co.perspective_dates(old,['pr-author']),['2026-01-02T00:00:00Z'])

    def test_month_perspectives_reference_shared_records(self):
        with tempfile.TemporaryDirectory()as root:
            co=c.Collector(cfg(),root);shared=Path(root)/'repos/sample__product'
            rec=co.record('sample/product','review',3,'Alice','2026-07-10T00:00:00Z',data={'prNumber':2})
            co.write_perspectives('sample/product',shared,[rec],{'status':'partial'})
            folder=Path(root)/'users/Alice/repos/sample__product/months'
            self.assertEqual(len(list(folder.iterdir())),12)
            self.assertEqual(c.read(folder/'2026-07/index.json')['state'],'partial')
            self.assertEqual(c.read(folder/'2026-12/index.json')['state'],'outside-reporting-window')
            line=json.loads((folder/'2026-07/records.jsonl').read_text());self.assertEqual(line['roles'],['reviewer'])

    def test_org_expands_beyond_current_roster_and_scoped_users_do_not_expand(self):
        with tempfile.TemporaryDirectory()as root:
            data=cfg(orgs=['sample'],expandOrganizationContributors=True)
            co=c.Collector(data,root)
            co.expand_subjects('sample/product',['FormerMember','dependabot[bot]','Alice'])
            self.assertEqual({p['id']for p in co.config['subjects']},{'Alice','FormerMember'})
            self.assertTrue(co.config['subjects'][-1]['autoDiscovered'])
            co.expand_subjects('outside/product',['Unrelated'])
            self.assertNotIn('Unrelated',co.logins.values())
        with tempfile.TemporaryDirectory()as root:
            co=c.Collector(cfg(orgs=['sample']),root)
            co.expand_subjects('sample/product',['FormerMember'])
            self.assertEqual(len(co.config['subjects']),1)

    def test_partial_collection_keeps_errors_and_private_files(self):
        with tempfile.TemporaryDirectory()as root:
            co=c.Collector(cfg(),root)
            co.safe('unavailable',lambda:(_ for _ in ()).throw(c.CommandError('403 forbidden')),repo='sample/product')
            result=co.manifest('partial')
            self.assertEqual(len(result['coverage']['errors']),1)
            path=Path(root)/'manifest.json'
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertTrue((Path(root)/'users/Alice/index.json').exists())
            with self.assertRaises(ValueError):c.Collector(cfg(repos=['different/repo']),root)

    def test_private_viewer_inventory_is_included_in_unscoped_discovery(self):
        with tempfile.TemporaryDirectory()as root:
            co=c.Collector(cfg(repos=[]),root)
            private={'full_name':'private/branch-work','id':42}
            def get(endpoint,*args,**kwargs):
                if endpoint=='user':return {'login':'Alice','id':1}
                if endpoint=='users/Alice':return {'login':'Alice','id':1,'name':None}
                if endpoint=='graphql':return {'data':{'user':{'contributionsCollection':{'commitContributionsByRepository':[]}}}}
                return private
            co.api.get=get
            co.api.paginate=lambda endpoint,*a,**k:[private]if endpoint=='user/repos'else[]
            co.api.search=lambda *a,**k:[]
            self.assertIn('private/branch-work',co.discover())

    def test_organization_with_no_visible_members_still_discovers_repositories(self):
        with tempfile.TemporaryDirectory()as root:
            co=c.Collector(cfg(subjects=[],repos=[],orgs=['sample'],expandOrganizationContributors=True),root)
            obj={'full_name':'sample/product','id':1}
            co.api.get=lambda *a,**k:{'login':'Viewer','id':1}
            co.api.paginate=lambda endpoint,*a,**k:[obj]if endpoint=='orgs/sample/repos'else[]
            self.assertIn('sample/product',co.discover())
            co.expand_subjects('sample/product',['FormerMember'])
            self.assertEqual(co.config['subjects'][0]['id'],'FormerMember')

    def test_null_commit_enrichment_is_covered_as_partial(self):
        with tempfile.TemporaryDirectory()as root:
            co=c.Collector(cfg(),root)
            co.api.get=lambda *a,**k:{'data':{'repository':{'c0':None}}}
            self.assertEqual(co.enrich_identities('sample/product',[{'sha':'a'*40}]),{})
            self.assertEqual(co.errors[0]['stage'],'missing-commit-account-objects')

    def test_full_fixture_collection_and_resume(self):
        with tempfile.TemporaryDirectory()as root:
            root=Path(root);repo=root/'git';repo.mkdir()
            c.command(['git','init','-q',str(repo)])
            (repo/'sample.txt').write_text('source fixture\n')
            c.command(['git','-C',str(repo),'add','sample.txt'])
            env={'GIT_AUTHOR_NAME':'Local Alice','GIT_AUTHOR_EMAIL':'alice@fixture.invalid','GIT_AUTHOR_DATE':'2026-03-01T03:00:00+02:00','GIT_COMMITTER_NAME':'Local Alice','GIT_COMMITTER_EMAIL':'alice@fixture.invalid','GIT_COMMITTER_DATE':'2026-03-01T03:00:00+02:00'}
            c.command(['git','-C',str(repo),'commit','-q','-m','Source fixture'],env=env)
            sha=c.command(['git','-C',str(repo),'rev-parse','HEAD']).strip()
            class Fixture(c.Collector):
                def discover(self):return {'sample/product':{'full_name':'sample/product'},'sample/shared':{'full_name':'sample/shared'}}
                def mirror(self,name):return repo,[{'ref':'refs/heads/main','sha':sha}]
                def enrich_identities(self,name,rows):return {sha:{'author':{'user':{'login':'OldAlice'}},'authors':{'nodes':[]}}}
                def pull_requests(self,name):return [self.record(name,'pull_request',1,'OldAlice','2025-12-01T00:00:00Z',title='Old proposal merged this year',data={'number':1,'author':'Alice','createdAt':'2025-12-01T00:00:00Z','mergedAt':'2026-03-02T00:00:00Z','closedAt':'2026-03-02T00:00:00Z','state':'MERGED'})]
                def issues(self,name):return []
                def optional_metadata(self,name):return []
            data=cfg(repos=['sample/product','sample/shared']);out=root/'run'
            result=Fixture(data,out).run()
            self.assertTrue(result['coverage']['complete'])
            self.assertEqual(len(result['repos']),2)
            records=[json.loads(line)for line in (out/'repos/sample__product/records.jsonl').read_text().splitlines()]
            commit=next(r for r in records if r['kind']=='commit')
            self.assertEqual(commit['actor'],'Alice')
            self.assertEqual(commit['data']['sourceAccount'],'OldAlice')
            self.assertEqual(commit['data']['paths'],['sample.txt'])
            self.assertEqual(commit['data']['additions'],1)
            self.assertFalse(commit['data']['inspected'])
            resumed=Fixture(data,out)
            resumed.mirror=lambda name:(_ for _ in ()).throw(AssertionError('Completed mirror should not run'))
            self.assertTrue(resumed.run()['coverage']['complete'])

    def test_patch_redaction_and_sensitive_paths(self):
        secret='ghp_'+'a'*35
        self.assertNotIn(secret,c.patch_scrub('+ token '+secret))
        self.assertNotIn('alice@fixture.invalid',c.patch_scrub('+ email alice@fixture.invalid'))
        self.assertTrue(c.sensitive_path('.env.production'));self.assertTrue(c.sensitive_path('private.pem'))
        self.assertFalse(c.sensitive_path('src/Eligibility.cs'))


if __name__=='__main__':unittest.main(verbosity=2)
