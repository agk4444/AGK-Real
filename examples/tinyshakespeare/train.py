#!/usr/bin/env python3
"""Train the tiny Shakespeare transformer that `demo.agk` runs.

Llama-style decoder (RMSNorm, interleaved RoPE, SwiGLU), char-level.
Weight layout mirrors the AGK `infer` module exactly: every matrix is
(in_features, out_features) and the forward pass is x @ w, so the
exported .npz loads straight into infer_load_model with no transpose.

Usage: python train.py [--steps 2500]
Produces: weights.npz, training_log.txt
Requires: pip install torch numpy
"""
import argparse
import math
import os
import sys
import urllib.request

import numpy as np
import torch
import torch.nn as nn

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS_URL = "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt"

# Model config (also written into weights.npz -> "config").
N_LAYER, N_HEAD, N_EMBD, FFN = 3, 3, 96, 256
HEAD_DIM = N_EMBD // N_HEAD
BLOCK = 96
EPS = 1e-5


def get_corpus():
    path = os.path.join(HERE, "input.txt")
    if not os.path.exists(path):
        print("downloading tiny-shakespeare...", flush=True)
        urllib.request.urlretrieve(CORPUS_URL, path)
    with open(path) as f:
        return f.read()


def rope_tables(block, head_dim):
    half = head_dim // 2
    i = torch.arange(half).float()
    freqs = 1.0 / (10000.0 ** (2.0 * i / head_dim))
    m = torch.arange(block).float().unsqueeze(1)
    ang = m * freqs.unsqueeze(0)
    return torch.cos(ang), torch.sin(ang)


def apply_rope(x, cos, sin):
    # x: (B, T, H, head_dim), interleaved pairs; cos/sin: (T, half)
    cos = cos.unsqueeze(0).unsqueeze(2)
    sin = sin.unsqueeze(0).unsqueeze(2)
    x1 = x[..., 0::2]
    x2 = x[..., 1::2]
    o1 = x1 * cos - x2 * sin
    o2 = x1 * sin + x2 * cos
    out = torch.empty_like(x)
    out[..., 0::2] = o1
    out[..., 1::2] = o2
    return out


class RMSNorm(nn.Module):
    def __init__(self, d):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(d))

    def forward(self, x):
        return x / torch.sqrt(x.pow(2).mean(-1, keepdim=True) + EPS) * self.weight


class Block(nn.Module):
    def __init__(self):
        super().__init__()
        self.rms1 = RMSNorm(N_EMBD)
        self.wq = nn.Parameter(torch.randn(N_EMBD, N_EMBD) * 0.02)
        self.wk = nn.Parameter(torch.randn(N_EMBD, N_EMBD) * 0.02)
        self.wv = nn.Parameter(torch.randn(N_EMBD, N_EMBD) * 0.02)
        self.wo = nn.Parameter(torch.randn(N_EMBD, N_EMBD) * 0.02)
        self.rms2 = RMSNorm(N_EMBD)
        self.wgate = nn.Parameter(torch.randn(N_EMBD, FFN) * 0.02)
        self.wup = nn.Parameter(torch.randn(N_EMBD, FFN) * 0.02)
        self.wdown = nn.Parameter(torch.randn(FFN, N_EMBD) * 0.02)

    def forward(self, x, cos, sin):
        B, T, C = x.shape
        h = self.rms1(x)
        q = (h @ self.wq).view(B, T, N_HEAD, HEAD_DIM)
        k = (h @ self.wk).view(B, T, N_HEAD, HEAD_DIM)
        v = (h @ self.wv).view(B, T, N_HEAD, HEAD_DIM)
        q = apply_rope(q, cos[:T], sin[:T]).transpose(1, 2)
        k = apply_rope(k, cos[:T], sin[:T]).transpose(1, 2)
        v = v.transpose(1, 2)
        att = (q @ k.transpose(-2, -1)) / math.sqrt(HEAD_DIM)
        att = att.masked_fill(~torch.tril(torch.ones(T, T, dtype=torch.bool)), float("-inf"))
        att = torch.softmax(att, dim=-1)
        o = (att @ v).transpose(1, 2).reshape(B, T, C)
        x = x + o @ self.wo
        h2 = self.rms2(x)
        m = torch.nn.functional.silu(h2 @ self.wgate) * (h2 @ self.wup)
        return x + m @ self.wdown


