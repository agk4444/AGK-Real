"""Tests for the graphics stdlib module (AGK-Real 0.5.0).

A pure-stdlib software rasterizer: drawing primitives plus a hand-rolled
PNG writer (struct + zlib only). Tests run through real AGK programs
(`import graphics`) and call the compiled functions directly.
"""

import binascii
import struct
import zlib

import pytest

from agk.pipeline import run_source


def ns():
    _, namespace, warnings = run_source(
        "import graphics\ndefine function main:\n    print(\"ok\")\n")
    assert warnings == []
    return namespace


def colored(canvas, x, y):
    return canvas["pixels"][y * canvas["width"] + x]


def count_color(canvas, rgb):
    return sum(1 for px in canvas["pixels"] if px == rgb)


def test_new_fills_background():
    g = ns()
    c = g["new"](4, 3, "#112233")
    assert c["width"] == 4 and c["height"] == 3
    assert all(px == [17, 34, 51] for px in c["pixels"])
    c2 = g["new"](2, 2, [10, 20, 30])
    assert all(px == [10, 20, 30] for px in c2["pixels"])


def test_new_rejects_bad_size():
    g = ns()
    with pytest.raises(Exception, match="width and height must be at least 1"):
        g["new"](0, 5, "#000000")


def test_pixel_and_get_pixel():
    g = ns()
    c = g["new"](10, 10, "#000000")
    g["pixel"](c, 1, 2, "#ff0000")
    assert g["get_pixel"](c, 1, 2) == [255, 0, 0]
    assert g["get_pixel"](c, 0, 0) == [0, 0, 0]
    # get_pixel returns a copy: mutating it must not touch the canvas
    px = g["get_pixel"](c, 1, 2)
    px[0] = 0
    assert g["get_pixel"](c, 1, 2) == [255, 0, 0]


def test_pixel_accepts_tuples_and_clamps():
    g = ns()
    c = g["new"](4, 4, "#000000")
    g["pixel"](c, 0, 0, (0, 255, 0))  # tuple works from Python callers
    assert g["get_pixel"](c, 0, 0) == [0, 255, 0]
    g["pixel"](c, 1, 1, [300, -5, 128])  # out-of-range channels clamp
    assert g["get_pixel"](c, 1, 1) == [255, 0, 128]


def test_pixel_rejects_bad_color():
    g = ns()
    c = g["new"](4, 4, "#000000")
    with pytest.raises(Exception, match="must look like"):
        g["pixel"](c, 0, 0, "red")
    with pytest.raises(Exception, match="must be an"):
        g["pixel"](c, 0, 0, 42)


def test_out_of_bounds_drawing_is_clipped():
    g = ns()
    c = g["new"](5, 5, "#000000")
    before = [list(px) for px in c["pixels"]]
    for x, y in [(-1, 0), (0, -1), (5, 0), (0, 5), (100, 100), (-100, -100)]:
        g["pixel"](c, x, y, "#ffffff")
    assert [list(px) for px in c["pixels"]] == before
    # shapes partially off-canvas must not crash either
    g["line"](c, -10, -10, 20, 20, "#ffffff")
    g["rect"](c, -3, -3, 10, 10, "#ffffff", True)
    g["circle"](c, 2, 2, 30, "#ffffff", True)
    with pytest.raises(Exception, match="out of bounds"):
        g["get_pixel"](c, 9, 9)


def test_line_endpoints_and_horizontal():
    g = ns()
    c = g["new"](8, 8, "#000000")
    g["line"](c, 1, 2, 6, 2, "#0000ff")
    for x in range(1, 7):
        assert colored(c, x, 2) == [0, 0, 255], x
    assert colored(c, 0, 2) == [0, 0, 0]
    assert colored(c, 7, 2) == [0, 0, 0]


def test_line_diagonal_through_agk():
    src = ("import graphics\n"
           "define function main:\n"
           "    create c as Object\n"
           '    set c to new(6, 6, "#000000")\n'
           '    line(c, 0, 0, 4, 4, "#00ff00")\n'
           "    print(get_pixel(c, 0, 0))\n"
           "    print(get_pixel(c, 4, 4))\n"
           "    print(get_pixel(c, 2, 3))\n")
    out, _, warnings = run_source(src)
    assert warnings == []
    assert out == "[0, 255, 0]\n[0, 255, 0]\n[0, 0, 0]\n"


