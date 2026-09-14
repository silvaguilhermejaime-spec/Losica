from pathlib import Path
import json, tempfile
from losica_engine.config import load_phonology, load_transition
from losica_engine.phonology import Root, estimate_root_count
from losica_engine.legacy_history_v018 import proto_forms, historical_branch_count
from losica_engine.project_data import load_stimuli, load_categories, measurement_catalog
from losica_engine.relations import load_relations, matched_relations
from losica_engine.full_language import generate_complete_language
from losica_engine.validation_v021 import validate_complete_language

ROOT=Path(__file__).resolve().parents[1]
CFG=load_phonology(ROOT/'config/preproto.json'); TR=load_transition(ROOT/'config/transition.json')

def run():
    assert CFG.legal_syllable_count==189
    assert estimate_root_count(CFG,[1])==189
    assert historical_branch_count(Root(('a','i','u'),0),CFG,TR)>=1
    stimuli=load_stimuli(ROOT/'data/stimuli.example.jsonl')
    catalog=measurement_catalog(stimuli)
    assert catalog['event_rate_s_1']=='s-1'
    relations=load_relations(ROOT/'config/iconic_relations.example.json',CFG,catalog)
    synthetic=[
        {'id':'A','measurements':{'event_rate_s_1':{'value':8.0,'unit':'s-1'}}},
        {'id':'B','measurements':{'event_rate_s_1':{'value':2.0,'unit':'s-1'}}},
    ]
    root=Root(('ka','ti','ka','ti'),0)
    matches=matched_relations(root,CFG,synthetic,relations,morphological_process='reduplication')
    m=next(x for x in matches if x.relation_id=='EX_R001')
    assert (m.predicate_count,m.category_size)==(1,2)
    assert m.serialize()['predicate_prevalence']['fraction']=='1/2'
    primitive=matched_relations(root,CFG,synthetic,relations,morphological_process=None)
    assert not any(x.relation_id=='EX_R001' for x in primitive)
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'bad.jsonl'
        p.write_text('{"id":"S","observations":["cold"]}\n')
        try: load_stimuli(p)
        except ValueError: pass
        else: raise AssertionError('semantic observation input must be rejected')
    language=generate_complete_language(seed=19020,vocabulary_scale='core')
    result=validate_complete_language(language)
    assert result['status']=='PASS'
    print(json.dumps({'selfcheck':'PASS',**result},sort_keys=True))
if __name__=='__main__': run()
