#!/usr/bin/env python3
"""Dump dynamic symbols from a PS4 ELF (ET_SCE_DYNAMIC) — imports or all.

PS4 game executables have NO section headers (e_shoff=0, shnum=0), so
readelf/objdump see nothing. The dynamic symbol table must be found by
walking the PT_DYNAMIC program header and mapping virtual addresses to
file offsets via PT_LOAD segments.

Usage:
    python3 ps4_elf_imports.py <eboot.bin> [--all] [--filter <substring>]
        --filter   only symbols containing this substring (case-insensitive)
        --all      list ALL dynamic symbols (not just undefined imports)
        --verbose  also print symbol counts and DT entries

Returns the sorted list of imported (SHN_UNDEF) symbol names; with --all,
every defined+undefined symbol with its address/size.

Verified against Beat Saber eboot.bin (CUSA12878 patch 2.04).

NOTE: PS4 game/app dynsym entries are NID-obfuscated (11-char base64-ish
hashes + '#lib#mod' suffixes), NOT readable names — readable names only
appear in toolchain-built stubs. To decode game NIDs, join them against a NID
database (e.g. shadPS4's src/core/aerolib/aerolib.inl, format
STUB("NID", name)). Exp 278 used this to prove Beat Saber imports
scePadRead (NID q1cHNfGycLI) and does NOT import scePadReadState.
"""
import argparse
import struct
import sys

PT_LOAD = 1
PT_DYNAMIC = 2
PT_SCE_DYNLIBDATA = 0x61000000

DT_NULL = 0
DT_HASH = 4
DT_STRTAB = 5
DT_SYMTAB = 6
DT_GNU_HASH = 0x6FFFFEF5

# PS4 ET_SCE_DYNAMIC/ET_SCE_DYNEXEC dynamic tags (OpenOrbis PS4 ELF Spec).
# NOTE: the SCE tag values are FILE OFFSETS RELATIVE TO THE PT_SCE_DYNLIBDATA
# SEGMENT (phdr p_type 0x61000000) — not file offsets and not vaddrs.
# Verified self-consistent on Beat Saber's eboot.bin:
#   dynlibdata(0x1bd5570) + STRTAB(0x18) + STRSZ(0x3ca0) == dynlibdata + SYMTAB(0x3cb8);
#   SYMTAB + SYMTABSZ(0x5268) == JMPREL(0x8f20).
DT_SCE_HASH = 0x61000025
DT_SCE_PLTGOT = 0x61000027
DT_SCE_JMPREL = 0x61000029
DT_SCE_PLTREL = 0x6100002B
DT_SCE_PLTRELSZ = 0x6100002D
DT_SCE_RELA = 0x6100002F
DT_SCE_RELASZ = 0x61000031
DT_SCE_RELAENT = 0x61000033
DT_SCE_STRTAB = 0x61000035
DT_SCE_STRSZ = 0x61000037
DT_SCE_SYMTAB = 0x61000039
DT_SCE_SYMENT = 0x6100003B
DT_SCE_HASHSZ = 0x6100003D
DT_SCE_SYMTABSZ = 0x6100003F

ELF_MAGIC = b"\x7fELF"


def parse_phdrs(data: bytes) -> list[tuple[int, int, int, int]]:
    """Return [(p_type, p_offset, p_vaddr, p_filesz)] for each program header."""
    if data[:4] != ELF_MAGIC:
        raise SystemExit("not an ELF file")
    e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", data, 0x36)[0]
    e_phnum = struct.unpack_from("<H", data, 0x38)[0]
    phdrs = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        (p_type, p_flags, p_offset, p_vaddr, _p_paddr,
         p_filesz, _p_memsz, _p_align) = struct.unpack_from("<IIQQQQQQ", data, off)
        phdrs.append((p_type, p_offset, p_vaddr, p_filesz))
    return phdrs


def vaddr_to_off(phdrs, vaddr: int) -> int | None:
    for p_type, p_offset, p_vaddr, p_filesz in phdrs:
        if p_type == PT_LOAD and p_vaddr <= vaddr < p_vaddr + p_filesz:
            return p_offset + (vaddr - p_vaddr)
    return None


def find_dynamic(data: bytes, phdrs) -> tuple[dict, list[tuple[int, int]]]:
    dyn_off = None
    dyn_sz = 0
    for p_type, p_offset, p_vaddr, p_filesz in phdrs:
        if p_type == PT_DYNAMIC:
            dyn_off, dyn_sz = p_offset, p_filesz
            break
    if dyn_off is None:
        raise SystemExit("no PT_DYNAMIC segment")
    entries = []
    dt = {}
    for off in range(dyn_off, dyn_off + dyn_sz, 16):
        tag, val = struct.unpack_from("<QQ", data, off)
        if tag == DT_NULL:
            break
        entries.append((tag, val))
        dt.setdefault(tag, val)
    return dt, entries


