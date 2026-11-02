"""Per-stage build dependencies, independent of the release/engine cache key.

Workspace files are mutable build artifacts. Installed releases are separate
verified clones and are never used as writable build outputs.
"""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
import re
import sys
from core import atomic, contained, digest, read

SCHEMA = 1
WORKER = Path(__file__).parent
GENERATED_TABLES = {'shader_map.tsv','shader_facts.tsv','shader_pairs.tsv',
    'shader_map.tsv.conflicts.tsv','c1_full.tsv','cb_extent.tsv','dmsh_chain.h'}
HOST_KEYS = {'name','ipa','app_category','pad_layout','op_mode','romfs_marker','zip_store',
    'mem_used','mem_reserve','mem_alias','mem_stack','app_pool','sys_resource','render_cond'}


def hash_value(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def cache_object(path):
    try: value={} if Path(path).is_symlink() else read(path,{})
    except (OSError,ValueError): return {}
    return value if isinstance(value,dict) else {}


def checkpoints(path):
    return {name:record for name,record in cache_object(path).items()
        if isinstance(name,str) and isinstance(record,dict) and record and all(
            isinstance(p,str) and isinstance(v,list) and len(v)==2 and type(v[0]) is int and v[0]>=0
            and isinstance(v[1],str) and re.fullmatch('[0-9a-f]{64}',v[1]) for p,v in record.items())}


def pipeline_version(target='macos'):
    names=('incremental.py','build.py','core.py','derived.py','dump.py')+(('ipa.py',) if target=='ios' else ())
    return hash_value({name:digest(WORKER/name) for name in names})


def runtime_inventory(c, root):
    """Seal installed payloads too; an idempotent prepare must not skip over
    a corrupted ready runtime merely because its manifest's cache key matches."""
    from dump import tree_entries
    root=contained(c.library,Path(root).resolve())
    sizes,directories=tree_entries(c,root);sizes.pop('manifest.json',None)
    total=sum(sizes.values());done=0;files={}
    for name,size in sorted(sizes.items()):
        files[name]=[size,digest(root/name,lambda n,t:c.progress(done+n,total))];done+=size
    return dict(files=files,directories=sorted(directories))


def python_recipe(path, entries):
    """Follow local function/global references; a host-only function edit need
    not invalidate unrelated functions in the same upstream packing script."""
    if not path.is_file(): return 'missing'
    try: tree=ast.parse(path.read_text())
    except (SyntaxError,UnicodeError): return digest(path)
    definitions={}
    imports=[]
    for node in tree.body:
        if isinstance(node,(ast.Import,ast.ImportFrom)): imports.append(ast.dump(node))
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)): definitions[node.name]=node
        elif isinstance(node,(ast.Assign,ast.AnnAssign)):
            for name in ast.walk(node):
                if isinstance(name,ast.Name) and isinstance(name.ctx,ast.Store): definitions[name.id]=node
    selected={};pending=list(entries)
    while pending:
        name=pending.pop()
        if name in selected or name not in definitions: continue
        node=definitions[name];selected[name]=ast.dump(node)
        pending.extend(n.id for n in ast.walk(node) if isinstance(n,ast.Name) and n.id not in selected)
    return hash_value(dict(imports=imports,definitions=selected,requested=list(entries),python=list(sys.version_info[:2])))


