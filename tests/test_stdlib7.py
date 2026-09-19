"""tensor + infer stdlib modules: NumPy-backed tensor primitives and the
AGK transformer inference engine.

Unlike the other LLM modules, these run against the real NumPy backend
(installed in this environment) and verify actual numerics: tensor op
correctness, tokenizer round-trips, greedy determinism, and — most
importantly — that the AGK engine with its per-head KV-cache produces
logits identical to an independent full-sequence NumPy reference on the
same weights.
"""

import math

import numpy as np
import pytest

from agk.pipeline import run_source


def run(src, **kw):
    return run_source(src, **kw)


# -- tensor primitives -------------------------------------------------

def test_matmul():
    out, _, warnings = run("""
import tensor
define function main:
    create a as Object
    set a to tensor_from_list([[1.0, 2.0], [3.0, 4.0]])
    create b as Object
    set b to tensor_from_list([[5.0, 6.0], [7.0, 8.0]])
    print(tensor_to_list(tensor_matmul(a, b)))
""")
    assert warnings == []
    assert out.strip() == "[[19.0, 22.0], [43.0, 50.0]]"


def test_elementwise_ops():
    out, _, warnings = run("""
import tensor
define function main:
    create a as Object
    set a to tensor_from_list([1.0, 2.0, 3.0])
    create b as Object
    set b to tensor_from_list([4.0, 5.0, 6.0])
    print(tensor_to_list(tensor_add(a, b)))
    print(tensor_to_list(tensor_sub(b, a)))
    print(tensor_to_list(tensor_mul(a, b)))
    print(tensor_to_list(tensor_div(b, a)))
    print(tensor_to_list(tensor_neg(a)))
""")
    assert warnings == []
    lines = out.strip().splitlines()
    assert lines[0] == "[5.0, 7.0, 9.0]"
    assert lines[1] == "[3.0, 3.0, 3.0]"
    assert lines[2] == "[4.0, 10.0, 18.0]"
    assert lines[3] == "[4.0, 2.5, 2.0]"
    assert lines[4] == "[-1.0, -2.0, -3.0]"


def test_shape_reshape_transpose():
    out, _, warnings = run("""
import tensor
define function main:
    create a as Object
    set a to tensor_from_list([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    print(tensor_shape(a))
    print(tensor_numel(a))
    create r as Object
    set r to tensor_reshape(a, [3, 2])
    print(tensor_shape(r))
    print(tensor_to_list(tensor_transpose(a)))
""")
    assert warnings == []
    lines = out.strip().splitlines()
    assert lines[0] == "[2, 3]"
    assert lines[1] == "6"
    assert lines[2] == "[3, 2]"
    assert lines[3] == "[[1.0, 4.0], [2.0, 5.0], [3.0, 6.0]]"


def test_softmax_sums_to_one():
    out, _, warnings = run("""
import tensor
define function main:
    create p as Object
    set p to tensor_softmax_1d(tensor_from_list([1.0, 2.0, 3.0]))
    print(tensor_sum(p))
    print(tensor_to_list(p)[2] > 0.6)
""")
    assert warnings == []
    lines = out.strip().splitlines()
    assert abs(float(lines[0]) - 1.0) < 1e-6
    assert lines[1] == "True"


def test_rmsnorm_matches_formula():
    out, _, warnings = run("""
import tensor
define function main:
    create x as Object
    set x to tensor_from_list([2.0, -1.0, 0.5])
    create n as Object
    set n to tensor_rmsnorm(x, tensor_from_list([1.0, 1.0, 1.0]), 0.00001)
    print(tensor_to_list(n))
""")
    assert warnings == []
    xs = [2.0, -1.0, 0.5]
    rms = math.sqrt(sum(v * v for v in xs) / 3 + 1e-5)
    got = eval(out.strip())
    for g, e in zip(got, [v / rms for v in xs]):
        assert abs(g - e) < 1e-6


def test_silu_sigmoid_exp_sqrt():
    out, _, warnings = run("""
import tensor
define function main:
    create z as Object
    set z to tensor_from_list([0.0])
    print(tensor_to_list(tensor_sigmoid(z))[0])
    print(tensor_to_list(tensor_silu(tensor_from_list([1.0])))[0])
    print(tensor_to_list(tensor_exp(z))[0])
    print(tensor_to_list(tensor_sqrt(tensor_from_list([4.0])))[0])
""")
    assert warnings == []
    lines = out.strip().splitlines()
    assert abs(float(lines[0]) - 0.5) < 1e-7
    assert abs(float(lines[1]) - 1.0 / (1.0 + math.exp(-1.0))) < 1e-6
    assert abs(float(lines[2]) - 1.0) < 1e-7
    assert abs(float(lines[3]) - 2.0) < 1e-7


