"""Synthetic compiled payloads only; no games, keys, external drives or NAS IO."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Worker'))
from core import Context, Failure, Cancelled, atomic
import library
import runtime_archive

GAME='040074A01BF12000'


class RuntimeArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.library=self.root/'local';self.library.mkdir()
        self.archive=self.root/'nas-simulation'
        self.c=Context(dict(operation='archiveGame',privateRoot=str(self.root/'private'),library=str(self.library),gameId=GAME,archiveRoot=str(self.archive)))
        self.c.save_catalog(dict(schema=1,games=[dict(id=GAME,name='Synthetic game',sourceKind='nup',display='v458752',packages=[],hidden=False)]))
        self.local=self.library/'games'/GAME;runtime=self.local/'releases'/'fixture';runtime.mkdir(parents=True)
        (self.local/'current').symlink_to('releases/fixture',target_is_directory=True)
        for folder in ['romfs','modules','shaders','profile']:(runtime/folder).mkdir()
        (runtime/'dmhost').write_bytes(b'synthetic host');(runtime/'dmhost').chmod(0o755)
        (runtime/'romfs/assets').write_bytes(b'A'*100000)
        for ext in ('patched.bin','fixups.tsv','gates.tsv'):(runtime/'modules'/('main.'+ext)).write_bytes(b'synthetic module')
        shaders=runtime/'shaders/b-abc';shaders.mkdir()
        (shaders/'key_b.json').write_text(json.dumps(dict(chain='abc')))
        (shaders/'key_b.metallib').write_bytes(b'synthetic shader')
        (shaders/'key_b.metal').write_bytes(b'generated source'*10000)
        (runtime/'shaders/cas-abc.db').write_bytes(b'build cache'*10000)
        atomic(runtime/'manifest.json',dict(schema=1,gameId=GAME,chain='abc',graphics='nvn',version='v458752',preparationMode='registered'))
        saves=self.library/'saves'/GAME;saves.mkdir(parents=True);(saves/'save.dat').write_bytes(b'keep my save')
        self.runtime=runtime

    def tearDown(self):self.tmp.cleanup()
    def quiet(self,fn,*args):
        with contextlib.redirect_stdout(io.StringIO()):return fn(*args)
    def saved(self):return (self.library/'saves'/GAME/'save.dat').read_bytes()

    def test_archive_restore_round_trip_without_sources_or_build_cache(self):
        result=self.quiet(runtime_archive.archive,self.c)
        entry=result['archive'];archived=Path(entry['path'])
        self.assertFalse((self.local/'current').exists());self.assertTrue(archived.is_dir())
        self.assertEqual(self.saved(),b'keep my save')
        self.assertTrue((archived/'runtime.zip').is_file())
        self.assertTrue(entry['compressed']);self.assertLess(entry['size'],entry['runtimeSize'])
        self.assertEqual(self.c.catalog()['games'][0]['runtimeArchive']['path'],str(archived))
        restored=self.quiet(runtime_archive.restore,self.c)
        self.assertTrue((self.local/'current/dmhost').is_file());self.assertTrue(restored['archiveKept'])
        self.assertEqual(self.saved(),b'keep my save');self.assertTrue(archived.exists())
        self.assertFalse((self.local/'current/shaders/cas-abc.db').exists())
        import os
        self.assertTrue(os.access(self.local/'current/dmhost',os.X_OK))
        import runtime_payload
        view=runtime_payload.shader_tools().view(self.local/'current/shaders/b-abc')
        self.assertTrue((view/'key_b.metallib').is_file());self.assertFalse((view/'key_b.metal').exists())
        self.assertFalse((self.library/'sources').exists());self.assertFalse((self.library/'cache').exists())

    def test_failed_copy_keeps_local_game_and_saves(self):
        with patch.object(runtime_archive,'_zip',side_effect=OSError('simulated SMB failure')):
            with self.assertRaises(OSError):self.quiet(runtime_archive.archive,self.c)
        self.assertTrue((self.local/'current/dmhost').is_file());self.assertEqual(self.saved(),b'keep my save')
        self.assertNotIn('runtimeArchive',self.c.catalog()['games'][0])

    def test_cancellation_before_verified_copy_keeps_local_game(self):
        with patch.object(runtime_archive,'_zip',side_effect=Cancelled):
            with self.assertRaises(Cancelled):self.quiet(runtime_archive.archive,self.c)
        self.assertTrue((self.local/'current/dmhost').is_file());self.assertEqual(self.saved(),b'keep my save')

    def test_corrupt_archive_cannot_replace_local_game_or_saves(self):
        result=self.quiet(runtime_archive.archive,self.c)
        (Path(result['archive']['path'])/'runtime.zip').write_bytes(b'corrupted')
        with self.assertRaises(Failure):self.quiet(runtime_archive.restore,self.c)
        self.assertFalse((self.local/'current').exists());self.assertEqual(self.saved(),b'keep my save')

    def test_archive_manifest_is_pinned_in_local_catalog(self):
        result=self.quiet(runtime_archive.archive,self.c)
        manifest=Path(result['archive']['path'])/'manifest.json'
        manifest.write_text(manifest.read_text()+' ')
        with self.assertRaisesRegex(Failure,'manifest changed'):self.quiet(runtime_archive.restore,self.c)
        self.assertEqual(self.saved(),b'keep my save')

    def test_requirements_distinguish_playing_from_rebuilding(self):
        profile=dict(id=GAME,name='Synthetic game',package='v458752',builds={'v458752':{'display':'2.0'}},compatibility='verified')
        self.c.engine=self.root/'engine'
        from incremental import pipeline_version
        manifest=json.loads((self.runtime/'manifest.json').read_text())
        manifest.update(engine='new-engine',pipeline=pipeline_version())
        atomic(self.runtime/'manifest.json',manifest)
        with patch('engine.inspect_source',return_value=dict(fingerprint='new-engine',derivedProfiles=False,inputConfig=False)),patch.object(library,'refresh_container_metadata'),patch.object(library,'profiles',return_value={GAME:profile}):
            game=self.quiet(library.catalog,self.c)['games'][0]
            self.assertTrue(game['ready']);self.assertEqual(game['missing'],[]);self.assertTrue(game['buildMissing'])
            self.assertFalse(game['needsPreparation'])
            self.quiet(runtime_archive.archive,self.c)
            game=self.quiet(library.catalog,self.c)['games'][0]
            self.assertFalse(game['ready']);self.assertTrue(game['archived']);self.assertEqual(game['missing'],[])
            self.assertTrue(game['buildMissing'])

    def test_library_cannot_be_its_own_archive_destination(self):
        self.c.r['archiveRoot']=str(self.library/'archive')
        with self.assertRaises(Failure):self.quiet(runtime_archive.archive,self.c)
        self.assertTrue((self.local/'current/dmhost').is_file())
