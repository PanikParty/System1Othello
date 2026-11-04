/* s1othello native core: bitboard move generation, an exact endgame solver and a
 * depth-limited midgame search. Loaded through ctypes by s1othello/native/__init__.py.
 *
 * Square index sq = row * 8 + col, A1 = bit 0, H8 = bit 63 (same as engine.py).
 * P = discs of the side to move, O = the opponent's discs.
 * Exact scores are the final disc differential (P - O) with empty squares uncounted,
 * which matches engine.disc_counts. Single-threaded: one process, one search at a time.
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef uint64_t u64;

static inline int popc(u64 b) { return __builtin_popcountll(b); }

static inline u64 run_l(u64 P, u64 M, int s) {
    u64 t = M & (P << s);
    t |= M & (t << s); t |= M & (t << s); t |= M & (t << s); t |= M & (t << s); t |= M & (t << s);
    return t << s;
}

static inline u64 run_r(u64 P, u64 M, int s) {
    u64 t = M & (P >> s);
    t |= M & (t >> s); t |= M & (t >> s); t |= M & (t >> s); t |= M & (t >> s); t |= M & (t >> s);
    return t >> s;
}

u64 ob_moves(u64 P, u64 O) {
    u64 H = O & 0x7E7E7E7E7E7E7E7EULL;  /* drop files A and H so runs cannot wrap */
    u64 m = run_l(P, H, 1) | run_r(P, H, 1) | run_l(P, O, 8) | run_r(P, O, 8)
          | run_l(P, H, 7) | run_r(P, H, 7) | run_l(P, H, 9) | run_r(P, H, 9);
    return m & ~(P | O);
}

static const int DR[8] = {-1, -1, -1, 0, 0, 1, 1, 1};
static const int DC[8] = {-1, 0, 1, -1, 1, -1, 0, 1};

u64 ob_flips(u64 P, u64 O, int sq) {
    u64 f = 0;
    int r0 = sq >> 3, c0 = sq & 7;
    for (int d = 0; d < 8; d++) {
        u64 line = 0;
        int r = r0 + DR[d], c = c0 + DC[d];
        while (r >= 0 && r < 8 && c >= 0 && c < 8) {
            u64 b = 1ULL << (r * 8 + c);
            if (O & b) { line |= b; r += DR[d]; c += DC[d]; continue; }
            if (P & b) f |= line;
            break;
        }
    }
    return f;
}

/* ---------- exact solver ---------- */

#define TT_BITS 21
#define TT_MIN_EMPTIES 9
typedef struct { u64 P, O; int8_t lo, hi; } TTE;
static TTE *tt = NULL;
static long long nodes = 0;

static inline TTE *tt_slot(u64 P, u64 O) {
    u64 h = (P * 0x9E3779B97F4A7C15ULL) ^ (O * 0xC2B2AE3D27D4EB4FULL);
    return &tt[h >> (64 - TT_BITS)];
}

static const u64 CORNERS = 0x8100000000000081ULL;

static int solve(u64 P, u64 O, int alpha, int beta) {
    nodes++;
    u64 mv = ob_moves(P, O);
    if (!mv) {
        if (!ob_moves(O, P)) return popc(P) - popc(O);
        return -solve(O, P, -beta, -alpha);
    }
    int empties = 64 - popc(P | O);
    TTE *e = NULL;
    int a0 = alpha;
    if (tt && empties >= TT_MIN_EMPTIES) {
        e = tt_slot(P, O);
        if (e->P == P && e->O == O) {
            if (e->lo >= beta) return e->lo;
            if (e->hi <= alpha) return e->hi;
            if (e->lo > alpha) alpha = e->lo;
            if (e->hi < beta) beta = e->hi;
            a0 = alpha;
        }
    }
    int sq[32], key[32], n = 0;
    u64 fl[32];
    while (mv) {
        int s = __builtin_ctzll(mv);
        mv &= mv - 1;
        u64 f = ob_flips(P, O, s);
        int k = 0;
        if (empties > 7) {  /* fastest-first: fewest opponent replies, corners first */
            u64 nP = P | f | (1ULL << s), nO = O & ~f;
            k = popc(ob_moves(nO, nP)) * 4 - (((1ULL << s) & CORNERS) ? 8 : 0);
        }
        int i = n++;
        while (i > 0 && key[i - 1] > k) { sq[i] = sq[i - 1]; key[i] = key[i - 1]; fl[i] = fl[i - 1]; i--; }
        sq[i] = s; key[i] = k; fl[i] = f;
    }
    int best = -65;
    for (int i = 0; i < n; i++) {
        u64 nP = P | fl[i] | (1ULL << sq[i]), nO = O & ~fl[i];
        int v = -solve(nO, nP, -beta, -alpha);
        if (v > best) {
            best = v;
            if (v > alpha) { alpha = v; if (alpha >= beta) break; }
        }
    }
    if (e) {
        if (!(e->P == P && e->O == O)) { e->P = P; e->O = O; e->lo = -64; e->hi = 64; }
        if (best <= a0) e->hi = (int8_t)best;
        else if (best >= beta) e->lo = (int8_t)best;
        else { e->lo = (int8_t)best; e->hi = (int8_t)best; }
    }
    return best;
}

