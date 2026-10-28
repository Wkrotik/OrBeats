#include "additive_module_symbols.h"
#include <assert.h>
#include <stdio.h>
using namespace BsdAdditive;
static int calls, validations, wanted_handle, rc;
static void* supplied;
static int inside, marker;
static const char* wanted_name = "il2cpp_object_get_class";
static int32_t lookup(int32_t handle, const char* name, void** out) {
    ++calls; assert(handle == wanted_handle); assert(!strcmp(name, wanted_name));
    *out = supplied; return rc;
}
static bool validate(const void* context, const void* address) {
    ++validations; assert(context == &marker); assert(address == supplied);
    return inside != 0;
}
static void reset() { calls=validations=0; wanted_handle=47; rc=0; inside=1; supplied=&marker; }
int main() {
    reset();assert(module_symbol(47,wanted_name,lookup,validate,&marker)==&marker);assert(calls==1&&validations==1);
    reset();wanted_handle=0;assert(module_symbol(0,wanted_name,lookup,validate,&marker)==&marker);
    reset();assert(!module_symbol(-1,wanted_name,lookup,validate,&marker));assert(!calls);
    reset();assert(!module_symbol(47,NULL,lookup,validate,&marker));assert(!calls);
    reset();assert(!module_symbol(47,"il2cpp_",lookup,validate,&marker));assert(!calls);
    reset();assert(!module_symbol(47,"sceKernelDlsym",lookup,validate,&marker));assert(!calls);
    reset();assert(!module_symbol(47,wanted_name,NULL,validate,&marker));assert(!calls);
    reset();assert(!module_symbol(47,wanted_name,lookup,NULL,&marker));assert(!calls);
    reset();assert(!module_symbol(47,wanted_name,lookup,validate,NULL));assert(!calls);
    reset();rc=-1;assert(!module_symbol(47,wanted_name,lookup,validate,&marker));assert(calls==1&&!validations);
    reset();rc=1;assert(!module_symbol(47,wanted_name,lookup,validate,&marker));assert(calls==1&&!validations);
    reset();supplied=NULL;assert(!module_symbol(47,wanted_name,lookup,validate,&marker));assert(calls==1&&!validations);
    reset();inside=0;assert(!module_symbol(47,wanted_name,lookup,validate,&marker));assert(calls==1&&validations==1);
    puts("explicit module handle/name, loader failure, null and nonlocal/nonexecutable refusal checks passed");
}
