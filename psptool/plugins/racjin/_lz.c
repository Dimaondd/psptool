/* Fast path for lz.decompress; same algorithm, see lz.py. */
#include <stddef.h>
#include <stdint.h>

long racjin_decompress(const uint8_t *src, size_t n, uint8_t *out, size_t size)
{
    uint32_t table[8192] = {0};
    uint8_t ring[256] = {0};
    size_t bitpos = 0, pos = 0, nbits = n * 8;
    while (pos < size && bitpos + 9 <= nbits) {
        size_t b = bitpos >> 3;
        uint32_t w = src[b] | (b + 1 < n ? src[b + 1] << 8 : 0);
        uint32_t v = (w >> (bitpos & 7)) & 0x1FF;
        bitpos += 9;
        uint8_t last = pos ? out[pos - 1] : 0;
        size_t start = pos;
        if (v & 0x100) {
            out[pos++] = v & 0xFF;
        } else {
            uint32_t s = table[(last << 5) | (v >> 3)];
            uint32_t len = (v & 7) + 1;
            for (uint32_t i = 0; i < len && pos < size; i++)
                out[pos++] = out[s + i];
        }
        table[(last << 5) | ring[last]] = (uint32_t)start;
        ring[last] = (ring[last] + 1) & 31;
    }
    return (long)pos;
}
