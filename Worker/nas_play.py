"""Publish a verified playable runtime to a mounted share."""
from pathlib import Path
import shutil
import tempfile
import uuid

from core import Failure, atomic, clone, contained, digest, read
from recovery import game_root, inventory
from runtime_archive import _copy, _space



def inventory_progress(c, expected=None, offset=0):
    """Report a stage-wide checksum total instead of resetting for each file."""
    done = 0
    positions = {}
    total = None if expected is None else 2 * sum(item['size'] for item in expected['files'].values())

    def report(path, count):
        nonlocal done
        done += count - positions.get(path, 0)
        positions[path] = count
        completed = offset + done
        c.progress(min(completed, total - 1) if total else completed, total)

    return report

def publish(c):
    from build import validate_runtime

    with c.lock('execution'), c.lock():
        game = c.game()
        local = game_root(c, 'games', game['id'])
        current = local / 'current'
        if not current.is_symlink() or not current.exists():
            raise Failure('Prepare a local runtime before publishing it to the NAS.')
        source = contained(local / 'releases', current.resolve(strict=True))
        validate_runtime(source)
        chosen = c.r.get('archiveRoot')
        if not isinstance(chosen, str) or not chosen:
            raise Failure('Choose a mounted NAS folder.')
        share = Path(chosen).expanduser()
        if share.is_symlink() or not share.is_dir():
            raise Failure('Choose a mounted NAS folder.')
        share = share.resolve(strict=True)
        library = c.library.resolve()
        if library == share or library in share.parents or share in library.parents:
            raise Failure('Choose a NAS folder outside the local LumaNX library.')

        c.job['archiveRoot'] = str(share)
        atomic(c.jobpath, c.job)
        identifier = uuid.uuid4().hex
        destination = share / game['id']
        if destination.is_symlink():
            raise Failure('The NAS game folder must not be a symbolic link.')
        destination.mkdir(exist_ok=True)
        remote = destination / identifier
        hosts = local / 'nas-hosts'
        if hosts.is_symlink():
            raise Failure('The local NAS host folder must not be a symbolic link.')
        hosts.mkdir(exist_ok=True)
        host = hosts / identifier / 'dmhost'
        c.begin('Inspect local runtime for NAS play', 1, 4)
        expected = inventory(c, source, inventory_progress(c))
        _space(destination, expected)
        with tempfile.TemporaryDirectory(prefix='.publishing-', dir=destination) as scratch:
            staging = Path(scratch) / 'runtime'
            c.begin('Copy playable runtime to NAS', 2, 4)
            _copy(c, source, staging, expected)
            c.begin('Verify playable NAS runtime', 3, 4)
            size = sum(item['size'] for item in expected['files'].values())
            if (inventory(c, staging, inventory_progress(c, expected)) != expected
                    or inventory(c, source, inventory_progress(c, expected, offset=size)) != expected):
                raise Failure('Runtime verification failed. The local runtime was kept.')
            # We validated the source and verified the destination byte for byte.
            host.parent.mkdir()
            clone(source / 'dmhost', host)
            host.chmod(0o755)
            c.check()
            staging.rename(remote)

        manifest = read(source / 'manifest.json')
        entry = dict(id=identifier, path=str(remote), manifestHash=expected['files']['manifest.json']['sha256'],
                     version=manifest['version'], assetCompression=bool(manifest.get('assetCompression')),
                     inputConfig=manifest.get('inputConfig', True))
        catalog = c.catalog()
        next(item for item in catalog['games'] if item['id'] == game['id'])['nasRuntime'] = entry
        c.save_catalog(catalog)
        c.begin('Release local compiled game space', 4, 4)
        if current.resolve() != source:
            raise Failure('The active runtime changed. The local runtime was kept.')
        # The verified NAS path is already registered if an interruption occurs
        # after unlinking current. An older release is never removed here.
        current.unlink()
        shutil.rmtree(source)
        return {'path': str(remote), 'savesKeptLocal': True}


def launch_paths(c, game, current):
    """Prefer a new local build. A published game uses its local host on launch."""
    if current.exists() or not game.get('nasRuntime'):
        return current, current / 'dmhost'
    entry = game['nasRuntime']
    remote = Path(entry['path'])
    manifest = remote / 'manifest.json'
    if not manifest.is_file() or remote.is_symlink():
        raise Failure('The playable NAS runtime is offline. Reconnect the share and retry.')
    if digest(manifest) != entry['manifestHash']:
        raise Failure('The playable NAS runtime manifest changed. Publish the runtime again.')
    if not (remote / 'modules').is_dir() or not (remote / 'shaders').is_dir() or not (
        (remote / 'romfs.img').is_file() or (remote / 'romfs').is_dir()
    ):
        raise Failure('The playable NAS runtime is incomplete. Publish the runtime again.')
    host = contained(current.parent / 'nas-hosts', current.parent / 'nas-hosts' / entry['id'] / 'dmhost')
    if not host.is_file():
        raise Failure('The local NAS game host is missing. Publish the runtime again.')
    return remote, host
