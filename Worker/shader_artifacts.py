"""Read nxnative shader libraries in either their on-disk or image layout."""
from functools import cache
import json
from pathlib import Path
import sys

from core import Failure


@cache
def image_reader():
    from derived import module
    tools = Path(__file__).resolve().parents[1]/'Engine/nxnative/dm/tools'
    return module(tools/'romfs.py', 'lumanx_shader_romfs')


def library_view(cache_dir, chain):
    folder = Path(cache_dir)/('b-'+chain)
    image = folder.with_suffix('.img')
    # Match nxnative's shader_lib.view preference for a stamped full build.
    if image.is_file() and not (folder/'inputs.tsv').is_file():
        return image_reader().Path(image)
    return folder


def validate_library(cache_dir, chain, *, ios=False):
    if not chain:
        raise Failure('Metal 着色器缓存不完整或版本不一致。')
    try:
        library = library_view(cache_dir, chain)
        reflections = list(library.glob('*_b.json'))
        for reflection in reflections:
            record = json.loads(reflection.read_text())
            if (not isinstance(record, dict) or record.get('chain') != chain
                    or not reflection.with_suffix('.metallib').is_file()
                    or (ios and 'iphoneos' not in str(record.get('chain_metal', '')))):
                raise ValueError('invalid shader reflection or library')
    except (OSError, ValueError) as error:
        raise Failure('Metal 着色器缓存不完整或版本不一致。') from error
    if not reflections:
        raise Failure('Metal 着色器缓存缺失。')


def generate_tables(c, repo, library, table, log, env):
    tools = repo/'dm/gfx/tools'
    if (repo/'dm/tools/shader_lib.py').is_file():
        for script, name in (('c1_guard.py', 'c1_full.tsv'), ('cb_extent.py', 'cb_extent.tsv')):
            c.run([sys.executable, tools/script, library, table(name)], log, env)
    else:
        c.run([sys.executable, Path(__file__).with_name('c1_generate.py'), tools/'c1_guard.py',
               library, table('c1_full.tsv')], log, env)
