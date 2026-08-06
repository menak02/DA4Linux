"""Impulse response generation from 20-band frequency target curves.

Generates minimum-phase FIR impulse responses that can be loaded by
PipeWire's built-in convolver plugin.

Requires numpy for FIR generation. Without it, the convolver should
be configured to use /dirac (passthrough) as a fallback.
"""

import struct
from pathlib import Path

from .constants import DEFAULT_SAMPLE_RATE, DEFAULT_FIR_TAPS

try:
    import numpy as np

    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


def generate_minimum_phase_fir(
    target_gains_db: list[float],
    freqs: list[float],
    num_taps: int = DEFAULT_FIR_TAPS,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
):
    """Generate minimum-phase FIR from target frequency response.

    Uses the cepstral method:
    1. Interpolate target gains across linear frequency grid
    2. Convert dB to linear magnitude
    3. Compute minimum phase via Hilbert transform of log-magnitude
       (cepstral method: IFFT of log-magnitude -> fold cepstrum -> FFT back)
    4. IFFT to time domain
    5. Apply Blackman window

    Args:
        target_gains_db: Gain values in dB at each frequency point
        freqs: Frequency points in Hz (must match target_gains_db length)
        num_taps: Number of FIR taps (default 4096 at 48kHz ~85ms)
        sample_rate: Sample rate in Hz

    Returns:
        numpy array of FIR coefficients (float64)
    """
    if not _HAS_NUMPY:
        raise ImportError("numpy is required for FIR IR generation")

    target_gains_db = np.array(target_gains_db, dtype=np.float64)
    freqs = np.array(freqs, dtype=np.float64)

    # Build linear frequency grid up to Nyquist
    n_fft = num_taps * 2
    nyquist = sample_rate / 2
    fft_freqs = np.linspace(0, nyquist, n_fft // 2 + 1)

    # Interpolate target gains onto linear grid
    # Log-frequency interpolation is more natural for audio
    log_freqs = np.log2(np.maximum(freqs, 1.0))
    log_fft_freqs = np.log2(np.maximum(fft_freqs, 1.0))
    interp_gains_db = np.interp(
        log_fft_freqs, log_freqs, target_gains_db,
        left=target_gains_db[0], right=target_gains_db[-1],
    )

    # Convert dB to linear magnitude
    magnitude = 10.0 ** (interp_gains_db / 20.0)
    magnitude = np.maximum(magnitude, 1e-10)

    # Cepstral method for minimum phase
    log_mag = np.log(magnitude)

    # Full-spectrum cepstrum (symmetrical)
    log_mag_full = np.concatenate([log_mag, log_mag[-2:0:-1]])

    # IFFT to cepstrum domain
    cepstrum = np.fft.ifft(log_mag_full).real

    # Fold cepstrum: double non-negative quefrencies, zero negative
    # (except keep DC and Nyquist unchanged for even N)
    folded = np.zeros_like(cepstrum)
    folded[0] = cepstrum[0]
    mid = n_fft // 2
    folded[mid] = cepstrum[mid]
    quarter = mid // 2  # approximate
    folded[1:mid] = 2.0 * cepstrum[1:mid]

    # FFT back to frequency domain -> minimum-phase spectrum
    min_phase_spec = np.fft.fft(folded)

    # IFFT to time domain
    impulse = np.fft.ifft(min_phase_spec).real

    # Truncate to num_taps
    impulse = impulse[:num_taps]

    # Apply Blackman window
    window = np.blackman(num_taps)
    impulse *= window

    # Normalize so peak = 1.0 (linear gain)
    peak = np.max(np.abs(impulse))
    if peak > 0:
        impulse /= peak

    return impulse


def write_wav_ir(
    ir_array,
    filepath: str,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> None:
    """Write IR array as a WAV file using stdlib struct module.

    Handles mono or 2-channel (L, R tuple) impulses.
    """
    if _HAS_NUMPY and isinstance(ir_array, np.ndarray):
        if ir_array.ndim == 1:
            ir_array = (ir_array, ir_array)
    elif isinstance(ir_array, (list, tuple)):
        pass
    else:
        ir_array = (ir_array, ir_array)

    if isinstance(ir_array, (list, tuple)):
        left = ir_array[0]
        right = ir_array[1] if len(ir_array) > 1 else left
    else:
        left = right = ir_array

    if _HAS_NUMPY and isinstance(left, np.ndarray):
        left = left.tolist()
        right = right.tolist()

    num_channels = 1 if left == right else 2
    num_samples = len(left)
    bits_per_sample = 32
    byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
    block_align = num_channels * (bits_per_sample // 8)
    data_size = num_samples * block_align
    fmt = 3  # IEEE float

    p = Path(filepath)
    p.parent.mkdir(parents=True, exist_ok=True)

    with open(p, "wb") as f:
        # RIFF header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")

        # fmt subchunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))  # chunk size
        f.write(struct.pack("<H", fmt))
        f.write(struct.pack("<H", num_channels))
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", byte_rate))
        f.write(struct.pack("<H", block_align))
        f.write(struct.pack("<H", bits_per_sample))

        # data subchunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))

        if num_channels == 1:
            for s in left:
                f.write(struct.pack("<f", float(s)))
        else:
            for l, r in zip(left, right):
                f.write(struct.pack("<f", float(l)))
                f.write(struct.pack("<f", float(r)))