def worker_recipe(kind):
    common=python_recipe(WORKER/'core.py',('clone','clone_tree','digest','Context'))
    # Changes to command wiring have no older per-call ABI. Conservatively
    # rebuild on coordinator edits; leaf helpers keep their stage-local keys.
    coordinator={}
    for name,functions in (('build.py',('build',)),('derived.py',('prepare_profile','shaders'))):
        tree=ast.parse((WORKER/name).read_text())
        coordinator[name]=[ast.dump(n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in functions]
    entries={
        'unpack':{'build.py':('container_runner',),'dump.py':('extract',)},
        'dlc':{'build.py':('container_runner',),'dump.py':('extract_dlc',)},
        'profile':{'derived.py':('prepare_profile',)},
        'rewrite':{},
        'capture':{},
        'decode':{},
        'split':{'derived.py':('detect_sources','oodle_decoder')},
        'shaders':{'build.py':('ShaderProgress',),'derived.py':('validate_tables',)},
        'host':{'build.py':('compile_host',)},
    }
    return dict(common=common,coordinator=hash_value(coordinator),functions={name:python_recipe(WORKER/name,functions)
        for name,functions in entries.get(kind,{}).items()})


def kind_of(name):
    if name.startswith('解包与合并 '): return 'unpack'
    return {'处理 DLC':'dlc','生成版本配置':'profile','重写原生代码':'rewrite',
        '采集运行时 GLSLC 着色器':'capture','采集运行时 Vulkan 着色器':'capture',
        '采集运行时着色器':'capture','解码游戏着色器':'decode',
        '提取并核对着色器':'split','转换并编译 Metal 着色器':'shaders',
        '转换并编译 Vulkan 着色器':'shaders','编译 Mac 主程序':'host'}.get(name,'unknown')


def excluded(name, relative):
    parts=Path(relative).parts
    if kind_of(name)=='unpack':
        return any(p in ('glslc_capture','vk_capture','gl_capture','ue_shaders') for p in parts)
    if kind_of(name)=='profile': return Path(relative).name in GENERATED_TABLES
    return False


class Graph:
    def __init__(self, source, root, game, tools, strategy, target):
        self.source=Path(source);self.root=Path(root);self.game=game;self.tools=tools
        self.strategy=strategy;self.target=target;self.profile=None;self.decoder=False
        self.groups={k:{} for k in ('reader','rewrite','shader','host','execution','profile','other')}
        for path in sorted(self.source.rglob('*')):
            if not path.is_file(): continue
            rel=path.relative_to(self.source).as_posix();parts=Path(rel).parts
            if any(p in ('gen','obj','bin','__pycache__','tests','docs','fuzz') for p in parts): continue
            if path.name in ('.source-ready','global.json','manifest.json','LICENSE') or path.suffix in ('.md','.log'): continue
            if rel.startswith('dm/tools/nx_extract/'): groups=['reader']
            elif rel.startswith('dm/tools/'):
                groups=['rewrite']
                if path.name in ('romfs.py','romfs_image.py','nso.py','nacp.py'): groups.append('shader')
            elif rel.startswith('dm/gfx/tools/') or rel.startswith('dm/third_party/ryujinx/'):
                groups=['shader']
            elif rel.startswith('dm/host/') or rel.startswith('dm/gfx/'):
                groups=['host','execution']
                if path.name=='controller_native.h': groups=['host']
                if path.name=='dmsh_abi.h': groups.append('shader')
            elif rel.startswith(f'dm/games/{game["id"]}/'): groups=['profile']
            elif rel.startswith('dm/games/'):
                groups=['profile'] if len(parts)==3 else []  # shared profile reader/guesser, not other games
            elif rel.startswith('dm/third_party/'): groups=['host','execution','shader']
            elif rel.startswith('dm/ios/tools/'): groups=['shader']
            elif rel.startswith('dm/mac/'): groups=['host','execution']
            elif rel=='scripts/build_ipa_from_nsp.py': continue  # fingerprint function closures below
            elif rel.startswith('scripts/'): groups=['other']
            elif rel.startswith('dm/ios/'): groups=[]
            else: groups=['other']
            for group in groups: self.groups[group][rel]=digest(path)
        profile=self.source/'dm/games'/game['id']
        self.registered_rows=self.rows(profile/'game.tsv')
        # game.tsv is projected by stage. Generated shader tables are outputs,
        # never source dependencies of their own producer.
        self.groups['profile'].pop(f'dm/games/{game["id"]}/game.tsv',None)
        for rel in list(self.groups['profile']):
            if Path(rel).name in ('c1_full.tsv','cb_extent.tsv','dmsh_chain.h'): del self.groups['profile'][rel]
        self.profile_keys={
            'rewrite':hash_value({p:v for p,v in self.groups['profile'].items() if Path(p).suffix=='.py'}),
            'shader':hash_value({p:v for p,v in self.groups['profile'].items() if Path(p).name!='pso_manifest.tsv' and Path(p).name!='patches.py'}),
        }
        # Shader readers sometimes import helpers from dm/tools. Follow those
        # imports rather than making CPU-only patch_nso changes shader inputs.
        todo=list((self.source/'dm/gfx/tools').glob('*.py'));seen=set()
        while todo:
            path=todo.pop()
            if path in seen or not path.is_file(): continue
            seen.add(path)
            try: tree=ast.parse(path.read_text())
            except (SyntaxError,UnicodeError):
                self.groups['shader'].update(self.groups['rewrite']);continue
            for node in ast.walk(tree):
                mods=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) and node.module else []
                for mod in mods:
                    dependency=self.source/'dm/tools'/f'{mod.split(".")[0]}.py'
                    if dependency.is_file():
                        self.groups['shader'][dependency.relative_to(self.source).as_posix()]=digest(dependency)
                        todo.append(dependency)
        script=self.source/'scripts/build_ipa_from_nsp.py'
        functions={'unpack':('extract',),'dlc':('extract_aoc',),'profile':('derive_profile','provisional_prep'),
            'rewrite':('rewrite',),'capture':('capture_glslc','capture_shaders','capture_vk'),
            'decode':('decode_ue_shaders',),'split':('split_shaders',),
            'shaders':('build_shaders','build_vk_shaders','build_gl_shaders'), 'host':('build_mac_host',)}
        self.recipes={k:dict(upstream=python_recipe(script,v),worker=worker_recipe(k)) for k,v in functions.items()}
        self.group_keys={k:hash_value(v) for k,v in self.groups.items()}

    @staticmethod
    def rows(path):
        try: return [line.split('\t') for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]
        except OSError: return []

    def profile_rows(self, kind):
        rows=self.rows(self.profile.table('game.tsv')) if self.profile and hasattr(self.profile,'table') else self.registered_rows
        if kind=='rewrite':
            return [r for r in rows if r[0] not in HOST_KEYS and not r[0].startswith(('shader_','nvn_')) and r[0]!='graphics']
        if kind in ('split','shaders','decode','capture'):
            return [r for r in rows if r[0].startswith(('shader_','nvn_')) or r[0] in ('graphics','modules','package','shader_versions')]
        return rows

    def packages(self, kinds, version=None):
        return sorted((p.get('titleId',self.game['id']),p['type'],p['version'],p['sha256'])
            for p in self.game['packages'] if p['type'] in kinds and (version is None or p['version'] in (0,version)))

    def artifacts(self, saved, kinds, *, files=None):
        result={}
        for name,record in saved.items():
            if kind_of(name) not in kinds: continue
            if kind_of(name)=='unpack' and self.strategy.get('versions') and name.rsplit(' ',1)[-1] not in self.strategy['versions']: continue
            for path,value in record.items():
                if files is None or files(path): result[path]=value
        return result

    def key(self, name, saved):
        kind=kind_of(name);t=self.tools
        base=dict(schema=SCHEMA,kind=kind,name=name,target=self.target,game=self.game['id'],
            sourceKind=self.game.get('sourceKind','container'),recipe=self.recipes.get(kind),
            runtime=t.get('runtime'),other=self.group_keys['other'])
        if kind=='unpack':
            version=int(name.rsplit('v',1)[1]);packages=self.packages(('base','update'),version)
            if self.game.get('sourceKind')=='dump' and version: packages=[p for p in packages if p[1]=='update']
            base.update(packages=packages,reader=self.group_keys['reader'],library=t.get('readerLibrary'),sdk=t.get('readerSDK'))
        elif kind=='dlc':
            base.update(packages=self.packages(('dlc',)),reader=self.group_keys['reader'],library=t.get('readerLibrary'),sdk=t.get('readerSDK'))
        elif kind=='profile':
            base.update(inputs=self.artifacts(saved,{'unpack'}),profile=self.registered_rows,
                tables=self.group_keys['profile'],tools=self.group_keys['rewrite'],strategy=self.strategy)
        elif kind=='rewrite':
            base.update(inputs=self.artifacts(saved,{'unpack'},files=lambda p:'/ExeFS/' in p or Path(p).suffix.lower() in ('.nro','.nrr')),
                tools=self.group_keys['rewrite'],profile=self.profile_rows(kind),tables=self.profile_keys['rewrite'])
        elif kind in ('capture','decode','split'):
            # Capture and decoder producers read source/rewrite artifacts, not
            # their own previous outputs or results of later stages. Only the
            # split consumes completed capture/decoder outputs.
            parents={'unpack','rewrite','capture','decode'} if kind=='split' else {'unpack','rewrite'}
            base.update(inputs=self.artifacts(saved,parents),
                tools=self.group_keys['shader'],profile=self.profile_rows(kind),tables=self.profile_keys['shader'])
            if kind in ('capture','decode'):
                base.update(host=self.group_keys['execution'],clang=t.get('clang'),metal=t.get('metal'),sdk=t.get('macos-sdk'),sdkBuild=t.get('macos-sdk-build'))
            if kind=='split' and self.decoder:
                base.update(decoder=self.group_keys['execution'],clang=t.get('clang'),sdk=t.get('macos-sdk'),sdkBuild=t.get('macos-sdk-build'))
        elif kind=='shaders':
            base.update(inputs=self.artifacts(saved,{'split','capture','decode','unpack'}),
                tools=self.group_keys['shader'],profile=self.profile_rows(kind),tables=self.profile_keys['shader'],
                chain=self.chain(),metal=t.get('metal'),spirv=t.get('spirv-cross'),ios=t.get('ios'))
        elif kind=='host':
            base.update(host=self.group_keys['host'],profile=self.profile_rows(kind),tables=self.profile_keys['rewrite'],
                clang=t.get('clang'),metal=t.get('metal'),sdk=t.get('macos-sdk'),sdkBuild=t.get('macos-sdk-build'),chain=self.chain())
        else: base.update(identity=t,sources=self.packages(('base','update','dlc')),artifacts=saved)
        return hash_value(base)

    def chain(self):
        from core import chain_of
        return chain_of(self.root/'engine',self.profile if hasattr(self.profile,'table') else None)


