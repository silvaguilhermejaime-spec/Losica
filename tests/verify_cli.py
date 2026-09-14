from pathlib import Path
import csv, json, subprocess, sys, tempfile, os
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as td:
    out=Path(td)/'example.tsv'
    cmd=[sys.executable,'-m','losica_engine.cli','--stimuli','data/stimuli.example.jsonl','--categories','data/categories.example.json','--relations','config/iconic_relations.example.json','--lexical-processes','config/lexical_processes.example.json','--lexicon','data/lexicon.example.tsv','--syllables','1','--matched-only','--out',str(out)]
    r=subprocess.run(cmd,cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT)},capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    with out.open() as f:
        rows=list(csv.DictReader(f,delimiter='\t'))
    assert rows
    for row in rows:
        for match in json.loads(row['matched_relations']):
            p=match['predicate_prevalence']; assert 0<p['predicate_count']<=p['category_size']
    diag=json.loads(Path(str(out)+'.diagnostics.json').read_text())
    assert diag['output_schema_version']=='4.0'
print('verify_cli: PASS')
