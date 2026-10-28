// CUSA12878/2.04 code fingerprints. No owned binary bytes are distributed.
#pragma once
#include "health.h"
namespace OrBeatsExtras {
static const CodeSpec kLeaderboardCode[]={
    {0x1c26290,0x120,UINT64_C(0x8dc6a106cf89280d)}, // setdata
    {0x1c264f0,0x120,UINT64_C(0xb6912fb2f2829302)}, // activate
    {0x1c26ed0,0x120,UINT64_C(0x5b107e4613c11473)}, // deactivate
    {0x1c272d0,0x120,UINT64_C(0x53c132445124cfac)}, // destroy
    {0x31f5a40,0x100,UINT64_C(0x86be8ee720212e6f)}, // process
    {0x1c28740,0xd0,UINT64_C(0x741fdfa07a7e16f0)}, // ctor
    {0x1c264b0,0x40,UINT64_C(0xfd18f25f8a5cbbc6)}, // stats
};
} // namespace
