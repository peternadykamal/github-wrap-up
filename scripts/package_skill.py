#!/usr/bin/env python3
"""Package only the reusable skill, excluding Git history, caches and run data."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from install_skill import NAME,distribution_files


def package(source,output):
 source=Path(source).resolve();output=Path(output).resolve()
 if output.exists():raise ValueError('Output exists; choose a new package path')
 files=list(distribution_files(source));output.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED)as z:
  for p,relative in files:z.write(p,Path(NAME)/relative)
 return {'path':str(output),'files':len(files),'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
 try:result=package(Path(__file__).resolve().parent.parent,a.output)
 except(ValueError,OSError)as e:p.exit(1,json.dumps({'error':str(e)})+'\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
