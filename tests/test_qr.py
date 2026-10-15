"""Tests for the built-in, dependency-free QR encoder."""

import sys
import unittest

from pydrud.commands.preview import terminal_qr
from pydrud.core.qr import QRCodeError, encode_matrix
from pydrud.core.qr import (
    _FORMAT_EC_BITS,
    _FORMAT_XOR,
    _RS_BLOCKS,
    _mask_bit,
    _reserved_mask,
)
from pydrud.core.preview import PreviewSession, build_preview_uri

_EC_LEVEL_INDEX = {"L": 0, "M": 1, "Q": 2, "H": 3}


def _strip_border(matrix):
    """Remove the quiet zone so only the symbol itself remains."""
    rows = [row for row in matrix if any(row)]
    first = min(row.index(True) for row in rows)
    last = max(len(row) - 1 - row[::-1].index(True) for row in rows)
    top = matrix.index(rows[0])
    return [row[first:last + 1] for row in matrix[top:top + (last - first + 1)]]


def _read_format(symbol):
    size = len(symbol)
    bits = 0
    for i in range(15):
        if i < 6:
            bit = symbol[i][8]
        elif i < 8:
            bit = symbol[i + 1][8]
        else:
            bit = symbol[size - 15 + i][8]
        bits |= int(bit) << i
    data = (bits ^ _FORMAT_XOR) >> 10
    return data >> 3, data & 0b111


