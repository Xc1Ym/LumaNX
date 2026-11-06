"""The installed ZBIC extension decodes synthetic NSOs through nxnative."""
import hashlib
from pathlib import Path
import struct
import sys
import unittest
import zbic

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Worker'))
from derived import module
nso=module(ROOT/'Engine/nxnative/dm/tools/nso.py','lumanx_zbic_nso')


class Switch2CompressionTests(unittest.TestCase):
    def fixture(self):
        segments=(bytes.fromhex('1f2003d5')*64,b'synthetic read-only data'*32,b'\x01\x02'*128)
        header=bytearray(0x100);header[:4]=b'NSO0'
        struct.pack_into('<I',header,0xc,0x80|0x38|7)
        payload=b'';memory=0
        for i,data in enumerate(segments):
            stored=zbic.compress(data)
            struct.pack_into('<III',header,0x10+16*i,0x100+len(payload),memory,len(data))
            struct.pack_into('<I',header,0x60+4*i,len(stored))
            header[0xa0+32*i:0xc0+32*i]=hashlib.sha256(data).digest()
            payload+=stored;memory=(memory+len(data)+0xfff)&~0xfff
        return bytearray(header+payload),segments

    def test_zbic_segments_load_and_verify_content_hashes(self):
        data,segments=self.fixture();loaded=nso.load(data)
        for (offset,size),original in zip(loaded.segments,segments):
            self.assertEqual(loaded.image[offset:offset+size],original)

    def test_bad_zbic_and_wrong_segment_hash_are_rejected(self):
        data,_=self.fixture();data[0x100]^=0xff
        with self.assertRaises(nso.Error): nso.load(data)
        data,_=self.fixture();data[0xa0]^=0xff
        with self.assertRaises(nso.Error): nso.load(data)


if __name__=='__main__': unittest.main()