def workspace(c, game, target, new_key):
    """One writable workspace per target; adopt a legacy workspace in place.
    Installed releases and the other target's workspace remain independent."""
    parent=c.library/'cache'/game['id'];parent.mkdir(parents=True,exist_ok=True)
    marker=parent/f'workspace-{target}.json'
    record=cache_object(marker)
    directory=record.get('directory')
    if record.get('schema')==SCHEMA and isinstance(directory,str) and Path(directory).name==directory and directory not in ('.','..'):
        raw=parent/record['directory'];root=contained(parent,raw)
        if root.is_dir() and not raw.is_symlink() and cache_object(root/'identity.json').get('target',target)==target: return root
    candidates=[]
    for path in parent.iterdir():
        if not path.is_dir() or path.is_symlink(): continue
        old=cache_object(path/'identity.json')
        if old.get('game')==game['id'] and old.get('target')==target:
            candidates.append(path)
    root=max(candidates,key=lambda p:(p/'identity.json').stat().st_mtime_ns) if candidates else parent/new_key
    root.mkdir(parents=True,exist_ok=True)
    atomic(marker,dict(schema=SCHEMA,directory=root.name))
    return root


def engine_matches(c, repo, source):
    """Check writable source against the verified immutable snapshot. Only
    documented generated headers/tables and package selection may differ."""
    from engine import source_files
    repo,source=Path(repo),Path(source)
    previous=cache_object(repo.parent/'identity.json')
    if not isinstance(previous.get('preparation',{}),dict): return False
    selected=f'dm/games/{previous.get("game","")}/game.tsv'
    source_rows=Graph.rows(source/selected)
    package=previous.get('preparation',{}).get('version') if previous.get('preparation',{}).get('mode')=='registered' else next((r[1] for r in source_rows if r[0]=='package'),None)
    def files(root):
        result={}
        for path in source_files(root):
            c.check();rel=path.relative_to(root).as_posix()
            if path.name in ('c1_full.tsv','cb_extent.tsv'): continue
            if rel in ('dm/gfx/nvn/dmsh_chain.h','dm/gfx/tools/dmsh_chain.lock'): continue
            if rel==selected:
                rows=Graph.rows(path)
                if root==repo and [r[1] for r in rows if r[0]=='package']!=[package]:
                    result[rel]='unrecorded package selection';continue
                result[rel]=hash_value([row for row in rows if row[0]!='package'])
            else: result[rel]=digest(path)
        return result
    return files(repo)==files(source)


