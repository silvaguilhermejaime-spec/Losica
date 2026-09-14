import json, subprocess, sys, tempfile, unittest
from pathlib import Path
from losica_engine.config import load_phonology, load_transition
from losica_engine.phonology import Root, estimate_root_count, generate_roots
from losica_engine.legacy_history_v018 import proto_forms, historical_branch_count
from losica_engine.project_data import load_stimuli, load_categories, measurement_catalog
from losica_engine.relations import load_relations, matched_relations, predicate_matches

ROOT=Path(__file__).resolve().parents[1]
CFG=load_phonology(ROOT/'config/preproto.json'); TR=load_transition(ROOT/'config/transition.json')

def measurement(q,v,u='1'):
    return {'quantity_id':q,'value':v,'unit':u,'source':'test','model':'TEST','status':'test'}

def stimulus(sid, measurements):
    return {'id':sid,'measurements':measurements}

class ReleaseTests(unittest.TestCase):
    def test_phonology_and_history_unchanged(self):
        self.assertEqual(CFG.legal_syllable_count,189)
        self.assertEqual(estimate_root_count(CFG,[1]),189)
        root=Root(('a','i','u'),0)
        self.assertGreaterEqual(historical_branch_count(root,CFG,TR),1)
        self.assertTrue(proto_forms(root,CFG,TR))

    def test_root_count_excludes_degeminated_duplicate_representations(self):
        self.assertEqual(len(list(generate_roots(CFG, [2]))), estimate_root_count(CFG, [2]))

    def test_example_quantitative_inputs(self):
        s=load_stimuli(ROOT/'data/stimuli.example.jsonl')
        self.assertEqual(set(s),{'S001','S002'})
        cat=measurement_catalog(s)
        self.assertEqual(cat['event_rate_s_1'],'s-1')
        r=load_relations(ROOT/'config/iconic_relations.example.json',CFG,cat)
        self.assertEqual(r[0].stimulus_predicate.quantity_id,'event_rate_s_1')

    def test_semantic_observation_schema_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'s.jsonl'; p.write_text('{"id":"S","observations":["hot"]}\n')
            with self.assertRaises(ValueError): load_stimuli(p)

    def test_duplicate_measurement_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'s.jsonl'; p.write_text(json.dumps(stimulus('S',[measurement('q',1),measurement('q',2)]))+'\n')
            with self.assertRaises(ValueError): load_stimuli(p)

    def test_nonfinite_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'s.jsonl'; p.write_text('{"id":"S","measurements":[{"quantity_id":"q","value":NaN,"unit":"1","source":"x","model":"X","status":"x"}]}\n')
            with self.assertRaises(ValueError): load_stimuli(p)

    def test_unit_consistency_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'s.jsonl'
            p.write_text(json.dumps(stimulus('A',[measurement('q',1,'m')]))+'\n'+json.dumps(stimulus('B',[measurement('q',2,'s')]))+'\n')
            s=load_stimuli(p)
            with self.assertRaises(ValueError): measurement_catalog(s)

    def test_relation_unknown_quantity_and_wrong_unit_rejected(self):
        cat={'q':'m'}
        base={'relations':[{'id':'R','stimulus_predicate':{'quantity_id':'missing','unit':'m','operator':'ge','value':1},'candidate_property':{'type':'syllable_count','values':[1]},'provenance':{'status':'test','source':'test'}}]}
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'r.json'; p.write_text(json.dumps(base))
            with self.assertRaises(ValueError): load_relations(p,CFG,cat)
            base['relations'][0]['stimulus_predicate']['quantity_id']='q'; base['relations'][0]['stimulus_predicate']['unit']='s'; p.write_text(json.dumps(base))
            with self.assertRaises(ValueError): load_relations(p,CFG,cat)

    def test_predicate_prevalence_is_quantitative(self):
        relations=load_relations(ROOT/'config/iconic_relations.example.json',CFG,{'event_rate_s_1':'s-1','spectral_centroid_Hz':'Hz'})
        members=[{'measurements':{'event_rate_s_1':{'value':8.0,'unit':'s-1'}}},{'measurements':{'event_rate_s_1':{'value':2.0,'unit':'s-1'}}}]
        root=Root(('ka','ti','ka','ti'),0)
        matches=matched_relations(root,CFG,members,relations,morphological_process='reduplication')
        r=next(x for x in matches if x.relation_id=='EX_R001')
        self.assertEqual(r.serialize()['predicate_prevalence']['fraction'],'1/2')

    def test_vector_requires_component_index(self):
        from losica_engine.schema import StimulusPredicate
        s={'measurements':{'q':{'value':(1.0,3.0),'unit':'m'}}}
        self.assertFalse(predicate_matches(s,StimulusPredicate('q','m','gt',value=2)))
        self.assertTrue(predicate_matches(s,StimulusPredicate('q','m','gt',value=2,component_index=1)))

    def test_between_inclusive(self):
        from losica_engine.schema import StimulusPredicate
        s={'measurements':{'q':{'value':2.0,'unit':'m'}}}
        self.assertTrue(predicate_matches(s,StimulusPredicate('q','m','between',lower=2,upper=3)))

    def test_world_handoff_shape_is_accepted(self):
        row={'id':'OI00001','region_id':3,'source_process':'CLIMATE_REGION_ORBITAL_BIN','temporal_support':{'orbital_bin':0},'measurements':[measurement('air_temperature_K',292.9,'K')],'model':'OBS1','status':'derived_handoff'}
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'s.jsonl';p.write_text(json.dumps(row)+'\n');loaded=load_stimuli(p)
            self.assertEqual(loaded['OI00001']['measurements']['air_temperature_K']['value'],292.9)

    def test_cli_emits_schema4(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'out.tsv'
            cmd=[sys.executable,'-m','losica_engine.cli','--stimuli',str(ROOT/'data/stimuli.example.jsonl'),'--categories',str(ROOT/'data/categories.example.json'),'--relations',str(ROOT/'config/iconic_relations.example.json'),'--lexical-processes',str(ROOT/'config/lexical_processes.example.json'),'--lexicon',str(ROOT/'data/lexicon.example.tsv'),'--syllables','1','--matched-only','--out',str(out)]
            r=subprocess.run(cmd,cwd=ROOT,env={**__import__('os').environ,'PYTHONPATH':str(ROOT)},capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            text=out.read_text();self.assertIn('\t4.0\t' if False else 'schema_version',text)
            diag=json.loads(Path(str(out)+'.diagnostics.json').read_text())
            self.assertEqual(diag['output_schema_version'],'4.0')
            registry={x['relation_id']:x for x in diag['relation_premises']}
            self.assertIn('stimulus_predicate',registry['EX_R001'])

if __name__=='__main__': unittest.main()
