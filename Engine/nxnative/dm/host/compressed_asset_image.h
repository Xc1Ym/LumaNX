/* LNXBLK01 prototype. Independent blocks, bounded cache, checksums, pread semantics.
 * macOS-only prototype: zstd/LZ4 static libraries supplied by benchmark build.
 * Not part of the installed app or the verified upstream engine snapshot. */
#pragma once
#include <stdint.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <pthread.h>
#include <CommonCrypto/CommonDigest.h>
#include <dlfcn.h>
/* Decode through the app's existing pinned libzstd; no Homebrew link dependency. */
static const char ax_capability[] __attribute__((used)) = "LUMANX_ASSET_COMPRESSION_V1";
typedef struct { void *library; void *(*create)(void); size_t (*destroy)(void *); size_t (*parameter)(void *,int,int); size_t (*decode)(void *,void *,size_t,const void *,size_t); unsigned (*error)(size_t); } ax_codec;
static ax_codec ax_zstd;
static pthread_once_t ax_codec_once = PTHREAD_ONCE_INIT;
static void ax_load_codec(void) {
 const char *path=getenv("DM_ASSET_ZSTD_LIBRARY");
 if(!path || path[0]!='/')return;
 ax_zstd.library=dlopen(path,RTLD_NOW|RTLD_LOCAL);if(!ax_zstd.library)return;
 #define AX_SYMBOL(field,name) *(void **)(&ax_zstd.field)=dlsym(ax_zstd.library,name)
 AX_SYMBOL(create,"ZSTD_createDCtx");AX_SYMBOL(destroy,"ZSTD_freeDCtx");AX_SYMBOL(parameter,"ZSTD_DCtx_setParameter");AX_SYMBOL(decode,"ZSTD_decompressDCtx");AX_SYMBOL(error,"ZSTD_isError");
 #undef AX_SYMBOL
}

