import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Worker'))
import incremental
import build
from core import Failure


class ActivityRecoveryTests(unittest.TestCase):
    def test_only_exact_reviewed_telemetry_recipes_reuse_old_producers(self):
        record=json.loads((ROOT/'Worker/telemetry_recipe_compatibility.json').read_text())[f'{sys.version_info.major}.{sys.version_info.minor}']
        for kind,item in record.items():
            def recipe(path, entries):
                return item['telemetry']['common'] if path.name=='core.py' else item['telemetry']['functions'][path.name]
            with patch.object(incremental,'python_recipe',side_effect=recipe),patch.object(incremental,'hash_value',return_value=item['telemetry']['coordinator']):
                self.assertEqual(incremental.worker_recipe(kind),item['producer'])
                with patch.object(incremental,'hash_value',return_value='changed-coordinator'):
                    self.assertNotEqual(incremental.worker_recipe(kind),item['producer'])
                with patch.object(incremental,'python_recipe',return_value='changed-producer'):
                    self.assertNotEqual(incremental.worker_recipe(kind),item['producer'])

    def test_runtime_validator_accepts_packed_image_and_rejects_wrong_chain(self):
        tools=ROOT/'Engine/nxnative/dm/tools';sys.path.insert(0,str(tools))
        import shader_lib
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'romfs').mkdir();(root/'modules').mkdir();(root/'shaders').mkdir()
            (root/'dmhost').write_bytes(b'host')
            for ext in ('patched.bin','fixups.tsv','gates.tsv'):(root/'modules'/('main.'+ext)).write_bytes(b'module')
            (root/'manifest.json').write_text(json.dumps(dict(chain='abc',graphics='nvn',preparationMode='registered')))
            image=root/'shaders/b-abc.img'
            def write(chain):shader_lib.write({'key_b.json':json.dumps(dict(chain=chain)).encode(),'key_b.metallib':b'library'},str(image))
            write('abc');build.validate_runtime(root)
            write('wrong')
            with self.assertRaises(Failure):build.validate_runtime(root)
