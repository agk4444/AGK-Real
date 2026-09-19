"""New stdlib modules (mathutils, randutils, timeutils, sysutils, pathutils,
urlutils, uuidutils, ziputils, iniutils, htmlutils, xmlutils, statutils,
iterutils, colorutils, logutils)."""

import os
import subprocess
import sys

import pytest

from agk.pipeline import run_source


def run(src, **kw):
    return run_source(src, **kw)


def test_mathutils():
    src = ("import mathutils\n"
           "define function main:\n"
           "    print(pi_value())\n"
           "    print(e_value())\n"
           "    print(sqrt_of(2.0))\n"
           "    print(floor_of(3.7))\n"
           "    print(ceil_of(3.2))\n"
           "    print(round_to(3.14159, 2))\n"
           "    print(sin_of(0.0))\n"
           "    print(cos_of(0.0))\n"
           "    print(ln(2.718281828459045))\n"
           "    print(log10_of(100.0))\n"
           "    print(log_base(8.0, 2.0))\n"
           "    print(exp_of(0.0))\n"
           "    print(power(2.0, 10.0))\n"
           "    print(gcd_of(12, 18))\n"
           "    print(factorial_of(5))\n"
           "    print(to_radians(180.0))\n"
           "    print(to_degrees(3.141592653589793))\n"
           "    print(is_close(0.1 + 0.2, 0.3))\n"
           "    print(hypot_of(3.0, 4.0))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == ("3.141592653589793\n2.718281828459045\n1.4142135623730951\n"
                   "3\n4\n3.14\n0.0\n1.0\n1.0\n2.0\n3.0\n1.0\n1024.0\n6\n"
                   "120\n3.141592653589793\n180.0\nTrue\n5.0\n")


def test_mathutils_domain_errors():
    with pytest.raises(Exception, match="square root of a negative"):
        run("import mathutils\ndefine function main:\n    print(sqrt_of(-1.0))\n")
    with pytest.raises(Exception, match="must be positive"):
        run("import mathutils\ndefine function main:\n    print(ln(0.0))\n")
    with pytest.raises(Exception, match="must not be negative"):
        run("import mathutils\ndefine function main:\n    print(factorial_of(-2))\n")


def test_randutils():
    src = ("import randutils\n"
           "define function main:\n"
           "    seed(7)\n"
           "    print(randint_between(5, 5))\n"
           "    print(choice_of([42]))\n"
           "    print(sample_of([1, 2, 3], 0))\n"
           "    seed(7)\n"
           "    print(randint_between(1, 100))\n"
           "    print(randfloat())\n"
           "    print(choice_of([\"a\", \"b\", \"c\"]))\n"
           "    seed(7)\n"
           "    print(randint_between(1, 100))\n"
           "    print(randfloat())\n"
           "    print(choice_of([\"a\", \"b\", \"c\"]))\n"
           "    create xs as List\n"
           "    set xs to [1, 2, 3, 4, 5]\n"
           "    print(sorted(shuffle_list(xs)))\n"
           "    print(sorted(sample_of([10, 20, 30, 40], 2)))\n")
    out, _, warnings = run(src)
    assert warnings == []
    # The two seeded blocks must be identical (reproducible).
    lines = out.splitlines()
    assert lines[0] == "5"
    assert lines[1] == "42"
    assert lines[2] == "[]"
    assert lines[3:6] == lines[6:9]
    assert lines[9] == "[1, 2, 3, 4, 5]"
    assert len(lines[10].strip("[]").split(", ")) == 2


def test_randutils_errors():
    with pytest.raises(Exception, match="empty list"):
        run("import randutils\ndefine function main:\n    print(choice_of([]))\n")
    with pytest.raises(Exception, match="larger than the list"):
        run("import randutils\ndefine function main:\n"
            "    print(sample_of([1], 2))\n")


