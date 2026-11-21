"""A game with installed DLC needs the engine's shader-only profile derivation.

The registered tables hold the base game's shaders; the split scans the installed DLC as
well, so its tables differ and the comparison fails. The engine's rule for that case is a
shader-only derivation, which keeps the registered module builds and settings.
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Worker'))
from core import Context, digest
import build

TITLE='0100000000010000'
CHAIN='testchain'
STAMP='abc123abc123'


class Profile:
    def __init__(self,folder): self.dir=Path(folder);self.id=self.dir.name
    def table(self,name): return self.dir/name
    def rows(self):
        return [line.split('\t') for line in self.table('game.tsv').read_text().splitlines() if line and not line.startswith('#')]
    def get(self,key,default=None): return next(('\t'.join(r[1:]) for r in self.rows() if r[0]==key),default)
    def words(self,key,default=None): return self.get(key,default).split()


class DLCDerivationTests(unittest.TestCase):
    def build(self,dlc=True):
        with tempfile.TemporaryDirectory(prefix='lumanx-dlc-derive-') as directory:
            root=Path(directory)
            c=Context(dict(operation='build',privateRoot=str(root/'private'),library=str(root/'library'),
                resources=str(root/'resources'),gameId=TITLE))
            c.library.mkdir(parents=True)
            work=c.library/'cache'/'macos';work.mkdir(parents=True)
            repo=work/'engine';(repo/'dm/gfx/nvn').mkdir(parents=True);(repo/'dm/tools').mkdir();(repo/'dm/games').mkdir()
            (repo/'dm/gfx/nvn/dmsh_chain.h').write_text('#define DMSH_CHAIN "'+CHAIN+'"\n')
            (repo/'dm/tools/nacp.py').write_text('LANGUAGES=[]\ndef version(p): return "1.0"\n')
            (repo/'dm/games/profile_guess.py').write_text('def main_modules(*a): return {}\ndef build_sources(*a): return {}\n')
            profile=repo/'dm/games'/TITLE;profile.mkdir()
            (profile/'game.tsv').write_text('package\tv0\nmodules\tmain\ngraphics\tnvn\n')
            (profile/'shader_map.tsv').write_text('vs_data.bin\t0\tvs\tkey\tsynthetic\n')
            game=dict(id=TITLE,packages=[])
            items=(('base','base',TITLE,0),)+((('dlc-one','dlc','0100000000011001',0),) if dlc else ())
            for name,kind,tid,version in items:
                path=c.library/(name+'.nsp');path.write_text('synthetic '+name)
                game['packages'].append(dict(type=kind,titleId=tid,version=version,path=path.name,
                    size=path.stat().st_size,sha256=digest(path),builds={'main':'fixture'}))
            c.save_catalog({'games':[game]})
            calls={}
            def extract(nx,keys,dst,version,base,update,extra,logs,gp,**kw):
                d=dst/version;(d/'ExeFS').mkdir(parents=True);(d/'ExeFS/main').write_text('code')
                (d/'RomFS').mkdir();(d/'RomFS/marker').write_text('asset');(d/'control.nacp').write_text('nacp')
            def extract_aoc(nx,keys,engine,build_root,app,family,logs):
                for tid,version,path in family['dlc']:
                    dst=build_root/'aoc'/str(tid-app-0x1000);dst.mkdir(parents=True);(dst/'data').write_text('dlc')
            def rewrite(py,engine,exefs,out,env,logs,gp):
                out.mkdir();(out/'main.patched.bin').write_text('code')
            def derive_profile(gp,folder,ver,d,mods,app=None,shader_only=False):
                folder.mkdir(parents=True,exist_ok=True)
                (folder/'game.tsv').write_text('package\t'+ver+'\nmodules\tmain\ngraphics\tnvn\n')
                calls['derived']=dict(version=ver,modules=mods,shader_only=shader_only)
                return Profile(folder)
            def split_shaders(py,engine,roms,mains,pkg,env,logs,gp,provisional=False,oodle=None,dlc_roms=(),derive_dlc=None,derive_compute=None):
                calls['split']=dict(dlc_roms=list(dlc_roms),derive_dlc=derive_dlc)
                pkg.mkdir(parents=True,exist_ok=True);(pkg/'shader.bin').write_text('shaders')
                if derive_dlc is not None:
                    calls['profile']=derive_dlc()
                    for name in ('shader_map.tsv','shader_facts.tsv','shader_pairs.tsv'):
                        if (gp.dir/name).is_file(): (calls['profile'].dir/name).write_text((gp.dir/name).read_text())
                return 'key'
            class Prog:
                def stage(self,*a,**kw): pass
                def watch(self,*a): pass
                def set(self,**kw): pass
                def end(self,*a): pass
            upstream=SimpleNamespace(extract=extract,extract_aoc=extract_aoc,rewrite=rewrite,
                derive_profile=derive_profile,split_shaders=split_shaders,PROG=Prog())
            gp=Profile(profile)
            env=c.env()
            prepared=(work,repo,env,upstream,gp,'fixture')
            def host(*a):
                (work/'tools').mkdir(parents=True,exist_ok=True)
                path=work/'tools'/'dmhost';path.write_text('host');return path
            def tool_run(args,log=None,env=None,**kw):
                script=Path(args[1])
                if script.name=='dmsh_build.py':
                    folder=work/'shader'/'cache'/('b-'+CHAIN);folder.mkdir(parents=True,exist_ok=True)
                    (folder/'key_b.metallib').write_text('library');(folder/'key_b.json').write_text(json.dumps(dict(chain=CHAIN)))
                    (folder/'inputs.tsv').write_text('game\t'+TITLE+'\ninputs\t'+STAMP+'\n')
                    for name in ('c1_full.tsv','cb_extent.tsv'):
                        (profile/name).write_text('# chain b-'+CHAIN+' inputs '+STAMP+' synthetic\n')
                elif script.name=='make_ext_font.py': Path(args[2]).write_text('font')
                else: raise AssertionError(args)
            with contextlib.redirect_stdout(io.StringIO()),patch('build.prepare',return_value=prepared),\
                 patch.object(c,'nx',return_value=root/'reader'),patch.object(c,'run',side_effect=tool_run),\
                 patch('build.shutil.disk_usage',return_value=SimpleNamespace(free=100*2**30)),\
                 patch('build.compile_host',side_effect=host),\
                 patch('build.install',return_value={'path':'installed'}):
                build.build(c,'macos')
            return calls,env,work
    def test_installed_dlc_derives_a_shader_only_profile(self):
        calls,env,work=self.build(dlc=True)
        self.assertIsNotNone(calls['split']['derive_dlc'])
        self.assertTrue(calls['split']['dlc_roms'])
        self.assertTrue(calls['derived']['shader_only'])
        self.assertEqual(calls['derived']['version'],'v0')
        self.assertEqual(calls['profile'].dir,work/'profiles'/TITLE)
        self.assertEqual(env['DM_GAMES_DIR'].split(':')[0],str(work/'profiles'))
        self.assertEqual(env['DM_GAMES_FIRST'],'1')
    def test_without_dlc_the_registered_profile_is_kept(self):
        calls,env,work=self.build(dlc=False)
        self.assertIsNone(calls['split']['derive_dlc'])
        self.assertNotIn('derived',calls)


if __name__=='__main__': unittest.main()
