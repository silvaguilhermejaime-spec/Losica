from __future__ import annotations
import argparse, json, os, subprocess
from pathlib import Path

def export_override(*, seed:int, affixes:list[str], out:str|Path, iterations:int=500, num_agents:int=40, ticks_per_generation:int=50)->Path:
    payload={
      'seed':int(seed),
      'language':{'affixes':{'count':len(affixes),'explicit_list':list(affixes)},'phonology':{'rules':[]}},
      'population':{'num_agents':int(num_agents),'cache_params':{'enabled':False}},
      'simulation':{'iterations':int(iterations)},
      'ilm':{'enabled':True,'ticks_per_generation':int(ticks_per_generation)},
      'output':{'data_dir':'losica_run','overwrite_output_dir':True},
    }
    p=Path(out); p.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n'); return p

def run(repo:str|Path|None, config:str|Path, *, python:str='python'):
    value=str(repo) if repo is not None else os.environ.get('LOSICA_LANGUAGEEVOLUTION_DIR','')
    r=Path(value) if value else None
    if r is None or not (r/'run.py').exists():
        raise FileNotFoundError('set LOSICA_LANGUAGEEVOLUTION_DIR to an upstream LanguageEvolution checkout containing run.py')
    proc=subprocess.run([python,'run.py',str(Path(config).resolve())],cwd=r,text=True,capture_output=True)
    if proc.returncode!=0: raise RuntimeError(f'LanguageEvolution failed\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}')
    return proc

def inventory_output(directory:str|Path, out:str|Path|None=None):
    root=Path(directory)
    files=[]
    if root.exists():
        for p in sorted(x for x in root.rglob('*') if x.is_file()): files.append(str(p.relative_to(root)))
    obj={'schema':'losica-languageevolution-output-inventory/1','root':str(root),'files':files}
    if out: Path(out).write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
    return obj

def export_language_state(language:dict, out:str|Path, *, generations:int=10, num_agents:int=40, network:str='small_world')->Path:
    """Export a generated synchronic language as generation zero.

    Language state → per-lexeme/per-exponent representation → population and
    learner parameters → LanguageEvolution experiment JSON.
    """
    payload={
      'schema':'losica-languageevolution-experiment/1',
      'seed':int(language['seed']),
      'initial_generation':0,
      'language':{
        'lexicon':[{'lexeme_id':x['lexeme_id'],'form':x['form'],'concepts':[m['concept'] for m in x.get('concept_mappings',[])]} for x in language['lexicon']],
        'morphology':language['morphology'],
        'phonology':language['phonology'],
      },
      'population':{'num_agents':int(num_agents),'network':network,'learner_turnover':True},
      'simulation':{'generations':int(generations),'track_per_agent_lexicons':True,'track_morphological_states':True},
      'provenance':{'engine':'SakanaAI/LanguageEvolution','role':'subsequent optional evolutionary process','seed':int(language['seed'])},
    }
    p=Path(out); p.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8'); return p

def import_language_states(path:str|Path, *, experiment:dict|None=None)->dict:
    """Import per-agent outputs while preserving population variation."""
    p=Path(path)
    obj=json.loads(p.read_text(encoding='utf-8'))
    agents=obj.get('agents') or obj.get('population_states')
    if not isinstance(agents,list):
        raise ValueError('LanguageEvolution import requires an agents or population_states list')
    generation=obj.get('generation')
    if generation is None: raise ValueError('LanguageEvolution import requires an explicit generation')
    return {
      'schema':'losica-population-history-stage/1','generation':int(generation),'agents':agents,
      'population':(experiment or {}).get('population',obj.get('population',{})),
      'network':(experiment or {}).get('population',{}).get('network',obj.get('network')),
      'seed':(experiment or {}).get('seed',obj.get('seed')),
      'provenance':{'engine':'SakanaAI/LanguageEvolution','source_file':str(p),'imported_agent_count':len(agents)},
    }

def main(argv=None):
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
    e=sub.add_parser('export'); e.add_argument('--affix',action='append',default=[]); e.add_argument('--seed',type=int,default=1701); e.add_argument('--out',required=True); e.add_argument('--iterations',type=int,default=500); e.add_argument('--agents',type=int,default=40); e.add_argument('--ticks-per-generation',type=int,default=50)
    es=sub.add_parser('export-state'); es.add_argument('--language',required=True); es.add_argument('--out',required=True); es.add_argument('--generations',type=int,default=10); es.add_argument('--agents',type=int,default=40); es.add_argument('--network',default='small_world')
    ims=sub.add_parser('import-state'); ims.add_argument('--results',required=True); ims.add_argument('--experiment'); ims.add_argument('--out')
    r=sub.add_parser('run'); r.add_argument('--repo'); r.add_argument('--config',required=True); r.add_argument('--python',default='python')
    i=sub.add_parser('inventory'); i.add_argument('--directory',required=True); i.add_argument('--out')
    a=ap.parse_args(argv)
    if a.cmd=='export':
        p=export_override(seed=a.seed,affixes=a.affix,out=a.out,iterations=a.iterations,num_agents=a.agents,ticks_per_generation=a.ticks_per_generation); print(json.dumps({'out':str(p),'affix_count':len(a.affix)},sort_keys=True))
    elif a.cmd=='export-state':
        language=json.loads(Path(a.language).read_text(encoding='utf-8'))
        p=export_language_state(language,a.out,generations=a.generations,num_agents=a.agents,network=a.network); print(json.dumps({'out':str(p),'lexeme_count':len(language['lexicon'])},sort_keys=True))
    elif a.cmd=='import-state':
        experiment=json.loads(Path(a.experiment).read_text(encoding='utf-8')) if a.experiment else None
        obj=import_language_states(a.results,experiment=experiment)
        if a.out: Path(a.out).write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        print(json.dumps({'out':a.out,'generation':obj['generation'],'agent_count':len(obj['agents'])},sort_keys=True))
    elif a.cmd=='run':
        p=run(a.repo,a.config,python=a.python); print(json.dumps({'returncode':p.returncode,'stdout':p.stdout[-2000:]},sort_keys=True))
    else:
        print(json.dumps(inventory_output(a.directory,a.out),sort_keys=True))
if __name__=='__main__': main()
