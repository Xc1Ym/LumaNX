"""Verified compressed compiled-runtime archives; saves remain in the local library."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import uuid
import zipfile

from core import Failure, atomic, clone, contained, digest, read
from recovery import game_root, inventory, backup_manifest


def _copy(c, source, destination, expected):
    destination.mkdir(mode=0o700)
    for name in expected['directories']:(destination/name).mkdir(parents=True,exist_ok=True,mode=0o700)
    total=sum(v['size'] for v in expected['files'].values());done=0
    for name,item in expected['files'].items():
        c.check();clone(source/name,destination/name,lambda n,t:c.progress(done+n,total))
        with (destination/name).open('rb') as stream:os.fsync(stream.fileno())
        done+=item['size']


def _space(path, expected):
    needed=sum(v['size'] for v in expected['files'].values())+64*2**20
    if shutil.disk_usage(path).free<needed:raise Failure('Not enough free space. The local game and saves were kept.')


def _record(c, game_id, entry):
    catalog=c.catalog();game=next(g for g in catalog['games'] if g['id']==game_id)
    game['runtimeArchive']=entry;c.save_catalog(catalog)


def _zip(c, source, target, expected):
    total=sum(v['size'] for v in expected['files'].values());done=0
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as archive:
        for name,item in expected['files'].items():
            c.check();info=zipfile.ZipInfo.from_file(source/name,'data/'+name)
            info.compress_type=zipfile.ZIP_DEFLATED
            with (source/name).open('rb') as incoming,archive.open(info,'w',force_zip64=True) as outgoing:
                while block:=incoming.read(8<<20):
                    c.check();outgoing.write(block);done+=len(block);c.progress(done,total)
    with target.open('rb') as stream:os.fsync(stream.fileno())


def _zip_files(archive, expected):
    names=archive.namelist();wanted={'data/'+name for name in expected['files']}
    if len(names)!=len(wanted) or set(names)!=wanted:raise Failure('The compressed archive file list is invalid.')
    for name,item in expected['files'].items():
        info=archive.getinfo('data/'+name)
        if info.file_size!=item['size']:raise Failure('The compressed archive file size is invalid.')


def _unzip(c, source, expected, destination=None):
    total=sum(v['size'] for v in expected['files'].values());done=0
    if destination:
        destination.mkdir(mode=0o700)
        for name in expected['directories']:(destination/name).mkdir(parents=True,exist_ok=True,mode=0o700)
    try:
        with zipfile.ZipFile(source,'r') as archive:
            _zip_files(archive,expected)
            for name,item in expected['files'].items():
                c.check();h=hashlib.sha256();out=None
                try:
                    if destination:out=(destination/name).open('wb')
                    with archive.open('data/'+name) as stream:
                        while block:=stream.read(8<<20):
                            c.check();h.update(block)
                            if out:out.write(block)
                            done+=len(block);c.progress(done,total)
                    if out:out.flush();os.fsync(out.fileno())
                finally:
                    if out:out.close()
                if h.hexdigest()!=item['sha256']:raise Failure('The compressed runtime failed checksum verification. Local saves were kept.')
                if destination:
                    mode=(archive.getinfo('data/'+name).external_attr>>16)&0o777
                    (destination/name).chmod(mode|0o600)
    except (zipfile.BadZipFile,RuntimeError,EOFError) as error:
        raise Failure('The compressed archive is damaged. Local saves were kept.') from error


def archive(c):
    from build import validate_runtime
    from runtime_payload import lean_copy
    with c.lock('execution'),c.lock():
        game=c.game();game_id=game['id'];local=game_root(c,'games',game_id);current=local/'current'
        if not current.exists():raise Failure('Prepare or restore a local compiled game before archiving it.')
        source=contained(local,current.resolve());validate_runtime(source)
        raw=c.r.get('archiveRoot','')
        if not isinstance(raw,str) or not raw.strip():raise Failure('Choose a NAS archive folder first.')
        chosen=Path(raw).expanduser()
        if chosen.is_symlink():raise Failure('Choose the archive folder itself, not a symbolic link.')
        destination=chosen.resolve();library=c.library.resolve()
        if destination==library or library in destination.parents or destination in library.parents:
            raise Failure('Choose an archive folder outside the local LumaNX library.')
        destination.mkdir(parents=True,exist_ok=True);root=destination/game_id
        if root.is_symlink():raise Failure('The archive game folder must not be a symbolic link.')
        root.mkdir(exist_ok=True)
        c.job['archiveRoot']=str(destination);atomic(c.jobpath,c.job)
        c.begin('Inspect compiled game for archive',1,5);original=inventory(c,source)
        temporary_root=game_root(c,'temp',game_id);temporary_root.mkdir(parents=True,exist_ok=True)
        # Clones keep the asset staging cheap on APFS; only the runtime shader
        # subset is rewritten. On other filesystems reserve a complete copy.
        _space(temporary_root,original)
        with tempfile.TemporaryDirectory(prefix='.runtime-archive-',dir=temporary_root) as local_tmp:
            c.begin('Package runtime-only shader assets',2,5)
            lean=lean_copy(c,source,Path(local_tmp)/'runtime');expected=inventory(c,lean)
            _space(root,expected)
            identifier=uuid.uuid4().hex;runtime=read(lean/'manifest.json',{})
            manifest=dict(schema=1,id=identifier,gameId=game_id,created=time.time(),reason='runtimeArchive',
                          kind='lumanx-runtime',storage='zip',name=game.get('name',game_id),version=runtime.get('version',''),**expected)
            manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
            manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
            final=root/identifier
            with tempfile.TemporaryDirectory(prefix='.archive-',dir=root) as temporary:
                stage=Path(temporary)/'snapshot';stage.mkdir(mode=0o700)
                c.begin('Compress compiled game to NAS',3,5);_zip(c,lean,stage/'runtime.zip',expected)
                c.begin('Verify compressed NAS archive',4,5);_unzip(c,stage/'runtime.zip',expected)
                if inventory(c,source)!=original:raise Failure('The local runtime changed during archive. Local files were kept.')
                with (stage / 'manifest.json').open('xb') as stream:
                    stream.write(manifest_bytes)
                    stream.flush()
                    os.fsync(stream.fileno())
                if (stage / 'manifest.json').read_bytes() != manifest_bytes:
                    raise Failure('The NAS archive manifest changed. No local files or saves were changed.')
                c.check()
                os.rename(stage, final)
            entry=dict(path=str(final),id=identifier,version=manifest['version'],created=manifest['created'],
                       size=(final/'runtime.zip').stat().st_size,runtimeSize=sum(v['size'] for v in expected['files'].values()),
                       manifestHash=manifest_hash,compressed=True)
            _record(c,game_id,entry);c.check()
            if current.resolve()!=source:raise Failure('The active runtime changed. Local files were kept; the NAS archive is verified.')
            c.begin('Release local compiled game space',5,5)
            if current.is_symlink():current.unlink();shutil.rmtree(source)
            else:
                retired=local/('.archived-'+identifier);current.rename(retired);shutil.rmtree(retired)
        return dict(archive=entry,savesKeptLocal=True)


def restore(c):
    from build import validate_runtime
    with c.lock('execution'),c.lock():
        game=c.game();game_id=game['id'];local=game_root(c,'games',game_id);current=local/'current'
        if current.exists():validate_runtime(current);return dict(path=str(current.resolve()),alreadyLocal=True)
        entry=game.get('runtimeArchive',{});raw=entry.get('path')
        if not isinstance(raw,str) or not raw:raise Failure('No compiled-game archive is registered for this game.')
        source=Path(raw)
        if not source.is_dir():raise Failure('The NAS archive is unavailable. Connect the share and retry; local saves were not changed.')
        if source.is_symlink():raise Failure('The archive must not be a symbolic link.')
        manifest_path = source / 'manifest.json'
        try:
            if manifest_path.is_symlink(): raise OSError('manifest is a symbolic link')
            manifest_bytes = manifest_path.read_bytes()
        except OSError as error:
            raise Failure('The NAS archive manifest changed. No local files or saves were changed.') from error
        if hashlib.sha256(manifest_bytes).hexdigest() != entry.get('manifestHash'):
            raise Failure('The NAS archive manifest changed. No local files or saves were changed.')
        manifest = backup_manifest(source, game_id, authenticated_bytes=manifest_bytes)
        if manifest.get('kind')!='lumanx-runtime':raise Failure('This is not a LumaNX compiled-game archive.')
        expected={k:manifest[k] for k in ('files','directories')}
        releases=local/'releases'
        if releases.is_symlink():raise Failure('The local release folder must not be a symbolic link.')
        releases.mkdir(parents=True,exist_ok=True);_space(releases,expected)
        with tempfile.TemporaryDirectory(prefix='.restore-',dir=releases) as temporary:
            stage=Path(temporary)/'runtime';c.begin('Restore and verify compiled game locally',1,2)
            if manifest.get('storage')=='zip':_unzip(c,source/'runtime.zip',expected,stage)
            else:
                if inventory(c,source/'data')!=expected:raise Failure('The NAS archive failed verification. Local saves were kept.')
                _copy(c,source/'data',stage,expected)
            c.begin('Verify restored game',2,2)
            if inventory(c,stage)!=expected:raise Failure('The restored copy failed verification. The NAS archive and saves were kept.')
            validate_runtime(stage);c.check()
            final=releases/('restored-'+uuid.uuid4().hex);stage.rename(final)
            link=local/'current.next';link.unlink(missing_ok=True);link.symlink_to(final.relative_to(local),target_is_directory=True);os.replace(link,current)
        return dict(path=str(final),archiveKept=True,savesKeptLocal=True)
