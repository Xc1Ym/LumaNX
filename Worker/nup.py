"""Keyless NUP imports using the bundled nxnative parser and image packer."""
from contextlib import contextmanager, suppress
from pathlib import Path
import os
import shutil
import struct
import tempfile
from core import Failure, clone, contained, digest, profiles
from derived import module


@contextmanager
def opened(c, path):
    parser_path=c.engine/'scripts/pack_nup.py'
    if not parser_path.is_file(): raise Failure('当前引擎不支持 NUP，请更新璃游。')
    parser=module(parser_path,'lumanx_pack_nup')
    # A worker may inspect more than one snapshot in its lifetime. Bind the
    # packer's dependency to this source tree, rather than sys.modules' first one.
    parser.romfs_image=module(c.engine/'dm/tools/romfs_image.py','lumanx_nup_romfs_image')
    try:
        n=parser.Nup(path)
        copy=n.copy
        class Checked:
            def __init__(self,out): self.out=out
            def write(self,data):
                c.check();return self.out.write(data)
        n.copy=lambda i,out:copy(i,Checked(out))
        try: yield parser,n
        except BaseException:
            # A cancelled/failed streamed read may retain mmap views in its
            # traceback. Preserve that error; views close when it unwinds.
            with suppress(BufferError): n.close()
            raise
        else: n.close()
    except (parser.Error,OSError,ValueError,struct.error,IndexError,RecursionError,BufferError) as error:
        raise Failure('NUP 文件无效或内容校验失败：'+str(error)) from error


class Prefix:
    def __init__(self,c,limit=0): self.c=c;self.limit=limit;self.data=bytearray()
    def write(self,data):
        self.c.check()
        self.data.extend(data[:max(0,self.limit-len(self.data))])


def metadata(c, parser, n):
    app,base,updates,dlc=parser.scan(n);tid=f'{app:016X}'
    profile=profiles(c.engine).get(tid)
    if not profile: raise Failure('已解包游戏需要 nxnative 已适配的游戏配置。')
    packages=[]
    for version,k in ([(0,base)] if base is not None else [])+sorted(updates.items()):
        if k.exefs==parser.NO_DIR: raise Failure('解包目录缺少有效的 NSO 代码模块。')
        builds={}
        for name,isdir,i in n.children(k.exefs):
            if isdir: continue
            data=Prefix(c,0x100);n.copy(i,data)
            if len(data.data)==0x100 and data.data[:4]==b'NSO0': builds[os.fsdecode(name)]=data.data[0x40:0x50].hex()
        if any(m not in builds for m in profile.get('modules','main').split()):
            raise Failure('解包目录缺少有效的 NSO 代码模块。')
        # Check the profile marker without unpacking a potentially huge RomFS.
        directory=parser.romfs_of(k,base)
        marker=profile.get('romfs_marker','')
        for part in Path(marker).parts:
            child=next(((isdir,i) for name,isdir,i in n.children(directory) if name==os.fsencode(part)),None)
            if child is None: raise Failure('游戏资源缺少配置指定的文件。')
            isdir,directory=child
        if marker and isdir: raise Failure('游戏资源缺少配置指定的文件。')
        packages.append(dict(titleId=tid if version==0 else f'{app+0x800:016X}',baseId=tid,
            type='base' if version==0 else 'update',version=version,name=profile['name'],
            display=profile['builds'].get(f'v{version}',{}).get('display',f'v{version}'),builds=builds))
    packages.extend(dict(titleId=f'{title:016X}',baseId=tid,type='dlc',version=k.version,
                         name=profile['name'],display='',builds={}) for title,k in sorted(dlc.items()))
    return tid,profile,packages