def test_take_stack_argmax():
    out, _, warnings = run("""
import tensor
define function main:
    create m as Object
    set m to tensor_from_list([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    print(tensor_to_list(tensor_take1(m, 1, 0)))
    print(tensor_to_list(tensor_take(m, [0, 2], 0)))
    create s as Object
    set s to tensor_stack([tensor_from_list([1.0]), tensor_from_list([2.0])])
    print(tensor_shape(s))
    print(tensor_argmax(tensor_from_list([0.2, 0.9, 0.4])))
    print(tensor_max(tensor_from_list([0.2, 0.9, 0.4])))
""")
    assert warnings == []
    lines = out.strip().splitlines()
    assert lines[0] == "[3.0, 4.0]"
    assert lines[1] == "[[1.0, 2.0], [5.0, 6.0]]"
    assert lines[2] == "[2, 1]"
    assert lines[3] == "1"
    assert abs(float(lines[4]) - 0.9) < 1e-7


def test_randn_is_reproducible():
    out, _, warnings = run("""
import tensor
define function main:
    create a as Object
    set a to tensor_randn([2, 3], 42)
    create b as Object
    set b to tensor_randn([2, 3], 42)
    create c as Object
    set c to tensor_randn([2, 3], 43)
    print(tensor_max_abs_diff(a, b))
    print(tensor_max_abs_diff(a, c) > 0.0)
    print(tensor_shape(tensor_zeros([2, 2])))
    print(tensor_sum(tensor_ones([2, 2])))
""")
    assert warnings == []
    lines = out.strip().splitlines()
    assert float(lines[0]) == 0.0
    assert lines[1] == "True"
    assert lines[2] == "[2, 2]"
    assert float(lines[3]) == 4.0


def test_random_choice_valid_index():
    out, _, warnings = run("""
import tensor
define function main:
    tensor_seed(11)
    create i as Integer
    set i to tensor_random_choice(4, [0.1, 0.2, 0.3, 0.4])
    print(i >= 0 and i < 4)
""")
    assert warnings == []
    assert out.strip() == "True"


def test_load_npz_missing_file_errors():
    with pytest.raises(Exception) as ei:
        run("""
import tensor
define function main:
    tensor_load_npz("no_such_weights_xyz.npz")
""")
    assert "no_such_weights_xyz.npz" in str(ei.value)


# -- infer: tokenizer + engine ------------------------------------------

def test_tokenizer_roundtrip():
    out, _, warnings = run("""
import infer
define function main:
    create model as List
    set model to infer_random_model([1, 2, 8, 4, 16, 16, 10], 7)
    create text as String
    set text to "bead"
    print(infer_decode(model, infer_encode(model, text)) == text)
    print(infer_encode(model, "cab"))
""")
    assert warnings == []
    lines = out.strip().splitlines()
    assert lines[0] == "True"
    # alphabet is a-z then digits...: c=2, a=0, b=1
    assert lines[1] == "[2, 0, 1]"


def test_tokenizer_unknown_char_errors():
    with pytest.raises(Exception) as ei:
        run("""
import infer
define function main:
    create model as List
    set model to infer_random_model([1, 2, 8, 4, 16, 16, 10], 7)
    infer_encode(model, "ABC")
""")
    assert "not in vocabulary" in str(ei.value)


def test_forward_logits_shape_and_greedy_determinism():
    out, _, warnings = run("""
import infer
define function main:
    create model as List
    set model to infer_random_model([2, 2, 16, 8, 32, 32, 12], 9)
    create logits as Object
    set logits to infer_forward_logits(model, [3, 1, 4, 1, 5])
    print(tensor_shape(logits))
    create g1 as String
    set g1 to infer_generate(model, "ab", 8, 0.0)
    create g2 as String
    set g2 to infer_generate(model, "ab", 8, 0.0)
    print(g1 == g2)
    print(len(g1) == 8)
""")
    assert warnings == []
    lines = out.strip().splitlines()
    assert lines[0] == "[12]"
    assert lines[1] == "True"
    assert lines[2] == "True"


def test_sample_temperature_returns_valid_id():
    out, _, warnings = run("""
import infer
define function main:
    create model as List
    set model to infer_random_model([1, 2, 8, 4, 16, 16, 10], 3)
    tensor_seed(5)
    create logits as Object
    set logits to infer_forward_logits(model, [1, 2, 3])
    create i as Integer
    set i to infer_sample(logits, 1.0)
    print(i >= 0 and i < 10)
    create g as Integer
    set g to infer_sample(logits, 0.0)
    print(g == tensor_argmax(logits))
""")
    assert warnings == []
    lines = out.strip().splitlines()
    assert lines[0] == "True"
    assert lines[1] == "True"


def test_cache_grows_with_positions():
    out, _, warnings = run("""
import infer
define function main:
    create model as List
    set model to infer_random_model([2, 3, 12, 4, 24, 16, 10], 4)
    create caches as List
    set caches to infer_new_caches(model)
    infer_step(model, caches, 2, 0)
    infer_step(model, caches, 5, 1)
    print(len(caches))
    print(len(caches[0][0]))
    print(len(caches[0][0][0]))
""")
    assert warnings == []
    lines = out.strip().splitlines()
    assert lines[0] == "2"   # two layers
    assert lines[1] == "3"   # three heads
    assert lines[2] == "2"   # two cached positions per head


# -- the big one: cached AGK engine vs uncached NumPy reference ---------