int ob_init(void) {
    if (!tt) tt = calloc((size_t)1 << TT_BITS, sizeof(TTE));
    return tt != NULL;
}

int ob_solve(u64 P, u64 O) {
    ob_init();
    return solve(P, O, -65, 65);
}

long long ob_nodes(void) { return nodes; }

/* ---------- depth-limited midgame search ---------- */

/* Static evaluation for the midgame proxy, in "eval points". Deliberately not the
 * heuristic backend's square table: corners, squares next to empty corners,
 * mobility and frontier discs. Terminal positions score +-(10000 + disc diff). */
static const u64 XSQ[4] = {1ULL << 9, 1ULL << 14, 1ULL << 49, 1ULL << 54};
static const u64 CSQ[4] = {(1ULL << 1) | (1ULL << 8), (1ULL << 6) | (1ULL << 15),
                           (1ULL << 48) | (1ULL << 57), (1ULL << 55) | (1ULL << 62)};
static const u64 CRN[4] = {1ULL << 0, 1ULL << 7, 1ULL << 56, 1ULL << 63};

static u64 neighbours(u64 b) {
    u64 notA = 0xFEFEFEFEFEFEFEFEULL, notH = 0x7F7F7F7F7F7F7F7FULL;
    return ((b << 1) & notA) | ((b >> 1) & notH) | (b << 8) | (b >> 8)
         | ((b << 9) & notA) | ((b << 7) & notH) | ((b >> 7) & notA) | ((b >> 9) & notH);
}

static int eval_mid(u64 P, u64 O) {
    int v = 0;
    for (int i = 0; i < 4; i++) {
        if (P & CRN[i]) v += 30;
        else if (O & CRN[i]) v -= 30;
        else {
            v -= 15 * (popc(P & XSQ[i]) - popc(O & XSQ[i]));
            v -= 5 * (popc(P & CSQ[i]) - popc(O & CSQ[i]));
        }
    }
    v += 6 * (popc(ob_moves(P, O)) - popc(ob_moves(O, P)));
    u64 fr = neighbours(~(P | O));
    v -= 2 * (popc(P & fr) - popc(O & fr));
    return v;
}

static int search(u64 P, u64 O, int depth, int alpha, int beta) {
    nodes++;
    u64 mv = ob_moves(P, O);
    if (!mv) {
        if (!ob_moves(O, P)) {
            int d = popc(P) - popc(O);
            return d > 0 ? 10000 + d : (d < 0 ? -10000 + d : 0);
        }
        return -search(O, P, depth, -beta, -alpha);  /* a pass does not use up depth */
    }
    if (depth <= 0) return eval_mid(P, O);
    int best = -100000;
    while (mv) {
        int s = __builtin_ctzll(mv);
        mv &= mv - 1;
        u64 f = ob_flips(P, O, s);
        int v = -search(O & ~f, P | f | (1ULL << s), depth - 1, -beta, -alpha);
        if (v > best) {
            best = v;
            if (v > alpha) { alpha = v; if (alpha >= beta) break; }
        }
    }
    return best;
}

/* Value of every legal move for the side to move, from its perspective.
 * exact != 0: exact final disc differential. Otherwise: depth-limited search score
 * (the move itself counts as one ply). Returns the number of moves written. */
int ob_move_values(u64 P, u64 O, int depth, int exact, int *out_sq, int *out_val) {
    ob_init();
    u64 mv = ob_moves(P, O);
    int n = 0;
    while (mv) {
        int s = __builtin_ctzll(mv);
        mv &= mv - 1;
        u64 f = ob_flips(P, O, s);
        u64 nP = P | f | (1ULL << s), nO = O & ~f;
        out_sq[n] = s;
        out_val[n] = exact ? -solve(nO, nP, -65, 65) : -search(nO, nP, depth - 1, -100000, 100000);
        n++;
    }
    return n;
}
