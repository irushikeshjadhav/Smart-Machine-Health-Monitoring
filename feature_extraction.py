import numpy as np
import pandas as pd
from scipy.stats import kurtosis
from scipy.fft import rfft, rfftfreq

def compute_window_features(w, fs_actual):
    """Core feature computation from a 1D magnitude array sampled at fs_actual Hz."""
    rms = np.sqrt(np.mean(w**2))
    kurt = kurtosis(w)
    crest = np.max(np.abs(w)) / (rms + 1e-9)
    std = np.std(w)
    spec = np.abs(rfft(w - np.mean(w)))
    freqs = rfftfreq(len(w), d=1/fs_actual)
    peak_freq = freqs[np.argmax(spec)] if len(freqs) > 1 else 0.0
    return [rms, kurt, crest, std, peak_freq]

def extract_features(path, window_seconds=5.0, min_samples=40):
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')
    mag = np.sqrt(df['ax']**2 + df['ay']**2 + df['az']**2)

    feats = []
    for _, window in mag.resample(f'{window_seconds}s'):
        w = window.dropna().values
        if len(w) < min_samples:
            continue
        fs_actual = len(w) / window_seconds
        feats.append(compute_window_features(w, fs_actual))
    return np.array(feats)