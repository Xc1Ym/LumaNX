import contextlib,io,json,os,random,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Worker'))
import compressed_assets as assets,asset_storage
from core import Failure,Cancelled,atomic
import test_runtime_archive as fixtures

class AssetCompressionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.RuntimeArchiveTests();self.fixture.setUp()
        for key in ['root','c','runtime','local','library']:setattr(self,key,getattr(self.fixture,key))
        from derived import module
        packer=module(ROOT/'Engine/nxnative/dm/tools/romfs_image.py','luma_test_asset_packer')
        packer.pack(self.runtime/'romfs',self.runtime/'romfs.img');shutil.rmtree(self.runtime/'romfs')
        (self.runtime/'dmhost').write_bytes(b'LUMANX_ASSET_COMPRESSION_V1');(self.runtime/'dmhost').chmod(0o755)
        manifest=json.loads((self.runtime/'manifest.json').read_text());manifest.update(assetCompressionReader=1,assetCompression=False)
        atomic(self.runtime/'manifest.json',manifest)
    def tearDown(self):self.fixture.tearDown()
    def quiet(self,fn,*args):
        with contextlib.redirect_stdout(io.StringIO()):return fn(*args)
    def test_opt_in_roundtrip_keeps_saves_and_skips_compilation(self):
        original=(self.runtime/'romfs.img').read_bytes()
        self.quiet(asset_storage.compress,self.c);active=self.local/'current'
        self.assertTrue(assets.is_compressed(active/'romfs.img'));self.assertFalse(self.runtime.exists())
        with assets.Reader(active/'romfs.img') as reader:self.assertEqual(reader.read(),original)
        self.assertTrue(self.c.game()['assetCompressionRequested']);self.assertEqual(self.fixture.saved(),b'keep my save')
        self.quiet(asset_storage.uncompress,self.c)
        self.assertEqual((active/'romfs.img').read_bytes(),original);self.assertFalse(self.c.game()['assetCompressionRequested'])
        self.assertEqual(self.fixture.saved(),b'keep my save')
    def test_older_host_only_sets_future_preference(self):
        (self.runtime/'dmhost').write_bytes(b'old host');original=(self.runtime/'romfs.img').read_bytes()
        result=self.quiet(asset_storage.compress,self.c)
        self.assertTrue(result['requiresPreparation']);self.assertEqual((self.runtime/'romfs.img').read_bytes(),original)
        self.assertTrue(self.c.game()['assetCompressionRequested'])
        self.quiet(asset_storage.uncompress,self.c);self.assertFalse(self.c.game()['assetCompressionRequested'])
    def test_cancel_and_low_space_keep_previous_runtime_and_preference(self):
        for error in [Cancelled(),OSError('injected failure')]:
            with patch.object(asset_storage,'convert_files',side_effect=error):
                with self.assertRaises(type(error)):self.quiet(asset_storage.compress,self.c)
            self.assertEqual((self.local/'current').resolve(),self.runtime.resolve())
            self.assertFalse(self.c.game().get('assetCompressionRequested',False))
        with patch('asset_storage.shutil.disk_usage',return_value=shutil._ntuple_diskusage(1,1,0)):
            with self.assertRaises(Failure):self.quiet(asset_storage.compress,self.c)
        self.assertTrue(self.runtime.exists())
    def test_apfs_reversal_reserves_image_space_without_double_counting_clones(self):
        self.quiet(asset_storage.compress,self.c)
        # Enough for a replacement image plus margin, but less than a duplicate
        # runtime plus image. This is the real low-space reversal regression.
        required=(self.local/'current/romfs.img').stat().st_size
        available=200000+(256<<20)
        with patch('asset_storage.shutil.disk_usage',return_value=shutil._ntuple_diskusage(1<<30,0,available)):
            self.quiet(asset_storage.uncompress,self.c)
        self.assertFalse(assets.is_compressed(self.local/'current/romfs.img'))

    def test_bad_payload_and_index_are_rejected(self):
        p=self.root/'compressed';self.quiet(assets.convert,self.c,self.runtime/'romfs.img',p,True);original=p.read_bytes()
        for offset in [0,20,40,len(original)-1,assets.HEADER.size+5]:
            data=bytearray(original);data[offset]^=1;p.write_bytes(data)
            with self.assertRaises((ValueError,assets.zstd.ZstdError)):
                with assets.Reader(p) as reader:reader.read()
    def test_random_cross_block_reads_raw_fallback_and_cache_bound(self):
        raw=self.root/'random';data=random.Random(123).randbytes(6<<20)+b'A'*100;raw.write_bytes(data);p=self.root/'compressed'
        self.quiet(assets.convert,self.c,raw,p,True)
        with assets.Reader(p) as reader:
            for offset in [0,262140,3000000,len(data)-10,len(data)]:
                reader.seek(offset);self.assertEqual(reader.read(4096),data[offset:offset+4096])
            for i in range(len(reader.entries)):reader.seek(i*reader.block);reader.read(1)
            self.assertLessEqual(sum(len(v) for v in reader.cache.values()),4<<20)
    def test_archive_restore_preserves_compression_and_validation(self):
        self.quiet(asset_storage.compress,self.c)
        self.quiet(self.fixture.quiet,__import__('runtime_archive').archive,self.c)
        self.quiet(__import__('runtime_archive').restore,self.c)
        self.assertTrue(assets.is_compressed(self.local/'current/romfs.img'))
        self.assertEqual(self.fixture.saved(),b'keep my save')
    def test_default_game_has_no_compression_preference(self):
        self.assertFalse(self.c.game().get('assetCompressionRequested',False))
    def test_converter_does_not_overwrite_or_publish_cancelled_output(self):
        output=self.root/'converted';output.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):self.quiet(assets.convert,self.c,self.runtime/'romfs.img',output,True)
        self.assertEqual(output.read_bytes(),b'keep');output.unlink()
        with patch.object(self.c,'check',side_effect=Cancelled):
            with self.assertRaises(Cancelled):self.quiet(assets.convert,self.c,self.runtime/'romfs.img',output,True)
        self.assertFalse(output.exists());self.assertEqual(list(self.root.glob('*.part')),[])
