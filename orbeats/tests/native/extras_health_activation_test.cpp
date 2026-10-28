// Execute the production relocated prefix, not a mock returning success.
#include "health_activation.h"
#include <assert.h>
#include <sys/mman.h>
#include <unistd.h>
#include <limits.h>
using namespace OrBeatsExtras;
// JIT buffers have no compiler UBSan type descriptor before their entry.
// Disable only that indirect-call descriptor check, not memory/UB sanitizers.
__attribute__((no_sanitize("function"))) static int call_native(void* code){return ((int(*)())code)();}
int main(){
    unsigned char out[kHealthTrampolineBytes]={},input[18]={};uintptr_t flag=0;
    input[11]=0x80;input[12]=0x3d;input[17]=0;
    assert(!health_activation_trampoline(NULL,0,out,sizeof(out),flag));
    assert(!health_activation_trampoline(input,0,NULL,sizeof(out),flag));
    assert(!health_activation_trampoline(input,0,out,sizeof(out)-1,flag));
    assert(!health_activation_trampoline(input,UINTPTR_MAX-17,out,sizeof(out),flag));
    int32_t displacement=INT32_MIN;memcpy(input+13,&displacement,4);
    assert(!health_activation_trampoline(input,0,out,sizeof(out),flag));
    displacement=INT32_MAX;memcpy(input+13,&displacement,4);
    assert(!health_activation_trampoline(input,UINTPTR_MAX-18,out,sizeof(out),flag));
    input[12]=0x05;assert(!health_activation_trampoline(input,4096,out,sizeof(out),flag));
    size_t page=(size_t)sysconf(_SC_PAGESIZE);
    auto* source=(unsigned char*)mmap(NULL,page,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    auto* stub=(unsigned char*)mmap(NULL,page,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    assert(source!=MAP_FAILED && stub!=MAP_FAILED);
    // Synthetic prologue/epilogue with the same instruction forms as the
    // fingerprint-verified health method. No shipped private game bytes.
    const unsigned char prefix[]={0x55,0x48,0x89,0xe5,0x41,0x57,0x41,0x56,0x41,0x54,0x53};
    const unsigned char tail[]={0x0f,0x94,0xc0,0x0f,0xb6,0xc0,0x5b,0x41,0x5c,0x41,0x5e,0x41,0x5f,0x5d,0xc3};
    memcpy(source,prefix,sizeof(prefix));source[11]=0x80;source[12]=0x3d;source[17]=0;
    displacement=64-18;memcpy(source+13,&displacement,4);memcpy(source+18,tail,sizeof(tail));
    assert(health_activation_trampoline(source,(uintptr_t)source,stub,page,flag));assert(flag==(uintptr_t)(source+64));
    assert(!mprotect(source,page,PROT_READ|PROT_WRITE|PROT_EXEC));assert(!mprotect(stub,page,PROT_READ|PROT_EXEC));
    
    for(unsigned value=0;value<256;++value){source[64]=(unsigned char)value;assert(call_native(source)==(value==0));assert(call_native(stub)==call_native(source));}
    assert(!munmap(stub,page) && !munmap(source,page));return 0;
}