def import_game(c,path):
    from library import requirements
    c.begin('校验 NUP 游戏容器')
    sha=digest(path,c.progress)
    with opened(c,path) as (parser,n):
        tid,profile,packages=metadata(c,parser,n)
        # Validate every payload, including DLC and versions not selected to run.
        for i in range(len(n.files)): n.copy(i,Prefix(c))
        expanded=sum(f[1] for f in n.files)
        selected=max((k for k in n.packages if k.kind in (parser.BASE,parser.UPDATE) and k.exefs!=parser.NO_DIR),key=lambda k:k.version)
        with tempfile.TemporaryDirectory(prefix='nup-meta-',dir=c.private) as directory:
            meta=Path(directory)
            fallback=parser.app_package(n) if hasattr(parser,'app_package') else None
            parser.control(selected,meta,fallback)
            nacp=module(c.engine/'dm/tools/nacp.py','lumanx_nup_nacp')
            name=nacp.name(meta/'control.nacp') or profile['name']
            display=nacp.version(meta/'control.nacp')
            icon=(meta/'icon.jpg').read_bytes() if (meta/'icon.jpg').is_file() else None
    c.begin('正在校验源文件内容')
    if digest(path,c.progress)!=sha: raise Failure('复制后校验失败，原始文件未改动。')
    with c.lock():
        cat=c.catalog();game=next((g for g in cat['games'] if g['id']==tid),None)
        if game and game['packages'] and game.get('sourceKind')!='nup':
            raise Failure('同一游戏不能混用 NUP 与其他来源，请先清理托管源文件。')
        parent=contained(c.library,c.library/'sources'/tid);parent.mkdir(parents=True,exist_ok=True)
        dest=contained(parent,parent/f'{tid}_{sha}.nup')
        if dest.exists():
            if not dest.is_file() or digest(dest,c.progress)!=sha: raise Failure('托管源文件已丢失或内容发生改变，请重新导入。')
        else:
            if shutil.disk_usage(parent).free<Path(path).stat().st_size+512*2**20:
                raise Failure('游戏库可用空间不足，复制尚未开始。')
            c.begin('复制游戏文件到游戏库')
            with tempfile.TemporaryDirectory(prefix='.nup-',dir=parent) as directory:
                stage=Path(directory)/'content';clone(path,stage,c.progress)
                if digest(stage,c.progress)!=sha or digest(path,c.progress)!=sha:
                    raise Failure('复制后校验失败，原始文件未改动。')
                c.check();stage.rename(dest)
        for p in packages:
            p.update(sourceKind='nup',metadataSchema=2,path=str(dest.relative_to(c.library)),size=dest.stat().st_size,sha256=sha,name=name)
        newest=max((p for p in packages if p['type']!='dlc'),key=lambda p:p['version'])
        if display: newest['display']=display
        duplicate=bool(game and game['packages']==packages)
        if game is None:
            game=dict(id=tid,packages=[]);cat['games'].append(game)
        cover=c.library/'games'/tid/'cover.jpg'
        if icon:
            cover.parent.mkdir(parents=True,exist_ok=True)
            temporary=cover.with_suffix('.partial');temporary.write_bytes(icon);os.replace(temporary,cover)
        else: cover.unlink(missing_ok=True)
        game.update(sourceKind='nup',name=name,packages=packages,hidden=False,display=newest['display'],
            compatibility=profile['compatibility'],cover=str(cover.relative_to(c.library)) if icon else '',sourceExpandedSize=expanded)
        game['missing']=requirements(game,profile)
        c.check();c.save_catalog(cat)
    return dict(name=Path(path).name,duplicate=duplicate,id=tid)


def extract(c,source,version,destination):
    with opened(c,source) as (parser,n):
        app,base,updates,_=parser.scan(n)
        package=base if version==0 else updates.get(version)
        if package is None: raise Failure('NUP 中缺少所需游戏版本。')
        parser.pack_version(n,package,base,app,destination,say=lambda s:c.check())


def extract_dlc(c,source,destination):
    with opened(c,source) as (parser,n):
        app,_,_,dlc=parser.scan(n)
        destination.mkdir(parents=True)
        parser.pack_dlc(n,app,dlc,destination,say=lambda s:c.check())
        if not dlc: (destination/'.empty').write_text('no DLC')