def _reference_forward(w, ids):
    eps = 1e-5
    n_layer, n_head, n_embd, hd = (int(x) for x in w["config"][:4])
    cos_t, sin_t = w["rope_cos"], w["rope_sin"]
    T = len(ids)

    def rope(x):
        x1, x2 = x[..., 0::2], x[..., 1::2]
        c, s = cos_t[:T, None, :], sin_t[:T, None, :]
        o = np.empty_like(x)
        o[..., 0::2] = x1 * c - x2 * s
        o[..., 1::2] = x1 * s + x2 * c
        return o

    def rmsnorm(x, wt):
        return x / np.sqrt((x.astype(np.float64) ** 2).mean(-1, keepdims=True) + eps) * wt

    x = w["tok_emb"][np.array(ids)]
    for l in range(n_layer):
        p = f"layers.{l}."
        h = rmsnorm(x, w[p + "rms1"])
        q = rope((h @ w[p + "wq"]).reshape(T, n_head, hd)).transpose(1, 0, 2)
        k = rope((h @ w[p + "wk"]).reshape(T, n_head, hd)).transpose(1, 0, 2)
        v = (h @ w[p + "wv"]).reshape(T, n_head, hd).transpose(1, 0, 2)
        s = q @ k.transpose(0, 2, 1) / math.sqrt(hd)
        s = np.where(np.tril(np.ones((T, T), bool)), s, -1e9)
        s = np.exp(s - s.max(-1, keepdims=True))
        s = s / s.sum(-1, keepdims=True)
        x = x + (s @ v).transpose(1, 0, 2).reshape(T, n_embd) @ w[p + "wo"]
        h2 = rmsnorm(x, w[p + "rms2"])
        m = (h2 @ w[p + "wgate"] / (1 + np.exp(-(h2 @ w[p + "wgate"])))) * (h2 @ w[p + "wup"])
        x = x + m @ w[p + "wdown"]
    return (rmsnorm(x, w["rms_final"]) @ w["lm_head"])[-1]


def _make_equiv_weights(path):
    rng = np.random.default_rng(1234)
    n_layer, n_head, n_embd, hd, ffn, block, vocab = 2, 3, 12, 4, 24, 24, 11
    half = hd // 2
    i = np.arange(half)
    freqs = 1.0 / (10000.0 ** (2.0 * i / hd))
    ang = np.arange(block)[:, None] * freqs[None, :]
    w = {
        "config": np.array([n_layer, n_head, n_embd, hd, ffn, block, vocab]),
        "tok_emb": rng.standard_normal((vocab, n_embd)).astype(np.float32),
        "rms_final": rng.standard_normal(n_embd).astype(np.float32),
        "lm_head": rng.standard_normal((n_embd, vocab)).astype(np.float32),
        "rope_cos": np.cos(ang).astype(np.float32),
        "rope_sin": np.sin(ang).astype(np.float32),
        "itos": np.array(list("abcdefghijk")),
    }
    for l in range(n_layer):
        p = f"layers.{l}."
        w[p + "rms1"] = rng.standard_normal(n_embd).astype(np.float32)
        w[p + "rms2"] = rng.standard_normal(n_embd).astype(np.float32)
        for n in ("wq", "wk", "wv", "wo"):
            w[p + n] = rng.standard_normal((n_embd, n_embd)).astype(np.float32)
        w[p + "wgate"] = rng.standard_normal((n_embd, ffn)).astype(np.float32)
        w[p + "wup"] = rng.standard_normal((n_embd, ffn)).astype(np.float32)
        w[p + "wdown"] = rng.standard_normal((ffn, n_embd)).astype(np.float32)
    np.savez(path, **w)
    return w


def test_cached_engine_matches_uncached_reference(tmp_path):
    """AGK infer_forward_logits (incremental, per-head KV-cache) must equal
    an independent full-sequence NumPy forward pass on identical weights."""
    path = str(tmp_path / "equiv.npz")
    w = _make_equiv_weights(path)
    ids = [3, 1, 4, 1, 5, 9, 2]
    expected = _reference_forward(w, ids)

    out, _, warnings = run(f"""
import infer
define function main:
    create model as List
    set model to infer_load_model("{path}")
    create logits as Object
    set logits to infer_forward_logits(model, [3, 1, 4, 1, 5, 9, 2])
    print(tensor_to_list(logits))
""")
    assert warnings == []
    got = np.array(eval(out.strip()), dtype=np.float64)
    assert got.shape == expected.shape
    assert np.max(np.abs(got - expected)) < 1e-4


def test_generate_matches_reference_argmax(tmp_path):
    """Greedy generation from AGK must pick the same token the reference
    forward pass ranks first."""
    path = str(tmp_path / "equiv2.npz")
    w = _make_equiv_weights(path)
    ids = [3, 1, 4]
    expected_id = int(np.argmax(_reference_forward(w, ids)))

    out, _, warnings = run(f"""
import infer
define function main:
    create model as List
    set model to infer_load_model("{path}")
    print(infer_generate(model, "dbe", 1, 0.0))
""")
    assert warnings == []
    itos = list("abcdefghijk")
    assert out.strip() == itos[expected_id]
