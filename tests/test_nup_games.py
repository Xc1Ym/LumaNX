"""NUP import → real image packing → mocked compilation → install and launch.

All code, control data and resources below are synthetic, never player files.
"""
import contextlib
from collections import Counter
import hashlib
import io
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Worker'))
from core import Context, Failure, Cancelled, atomic, profiles, read
import build, derived, library, nup
from nup_fixture import npdm, tlv, write_nup

TITLE='0400000000010000'
BID='12'*16
VERSION=458752
ICON=b'\x89PNG\r\n\x1a\nsynthetic icon'


class NupGameTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="nup-中文's-");self.root=Path(self.tmp.name)
        self.engine=self.root/'engine'
        for rel in ('scripts/pack_nup.py','dm/tools/romfs_image.py','dm/tools/nacp.py'):
            dest=self.engine/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/'Engine/nxnative'/rel,dest)
        folder=self.engine/'dm/games'/TITLE;folder.mkdir(parents=True)
        (folder/'game.tsv').write_text(f'name\tSynthetic Switch 2\npackage\tv{VERSION}\nshader_versions\tv{VERSION}\n'
            f'build\tv{VERSION}\t1.2\tmain={BID}\tsdk={BID}\nmodules\tmain sdk\nromfs_marker\tdir/marker\ngraphics\tvulkan\n')
        self.c=Context(dict(operation='import',privateRoot=str(self.root/'private'),library=str(self.root/'library'),
            resources=str(self.root/'resources'),engineDir=str(self.engine),gameId=TITLE))
        self.quiet(library.setup,self.c);self.source=self.root/'game.NUP'
        nacp=bytearray(0x4000);nacp[:14]=b'Synthetic Name';nacp[0x3060:0x3063]=b'1.2'
        self.nacp=bytes(nacp);self.meta=tlv([(2,self.nacp),(3,ICON)]);self.write()
        self.c.r['paths']=[str(self.source)]

    def tearDown(self): self.tmp.cleanup()
    def quiet(self,fn,*args,**kwargs):
        with contextlib.redirect_stdout(io.StringIO()): return fn(*args,**kwargs)
    def tree(self,base=False):
        nso=bytearray(0x100);nso[:4]=b'NSO0';nso[0x40:0x50]=bytes.fromhex(BID)
        return {'exefs':dict(main=bytes(nso),sdk=bytes(nso),**{'main.npdm':npdm(int(TITLE,16))}),
                'romfs':{'dir/marker':b'synthetic resource'*40,**({'removed':b'base only'} if base else {})}}
    def write(self,base=True,flags=0,update=True):
        packages=([(0,int(TITLE,16),0,self.tree(True),b'')] if base else [])
        if update: packages.append((1,int(TITLE,16)+0x800,VERSION,self.tree(),self.meta))
        packages.append((2,int(TITLE,16)+0x1001,0,{'romfs':{'addon':b'synthetic DLC'}},b''))
        write_nup(self.source,packages,update_flags=flags)
    def imported(self): return self.quiet(library.import_games,self.c)
    def game(self): return self.c.catalog()['games'][0]

    def test_keyless_preflight_import_metadata_single_managed_copy_and_duplicate(self):
        self.assertEqual(self.quiet(library.scan_import,self.c),dict(requiresKeys=False,containers=1,dumps=0))
        with patch.object(self.c,'nx',side_effect=AssertionError('must not decrypt')): self.imported()
        game=self.game();self.assertEqual(game['sourceKind'],'nup');self.assertEqual(game['missing'],[])
        self.assertEqual(game['name'],'Synthetic Name');self.assertEqual(game['display'],'1.2')
        self.assertEqual(len(game['packages']),3);self.assertEqual(len({p['path'] for p in game['packages']}),1)
        self.assertEqual((self.c.library/game['cover']).read_bytes(),ICON)
        self.assertTrue(self.imported()['imports'][0]['duplicate']);self.assertFalse(self.c.keys.exists())
        self.assertFalse((self.c.private/'keys/status.json').exists())

    def test_mixed_folder_requires_keys_before_any_import(self):
        self.c.r['paths']=[str(self.root)];(self.root/'game.nsp').write_bytes(b'synthetic')
        self.assertTrue(self.quiet(library.scan_import,self.c)['requiresKeys'])
        with self.assertRaisesRegex(Failure,'prod.keys'): self.imported()
        self.assertEqual(self.c.catalog()['games'],[])

    def test_standalone_update_has_no_fake_v0_and_builds_registered_version(self):
        self.write(base=False,flags=1);self.imported();game=self.game()
        self.assertEqual(game['missing'],[]);self.assertFalse(any(p['type']=='base' for p in game['packages']))
        self.assertEqual(derived.plan(game,profiles(self.engine)[TITLE],True)['versions'],[f'v{VERSION}'])
        self.pipeline()

    def test_missing_base_without_standalone_flag_and_missing_version_fail(self):
        self.write(base=False)
        with self.assertRaisesRegex(Failure,'NUP'): self.imported()
        self.assertEqual(self.c.catalog()['games'],[])
        self.write(update=False);self.imported()
        self.assertIn('缺少更新',self.game()['missing'][0])

    def test_corrupted_toc_payload_and_truncated_file_leave_no_catalog_entry(self):
        original=self.source.read_bytes()
        with nup.opened(self.c,self.source) as (_,n): payload=n.files[-1][3]
        for index in (0x90,payload):
            data=bytearray(original);data[index]^=0xff;self.source.write_bytes(data)
            with self.assertRaises(Failure): self.imported()
            self.assertEqual(self.c.catalog()['games'],[])
        self.source.write_bytes(original[:40])
        with self.assertRaises(Failure): self.imported()

    def test_changed_registered_build_and_missing_marker_are_detected(self):
        tree=self.tree();tree['exefs']['main']=b'NSO0'+b'\0'*252
        write_nup(self.source,[(1,int(TITLE,16)+0x800,VERSION,tree,b'')],update_flags=1)
        self.imported();self.assertTrue(any('构建标识' in m for m in self.game()['missing']))
        tree=self.tree();tree['romfs']={'wrong':b'no marker'}
        write_nup(self.source,[(1,int(TITLE,16)+0x800,VERSION,tree,b'')],update_flags=1)
        with self.assertRaisesRegex(Failure,'资源'): self.imported()

    def test_extract_images_no_base_overlay_dlc_and_romfs_fallback(self):
        self.imported();managed=self.c.library/self.game()['packages'][0]['path']
        out=self.root/'extract';self.quiet(nup.extract,self.c,managed,VERSION,out)
        rfs=derived.module(ROOT/'Engine/nxnative/dm/tools/romfs.py','nup_test_romfs')
        image=rfs.Image(out/'RomFS.img');self.assertIsNotNone(image.find('dir/marker'))
        with self.assertRaises(FileNotFoundError): image.find('removed')
        aoc=self.root/'aoc';self.quiet(nup.extract_dlc,self.c,managed,aoc)
        self.assertIsNotNone(rfs.Image(aoc/'1.img').find('addon'))
        tree=self.tree();tree.pop('romfs')
        write_nup(self.source,[(0,int(TITLE,16),0,self.tree(True),b''),(1,int(TITLE,16)+0x800,VERSION,tree,b'')])
        self.imported();out2=self.root/'fallback'
        self.quiet(nup.extract,self.c,self.c.library/self.game()['packages'][0]['path'],VERSION,out2)
        self.assertIsNotNone(rfs.Image(out2/'RomFS.img').find('removed'))

    def test_ios_blocked_before_engine_and_source_mixing_rejected(self):
        self.imported()
        with patch('build.tools') as tools:
            with self.assertRaisesRegex(Failure,'仅支持 Mac'): build.prepare(self.c,self.game(),'ios')
            tools.assert_not_called()
        cat=self.c.catalog();cat['games'][0]['sourceKind']='dump';self.c.save_catalog(cat)
        with self.assertRaisesRegex(Failure,'混用'): self.imported()

    def test_copy_failure_and_cleanup_keep_original(self):
        with patch('nup.copy_source',side_effect=Failure('synthetic copy failure')):
            with self.assertRaises(Failure): self.imported()
        self.assertEqual(self.c.catalog()['games'],[])
        self.imported();managed=self.c.library/self.game()['packages'][0]['path']
        self.c.r['kind']='sources';self.quiet(library.clean,self.c)
        self.assertFalse(managed.exists());self.assertTrue(self.source.exists());self.assertEqual(self.game()['packages'],[])

    def test_source_is_copied_and_hashed_in_one_pass_and_payloads_verified_once(self):
        original_open=Path.open;source_reads=[];payloads=Counter();expected=[];real_opened=nup.opened
        class Tracked:
            def __init__(self,stream): self.stream=stream
            def __enter__(self): return self
            def __exit__(self,*args): self.stream.close()
            def fileno(self): return self.stream.fileno()
            def read(self,*args):
                data=self.stream.read(*args);source_reads.append(len(data));return data
        def opening(path,*args,**kwargs):
            stream=original_open(path,*args,**kwargs)
            return Tracked(stream) if path.resolve()==self.source.resolve() and args==('rb',) else stream
        @contextlib.contextmanager
        def recording(c,path):
            with real_opened(c,path) as (parser,container):
                copy=container.copy;expected.append(len(container.files))
                def copying(i,out): payloads[i]+=1;return copy(i,out)
                container.copy=copying
                yield parser,container
        with patch.object(Path,'open',opening),patch('nup.opened',recording),patch('nup.digest',wraps=nup.digest) as hashes:
            self.imported();hashes.assert_not_called()
        self.assertEqual(sum(source_reads),self.source.stat().st_size)
        self.assertEqual(len(payloads),expected[0]);self.assertEqual(set(payloads.values()),{1})
        self.assertEqual(self.game()['packages'][0]['sha256'],hashlib.sha256(self.source.read_bytes()).hexdigest())

    def test_copy_cancellation_and_concurrent_source_change_leave_no_partial_files(self):
        for cancel in (True,False):
            def progress(done,total):
                if cancel: raise Cancelled()
                self.source.write_bytes(self.source.read_bytes()+b'changed during copy')
            with patch.object(self.c,'progress',side_effect=progress):
                with self.assertRaises(Cancelled if cancel else Failure): self.imported()
            self.assertEqual(self.c.catalog()['games'],[])
            self.assertEqual(list((self.c.library/'sources').iterdir()),[])
            self.write()

    def test_catalogue_save_failure_restores_existing_cover_and_catalogue(self):
        self.imported();before=self.c.catalog();cover=self.c.library/self.game()['cover']
        self.meta=tlv([(2,self.nacp),(3,b'\xff\xd8\xffnew icon')]);self.write()
        managed_before=set((self.c.library/'sources'/TITLE).iterdir())
        with patch.object(self.c,'save_catalog',side_effect=Failure('synthetic catalogue failure')):
            with self.assertRaises(Failure): self.imported()
        self.assertEqual(self.c.catalog(),before);self.assertEqual(cover.read_bytes(),ICON)
        self.assertEqual(set((self.c.library/'sources'/TITLE).iterdir()),managed_before)
        self.assertFalse(list(cover.parent.glob('.cover-*')))

    def test_first_import_save_failure_or_cancel_leaves_no_orphan_cover(self):
        cover=self.c.library/'games'/TITLE/'cover.jpg'
        for cancel in (False,True):
            if cancel:
                original=self.c.check
                def check():
                    if cover.exists(): raise Cancelled()
                    original()
                replacement=patch.object(self.c,'check',side_effect=check)
            else: replacement=patch.object(self.c,'save_catalog',side_effect=Failure('synthetic failure'))
            with replacement:
                with self.assertRaises(Cancelled if cancel else Failure): self.imported()
            self.assertEqual(self.c.catalog()['games'],[]);self.assertFalse(cover.exists())
            self.assertFalse(list((self.c.library/'sources').rglob('*.nup')))
            self.assertFalse(list(cover.parent.glob('.cover-*')))

    def test_marker_intermediate_file_has_resource_error(self):
        tree=self.tree();tree['romfs']={'dir':b'file instead of directory'}
        write_nup(self.source,[(1,int(TITLE,16),VERSION,tree,b'')],update_flags=1)
        with self.assertRaisesRegex(Failure,'^游戏资源缺少配置指定的文件。$'): self.imported()

    def test_update_title_id_must_identify_the_same_application(self):
        write_nup(self.source,[(1,int(TITLE,16)+0x2000,VERSION,self.tree(),b'')],update_flags=1)
        with self.assertRaisesRegex(Failure,'Title ID'): self.imported()
        self.assertEqual(self.c.catalog()['games'],[])
        write_nup(self.source,[(1,int(TITLE,16),VERSION,self.tree(),b'')],update_flags=1)
        self.imported();self.assertEqual(self.game()['packages'][0]['titleId'],f'{int(TITLE,16)+0x800:016X}')

    def test_invalid_or_oversized_optional_icon_and_nacp_use_defaults(self):
        self.meta=tlv([(2,b'truncated NACP'),(3,b'not an image')]);self.write();self.imported()
        self.assertEqual(self.game()['name'],'Synthetic Switch 2');self.assertEqual(self.game()['cover'],'')
        self.meta=tlv([(2,self.nacp+b'oversized'),(3,ICON)]);self.write()
        with patch('nup.MAX_ICON_BYTES',len(ICON)-1): self.imported()
        self.assertEqual(self.game()['name'],'Synthetic Switch 2');self.assertEqual(self.game()['cover'],'')
        self.assertFalse((self.c.library/'games'/TITLE/'cover.jpg').exists())
        self.meta=tlv([(2,self.nacp),(3,ICON)]);self.write()
        with patch('nup.MAX_ICON_BYTES',len(ICON)): self.imported()
        self.assertEqual((self.c.library/self.game()['cover']).read_bytes(),ICON)

    def test_oversized_control_block_is_rejected_before_reading_tlvs(self):
        with patch('nup.MAX_CONTROL_BYTES',len(self.meta)-1):
            with self.assertRaisesRegex(Failure,'控制数据'): self.imported()
        self.assertEqual(self.c.catalog()['games'],[])
        self.assertFalse(list((self.c.library/'sources').rglob('*.nup')))

    def test_cancellation_during_streaming_is_preserved(self):
        with patch.object(self.c,'check',side_effect=Cancelled()):
            with self.assertRaises(Cancelled):
                with nup.opened(self.c,self.source) as (_,container): container.read(0)

    def test_empty_base_placeholder_uses_complete_update(self):
        write_nup(self.source,[(0,0,0,{},b''),(1,int(TITLE,16)+0x800,VERSION,self.tree(),self.meta)])
        self.imported();self.assertEqual(self.game()['missing'],[])
        self.assertEqual([p['type'] for p in self.game()['packages']],['update'])

    def test_full_pipeline_cache_install_image_validation_launch_and_tamper(self):
        self.imported();self.pipeline()

    def pipeline(self):
        game=self.game();work=self.c.library/'cache'/TITLE/'fixture';work.mkdir(parents=True)
        gp=SimpleNamespace(id=TITLE,get=lambda k,d=None:{'package':f'v{VERSION}','graphics':'vulkan','romfs_marker':'dir/marker'}.get(k,d),
            words=lambda k,d=None:['main','sdk'] if k=='modules' else [d],builds=lambda:{f'v{VERSION}':{'display':'1.2'}},
            table=lambda n:self.engine/'dm/games'/TITLE/n)
        rewrites=[];runs=[]
        def rewrite(py,repo,exefs,out,env,logs,profile):
            rewrites.append(exefs);out.mkdir()
            for name in ('main','sdk'):
                for ext in ('patched.bin','fixups.tsv','gates.tsv'): (out/f'{name}.{ext}').write_text('synthetic')
        def run(args,log=None,env=None,**kw):
            runs.append((args,env))
            if Path(args[0]).name=='dmhost': return
            if Path(args[1]).name=='vk_shaders.py':
                self.assertTrue(str(args[2]).endswith('RomFS.img'))
                dst=work/'shader/vk';dst.mkdir();(dst/'vk_shaders.metallib').write_text('synthetic shader')
            elif Path(args[1]).name=='make_ext_font.py': Path(args[2]).write_text('synthetic font')
        def host(*args):
            path=work/'tools/dmhost';path.parent.mkdir();path.write_text('synthetic host');return path
        up=SimpleNamespace(extract=lambda *a:self.fail('must not decrypt'),rewrite=rewrite)
        atomic(work/'identity.json',dict(tools={'engine':'fixture'},sources=sorted(p['sha256'] for p in game['packages'])))
        with contextlib.redirect_stdout(io.StringIO()),patch('build.prepare',return_value=(work,self.engine,self.c.env(TITLE,work),up,gp,'fixture')),\
             patch.object(self.c,'nx',side_effect=AssertionError('must not decrypt')),patch.object(self.c,'run',side_effect=run),\
             patch('build.compile_host',side_effect=host),patch('toolchain.require_launch_environment'):
            result=build.build(self.c);runtime=Path(result['path']);build.validate_runtime(runtime,gp)
            self.assertTrue((runtime/'romfs.img').is_file());self.assertTrue((runtime/'aoc/1.img').is_file())
            build.launch(self.c);self.assertTrue(runs[-1][1]['DM_ROMFS'].endswith('romfs.img'))
            build.build(self.c);self.assertEqual(len(rewrites),1)
            managed=self.c.library/game['packages'][0]['path'];managed.write_bytes(b'changed')
            with self.assertRaisesRegex(Failure,'发生改变'): build.build(self.c)
            self.assertTrue((runtime/'romfs.img').is_file())


if __name__=='__main__': unittest.main()
