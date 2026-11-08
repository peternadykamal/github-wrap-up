"""Offline fictional runtime fixture, never a production model recommendation."""
import datetime as dt
from build_facts import save

def write(run):
 stamp=dt.datetime.now(dt.timezone.utc).isoformat();entries=[];assessments=[]
 for tier in ['efficient','balanced','deep']:
  mid='fictional-future-'+tier
  entries.append({'id':mid,'available':True,'toolCalling':True,'supportedEfforts':['quick','normal','deliberate']})
  assessments.append({'modelId':mid,'selectionClass':tier,'roles':['researcher','coordinator','challenge'],'effortByIntent':{'economical':'quick','moderate':'normal','deep':'deliberate'},'rationale':'Fictional '+tier+' candidate for deterministic offline tests','guidance':[{'kind':'runtime-metadata','identifier':'fixture descriptor','description':'Fictional '+tier+' capability','checkedAt':stamp}],'validation':{'status':'guidance-only'}})
 catalog={'schemaVersion':1,'capturedAt':stamp,'source':{'kind':'tool-metadata','identifier':'offline fixture; no runtime requests'},'controls':{'modelOverride':True,'effortOverride':True,'freshContextRequired':True},'parent':{'agentId':'root','confirmedByRuntime':False},'models':entries}
 assessment={'schemaVersion':1,'models':assessments}
 save(run/'analysis/runtime-models.json',catalog);save(run/'analysis/model-assessments.json',assessment);return catalog,assessment
