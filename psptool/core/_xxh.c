/* xxHash32 / xxHash64, written from the public algorithm description
 * (little-endian input, as on the PSP and on x86/ARM hosts). */
#include <stdint.h>
#include <stddef.h>
#include <string.h>

static const uint32_t P32_1 = 2654435761U, P32_2 = 2246822519U, P32_3 = 3266489917U,
                      P32_4 = 668265263U, P32_5 = 374761393U;
static const uint64_t P64_1 = 11400714785074694791ULL, P64_2 = 14029467366897019727ULL,
                      P64_3 = 1609587929392839161ULL, P64_4 = 9650029242287828579ULL,
                      P64_5 = 2870177450012600261ULL;

static uint32_t rd32(const uint8_t *p) { uint32_t v; memcpy(&v, p, 4); return v; }
static uint64_t rd64(const uint8_t *p) { uint64_t v; memcpy(&v, p, 8); return v; }
static uint32_t rol32(uint32_t x, int r) { return (x << r) | (x >> (32 - r)); }
static uint64_t rol64(uint64_t x, int r) { return (x << r) | (x >> (64 - r)); }

static uint32_t r32(uint32_t acc, uint32_t in) { return rol32(acc + in * P32_2, 13) * P32_1; }

uint32_t psptool_xxh32(const uint8_t *p, size_t len, uint32_t seed) {
    const uint8_t *end = p + len;
    uint32_t h;
    if (len >= 16) {
        uint32_t v1 = seed + P32_1 + P32_2, v2 = seed + P32_2, v3 = seed, v4 = seed - P32_1;
        const uint8_t *limit = end - 16;
        do {
            v1 = r32(v1, rd32(p)); v2 = r32(v2, rd32(p + 4));
            v3 = r32(v3, rd32(p + 8)); v4 = r32(v4, rd32(p + 12));
            p += 16;
        } while (p <= limit);
        h = rol32(v1, 1) + rol32(v2, 7) + rol32(v3, 12) + rol32(v4, 18);
    } else {
        h = seed + P32_5;
    }
    h += (uint32_t)len;
    while (p + 4 <= end) { h = rol32(h + rd32(p) * P32_3, 17) * P32_4; p += 4; }
    while (p < end) { h = rol32(h + (*p) * P32_5, 11) * P32_1; p++; }
    h ^= h >> 15; h *= P32_2; h ^= h >> 13; h *= P32_3; h ^= h >> 16;
    return h;
}

static uint64_t r64(uint64_t acc, uint64_t in) { return rol64(acc + in * P64_2, 31) * P64_1; }
static uint64_t merge64(uint64_t acc, uint64_t v) { acc ^= r64(0, v); return acc * P64_1 + P64_4; }

uint64_t psptool_xxh64(const uint8_t *p, size_t len, uint64_t seed) {
    const uint8_t *end = p + len;
    uint64_t h;
    if (len >= 32) {
        uint64_t v1 = seed + P64_1 + P64_2, v2 = seed + P64_2, v3 = seed, v4 = seed - P64_1;
        const uint8_t *limit = end - 32;
        do {
            v1 = r64(v1, rd64(p)); v2 = r64(v2, rd64(p + 8));
            v3 = r64(v3, rd64(p + 16)); v4 = r64(v4, rd64(p + 24));
            p += 32;
        } while (p <= limit);
        h = rol64(v1, 1) + rol64(v2, 7) + rol64(v3, 12) + rol64(v4, 18);
        h = merge64(h, v1); h = merge64(h, v2); h = merge64(h, v3); h = merge64(h, v4);
    } else {
        h = seed + P64_5;
    }
    h += (uint64_t)len;
    while (p + 8 <= end) { h ^= r64(0, rd64(p)); h = rol64(h, 27) * P64_1 + P64_4; p += 8; }
    if (p + 4 <= end) { h ^= (uint64_t)rd32(p) * P64_1; h = rol64(h, 23) * P64_2 + P64_3; p += 4; }
    while (p < end) { h ^= (*p) * P64_5; h = rol64(h, 11) * P64_1; p++; }
    h ^= h >> 33; h *= P64_2; h ^= h >> 29; h *= P64_3; h ^= h >> 32;
    return h;
}
