"""Write a NUP v1 containing only the selected packages and their stored extents."""
import hashlib
import shutil

from core import Failure


def align(offset):
    return (offset + 15) & ~15


def reachable(c, parser, container, packages):
    directory_ids, file_ids = {}, {}
    pending = [index for package in packages for index in (package.root, package.exefs, package.romfs)
               if index != parser.NO_DIR]
    while pending:
        c.check()
        index = pending.pop()
        if index in directory_ids:
            continue
        directory_ids[index] = len(directory_ids)
        for _, is_directory, child in container.children(index):
            if is_directory:
                pending.append(child)
            elif child not in file_ids:
                file_ids[child] = len(file_ids)

    return directory_ids, file_ids


def size_groups(c, parser, container, packages_by_key):
    """Group byte costs by the set of packages that reference them."""
    directories, files, extents = {}, {}, {}
    buckets = {}

    def add(mask, toc=0, data=0):
        bucket = buckets.setdefault(mask, [0, 0])
        bucket[0] += toc
        bucket[1] += data

    keys = list(packages_by_key)
    for bit, package in enumerate(packages_by_key.values()):
        mask = 1 << bit
        add(mask, parser.PKG.size, align(package.meta_size))
        package_dirs, package_files = reachable(c, parser, container, [package])
        for index in package_dirs:
            directories[index] = directories.get(index, 0) | mask
        for index in package_files:
            files[index] = files.get(index, 0) | mask
    for index, mask in directories.items():
        c.check()
        add(mask, parser.DIR.size + len(container.dirs[index][0]) + 4 * len(container.children(index)))
    for index, mask in files.items():
        c.check()
        name, _, _, offset, stored_size, _ = container.files[index]
        add(mask, parser.FILE.size + len(name))
        if stored_size:
            extent = (offset, stored_size)
            extents[extent] = extents.get(extent, 0) | mask
    for (_, stored_size), mask in extents.items():
        add(mask, data=align(stored_size))
    return [
        dict(keys=[key for bit, key in enumerate(keys) if mask & (1 << bit)], tocBytes=toc, dataBytes=data)
        for mask, (toc, data) in buckets.items()
    ]


def subset_size(groups, selection, header_bytes, toc_header_bytes):
    included = [group for group in groups if selection.intersection(group['keys'])]
    return header_bytes + align(toc_header_bytes + sum(group['tocBytes'] for group in included)) + sum(
        group['dataBytes'] for group in included)


def write(c, parser, container, packages, destination):
    directory_ids, file_ids = reachable(c, parser, container, packages)

    pool = bytearray()

    def name(value):
        offset = len(pool)
        pool.extend(value)
        return offset, len(value)

    def directory(index):
        return parser.NO_DIR if index == parser.NO_DIR else directory_ids[index]

    slots = bytearray()
    directories = bytearray()
    for index in directory_ids:
        children = container.children(index)
        directories.extend(parser.DIR.pack(*name(container.dirs[index][0]), len(slots) // 4, len(children), 0))
        for _, is_directory, child in children:
            slot = directory_ids[child] if is_directory else len(directory_ids) + file_ids[child]
            slots.extend(slot.to_bytes(4, 'little'))

    file_names = [name(container.files[index][0]) for index in file_ids]
    pool_offset = parser.TOC.size + len(packages) * parser.PKG.size + len(directories) + len(file_ids) * parser.FILE.size + len(slots)
    toc_size = align(pool_offset + len(pool))
    cursor = parser.SUPER.size + toc_size
    records, metadata = bytearray(), []
    has_base = any(package.kind == parser.BASE for package in packages)
    for package in packages:
        flags = package.flags
        if package.kind == parser.UPDATE and not has_base:
            flags |= parser.STANDALONE
        metadata_offset = cursor if package.meta_size else 0
        if package.meta_size:
            metadata.append((cursor, package.meta_off, package.meta_size))
            cursor = align(cursor + package.meta_size)
        records.extend(parser.PKG.pack(
            package.title_id, directory(package.root), directory(package.exefs), directory(package.romfs),
            package.version, package.kind, flags, 0, 0, metadata_offset, package.meta_size
        ))

    blob_offset = cursor
    files, extents = bytearray(), []
    copied_offsets = {}
    for index, file_name in zip(file_ids, file_names):
        _, size, sha, offset, stored_size, codec = container.files[index]
        new_offset = 0
        if stored_size:
            extent = (offset, stored_size)
            if extent not in copied_offsets:
                copied_offsets[extent] = cursor
                extents.append((cursor, offset, stored_size))
                cursor = align(cursor + stored_size)
            new_offset = copied_offsets[extent]
        files.extend(parser.FILE.pack(*file_name, size, new_offset, stored_size, sha, codec, 0, 0))
    toc = parser.TOC.pack(b'TOC\x01', len(packages), len(directory_ids), len(file_ids), pool_offset, len(pool), 0)
    toc += records + directories + files + slots + pool
    toc = toc.ljust(toc_size, b'\0')
    header = parser.SUPER.pack(b'NUP\x01', parser.SUPER.size, 1, parser.SUPER.size, toc_size,
                               hashlib.sha256(toc).digest(), blob_offset, cursor, len(packages), 0,
                               container.uuid, bytes(32))
    if shutil.disk_usage(destination.parent).free < cursor + (512 << 20):
        raise Failure('游戏库可用空间不足，复制尚未开始。')
    c.begin('复制所选 NUP 内容')
    with destination.open('xb') as output:
        output.write(header)
        output.write(toc)
        for destination_offset, source_offset, length in [*metadata, *extents]:
            output.seek(destination_offset)
            for offset in range(0, length, 4 << 20):
                c.check()
                start = source_offset + offset
                output.write(container.mm[start:start + min(4 << 20, length - offset)])
                c.progress(destination_offset + offset, cursor)
        output.truncate(cursor)
