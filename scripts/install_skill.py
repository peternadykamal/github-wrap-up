#!/usr/bin/env python3
"""Install this portable skill into a supplied harness skills directory."""
from __future__ import annotations
import argparse,json,shutil,tempfile
from pathlib import Path

NAME='github-year-in-review'
FOLDERS={'agents','references','scripts','assets'}
FILES={'SKILL.md','README.md','INSTALL.md','.gitignore'}
EXCLUDED={'.git','__pycache__','node_modules','dist','.venv','.DS_Store'}


def distribution_files(source):
 source=Path(source).resolve()
 if not(source/'SKILL.md').is_file():raise ValueError('Source must contain SKILL.md')
 candidates=[source/name for name in sorted(FILES)if(source/name).is_file()]
 for name in sorted(FOLDERS):
  folder=source/name
  if folder.is_dir():candidates.extend(folder.rglob('*'))
 for p in sorted(candidates):
  relative=p.relative_to(source)
  if not p.is_file()or any(part in EXCLUDED for part in relative.parts)or p.suffix in ['.pyc','.pyo']:continue
  if relative.parts[0]in FOLDERS or str(relative)in FILES:yield p,relative


def install(source,skills_dir,link=False,dry_run=False):
 source=Path(source).resolve();skills_dir=Path(skills_dir).expanduser().absolute();target=skills_dir/NAME
 if target.exists()or target.is_symlink():
  if target.resolve()==source:return {'status':'already-linked','target':str(target),'source':str(source)}
  raise ValueError('Destination already exists; installation never overwrites another copy')
 if target.resolve().is_relative_to(source):raise ValueError('Install outside the source repository')
 selected=list(distribution_files(source));result={'status':'planned'if dry_run else'installed','target':str(target),'method':'symlink'if link else'copy','files':len(selected)}
 if dry_run:return result
 skills_dir.mkdir(parents=True,exist_ok=True)
 if link:target.symlink_to(source,target_is_directory=True)
 else:
  with tempfile.TemporaryDirectory(prefix='.skill-install-',dir=skills_dir)as folder:
   staged=Path(folder)/NAME;staged.mkdir()
   for p,relative in selected:
    q=staged/relative;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
   staged.rename(target)
 return result


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--skills-dir',required=True,type=Path);p.add_argument('--link',action='store_true');p.add_argument('--dry-run',action='store_true');a=p.parse_args()
 try:result=install(Path(__file__).resolve().parent.parent,a.skills_dir,a.link,a.dry_run)
 except(ValueError,OSError)as e:p.exit(1,json.dumps({'error':str(e)})+'\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
