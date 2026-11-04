"""ctypes wrapper for ob.c, compiled on first use into ~/.cache/s1othello/.

The library is keyed by a hash of the source, so editing ob.c rebuilds it. Override the
compiler with $CC and the cache directory with $S1OTHELLO_CACHE.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
import platform
import subprocess
from pathlib import Path

from s1othello.engine import Board, rc_to_coord

_SRC = Path(__file__).with_name("ob.c")
_lib: ctypes.CDLL | None = None


def _build() -> Path:
    src = _SRC.read_bytes()
    tag = hashlib.sha1(src).hexdigest()[:12]
    cache = Path(os.environ.get("S1OTHELLO_CACHE", Path.home() / ".cache" / "s1othello"))
    cache.mkdir(parents=True, exist_ok=True)
    ext = "dylib" if platform.system() == "Darwin" else "so"
    out = cache / f"ob-{tag}-{platform.machine()}.{ext}"
    if not out.exists():
        tmp = out.with_suffix(f".{os.getpid()}.tmp")
        cmd = [os.environ.get("CC", "cc"), "-O3", "-std=c11", "-shared", "-fPIC", str(_SRC), "-o", str(tmp)]
        if platform.system() == "Darwin":
            # build for this Python's arch: a shell under Rosetta makes cc default to x86_64
            cmd[1:1] = ["-arch", platform.machine()]
        else:
            cmd[1:1] = ["-march=native"]
        subprocess.run(cmd, check=True, capture_output=True)
        tmp.replace(out)
    return out


def lib() -> ctypes.CDLL:
    global _lib
    if _lib is None:
        L = ctypes.CDLL(str(_build()))
        u64, i32 = ctypes.c_uint64, ctypes.c_int
        L.ob_moves.argtypes, L.ob_moves.restype = [u64, u64], u64
        L.ob_flips.argtypes, L.ob_flips.restype = [u64, u64, i32], u64
        L.ob_solve.argtypes, L.ob_solve.restype = [u64, u64], i32
        L.ob_nodes.argtypes, L.ob_nodes.restype = [], ctypes.c_longlong
        L.ob_move_values.argtypes = [u64, u64, i32, i32, ctypes.POINTER(i32), ctypes.POINTER(i32)]
        L.ob_move_values.restype = i32
        if not L.ob_init():
            raise MemoryError("ob_init: could not allocate the transposition table")
        _lib = L
    return _lib


def to_bitboards(board: Board, player: str) -> tuple[int, int]:
    """(P, O) for the side `player`, bit r*8+c set where that side has a disc."""
    p = o = 0
    for r, row in enumerate(board):
        for c, ch in enumerate(row):
            if ch == player:
                p |= 1 << (r * 8 + c)
            elif ch != ".":
                o |= 1 << (r * 8 + c)
    return p, o


def sq_to_coord(sq: int) -> str:
    return rc_to_coord(sq >> 3, sq & 7)


def moves(board: Board, player: str) -> list[str]:
    p, o = to_bitboards(board, player)
    m = lib().ob_moves(p, o)
    return [sq_to_coord(s) for s in range(64) if m >> s & 1]


def solve(board: Board, player: str) -> int:
    """Exact final disc differential for `player` (to move) under perfect play."""
    p, o = to_bitboards(board, player)
    return lib().ob_solve(p, o)


def move_values(board: Board, player: str, depth: int, exact: bool) -> dict[str, int]:
    """{coord: value} for every legal move, from `player`'s perspective."""
    p, o = to_bitboards(board, player)
    sq = (ctypes.c_int * 32)()
    val = (ctypes.c_int * 32)()
    n = lib().ob_move_values(p, o, depth, int(exact), sq, val)
    return {sq_to_coord(sq[i]): val[i] for i in range(n)}


def nodes() -> int:
    return lib().ob_nodes()
