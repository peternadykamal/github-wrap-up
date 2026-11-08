#!/usr/bin/env python3
"""Read-only GitHub evidence collection. Local output is private, resumable research data."""
from __future__ import annotations
import argparse
import calendar
import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
KINDS = {'commit':'commits','pull_request':'prs','issue':'issues','review':'reviews','comment':'comments','timeline':'timeline','workflow':'workflows','release':'releases','deployment':'deployments'}
LOGIN = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$')
REPO = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')


def instant(value):
    if not isinstance(value, str):
        raise ValueError('ISO timestamp required')
    value = dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if value.tzinfo is None:
        raise ValueError('Timestamps must include a timezone')
    return value.astimezone(UTC)


def iso(value):
    return value.astimezone(UTC).isoformat().replace('+00:00','Z')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def private_dir(path):
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    path.chmod(0o700)


def save(path, value, jsonl=False):
    path = Path(path)
    private_dir(path.parent)
    fd, name = tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            if jsonl:
                for row in value:
                    f.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
            else:
                json.dump(value,f,ensure_ascii=False,indent=2)
                f.write('\n')
        os.chmod(name,0o600)
        os.replace(name,path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else default


def scrub(value):
    text = str(value)
    text = re.sub(r'https?://[^\s/@]+:[^\s/@]+@','https://[credential redacted]@',text)
    text = re.sub(r'(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|AIza[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{20,})','[credential redacted]',text)
    text = re.sub(r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)?','[token redacted]',text)
    return text


def patch_scrub(value):
    text = scrub(value)
    text = re.sub(r'[\w.+%\-]+@[\w.\-]+\.[A-Za-z]{2,}','[email redacted]',text)
    text = re.sub(r'(?<!\w)\+?\d[\d ()-]{8,}\d(?!\w)','[identifier redacted]',text)
    lines=[]
    for line in text.splitlines():
        if re.search(r'BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY',line):
            return '[Private key material omitted]'
        if re.search(r'(?:password|passwd|client.?secret|api.?key|access.?token|refresh.?token|private.?key|connection.?string)\s*["\x27]?\s*[:=]\s*["\x27][^"\x27]{4,}["\x27]',line,re.I):
            line = line[:1]+' [credential-bearing assignment redacted]'
        lines.append(line)
    return '\n'.join(lines)


def sensitive_path(path):
    return bool(re.search(r'(^|/)(\.env(?:\..*)?|[^/]*(?:credentials|secrets?)[^/]*|id_rsa|id_ed25519)$|\.(?:pem|p12|pfx|key|tfvars)$',path,re.I))


class CommandError(RuntimeError):
    pass


def command(args, timeout=180, binary=False, env=None):
    child_env = os.environ.copy()
    child_env.update({'GH_PROMPT_DISABLED':'1','GIT_TERMINAL_PROMPT':'0','GIT_OPTIONAL_LOCKS':'0'})
    if env:
        child_env.update(env)
    result = subprocess.run(args,capture_output=True,timeout=timeout,env=child_env)
    if result.returncode:
        message = result.stderr.decode('utf-8','replace') or result.stdout.decode('utf-8','replace')
        raise CommandError(scrub(message[-1500:]))
    return result.stdout if binary else result.stdout.decode('utf-8','replace')


def preflight(host='github.com'):
    if not re.fullmatch(r'[A-Za-z0-9.-]+(?::\d+)?',host):
        raise ValueError('Invalid GitHub hostname')
    missing = [x for x in ['gh','git'] if not shutil.which(x)]
    if missing:
        return {'ok':False,'missing':missing,'action':'Install the missing prerequisites before collecting.'}
    versions={x:command([x,'--version']).splitlines()[0] for x in ['gh','git']}
    try:
        viewer=json.loads(command(['gh','api','--hostname',host,'user']))
    except (CommandError,subprocess.TimeoutExpired,json.JSONDecodeError):
        return {'ok':False,'versions':versions,'host':host,'action':'Authenticate gh for this host, then check organization/SSO authorization. Do not paste tokens into prompts.'}
    return {'ok':True,'versions':versions,'host':host,'viewer':{'login':viewer['login'],'id':viewer['id'],'url':viewer['html_url']}}


class API:
    def __init__(self, root, host='github.com', refresh=False):
        self.root=Path(root);self.host=host;self.refresh=refresh
        self.calls=0;self.hits=0;self.failures=[];self.pages=[];self.requests=[]
        private_dir(self.root)

    def get(self, endpoint, params=None, graphql=None):
        if endpoint.startswith(('http:','https:','/')):
            raise ValueError('Use a relative GitHub API endpoint')
        url=endpoint
        if params:
            url += ('&' if '?' in url else '?')+urllib.parse.urlencode(params)
        key=digest({'host':self.host,'endpoint':url,'graphql':graphql})
        cache=self.root/(key+'.json')
        self.requests.append({'endpoint':url,'cacheFile':str(cache.relative_to(self.root.parent)),'graphql':bool(graphql)})
        if cache.exists() and not self.refresh:
            self.hits+=1
            return read(cache)['response']
        args=['gh','api','--hostname',self.host,'--method','POST' if graphql else 'GET',url]
        if graphql:
            args += ['-f','query='+graphql]
        last=None
        for attempt in range(4):
            try:
                self.calls+=1
                result=json.loads(command(args))
                if isinstance(result,dict) and result.get('errors'):
                    raise CommandError('GraphQL returned errors: '+scrub(str(result['errors']))[:800])
                save(cache,{'retrievedAt':iso(dt.datetime.now(UTC)),'endpoint':url,'response':result})
                return result
            except (CommandError,subprocess.TimeoutExpired,json.JSONDecodeError) as e:
                last=e
                text=str(e).lower()
                retry=any(s in text for s in ['rate limit','429','502','503','504','timed out','timeout'])
                if not retry or attempt==3:
                    break
                time.sleep(min(2**attempt,8))
        self.failures.append({'endpoint':url.split('?')[0],'error':scrub(str(last))[:800]})
        raise CommandError(scrub(str(last)))

    def paginate(self, endpoint, params=None, key=None, stop=None, cap=None):
        rows=[];page=1;params=dict(params or {})
        while True:
            p={**params,'per_page':100,'page':page}
            result=self.get(endpoint,p)
            batch=result.get(key,[]) if key else result
            if not isinstance(batch,list):
                raise CommandError('Unexpected paginated response at '+endpoint)
            rows.extend(batch)
            if isinstance(result,dict) and result.get('incomplete_results'):
                raise CommandError('GitHub search reports incomplete_results at '+endpoint)
            self.pages.append({'endpoint':endpoint,'page':page,'count':len(batch)})
            if cap and len(rows)>=cap:
                if len(batch)==100:
                    raise CommandError('Endpoint result ceiling reached at '+endpoint)
                break
            if len(batch)<100 or (stop and stop(batch)):
                break
            page+=1
        return rows

    def search(self, endpoint, query, start, end, qualifier='created'):
        """Partition capped searches down to seconds, never silently accept 1,000 results."""
        if end<=start:
            return []
        value=f'{qualifier}:{iso(start)}..{iso(end-dt.timedelta(microseconds=1))}'
        q=query+' '+value
        first=self.get(endpoint,{'q':q,'per_page':100,'page':1})
        if first.get('incomplete_results'):
            raise CommandError('GitHub search returned incomplete_results')
        total=first.get('total_count',0)
        if total>1000:
            if (end-start).total_seconds()<=1:
                raise CommandError('Search cap exceeded in one-second partition')
            middle=start+(end-start)/2
            rows=self.search(endpoint,query,start,middle,qualifier)+self.search(endpoint,query,middle,end,qualifier)
            return list({r.get('id',r.get('sha',digest(r))):r for r in rows}.values())
        rows=list(first.get('items',[]))
        for page in range(2,(total+99)//100+1):
            result=self.get(endpoint,{'q':q,'per_page':100,'page':page})
            if result.get('incomplete_results'):
                raise CommandError('GitHub search returned incomplete_results')
            rows.extend(result.get('items',[]))
        return rows


def normalize_config(config, previous=None):
    cfg=json.loads(json.dumps(config)); cfg.setdefault('schemaVersion',1)
    if cfg['schemaVersion']!=1:
        raise ValueError('Only config schemaVersion 1 is supported')
    cfg.setdefault('host','github.com')
    if not re.fullmatch(r'[A-Za-z0-9.-]+(?::\d+)?',cfg['host']):
        raise ValueError('Invalid host')
    window=cfg.setdefault('window',{})
    if previous and previous.get('inputConfigHash')==digest(config):
        for k,v in previous['window'].items():
            window.setdefault(k,v)
    window.setdefault('timezone','UTC')
    zone=ZoneInfo(window['timezone'])
    now=dt.datetime.now(UTC)
    year=now.astimezone(zone).year
    window.setdefault('start',iso(dt.datetime(year,1,1,tzinfo=zone)))
    window.setdefault('endExclusive',iso(now))
    window.setdefault('dateBasis','authored')
    if instant(window['start'])>=instant(window['endExclusive']):
        raise ValueError('window.start must precede window.endExclusive')
    if window['dateBasis'] not in ['authored','committed']:
        raise ValueError('dateBasis must be authored or committed')
    for key in ['repos','orgs','subjects']:
        cfg.setdefault(key,[])
    for repo in cfg['repos']:
        if not REPO.fullmatch(repo) or any(x in ['.','..'] for x in repo.split('/')):
            raise ValueError('Invalid repository: '+repo)
    for org in cfg['orgs']:
        if not LOGIN.fullmatch(org):
            raise ValueError('Invalid organization login')
    for subject in cfg['subjects']:
        if isinstance(subject,str):
            raise ValueError('Subjects must be objects with id and login')
        subject.setdefault('id',subject['login'])
        if not LOGIN.fullmatch(subject['id']) or not LOGIN.fullmatch(subject['login']):
            raise ValueError('Subject IDs/logins must be GitHub usernames; resolve URLs before collection')
        aliases=subject.setdefault('aliases',{})
        aliases.setdefault('logins',[]);aliases.setdefault('emails',[])
        if not all(LOGIN.fullmatch(a) for a in aliases['logins']):
            raise ValueError('Invalid alias login')
    ids=[s['id'].lower() for s in cfg['subjects']]
    if len(ids)!=len(set(ids)):
        raise ValueError('Duplicate canonical subjects')
    owner={}
    for subject in cfg['subjects']:
        for login in [subject['id'],subject['login'],*subject['aliases']['logins']]:
            key=login.lower()
            if key in owner and owner[key]!=subject['id']:
                raise ValueError('Alias belongs to multiple subjects: '+login)
            owner[key]=subject['id']
    cfg.setdefault('patches',{})
    cfg['patches'].setdefault('maxFiles',12);cfg['patches'].setdefault('maxChars',80000)
    cfg['patches'].setdefault('perFileChars',10000)
    if any(not isinstance(v,int) or v<0 for v in cfg['patches'].values()):
        raise ValueError('Patch limits must be nonnegative integers')
    return cfg


def months_in_window(window):
    zone=ZoneInfo(window['timezone'])
    a=instant(window['start']).astimezone(zone);b=(instant(window['endExclusive'])-dt.timedelta(microseconds=1)).astimezone(zone)
    y,m=a.year,a.month;result=[]
    while (y,m)<=(b.year,b.month):
        result.append(f'{y:04d}-{m:02d}')
        y,m=(y+1,1) if m==12 else (y,m+1)
    # For a default calendar-year report expose the remaining months as not-yet-in-window.
    if a.month==1 and a.day==1 and a.year==b.year:
        result=[f'{a.year:04d}-{i:02d}' for i in range(1,13)]
    return result


class Collector:
    def __init__(self, config, output, refresh=False):
        self.root=Path(output).resolve();private_dir(self.root)
        self.previous=read(self.root/'manifest.json',{})
        self.input_hash=digest(config)
        self.config=normalize_config(config,self.previous if not refresh else None)
        if self.config.get('expandOrganizationContributors') and self.previous.get('inputConfigHash')==self.input_hash:
            existing={p['id'].lower() for p in self.config['subjects']}
            for p in self.previous.get('subjects',[]):
                if p.get('autoDiscovered') and p['id'].lower() not in existing:
                    self.config['subjects'].append(p);existing.add(p['id'].lower())
        self.config_hash=digest(self.config)
        if self.previous and self.previous.get('inputConfigHash')!=self.input_hash:
            raise ValueError('Output belongs to a different configuration; use a new output directory')
        self.window=self.config['window'];self.start=instant(self.window['start']);self.end=instant(self.window['endExclusive'])
        self.snapshot=iso(dt.datetime.now(UTC)) if refresh else self.previous.get('snapshotAt',iso(dt.datetime.now(UTC)))
        self.api=API(self.root/'cache',self.config['host'],refresh)
        self.refresh=refresh;self.errors=[];self.discovery_notes=[];self.repo_results=[]
        self.update_aliases()

    def update_aliases(self):
        self.logins={};self.emails={}
        for p in self.config['subjects']:
            for login in [p['id'],p['login'],*p['aliases']['logins']]:
                self.logins[login.lower()]=p['id']
            for email in p['aliases']['emails']:
                key=email.lower()
                if key in self.emails and self.emails[key]!=p['id']:
                    raise ValueError('Identity email belongs to multiple subjects')
                self.emails[key]=p['id']

    def canonical(self, login):
        return self.logins.get(str(login).lower(),login) if login else None

    def identity(self, source_login, email):
        if source_login:
            result=self.canonical(source_login)
            return result, ('configured-account-alias' if result!=source_login else 'github-account-association')
        if email and email.lower() in self.emails:
            return self.emails[email.lower()],'configured-exact-email-alias'
        return None,'unresolved; never inferred from display name'

    def expand_subjects(self, name, logins):
        if not self.config.get('expandOrganizationContributors'):
            return
        if name.split('/')[0].lower() not in {x.lower() for x in self.config['orgs']}:
            return
        existing={p['id'].lower() for p in self.config['subjects']}
        for login in sorted(set(filter(None,logins)),key=str.lower):
            if login.lower() in existing or not LOGIN.fullmatch(login) or login.lower() in {'ghost','github-actions','dependabot','renovate'}:
                continue
            self.config['subjects'].append({'id':login,'login':login,'aliases':{'logins':[],'emails':[]},'autoDiscovered':True,'discoveredFrom':name})
            existing.add(login.lower())
        self.update_aliases()
        self.config_hash=digest(self.config)

    def inside(self, value):
        return bool(value) and self.start<=instant(value)<self.end

    def safe(self, stage, fn, default=None, repo=None):
        try:
            return fn()
        except (CommandError,ValueError,OSError,subprocess.TimeoutExpired) as e:
            self.errors.append({'repo':repo,'stage':stage,'error':scrub(str(e))[:1000]})
            return default

    def discover(self):
        repos={};scoped=bool(self.config['orgs'] or self.config['repos'])
        for name in self.config['repos']:
            obj=self.safe('explicit-repository',lambda n=name:self.api.get('repos/'+n),repo=name)
            if obj:repos[obj['full_name']]=obj
        for org in self.config['orgs']:
            rows=self.safe('organization-inventory',lambda o=org:self.api.paginate(f'orgs/{o}/repos',{'type':'all'}),[],repo=org)
            for obj in rows:repos[obj['full_name']]=obj
        if not self.config['subjects'] and self.config['orgs']:
            roster={}
            for org in self.config['orgs']:
                rows=self.safe('organization-roster',lambda o=org:self.api.paginate(f'orgs/{o}/members'),[],repo=org)
                for p in rows:roster[p['login'].lower()]=p['login']
            self.config['subjects']=[{'id':login,'login':login,'aliases':{'logins':[],'emails':[]}} for login in sorted(roster.values(),key=str.lower)]
            self.discovery_notes.append('Organization roster is currently API-visible membership; private or former members and external contributors may require explicit subjects.')
            self.update_aliases()
        if not self.config['subjects'] and not (self.config['orgs'] and self.config.get('expandOrganizationContributors')):
            raise ValueError('No target subjects resolved; supply users or an accessible organization roster')
        viewer=self.safe('viewer-identity',lambda:self.api.get('user'),{}) or {}
        if not scoped and any(viewer.get('login','').lower() in [p['login'].lower(),*[x.lower()for x in p['aliases']['logins']]]for p in self.config['subjects']):
            accessible=self.safe('authenticated-repository-inventory',lambda:self.api.paginate('user/repos',{'visibility':'all','affiliation':'owner,collaborator,organization_member'}),[])
            for obj in accessible:repos[obj['full_name']]=obj
        for p in self.config['subjects']:
            found=self.safe('subject-profile',lambda p=p:self.api.get('users/'+p['login']))
            if found:
                p['githubId']=found['id'];p['displayName']=found.get('name') or found['login']
            if scoped:
                continue
            for login in [p['login'],*p['aliases']['logins']]:
                own=self.safe('owned-repositories',lambda l=login:self.api.paginate(f'users/{l}/repos',{'type':'owner'}),[])
                for obj in own:repos[obj['full_name']]=obj
                for query in [f'author:{login}',f'commenter:{login}',f'is:pr reviewed-by:{login}']:
                    rows=self.safe('repository-discovery-search',lambda q=query:self.api.search('search/issues',q+' created:<'+iso(self.end),self.start,dt.datetime.now(UTC),'updated'),[])
                    for row in rows:
                        name=row.get('repository_url','').split('/repos/')[-1]
                        if REPO.fullmatch(name):repos.setdefault(name,None)
                rows=self.safe('repository-discovery-commits',lambda l=login:self.api.search('search/commits',f'author:{l}',self.start,self.end,'author-date'),[])
                for row in rows:
                    obj=row.get('repository')
                    if obj:repos.setdefault(obj['full_name'],None)
                q='query { user(login:'+json.dumps(login)+') { contributionsCollection(from:'+json.dumps(iso(self.start))+', to:'+json.dumps(iso(self.end-dt.timedelta(microseconds=1)))+') { commitContributionsByRepository(maxRepositories:100) { repository { nameWithOwner } } } } }'
                hints=self.safe('contribution-discovery',lambda q=q:self.api.get('graphql',graphql=q),{}) or {}
                for row in (((hints.get('data') or {}).get('user') or {}).get('contributionsCollection') or {}).get('commitContributionsByRepository',[]):
                    repos.setdefault(row['repository']['nameWithOwner'],None)
        if not scoped:
            self.discovery_notes.append('Unscoped user discovery is a lower bound: private inaccessible repositories, unindexed branches, deleted repositories, older co-authorship and unavailable search results may be absent. Contribution results are hints, not the annual source of truth.')
        self.discovery_notes.append('Repository scope includes only the authenticated account’s accessible inventory; lack of activity is not evidence of lack of work.')
        for name in list(repos):
            if repos[name] is None:
                obj=self.safe('discovered-repository',lambda n=name:self.api.get('repos/'+n),repo=name)
                if obj:repos[name]=obj
                else:del repos[name]
        return repos

    def git(self, path, *args, binary=False, timeout=240):
        return command(['git','-c','core.hooksPath='+os.devnull,'-c','core.fsmonitor=false','-c','credential.helper=','-c','credential.helper=!gh auth git-credential','-c','credential.interactive=false','-C',str(path),*args],timeout,binary)

    def mirror(self, name):
        path=self.root/'mirrors'/name.replace('/','__')
        if not path.exists():
            private_dir(path.parent)
            url=f'https://{self.config["host"]}/{name}.git'
            command(['git','-c','core.hooksPath='+os.devnull,'-c','core.fsmonitor=false','-c','credential.helper=','-c','credential.helper=!gh auth git-credential','clone','--bare','--no-hardlinks',url,str(path)],timeout=1200)
            path.chmod(0o700)
        else:
            # This directory is collector-owned; never touch the user’s working checkout.
            self.git(path,'fetch','--prune','origin','+refs/heads/*:refs/heads/*','+refs/tags/*:refs/tags/*',timeout=1200)
        self.safe('historical-pr-refs',lambda:self.git(path,'fetch','origin','+refs/pull/*/head:refs/yearbook/pr/*',timeout=1200),repo=name)
        shallow=self.git(path,'rev-parse','--is-shallow-repository').strip()
        if shallow=='true':
            self.git(path,'fetch','--unshallow','origin',timeout=1200)
        refs=[]
        for row in self.git(path,'for-each-ref','--format=%(refname)%00%(objectname)').splitlines():
            ref,sha=row.split('\0');refs.append({'ref':ref,'sha':sha})
        return path,refs

    def git_commits(self, path):
        fmt='%H%x00%P%x00%an%x00%ae%x00%aI%x00%cn%x00%ce%x00%cI%x00%B'
        if not self.git(path,'for-each-ref').strip():
            return []
        raw=self.git(path,'log','--all','-z','--format='+fmt,binary=True,timeout=600)
        parts=raw.decode('utf-8','replace').split('\0')
        if parts and parts[-1]=='':parts.pop()
        if len(parts)%9:
            raise CommandError('Unexpected NUL-delimited Git record shape')
        rows=[]
        for i in range(0,len(parts),9):
            sha,parents,an,ae,ad,cn,ce,cd,body=parts[i:i+9]
            date=ad if self.window['dateBasis']=='authored' else cd
            if self.inside(date):
                rows.append({'sha':sha,'parents':parents.split(),'authorName':an,'authorEmail':ae,'authoredAt':ad,'committerName':cn,'committerEmail':ce,'committedAt':cd,'message':body.strip()})
        return rows

    def enrich_identities(self, name, rows):
        owner,repo=name.split('/')
        result={}
        for offset in range(0,len(rows),40):
            batch=rows[offset:offset+40]
            nodes=' '.join('c'+str(i)+': object(oid:'+json.dumps(c['sha'])+'){ ... on Commit { oid additions deletions author { user { login } } committer { user { login } } authors(first:100) { nodes { email user { login } } pageInfo { hasNextPage } } } }' for i,c in enumerate(batch))
            q='query { repository(owner:'+json.dumps(owner)+',name:'+json.dumps(repo)+'){ '+nodes+' } }'
            data=self.safe('commit-account-association',lambda q=q:self.api.get('graphql',graphql=q),{},repo=name) or {}
            for obj in ((data.get('data') or {}).get('repository') or {}).values():
                if obj:result[obj['oid']]=obj
            missing=[r['sha']for r in batch if r['sha']not in result]
            if missing:self.errors.append({'repo':name,'stage':'missing-commit-account-objects','error':f'{len(missing)} commit objects were unavailable for identity enrichment; affected identities may be unresolved.','shas':missing})
        return result

    def footprint(self, path, sha):
        raw=self.git(path,'diff-tree','--root','--no-commit-id','--no-renames','--numstat','-r','-z',sha,binary=True)
        files=[]
        for part in raw.split(b'\0'):
            if not part:continue
            a,d,name=part.split(b'\t',2)
            files.append({'path':name.decode('utf-8','replace'),'additions':int(a) if a.isdigit() else None,'deletions':int(d) if d.isdigit() else None})
        return files

    def changes(self, name, path, sha, dest):
        files=self.footprint(path,sha);limits=self.config['patches'];retained=[];budget=limits['maxChars'];skipped=0
        for f in files:
            if len(retained)>=limits['maxFiles'] or budget<=0:break
            if sensitive_path(f['path']):
                skipped+=1;continue
            raw=self.git(path,'show','--format=','--root','--no-ext-diff','--no-textconv','--no-renames',sha,'--',f['path'])
            if not raw.strip():continue
            red=patch_scrub(raw)
            maxchars=min(limits['perFileChars'],budget)
            retained.append({**f,'patch':red[:maxchars],'truncated':len(red)>maxchars})
            budget-=len(retained[-1]['patch'])
        out={'schemaVersion':1,'repo':name,'sha':sha,'paths':[f['path'] for f in files],'files':files,'patches':retained,'collected':True,'inspected':False,'limits':limits,'sensitiveFilesSkipped':skipped,'patchCoverage':'bounded excerpts; file footprint complete','truncated':len(retained)<len(files) or any(p['truncated'] for p in retained)}
        save(dest,out)
        return out

    def record(self, name, kind, key, actor, occurred, title='', body='', url=None, data=None):
        return {'id':f'{self.config["host"]}/{name}#{kind}:{key}','kind':kind,'repo':name,'actor':self.canonical(actor),'occurredAt':occurred,'url':url or f'https://{self.config["host"]}/{name}','title':title or '', 'body':body or '', 'data':data or {}}

    def pull_requests(self, name):
        stop=lambda batch:bool(batch) and instant(batch[-1]['updated_at'])<self.start
        listed=self.api.paginate(f'repos/{name}/pulls',{'state':'all','sort':'updated','direction':'desc'},stop=stop)
        records=[]
        for summary in listed:
            if instant(summary['created_at'])>=self.end or instant(summary['updated_at'])<self.start:continue
            number=summary['number'];p=self.safe('pr-details',lambda n=number:self.api.get(f'repos/{name}/pulls/{n}'),summary,repo=name)
            author=(p.get('user') or {}).get('login');merged=p.get('merged_at');base=(p.get('base') or {}).get('ref');head=(p.get('head') or {}).get('ref')
            files=self.safe('pr-files',lambda n=number:self.api.paginate(f'repos/{name}/pulls/{n}/files',cap=3000),[],repo=name)
            commits=self.safe('pr-commit-links',lambda n=number:self.api.paginate(f'repos/{name}/pulls/{n}/commits',cap=250),[],repo=name)
            if p.get('commits')is not None and p['commits']>len(commits):
                self.errors.append({'repo':name,'stage':'pr-commit-links','error':f'PR #{number} reports {p["commits"]} commits but endpoint retained {len(commits)}; Git PR refs provide history separately.'})
            rec=self.record(name,'pull_request',number,author,p['created_at'],p['title'],p.get('body'),p['html_url'],{'number':number,'createdAt':p['created_at'],'updatedAt':p['updated_at'],'mergedAt':merged,'closedAt':p.get('closed_at'),'state':'MERGED' if merged else str(p.get('state','')).upper(),'draft':p.get('draft',False),'author':self.canonical(author),'mergedBy':self.canonical((p.get('merged_by') or {}).get('login')),'base':base,'head':head,'headSha':(p.get('head') or {}).get('sha'),'baseSha':(p.get('base') or {}).get('sha'),'paths':[f['filename'] for f in files],'additions':p.get('additions'),'deletions':p.get('deletions'),'changedFiles':p.get('changed_files'),'commits':[c['sha'] for c in commits],'labels':[x['name'] for x in p.get('labels',[])],'assignees':[x['login'] for x in p.get('assignees',[])],'milestone':p.get('milestone'),'sourceAccount':author,'inspected':False})
            records.append(rec)
            reviews=self.safe('pr-reviews',lambda n=number:self.api.paginate(f'repos/{name}/pulls/{n}/reviews'),[],repo=name)
            for rv in reviews:
                date=rv.get('submitted_at')
                if date and self.inside(date):
                    records.append(self.record(name,'review',rv['id'],(rv.get('user')or{}).get('login'),date,'Review of '+p['title'],rv.get('body'),rv.get('html_url'),{'prNumber':number,'state':rv['state'],'commitSha':rv.get('commit_id'),'inspected':False}))
            records.extend(self.comments(name,number,True))
            timeline=self.safe('pr-timeline',lambda n=number:self.api.paginate(f'repos/{name}/issues/{n}/timeline'),[],repo=name)
            records.extend(self.timeline(name,number,timeline))
        return records

    def comments(self, name, number, is_pr):
        result=[]
        endpoints=[(f'repos/{name}/issues/{number}/comments','conversation')]
        if is_pr:endpoints.append((f'repos/{name}/pulls/{number}/comments','inline-review'))
        for endpoint,channel in endpoints:
            comments=self.safe('comments',lambda e=endpoint:self.api.paginate(e),[],repo=name)
            for c in comments:
                created=c.get('created_at');updated=c.get('updated_at');occurred=created if self.inside(created) else updated if self.inside(updated) else None
                if not occurred:continue
                result.append(self.record(name,'comment',channel+':'+str(c['id']),(c.get('user')or{}).get('login'),occurred,'Comment on '+('PR' if is_pr else 'issue')+f' #{number}',c.get('body'),c.get('html_url'),{'prNumber':number if is_pr else None,'issueNumber':None if is_pr else number,'channel':channel,'createdAt':created,'updatedAt':updated,'activityBasis':'created' if occurred==created else 'edited','path':c.get('path'),'line':c.get('line'),'reviewId':c.get('pull_request_review_id'),'inspected':False}))
        return result

    def timeline(self, name, number, timeline, is_pr=True):
        result=[]
        for ev in timeline:
            date=ev.get('created_at') or ev.get('submitted_at') or ev.get('committed_at')
            if not date or not self.inside(date):continue
            actor=(ev.get('actor') or ev.get('user') or {}).get('login')
            result.append(self.record(name,'timeline',str(ev.get('id') or digest(ev)),actor,date,ev.get('event','timeline event'),ev.get('body'),ev.get('html_url') or f'https://{self.config["host"]}/{name}/'+('pull' if is_pr else 'issues')+f'/{number}',{'prNumber':number if is_pr else None,'issueNumber':None if is_pr else number,'event':ev.get('event'),'commitSha':ev.get('commit_id'),'label':ev.get('label'),'assignee':(ev.get('assignee')or{}).get('login'),'reviewRequester':(ev.get('review_requester')or{}).get('login'),'requestedReviewer':(ev.get('requested_reviewer')or{}).get('login'),'inspected':False}))
        return result

    def issues(self, name):
        rows=self.api.paginate(f'repos/{name}/issues',{'state':'all','since':iso(self.start),'sort':'updated','direction':'desc'})
        result=[]
        for issue in rows:
            if issue.get('pull_request') or instant(issue['created_at'])>=self.end:continue
            n=issue['number'];author=(issue.get('user')or{}).get('login')
            result.append(self.record(name,'issue',n,author,issue['created_at'],issue['title'],issue.get('body'),issue['html_url'],{'number':n,'createdAt':issue['created_at'],'updatedAt':issue['updated_at'],'closedAt':issue.get('closed_at'),'state':issue['state'].upper(),'labels':[x['name'] for x in issue.get('labels',[])],'assignees':[x['login'] for x in issue.get('assignees',[])],'milestone':issue.get('milestone'),'inspected':False}))
            result.extend(self.comments(name,n,False))
            events=self.safe('issue-timeline',lambda n=n:self.api.paginate(f'repos/{name}/issues/{n}/timeline'),[],repo=name)
            result.extend(self.timeline(name,n,events,False))
        return result

    def optional_metadata(self, name):
        records=[]
        releases=self.safe('releases',lambda:self.api.paginate(f'repos/{name}/releases'),[],repo=name)
        for r in releases:
            date=r.get('published_at') or r['created_at']
            if self.inside(date):records.append(self.record(name,'release',r['id'],(r.get('author')or{}).get('login'),date,r.get('name') or r.get('tag_name'),r.get('body'),r.get('html_url'),{'tag':r['tag_name'],'publishedAt':r.get('published_at'),'targetSha':r.get('target_commitish'),'draft':r.get('draft'),'prerelease':r.get('prerelease'),'assets':[{'name':x['name'],'size':x['size'],'downloadCount':x['download_count']} for x in r.get('assets',[])],'inspected':False}))
        params={'created':f'{iso(self.start)}..{iso(self.end-dt.timedelta(microseconds=1))}'}
        runs=self.safe('workflow-runs',lambda:self.api.paginate(f'repos/{name}/actions/runs',params,key='workflow_runs',cap=1000),[],repo=name)
        for r in runs:
            date=r['created_at']
            if self.inside(date):records.append(self.record(name,'workflow',str(r['id'])+':'+str(r.get('run_attempt',1)),(r.get('actor')or{}).get('login'),date,r.get('name'),'',r.get('html_url'),{'headSha':r.get('head_sha'),'targetSha':r.get('head_sha'),'branch':r.get('head_branch'),'event':r.get('event'),'status':r.get('status'),'conclusion':r.get('conclusion'),'startedAt':r.get('run_started_at'),'updatedAt':r.get('updated_at'),'attempt':r.get('run_attempt',1),'inspected':False}))
        deployments=self.safe('deployments',lambda:self.api.paginate(f'repos/{name}/deployments'),[],repo=name)
        for d in deployments:
            if not self.inside(d['created_at']):continue
            statuses=self.safe('deployment-statuses',lambda d=d:self.api.paginate(f'repos/{name}/deployments/{d["id"]}/statuses'),[],repo=name)
            records.append(self.record(name,'deployment',d['id'],(d.get('creator')or{}).get('login'),d['created_at'],d.get('description') or d.get('environment','Deployment'),'',f'https://{self.config["host"]}/{name}/deployments',{'sha':d.get('sha'),'targetSha':d.get('sha'),'status':statuses[0]['state']if statuses else None,'statusObservedAt':statuses[0]['created_at']if statuses else None,'environment':d.get('environment'),'productionEnvironment':d.get('production_environment'),'statuses':[{'state':s['state'],'createdAt':s['created_at'],'environmentUrl':s.get('environment_url')}for s in statuses],'coverageNote':'Historical deployment statuses may have expired. A deployment record or workflow success alone does not prove production correctness.','inspected':False}))
        return records

    def collect_repo(self, name, metadata):
        dest=self.root/'repos'/name.replace('/','__');private_dir(dest)
        marker=read(dest/'coverage.json',{})
        if marker.get('configHash')==self.config_hash and marker.get('status')=='complete' and (dest/'records.jsonl').exists() and not self.refresh:
            return marker
        start_errors=len(self.errors);start_requests=len(self.api.requests);records=[];refs=[];save(dest/'metadata.json',metadata);private_dir(dest/'changes')
        mirrored=self.safe('git-history',lambda:self.mirror(name),repo=name)
        if mirrored:
            path,refs=mirrored
            rows=self.safe('git-commit-metadata',lambda:self.git_commits(path),[],repo=name)
            enriched=self.enrich_identities(name,rows)
            self.expand_subjects(name,[((v.get('author')or{}).get('user')or{}).get('login') for v in enriched.values()]+[((a.get('user')or{}).get('login'))for v in enriched.values()for a in (v.get('authors')or{}).get('nodes',[])])
            for c in rows:
                rich=enriched.get(c['sha'],{});source=((rich.get('author')or{}).get('user')or{}).get('login')
                actor,attribution=self.identity(source,c['authorEmail']);sha=c['sha'];merge=len(c['parents'])>1
                data={**c,'sha':sha,'merge':merge,'sourceAccount':source,'attribution':attribution,'paths':[],'additions':rich.get('additions'),'deletions':rich.get('deletions'),'detail':None,'inspected':False}
                coauthors=[]
                for co in (rich.get('authors')or{}).get('nodes',[]):
                    login=((co.get('user')or{}).get('login'));resolved,_=self.identity(login,co.get('email'))
                    if resolved and resolved!=actor:coauthors.append(resolved)
                data['coauthors']=list(dict.fromkeys(coauthors))
                if (rich.get('authors')or{}).get('pageInfo',{}).get('hasNextPage'):
                    self.errors.append({'repo':name,'stage':'coauthor-pagination','error':'More than 100 authors; coauthor list is partial for '+sha})
                if (actor in self.logins.values() or any(a in self.logins.values() for a in coauthors)) and not merge:
                    change=self.safe('source-excerpt',lambda sha=sha:self.changes(name,path,sha,dest/'changes'/f'{sha}.json'),repo=name)
                    if change:
                        data['paths']=change['paths']
                        if data['additions'] is None:data['additions']=sum(f['additions'] or 0 for f in change['files'])
                        if data['deletions'] is None:data['deletions']=sum(f['deletions'] or 0 for f in change['files'])
                        data['detail']=str((dest/'changes'/f'{sha}.json').relative_to(self.root))
                        data['collection']={'metadata':True,'completePaths':True,'boundedPatchExcerpts':True,'inspected':False}
                date=c['authoredAt'] if self.window['dateBasis']=='authored' else c['committedAt']
                records.append(self.record(name,'commit',sha,actor,date,c['message'].splitlines()[0] if c['message'] else '',c['message'],f'https://{self.config["host"]}/{name}/commit/{sha}',data))
        save(dest/'refs.json',refs)
        records.extend(self.safe('pull-requests',lambda:self.pull_requests(name),[],repo=name))
        records.extend(self.safe('issues',lambda:self.issues(name),[],repo=name))
        records.extend(self.optional_metadata(name))
        self.expand_subjects(name,[r['actor']for r in records if r['kind'] in {'commit','pull_request','review','issue','comment','timeline'} and (self.inside(r['occurredAt'])or(r['kind']=='pull_request'and self.inside(r['data'].get('mergedAt'))))])
        records=list({r['id']:r for r in records}.values());records.sort(key=lambda r:(r.get('occurredAt')or'',r['id']))
        save(dest/'records.jsonl',records,True)
        for kind,filename in KINDS.items():save(dest/(filename+'.jsonl'),[r for r in records if r['kind']==kind],True)
        problems=self.errors[start_errors:]
        coverage={'schemaVersion':1,'repo':name,'status':'partial' if problems else 'complete','configHash':self.config_hash,'snapshotAt':self.snapshot,'window':self.window,'recordCounts':dict(collections.Counter(r['kind']for r in records)),'refs':len(refs),'errors':problems,'meaning':'Complete means all requested implemented collection dimensions returned without detected collection errors; it does not prove unavailable/deleted history exists or that source excerpts were inspected.','sourceInspection':'collected, not inspected','bounds':{'sourcePatchExcerpts':self.config['patches'],'prCommitsEndpoint':250,'prFilesEndpoint':3000,'workflowFilteredResults':1000}}
        coverage['unresolvedCommits']=sum(r['kind']=='commit' and r['actor']is None for r in records)
        save(dest/'api-index.json',self.api.requests[start_requests:])
        save(dest/'coverage.json',coverage)
        self.write_perspectives(name,dest,records,coverage)
        return coverage

    def roles(self, record, pid):
        roles=[];kind=record['kind'];data=record['data']
        if record['actor']==pid:
            roles.append({'commit':'author','pull_request':'pr-author','review':'reviewer','issue':'issue-author','comment':'commenter','timeline':'timeline-actor','workflow':'workflow-actor','release':'release-author','deployment':'deployment-creator'}[kind])
        if kind=='commit' and pid in data.get('coauthors',[]):roles.append('coauthor')
        if kind=='pull_request' and data.get('mergedBy')==pid:roles.append('merger')
        return roles

    def perspective_dates(self, record, roles):
        data=record['data'];dates=[]
        if self.inside(record['occurredAt']) and (record['kind']!='pull_request' or 'pr-author'in roles):dates.append(record['occurredAt'])
        if record['kind']=='pull_request':
            if 'pr-author'in roles:
                dates.extend(v for v in [data.get('mergedAt'),data.get('closedAt')]if self.inside(v))
            if 'merger'in roles and self.inside(data.get('mergedAt')):dates.append(data['mergedAt'])
        if record['kind']=='issue' and 'issue-author'in roles and self.inside(data.get('closedAt')):dates.append(data['closedAt'])
        return list(dict.fromkeys(dates))

    def write_perspectives(self, name, shared, records, coverage):
        zone=ZoneInfo(self.window['timezone']);subjects=self.config['subjects']
        for p in subjects:
            pid=p['id'];dest=self.root/'users'/pid/'repos'/name.replace('/','__')
            buckets={m:[] for m in months_in_window(self.window)};count=0
            for record in records:
                roles=self.roles(record,pid)
                if not roles:continue
                for month in {instant(t).astimezone(zone).strftime('%Y-%m')for t in self.perspective_dates(record,roles)}:
                    if month in buckets:buckets[month].append({'recordId':record['id'],'roles':roles})
                count+=1
            if not any(buckets.values()) and name not in self.config['repos']:continue
            private_dir(dest)
            save(dest/'index.json',{'schemaVersion':1,'subjectId':pid,'repo':name,'sharedRepo':str(shared.relative_to(self.root)),'recordCount':count,'coverage':coverage['status'],'months':list(buckets)})
            for month,rows in buckets.items():
                year,mon=map(int,month.split('-'));a=dt.datetime(year,mon,1,tzinfo=zone);y,m=(year+1,1)if mon==12 else(year,mon+1);b=dt.datetime(y,m,1,tzinfo=zone)
                intersects=a.astimezone(UTC)<self.end and b.astimezone(UTC)>self.start
                state=('observed' if rows else 'no-observed-activity')if intersects and coverage['status']=='complete' else 'partial'if intersects else 'outside-reporting-window'
                save(dest/'months'/month/'records.jsonl',rows,True)
                save(dest/'months'/month/'index.json',{'month':month,'subjectId':pid,'repo':name,'state':state,'recordCount':len(rows),'coverage':coverage['status'],'sharedRecords':str((shared/'records.jsonl').relative_to(self.root))})

    def manifest(self, status='collecting'):
        value={'schemaVersion':1,'inputConfigHash':self.input_hash,'configHash':self.config_hash,'snapshotAt':self.snapshot,'window':self.window,'subjects':self.config['subjects'],'host':self.config['host'],'orgs':self.config['orgs'],'repos':[r['repo']for r in self.repo_results],'config':self.config,'toolVersions':getattr(self,'tool_versions',None),'coverage':{'status':status,'complete':status=='complete','notes':self.discovery_notes,'errors':self.errors,'repositoryResults':self.repo_results,'apiRequests':self.api.calls,'cacheHits':self.api.hits,'sourceInspection':'collection only; research agents must log inspections separately','notCollected':['GitHub Discussions and Projects field history','organization audit logs','historical star/fork/follower snapshots','expired Actions logs/artifacts','deleted or unreachable Git objects not retained by fetched references'],'generatedAt':iso(dt.datetime.now(UTC))}}
        for subject in self.config['subjects']:
            folder=self.root/'users'/subject['id'];private_dir(folder)
            indexes=sorted(str(p.relative_to(self.root))for p in (folder/'repos').glob('*/index.json'))
            save(folder/'index.json',{'schemaVersion':1,'subject':subject,'window':self.window,'repositoryIndexes':indexes,'coverage':status})
        save(self.root/'manifest.json',value)
        return value

    def run(self):
        repos=self.discover();self.config_hash=digest(self.config);self.manifest()
        for name in sorted(repos,key=str.lower):
            result=self.collect_repo(name,repos[name]);self.repo_results.append(result)
            self.manifest()
            print(json.dumps({'repo':name,'status':result['status'],'records':result['recordCounts']},ensure_ascii=False),flush=True)
        status='partial'if self.errors or any(r['status']!='complete'for r in self.repo_results)else'complete'
        # Unscoped discovery is explicitly best-effort even when each known repository is complete.
        if not(self.config['orgs']or self.config['repos']):status='partial'
        final=self.manifest(status)
        save(self.root/'coverage.json',final['coverage'])
        save(self.root/'api-pages.json',self.api.pages)
        return final


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight',action='store_true')
    parser.add_argument('--host',default='github.com')
    parser.add_argument('--config',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--refresh',action='store_true',help='Refresh API responses and mirrors for the configured window; use a new directory for a changed configuration')
    args=parser.parse_args()
    if args.preflight:
        result=preflight(args.host);print(json.dumps(result,indent=2));return 0 if result['ok']else 2
    if not args.config or not args.output:parser.error('--config and --output are required for collection')
    config=read(args.config)
    if not isinstance(config,dict):parser.error('Config must be a JSON object')
    check=preflight(config.get('host','github.com'))
    if not check['ok']:
        print(json.dumps(check,indent=2));return 2
    try:
        collector=Collector(config,args.output,args.refresh);collector.tool_versions=check['versions'];result=collector.run()
    except (ValueError,OSError,CommandError,subprocess.TimeoutExpired) as e:
        print(json.dumps({'ok':False,'error':scrub(str(e))[:1200]}),file=sys.stderr);return 2
    print(json.dumps({'ok':True,'output':str(collector.root),'coverage':result['coverage']['status'],'repositories':len(result['repos']),'subjects':[p['id']for p in result['subjects']]}))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
