import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Worker'))
import build
from core import Context


class ShaderActivityTests(unittest.TestCase):
    def test_database_backed_compiler_feed_and_packaging_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';(repo/'dm/gfx/nvn').mkdir(parents=True)
            (repo/'dm/gfx/nvn/dmsh_chain.h').write_text('#define DMSH_CHAIN "abc"')
            profile=root/'map.tsv';profile.write_text('x.bin\t0\tvertex\tkey1\tdata\n')
            class Game:
                def table(self,name):return profile
            feed=root/'progress.json';watch=build.ShaderProgress(Game(),repo,root/'cache',feed)
            self.assertIsNone(watch()['total'])
            feed.write_text(json.dumps(dict(step='cache check',done=5,total=10)))
            self.assertEqual(watch()['step'],'Checking shader cache')
            feed.write_text(json.dumps(dict(step='compiling',done=7,total=10)))
            self.assertEqual(watch()['done'],7)
            feed.write_text('{')
            self.assertEqual(watch()['done'],7,'Partial/missing telemetry must not reset progress')
            feed.write_text(json.dumps(dict(step='compiling',done=10,total=10)))
            image=Path(str(watch.path)+'.img.part');image.parent.mkdir();image.write_bytes(b'packed')
            value=watch();self.assertEqual(value['done'],6);self.assertIsNone(value['total']);self.assertEqual(value['unit'],'B')
            feed.unlink();image.unlink()
            value=watch();self.assertIn('finalizing',value['step']);self.assertIsNone(value['total'])

    def test_heartbeat_reports_last_output_without_claiming_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                c=Context(dict(operation='preflight',privateRoot=tmp))
                c.last_output_at=1234
                c.emit('heartbeat')
            event=json.loads(output.getvalue().splitlines()[-1])
            self.assertEqual(event['outputAt'],1234)
            self.assertNotIn('done',event)
