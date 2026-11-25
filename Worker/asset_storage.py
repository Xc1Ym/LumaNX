"""Opt-in asset compression; transactional replacement of a capable runtime."""
import ctypes,os,shutil,time,uuid
from pathlib import Path
from core import Failure,atomic,read,clone,clone_tree,contained
from recovery import game_root
import compressed_assets as assets

def image_files(runtime):
    root=Path(runtime);files=[]
    if (root/'romfs.img').is_file():files.append(root/'romfs.img')
    files.extend(sorted((root/'aoc').glob('*.img')))
    return files

def convert_files(c,runtime,enabled):
    files=image_files(runtime)
    if enabled and not files:raise Failure('This game uses asset folders. Compression currently requires image assets.')
    for index,p in enumerate(files):
        if assets.is_compressed(p)==enabled:continue
        c.begin('Compress game assets' if enabled else 'Restore uncompressed game assets',index+1,len(files))
        temporary=p.with_name(p.name+'.converted')
        assets.convert(c,p,temporary,enabled);c.check();os.replace(temporary,p)

def change(c,enabled):
    from build import validate_runtime
    from incremental import runtime_inventory
    with c.lock('execution'),c.lock():
        game=c.game();root=game_root(c,'games',game['id']);current=root/'current'
        manifest=read(current/'manifest.json',{})
        capable=bool(manifest.get('assetCompressionReader')==1 and (current/'dmhost').is_file() and assets.host_supports(current/'dmhost'))
        if not capable:
            game['assetCompressionRequested']=enabled
            cat=c.catalog();next(g for g in cat['games'] if g['id']==game['id'])['assetCompressionRequested']=enabled;c.save_catalog(cat)
            return dict(requiresPreparation=enabled,assetCompressionRequested=enabled)
        source=contained(root,current.resolve());validate_runtime(source)
        if bool(manifest.get('assetCompression'))==enabled:
            cat=c.catalog();next(g for g in cat['games'] if g['id']==game['id'])['assetCompressionRequested']=enabled;c.save_catalog(cat)
            return dict(assetCompression=enabled)
        if not current.is_symlink():raise Failure('Prepare this legacy runtime before changing asset storage.')
        original=runtime_inventory(c,source)
        if manifest.get('artifacts') and original!=manifest['artifacts']:raise Failure('Runtime integrity check failed; current game was kept.')
        before={p:assets.identity(p) for p in source.rglob('*') if p.is_file()}
        def logical_size(p):
            if not assets.is_compressed(p):return p.stat().st_size
            with assets.Reader(p) as reader:return reader.size
        # APFS clones do not duplicate the unchanged runtime. Probe in the
        # destination filesystem; reserve a full copy only when cloning fails.
        probe=root/('.asset-clone-probe-'+uuid.uuid4().hex)
        try:
            clones=ctypes.CDLL(None,use_errno=True).clonefile(os.fsencode(source/'manifest.json'),os.fsencode(probe),0)==0 if hasattr(ctypes.CDLL(None),'clonefile') else False
        finally:probe.unlink(missing_ok=True)
        required=sum(logical_size(p) for p in image_files(source))
        if not clones:required+=sum(p.stat().st_size for p in source.rglob('*') if p.is_file())
        if shutil.disk_usage(root).free<required+(256<<20):raise Failure('Not enough local space to verify a replacement asset image. Existing game was kept.')
        releases=root/'releases';releases.mkdir(exist_ok=True);stage=releases/('.assets-'+uuid.uuid4().hex);target=None
        try:
            clone_tree(source,stage,c.progress);convert_files(c,stage,enabled)
            manifest.update(assetCompression=enabled,artifacts=runtime_inventory(c,stage));atomic(stage/'manifest.json',manifest);validate_runtime(stage)
            c.check()
            if current.resolve()!=source or any(assets.identity(p)!=v for p,v in before.items()):raise Failure('Runtime changed during conversion; original kept.')
            target=releases/('assets-'+str(time.time_ns()));stage.rename(target)
            link=root/('current.assets-'+uuid.uuid4().hex);link.symlink_to(target.relative_to(root),target_is_directory=True);os.replace(link,current)
            cat=c.catalog();next(g for g in cat['games'] if g['id']==game['id'])['assetCompressionRequested']=enabled;c.save_catalog(cat)
            # Only retire the replaced active runtime after verification and activation.
            try:shutil.rmtree(source)
            except OSError:c.emit('message','New runtime is active; some previous release files could not be removed.')
            return dict(assetCompression=enabled,path=str(target))
        finally:
            if stage.exists():shutil.rmtree(stage)

def compress(c):return change(c,True)
def uncompress(c):return change(c,False)
