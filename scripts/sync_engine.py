#!/usr/bin/env python3
"""Import a pinned public nxnative tree and reapply controller and SDK compatibility patches."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'Worker'))
from bundled_engine import inventory, verify_bundle

UPSTREAM = 'https://github.com/seedds/nxnative.git'
OMIT_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp', '.pdb'}
# Binary parser fuzz inputs are not runtime sources. Keep the bundle's strict
# private/generated-asset checks intact for every other upstream path.
OMIT_TREES = (Path('dm/tools/fuzz/corpus'),)


def patch_controller(root):
    header = ROOT/'scripts/patches/controller_native.h'
    shutil.copy2(header, root/'dm/host/controller_native.h')
    for name, old in (
        ('dm/host/front_mac.m', 'K(g.buttonB, DM_BTN_A); K(g.buttonA, DM_BTN_B); K(g.buttonY, DM_BTN_X); K(g.buttonX, DM_BTN_Y);'),
        ('dm/ios/Sources/DmGamepad.m', 'K(g.buttonB, B_A); K(g.buttonA, B_B); K(g.buttonY, B_X); K(g.buttonX, B_Y);'),
    ):
        path = root/name
        text = path.read_text()
        legacy = old+'   // by position: right A, bottom B, top X, left Y'
        shared = 'uint64_t m = dm_pad_face(g);   // by position, a Nintendo pad by its labels'
        include = '#include "haptics_apple.h"'
        if text.count(include) != 1 or text.count(legacy) + text.count(shared) != 1:
            raise RuntimeError('Upstream controller interface changed: '+name)
        text = text.replace(include, include+'\n#include "controller_native.h"')
        text = text.replace(legacy, 'm |= luma_face_buttons(g);   // automatic Nintendo / Xbox / PS semantics')
        text = text.replace(shared, 'uint64_t m = luma_face_buttons(g);   // automatic Nintendo / Xbox / PS semantics')
        text = text.replace('// Controllers: buttons by position as on the iPhone (right A, bottom B, top X, left Y),', '// Controllers: automatic Nintendo / Xbox / PS face-button semantics,')
        text = text.replace('face buttons as on the iPhone, by position (right A, bottom B, top X, left Y) or on a Nintendo pad by its labels (pad_apple.h)', 'automatic Nintendo / Xbox / PS face-button semantics (controller_native.h)')
        text = text.replace('map by position: bottom = B, right = A, left = Y, top = X (same positions as on a Switch controller); a Nintendo pad maps by its labels (pad_apple.h).', 'use automatic Nintendo / Xbox / PS semantics (controller_native.h).')
        text = text.replace('map by position: bottom = B, right = A, left = Y, top = X (same positions as on a Switch controller).', 'use automatic Nintendo / Xbox / PS semantics (controller_native.h).')
        if old in text or 'dm_pad_face(g)' in text or text.count('luma_face_buttons(g)') != 1:
            raise RuntimeError('Controller patch did not apply cleanly: '+name)
        path.write_text(text)


def patch_sdk_compatibility(root):
    patch_metalfx_compatibility(root)
    # Runtime availability does not make SDK 27 declarations visible to Xcode 26.
    path=root/'dm/ios/Sources/DmGamepad.m'
    text=path.read_text()
    if 'deviceMotionBody' not in text: return
    guard='#if defined(__IPHONE_OS_VERSION_MAX_ALLOWED) && __IPHONE_OS_VERSION_MAX_ALLOWED >= 270000'
    old='    if (@available(iOS 27.0, *)) { g_motion.deviceMotionBody = body; g_motion_body = YES; LOG("front end: the phone\'s motion comes in the pad view\'s frame (deviceMotionBody)"); }'
    guarded=guard+'\n'+old+'\n#else\n    (void)body;   // Older SDKs keep the hardware-frame orientation fallback.\n#endif'
    if guarded in text: return
    if text.count(old)!=1: raise RuntimeError('Upstream phone motion interface changed: '+str(path))
    path.write_text(text.replace(old,guarded))


def patch_metalfx_compatibility(root):
    path = root/'dm/gfx/nvn/nvn_mtl.m'
    if not path.exists(): return
    text = path.read_text()
    if 'colorContentOffsetX' not in text: return
    guard = '#if (defined(__MAC_OS_X_VERSION_MAX_ALLOWED) && __MAC_OS_X_VERSION_MAX_ALLOWED >= 270000) || (defined(__IPHONE_OS_VERSION_MAX_ALLOWED) && __IPHONE_OS_VERSION_MAX_ALLOWED >= 270000)'
    available = 'if (@available(macOS 27.0, iOS 27.0, *)) {'
    warning = 'if (c->base[DLSS_COLOR][0]'
    # Keep the nonzero-origin warning on older SDKs as well as older systems.
    # Runtime availability alone cannot hide properties absent from SDK 26.
    properties = ('colorContentOffsetX', 'colorContentOffsetY', 'depthContentOffsetX', 'depthContentOffsetY',
                  'motionContentOffsetX', 'motionContentOffsetY', 'outputOffsetX', 'outputOffsetY')
    # The offsets may be assigned immediately or inside rec_cb_block from a
    # captured value. Match the complete assignment block, not its comment or
    # a closing brace elsewhere in the renderer.
    blocks = list(re.finditer(r'(?m)^(?P<indent> +)'+re.escape(available)+
                             r'[^\n]*\n(?P<body>(?:[^\n]*\n)*?)(?P=indent)\}', text))
    blocks = [block for block in blocks if 'sc.colorContentOffsetX' in block['body']]
    if len(blocks) != 1 or any(text.count('sc.'+p) != 1 for p in properties):
        raise RuntimeError('Upstream MetalFX offset interface changed: '+str(path))
    block = blocks[0]
    assignments = ''.join(block['body'].split())
    expected = [''.join(f'sc.{prop}=(NSUInteger){base}[{kind}][{axis}];'
                       for (kind, prefix) in (('DLSS_COLOR', 'colorContentOffset'), ('DLSS_DEPTH', 'depthContentOffset'),
                                              ('DLSS_MOTION', 'motionContentOffset'), ('DLSS_OUTPUT', 'outputOffset'))
                       for axis, prop in enumerate((prefix+'X', prefix+'Y')))
                for base in ('c->base', 'a.base')]
    tail = text[block.end():]
    legacy = tail.startswith(' else '+warning)
    deferred_warning = '    '+available+'} else '+warning
    if assignments in expected and text[:block.start()].endswith(guard+'\n') and (
            tail.startswith(' else\n#endif\n'+block['indent']+warning) or tail.startswith('\n#endif\n')):
        return
    if assignments not in expected or (not legacy and text.count(deferred_warning) != 1):
        raise RuntimeError('Upstream MetalFX offset interface changed: '+str(path))
    if legacy:
        tail = ' else\n#endif\n'+block['indent']+tail[len(' else '):]
    else:
        tail = '\n#endif'+tail
    text = text[:block.start()]+guard+'\n'+block[0]+tail
    if not legacy:
        # An SDK 26 build cannot set offsets even on OS 27, so keep warning there.
        text = text.replace(deferred_warning, guard+'\n    '+available+'} else\n#endif\n    '+warning)
    path.write_text(text)


def sync(checkout, target):
    checkout, target = Path(checkout).resolve(), Path(target).resolve()
    sha = subprocess.check_output(['git', '-C', checkout, 'rev-parse', 'HEAD'], text=True).strip()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.nxnative-', dir=target.parent) as directory:
        stage = Path(directory)/'source'; stage.mkdir()
        paths = subprocess.check_output(['git', '-C', checkout, 'ls-files', '-z']).decode().split('\0')
        for name in filter(None, paths):
            rel = Path(name)
            if any(tree == rel or tree in rel.parents for tree in OMIT_TREES):
                continue
            if rel.parts[0] not in {'dm', 'scripts', 'docs', 'LICENSE', 'README.md'} or rel.name == 'AGENTS.md' or rel.suffix.lower() in OMIT_SUFFIXES:
                continue
            if (checkout/rel).is_symlink(): raise RuntimeError('Upstream symlink is not allowed: '+name)
            # Read committed bytes, never a builder's modified working copy.
            data = subprocess.check_output(['git', '-C', checkout, 'show', sha+':'+name])
            # Upstream's generated dav1d config has an extra blank EOF line.
            # Normalize only that file so the imported source passes diff checks.
            if name == 'dm/third_party/dav1d/config/config.h':
                data = data.rstrip(b'\n')+b'\n'
            dest = stage/rel; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(data)
            if (checkout/rel).stat().st_mode & 0o111: dest.chmod(0o755)
        patch_controller(stage)
        patch_sdk_compatibility(stage)
        record = dict(schema=1, repository=UPSTREAM, revision=sha,
                      controllerPatch=hashlib.sha256((ROOT/'scripts/patches/controller_native.h').read_bytes()).hexdigest(), files=inventory(stage))
        (stage/'manifest.json').write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')
        verify_bundle(stage)
        backup = Path(directory)/'previous'
        if target.exists(): target.rename(backup)
        try: stage.rename(target)
        except BaseException:
            if backup.exists(): backup.rename(target)
            raise
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'Engine/nxnative')
    args = parser.parse_args()
    if args.checkout:
        record = sync(args.checkout, args.output)
    else:
        with tempfile.TemporaryDirectory(prefix='lumanx-upstream-') as directory:
            subprocess.run(['git', 'clone', '--depth', '1', UPSTREAM, directory], check=True)
            record = sync(directory, args.output)
    print('Imported nxnative '+record['revision']+' ('+str(len(record['files']))+' files)')


if __name__ == '__main__': main()
