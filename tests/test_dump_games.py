"""Decrypted-tree integration tests. Every program and resource is synthetic."""
import contextlib
import io
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Worker'))
from core import Context, Failure, atomic, read, profiles
import build, derived, dump, library

TITLE='0400000000010000'
BID='12'*16


class DumpGameTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="lumanx-dump-中文's-")
        self.root=Path(self.tmp.name)
        self.engine=self.root/'engine'
        profile=self.engine/'dm/games'/TITLE/'game.tsv';profile.parent.mkdir(parents=True)
        profile.write_text(f'name\tSynthetic Switch 2\npackage\tv458752\nshader_versions\tv458752\n'
            f'build\tv458752\t1.2\tmain={BID}\tsdk={BID}\nmodules\tmain sdk\nromfs_marker\tmarker\ngraphics\tvulkan\n')
        self.c=Context(dict(operation='import',privateRoot=str(self.root/'private'),
            library=str(self.root/'library'),resources=str(self.root/'resources'),engineDir=str(self.engine),gameId=TITLE))
        self.quiet(library.setup,self.c)
        self.source=self.root/'玩家目录'
        self.version(self.source/'base')
        self.version(self.source/'updates/458752')
        (self.source/'base/romfs/removed-by-update').write_text('base only')
        dlc=self.source/f'dlc/{int(TITLE,16)+0x1001:016x}/0/romfs'
        dlc.mkdir(parents=True);(dlc/'addon').write_text('synthetic DLC')
        self.c.r['paths']=[str(self.source)]

    def tearDown(self): self.tmp.cleanup()
    def quiet(self, fn, *args, **kw):
        with contextlib.redirect_stdout(io.StringIO()): return fn(*args,**kw)
    def version(self, path, tid=TITLE):
        (path/'exefs').mkdir(parents=True);(path/'romfs').mkdir()
        npdm=bytearray(0x100);npdm[:4]=b'META'
        struct.pack_into('<II',npdm,0x70,0x80,0x80);npdm[0x80:0x84]=b'ACI0'
        struct.pack_into('<Q',npdm,0x90,int(tid,16));(path/'exefs/main.npdm').write_bytes(npdm)
        for name in ('main','sdk'):
            nso=bytearray(0x100);nso[:4]=b'NSO0';nso[0x40:0x50]=bytes.fromhex(BID)
            (path/'exefs'/name).write_bytes(nso)
        (path/'romfs/marker').write_text('synthetic resource')
        (path/'romfs/empty').mkdir()
    def imported(self): return self.quiet(library.import_games,self.c)
    def game(self): return self.c.catalog()['games'][0]

    def test_import_without_keys_copies_and_verifies_all_packages(self):
        with patch.object(self.c,'nx',side_effect=AssertionError('must not decrypt')):
            result=self.imported()
        self.assertFalse(self.c.keys.exists());self.assertEqual(result['imports'][0]['id'],TITLE)
        game=self.game();self.assertEqual(game['missing'],[])
        self.assertEqual(game['sourceKind'],'dump')
        self.assertEqual(len(game['packages']),3)
        for package in game['packages']:
            self.assertEqual(self.quiet(dump.verify,self.c,package),self.c.library/package['path'])
        (self.source/'updates/458752/romfs/marker').write_text('original changed')
        managed=self.c.library/game['packages'][1]['path']
        self.assertEqual((managed/'romfs/marker').read_text(),'synthetic resource')
        self.assertFalse((self.c.private/'keys/status.json').exists())

    def test_duplicate_then_changed_source_creates_new_revision(self):
        self.imported();before=self.game()
        self.assertTrue(self.imported()['imports'][0]['duplicate'])
        (self.source/'updates/458752/romfs/marker').write_text('new resource')
        self.assertFalse(self.imported()['imports'][0]['duplicate'])
        self.assertNotEqual(before['packages'][1]['sha256'],self.game()['packages'][1]['sha256'])
        self.assertTrue((self.c.library/before['packages'][1]['path']).exists())
        self.c.r['kind']='sources';self.quiet(library.clean,self.c)
        self.assertEqual(list((self.c.library/'sources'/TITLE).iterdir()),[])

    def test_dlc_identity_changes_invalidate_cache_even_for_identical_bytes(self):
        self.imported();old=self.game()['packages'][-1]
        parent=self.source/'dlc';path=next(parent.iterdir())
        path.rename(parent/f'{int(TITLE,16)+0x1002:016x}')
        self.imported();new=self.game()['packages'][-1]
        self.assertEqual(old['treeSha256'],new['treeSha256'])
        self.assertNotEqual(old['sha256'],new['sha256'])

    def test_bundled_bananza_profile_accepts_matching_synthetic_dump(self):
        tid='040074A01BF12000';self.c.engine=Path(__file__).resolve().parents[1]/'Engine/nxnative'
        profile=profiles(self.c.engine)[tid];folder=self.root/'bundled-profile-fixture'
        for version,part in ((0,'base'),(458752,'updates/458752')):
            path=folder/part;self.version(path,tid)
            marker=path/'romfs'/profile['romfs_marker'];marker.parent.mkdir(parents=True,exist_ok=True);marker.write_text('synthetic marker')
            for name,bid in profile['builds']['v458752'].items():
                if name=='display': continue
                module=path/'exefs'/name;data=bytearray(module.read_bytes());data[0x40:0x50]=bytes.fromhex(bid);module.write_bytes(data)
        self.c.r['paths']=[str(folder)];self.imported()
        game=self.game();self.assertEqual(game['id'],tid)
        self.assertEqual(library.requirements(game,profile,True),[])
        self.assertEqual(derived.plan(game,profile,True)['mode'],'registered')

    def test_scan_parent_finds_dump_without_keys(self):
        parent=self.root/'scan';parent.mkdir();self.source.rename(parent/'game')
        self.c.r['paths']=[str(parent)];self.imported()
        self.assertEqual(self.game()['id'],TITLE)

    def test_missing_registered_update_is_reported_without_deriving(self):
        import shutil
        shutil.rmtree(self.source/'updates')
        self.imported();game=self.game();profile=profiles(self.engine)[TITLE]
        self.assertIn('缺少更新',library.requirements(game,profile,True)[0])
        self.assertEqual(derived.plan(game,profile,True)['mode'],'registered')

    def test_wrong_registered_build_is_not_accepted_as_dynamic(self):
        (self.source/'updates/458752/exefs/main').write_bytes(b'NSO0'+b'\0'*252)
        self.imported();self.assertTrue(any('构建标识' in m for m in self.game()['missing']))

    def test_bad_npdm_update_id_and_missing_module_leave_catalog_unchanged(self):
        path=self.source/'updates/458752/exefs/main.npdm';original=path.read_bytes()
        for data in (b'bad', original[:0x90]+struct.pack('<Q',int(TITLE,16)+0x1000)+original[0x98:]):
            path.write_bytes(data)
            with self.assertRaises(Failure): self.imported()
            self.assertEqual(self.c.catalog()['games'],[])
        path.write_bytes(original);(self.source/'updates/458752/exefs/sdk').unlink()
        with self.assertRaises(Failure): self.imported()
        self.assertEqual(list((self.c.library/'sources').iterdir()),[])

    def test_unknown_game_invalid_versions_and_dlc_are_rejected(self):
        profile=self.engine/'dm/games'/TITLE/'game.tsv';original=profile.read_text();profile.unlink()
        with self.assertRaisesRegex(Failure,'已适配'): self.imported()
        profile.write_text(original)
        update=self.source/'updates/458752';update.rename(update.with_name('v458752'))
        with self.assertRaisesRegex(Failure,'十进制'): self.imported()
        update.with_name('v458752').rename(update)
        (self.source/'dlc/bad').mkdir()
        with self.assertRaisesRegex(Failure,'DLC'): self.imported()

    def test_links_and_special_files_are_rejected(self):
        link=self.source/'base/romfs/link';link.symlink_to(self.source/'base/romfs/marker')
        with self.assertRaisesRegex(Failure,'符号链接'): self.imported()
        link.unlink()
        import os
        os.mkfifo(link)
        with self.assertRaisesRegex(Failure,'符号链接'): self.imported()

    def test_changed_managed_copy_fails_before_build(self):
        self.imported();p=self.game()['packages'][0]
        (self.c.library/p['path']/'romfs/marker').write_text('changed')
        with self.assertRaisesRegex(Failure,'发生改变'): self.quiet(dump.verify,self.c,p)

    def test_copy_failure_preserves_catalog_and_cleans_partial_directory(self):
        with patch('dump.clone',side_effect=Failure('synthetic copy failure')):
            with self.assertRaises(Failure): self.imported()
        self.assertEqual(self.c.catalog()['games'],[])
        self.assertEqual(list((self.c.library/'sources'/TITLE).iterdir()),[])

    def test_clean_sources_keeps_original_and_ready_runtime(self):
        self.imported();paths=[self.c.library/p['path'] for p in self.game()['packages']]
        runtime=self.c.library/'games'/TITLE/'current';runtime.mkdir(parents=True)
        (runtime/'keep').write_text('runtime')
        self.c.r['kind']='sources';self.quiet(library.clean,self.c)
        self.assertTrue(all(not p.exists() for p in paths))
        self.assertTrue((self.source/'base/romfs/marker').is_file())
        self.assertTrue((runtime/'keep').is_file());self.assertEqual(self.game()['packages'],[])

    def test_ios_rejected_before_toolchain_or_engine_work(self):
        self.imported()
        with patch('build.tools') as tools:
            with self.assertRaisesRegex(Failure,'仅支持 Mac'): build.prepare(self.c,self.game(),'ios')
            tools.assert_not_called()

    def test_directory_pipeline_retry_install_launch_and_source_integrity(self):
        self.imported();game=self.game();work=self.c.library/'cache'/TITLE/'test';work.mkdir(parents=True)
        repo=work/'engine';repo.mkdir()
        gp=SimpleNamespace(id=TITLE,get=lambda k,d=None:{'package':'v458752','graphics':'vulkan','romfs_marker':'marker'}.get(k,d),
            words=lambda k,d=None:['main','sdk'] if k=='modules' else [d],
            builds=lambda:{'v458752':{'display':'1.2'}},table=lambda n:self.engine/'dm/games'/TITLE/n)
        failures=[True];rewrites=[];runs=[]
        def rewrite(py,engine,exefs,out,env,logs,profile):
            rewrites.append(exefs)
            out.mkdir()
            if failures.pop() if failures else False: raise Failure('synthetic rewrite failure')
            for mod in ('main','sdk'):
                for ext in ('patched.bin','fixups.tsv','gates.tsv'): (out/f'{mod}.{ext}').write_text('synthetic module')
        def run(args,log=None,env=None,**kw):
            runs.append((args,env))
            if Path(args[0]).name=='dmhost': return
            if Path(args[1]).name=='vk_shaders.py':
                dst=work/'shader/vk';dst.mkdir();(dst/'vk_shaders.metallib').write_text('synthetic shader')
            elif Path(args[1]).name=='make_ext_font.py': Path(args[2]).write_text('synthetic font')
        def host(*a):
            path=work/'tools/dmhost';path.parent.mkdir();path.write_text('synthetic host');return path
        up=SimpleNamespace(extract=lambda *a:self.fail('must not decrypt'),rewrite=rewrite)
        prepared=(work,repo,self.c.env(TITLE,work),up,gp,'test')
        atomic(work/'identity.json',dict(tools={'engine':'fixture'},sources=sorted(p['sha256'] for p in game['packages'])))
        with contextlib.redirect_stdout(io.StringIO()),patch('build.prepare',return_value=prepared),\
            patch.object(self.c,'nx',side_effect=AssertionError('must not use reader')),\
            patch.object(self.c,'run',side_effect=run),patch('build.compile_host',side_effect=host),\
            patch('toolchain.require_launch_environment'):
            with self.assertRaisesRegex(Failure,'rewrite failure'): build.build(self.c)
            self.assertNotIn('重写原生代码',read(work/'checkpoints.json',{}))
            result=build.build(self.c)
            runtime=Path(result['path']);build.validate_runtime(runtime,gp)
            self.assertTrue((runtime/'romfs/empty').is_dir())
            self.assertFalse((runtime/'romfs/removed-by-update').exists())
            self.assertEqual((runtime/'aoc/1/addon').read_text(),'synthetic DLC')
            self.assertEqual(read(runtime/'manifest.json')['sourceHashes'],sorted(p['sha256'] for p in game['packages']))
            build.launch(self.c)
            self.assertEqual(runs[-1][1]['DM_ROMFS'],str(self.c.library/'games'/TITLE/'current/romfs'))
            self.assertEqual(runs[-1][1]['DM_AOC_DIR'],str(self.c.library/'games'/TITLE/'current/aoc'))
            build.build(self.c);self.assertEqual(len(rewrites),2)
            (self.c.library/game['packages'][1]['path']/'romfs/marker').write_text('tampered')
            with self.assertRaisesRegex(Failure,'发生改变'): build.build(self.c)
            self.assertTrue((runtime/'romfs/marker').is_file())


if __name__=='__main__': unittest.main()