class TinyGPT(nn.Module):
    def __init__(self, vocab):
        super().__init__()
        self.tok_emb = nn.Parameter(torch.randn(vocab, N_EMBD) * 0.02)
        self.blocks = nn.ModuleList(Block() for _ in range(N_LAYER))
        self.rms_final = RMSNorm(N_EMBD)
        self.lm_head = nn.Parameter(torch.randn(N_EMBD, vocab) * 0.02)
        self.register_buffer("rope_cos", torch.zeros(1))
        self.register_buffer("rope_sin", torch.zeros(1))

    def forward(self, idx):
        cos, sin = self.rope_cos, self.rope_sin
        x = self.tok_emb[idx]
        for b in self.blocks:
            x = b(x, cos, sin)
        return self.rms_final(x) @ self.lm_head


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=2500)
    ap.add_argument("--batch", type=int, default=24)
    ap.add_argument("--lr", type=float, default=5e-4)
    args = ap.parse_args()

    torch.manual_seed(7)
    text = get_corpus()
    chars = sorted(set(text))
    vocab = len(chars)
    stoi = {c: i for i, c in enumerate(chars)}
    itos = chars
    print(f"corpus chars: {len(text)}, vocab: {vocab}", flush=True)
    data = torch.tensor([stoi[c] for c in text], dtype=torch.long)

    cos, sin = rope_tables(BLOCK, HEAD_DIM)
    model = TinyGPT(vocab)
    model.rope_cos = cos
    model.rope_sin = sin
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, betas=(0.9, 0.95), weight_decay=0.01)

    def batch():
        i = torch.randint(0, len(data) - BLOCK - 1, (args.batch,))
        x = torch.stack([data[j:j + BLOCK] for j in i])
        y = torch.stack([data[j + 1:j + BLOCK + 1] for j in i])
        return x, y

    log = open(os.path.join(HERE, "training_log.txt"), "w")
    for step in range(1, args.steps + 1):
        frac = step / args.steps
        lr = args.lr * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * frac)))
        for g in opt.param_groups:
            g["lr"] = lr
        xb, yb = batch()
        logits = model(xb)
        loss = torch.nn.functional.cross_entropy(logits.view(-1, vocab), yb.view(-1))
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if step % 250 == 0 or step == 1:
            msg = f"step {step}/{args.steps} loss {loss.item():.4f} lr {lr:.2e}"
            print(msg, flush=True)
            log.write(msg + "\n")
            log.flush()
        if step % 1000 == 0:
            sample = greedy_sample(model, stoi, itos, "The ", 120)
            print("--- sample ---")
            print(sample)
            print("--------------", flush=True)
            log.write("--- sample ---\n" + sample + "\n--------------\n")
            log.flush()
    log.close()

    # Export for the AGK infer module: (in, out) matrices, float32.
    w = {"config": np.array([N_LAYER, N_HEAD, N_EMBD, HEAD_DIM, FFN, BLOCK, vocab])}
    sd = model.state_dict()
    w["tok_emb"] = model.tok_emb.detach().numpy().astype(np.float32)
    w["rms_final"] = model.rms_final.weight.detach().numpy().astype(np.float32)
    w["lm_head"] = model.lm_head.detach().numpy().astype(np.float32)
    w["rope_cos"] = cos.numpy().astype(np.float32)
    w["rope_sin"] = sin.numpy().astype(np.float32)
    w["itos"] = np.array(itos, dtype="<U1")
    for l, b in enumerate(model.blocks):
        p = f"layers.{l}."
        w[p + "rms1"] = b.rms1.weight.detach().numpy().astype(np.float32)
        for n in ("wq", "wk", "wv", "wo", "wgate", "wup", "wdown"):
            w[p + n] = getattr(b, n).detach().numpy().astype(np.float32)
        w[p + "rms2"] = b.rms2.weight.detach().numpy().astype(np.float32)
    np.savez(os.path.join(HERE, "weights.npz"), **w)
    n_params = sum(v.size for v in w.values() if isinstance(v, np.ndarray) and v.dtype != np.dtype("<U1"))
    print(f"saved weights.npz ({n_params} params)")


@torch.no_grad()
def greedy_sample(model, stoi, itos, prompt, n):
    ids = [stoi[c] for c in prompt]
    for _ in range(n):
        x = torch.tensor([ids[-BLOCK:]])
        logits = model(x)[0, -1]
        ids.append(int(torch.argmax(logits)))
    return "".join(itos[i] for i in ids)


if __name__ == "__main__":
    main()