def test_timeutils():
    src = ("import timeutils\n"
           "define function main:\n"
           "    sleep_seconds(0.0)\n"
           "    print(epoch_seconds() > 1000000000.0)\n"
           "    print(monotonic_seconds() > 0.0)\n"
           "    print(cpu_seconds() >= 0.0)\n"
           "    create s as String\n"
           "    set s to format_epoch(0.0)\n"
           "    print(len(s) == 19)\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "True\nTrue\nTrue\nTrue\n"


def test_timeutils_negative_sleep():
    with pytest.raises(Exception, match="must not be negative"):
        run("import timeutils\ndefine function main:\n    sleep_seconds(-1.0)\n")


def test_sysutils(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prog", "a", "b"])
    monkeypatch.setenv("AGK_TEST_VAR_XYZ", "hello")
    src = ("import sysutils\n"
           "define function main:\n"
           "    setenv(\"AGK_TEST_VAR2_XYZ\", \"world\")\n"
           "    print(getenv(\"AGK_TEST_VAR_XYZ\"))\n"
           "    print(getenv(\"AGK_TEST_VAR2_XYZ\"))\n"
           "    print(getenv(\"AGK_DEFINITELY_MISSING\"))\n"
           "    print(getenv_or(\"AGK_DEFINITELY_MISSING\", \"dflt\"))\n"
           "    print(argv())\n"
           "    print(platform_name() != \"\")\n"
           "    print(len(python_version()) > 0)\n"
           "    print(cwd())\n"
           "    print(home_dir())\n"
           "    print(path_sep())\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == ("hello\nworld\n\ndflt\n['a', 'b']\nTrue\nTrue\n"
                   f"{os.getcwd()}\n{os.path.expanduser('~')}\n{os.sep}\n")


def test_sysutils_exit_code(tmp_path):
    prog = tmp_path / "bye.agk"
    prog.write_text("import sysutils\ndefine function main:\n"
                    "    exit_with_code(3)\n")
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = subprocess.run([sys.executable, "-m", "agk", "run", str(prog)],
                       cwd=repo, capture_output=True)
    assert p.returncode == 3


def test_pathutils():
    src = ("import pathutils\n"
           "define function main:\n"
           "    print(join_path(\"a\", \"b\"))\n"
           "    print(base_name(\"/x/y/z.agk\"))\n"
           "    print(dir_name(\"/x/y/z.agk\"))\n"
           "    print(file_extension(\"a.tar.gz\"))\n"
           "    print(file_stem(\"/x/y/z.agk\"))\n"
           "    print(is_abs_path(\"/x\"))\n"
           "    print(is_abs_path(\"x\"))\n"
           "    print(norm_path(\"a//b/./c\"))\n"
           "    print(is_abs_path(abs_path(\"x\")))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == (f"{os.path.join('a', 'b')}\nz.agk\n/x/y\n.gz\nz\n"
                   f"True\n{os.path.isabs('x')}\na{os.sep}b{os.sep}c\nTrue\n")


def test_urlutils():
    src = ("import urlutils\n"
           "define function main:\n"
           "    print(url_encode(\"hello world!\"))\n"
           "    print(url_decode(\"a%20b%21\"))\n"
           "    print(url_join(\"https://x.com/a/b\", \"c\"))\n"
           "    print(url_parts(\"https://h.com:1/p?q=1\"))\n"
           "    print(url_scheme(\"https://h.com/p\"))\n"
           "    print(url_host(\"https://h.com:8080/p\"))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == ("hello%20world%21\na b!\nhttps://x.com/a/c\n"
                   "['https', 'h.com:1', '/p', 'q=1']\nhttps\nh.com:8080\n")


def test_uuidutils():
    src = ("import uuidutils\n"
           "define function main:\n"
           "    print(len(uuid4_hex()) == 32)\n"
           "    print(len(uuid4_str()) == 36)\n"
           "    print(len(uuid1_hex()) == 32)\n")
    out, ns, warnings = run(src)
    assert warnings == []
    assert out == "True\nTrue\nTrue\n"
    # The version nibble of a v4 UUID string is always "4".
    u = ns["uuid4_str"]()
    assert u[14] == "4" and u[8] == "-" and u[13] == "-"


def test_ziputils_gzip():
    src = ("import ziputils\n"
           "define function main:\n"
           "    create h as String\n"
           "    set h to gzip_compress(\"hello, agk!\")\n"
           "    print(len(h) > 0)\n"
           "    print(gzip_decompress(h))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "True\nhello, agk!\n"


def test_ziputils_gzip_bad_input():
    with pytest.raises(Exception, match="not valid compressed data"):
        run("import ziputils\ndefine function main:\n"
            "    print(gzip_decompress(\"zzzz\"))\n")


def test_ziputils_archive(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.txt").write_text("aaa")
    (tmp_path / "b.txt").write_text("bbb")
    src = ("import ziputils\n"
           "define function main:\n"
           "    zip_create(\"t.zip\", [\"a.txt\", \"b.txt\"])\n"
           "    print(zip_list(\"t.zip\"))\n"
           "    print(zip_read_text(\"t.zip\", \"a.txt\"))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "['a.txt', 'b.txt']\naaa\n"
    with pytest.raises(Exception, match="no such file"):
        run("import ziputils\ndefine function main:\n"
            "    print(zip_read_text(\"t.zip\", \"nope.txt\"))\n")


INI_TEXT = "[server]\nhost = example.com\nport = 8080\n\n[auth]\nuser = gopi\n"


def test_iniutils(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.ini").write_text(INI_TEXT)
    src = ("import iniutils\n"
           "define function main:\n"
           "    print(ini_get(\"app.ini\", \"server\", \"host\"))\n"
           "    print(ini_get(\"app.ini\", \"server\", \"missing\"))\n"
           "    print(ini_get_or(\"app.ini\", \"server\", \"missing\", \"dflt\"))\n"
           "    print(ini_has(\"app.ini\", \"server\", \"port\"))\n"
           "    print(ini_has(\"app.ini\", \"server\", \"missing\"))\n"
           "    print(ini_has_section(\"app.ini\", \"auth\"))\n"
           "    print(ini_has_section(\"app.ini\", \"nope\"))\n"
           "    print(ini_sections(\"app.ini\"))\n"
           "    print(ini_keys(\"app.ini\", \"server\"))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == ("example.com\n\ndflt\nTrue\nFalse\nTrue\nFalse\n"
                   "['server', 'auth']\n['host', 'port']\n")


def test_iniutils_missing_section():
    with pytest.raises(Exception, match="no such section"):
        run("import iniutils\ndefine function main:\n"
            "    print(ini_keys(\"whatever.ini\", \"nope\"))\n")


def test_htmlutils():
    src = ("import htmlutils\n"
           "define function main:\n"
           "    print(html_escape(\"<a href=\\\"x\\\">hi & bye</a>\"))\n"
           "    print(html_unescape(\"&lt;3 &amp; &quot;q&quot;\"))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == ("&lt;a href=&quot;x&quot;&gt;hi &amp; bye&lt;/a&gt;\n"
                   "<3 & \"q\"\n")


XML_DOC = "<catalog><item id=\"a1\">one</item><item id=\"a2\">two</item></catalog>"
XML_DOC_AGK = XML_DOC.replace('"', '\\"')


def test_xmlutils():
    src = ("import xmlutils\n"
           "define function main:\n"
           "    create doc as String\n"
           f"    set doc to \"{XML_DOC_AGK}\"\n"
           "    print(xml_root_tag(doc))\n"
           "    print(xml_find_texts(doc, \"item\"))\n"
           "    print(xml_find_attr(doc, \"item\", \"id\"))\n"
           "    print(xml_find_attr(doc, \"item\", \"missing\"))\n"
           "    print(xml_find_attr(doc, \"nosuch\", \"id\"))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "catalog\n['one', 'two']\na1\n\n\n"


def test_xmlutils_invalid():
    with pytest.raises(Exception, match="invalid XML"):
        run("import xmlutils\ndefine function main:\n"
            "    print(xml_root_tag(\"<oops>\"))\n")


def test_statutils():
    src = ("import statutils\n"
           "define function main:\n"
           "    print(mean_of([1, 2, 3, 4]))\n"
           "    print(median_of([1, 2, 3, 4]))\n"
           "    print(stdev_of([2, 4, 4, 4, 5, 5, 7, 9]))\n"
           "    print(variance_of([2, 4, 4, 4, 5, 5, 7, 9]))\n"
           "    print(mode_of([1, 2, 2, 3]))\n"
           "    print(min_max_of([3, 1, 2]))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "2.5\n2.5\n2.138089935299395\n4.571428571428571\n2\n[1, 3]\n"


def test_statutils_empty():
    with pytest.raises(Exception, match="empty list"):
        run("import statutils\ndefine function main:\n"
            "    print(mean_of([]))\n")
    with pytest.raises(Exception, match="at least 2 values"):
        run("import statutils\ndefine function main:\n"
            "    print(stdev_of([1]))\n")


def test_iterutils():
    src = ("import iterutils\n"
           "define function main:\n"
           "    print(chunked([1, 2, 3, 4, 5], 2))\n"
           "    print(flatten([[1, 2], [3], []]))\n"
           "    print(unique([1, 2, 1, 3, 2]))\n"
           "    print(pairwise([1, 2, 3]))\n"
           "    print(zip_lists([1, 2], [3, 4, 5]))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == ("[[1, 2], [3, 4], [5]]\n[1, 2, 3]\n[1, 2, 3]\n"
                   "[[1, 2], [2, 3]]\n[[1, 3], [2, 4]]\n")


def test_iterutils_chunked_bad_n():
    with pytest.raises(Exception, match="n must be at least 1"):
        run("import iterutils\ndefine function main:\n"
            "    print(chunked([1], 0))\n")


def test_colorutils():
    src = ("import colorutils\n"
           "define function main:\n"
           "    print(strip_ansi(red(\"hi\")))\n"
           "    print(strip_ansi(bold(green(\"yo\"))))\n"
           "    print(red(\"hi\") != \"hi\")\n"
           "    print(strip_ansi(\"plain\"))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "hi\nyo\nTrue\nplain\n"
    # Exact escape sequences, checked from Python.
    _, ns, _ = run("import colorutils\ndefine function main:\n    print(1)\n")
    assert ns["red"]("hi") == "\x1b[31mhi\x1b[0m"
    assert ns["green"]("hi") == "\x1b[32mhi\x1b[0m"
    assert ns["yellow"]("hi") == "\x1b[33mhi\x1b[0m"
    assert ns["blue"]("hi") == "\x1b[34mhi\x1b[0m"
    assert ns["magenta"]("hi") == "\x1b[35mhi\x1b[0m"
    assert ns["cyan"]("hi") == "\x1b[36mhi\x1b[0m"
    assert ns["bold"]("hi") == "\x1b[1mhi\x1b[0m"
    assert ns["strip_ansi"]("\x1b[1;31mhi\x1b[0m") == "hi"


def test_logutils(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = ("import logutils\n"
           "define function main:\n"
           "    log_info(\"app.log\", \"started\")\n"
           "    log_warn(\"app.log\", \"careful\")\n"
           "    log_error(\"app.log\", \"boom\")\n"
           "    log_debug(\"app.log\", \"detail\")\n"
           "    log_line(\"app.log\", \"CUSTOM\", \"raw\")\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == ""
    lines = (tmp_path / "app.log").read_text().splitlines()
    assert len(lines) == 5
    assert lines[0].startswith("[") and "INFO: started" in lines[0]
    assert "WARN: careful" in lines[1]
    assert "ERROR: boom" in lines[2]
    assert "DEBUG: detail" in lines[3]
    assert "CUSTOM: raw" in lines[4]
