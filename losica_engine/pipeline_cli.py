from __future__ import annotations
import argparse, json, os
from pathlib import Path
from .corpus_vocalsketch import build_vocalsketch_index, write_index
from .external_retrieval import load_ranking, run_external_backend
from .transcription import transcribe_index
from .word_generation import candidates_from_ranking
from .world_audio import world_acoustic_to_wav

def main(argv=None):
    ap=argparse.ArgumentParser(description='Losica empirical vocal-imitation word pipeline')
    ap.add_argument('--dataset-root',required=True); ap.add_argument('--query',required=True); ap.add_argument('--workdir',required=True)
    ap.add_argument('--phonology',default='config/preproto.json')
    ap.add_argument('--transcription-mode',choices=['allosaurus','command'],required=True); ap.add_argument('--transcriber-command',nargs='+'); ap.add_argument('--allosaurus-model',default='uni2005'); ap.add_argument('--allosaurus-lang',default='ipa')
    rg=ap.add_mutually_exclusive_group(required=True); rg.add_argument('--ranking'); rg.add_argument('--qbv-command',default=os.environ.get('LOSICA_QBV_COMMAND'))
    ap.add_argument('--qbv-extra-arg',action='append',default=[]); ap.add_argument('--top-imitations',type=int,default=64)
    a=ap.parse_args(argv); w=Path(a.workdir); w.mkdir(parents=True,exist_ok=True)
    index_path=w/'paired_index.json'; index=build_vocalsketch_index(a.dataset_root,verify_files=True); write_index(index,index_path)
    if not index['pairs']: raise ValueError('dataset directory contains zero eligible paired recordings')
    trans_path=w/'transcriptions.json'; trans=transcribe_index(index_path,phonology_path=a.phonology,out=trans_path,mode=a.transcription_mode,command_template=a.transcriber_command,allosaurus_model=a.allosaurus_model,allosaurus_lang=a.allosaurus_lang)
    query=Path(a.query)
    if query.suffix.lower()=='.json': query=world_acoustic_to_wav(query,w/'world_query.wav')
    if a.ranking: ranking=load_ranking(a.ranking); ranking_path=Path(a.ranking)
    else:
        if not a.qbv_command: raise ValueError('QBV bridge command required via --qbv-command or LOSICA_QBV_COMMAND')
        ranking_path=w/'imitation_ranking.json'; ranking=run_external_backend(query,command=a.qbv_command,out_path=ranking_path,extra_args=['--index',str(index_path),*a.qbv_extra_arg])
    candidates=candidates_from_ranking(ranking,transcriptions_path=trans_path,phonology_path=a.phonology,top_imitation_count=a.top_imitations)
    candidates['query_waveform']=str(query); cand_path=w/'word_candidates.json'; cand_path.write_text(json.dumps(candidates,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    result={'schema':'losica-end-to-end-run/2','pair_count':len(index['pairs']),'accepted_transcription_count':sum(r['status']=='accepted' for r in trans['records']),'retrieval_backend':ranking.get('backend',{}),'word_candidate_count':len(candidates['candidates']),'artifacts':{'index':str(index_path),'transcriptions':str(trans_path),'ranking':str(ranking_path),'candidates':str(cand_path)}}
    (w/'run_summary.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n'); print(json.dumps(result,sort_keys=True))
if __name__=='__main__': main()
