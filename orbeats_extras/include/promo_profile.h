// CUSA12878/2.04 only; fingerprints, not copyrighted binary bodies.
#pragma once
#include "health.h"
namespace OrBeatsExtras {
static const CodeSpec kPromoCode[]={
    {0x1c40fc0,0xc10,UINT64_C(0x274845f9baa34804)}, // main-menu activation; first17 bytes are whole nonrelative instructions
    {0x1c41fe0,0x4b0,UINT64_C(0xa4a02c278a87f752)}, // async promo completion: updates banner children, not its component root
    {0x1b97ff0,0x100,UINT64_C(0xd430ebee8e029bd7)}, // banner loading: child visibility only
    {0x1b980f0,0x2a0,UINT64_C(0xf38cfb95bb7aaf33)}, // banner setup: child visibility only
};
} // namespace
