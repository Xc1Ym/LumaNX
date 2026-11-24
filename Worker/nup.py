"""Keyless NUP imports using the bundled nxnative parser and image packer."""
from contextlib import contextmanager, suppress
from pathlib import Path
import hashlib
import os
import shutil
import struct
import tempfile
from core import Failure, contained, digest, profiles
from derived import module

MAX_ICON_BYTES=4*2**20
MAX_CONTROL_BYTES=64*2**20
NACP_BYTES=0x4000


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
        n.verified_files=set()
        class Checked:
            def __init__(self,out): self.out=out
            def write(self,data):
                c.check();return self.out.write(data)
        def checked_copy(i,out):
            result=copy(i,Checked(out));n.verified_files.add(i);return result
        n.copy=checked_copy
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
    module_ids = {}
    for version,k in ([(0,base)] if base is not None else [])+sorted(updates.items()):
        # NUP producers use either the application ID (upstream fixtures) or
        # the update title ID. Both must identify this application's family.
        if version and k.title_id not in (app,app+0x800):
            raise Failure('NUP 更新包的 Title ID 与本体不一致。')
        if k.exefs==parser.NO_DIR: raise Failure('解包目录缺少有效的 NSO 代码模块。')
        builds={}
        for name,isdir,i in n.children(k.exefs):
            if isdir or (i in n.verified_files and i not in module_ids): continue
            if i not in module_ids:
                data=Prefix(c,0x100);n.copy(i,data)
                module_ids[i] = data.data[0x40:0x50].hex() if len(data.data)==0x100 and data.data[:4]==b'NSO0' else None
            if module_ids[i] is not None:
                builds[os.fsdecode(name)] = module_ids[i]
        # A profile can list modules from multiple versions. Registered build
        # rows describe the code each individual package actually ships.
        registered = profile['builds'].get(f'v{version}', {})
        required = {'main'} | (set(registered) - {'display'})
        if not required.issubset(builds):
            raise Failure('解包目录缺少有效的 NSO 代码模块。')
        # Check the profile marker without unpacking a potentially huge RomFS.
        directory=parser.romfs_of(k,base)
        marker=profile.get('romfs_marker','')
        isdir=True
        for part in Path(marker).parts:
            if not isdir: raise Failure('游戏资源缺少配置指定的文件。')
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


def copy_source(c,source,destination):
    """Read the player file once, hashing exactly the bytes written to staging."""
    source=Path(source)
    if source.is_symlink(): raise Failure('不接受指向游戏库之外的符号链接。')
    h=hashlib.sha256();done=0
    with source.open('rb') as src,destination.open('xb') as dst:
        before=os.fstat(src.fileno())
        while block:=src.read(8<<20):
            c.check();dst.write(block);h.update(block);done+=len(block);c.progress(done,before.st_size)
            if done>before.st_size: raise Failure('复制后校验失败，原始文件未改动。')
        after=os.fstat(src.fileno())
        stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if done!=before.st_size or stamp(before)!=stamp(after) or stamp(after)!=stamp(source.stat()):
            raise Failure('复制后校验失败，原始文件未改动。')
    c.check();return h.hexdigest(),done


def control_data(c,parser,n,selected):
    # Bound metadata before upstream materializes TLV payloads. Bad optional
    # names/artwork use the profile name/default cover rather than UI file data.
    if any(k.meta_size>MAX_CONTROL_BYTES for k in n.packages):
        raise Failure('NUP 控制数据超过大小限制。')
    with tempfile.TemporaryDirectory(prefix='nup-meta-',dir=c.private) as directory:
        meta=Path(directory)
        fallback=parser.app_package(n) if hasattr(parser,'app_package') else None
        parser.control(selected,meta,fallback)
        nacp=module(c.engine/'dm/tools/nacp.py','lumanx_nup_nacp')
        control=meta/'control.nacp';name=display=''
        if control.is_file() and control.stat().st_size==NACP_BYTES:
            name=nacp.name(control);display=nacp.version(control)
        icon=meta/'icon.jpg';data=None
        if icon.is_file() and 0<icon.stat().st_size<=MAX_ICON_BYTES:
            with icon.open('rb') as stream: header=stream.read(8)
            if header.startswith(b'\xff\xd8\xff') or header==b'\x89PNG\r\n\x1a\n': data=icon.read_bytes()
        return name,display,data