def legacy_keys(c, root, game, target):
    """Bootstrap old checkpoints only from their verified immutable engine source.
    Missing provenance, different game sources or a derived profile rebuild once.
    No keys are inferred from a dirty writable engine checkout."""
    if (root/'stage-inputs.json').exists(): return {}
    old=cache_object(root/'identity.json');tools=old.get('tools',{});strategy=old.get('preparation',{})
    if not isinstance(tools,dict) or not isinstance(strategy,dict): return {}
    fp=tools.get('engineSource','')
    if old.get('sources')!=sorted(p['sha256'] for p in game['packages']) or strategy.get('mode')!='registered': return {}
    if not isinstance(fp,str) or not re.fullmatch(r'(bundled|external)-[0-9a-f]{64}',fp): return {}
    marker=root/'engine/.source-ready'
    if not marker.is_file() or marker.read_text()!=fp: return {}
    source=c.private/'engines'/fp/'source';ready=cache_object(source.parent/'ready.json')
    if ready.get('fingerprint')!=fp or not isinstance(ready.get('files'),dict): return {}
    from engine import source_hash
    if not source.is_dir() or source_hash(source)!=ready.get('snapshotHash'): return {}
    # .NET embeds build-location information in nx_extract.dll. A new private
    # path alone changes its bytes, although its verified source is identical.
    # Track its source, compiler and LibHac instead of that incidental DLL hash.
    library=source.parent/'tools/nx_extract/LibHac.dll'
    if not library.is_file() or digest(library)!=ready.get('files',{}).get('tools/nx_extract/LibHac.dll'): return {}
    tools=tools|dict(readerLibrary=digest(library),readerSDK=ready.get('sdk',''))
    graph=Graph(source,root,game,tools,strategy,target)
    saved=checkpoints(root/'checkpoints.json')
    return {name:graph.key(name,saved) for name in saved}
