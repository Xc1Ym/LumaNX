"""Runtime-only shader packaging using the engine's own image/subset reader."""
from pathlib import Path
import json
import shutil
from core import Failure, atomic, clone, clone_tree


def shader_tools():
    from derived import module
    helper=Path(__file__).resolve().parents[1]/'Engine/nxnative/dm/tools/shader_lib.py'
    return module(helper,'lumanx_payload_shader_lib') if helper.is_file() else None


def copy_shaders(c, source, destination, chain, graphics='nvn'):
    source,destination=Path(source),Path(destination)
    helper=shader_tools() if graphics not in ('vulkan','gl') else None
    library=source/('b-'+chain) if chain else None
    if helper and library and helper.exists(library):
        destination.mkdir(parents=True,exist_ok=True)
        c.emit('message','Packaging runtime-only shader libraries; build caches and generated source stay out.')
        helper.subset(library,destination/('b-'+chain+'.img'))
    else:
        clone_tree(source,destination,c.progress)


def lean_copy(c, source, destination):
    from build import validate_runtime
    from incremental import runtime_inventory, pipeline_version
    source,destination=Path(source),Path(destination)
    if destination.exists():raise Failure('Runtime staging directory already exists.')
    destination.mkdir(mode=0o700)
    manifest=json.loads((source/'manifest.json').read_text())
    for item in source.iterdir():
        c.check()
        if item.is_symlink():raise Failure('Runtime payload contains a symbolic link.')
        if item.name=='shaders':
            copy_shaders(c,item,destination/'shaders',manifest.get('chain'),manifest.get('graphics','nvn'))
        elif item.is_dir():clone_tree(item,destination/item.name,c.progress)
        else:clone(item,destination/item.name,c.progress)
    manifest['artifacts']=runtime_inventory(c,destination)
    manifest['pipeline']=pipeline_version()
    manifest['runtimeOnly']=True
    atomic(destination/'manifest.json',manifest)
    validate_runtime(destination)
    return destination