def _read_payload(matrix):
    """Decode a symbol produced by :func:`encode_matrix` back to bytes.

    The reader intentionally mirrors the specification rather than the
    encoder's own helpers for placement, so a structural mistake in the
    encoder shows up as a decoding failure.
    """
    symbol = _strip_border(matrix)
    size = len(symbol)
    version = (size - 17) // 4
    ec_bits, mask = _read_format(symbol)
    level = next(key for key, value in _FORMAT_EC_BITS.items() if value == ec_bits)

    reserved = _reserved_mask(version, size)
    bits = []
    upward = True
    col = size - 1
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for row in rows:
            for offset in (0, 1):
                cc = col - offset
                if reserved[row][cc]:
                    continue
                bit = int(symbol[row][cc]) ^ int(_mask_bit(mask, row, cc))
                bits.append(bit)
        upward = not upward
        col -= 2

    codewords = [
        int("".join(str(bit) for bit in bits[i:i + 8]), 2)
        for i in range(0, len(bits) // 8 * 8, 8)
    ]

    # Undo the block interleaving to recover the data codewords.
    ec_count, groups = _RS_BLOCKS[version - 1][_EC_LEVEL_INDEX[level]]
    sizes = [size_ for count, size_ in groups for _ in range(count)]
    blocks = [[] for _ in sizes]
    index = 0
    for position in range(max(sizes)):
        for block_index, block_size in enumerate(sizes):
            if position < block_size:
                blocks[block_index].append(codewords[index])
                index += 1
    data = [codeword for block in blocks for codeword in block]

    stream = []
    for codeword in data:
        stream.extend((codeword >> shift) & 1 for shift in range(7, -1, -1))

    def take(count):
        nonlocal stream
        value = int("".join(str(bit) for bit in stream[:count]), 2)
        stream = stream[count:]
        return value

    assert take(4) == 0b0100, "expected byte mode"
    length = take(8 if version < 10 else 16)
    return bytes(take(8) for _ in range(length)), version, level, ec_count


class QRCodeEncoderTests(unittest.TestCase):
    def test_round_trips_payloads_across_versions_and_levels(self):
        payloads = [
            "A",
            "pydrud",
            "https://github.com/MurShidM01/Pydrud",
            "pydrud://preview/connect?host=192.168.1.24&port=8597"
            "&session=b8d3ccf1-0902-4e4d-b24f-3d1ce1af2423"
            "&token=cLE5V-ksANHidzBKFXbkmkIs8qYZ3HrcjKfI8l6SOaQ"
            "&protocol=1&renderer=2&project=com.example.preview&name=Preview+App",
            "x" * 300,
            "y" * 900,
        ]
        for payload in payloads:
            for level in ("L", "M", "Q", "H"):
                with self.subTest(length=len(payload), level=level):
                    matrix = encode_matrix(payload, error_correction=level)
                    decoded, version, read_level, _ = _read_payload(matrix)
                    self.assertEqual(decoded.decode("utf-8"), payload)
                    self.assertEqual(read_level, level)
                    self.assertTrue(1 <= version <= 40)

    def test_round_trips_non_ascii_payload(self):
        payload = "pydrud — prévisualisation 📱"
        matrix = encode_matrix(payload)
        decoded, _, _, _ = _read_payload(matrix)
        self.assertEqual(decoded.decode("utf-8"), payload)

    def test_matrix_geometry_and_quiet_zone(self):
        matrix = encode_matrix("pydrud", border=4)
        size = len(matrix)
        self.assertTrue(all(len(row) == size for row in matrix))
        self.assertEqual((size - 8 - 17) % 4, 0)
        for index in range(4):
            self.assertFalse(any(matrix[index]))
            self.assertFalse(any(matrix[size - 1 - index]))
            self.assertFalse(any(row[index] for row in matrix))
            self.assertFalse(any(row[size - 1 - index] for row in matrix))

    def test_finder_patterns_are_present_in_all_three_corners(self):
        symbol = _strip_border(encode_matrix("pydrud"))
        size = len(symbol)
        expected = [
            [True] * 7,
            [True] + [False] * 5 + [True],
            [True, False, True, True, True, False, True],
            [True, False, True, True, True, False, True],
            [True, False, True, True, True, False, True],
            [True] + [False] * 5 + [True],
            [True] * 7,
        ]
        corners = ((0, 0), (0, size - 7), (size - 7, 0))
        for row, col in corners:
            block = [list(line[col:col + 7]) for line in symbol[row:row + 7]]
            self.assertEqual(block, expected)

    def test_version_selection_grows_with_payload_and_error_correction(self):
        small = len(_strip_border(encode_matrix("pydrud", error_correction="L")))
        large = len(_strip_border(encode_matrix("pydrud" * 40,
                                                error_correction="L")))
        protective = len(_strip_border(encode_matrix("pydrud" * 40,
                                                     error_correction="H")))
        self.assertLess(small, large)
        self.assertLess(large, protective)

    def test_encoding_is_deterministic(self):
        first = encode_matrix("pydrud://preview", error_correction="Q")
        second = encode_matrix("pydrud://preview", error_correction="Q")
        self.assertEqual(first, second)

    def test_rejects_invalid_arguments(self):
        with self.assertRaises(QRCodeError):
            encode_matrix("pydrud", error_correction="Z")
        with self.assertRaises(QRCodeError):
            encode_matrix("pydrud", border=-1)
        with self.assertRaises(QRCodeError):
            encode_matrix("x" * 3000, error_correction="H")


class TerminalQRWithoutThirdPartyPackageTests(unittest.TestCase):
    """``pydrud dev`` must print a QR even with no third-party packages."""

    def setUp(self):
        self._saved = sys.modules.get("qrcode")
        sys.modules["qrcode"] = None  # make ``import qrcode`` raise ImportError

    def tearDown(self):
        if self._saved is None:
            sys.modules.pop("qrcode", None)
        else:
            sys.modules["qrcode"] = self._saved

    def test_terminal_qr_falls_back_to_the_builtin_encoder(self):
        session = PreviewSession.create("com.example.preview", "Preview App")
        rendered = terminal_qr(
            build_preview_uri(session, "192.168.1.24", 8597), ansi=False)
        lines = rendered.splitlines()
        # Preview payloads use the square half-block rendering.
        self.assertTrue(10 < len(lines) < 40)
        width = len(lines[0])
        height_in_char_units = len(lines) * 2
        # Visual width and height are approximately equal (square).
        self.assertAlmostEqual(width, height_in_char_units, delta=4)
        self.assertTrue(any("█▀▀▀▀▀█" in line for line in lines))

    def test_fallback_output_is_scannable(self):
        session = PreviewSession.create("com.example.preview", "Preview App")
        uri = build_preview_uri(session, "192.168.1.24", 8597)
        matrix = encode_matrix(uri, error_correction="M", border=2)
        decoded, _, _, _ = _read_payload(matrix)
        self.assertEqual(decoded.decode("utf-8"), uri)


if __name__ == "__main__":
    unittest.main()
