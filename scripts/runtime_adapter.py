"""Render provider-neutral launch choices into captured harness-native JSON fields.

This module never launches a process, calls an agent, or writes harness settings.
Schema 1 is the frozen legacy Codex contract; schema 2 declares its own adapter.
"""
from __future__ import annotations
import copy


def need(ok,message):
 if not ok:raise ValueError(message)


def check_path(path):
 need(isinstance(path,list)and path and all(isinstance(p,str)and p and not any(x in p for x in ['\x00','\n','\r'])for p in path),'Adapter parameter paths must be nonempty arrays of field names')


def put(value,path,item):
 check_path(path);node=value
 for part in path[:-1]:
  node=node.setdefault(part,{})
  need(isinstance(node,dict),'Adapter parameter paths collide')
 need(path[-1]not in node,'Adapter parameter overlaps a fixed or selected field')
 node[path[-1]]=copy.deepcopy(item)


def check(catalog):
 if catalog['schemaVersion']==1:return
 a=catalog.get('adapter',{});controls=catalog['controls']
 need(a.get('kind')in ['tool-arguments','agent-configuration']and isinstance(a.get('interface'),str)and a['interface'],'Declare the actual harness agent tool/configuration interface')
 need(isinstance(a.get('fixedArguments',{}),dict),'Adapter fixedArguments must be a JSON object')
 if controls['modelOverride']:check_path(a.get('modelPath'))
 if controls['effortOverride']:check_path(a.get('effortPath'))
 context=a.get('freshContext',{})
 need(context.get('strategy')in ['native','parameter'],'Describe how this harness starts a fresh context')
 if context['strategy']=='parameter':
  check_path(context.get('path'));need('value'in context,'Fresh-context parameter needs its actual native value')
 # Render with sentinels to catch overlapping paths, even on an empty catalog.
 probe=copy.deepcopy(a.get('fixedArguments',{}))
 if controls['modelOverride']:put(probe,a['modelPath'],'adapter-model-probe')
 if controls['effortOverride']:put(probe,a['effortPath'],'adapter-effort-probe')
 if context['strategy']=='parameter':put(probe,context['path'],context['value'])


def dispatch(catalog,model,effort):
 controls=catalog['controls']
 if catalog['schemaVersion']==1:
  result={'model':model['id'],'reasoning_effort':effort}
  if controls['freshContextRequired']:result['fork_turns']='none'
  return result
 a=catalog['adapter'];arguments=copy.deepcopy(a.get('fixedArguments',{}));put(arguments,a['modelPath'],model['id'])
 if controls['effortOverride']:
  need(effort is not None,'Explicit effort requires an advertised value')
  # Labels can map to numbers or structured native controls, e.g. a thinking budget.
  native=model.get('effortValues',{}).get(effort,effort);put(arguments,a['effortPath'],native)
 context=a['freshContext']
 if context['strategy']=='parameter':put(arguments,context['path'],context['value'])
 return {'kind':a['kind'],'interface':a['interface'],'arguments':arguments,'context':'fresh-native'if context['strategy']=='native'else'fresh-parameter'}
