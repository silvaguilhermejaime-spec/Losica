import csv, json, sys, tempfile, unittest
from pathlib import Path
import numpy as np, soundfile as sf
from losica_engine.corpus_vocalsketch import build_vocalsketch_index
from losica_engine.external_retrieval import load_ranking, run_external_backend
from losica_engine.transcription import transcribe_index
from losica_engine.word_generation import syllabify_tokens, candidates_from_ranking, append_accepted_candidate
from losica_engine.config import load_phonology
from losica_engine.lexical_history import load_lexicon
ROOT=Path(__file__).resolve().parents[1]; CFG=load_phonology(ROOT/'config/preproto.json')
def tone(path,hz,fs=8000):
    t=np.arange(fs)/fs; sf.write(path,np.sin(2*np.pi*hz*t),fs)
class EmpiricalPipelineTests(unittest.TestCase):
    def fixture_dataset(self,td):
        td=Path(td); (td/'sound_recordings').mkdir(); (td/'vocal_imitations'/'included').mkdir(parents=True)
        fields=['id','filename','stimulus_type','included','draft','training','participant_id','satisfaction','sound_label','sound_label_id','sound_recording','sound_recording_id','audio_concept_subset','participants_sound_recording_description','participants_sound_recording_description_confidence','description_match']
        rows=[]
        for i,hz in enumerate([220,440]):
            ref=f'ref_{i}.wav'; tone(td/'sound_recordings'/ref,hz); name=f'im_{i}.wav'; tone(td/'vocal_imitations'/'included'/name,hz)
            r=dict.fromkeys(fields,''); r.update({'id':f'I{i}','filename':name,'stimulus_type':'sound recording','included':'True','draft':'False','training':'False','participant_id':f'S{i}','sound_recording':ref,'sound_recording_id':f'R{i}'}); rows.append(r)
        with (td/'vocal_imitations.csv').open('w',newline='',encoding='utf-8') as f: w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
        return td
    def test_vocalsketch_pairs(self):
        with tempfile.TemporaryDirectory() as d:
            idx=build_vocalsketch_index(self.fixture_dataset(d)); self.assertEqual(len(idx['pairs']),2)
    def test_external_ranking_contract(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); q=d/'q.wav'; tone(q,220); helper=d/'rank.py'; out=d/'ranking.json'
            helper.write_text("import json,sys\na=sys.argv; out=a[a.index('--out')+1]\njson.dump({'schema':'losica-vocal-retrieval-ranking/1','backend':{'engine':'fixture'},'ranking':[{'imitation_id':'I1','speaker_id':'S1','score':0.8}]},open(out,'w'))\n")
            obj=run_external_backend(q,command=[sys.executable,str(helper)],out_path=out); self.assertEqual(obj['ranking'][0]['imitation_id'],'I1')
    def test_transcription_to_candidates(self):
        ranking=load_ranking(ROOT/'data/imitation_ranking.example.json')
        out=candidates_from_ranking(ranking,transcriptions_path=ROOT/'data/imitation_transcriptions.example.json',phonology_path=ROOT/'config/preproto.json')
        self.assertTrue(out['candidates']); self.assertEqual(out['candidates'][0]['preproto_form'],'ma'); self.assertEqual(out['candidates'][0]['speaker_count'],2)
    def test_acceptance_enters_lexicon(self):
        ranking=load_ranking(ROOT/'data/imitation_ranking.example.json'); out=candidates_from_ranking(ranking,transcriptions_path=ROOT/'data/imitation_transcriptions.example.json',phonology_path=ROOT/'config/preproto.json')
        with tempfile.TemporaryDirectory() as d:
            cp=Path(d)/'c.json'; cp.write_text(json.dumps(out)); lex=Path(d)/'lex.tsv'; append_accepted_candidate(cp,index=0,lexicon_path=lex,lexeme_id='L_TEST',category_id='C_TEST',provenance='fixture')
            self.assertEqual(load_lexicon(lex,CFG)['L_TEST'].root.form,out['candidates'][0]['preproto_form'])
    def test_syllabification(self):
        self.assertIn(('ma',),syllabify_tokens(['m','a'],CFG)); self.assertEqual(syllabify_tokens(['m','m'],CFG),[])
        forms=syllabify_tokens(['u','k','k','u','k'],CFG)
        self.assertTrue(forms); self.assertTrue(all(''.join(x)=='ukuk' for x in forms))
if __name__=='__main__': unittest.main()
