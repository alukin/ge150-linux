#!/usr/bin/env python3
"""Extract Qt rcc (v1/v2) resources embedded in a PE32 executable.

Usage: extract_qrc.py <exe> <tree_va> <names_va> <data_va> <version> <outdir>
The VAs are the arguments passed to qRegisterResourceData (found with REA/Ghidra).
"""
import os
import struct
import sys
import zlib


def load_pe(path):
    with open(path, 'rb') as f:
        d = f.read()
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    nsec = struct.unpack_from('<H', d, pe + 6)[0]
    opt = struct.unpack_from('<H', d, pe + 20)[0]
    base = struct.unpack_from('<I', d, pe + 24 + 28)[0]
    secs = []
    off = pe + 24 + opt
    for i in range(nsec):
        _, vs, va, rs, rp = struct.unpack_from('<8sIIII', d, off + i * 40)
        secs.append((base + va, max(vs, rs), rp))
    def va2off(va):
        for sva, size, rp in secs:
            if sva <= va < sva + size:
                return va - sva + rp
        raise ValueError(hex(va))
    return d, va2off

def main():
    exe, tree, names, data, ver, out = sys.argv[1:7]
    d, v2o = load_pe(exe)
    tree, names, data = (v2o(int(x, 16)) for x in (tree, names, data))
    ver = int(ver)
    esz = 22 if ver >= 2 else 14

    def name_at(o):
        n = struct.unpack_from('>H', d, names + o)[0]
        return d[names + o + 6: names + o + 6 + n * 2].decode('utf-16-be')

    def walk(idx, path):
        e = tree + idx * esz
        noff, flags = struct.unpack_from('>IH', d, e)
        name = name_at(noff) if idx else ''
        p = os.path.join(path, name)
        if flags & 2:  # directory
            cnt, first = struct.unpack_from('>II', d, e + 6)
            os.makedirs(p, exist_ok=True)
            for c in range(first, first + cnt):
                walk(c, p)
        else:
            doff = struct.unpack_from('>I', d, e + 10)[0]
            size = struct.unpack_from('>I', d, data + doff)[0]
            blob = d[data + doff + 4: data + doff + 4 + size]
            if flags & 1:
                blob = zlib.decompress(blob[4:])
            with open(p, 'wb') as f:
                f.write(blob)
            print(f'{len(blob):9d} {p}')
    walk(0, out)

if __name__ == '__main__':
    main()
