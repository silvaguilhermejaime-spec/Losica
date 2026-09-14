import json, tempfile, unittest
from pathlib import Path
import soundfile as sf
from losica_engine.world_audio import world_acoustic_to_wav

class WorldAudioTests(unittest.TestCase):
    def test_acoustic_path_to_wav(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); src=td/'q.json'; out=td/'q.wav'
            src.write_text(json.dumps({'schema':'losica-acoustic-path/3','propagated_waveform':{'schema':'propagated-sound/2','sample_rate_hz':16000,'pressure_Pa':[0.0,0.1,-0.1,0.0]}}))
            world_acoustic_to_wav(src,out)
            x,fs=sf.read(out,dtype='float32')
            self.assertEqual(fs,16000); self.assertEqual(len(x),4)
            self.assertAlmostEqual(float(x[1]),0.1,places=5)

if __name__=='__main__': unittest.main()