def symbol_count(data: bytes, dt: dict, symtab_off: int, strtab_off: int) -> int:
    # PS4 path: SYMTABSZ / SYMENT (file offsets, no vaddr math)
    if DT_SCE_SYMTABSZ in dt:
        syment = dt.get(DT_SCE_SYMENT, 24)
        if syment:
            return dt[DT_SCE_SYMTABSZ] // syment
    if DT_HASH in dt:
        hash_off = dt[DT_HASH]
        # nbucket @ +0, nchain @ +4; nchain == number of dynsyms
        nchain = struct.unpack_from("<I", data, hash_off + 4)[0]
        return nchain
    if DT_GNU_HASH in dt:
        gnu_off = dt[DT_GNU_HASH]
        nbuckets = struct.unpack_from("<I", data, gnu_off)[0]
        symoffset = struct.unpack_from("<I", data, gnu_off + 4)[0]
        bloom_size = struct.unpack_from("<I", data, gnu_off + 8)[0]
        # bloom (8B words), then buckets (4B), then chain (4B each)
        buckets_off = gnu_off + 16 + bloom_size * 8
        max_bucket = 0
        for i in range(nbuckets):
            b = struct.unpack_from("<I", data, buckets_off + i * 4)[0]
            if b > max_bucket:
                max_bucket = b
        chain_off = buckets_off + nbuckets * 4
        if max_bucket < symoffset:
            return symoffset
        idx = max_bucket
        while True:
            val = struct.unpack_from("<I", data, chain_off + (idx - symoffset) * 4)[0]
            if val & 1:
                break
            idx += 1
        return idx + 1
    # Fallback: symtab is contiguous, strtab usually follows immediately
    if strtab_off > symtab_off:
        return (strtab_off - symtab_off) // 24
    raise SystemExit("cannot determine symbol count")


def read_cstr(data: bytes, off: int) -> str:
    end = data.find(b"\x00", off)
    if end == -1:
        return ""
    return data[off:end].decode("utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser(description="Dump PS4 ELF dynamic symbols")
    ap.add_argument("elf")
    ap.add_argument("--all", action="store_true", help="list all symbols, not just imports")
    ap.add_argument("--filter", default=None, help="substring filter (case-insensitive)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    data = open(args.elf, "rb").read()
    phdrs = parse_phdrs(data)
    dt, entries = find_dynamic(data, phdrs)
    if args.verbose:
        names = {DT_HASH: "DT_HASH", DT_STRTAB: "DT_STRTAB", DT_SYMTAB: "DT_SYMTAB",
                 DT_GNU_HASH: "DT_GNU_HASH", DT_SCE_HASH: "DT_SCE_HASH",
                 DT_SCE_PLTGOT: "DT_SCE_PLTGOT", DT_SCE_JMPREL: "DT_SCE_JMPREL",
                 DT_SCE_PLTREL: "DT_SCE_PLTREL", DT_SCE_PLTRELSZ: "DT_SCE_PLTRELSZ",
                 DT_SCE_RELA: "DT_SCE_RELA", DT_SCE_RELASZ: "DT_SCE_RELASZ",
                 DT_SCE_RELAENT: "DT_SCE_RELAENT", DT_SCE_STRTAB: "DT_SCE_STRTAB",
                 DT_SCE_STRSZ: "DT_SCE_STRSZ", DT_SCE_SYMTAB: "DT_SCE_SYMTAB",
                 DT_SCE_SYMENT: "DT_SCE_SYMENT", DT_SCE_HASHSZ: "DT_SCE_HASHSZ",
                 DT_SCE_SYMTABSZ: "DT_SCE_SYMTABSZ"}
        print(f"program headers: {len(phdrs)}", file=sys.stderr)
        for tag, val in entries:
            print(f"  {names.get(tag, hex(tag))} = {hex(val)}", file=sys.stderr)

    # SCE tags are offsets relative to the PT_SCE_DYNLIBDATA segment.
    if DT_SCE_STRTAB in dt:
        dynlib_base = None
        for p_type, p_offset, p_vaddr, p_filesz in phdrs:
            if p_type == PT_SCE_DYNLIBDATA:
                dynlib_base = p_offset
                break
        if dynlib_base is None:
            raise SystemExit("DT_SCE_* tags present but no PT_SCE_DYNLIBDATA segment")
        strtab_off = dynlib_base + dt[DT_SCE_STRTAB]
        symtab_off = dynlib_base + dt[DT_SCE_SYMTAB]
    else:
        strtab_off = vaddr_to_off(phdrs, dt[DT_STRTAB])
        symtab_off = vaddr_to_off(phdrs, dt[DT_SYMTAB])
    if strtab_off is None or symtab_off is None:
        raise SystemExit("symtab/strtab not found (need DT_SCE_* or DT_STRTAB/DT_SYMTAB)")

    nsyms = symbol_count(data, dt, symtab_off, strtab_off)
    if args.verbose:
        print(f"symbol count: {nsyms}", file=sys.stderr)

    results = []
    for i in range(nsyms):
        off = symtab_off + i * 24
        st_name, st_info, st_other, st_shndx, st_value, st_size = struct.unpack_from("<IBBHQQ", data, off)
        name = read_cstr(data, strtab_off + st_name) if st_name else ""
        is_import = st_shndx == 0 and st_value == 0
        if args.all:
            results.append((name, is_import, st_value, st_size))
        elif is_import:
            results.append((name, is_import, st_value, st_size))

    flt = args.filter.lower() if args.filter else None
    for name, is_import, value, size in results:
        if flt and flt not in name.lower():
            continue
        if args.all:
            kind = "IMP" if is_import else "DEF"
            print(f"{kind} {name} value={hex(value)} size={size}")
        else:
            print(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
