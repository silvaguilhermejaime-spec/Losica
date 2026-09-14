import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError

from losica_engine import vocalsketch_fetch as vf

CSV = b'''id,filename,stimulus_type,included,draft,training,participant_id,sound_recording\n1,im1.wav,sound recording,True,False,False,P1,ref1.wav\n2,im2.wav,sound recording,True,False,False,P2,missing.wav\n'''
CSV2 = b'''id,filename,stimulus_type,included,draft,training,participant_id,sound_recording\n3,im3.wav,sound recording,True,False,False,P3,ref1.wav\n'''

class FetchTests(unittest.TestCase):
    def test_unavailable_referent_is_recorded_and_valid_pairs_continue(self):
        def fake(url):
            if url.endswith('vocal_imitations.csv'):
                return CSV
            if url.endswith('vocal_imitaitons_set2.csv'):
                return CSV2
            if url.endswith('/sound_recordings/missing.wav'):
                raise HTTPError(url, 404, 'missing', None, None)
            return b'RIFFfixture'
        with TemporaryDirectory() as td, patch.object(vf, 'fetch_bytes', side_effect=fake):
            out = vf.fetch_subset(td, max_referents=0, imitations_per_referent=0)
            self.assertEqual(out['downloaded_referent_count'], 1)
            self.assertEqual(out['pair_count'], 2)
            self.assertEqual(out['unavailable_referents'], ['missing.wav'])
            self.assertTrue((Path(td)/'sound_recordings'/'ref1.wav').exists())

if __name__ == '__main__': unittest.main()