def test_rect_fill_vs_outline_counts():
    g = ns()
    c = g["new"](10, 10, "#000000")
    g["rect"](c, 2, 2, 4, 3, "#ff0000", True)
    assert count_color(c, [255, 0, 0]) == 12
    c2 = g["new"](10, 10, "#000000")
    g["rect"](c2, 2, 2, 4, 3, "#00ff00", False)
    assert count_color(c2, [0, 255, 0]) == 2 * 4 + 2 * 3 - 4


def test_rect_default_is_filled():
    g = ns()
    c = g["new"](6, 6, "#000000")
    g["rect"](c, 1, 1, 2, 2, "#ffffff")  # fill defaults to true
    assert count_color(c, [255, 255, 255]) == 4


def test_circle_cardinal_points():
    g = ns()
    c = g["new"](21, 21, "#000000")
    g["circle"](c, 10, 10, 5, "#ffffff", False)
    for pt in [(15, 10), (5, 10), (10, 15), (10, 5)]:
        assert colored(c, *pt) == [255, 255, 255], pt
    # outline must not fill the center
    assert colored(c, 10, 10) == [0, 0, 0]


def test_circle_fill_covers_center():
    g = ns()
    c = g["new"](21, 21, "#000000")
    g["circle"](c, 10, 10, 4, "#ffffff", True)
    assert colored(c, 10, 10) == [255, 255, 255]
    assert colored(c, 14, 10) == [255, 255, 255]
    # symmetry: filled disc is symmetric in all four quadrants
    for dx in range(5):
        for dy in range(5):
            vals = {tuple(colored(c, 10 + dx, 10 + dy)),
                    tuple(colored(c, 10 - dx, 10 + dy)),
                    tuple(colored(c, 10 + dx, 10 - dy)),
                    tuple(colored(c, 10 - dx, 10 - dy))}
            assert len(vals) == 1, (dx, dy, vals)


def test_circle_rejects_negative_radius():
    g = ns()
    c = g["new"](8, 8, "#000000")
    with pytest.raises(Exception, match="radius must be >= 0"):
        g["circle"](c, 4, 4, -1, "#ffffff")


def test_save_png_is_valid_png(tmp_path):
    g = ns()
    c = g["new"](7, 5, "#112233")
    g["pixel"](c, 2, 3, "#ff0000")
    g["line"](c, 0, 0, 6, 4, [0, 255, 0])
    path = str(tmp_path / "out.png")
    assert g["save_png"](c, path) == path
    data = open(path, "rb").read()
    assert data[:8] == bytes([137, 80, 78, 71, 13, 10, 26, 10])
    assert len(data) > 8 + 3 * 12  # magic + at least 3 chunks

    pos, chunks = 8, {}
    while pos < len(data):
        (ln,) = struct.unpack(">I", data[pos:pos + 4])
        typ = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        (crc,) = struct.unpack(">I", data[pos + 8 + ln:pos + 12 + ln])
        assert binascii.crc32(typ + body) == crc, typ
        chunks[typ] = body
        pos += 12 + ln
    assert set(chunks) == {b"IHDR", b"IDAT", b"IEND"}

    w, h, depth, ctype, comp, filt, interlace = struct.unpack(
        ">IIBBBBB", chunks[b"IHDR"])
    assert (w, h, depth, ctype) == (7, 5, 8, 2)

    raw = zlib.decompress(chunks[b"IDAT"])
    assert len(raw) == 5 * (1 + 7 * 3)
    expected = b"".join(
        b"\x00" + b"".join(bytes(c["pixels"][y * 7 + x]) for x in range(7))
        for y in range(5))
    assert raw == expected


def test_save_png_through_agk(tmp_path):
    path = str(tmp_path / "demo.png").replace("\\", "/")
    src = ("import graphics\n"
           "define function main:\n"
           "    create c as Object\n"
           '    set c to new(16, 12, "#1a1a2e")\n'
           '    line(c, 0, 0, 15, 11, "#e94560")\n'
           '    rect(c, 2, 2, 5, 4, [0, 255, 0], false)\n'
           '    circle(c, 8, 6, 3, "#0f3460", true)\n'
           f'    print(save_png(c, "{path}"))\n')
    out, _, warnings = run_source(src)
    assert warnings == []
    assert out == path + "\n"
    data = open(path, "rb").read()
    assert data[:8] == bytes([137, 80, 78, 71, 13, 10, 26, 10])
    raw = zlib.decompress(_idat(data))
    assert len(raw) == 12 * (1 + 16 * 3)


def _idat(data):
    pos = 8
    while pos < len(data):
        (ln,) = struct.unpack(">I", data[pos:pos + 4])
        typ = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        if typ == b"IDAT":
            return body
        pos += 12 + ln
    raise AssertionError("no IDAT chunk")
