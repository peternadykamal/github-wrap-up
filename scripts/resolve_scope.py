#!/usr/bin/env python3
"""Resolve explicit targets to a private frozen collector configuration using gh."""
import argparse, datetime as dt, json, os, re, shutil, subprocess
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

def gh(host,path,paginate=False):
 args=['gh','api','--hostname',host,path]
 if paginate:args+=['--paginate','--slurp']
 r=subprocess.run(args,text=True,capture_output=True)
 if r.returncode:raise ValueError('GitHub lookup failed; check gh auth status and repository/organization permissions. No tokens are needed in this command.')
 return json.loads(r.stdout)
def target(s,host):
 if s.startswith(('https://','http://')):
  u=urlsplit(s)
  if u.scheme!='https'or u.netloc!=host:raise ValueError('Profile URL must use HTTPS and the configured GitHub host')
  bits=u.path.strip('/').split('/')
  if len(bits)==2 and bits[0]=='orgs':s=bits[1]
  elif len(bits)==1:s=bits[0]
  else:raise ValueError('Expected a profile or organization URL, not a repository')
 s=s.lstrip('@')
 if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}',s):raise ValueError('Invalid GitHub account name')
 return s

def make(args,lookup=gh,now=None):
 now=now or dt.datetime.now(dt.timezone.utc);zone=ZoneInfo(args.timezone or'UTC');local=now.astimezone(zone);year=args.year or local.year
 start=dt.datetime(year,1,1,tzinfo=zone)if not args.start else dt.datetime.fromisoformat(args.start.replace('Z','+00:00'))
 end=dt.datetime(year+1,1,1,tzinfo=zone)if not args.end_exclusive else dt.datetime.fromisoformat(args.end_exclusive.replace('Z','+00:00'))
 if start.tzinfo is None:start=start.replace(tzinfo=zone)
 if end.tzinfo is None:end=end.replace(tzinfo=zone)
 end=min(end,now);start=start.astimezone(dt.timezone.utc);end=end.astimezone(dt.timezone.utc)
 if start>=end:raise ValueError('The requested interval has no elapsed time')
 requested=dt.datetime(year+1,1,1,tzinfo=zone)if not args.end_exclusive else dt.datetime.fromisoformat(args.end_exclusive.replace('Z','+00:00'))
 if requested.tzinfo is None:requested=requested.replace(tzinfo=zone)
 subjects={};orgs=set();notes=[];expand=False
 for org in args.org or[]:orgs.add(target(org,args.host))
 for value in args.targets:
  info=lookup(args.host,'user'if value.lower()=='me'else'users/'+target(value,args.host))
  if info.get('type')=='Organization':orgs.add(info['login']);expand=True
  elif info.get('type')in ['User',None]:subjects[info['login']]={'id':info['login'],'login':info['login'],'aliases':{'logins':[],'emails':[]}}
  else:raise ValueError('Targets must be human accounts or organizations')
 explicit=bool(subjects)
 if orgs and not subjects:
  expand=True
  for org in sorted(orgs):
   pages=lookup(args.host,f'orgs/{org}/members?per_page=100',True)
   for page in pages:
    for item in page:
     if item.get('type')=='Bot'or item['login'].endswith('[bot]'):continue
     subjects[item['login']]={'id':item['login'],'login':item['login'],'aliases':{'logins':[],'emails':[]}}
  notes.append('Current accessible members are roster hints. Expand to recovered historical nonbot contributor accounts; membership alone is not the historical roster.')
 if explicit and expand:notes.append('Explicit people and organization targets were combined; confirm whether organization expansion is intended before collecting.')
 return {'schemaVersion':1,'host':args.host,'window':{'start':start.isoformat(),'endExclusive':end.isoformat(),'requestedEndExclusive':requested.astimezone(dt.timezone.utc).isoformat(),'timezone':args.timezone or'UTC','timezoneConfirmed':bool(args.timezone),'dateBasis':args.date_basis,'weekendDays':args.weekend_days},'subjects':list(subjects.values()),'orgs':sorted(orgs),'repos':args.repo or[],'expandOrganizationContributors':expand,'scopeNotes':notes}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--targets',nargs='+',required=True,help='me, logins, profile URLs, or organization URLs/logins');p.add_argument('--org',action='append',help='Restrict people to this organization (repeatable)');p.add_argument('--repo',action='append');p.add_argument('--host',default='github.com');p.add_argument('--year',type=int);p.add_argument('--start');p.add_argument('--end-exclusive');p.add_argument('--timezone');p.add_argument('--date-basis',choices=['authored','committed'],default='authored');p.add_argument('--weekend-days',nargs='+',type=int,choices=range(7),default=[5,6],help='Monday=0; customize to the subject calendar');p.add_argument('--output',type=Path);a=p.parse_args()
 if not shutil.which('gh')or not shutil.which('git'):p.error('Install Git and GitHub CLI, then authenticate gh first')
 try:c=make(a)
 except(ValueError,KeyError)as e:p.error(str(e))
 if a.output:
  if a.output.exists():p.error('Refusing to overwrite an existing config; choose a new path')
  a.output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
  fd=os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'w')as f:json.dump(c,f,indent=2)
  print(json.dumps({'config':str(a.output),'subjects':[s['id']for s in c['subjects']],'organizations':c['orgs'],'window':c['window'],'notes':c['scopeNotes']}))
 else:print(json.dumps(c,indent=2))
if __name__=='__main__':main()
