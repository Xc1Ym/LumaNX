"""Registered, decrypted game trees. Player files stay in the managed library."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import shutil
import stat
import struct
import tempfile
from core import Failure, clone, contained, digest, profiles


def is_dump(path):
    path=Path(path)
    return (path/'base/exefs/main.npdm').is_file() and (path/'base/romfs').is_dir()


def tree_entries(c, root):
    """Reject links and special files before reading or copying any file bytes."""
    root=Path(root)
    if root.is_symlink() or not root.is_dir(): raise Failure('解包目录无效或包含符号链接。')
    files={}; directories=[]
    for parent, dirs, names in os.walk(root, followlinks=False):
        c.check()
        for name in sorted(dirs+names):
            path=Path(parent)/name; mode=path.lstat().st_mode; rel=path.relative_to(root).as_posix()
            if stat.S_ISDIR(mode): directories.append(rel)
            elif stat.S_ISREG(mode):
                files[rel]=path.stat().st_size
            else: raise Failure('解包目录无效或包含符号链接。')
    return files,directories


def inventory(c, root):
    sizes,directories=tree_entries(c,root)
    total=sum(sizes.values());done=0;files={}
    for name,size in sorted(sizes.items()):
        files[name]=(size,digest(Path(root)/name,lambda n,t:c.progress(done+n,total)))
        done+=size
    h=hashlib.sha256()
    for directory in sorted(directories): h.update(b'D\0'+directory.encode()+b'\0')
    for name,(size,sha) in sorted(files.items()):
        h.update(b'F\0'+name.encode()+b'\0'+str(size).encode()+b'\0'+bytes.fromhex(sha))
    return dict(sha256=h.hexdigest(),size=sum(v[0] for v in files.values()),files=files,directories=directories)


def copy_tree(c, source, destination, expected=None):
    expected=expected or inventory(c,source)
    destination=Path(destination);destination.mkdir(parents=True)
    for name in expected['directories']:
        c.check();(destination/name).mkdir(parents=True,exist_ok=True)
    done=0;total=expected['size']
    for name,(size,sha) in expected['files'].items():
        c.check();clone(Path(source)/name,destination/name,lambda n,t:c.progress(done+n,total));done+=size
    if inventory(c,destination)!=expected or inventory(c,source)!=expected:
        raise Failure('复制后校验失败，原始文件未改动。')


def program_id(path):
    with Path(path).open('rb') as stream: data=stream.read(0x10000)
    if len(data)<0x80 or data[:4]!=b'META': raise Failure('解包目录的 main.npdm 无效。')
    off,size=struct.unpack_from('<II',data,0x70)
    if size<0x18 or off<0x80 or off+size>len(data) or data[off:off+4]!=b'ACI0':
        raise Failure('解包目录的 main.npdm 无效。')
    return f'{struct.unpack_from("<Q",data,off+0x10)[0]:016X}'


def scan(c, folder):
    """Validate all metadata before registering any content; no NSP reader or keys."""
    folder=Path(folder)
    # Check the whole source, including directory links, before reading metadata.
    tree_entries(c,folder)
    try: tid=program_id(folder/'base/exefs/main.npdm')
    except OSError: raise Failure('解包目录缺少 base/exefs/main.npdm。')
    if int(tid,16)&0xFFF: raise Failure('解包目录的程序标识不是游戏本体。')
    profile=profiles(c.engine).get(tid)
    if not profile: raise Failure('已解包游戏需要 nxnative 已适配的游戏配置。')
    packages=[]
    versions=[(0,folder/'base')]
    if (folder/'updates').exists():
        seen=set()
        for path in sorted((folder/'updates').iterdir()):
            if path.name.startswith('.'): continue
            if not path.is_dir() or not path.name.isascii() or not path.name.isdecimal() or not 0<int(path.name)<=0xffffffff or int(path.name) in seen:
                raise Failure('更新目录名必须是唯一的十进制版本号。')
            seen.add(int(path.name));versions.append((int(path.name),path))
    for version,path in versions:
        if not (path/'romfs').is_dir() or not (path/'exefs/main').is_file():
            raise Failure('解包目录缺少 exefs/main 或完整 romfs。')
        try:
            if program_id(path/'exefs/main.npdm')!=tid: raise Failure('更新与本体的程序标识不一致。')
        except OSError: raise Failure('解包目录的 main.npdm 无效。')
        builds={}
        for module in path.joinpath('exefs').iterdir():
            if not module.is_file(): continue
            with module.open('rb') as stream: header=stream.read(0x100)
            if header[:4]==b'NSO0' and len(header)==0x100: builds[module.name]=header[0x40:0x50].hex()
        # The base is kept even when only the updated build is registered upstream.
        required=profile.get('modules','main').split()
        if any(name not in builds for name in required): raise Failure('解包目录缺少有效的 NSO 代码模块。')
        marker=profile.get('romfs_marker')
        if marker and not (path/'romfs'/marker).is_file(): raise Failure('游戏资源缺少配置指定的文件。')
        packages.append(dict(titleId=tid if version==0 else f'{int(tid,16)+0x800:016X}',baseId=tid,
            type='base' if version==0 else 'update',version=version,name=profile['name'],
            display=profile['builds'].get(f'v{version}',{}).get('display',f'v{version}'),builds=builds,source=path))
    if (folder/'dlc').exists():
        seen=set()
        for path in sorted((folder/'dlc').iterdir()):
            if path.name.startswith('.'): continue
            try: dtid=int(path.name,16)
            except ValueError: raise Failure('DLC 目录名必须是该游戏的十六进制 Title ID。') from None
            if len(path.name)!=16 or not 0<dtid-int(tid,16)-0x1000<=2000 or dtid in seen:
                raise Failure('DLC 目录名必须是该游戏的十六进制 Title ID。')
            seen.add(dtid)
            roms=sorted(path.glob('*/romfs'))+([path/'romfs'] if (path/'romfs').is_dir() else [])
            if len(roms)!=1 or not roms[0].is_dir(): raise Failure('DLC 必须包含一个完整 romfs 目录。')
            packages.append(dict(titleId=f'{dtid:016X}',baseId=tid,type='dlc',version=0,
                name=profile['name'],display='',builds={},source=roms[0]))
    return tid,profile,packages


def import_game(c, folder):
    from library import requirements
    c.begin('校验已解包游戏目录')
    tid,profile,packages=scan(c,folder)
    with c.lock():
        cat=c.catalog();game=next((g for g in cat['games'] if g['id']==tid),None)
        if game and game['packages'] and game.get('sourceKind')!='dump':
            raise Failure('同一游戏不能混用游戏包和解包目录，请先清理托管源文件。')
        recorded=[]
        for package in packages:
            source=package.pop('source');expected=inventory(c,source)
            parent=contained(c.library,c.library/'sources'/tid);parent.mkdir(parents=True,exist_ok=True)
            dest=parent/f'{package["titleId"]}_v{package["version"]}_{expected["sha256"]}.dump'
            contained(parent,dest)
            if not dest.exists() or inventory(c,dest)!=expected:
                if dest.exists(): raise Failure('托管源文件已丢失或内容发生改变，请重新导入。')
                if shutil.disk_usage(parent).free<expected['size']+512*2**20:
                    raise Failure('游戏库可用空间不足，复制尚未开始。')
                c.begin('复制已解包游戏到游戏库')
                with tempfile.TemporaryDirectory(prefix='.dump-',dir=parent) as temporary:
                    stage=Path(temporary)/'content';copy_tree(c,source,stage,expected)
                    c.check();stage.rename(dest)
            recorded.append(package|dict(sourceKind='dump',metadataSchema=2,path=str(dest.relative_to(c.library)),
                size=expected['size'],treeSha256=expected['sha256'],sha256=package_hash(package,expected['sha256'])))
        duplicate=bool(game and game['packages']==recorded)
        if game is None:
            game=dict(id=tid,name=profile['name'],packages=[],hidden=False);cat['games'].append(game)
        game.update(sourceKind='dump',packages=recorded,hidden=False,display=max(
            (p for p in recorded if p['type']!='dlc'),key=lambda p:p['version'])['display'],
            compatibility=profile['compatibility'],cover='')
        game['missing']=requirements(game,profile)
        c.check();c.save_catalog(cat)
    return dict(name=Path(folder).name,duplicate=duplicate,id=tid)


def package_hash(package, tree_hash):
    # DLC trees do not carry a title/version header. Bind their mount identity as
    # well as their bytes so a different DLC never reuses the previous checkpoint.
    identity='\0'.join((package['titleId'],package['type'],str(package['version']),tree_hash))
    return hashlib.sha256(identity.encode()).hexdigest()


def verify(c, package):
    path=contained(c.library/'sources',c.library/package['path'])
    actual=inventory(c,path)
    if package_hash(package,actual['sha256'])!=package['sha256'] or actual['size']!=package['size']:
        raise Failure('托管源文件已丢失或内容发生改变，请重新导入。')
    return path


def extract(c, source, destination):
    """Updates already hold complete patched trees: never overlay the base."""
    destination.mkdir(parents=True)
    copy_tree(c,source/'exefs',destination/'ExeFS')
    copy_tree(c,source/'romfs',destination/'RomFS')


def extract_dlc(c, packages, destination, title):
    destination.mkdir()
    if not packages: (destination/'.empty').write_text('no DLC')
    for package in packages:
        copy_tree(c,contained(c.library/'sources',c.library/package['path']),
            destination/str(int(package['titleId'],16)-int(title,16)-0x1000))
