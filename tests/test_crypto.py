"""Tests for the crypto stdlib module (AGK-Real 0.5.0).

Known-answer vectors are checked both through real AGK programs
(`import crypto`) and by calling the compiled functions directly.
"""

import base64
import hashlib
import hmac
import secrets

import pytest

from agk.pipeline import run_source


def ns():
    _, namespace, warnings = run_source(
        "import crypto\ndefine function main:\n    print(\"ok\")\n")
    assert warnings == []
    return namespace


def test_hash_vectors_through_agk():
    src = ("import crypto\n"
           "define function main:\n"
           '    print(sha256("abc"))\n'
           '    print(sha1("abc"))\n'
           '    print(md5("abc"))\n'
           '    print(len(sha512("abc")))\n')
    out, _, warnings = run_source(src)
    assert warnings == []
    assert out == ("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad\n"
                   "a9993e364706816aba3e25717850c26c9cd0d89d\n"
                   "900150983cd24fb0d6963f7d28e17f72\n"
                   "128\n")


def test_hash_vectors_cross_checked():
    c = ns()
    for name in ("sha256", "sha512", "sha1", "md5"):
        for text in ("", "abc", "The quick brown fox jumps over the lazy dog",
                     "héllo wörld"):
            want = hashlib.new(name, text.encode("utf-8")).hexdigest()
            assert c[name](text) == want


def test_hmac_rfc4231_vector():
    # RFC 4231 test case 1 (HMAC-SHA-256): key is 20 bytes of 0x0b.
    c = ns()
    assert c["hmac_sha256"]("\x0b" * 20, "Hi There") == \
        "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7"


def test_hmac_cross_checked():
    c = ns()
    cases = [("key", "The quick brown fox jumps over the lazy dog"),
             ("", ""), ("longer-key-here", "message")]
    for key, msg in cases:
        want = hmac.new(key.encode(), msg.encode(),
                        hashlib.sha256).hexdigest()
        assert c["hmac_sha256"](key, msg) == want


def test_pbkdf2_cross_checked():
    c = ns()
    for iters in (1, 1000):
        want = hashlib.pbkdf2_hmac("sha256", b"password", b"salt",
                                   iters).hex()
        assert c["pbkdf2_hex"]("password", "salt", iters) == want


def test_pbkdf2_rejects_bad_iterations():
    c = ns()
    with pytest.raises(Exception, match="iterations must be at least 1"):
        c["pbkdf2_hex"]("password", "salt", 0)


def test_base64_round_trip():
    src = ("import crypto\n"
           "define function main:\n"
           '    print(base64_encode("hello, agk"))\n'
           '    print(base64_decode("aGVsbG8sIGFnaw=="))\n'
           '    print(base64_decode(base64_encode("round-trip 123")))\n')
    out, _, warnings = run_source(src)
    assert warnings == []
    assert out == "aGVsbG8sIGFnaw==\nhello, agk\nround-trip 123\n"


def test_base64_known_value():
    c = ns()
    assert c["base64_encode"]("hello") == base64.b64encode(b"hello").decode()


def test_base64_decode_rejects_garbage():
    c = ns()
    with pytest.raises(Exception, match="not valid base64"):
        c["base64_decode"]("!!! not base64 !!!")


def test_token_hex_shape():
    c = ns()
    for n in (1, 8, 16):
        tok = c["token_hex"](n)
        assert len(tok) == 2 * n
        assert all(ch in "0123456789abcdef" for ch in tok)
        # matches the stdlib generator it wraps
        assert len(secrets.token_hex(n)) == 2 * n


def test_token_hex_rejects_zero():
    c = ns()
    with pytest.raises(Exception, match="nbytes must be at least 1"):
        c["token_hex"](0)


def test_compare_digest():
    src = ("import crypto\n"
           "define function main:\n"
           '    print(compare_digest("abc", "abc"))\n'
           '    print(compare_digest("abc", "abd"))\n')
    out, _, warnings = run_source(src)
    assert warnings == []
    assert out == "True\nFalse\n"
