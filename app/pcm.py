"""16-bit PCM helpers. Uses audioop when installed, else a pure-Python fallback.

The fallback keeps logic modules importable (and testable) without the native
audio packages; capture and resampling still require audioop at runtime.
"""

from array import array
import math
import sys

try:
    import audioop
except ImportError:  # audioop-lts missing: only level measurement falls back
    audioop = None


def rms(pcm):
    """Root mean square of little-endian signed 16-bit mono samples."""
    if audioop is not None:
        return audioop.rms(pcm, 2)
    samples = array('h')
    samples.frombytes(pcm[: len(pcm) // 2 * 2])
    if sys.byteorder == 'big':
        samples.byteswap()
    if not samples:
        return 0
    return int(math.sqrt(sum(value * value for value in samples) / len(samples)))