def save_with_cover(c,cat,cover,icon):
    """Publish catalogue and optional artwork together, restoring the old cover
    on a failed save or cancellation. Temporary files never outlive the attempt."""
    cover.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.cover-',dir=cover.parent) as directory:
        previous=Path(directory)/'previous';candidate=Path(directory)/'candidate'
        if icon: candidate.write_bytes(icon)
        c.check();replaced=False
        try:
            if cover.exists(): cover.replace(previous)
            if icon: candidate.replace(cover);replaced=True
            c.check();c.save_catalog(cat)
        except BaseException:
            if replaced: cover.unlink(missing_ok=True)
            if previous.exists(): previous.replace(cover)
            raise


def package_key(package):
    return f"{package['type']}:{package['version']}:{package['titleId']}"


def select_packages(c, parser, container, selection):
    app, base, updates, dlc = parser.scan(container)
    if container.siblings:
        raise Failure('此 NUP 包含多个程序，需要完整导入。')
    candidates = {}
    if base is not None:
        candidates[f'base:0:{app:016X}'] = base
    candidates.update({f'update:{version}:{app + 0x800:016X}': package for version, package in updates.items()})
    candidates.update({f'dlc:{package.version}:{title:016X}': package for title, package in dlc.items()})
    if not isinstance(selection, list) or not selection or any(not isinstance(key, str) or key not in candidates for key in selection):
        raise Failure('所选 NUP 内容已变化，请重新扫描。')
    chosen = [package for key, package in candidates.items() if key in selection]
    if not any(package.kind in (parser.BASE, parser.UPDATE) for package in chosen):
        raise Failure('请选择本体或更新。')
    if base not in chosen and any(package.kind == parser.UPDATE and package.romfs == parser.NO_DIR for package in chosen):
        raise Failure('此更新需要同一 NUP 中的本体资源，请同时选择本体。')
    return chosen


def import_game(c,path):
    c.begin('校验 NUP 游戏容器')
    sources=contained(c.library,c.library/'sources')
    selections = c.r.get('nupSelections', {})
    if not isinstance(selections, dict): raise Failure('无效的 NUP 内容选择。')
    selection = selections.get(str(path))
    with tempfile.TemporaryDirectory(prefix='.nup-',dir=sources) as directory:
        stage=Path(directory)/'source.nup'
        if selection is None:
            if shutil.disk_usage(sources).free<Path(path).stat().st_size+512*2**20:
                raise Failure('游戏库可用空间不足，复制尚未开始。')
            c.begin('复制游戏文件到游戏库');sha,size=copy_source(c,path,stage)
        else:
            from nup_subset import write
            before = path.stat()
            with opened(c, path) as (parser, container):
                chosen = select_packages(c, parser, container, selection)
                write(c, parser, container, chosen, stage)
            after = path.stat()
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                raise Failure('复制期间源文件发生变化，请重新扫描。')
            size = stage.stat().st_size
            sha = digest(stage, c.progress)
        return register(c,path,stage,sha,size)


