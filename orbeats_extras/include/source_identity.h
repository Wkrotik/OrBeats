#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>
namespace OrBeatsExtras {
static const size_t kSourceIdentityBytes=158;
inline uint64_t source_checksum(const unsigned char* raw,size_t bytes) {
    uint64_t value=UINT64_C(14695981039346656037);
    for(size_t i=0;i<bytes;++i){value^=raw[i];value*=UINT64_C(1099511628211);}return value;
}
inline bool own_level(const char* id) {
    if(!id || strlen(id)!=37 || strncmp(id,"bsd_additive_",13))return false;
    for(size_t i=13;i<37;++i)if(!((id[i]>='0'&&id[i]<='9')||(id[i]>='a'&&id[i]<='f')))return false;
    return true;
}
inline bool source_identity(const unsigned char* raw,size_t bytes,const char* id,const char* bundle,uint32_t mask,char hash[41]) {
    memset(hash,0,41);
    if(!raw || bytes!=kSourceIdentityBytes || !own_level(id) || !bundle || strlen(bundle)!=64 ||
       mask>31 || memcmp(raw,"ORBSSRC1",8) || memcmp(raw+8,id,37) || memcmp(raw+45,bundle,64) || raw[149]!=mask)return false;
    uint64_t expected=0;for(size_t i=0;i<8;++i)expected|=uint64_t(raw[150+i])<<(8*i);
    if(source_checksum(raw,150)!=expected)return false; // detect corruption, not authentication
    for(size_t i=109;i<149;++i)if(!((raw[i]>='0'&&raw[i]<='9')||(raw[i]>='a'&&raw[i]<='f')))return false;
    memcpy(hash,raw+109,40);return true;
}
} // namespace
