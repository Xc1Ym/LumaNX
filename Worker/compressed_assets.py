"""Versioned Zstandard asset blocks; bounded random reads and verified conversion."""
import hashlib,io,os,struct,tempfile
from collections import OrderedDict
from pathlib import Path
from compression import zstd
HEADER=struct.Struct('<8sQIIQ32sII');ENTRY=struct.Struct('<QII32s');MAGIC=b'LNXBLK01';BLOCK=262144

def is_compressed(path):
    with Path(path).open('rb') as f:return f.read(8)==MAGIC

def host_supports(path):
    return b'LUMANX_ASSET_COMPRESSION_V1' in Path(path).read_bytes()

class Reader(io.RawIOBase):
    def __init__(self,path,mode='rb'):
        if mode!='rb':raise ValueError('asset images are read-only')
        self.file=Path(path).open('rb');self.cache=OrderedDict();self.position=0
        try:
            head=self.file.read(HEADER.size)
            magic,self.size,self.block,count,index,digest,codec,flags=HEADER.unpack(head)
            physical=os.fstat(self.file.fileno()).st_size
            if magic!=MAGIC or codec!=2 or flags or self.size>2**63-1 or not 65536<=self.block<=1048576 or self.block&(self.block-1):raise ValueError('Invalid compressed asset header')
            if count!=(self.size+self.block-1)//self.block or count*ENTRY.size>64<<20 or index<HEADER.size or index>physical or count*ENTRY.size!=physical-index:raise ValueError('Invalid compressed asset index bounds')
            self.file.seek(index);table=self.file.read(count*ENTRY.size)
            zero=HEADER.pack(magic,self.size,self.block,count,index,bytes(32),codec,flags)
            if hashlib.sha256(zero+table).digest()!=digest:raise ValueError('Compressed asset index checksum failed')
            self.entries=list(ENTRY.iter_unpack(table));next_offset=HEADER.size
            for i,(offset,stored,raw,_) in enumerate(self.entries):
                if offset!=next_offset or not 0<stored<=raw or raw!=min(self.block,self.size-i*self.block) or stored>index-offset:raise ValueError('Invalid compressed asset block range')
                next_offset+=stored
            if next_offset!=index:raise ValueError('Invalid compressed asset payload')
        except BaseException:
            self.file.close();raise
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.position
    def seek(self,offset,whence=0):
        if whence not in (0,1,2):raise ValueError('invalid seek origin')
        value=offset+(self.position if whence==1 else self.size if whence==2 else 0)
        if value<0:raise ValueError('negative seek')
        self.position=value;return value
    def block_data(self,k):
        if k in self.cache:self.cache.move_to_end(k);return self.cache[k]
        offset,stored,raw,digest=self.entries[k];data=os.pread(self.file.fileno(),stored,offset)
        if len(data)!=stored:raise ValueError('Truncated compressed assets')
        if stored!=raw:
            decoder=zstd.ZstdDecompressor(options={zstd.DecompressionParameter.window_log_max:20})
            data=decoder.decompress(data,max_length=raw+1)
            if not decoder.eof or decoder.unused_data:raise ValueError('Invalid compressed asset frame')
        if len(data)!=raw or hashlib.sha256(data).digest()!=digest:raise ValueError('Compressed asset block checksum failed')
        while len(self.cache)>=max(1,(4<<20)//self.block):self.cache.popitem(last=False)
        self.cache[k]=data;return data
    def readinto(self,buffer):
        wanted=min(len(buffer),max(0,self.size-self.position));done=0
        while done<wanted:
            k,at=divmod(self.position,self.block);data=self.block_data(k);n=min(wanted-done,len(data)-at)
            buffer[done:done+n]=data[at:at+n];done+=n;self.position+=n
        return done
    def close(self):
        if hasattr(self,'file'):self.file.close()
        if hasattr(self,'cache'):self.cache.clear()
        super().close()

def identity(path):
    s=Path(path).stat();return s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns

def convert(c,source,destination,compressed):
    source,destination=Path(source),Path(destination);before=identity(source)
    if destination.exists():raise FileExistsError(destination)
    fd,temporary=tempfile.mkstemp(prefix='.'+destination.name+'.',suffix='.part',dir=destination.parent)
    try:
        out=os.fdopen(fd,'w+b')
        try:incoming=Reader(source) if is_compressed(source) else source.open('rb')
        except BaseException:out.close();raise
        with incoming,out:
            size=incoming.size if isinstance(incoming,Reader) else before[2];done=0;table=bytearray()
            if compressed:out.write(bytes(HEADER.size))
            while data:=incoming.read(BLOCK):
                c.check()
                if compressed:
                    encoded=zstd.compress(data,level=3)
                    if len(encoded)>=len(data):encoded=data
                    table.extend(ENTRY.pack(out.tell(),len(encoded),len(data),hashlib.sha256(data).digest()));out.write(encoded)
                else:out.write(data)
                done+=len(data);c.progress(done,size)
            if done!=size:raise ValueError('Asset source changed')
            if compressed:
                offset=out.tell();out.write(table);zero=HEADER.pack(MAGIC,size,BLOCK,len(table)//ENTRY.size,offset,bytes(32),2,0)
                head=HEADER.pack(MAGIC,size,BLOCK,len(table)//ENTRY.size,offset,hashlib.sha256(zero+table).digest(),2,0);out.seek(0);out.write(head)
            out.flush();os.fsync(out.fileno())
        c.emit('message','Verifying converted asset bytes')
        original=Reader(source) if is_compressed(source) else source.open('rb')
        result=Reader(temporary) if compressed else open(temporary,'rb')
        with original,result:
            done=0
            while data:=original.read(1<<20):
                c.check()
                if result.read(len(data))!=data:raise ValueError('Converted asset verification failed')
                done+=len(data);c.progress(done,size)
            if result.read(1):raise ValueError('Converted asset size mismatch')
        if identity(source)!=before:raise ValueError('Asset source changed during conversion')
        os.link(temporary,destination)
    finally:
        os.unlink(temporary)

def validate_romfs(rfs,path,marker=None):
    with Reader(path) as reader:
        image=rfs.Image(path,opener=Reader,logical_size=reader.size)
        if marker:image.find(marker)
        return image
