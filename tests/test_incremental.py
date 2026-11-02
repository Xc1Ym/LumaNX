"""Run the actual preparation/build coordinator with synthetic engine producers.

No player games, keys or native game code are read or executed.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'Worker'),str(ROOT/'tests')]
from core import Context, Failure, Cancelled, atomic, digest, read
import build, engine, incremental, library
from engine_fixture import make_engine

TITLE='0100000000010000'
SCRIPT='''
from pathlib import Path
class Progress:
    def __init__(self, mode): self.cur=None
    def stage(self,*a,**kw): pass
    def watch(self,*a): pass
def event(logs, name):
    with (logs.parent/'events').open('a') as f: f.write(name+'\\n')
def extract(nx, keys, ex, version, base, update, extra, logs, gp, app):
    event(logs,'unpack')
    d=ex/version;(d/'ExeFS').mkdir(parents=True);(d/'RomFS').mkdir()
    code,asset=(update or base).read_text().split('|')
    (d/'ExeFS/main').write_text(code);(d/'RomFS/marker').write_text(asset)
    (d/'RomFS/empty').mkdir()
def extract_aoc(nx,keys,repo,root,app,family,logs):
    event(logs,'dlc');(root/'aoc').mkdir()
    for tid,version,path in family['dlc']:
        d=root/'aoc'/str(tid-app-0x1000);d.mkdir();(d/'data').write_text(path.read_text())
def rewrite(py,repo,exefs,out,env,logs,gp):
    event(logs,'rewrite');out.mkdir()
    for ext in ('patched.bin','fixups.tsv','gates.tsv'):
        (out/('main.'+ext)).write_text((exefs/'main').read_text())
def split_shaders(py,repo,roms,mains,pkg,env,logs,gp,**kw):
    event(logs,'split');pkg.mkdir(parents=True);(pkg/'shader.bin').write_text('synthetic shader package')
def capture_glslc(repo,dirs,version,patched,root,env,logs,gp):
    event(logs,'capture');out=dirs[version]/'glslc_capture';out.mkdir();(out/'shader').write_text('captured')
def decode_ue_shaders(repo,dirs,version,patched,root,env,logs,gp):
    event(logs,'decode');out=dirs[version]/'ue_shaders';out.mkdir();(out/'shader').write_text('decoded')
def build_mac_host(*a): pass
'''


class IncrementalBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="luma-incremental-中文's-")
        self.root=Path(self.tmp.name);self.source=make_engine(self.root/'source')
        (self.source/'scripts/build_ipa_from_nsp.py').write_text(SCRIPT)
        (self.source/'dm/games/game.py').write_bytes((ROOT/'Engine/nxnative/dm/games/game.py').read_bytes())
        self.profile=self.source/'dm/games'/TITLE/'game.tsv'
        self.profile.write_text('name\tSynthetic\npackage\tv1114112\nshader_versions\tv1114112\nmodules\tmain\n'
            'build\tv1114112\t1.0\tmain=fixture-build\ngraphics\tvulkan\nromfs_marker\tmarker\napp_pool\t0x100000\n')
        (self.source/'dm/host/controller_native.h').write_text('controller revision 1')
        (self.source/'dm/gfx/tools/compiler.py').write_text('REVISION = 1\n')
        (self.source/'dm/tools/patch_nso.py').write_text('rewriter revision 1')
        self.c=Context(dict(operation='build',privateRoot=str(self.root/'private'),resources=str(self.root/'resources'),
            library=str(self.root/'library'),engineDir=str(self.source),gameId=TITLE))
        self.c.library.mkdir();self.c.r['paths']=[]
        self.packages=[]
        for kind,version,content in (('base',0,'code|base'),('update',1114112,'code|asset')):
            path=self.c.library/(kind+'.nsp');path.write_text(content)
            self.packages.append(dict(type=kind,version=version,titleId=TITLE,baseId=TITLE,path=path.name,
                size=path.stat().st_size,sha256=digest(path),builds={'main':'fixture-build'}))
        self.save_game();self.tool_versions=dict(runtime='runtime1',clang='clang1',metal='metal1',
            **{'macos-sdk':'sdk1','spirv-cross':'spirv1','inputConfig':False,'readerLibrary':__import__('hashlib').sha256(b'library1').hexdigest(),'readerSDK':'10.0'})
        self.prepared=None;self.host_failure=False;self.cancel_host=False;self.compiler_invocations=0
        self.prior_game=sys.modules.pop('game',None);self.sys_path=list(sys.path)
        self.stack=contextlib.ExitStack()
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stack.enter_context(patch('engine.inspect_source',side_effect=lambda c:dict(fingerprint=self.info()['engineSource'],derivedProfiles=False)))
        self.stack.enter_context(patch('engine.prepared_tools',side_effect=lambda *a,**kw:self.prepared))
        self.stack.enter_context(patch('build.tools',side_effect=lambda *a:self.info()))
        self.stack.enter_context(patch('build.compile_host',side_effect=self.host))
        self.stack.enter_context(patch.object(self.c,'nx',return_value=self.root/'reader'))
        self.stack.enter_context(patch.object(self.c,'run',side_effect=self.tool_run))
        self.stack.enter_context(patch('ipa.validate_shaders'))
        self.stack.enter_context(patch('ipa.package',return_value={'path':'synthetic IPA'}))

    def tearDown(self):
        self.stack.close();sys.modules.pop('game',None);sys.path[:]=self.sys_path
        if self.prior_game is not None: sys.modules['game']=self.prior_game
        self.tmp.cleanup()

    def info(self):
        fp='external-'+engine.source_hash(self.source)
        return self.tool_versions|dict(engine=fp,engineSource=fp,reader='incidental-dll-'+fp)

    def save_game(self):
        self.c.save_catalog({'games':[dict(id=TITLE,name='Synthetic',packages=self.packages,hidden=False)]})

    def event(self, root, name):
        with (root/'events').open('a') as f:f.write(name+'\n')

    def tool_run(self,args,log=None,env=None,**kw):
        script=Path(args[1]);work=Path(log).parent.parent
        if script.name in ('dmsh_chain.py','tool_lock.py'):
            tools=work/'engine/dm/gfx/tools';tools.mkdir(parents=True,exist_ok=True)
            if args[-1]=='--update-lock': (tools/'dmsh_chain.lock').write_text('synthetic lock')
            if args[-1]=='--header':
                header=work/'engine/dm/gfx/nvn/dmsh_chain.h';header.parent.mkdir(parents=True,exist_ok=True)
                header.write_text('#define DMSH_CHAIN "'+digest(self.source/'dm/gfx/tools/compiler.py')[:12]+'"')
        elif script.name=='vk_shaders.py':
            self.compiler_invocations+=1;self.event(work,'shaders')
            dst=work/'shader/vk';dst.mkdir(parents=True)
            (dst/'vk_shaders.metallib').write_text('synthetic shader '+self.tool_versions['metal'])
            if '--ios' in args:
                (work/'shader/ios/vk').mkdir(parents=True)
                (work/'shader/ios/vk/vk_shaders.metallib').write_text('synthetic iOS')
        elif script.name=='dmsh_build.py':
            self.compiler_invocations+=1;self.event(work,'shaders')
            from core import chain_of
            chain=chain_of(work/'engine');folder=work/'shader/cache'/('b-'+chain);folder.mkdir(parents=True)
            (folder/'key_b.metallib').write_text('synthetic Metal library')
            atomic(folder/'key_b.json',{'chain':chain})
        elif script.name=='c1_generate.py':
            from core import chain_of
            Path(args[-1]).write_text('# chain b-'+chain_of(work/'engine')+' synthetic table\n')
        elif script.name=='make_ext_font.py': Path(args[2]).write_text('synthetic font')
        else: raise AssertionError(args)

    def host(self,c,up,repo,env,root,gp):
        self.event(root,'host')
        if self.host_failure: raise Failure('synthetic host failure')
        if self.cancel_host: raise Cancelled()
        path=root/'tools/dmhost';path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('synthetic host '+(repo/'dm/host/controller_native.h').read_text());return path

    def build(self,target='macos'):
        info=self.info();self.prepared=self.c.private/'engines'/info['engineSource']
        if not self.prepared.exists():
            shutil.copytree(self.source,self.prepared/'source')
            (self.prepared/'source/.source-ready').write_text(info['engineSource'])
            library=self.prepared/'tools/nx_extract/LibHac.dll';library.parent.mkdir(parents=True);library.write_bytes(b'library1')
            atomic(self.prepared/'ready.json',dict(fingerprint=info['engineSource'],sdk='10.0',
                snapshotHash=engine.source_hash(self.prepared/'source'),files={'tools/nx_extract/LibHac.dll':digest(library)}))
        # The real prepare builds a stable workspace and an independent graph.
        self.c.r['operation']='exportIPA' if target=='ios' else 'build'
        result=build.build(self.c,target)
        self.work=incremental.workspace(self.c,self.c.game(),target,'unused')
        return result

    def events(self): return (self.work/'events').read_text().splitlines()
    def delta(self, change):
        before=self.events();change();self.build();return self.events()[len(before):]

    def test_controller_edit_updates_only_host_and_preserves_workspace(self):
        first=self.build();workspace=self.work
        delta=self.delta(lambda:(self.source/'dm/host/controller_native.h').write_text('controller revision 2'))
        self.assertEqual(delta,['host']);self.assertEqual(self.work,workspace)
        self.assertEqual(self.compiler_invocations,1)
        self.assertNotEqual(first['path'],str((self.c.library/'games'/TITLE/'current').resolve()))
        self.assertTrue((Path(first['path'])/'romfs/marker').is_file())
        self.assertTrue((Path(first['path'])/'romfs/empty').is_dir())
        self.assertEqual(self.delta(lambda:None),[])

    def test_registered_nvn_cache_survives_controller_fix_and_legacy_adoption(self):
        self.profile.write_text(self.profile.read_text().replace('graphics\tvulkan','graphics\tnvn'))
        (self.profile.parent/'shader_map.tsv').write_text('vs_data.bin\t0\tvs\tkey\tsynthetic\n')
        self.build();(self.work/'stage-inputs.json').unlink()
        self.assertEqual(self.delta(lambda:(self.source/'dm/host/controller_native.h').write_text('controller revision 2')),['host'])
        self.assertEqual(self.compiler_invocations,1)

    def test_capture_and_decode_do_not_depend_on_later_stage_outputs(self):
        self.profile.write_text(self.profile.read_text().replace('graphics\tvulkan','graphics\tnvn')+'shader_glslc_capture\ton\n')
        (self.profile.parent/'shader_map.tsv').write_text('vs_data.bin\t0\tvs\tkey\tsynthetic\n')
        with patch('derived.detect_sources',return_value={'ue_decode':(True,'synthetic')}):
            self.build()
            self.assertEqual(self.events().count('capture'),1)
            self.assertEqual(self.events().count('decode'),1)
            self.assertEqual(self.delta(lambda:None),[])
            self.assertEqual(self.delta(lambda:(self.source/'dm/host/controller_native.h').write_text('controller revision 2')),['host'])

    def test_shader_compiler_updates_shader_stage_and_matching_host(self):
        self.build()
        self.assertEqual(self.delta(lambda:(self.source/'dm/gfx/tools/compiler.py').write_text('REVISION = 2\n')),['shaders','host'])

    def test_rewriter_change_only_rewrites_modules(self):
        self.build()
        self.assertEqual(self.delta(lambda:(self.source/'dm/tools/patch_nso.py').write_text('rewriter revision 2')),['rewrite'])

    def test_host_profile_setting_does_not_rewrite_or_compile_shaders(self):
        self.build()
        self.assertEqual(self.delta(lambda:self.profile.write_text(self.profile.read_text().replace('0x100000','0x200000'))),['host'])

    def test_asset_update_reuses_unchanged_exefs_rewrite_and_host(self):
        self.build()
        def change():
            p=self.c.library/'update.nsp';p.write_text('code|new asset')
            self.packages[1].update(size=p.stat().st_size,sha256=digest(p));self.save_game()
        self.assertEqual(self.delta(change),['unpack','shaders'])

    def test_dlc_addition_only_extracts_dlc(self):
        self.build()
        def change():
            p=self.c.library/'dlc.nsp';p.write_text('synthetic DLC')
            self.packages.append(dict(type='dlc',version=0,titleId='0100000000011001',baseId=TITLE,
                path=p.name,size=p.stat().st_size,sha256=digest(p),builds={}))
            self.save_game()
        self.assertEqual(self.delta(change),['dlc'])
        runtime=self.c.library/'games'/TITLE/'current'
        self.assertEqual((runtime/'aoc/1/data').read_text(),'synthetic DLC')

    def test_reader_source_change_checks_extraction_but_keeps_identical_outputs(self):
        self.build()
        self.assertEqual(self.delta(lambda:(self.source/'dm/tools/nx_extract/Program.cs').write_text('reader revision 2')),['unpack'])

    def test_other_game_profile_change_does_not_rebuild_this_game(self):
        self.build()
        path=self.source/'dm/games/01007EF00011E000/game.tsv'
        self.assertEqual(self.delta(lambda:path.write_text(path.read_text()+'\n# another title\n')),[])

    def test_corrupt_or_extra_stage_files_rebuild_only_affected_producer(self):
        self.build()
        self.assertEqual(self.delta(lambda:(self.work/'tools/dmhost').write_text('tampered')),['host'])
        self.assertEqual(self.delta(lambda:(self.work/'extract/v1114112/RomFS/extra').write_text('extra')),['unpack'])
        self.assertEqual(self.delta(lambda:(self.work/'shader/vk/vk_shaders.metallib').unlink()),['shaders'])

    def test_failed_or_cancelled_host_preserves_old_release_and_retries_only_host(self):
        self.build();current=self.c.library/'games'/TITLE/'current';old=current.resolve()
        (self.source/'dm/host/controller_native.h').write_text('controller revision 2')
        self.host_failure=True
        with self.assertRaisesRegex(Failure,'host failure'): self.build()
        self.assertEqual(current.resolve(),old)
        self.assertNotIn('编译 Mac 主程序',read(self.work/'stage-inputs.json'))
        self.host_failure=False;self.cancel_host=True
        with self.assertRaises(Cancelled): self.build()
        self.assertEqual(current.resolve(),old)
        self.cancel_host=False;before=self.events();self.build()
        self.assertEqual(self.events()[len(before):],['host'])

    def test_target_workspaces_are_separate(self):
        self.build();mac=self.work
        # Test the coordinator's target selection without a real iOS compiler.
        with patch('ipa.environment',return_value=({},{})):
            self.build('ios')
        self.assertNotEqual(self.work,mac)
        self.build();self.assertEqual(self.work,mac)

    def test_verified_legacy_cache_can_apply_controller_fix_without_full_rebuild(self):
        self.build();before=self.events();(self.work/'stage-inputs.json').unlink()
        (self.source/'dm/host/controller_native.h').write_text('controller revision 2')
        self.build()
        self.assertEqual(self.events()[len(before):],['host'])

    def test_legacy_cache_without_provenance_rebuilds_instead_of_guessing(self):
        self.build();before=self.events();(self.work/'stage-inputs.json').unlink()
        (self.prepared/'ready.json').unlink()
        self.build()
        self.assertEqual(self.events()[len(before):],['unpack','rewrite','shaders','host'])

    def test_dirty_workspace_source_is_replaced_before_any_tool_runs(self):
        self.build()
        (self.work/'engine/dm/host/controller_native.h').write_text('dirty local modification')
        self.assertEqual(self.delta(lambda:None),[])
        self.assertEqual((self.work/'engine/dm/host/controller_native.h').read_text(),'controller revision 1')
        profile=self.work/'engine/dm/games'/TITLE/'game.tsv'
        profile.write_text(profile.read_text().replace('package\tv1114112','package\tv0'))
        self.assertEqual(self.delta(lambda:None),[])
        self.assertIn('package\tv1114112',profile.read_text())

    def test_toolchain_change_rebuilds_only_its_consumers(self):
        self.build()
        self.assertEqual(self.delta(lambda:self.tool_versions.update(clang='clang2')),['host'])
        self.assertEqual(self.delta(lambda:self.tool_versions.update(metal='metal2')),['shaders','host'])

    def test_missing_empty_resource_directory_is_repaired_without_recompiling(self):
        self.build()
        self.assertEqual(self.delta(lambda:(self.work/'extract/v1114112/RomFS/empty').rmdir()),['unpack'])

    def test_corrupt_ready_runtime_is_reinstalled_without_recompiling(self):
        self.build();current=self.c.library/'games'/TITLE/'current';old=current.resolve()
        self.assertEqual(self.delta(lambda:(current/'romfs/marker').write_text('tampered')),[])
        self.assertNotEqual(current.resolve(),old)
        self.assertEqual((current/'romfs/marker').read_text(),'asset')

    def test_malformed_checkpoint_only_rebuilds_the_affected_stage(self):
        self.build()
        def change():
            records=read(self.work/'checkpoints.json');records['编译 Mac 主程序']={'tools/dmhost':None}
            atomic(self.work/'checkpoints.json',records)
        self.assertEqual(self.delta(change),['host'])


if __name__=='__main__':unittest.main()
