import json, sys, tempfile, unittest
from pathlib import Path
from losica_engine.config import load_phonology
from losica_engine.language_generation import generate_language
from losica_engine.phonology import syllabify_surface
from losica_engine.languageevolution_adapter import export_override

ROOT=Path(__file__).resolve().parents[1]
CFG=load_phonology(ROOT/'config/preproto.json')

class LanguageGenerationTests(unittest.TestCase):
    def generate(self,**kw):
        return generate_language(
            lexicon_path=ROOT/'data/lexicon.example.tsv',
            usage_path=ROOT/'data/usage_events.example.jsonl',
            pathway_registry_path=ROOT/'config/grammaticalization_registry.json',
            phonology_path=ROOT/'config/preproto.json',
            **kw,
        )

    def test_reproducible_and_real_lexemes(self):
        a=self.generate(); b=self.generate(); self.assertEqual(a,b)
        ids={x['lexeme_id'] for x in a['lexicon']}
        self.assertEqual(ids,{'L_EX_BASE','L_HOST_A','L_HOST_B','L_HOST_C','L_MARK_A','L_MARK_B','L_MARK_C'})

    def test_history_produces_affix_and_clitic_states(self):
        obj=self.generate()
        states={(x['marker_lexeme_id'],x['function_id']):x for x in obj['marker_states']}
        self.assertEqual(states[('L_MARK_A','F001')]['attachment'],'affix')
        self.assertEqual(states[('L_MARK_B','F002')]['attachment'],'affix')
        self.assertEqual(states[('L_MARK_C','F003')]['attachment'],'clitic')

    def test_order_comes_from_observed_positions(self):
        obj=self.generate()
        pos=[x['position'] for x in obj['morphotactics']['positions']]
        self.assertEqual(pos,[-2,1])
        forms={x['preproto_form'] for x in obj['generated_forms']}
        self.assertIn('ru.kan',forms)

    def test_host_conditioned_allomorphs_are_attested(self):
        obj=self.generate()
        a=next(x for x in obj['productive_affixes'] if x['marker_lexeme_id']=='L_MARK_A')
        self.assertEqual(a['source_lexical_form'],'na')
        self.assertEqual(a['current_form'],'n')
        self.assertEqual(a['current_allomorphs'],['n','na'])
        rows={(x['host_lexeme_id'],tuple(x['function_ids'])):x for x in obj['generated_forms']}
        self.assertEqual(rows[('L_HOST_A',('F001',))]['marker_forms'],['n'])
        self.assertEqual(rows[('L_HOST_A',('F001',))]['preproto_form'],'kan')
        self.assertEqual(rows[('L_HOST_C',('F001',))]['marker_forms'],['na'])
        self.assertEqual(rows[('L_HOST_C',('F001',))]['preproto_form'],'tuk.na')

    def test_every_generated_preproto_form_is_legal(self):
        obj=self.generate()
        for row in obj['generated_forms']:
            surface=row['preproto_form'].replace('.','')
            self.assertTrue(syllabify_surface(surface,CFG))
        illegal={'rka','rtuk','tukn','rkan','rtukn'}
        self.assertFalse(illegal & {x['preproto_form'].replace('.','') for x in obj['generated_forms']})

    def test_illegal_current_affix_event_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            usage=d/'usage.jsonl'
            rows=[]
            for line in (ROOT/'data/usage_events.example.jsonl').read_text().splitlines():
                r=json.loads(line)
                if r['event_id']=='E007': r['marker_form']='n'
                rows.append(json.dumps(r))
            usage.write_text('\n'.join(rows)+'\n')
            with self.assertRaisesRegex(ValueError,'E007.*phonotactically illegal'):
                generate_language(
                    lexicon_path=ROOT/'data/lexicon.example.tsv',
                    usage_path=usage,
                    pathway_registry_path=ROOT/'config/grammaticalization_registry.json',
                    phonology_path=ROOT/'config/preproto.json',
                )

    def test_external_sound_change_contract(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); rules=d/'r.txt'; rules.write_text('fixture')
            helper=d/'sca.py'; helper.write_text("import sys\nwords=sys.argv[-1]\nfor x in open(words): print(x.strip()+'X')\n")
            obj=self.generate(sound_rules_path=rules,sound_command=[sys.executable,str(helper),'{rules}','{words}'],sound_contract='generic')
            self.assertTrue(all(x['historical_form'].endswith('X') for x in obj['generated_forms']))

    def test_languageevolution_export_uses_current_affixes(self):
        obj=self.generate(); aff=[x['current_form'] for x in obj['productive_affixes']]
        with tempfile.TemporaryDirectory() as d:
            p=export_override(seed=1,affixes=aff,out=Path(d)/'o.json')
            x=json.loads(p.read_text())
            self.assertEqual(x['language']['affixes']['explicit_list'],aff)

if __name__=='__main__': unittest.main()
