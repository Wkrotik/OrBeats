// Bounded kernel-only media IO; no Unity calls or all-library raw-byte cache.
#pragma once
#include "additive_menu_profile.h"
#include "additive_probe_profile.h"
#include "additive_menu_media.h"
namespace BsdAdditive {
struct MenuFileIo {
    int (*open)(const char*);
    int64_t (*read)(int,void*,size_t);
    void (*close)(int);
    void* (*allocate)(size_t);
    void (*release)(void*);
};
struct MenuFileDiagnostic {
    const char* stage="none";int64_t code=0;size_t actual=0;
    uint64_t hash=UINT64_C(14695981039346656037);
};
// out==NULL validates via fixed-size stack storage without retaining raw files.
// With out, ownership transfers only after exact length/EOF/FNV verification.
inline int read_menu_file(const MenuFileIo& io,const MenuFileSpec& spec,
                          MediaBytes* out,MenuFileDiagnostic* d){
    *d=MenuFileDiagnostic{};
    if(!spec.path||!spec.bytes||spec.bytes>6000000){d->stage="bounds";return -1;}
    int fd=io.open(spec.path);
    if(fd<0){d->stage="open";d->code=fd;return -1;}
    unsigned char* data=NULL;
    if(out){
        if(out->data||out->size){io.close(fd);d->stage="occupied-output";return -1;}
        data=(unsigned char*)io.allocate(spec.bytes);
        if(!data){io.close(fd);d->stage="allocation";return -1;}
    }
    unsigned char scratch[8192];bool valid=true;
    while(d->actual<spec.bytes){
        size_t count=spec.bytes-d->actual;if(count>sizeof(scratch))count=sizeof(scratch);
        unsigned char* target=data?data+d->actual:scratch;
        int64_t n=io.read(fd,target,count);
        if(n<=0||(uint64_t)n>count){d->stage=n<0?"read":"length";d->code=n;valid=false;break;}
        d->hash=probe_fnv_update(d->hash,target,(size_t)n);d->actual+=(size_t)n;
    }
    if(valid){
        unsigned char extra=0;int64_t tail=io.read(fd,&extra,1);
        if(tail!=0){d->stage="tail";d->code=tail;valid=false;}
        else if(d->hash!=spec.fnv){d->stage="checksum";valid=false;}
    }
    io.close(fd);
    if(!valid){if(data)io.release(data);return -1;}
    if(out){out->data=data;out->size=spec.bytes;}
    d->stage="verified";return 1;
}
}