typedef struct { char magic[8]; uint64_t logical; uint32_t block, count; uint64_t index; unsigned char hash[32]; uint32_t codec, flags; } __attribute__((packed)) ax_header;
typedef struct { uint64_t offset; uint32_t stored, raw; unsigned char hash[32]; } __attribute__((packed)) ax_entry;
_Static_assert(sizeof(ax_header)==72 && sizeof(ax_entry)==48,"asset container layout");
typedef struct { uint32_t block; uint64_t age; unsigned char *data; int valid; } ax_slot;
typedef struct { int fd; ax_header h; ax_entry *entries; ax_slot *slots; unsigned char *memory,*scratch; size_t nslots; uint64_t clock,hits,misses,physical; pthread_mutex_t lock; } ax_image;
static int ax_exact(int fd,void *buf,size_t size,uint64_t offset) {
 size_t got=0; while(got<size) { ssize_t n=pread(fd,(char*)buf+got,size-got,(off_t)(offset+got));if(n<0&&errno==EINTR)continue;if(n<=0){if(!n)errno=EIO;return 0;}got+=(size_t)n;}return 1;
}
static void ax_close(ax_image *a) {if(!a)return;close(a->fd);pthread_mutex_destroy(&a->lock);free(a->entries);free(a->slots);free(a->memory);free(a->scratch);free(a);}
static ax_image *ax_open(const char *path,size_t cache_bytes) {
 int fd=open(path,O_RDONLY);if(fd<0)return NULL;
 ax_image *a=calloc(1,sizeof *a);if(!a){close(fd);return NULL;}a->fd=fd;
 if(pthread_mutex_init(&a->lock,NULL)){close(fd);free(a);errno=ENOMEM;return NULL;}
 struct stat st;
 if(fstat(fd,&st)||!ax_exact(fd,&a->h,sizeof a->h,0))goto bad;
 pthread_once(&ax_codec_once,ax_load_codec);
 if(!ax_zstd.create||!ax_zstd.destroy||!ax_zstd.parameter||!ax_zstd.decode||!ax_zstd.error){errno=ENOTSUP;goto bad;}
 ax_header *h=&a->h;errno=EINVAL;
 if(memcmp(h->magic,"LNXBLK01",8)||h->flags||h->codec!=2||h->logical>INT64_MAX||h->block<65536||h->block>1048576||(h->block&(h->block-1)))goto bad;
 if(h->count!=h->logical/h->block+(h->logical%h->block!=0)||h->count>(64u<<20)/sizeof(ax_entry))goto bad;
 uint64_t bytes=(uint64_t)h->count*sizeof(ax_entry);
 if(st.st_size<0||h->index<sizeof *h||h->index>(uint64_t)st.st_size||bytes!=(uint64_t)st.st_size-h->index)goto bad;
 a->entries=malloc(bytes?bytes:1);if(!a->entries)goto bad;
 if(!ax_exact(fd,a->entries,(size_t)bytes,h->index))goto bad;
 ax_header zero=*h;memset(zero.hash,0,32);CC_SHA256_CTX ctx;unsigned char hash[32];
 CC_SHA256_Init(&ctx);CC_SHA256_Update(&ctx,&zero,sizeof zero);CC_SHA256_Update(&ctx,a->entries,(CC_LONG)bytes);CC_SHA256_Final(hash,&ctx);
 errno=EINVAL;if(memcmp(hash,h->hash,32))goto bad;
 uint64_t next=sizeof *h;
 for(uint32_t i=0;i<h->count;i++) {ax_entry *e=&a->entries[i];uint32_t raw=(uint32_t)((h->logical-(uint64_t)i*h->block)<h->block?h->logical-(uint64_t)i*h->block:h->block);
  if(e->offset!=next||!e->stored||e->stored>e->raw||e->raw!=raw||next>h->index||e->stored>h->index-next)goto bad;next+=e->stored;
 }
 if(next!=h->index)goto bad;
 if(cache_bytes<h->block||cache_bytes>(64u<<20)){errno=EINVAL;goto bad;}
 a->nslots=cache_bytes/h->block;a->slots=calloc(a->nslots,sizeof(ax_slot));a->memory=malloc(a->nslots*h->block);a->scratch=malloc(h->block);
 if(!a->slots||!a->memory||!a->scratch)goto bad;
 for(size_t i=0;i<a->nslots;i++)a->slots[i].data=a->memory+i*h->block;
 return a;
bad:{int error=errno;ax_close(a);errno=error;return NULL;}
}
/* Lock covers cache and backing reads; no mutable shared seek position. */
static ssize_t ax_pread(ax_image *a,void *out,size_t size,int64_t offset) {
 if(offset<0||size>SSIZE_MAX){errno=EINVAL;return -1;}if((uint64_t)offset>=a->h.logical)return 0;
 uint64_t available=a->h.logical-(uint64_t)offset;if(size>available)size=(size_t)available;
 pthread_mutex_lock(&a->lock);size_t done=0;
 while(done<size) {
  uint64_t pos=(uint64_t)offset+done;uint32_t block=(uint32_t)(pos/a->h.block);ax_entry *e=&a->entries[block];ax_slot *slot=NULL,*victim=&a->slots[0];
  for(size_t i=0;i<a->nslots;i++){ax_slot *s=&a->slots[i];if(s->valid&&s->block==block){slot=s;break;}if(!s->valid||(victim->valid&&s->age<victim->age))victim=s;}
  if(slot)a->hits++;
  else {slot=victim;slot->valid=0;a->misses++;
   if(!ax_exact(a->fd,a->scratch,e->stored,e->offset))goto bad;a->physical+=e->stored;
   size_t n;
   if(e->stored==e->raw){memcpy(slot->data,a->scratch,e->raw);n=e->raw;}
   else {void *dc=ax_zstd.create();if(!dc){errno=ENOMEM;goto bad;}size_t param=ax_zstd.parameter(dc,100,20);if(ax_zstd.error(param)){ax_zstd.destroy(dc);errno=EIO;goto bad;}n=ax_zstd.decode(dc,slot->data,e->raw,a->scratch,e->stored);ax_zstd.destroy(dc);if(ax_zstd.error(n)){errno=EIO;goto bad;}}
   if(n!=e->raw){errno=EIO;goto bad;}unsigned char hash[32];CC_SHA256(slot->data,(CC_LONG)n,hash);if(memcmp(hash,e->hash,32)){errno=EIO;goto bad;}
   slot->block=block;slot->valid=1;
  }
  slot->age=++a->clock;size_t at=(size_t)(pos%a->h.block),take=e->raw-at;if(take>size-done)take=size-done;
  memcpy((char*)out+done,slot->data+at,take);done+=take;
 }
 pthread_mutex_unlock(&a->lock);return (ssize_t)done;
bad:pthread_mutex_unlock(&a->lock);return -1;
}
