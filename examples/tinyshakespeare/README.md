# Tiny Shakespeare inference in AGK

A complete, honest example of neural network inference orchestrated by AGK:
a 3-layer Llama-style transformer (RMSNorm, RoPE, SwiGLU MLP, ~345K params)
trained on Shakespeare, then run token-by-token from an AGK program.

## Quick start

```shell
pip install torch numpy        # training + inference backends
python train.py --steps 2500   # ~10 min on CPU, writes weights.npz
cd examples/tinyshakespeare
agk run demo.agk               # talk to the model
```

## How it works

- `train.py` trains a character-level transformer in PyTorch and exports
  `weights.npz` in the exact layout the AGK `infer` module expects.
  Every matrix is stored `(in_features, out_features)` and the forward
  pass is `x @ w`, so no transposes are needed on the AGK side.
- `demo.agk` is a plain AGK program: it loads the weights with
  `infer_load_model` and generates text with `infer_generate`.
- The engine itself lives in the stdlib: `agk/stdlib/infer.agk`
  (transformer, per-head KV-cache, sampling, tokenizer) on top of
  `agk/stdlib/tensor.agk` (NumPy-backed tensor primitives).

AGK owns the orchestration — tokenization, the forward pass, cache
management, sampling — while NumPy does the arithmetic. Pure-AGK tensor
math would be orders of magnitude too slow; the hybrid is the honest
design, and the cached engine is verified bit-close against an
independent full-sequence NumPy reference (`tests/test_stdlib7.py`).

## Files

- `train.py` — training + export (needs `torch`, `numpy`)
- `demo.agk` — interactive AGK demo (needs `weights.npz`, `numpy`)
- `input.txt` — tiny-shakespeare corpus (downloaded on first run)
- `weights.npz` — trained weights (created by `train.py`)
- `training_log.txt` — loss curve + samples (created by `train.py`)
