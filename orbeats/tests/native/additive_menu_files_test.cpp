#include "additive_menu_files.h"
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <vector>
#include <map>
using namespace BsdAdditive;
static std::vector<unsigned char> bytes(1764078,42);
static size_t offset=0,live=0,peak=0,budget=3000000,allocations=0,limit=8192;
static int opened=0,closed=0;static bool missing=false,read_error=false,oversized=false;
static std::map<void*,size_t> sizes;
static int op(const char*){if(missing)return -2;offset=0;++opened;return 3;}
static int64_t rd(int fd,void* out,size_t n){
 assert(fd==3);if(read_error)return -7;if(oversized)return (int64_t)n+1;
 if(n>limit)n=limit;if(n>bytes.size()-offset)n=bytes.size()-offset;
 memcpy(out,bytes.data()+offset,n);offset+=n;return (int64_t)n;
}
static void cl(int fd){assert(fd==3);++closed;}
static void* al(size_t n){++allocations;if(n>budget-live)return NULL;void* p=malloc(n);assert(p);sizes[p]=n;live+=n;if(live>peak)peak=live;return p;}
static void fr(void* p){assert(p&&sizes.count(p));live-=sizes[p];sizes.erase(p);free(p);}
static MenuFileIo io={op,rd,cl,al,fr};
static MenuFileSpec spec(){return {"fixture.wav",bytes.size(),probe_fnv_update(UINT64_C(14695981039346656037),bytes.data(),bytes.size())};}
static void drop(MediaBytes& out){if(out.data)fr((void*)out.data);out={};}
int main(){
 MenuFileDiagnostic d;MediaBytes out={};auto s=spec();
 assert(read_menu_file(io,s,NULL,&d)==1&&allocations==0&&live==0);
 limit=257;assert(read_menu_file(io,s,&out,&d)==1&&out.size==s.bytes);drop(out);limit=8192;
 auto fail=[&](const char* stage){assert(read_menu_file(io,s,&out,&d)==-1);assert(!strcmp(d.stage,stage)&&!out.data&&!live);};
 missing=true;fail("open");missing=false;
 budget=1;fail("allocation");budget=3000000;
 read_error=true;fail("read");assert(d.code==-7);read_error=false;
 oversized=true;fail("length");oversized=false;
 s.bytes-=1;fail("tail");s=spec();
 s.bytes+=1;fail("length");s=spec();
 s.fnv^=1;fail("checksum");s=spec();
 s.bytes=6000001;fail("bounds");s=spec();
 assert(opened==closed);
 // Validate 64 media sets without raw heap allocation, then construct one pair
 // at a time under a budget where two retained previews cannot coexist.
 allocations=0;for(int i=0;i<64;++i)assert(read_menu_file(io,s,NULL,&d)==1);
 assert(allocations==0);
 for(int i=0;i<64;++i){
  MediaBytes preview={};assert(read_menu_file(io,s,&preview,&d)==1);
  void* cover=al(700000);assert(cover);void* pack=al(31229);assert(pack);
  fr(cover);fr(pack);drop(preview);assert(live==0);
 }
 MediaBytes first={},second={};assert(read_menu_file(io,s,&first,&d)==1);
 assert(read_menu_file(io,s,&second,&d)==-1&&!strcmp(d.stage,"allocation"));drop(first);
 assert(live==0&&sizes.empty()&&opened==closed&&peak<=budget);
 puts("64-song bounded media IO, integrity and allocation diagnostics passed");
}
