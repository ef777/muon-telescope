"""Small CNN cluster classifier (dot / worm / track) on 32x32 crops. Needs torch (optional dependency).

Training labels:
  * synthetic data: truth labels from sim/synth.py (rendered crops);
  * real data: positives = clusters confirmed by triple coincidence, negatives = clusters outside any coincidence
    (contaminated by single muons, but background dominates). Use only once hundreds of labels exist (CLAUDE.md Phase 5).
"""
from __future__ import annotations

import numpy as np

CLASSES = ["dot", "worm", "track"]
SIZE = 32


def render_crop(length: float, width: float, angle: float, amp: float = 150.0, noise: float = 3.0,
                rng: np.random.Generator | None = None, curl: float = 0.0, size: int = SIZE) -> np.ndarray:
    """Render a cluster (rod with Gaussian profile; curl>0 bends it like a beta 'worm') on Gaussian noise."""
    rng = rng or np.random.default_rng()
    yy, xx = np.mgrid[0:size, 0:size] - (size - 1) / 2.0
    img = rng.normal(64.0, noise, (size, size))
    half = max(length, 1.0) / 2.0
    for t in np.linspace(-half, half, max(int(length * 2), 2)):
        a = angle + curl * t / max(half, 1.0)
        cx, cy = t * np.cos(a), t * np.sin(a)
        img += amp * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * (width / 2.355 + 0.3) ** 2)) / max(length, 1.0) * 2
    return img


def normalise(crop: np.ndarray) -> np.ndarray:
    c = crop.astype(np.float32)
    c = c - np.median(c)
    return c / (c.max() + 1e-3)


def center32(crop64: np.ndarray) -> np.ndarray:
    """Real 64x64 crops -> central 32x32."""
    o = (crop64.shape[0] - SIZE) // 2
    return crop64[o:o + SIZE, o:o + SIZE]


def synthetic_dataset(n_per_class: int = 600, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    X, y = [], []
    for _ in range(n_per_class):
        X.append(render_crop(rng.uniform(0.5, 1.8), rng.uniform(0.8, 1.6), rng.uniform(0, np.pi), rng.normal(500, 150), rng=rng)); y.append(0)
        X.append(render_crop(rng.uniform(4, 14), rng.uniform(2.5, 5), rng.uniform(0, np.pi), rng.normal(250, 60), rng=rng,
                             curl=rng.uniform(-1.5, 1.5)))
        y.append(1)
        X.append(render_crop(rng.uniform(3, 20), rng.uniform(1.0, 2.0), rng.uniform(0, np.pi), rng.normal(380, 40), rng=rng)); y.append(2)
    X = np.stack([normalise(c) for c in X])[:, None]
    return X.astype(np.float32), np.array(y)


def _net():
    import torch.nn as nn
    return nn.Sequential(
        nn.Conv2d(1, 8, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(8, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Flatten(), nn.Linear(16 * 8 * 8, 32), nn.ReLU(), nn.Linear(32, len(CLASSES)))


def train(X: np.ndarray, y: np.ndarray, epochs: int = 12, lr: float = 3e-3, seed: int = 0):
    import torch
    torch.manual_seed(seed)
    net = _net()
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    Xt, yt = torch.from_numpy(X), torch.from_numpy(y).long()
    for _ in range(epochs):
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), 64):
            idx = perm[i:i + 64]
            opt.zero_grad()
            torch.nn.functional.cross_entropy(net(Xt[idx]), yt[idx]).backward()
            opt.step()
    return net


def predict(net, X: np.ndarray) -> np.ndarray:
    import torch
    with torch.no_grad():
        return net(torch.from_numpy(X)).argmax(1).numpy()


def confusion(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    m = np.zeros((3, 3), int)
    for a, b in zip(y, p):
        m[a, b] += 1
    return m
