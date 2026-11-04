"""Daily engine synchronization uses committed sources and preserves good data on failure."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'Worker'),str(ROOT/'scripts')]
from bundled_engine import inventory, verify_bundle
from engine_fixture import make_engine
from sync_engine import sync, patch_sdk_compatibility


class EngineSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.source=make_engine(self.root/'upstream');self.target=self.root/'Engine/nxnative'
        (self.source/'LICENSE').write_text('Synthetic license fixture')
        self.front=self.source/'dm/host/front_mac.m'
        self.front.write_text('#include "haptics_apple.h"\nK(g.buttonB, DM_BTN_A); K(g.buttonA, DM_BTN_B); K(g.buttonY, DM_BTN_X); K(g.buttonX, DM_BTN_Y);   // by position: right A, bottom B, top X, left Y\n')
        ios=self.source/'dm/ios/Sources/DmGamepad.m';ios.parent.mkdir(parents=True)
        ios.write_text('#include "haptics_apple.h"\nK(g.buttonB, B_A); K(g.buttonA, B_B); K(g.buttonY, B_X); K(g.buttonX, B_Y);   // by position: right A, bottom B, top X, left Y\n')
        self.git('init','-q');self.commit()

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.source),*args],text=True,stderr=subprocess.STDOUT)

    def commit(self):
        self.git('add','.');self.git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','Synthetic upstream fixture')

    def tearDown(self):self.tmp.cleanup()

    def test_sync_uses_committed_bytes_and_reapplies_both_frontends(self):
        self.front.write_text('Uncommitted builder mutation must not be imported')
        (self.source/'untracked.keys').write_text('Synthetic private data')
        record=sync(self.source,self.target)
        self.assertEqual(record['revision'],self.git('rev-parse','HEAD').strip())
        self.assertEqual(record,verify_bundle(self.target))
        for name in ('dm/host/front_mac.m','dm/ios/Sources/DmGamepad.m'):
            self.assertIn('luma_face_buttons(g)',(self.target/name).read_text())
        self.assertFalse((self.target/'untracked.keys').exists())

    def test_interface_drift_preserves_previous_snapshot(self):
        sync(self.source,self.target);before=inventory(self.target)
        self.front.write_text('Upstream interface changed');self.commit()
        with self.assertRaisesRegex(RuntimeError,'interface changed'):sync(self.source,self.target)
        self.assertEqual(inventory(self.target),before)
        verify_bundle(self.target)

    def test_shared_face_helper_is_replaced_in_both_frontends(self):
        for name in ('dm/host/front_mac.m', 'dm/ios/Sources/DmGamepad.m'):
            path=self.source/name
            path.write_text('#include "haptics_apple.h"\nuint64_t m = dm_pad_face(g);   // by position, a Nintendo pad by its labels\n')
        self.commit()
        sync(self.source,self.target)
        for name in ('dm/host/front_mac.m', 'dm/ios/Sources/DmGamepad.m'):
            text=(self.target/name).read_text()
            self.assertIn('#include "controller_native.h"',text)
            self.assertIn('uint64_t m = luma_face_buttons(g);',text)
            self.assertNotIn('dm_pad_face(g)',text)
        verify_bundle(self.target)

    def test_ambiguous_or_missing_controller_anchors_preserve_snapshot(self):
        sync(self.source,self.target);before=inventory(self.target)
        original=self.front.read_text()
        for text in (original.replace('#include "haptics_apple.h"',''),
                     original+'uint64_t m = dm_pad_face(g);   // by position, a Nintendo pad by its labels\n',
                     original.replace('   // by position: right A, bottom B, top X, left Y','')):
            with self.subTest(text=text):
                self.front.write_text(text);self.commit()
                with self.assertRaisesRegex(RuntimeError,'controller interface changed'):
                    sync(self.source,self.target)
                self.assertEqual(inventory(self.target),before)
                verify_bundle(self.target)

    def test_binary_fuzz_corpus_is_omitted_but_harness_is_preserved(self):
        corpus=self.source/'dm/tools/fuzz/corpus/nso'
        corpus.mkdir(parents=True)
        (corpus/'huge-segment.nso').write_bytes(b'Synthetic parser input')
        (corpus/'other.bin').write_bytes(b'Synthetic parser input')
        harness=self.source/'dm/tools/fuzz/fuzz_nso.py'
        harness.write_text('# Synthetic harness source\n')
        self.commit()
        record=sync(self.source,self.target)
        self.assertFalse((self.target/'dm/tools/fuzz/corpus').exists())
        self.assertEqual((self.target/'dm/tools/fuzz/fuzz_nso.py').read_text(),harness.read_text())
        self.assertEqual(record,verify_bundle(self.target))

    def test_private_asset_outside_corpus_still_rejects_sync(self):
        sync(self.source,self.target);before=inventory(self.target)
        (self.source/'dm/unexpected.nso').write_bytes(b'Synthetic forbidden input')
        self.commit()
        with self.assertRaisesRegex(ValueError,'Private/generated engine asset'):
            sync(self.source,self.target)
        self.assertEqual(inventory(self.target),before)
        verify_bundle(self.target)

    def test_phone_motion_sdk_guard_survives_sync_and_reapplication(self):
        ios=self.source/'dm/ios/Sources/DmGamepad.m'
        statement='    if (@available(iOS 27.0, *)) { g_motion.deviceMotionBody = body; g_motion_body = YES; LOG("front end: the phone\'s motion comes in the pad view\'s frame (deviceMotionBody)"); }'
        ios.write_text(ios.read_text()+statement+'\n');self.commit()
        sync(self.source,self.target)
        imported=self.target/'dm/ios/Sources/DmGamepad.m';before=imported.read_text()
        self.assertIn('#if defined(__IPHONE_OS_VERSION_MAX_ALLOWED) && __IPHONE_OS_VERSION_MAX_ALLOWED >= 270000\n'+statement,before)
        self.assertIn('#else\n    (void)body;',before)
        patch_sdk_compatibility(self.target);self.assertEqual(imported.read_text(),before)
        verify_bundle(self.target)

    def test_changed_phone_motion_interface_preserves_previous_snapshot(self):
        sync(self.source,self.target);before=inventory(self.target)
        ios=self.source/'dm/ios/Sources/DmGamepad.m'
        ios.write_text(ios.read_text()+'g_motion.deviceMotionBody = body; // changed upstream interface\n');self.commit()
        with self.assertRaisesRegex(RuntimeError,'phone motion interface changed'):sync(self.source,self.target)
        self.assertEqual(inventory(self.target),before);verify_bundle(self.target)

    def test_reformatted_phone_motion_interface_preserves_previous_snapshot(self):
        sync(self.source,self.target);before=inventory(self.target)
        ios=self.source/'dm/ios/Sources/DmGamepad.m';original=ios.read_text()
        for statement in ('g_motion.deviceMotionBody=body;',
                          'g_motion.deviceMotionBody =\n    body;',
                          'g_motion . deviceMotionBody = body;'):
            with self.subTest(statement=statement):
                ios.write_text(original+statement+'\n');self.commit()
                with self.assertRaisesRegex(RuntimeError,'phone motion interface changed'):
                    sync(self.source,self.target)
                self.assertEqual(inventory(self.target),before);verify_bundle(self.target)

    @unittest.skipUnless(sys.platform=='darwin','Objective-C SDK compatibility check needs Apple clang')
    def test_phone_motion_compiles_with_and_without_sdk27_declaration(self):
        ios=self.source/'dm/ios/Sources/DmGamepad.m'
        ios.write_text('    if (@available(iOS 27.0, *)) { g_motion.deviceMotionBody = body; g_motion_body = YES; LOG("front end: the phone\'s motion comes in the pad view\'s frame (deviceMotionBody)"); }\n')
        patch_sdk_compatibility(self.source);guarded=ios.read_text()
        for sdk in (260500,270000):
            with self.subTest(sdk=sdk):
                declaration='@property void *deviceMotionBody;' if sdk>=270000 else ''
                source=(f'#define __IPHONE_OS_VERSION_MAX_ALLOWED {sdk}\n#define YES 1\n#define LOG(...) ((void)0)\n'
                    '@interface CMMotionManager\n'+declaration+'\n@end\n'
                    'static CMMotionManager *g_motion; static int g_motion_body;\n'
                    'void phone_motion_start(void *body) {\n'+guarded+'}\n')
                result=subprocess.run(['xcrun','clang','-target','arm64-apple-ios26.0','-x','objective-c','-fsyntax-only','-'],
                    input=source,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr)

    def metalfx_source(self, deferred=False):
        base='a.base' if deferred else 'c->base'
        indent='        ' if deferred else '    '
        assignments='\n'.join(f'{indent}    sc.{name} = (NSUInteger){base}[{kind}][{axis}];'
            for kind,prefix in [('DLSS_COLOR','colorContentOffset'),('DLSS_DEPTH','depthContentOffset'),('DLSS_MOTION','motionContentOffset'),('DLSS_OUTPUT','outputOffset')]
            for axis,name in enumerate([prefix+'X',prefix+'Y']))
        path=self.source/'dm/gfx/nvn/nvn_mtl.m';path.parent.mkdir(parents=True,exist_ok=True)
        available='if (@available(macOS 27.0, iOS 27.0, *)) {'
        warning='if (c->base[DLSS_COLOR][0] || c->base[DLSS_OUTPUT][1]) {\n        MLOG("nonzero origin");\n    }\n'
        block=indent+available+'   // SDK 27 offsets\n'+assignments+'\n'+indent+'}'
        if deferred:
            path.write_text('    '+available+'} else '+warning+
                            '    const struct C a = *c;\n    void (^encode)(void) = ^{\n'+block+'\n    };\n    encode();\n')
        else:
            path.write_text(block+' else '+warning)
        return path

    @unittest.skipUnless(sys.platform=='darwin','SDK compilation needs Apple clang')
    def test_metalfx_offsets_compile_on_old_and_new_mac_and_ios_sdks(self):
        self.check_metalfx_compilation(deferred=False)
        self.check_metalfx_compilation(deferred=True)

    def check_metalfx_compilation(self, deferred):
        path=self.metalfx_source(deferred);original=path.read_text();patch_sdk_compatibility(self.source)
        guarded=path.read_text();patch_sdk_compatibility(self.source)
        self.assertEqual(path.read_text(),guarded)
        self.assertIn('#endif\n    if (c->base[DLSS_COLOR][0]',guarded)
        self.assertEqual(guarded.count('MLOG("nonzero origin")'),1)
        for target,macro in [('arm64-apple-macos26.0','__MAC_OS_X_VERSION_MAX_ALLOWED'),('arm64-apple-ios26.0','__IPHONE_OS_VERSION_MAX_ALLOWED')]:
            for sdk in (260600,270000):
                with self.subTest(target=target,sdk=sdk,deferred=deferred):
                    names=['colorContentOffsetX','colorContentOffsetY','depthContentOffsetX','depthContentOffsetY','motionContentOffsetX','motionContentOffsetY','outputOffsetX','outputOffsetY']
                    declarations=''.join('@property unsigned long '+name+';\n' for name in names) if sdk>=270000 else ''
                    prefix=(f'#define {macro} {sdk}\n#define MLOG(...) ((void)0)\n'
                        'typedef unsigned long NSUInteger; enum {DLSS_COLOR,DLSS_DEPTH,DLSS_MOTION,DLSS_OUTPUT};\n'
                        'struct C {int base[4][2];};\n@protocol Scaler\n'+declarations+'@end\nvoid run(id<Scaler> sc,struct C *c) {\n')
                    command=['xcrun','clang','-target',target,'-x','objective-c','-fblocks','-fsyntax-only','-']
                    result=subprocess.run(command,input=prefix+guarded+'}\n',text=True,capture_output=True)
                    self.assertEqual(result.returncode,0,result.stderr)
                    if sdk<270000:
                        broken=subprocess.run(command,input=prefix+original+'}\n',text=True,capture_output=True)
                        self.assertNotEqual(broken.returncode,0)

    def test_deferred_metalfx_offsets_survive_sync_and_reapplication(self):
        self.metalfx_source(deferred=True);self.commit()
        sync(self.source,self.target)
        imported=self.target/'dm/gfx/nvn/nvn_mtl.m';before=imported.read_text()
        self.assertIn('#endif\n    if (c->base[DLSS_COLOR][0]',before)
        self.assertIn('sc.colorContentOffsetX = (NSUInteger)a.base[DLSS_COLOR][0]',before)
        patch_sdk_compatibility(self.target)
        self.assertEqual(imported.read_text(),before)
        verify_bundle(self.target)

    def test_metalfx_interface_drift_preserves_previous_snapshot(self):
        for deferred in (False,True):
            with self.subTest(deferred=deferred):
                path=self.metalfx_source(deferred);self.commit();sync(self.source,self.target)
                before=inventory(self.target);original=path.read_text()
                for changed in (original.replace('sc.outputOffsetY','sc.newOutputOffsetY'),
                                original.replace('[DLSS_OUTPUT][1]','[DLSS_OUTPUT][0]'),
                                original+original):
                    path.write_text(changed);self.commit()
                    with self.assertRaisesRegex(RuntimeError,'MetalFX offset interface changed'):sync(self.source,self.target)
                    self.assertEqual(inventory(self.target),before);verify_bundle(self.target)


if __name__=='__main__':unittest.main()
