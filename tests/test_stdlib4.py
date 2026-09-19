"""LLM stdlib modules (transformers, tokenizer, torchutils, datasets,
embeddings, finetune).

The real Python packages (torch, transformers, ...) are not installed in
this environment, so tests inject lightweight fakes into sys.modules and
verify the AGK wrappers call the underlying APIs correctly. Separate tests
verify the clean "pip install ..." error when a backend is missing.
"""

import sys
import types

import pytest

from agk.pipeline import run_source


def run(src, **kw):
    return run_source(src, **kw)


class FakeVec(list):
    """A list that supports tensor-style division (for the generate loop)."""

    def __truediv__(self, other):
        return FakeVec([v / other for v in self])


class FakeT:
    """Minimal tensor stand-in wrapping nested Python lists."""

    def __init__(self, data):
        self.data = data

    @property
    def shape(self):
        d = self.data
        out = []
        while isinstance(d, list):
            out.append(len(d))
            d = d[0] if d else None
        return tuple(out)

    def tolist(self):
        return self.data

    def _elem(self, other, op):
        o = other.data if isinstance(other, FakeT) else other
        if isinstance(self.data[0], list):
            return FakeT([[op(a, b) for a, b in zip(r1, r2)]
                          for r1, r2 in zip(self.data, o)])
        return FakeT([op(a, b) for a, b in zip(self.data, o)])

    def __add__(self, other):
        return self._elem(other, lambda a, b: a + b)

    def __sub__(self, other):
        return self._elem(other, lambda a, b: a - b)

    def __mul__(self, other):
        return self._elem(other, lambda a, b: a * b)

    def __getitem__(self, i):
        v = self.data[i]
        return FakeT(v) if isinstance(v, list) else v


def _matmul(a, b):
    ad = a.data if isinstance(a, FakeT) else a
    bd = b.data if isinstance(b, FakeT) else b
    n = len(bd[0])
    return FakeT([[sum(x * y for x, y in zip(row, col))
                   for col in zip(*bd)] for row in ad])


