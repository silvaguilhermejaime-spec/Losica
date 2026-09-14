from __future__ import annotations
import argparse, json, os, shlex, shutil
from pathlib import Path
from .sound_change_external import load_integration_config

def check(path='config/integrations.json'):
    cfg=load_integration_config(path)
    sc=cfg['sound_change']; sc_cmd=shlex.split(sc.get('command','lexurgy'))[0]
    le_dir=os.environ.get(cfg['population_evolution'].get('environment_variable','LOSICA_LANGUAGEEVOLUTION_DIR'),'')
    qcmd=os.environ.get(cfg['vocal_retrieval'].get('environment_variable','LOSICA_QBV_COMMAND'),'')
    return {
      'schema':'losica-integration-check/1',
      'vocal_retrieval':{'configured':bool(qcmd),'command':qcmd or None},
      'population_evolution':{'configured':bool(le_dir and (Path(le_dir)/cfg['population_evolution'].get('entrypoint','run.py')).exists()),'repo':le_dir or None},
      'sound_change':{'configured':shutil.which(sc_cmd) is not None,'command':sc_cmd,'rules':sc.get('rules')},
    }

def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument('--integrations',default='config/integrations.json'); ap.add_argument('--out')
    a=ap.parse_args(argv); obj=check(a.integrations); text=json.dumps(obj,indent=2,sort_keys=True)
    if a.out: Path(a.out).write_text(text+'\n')
    print(text)
if __name__=='__main__': main()
