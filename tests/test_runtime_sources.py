"""The redistributed ZBIC binary keeps its matching source and license offline."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import bundle_runtime


class RuntimeSourceTests(unittest.TestCase):
    def fixture(self,root):
        archive=root/'work/runtime-downloads'/f'zbic-{bundle_runtime.ZBIC_VERSION}.tar.gz'
        archive.parent.mkdir(parents=True)
        license=b'Synthetic ZBIC license fixture'
        with tarfile.open(archive,'w:gz') as source:
            entry=tarfile.TarInfo(f'zbic-{bundle_runtime.ZBIC_VERSION}/LICENSE');entry.size=len(license)
            source.addfile(entry,io.BytesIO(license))
        return archive,license,hashlib.sha256(archive.read_bytes()).hexdigest()

    def test_bundled_output_contains_verified_source_manifest_and_license(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);archive,license,sha=self.fixture(root);output=root/'runtime'
            with patch.object(bundle_runtime,'ROOT',root),patch.object(bundle_runtime,'ZBIC_SHA256',sha),\
                 patch('urllib.request.urlopen',side_effect=AssertionError('must reuse verified cache')):
                bundle_runtime.retain_zbic_sources(output)
            self.assertEqual((output/'sources'/archive.name).read_bytes(),archive.read_bytes())
            self.assertEqual((output/'licenses/zbic-LICENSE.txt').read_bytes(),license)
            self.assertEqual(json.loads((output/'sources/zbic.json').read_text()),dict(
                version=bundle_runtime.ZBIC_VERSION,url=bundle_runtime.ZBIC_SOURCE,sha256=sha))

    def test_changed_cached_source_is_rejected_before_publishing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.fixture(root);output=root/'runtime'
            with patch.object(bundle_runtime,'ROOT',root),patch.object(bundle_runtime,'ZBIC_SHA256','0'*64),\
                 patch('urllib.request.urlopen',side_effect=AssertionError('must validate cached bytes')):
                with self.assertRaisesRegex(RuntimeError,'hash mismatch'): bundle_runtime.retain_zbic_sources(output)
            self.assertFalse(output.exists())