@pytest.fixture
def fake_llm(monkeypatch):
    """Inject fake torch/transformers/datasets/sentence_transformers/peft/tiktoken/huggingface_hub."""
    state = {"argmax": None, "multinomial": 6, "seed": None,
             "saved": {}, "trained": False, "save_model_dir": None,
             "lora_cfg": None, "trainer_dc": "unset", "merged_dir": None}

    torch = types.ModuleType("torch")
    torch.__version__ = "2.9.0-fake"
    torch.cuda = types.SimpleNamespace(is_available=lambda: True)
    torch.manual_seed = lambda s: state.update(seed=s)
    torch.tensor = lambda data: FakeT(data)
    torch.zeros = lambda shape: FakeT(_nested(shape, 0.0))
    torch.ones = lambda shape: FakeT(_nested(shape, 1.0))
    torch.rand = lambda shape: FakeT(_nested(shape, 0.5))
    torch.matmul = _matmul
    torch.softmax = lambda x, dim: x
    torch.multinomial = lambda x, n: [state["multinomial"]] * n
    torch.save = lambda obj, path: state["saved"].__setitem__(path, obj)
    torch.load = lambda path: state["saved"][path]

    def _argmax(x):
        if state["argmax"] is not None:
            return state["argmax"]
        d = x.data if isinstance(x, FakeT) else x
        return max(range(len(d)), key=lambda i: d[i])

    def _reduce(x, fn):
        d = x.data if isinstance(x, FakeT) else x
        flat = []

        def walk(v):
            if isinstance(v, list):
                for e in v:
                    walk(e)
            else:
                flat.append(v)
        walk(d)
        return float(fn(flat))

    torch.argmax = _argmax
    torch.sum = lambda x: _reduce(x, sum)
    torch.mean = lambda x, dim=None: _mean(x, dim)
    torch.norm = lambda x: _reduce(x, lambda f: sum(v * v for v in f) ** 0.5)
    monkeypatch.setitem(sys.modules, "torch", torch)

    def _nested(shape, val):
        if not shape:
            return val
        return [_nested(shape[1:], val) for _ in range(shape[0])]

    def _mean(x, dim):
        d = x.data if isinstance(x, FakeT) else x
        if dim == 0 and isinstance(d[0], list):
            cols = list(zip(*d))
            m = [sum(c) / len(c) for c in cols]
            return types.SimpleNamespace(tolist=lambda: m)
        flat = []
        for v in d:
            flat.append(v)
        return sum(flat) / len(flat)

    transformers = types.ModuleType("transformers")

    class FakeTok:
        eos_token_id = 999

        def encode(self, text):
            return [7] * len(text.split())

        def decode(self, ids):
            return "d:%d" % len(ids)

        def save_pretrained(self, d):
            state["tok_dir"] = d

    transformers.AutoTokenizer = types.SimpleNamespace(
        from_pretrained=lambda model: FakeTok())

    class FakeLogits:
        def __getitem__(self, i):
            assert i == 0
            return [FakeVec([0.1, 0.9, 0.3]) for _ in range(20)]

    class FakeModel:
        def eval(self):
            pass

        def __call__(self, inp):
            return types.SimpleNamespace(logits=FakeLogits())

    transformers.AutoModelForCausalLM = types.SimpleNamespace(
        from_pretrained=lambda model: FakeModel())
    transformers.pipeline = lambda task, model: _fake_pipeline(task, model, state)
    transformers.TrainingArguments = lambda out: types.SimpleNamespace(
        output_dir=out)

    class FakeTrainer:
        def __init__(self, model, args, dc, ds):
            state["trainer_dc"] = dc
            self.ds = ds

        def train(self):
            state["trained"] = True

        def save_model(self, d):
            state["save_model_dir"] = d

    transformers.Trainer = FakeTrainer
    monkeypatch.setitem(sys.modules, "transformers", transformers)

    def _fake_pipeline(task, model, state):
        if task == "text-generation":
            return lambda prompt: [{"generated_text": "gen:" + prompt}]
        if task == "sentiment-analysis":
            return lambda text: [{"label": "POSITIVE", "score": 0.97}]
        if task == "summarization":
            return lambda text: [{"summary_text": "sum:" + text[:5]}]
        if task == "translation":
            return lambda text: [{"translation_text": "tra:" + text}]
        if task == "fill-mask":
            return lambda text: [{"token_str": "paris"}]
        if task == "question-answering":
            return lambda q, c: {"answer": "ans:" + q}
        if task == "zero-shot-classification":
            return lambda text, labels: {"labels": list(labels),
                                         "scores": [0.9] * len(labels)}
        if task == "feature-extraction":
            return lambda text: [[[1.0, 2.0], [3.0, 4.0]]]
        raise AssertionError("unexpected pipeline task " + task)

    datasets = types.ModuleType("datasets")

    class FakeDS:
        def __init__(self, rows):
            self.rows = rows

        def __len__(self):
            return len(self.rows)

        def __getitem__(self, i):
            if isinstance(i, str):
                return [r[i] for r in self.rows]
            return dict(self.rows[i])

        def select(self, indices):
            return FakeDS([self.rows[i] for i in indices])

        def shuffle(self, seed):
            return FakeDS(list(reversed(self.rows)))

        @property
        def column_names(self):
            return list(self.rows[0].keys())

        def to_list(self):
            return [dict(r) for r in self.rows]

        def save_to_disk(self, path):
            state["ds_saved"] = path

    datasets.load_dataset = lambda name, *a: FakeDS(
        [{"x": 1}, {"x": 2}, {"x": 3}])
    datasets.Dataset = types.SimpleNamespace(
        from_list=lambda records: FakeDS(records))
    datasets.load_from_disk = lambda path: FakeDS([{"x": 9}])
    monkeypatch.setitem(sys.modules, "datasets", datasets)

    st = types.ModuleType("sentence_transformers")

    class FakeArr:
        def __init__(self, vecs):
            self.vecs = vecs

        def tolist(self):
            return self.vecs

    class FakeST:
        def __init__(self, model):
            pass

        def encode(self, texts):
            table = {"q": [1.0, 0.0], "a": [1.0, 0.0],
                     "b": [0.0, 1.0], "c": [0.7, 0.7]}
            return FakeArr([table.get(t, [0.5, 0.5]) for t in texts])

    st.SentenceTransformer = FakeST
    monkeypatch.setitem(sys.modules, "sentence_transformers", st)

    peft = types.ModuleType("peft")
    peft.LoraConfig = lambda r, tm, alpha: state.update(
        lora_cfg=(r, list(tm), alpha)) or types.SimpleNamespace(
            r=r, target_modules=tm, lora_alpha=alpha)

    class FakePeftModel:
        def eval(self):
            pass

        def __call__(self, inp):
            return types.SimpleNamespace(logits=FakeLogits())

        def merge_and_unload(self):
            return types.SimpleNamespace(
                save_pretrained=lambda d: state.update(merged_dir=d))

    peft.get_peft_model = lambda m, cfg: FakePeftModel()
    peft.PeftModel = types.SimpleNamespace(
        from_pretrained=lambda m, d: FakePeftModel())
    monkeypatch.setitem(sys.modules, "peft", peft)

    tiktoken = types.ModuleType("tiktoken")

    class FakeEnc:
        def encode(self, text):
            return [100 + i for i in range(len(text.split()))]

        def decode(self, ids):
            return "tt:%d" % len(ids)

    tiktoken.get_encoding = lambda name: FakeEnc()
    monkeypatch.setitem(sys.modules, "tiktoken", tiktoken)

    hub = types.ModuleType("huggingface_hub")
    hub.snapshot_download = lambda model: "/cache/" + model
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)

    return state


