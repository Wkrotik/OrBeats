// Relocate only the fingerprint-verified 2.04 health activation prefix.
// No general instruction decoder, runtime code scan, or agreement callback.
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>
namespace OrBeatsExtras {
static const size_t kHealthPrefixBytes=18,kHealthTrampolineBytes=40;
inline bool health_activation_trampoline(const unsigned char* code,uintptr_t address,
                                        unsigned char* out,size_t capacity,uintptr_t& flag) {
    if(!code || !out || capacity<kHealthTrampolineBytes || address>UINTPTR_MAX-kHealthPrefixBytes ||
       code[11]!=0x80 || code[12]!=0x3d || code[17]!=0)return false;
    int32_t displacement=0;memcpy(&displacement,code+13,4);
    uintptr_t next=address+kHealthPrefixBytes;
    if(displacement>=0){if(next>UINTPTR_MAX-(uintptr_t)displacement)return false;flag=next+(uintptr_t)displacement;}
    else {uintptr_t distance=(uintptr_t)-(int64_t)displacement;if(next<distance)return false;flag=next-distance;}
    // Preserve the eleven non-relative prologue bytes, RAX and CMP flags.
    // movabs permits arbitrary mmap distance; no truncated RIP displacement.
    memcpy(out,code,11);out[11]=0x50;out[12]=0x48;out[13]=0xb8;
    memcpy(out+14,&flag,8);out[22]=0x80;out[23]=0x38;out[24]=0;out[25]=0x58;
    out[26]=0xff;out[27]=0x25;memset(out+28,0,4);memcpy(out+32,&next,8);
    return true;
}
} // namespace
