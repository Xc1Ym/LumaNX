"""Synthetic NUP v1 writer, adapted from nxnative test_nsp_nup.py (MIT)."""
import hashlib
from pathlib import Path
import struct
try:
    from compression import zstd
except ImportError:
    from backports import zstd

def npdm(tid):
    d = bytearray(0x100)
    d[:4] = b'META'
    struct.pack_into('<II', d, 0x70, 0x80, 0x20)
    d[0x80:0x84] = b'ACI0'
    struct.pack_into('<Q', d, 0x90, tid)
    return bytes(d)


def tlv(recs):
    return b''.join(struct.pack('<HHI', t, 0, len(v)) + v for t, v in recs)


def write_nup(path, packages, *, update_flags=0):
    """packages: [(kind, title ID, version, {'exefs': {name: bytes}, 'romfs': {path: bytes}}, meta bytes)] → a NUP file, every file of 200 bytes or more zstd-compressed"""
    dirs, files, slots, pool = [], [], [], bytearray()
    def walk(name, tree):   # tree: {name: bytes or dict}; dirs pre-order, children contiguous and sorted
        d = len(dirs); dirs.append([name, 0, 0])
        kids = sorted(tree.items(), key=lambda kv: kv[0].encode())
        first = len(slots); slots.extend([None] * len(kids)); dirs[d][1:] = [first, len(kids)]
        for j, (n, v) in enumerate(kids):
            if isinstance(v, bytes): slots[first + j] = ('f', len(files)); files.append((n, v))
        for j, (n, v) in enumerate(kids):
            if isinstance(v, dict): slots[first + j] = ('d', walk(n, v))
        return d
    def nest(flat):
        t = {}
        for p, v in flat.items():
            *ds, f = p.split('/'); c = t
            for x in ds: c = c.setdefault(x, {})
            c[f] = v
        return t
    recs = []
    for kind, tid, ver, tree, meta in packages:
        t = {k: v if k == 'exefs' else nest(v) for k, v in tree.items()}
        root = walk('', t)
        sub = {n: s[1] for n, s in zip(sorted(t), slots[dirs[root][1]:dirs[root][1] + dirs[root][2]])}
        recs.append([tid, root, sub.get('exefs', 0xFFFFFFFF), sub.get('romfs', 0xFFFFFFFF), ver, kind, meta])
    def name(s):
        b = s.encode(); off = len(pool); pool.extend(b); return off, len(b)
    toc_len = 0x30 + len(recs) * 0x40 + len(dirs) * 0x18 + len(files) * 0x50 + len(slots) * 4
    pool_off = toc_len
    names_d = [name(d[0]) for d in dirs]; names_f = [name(f[0]) for f in files]
    toc_size = (pool_off + len(pool) + 15) // 16 * 16
    pos = 0x80 + toc_size
    metas = []
    for r in recs:
        metas.append((pos, r[6])); pos = (pos + len(r[6]) + 15) // 16 * 16
    blob, blobs = pos, []
    ext = []
    for n, data in files:
        stored, codec = (zstd.compress(data), 1) if len(data) >= 200 else (data, 0)
        if not data: ext.append((0, 0, 0)); continue
        ext.append((pos, len(stored), codec)); blobs.append((pos, stored)); pos = (pos + len(stored) + 15) // 16 * 16
    toc = bytearray(struct.pack('<4sIQQQQQ', b'TOC\x01', len(recs), len(dirs), len(files), pool_off, len(pool), 0))
    for r, (moff, m) in zip(recs, metas):
        toc += struct.pack('<QIIIIBBHIQI20x', r[0], r[1], r[2], r[3], r[4], r[5], update_flags if r[5] == 1 else 0, 0, 0, moff if m else 0, len(m))
    for (o, ln), d in zip(names_d, dirs): toc += struct.pack('<IIIIQ', o, ln, d[1], d[2], 0)
    for (o, ln), (n, data), (eo, es, c) in zip(names_f, files, ext): toc += struct.pack('<IIQQQ32sBBH12x', o, ln, len(data), eo, es, hashlib.sha256(data).digest(), c, 0, 0)
    for k, i in slots: toc += struct.pack('<I', i if k == 'd' else len(dirs) + i)
    toc += pool; toc += b'\0' * (toc_size - len(toc))
    body = bytearray(pos)
    body[0x80:0x80 + toc_size] = toc
    for moff, m in metas: body[moff:moff + len(m)] = m
    for o, b in blobs: body[o:o + len(b)] = b
    uuid = hashlib.sha256(b''.join(struct.pack('<QIB', r[0], r[4], r[5]) for r in recs)).digest()[:16]
    body[:0x80] = struct.pack('<4sHHQQ32sQQII16s32s', b'NUP\x01', 0x80, 1, 0x80, toc_size, hashlib.sha256(toc).digest(), blob, pos, len(recs), 0, uuid, b'\0' * 32)
    Path(path).write_bytes(body)