# ---------------- transformers ----------------

def test_transformers_missing():
    with pytest.raises(Exception, match="pip install transformers"):
        run("import transformers\ndefine function main:\n"
            "    print(tf_encode(\"m\", \"hi\"))\n")


def test_tf_generate_greedy(fake_llm):
    src = ("import transformers\ndefine function main:\n"
           "    print(tf_generate(\"m\", \"hi there\", 3, 0.0))\n")
    out, _, warnings = run(src)
    assert warnings == []
    # encode -> [7, 7]; argmax picks index 1 three times; eos=999 never hit
    assert out == "d:5\n"


def test_tf_generate_temperature(fake_llm):
    src = ("import transformers\ndefine function main:\n"
           "    print(tf_generate(\"m\", \"hi there\", 2, 2.0))\n")
    out, _, warnings = run(src)
    assert warnings == []
    # multinomial fake returns 6 each step
    assert out == "d:4\n"


def test_tf_generate_stops_at_eos(fake_llm):
    fake_llm["argmax"] = 999
    src = ("import transformers\ndefine function main:\n"
           "    print(tf_generate(\"m\", \"hi there\", 5, 0.0))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "d:2\n"


def test_tf_pipelines(fake_llm):
    src = ("import transformers\ndefine function main:\n"
           "    print(tf_generate_pipeline(\"m\", \"hello\"))\n"
           "    create r as Dict\n"
           "    set r to tf_classify(\"m\", \"i love it\")\n"
           "    print(r[\"label\"])\n"
           "    print(r[\"score\"])\n"
           "    print(tf_summarize(\"m\", \"long text here\"))\n"
           "    print(tf_translate(\"m\", \"hello\"))\n"
           "    print(tf_fill_mask(\"m\", \"Paris is the [MASK] of France\"))\n"
           "    print(tf_answer(\"m\", \"who?\", \"some context\"))\n"
           "    print(tf_zero_shot(\"m\", \"i love it\", [\"pos\", \"neg\"]))\n"
           "    print(tf_encode(\"m\", \"a b c\"))\n"
           "    print(tf_decode(\"m\", [7, 7]))\n"
           "    print(tf_download(\"m\"))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == ("gen:hello\nPOSITIVE\n0.97\nsum:long \ntra:hello\n"
                   "paris\nans:who?\npos\n[7, 7, 7]\nd:2\n/cache/m\n")


def test_tf_embed(fake_llm):
    src = ("import transformers\ndefine function main:\n"
           "    print(tf_embed(\"m\", \"hi\"))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "[2.0, 3.0]\n"


# ---------------- tokenizer ----------------

def test_tok_estimate_no_deps():
    out, _, warnings = run("import tokenizer\ndefine function main:\n"
                           "    print(tok_estimate(\"hello world\"))\n")
    assert warnings == []
    assert out == "3\n"


def test_tokenizer_missing():
    with pytest.raises(Exception, match="pip install transformers"):
        run("import tokenizer\ndefine function main:\n"
            "    print(tok_count(\"m\", \"hi\"))\n")
    with pytest.raises(Exception, match="pip install tiktoken"):
        run("import tokenizer\ndefine function main:\n"
            "    print(tok_tiktoken_count(\"cl100k_base\", \"hi\"))\n")


def test_tokenizer_hf(fake_llm):
    src = ("import tokenizer\ndefine function main:\n"
           "    print(tok_count(\"m\", \"a b c\"))\n"
           "    print(tok_truncate(\"m\", \"a b c d\", 2))\n"
           "    create ch as List\n"
           "    set ch to tok_chunks(\"m\", \"aaa\\n\\nbbb\", 1)\n"
           "    print(len(ch))\n"
           "    print(ch[0])\n"
           "    print(ch[1])\n"
           "    create ch2 as List\n"
           "    set ch2 to tok_chunks(\"m\", \"aaa\\n\\nbbb\", 2)\n"
           "    print(len(ch2))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "3\nd:2\n2\naaa\nbbb\n1\n"


def test_tokenizer_tiktoken(fake_llm):
    src = ("import tokenizer\ndefine function main:\n"
           "    print(tok_tiktoken_count(\"cl100k_base\", \"a b c\"))\n"
           "    print(tok_tiktoken_decode(\"cl100k_base\", [100, 101]))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "3\ntt:2\n"


# ---------------- torchutils ----------------

def test_torchutils_missing():
    with pytest.raises(Exception, match="pip install torch"):
        run("import torchutils\ndefine function main:\n"
            "    print(torch_version())\n")


def test_torchutils(fake_llm):
    src = ("import torchutils\ndefine function main:\n"
           "    print(torch_version())\n"
           "    print(torch_cuda_available())\n"
           "    print(torch_device())\n"
           "    torch_seed(7)\n"
           "    create a as Object\n"
           "    set a to torch_tensor([1, 2])\n"
           "    create b as Object\n"
           "    set b to torch_tensor([3, 4])\n"
           "    print(torch_to_list(torch_add(a, b)))\n"
           "    print(torch_to_list(torch_sub(b, a)))\n"
           "    print(torch_to_list(torch_mul(a, b)))\n"
           "    create m1 as Object\n"
           "    set m1 to torch_tensor([[1, 2], [3, 4]])\n"
           "    create m2 as Object\n"
           "    set m2 to torch_tensor([[5, 6], [7, 8]])\n"
           "    print(torch_to_list(torch_matmul(m1, m2)))\n"
           "    print(torch_argmax(torch_tensor([0.1, 0.9, 0.3])))\n"
           "    print(torch_sum(torch_tensor([1, 2, 3])))\n"
           "    print(torch_mean(torch_tensor([1.0, 2.0, 3.0])))\n"
           "    print(torch_norm(torch_tensor([3.0, 4.0])))\n"
           "    print(torch_shape(torch_zeros([2, 3])))\n"
           "    torch_save(a, \"t.pt\")\n"
           "    print(torch_to_list(torch_load(\"t.pt\")))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == ("2.9.0-fake\nTrue\ncuda\n[4, 6]\n[2, 2]\n[3, 8]\n"
                   "[[19, 22], [43, 50]]\n1\n6.0\n2.0\n5.0\n[2, 3]\n[1, 2]\n")
    assert fake_llm["seed"] == 7


# ---------------- datasets ----------------

def test_datasets_missing():
    with pytest.raises(Exception, match="pip install datasets"):
        run("import datasets\ndefine function main:\n"
            "    print(ds_len(ds_load(\"x\")))\n")


def test_datasets(fake_llm):
    src = ("import datasets\ndefine function main:\n"
           "    create ds as Object\n"
           "    set ds to ds_load(\"squad\")\n"
           "    print(ds_len(ds))\n"
           "    create r as Dict\n"
           "    set r to ds_row(ds, 1)\n"
           "    print(r[\"x\"])\n"
           "    print(ds_column(ds, \"x\"))\n"
           "    print(ds_column_names(ds))\n"
           "    print(ds_len(ds_take(ds, 2)))\n"
           "    create sk as Object\n"
           "    set sk to ds_skip(ds, 1)\n"
           "    print(ds_column(sk, \"x\"))\n"
           "    create parts as List\n"
           "    set parts to ds_split(ds, 0.5, 7)\n"
           "    print(ds_len(parts[0]))\n"
           "    print(ds_len(parts[1]))\n"
           "    create recs as List\n"
           "    set recs to ds_to_records(parts[1])\n"
           "    print(recs[0][\"x\"])\n"
           "    ds_save(ds, \"/tmp/ds\")\n"
           "    create back as Object\n"
           "    set back to ds_load_disk(\"/tmp/ds\")\n"
           "    print(ds_len(back))\n"
           "    create made as Object\n"
           "    set made to ds_from_records([{\"x\": 1}])\n"
           "    print(ds_len(made))\n")
    out, _, warnings = run(src)
    assert warnings == []
    # shuffle reverses -> [3,2,1]; n_test=int(3*0.5)=1 -> test=[3], train=[2,1]
    assert out == ("3\n2\n[1, 2, 3]\n['x']\n2\n[2, 3]\n2\n1\n3\n1\n1\n")
    assert fake_llm.get("ds_saved") == "/tmp/ds"


# ---------------- embeddings ----------------

def test_emb_cosine_no_deps():
    src = ("import embeddings\ndefine function main:\n"
           "    print(emb_cosine([1.0, 0.0], [1.0, 0.0]))\n"
           "    print(emb_cosine([1.0, 0.0], [0.0, 1.0]))\n"
           "    print(emb_cosine([0.0, 0.0], [1.0, 1.0]))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "1.0\n0.0\n0.0\n"


def test_embeddings_missing():
    with pytest.raises(Exception, match="pip install sentence-transformers"):
        run("import embeddings\ndefine function main:\n"
            "    print(emb_encode(\"m\", [\"hi\"]))\n")


def test_embeddings_search(fake_llm):
    src = ("import embeddings\ndefine function main:\n"
           "    create hits as List\n"
           "    set hits to emb_search(\"m\", \"q\", [\"a\", \"b\", \"c\"])\n"
           "    for each h in hits:\n"
           "        print(h[0])\n")
    out, _, warnings = run(src)
    assert warnings == []
    # q~a cosine 1.0, q~c ~0.707, q~b 0.0 -> order a, c, b
    assert out == "0\n2\n1\n"


# ---------------- finetune ----------------

def test_finetune_missing():
    with pytest.raises(Exception, match="pip install transformers"):
        run("import finetune\ndefine function main:\n"
            "    print(ft_prepare_lm(\"m\", [\"hi\"]))\n")


def test_ft_prepare_lm(fake_llm):
    src = ("import finetune\ndefine function main:\n"
           "    create recs as List\n"
           "    set recs to ft_prepare_lm(\"m\", [\"a b\"], 4)\n"
           "    print(len(recs))\n"
           "    print(recs[0][\"input_ids\"])\n"
           "    print(recs[0][\"attention_mask\"])\n"
           "    print(recs[0][\"labels\"])\n")
    out, _, warnings = run(src)
    assert warnings == []
    # encode("a b") -> [7, 7]; pad id = eos 999 -> [7, 7, 999, 999]
    assert out == "1\n[7, 7, 999, 999]\n[1, 1, 0, 0]\n[7, 7, 999, 999]\n"


def test_ft_lora_train(fake_llm):
    src = ("import finetune\ndefine function main:\n"
           "    create recs as List\n"
           "    set recs to [{\"input_ids\": [1], \"attention_mask\": [1],"
           " \"labels\": [1]}]\n"
           "    print(ft_lora_train(\"m\", recs, \"/tmp/out\", [\"q_proj\"]))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "/tmp/out\n"
    assert fake_llm["lora_cfg"] == (8, ["q_proj"], 16)
    assert fake_llm["trained"] is True
    assert fake_llm["save_model_dir"] == "/tmp/out"
    assert fake_llm["trainer_dc"] is None


def test_ft_merge_lora(fake_llm):
    src = ("import finetune\ndefine function main:\n"
           "    print(ft_merge_lora(\"m\", \"ad\", \"/tmp/merged\"))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "/tmp/merged\n"
    assert fake_llm["merged_dir"] == "/tmp/merged"


def test_ft_generate_adapter(fake_llm):
    src = ("import finetune\ndefine function main:\n"
           "    print(ft_generate_adapter(\"m\", \"ad\", \"hi there\", 2, 0.0))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "d:4\n"