def register(c,path,stage,sha,size):
    from library import requirements
    c.begin('校验 NUP 游戏容器')
    with opened(c,stage) as (parser,n):
        tid,profile,packages=metadata(c,parser,n)
        # Validate every payload, including DLC and versions not selected to run.
        for i in range(len(n.files)):
            if i not in n.verified_files: n.copy(i,Prefix(c))
        expanded=sum(f[1] for f in n.files)
        selected=max((k for k in n.packages if k.kind in (parser.BASE,parser.UPDATE) and k.exefs!=parser.NO_DIR),key=lambda k:k.version)
        name,display,icon=control_data(c,parser,n,selected)
        retail_origin = 'control' if display else 'container label'
        if not display and hasattr(parser, 'display_label'):
            candidate = parser.display_label(selected)
            if isinstance(candidate, str):
                import re
                if re.fullmatch(r'[vV]?\d+\.\d+(?:\.\d+){0,2}', candidate.strip()):
                    display = candidate.strip()
        name=name or profile['name']
    with c.lock():
        cat=c.catalog();game=next((g for g in cat['games'] if g['id']==tid),None)
        if game and game['packages'] and game.get('sourceKind')!='nup':
            raise Failure('同一游戏不能混用 NUP 与其他来源，请先清理托管源文件。')
        parent=contained(c.library,c.library/'sources'/tid);parent.mkdir(parents=True,exist_ok=True)
        dest=contained(parent,parent/f'{tid}_{sha}.nup')
        if dest.exists():
            if not dest.is_file() or digest(dest,c.progress)!=sha: raise Failure('托管源文件已丢失或内容发生改变，请重新导入。')
        for p in packages:
            p.update(sourceKind='nup',metadataSchema=2,path=str(dest.relative_to(c.library)),size=size,sha256=sha,name=name,sourceFilename=Path(path).name,sourceExpandedSize=expanded)
        newest=max((p for p in packages if p['type']!='dlc'),key=lambda p:p['version'])
        if display:
            newest.update(display=display, retailVersionSource=retail_origin)
        if game:
            replaced = {package_key(package) for package in packages}
            retained = [package for package in game['packages']
                        if package_key(package) not in replaced and contained(c.library, c.library / package['path']).is_file()]
            packages = sorted(retained + packages, key=lambda p: (p['type'] == 'dlc', p['version'], p['titleId']))
            if not icon and retained:
                cover_path = c.library / 'games' / tid / 'cover.jpg'
                if cover_path.is_file(): icon = cover_path.read_bytes()
        newest = max((p for p in packages if p['type'] != 'dlc'), key=lambda p: p['version'])
        expanded = sum({p['path']: p.get('sourceExpandedSize', p['size']) for p in packages}.values())
        duplicate=bool(game and game['packages']==packages)
        if game is None:
            game=dict(id=tid,packages=[]);cat['games'].append(game)
        cover=c.library/'games'/tid/'cover.jpg'
        game.update(sourceKind='nup',name=name,packages=packages,hidden=False,display=newest['display'],
            compatibility=profile['compatibility'],cover=str(cover.relative_to(c.library)) if icon else '',sourceExpandedSize=expanded)
        game['missing']=requirements(game,profile)
        c.check();created=False
        try:
            if not dest.exists(): stage.rename(dest);created=True
            save_with_cover(c,cat,cover,icon)
        except BaseException:
            if created: dest.unlink(missing_ok=True)
            raise
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


def extract_registered_dlc(c, packages, destination):
    groups = {}
    for package in packages:
        if package['type'] == 'dlc':
            groups.setdefault(package['path'], set()).add(int(package['titleId'], 16))
    destination.mkdir(parents=True)
    for source, titles in groups.items():
        with opened(c, contained(c.library, c.library / source)) as (parser, container):
            _, _, _, dlc = parser.scan(container)
            for title in sorted(titles):
                c.check()
                if title not in dlc: raise Failure('NUP 中缺少已登记的 DLC。')
                image = destination / f'{title - container.aoc_base}.img'
                if image.exists(): raise Failure('NUP DLC 索引冲突。')
                parser.pack(container, dlc[title].romfs, image, say=lambda _: c.check(), step=lambda _: c.check())
    if not groups: (destination / '.empty').write_text('no DLC')
