"""Dependency-free QR Code encoder (ISO/IEC 18004, byte mode).

Pydrud prints a QR code in the terminal so a phone can join a ``pydrud dev``
preview session.  That is a core workflow, so it must keep working even when
the optional third-party ``qrcode`` package is not installed — for example in a
fresh checkout where only the standard library is available.

This module implements just enough of the specification for that job:

* byte-mode encoding for every version (1-40) and error-correction level,
* Reed-Solomon error correction with block interleaving,
* function-pattern placement, data masking with the standard penalty rules,
* format and version information.

``encode_matrix()`` returns a list of rows of booleans (``True`` == dark),
matching the layout produced by ``qrcode.QRCode.get_matrix()``.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

__all__ = [
    "ERROR_CORRECTION_LEVELS",
    "QRCodeError",
    "encode_matrix",
]


class QRCodeError(ValueError):
    """Raised when a payload cannot be encoded as a QR code."""


# Error-correction level -> index used by the tables below and the two-bit
# value stored in the format information.
ERROR_CORRECTION_LEVELS = {"L": 0, "M": 1, "Q": 2, "H": 3}
_FORMAT_EC_BITS = {"L": 0b01, "M": 0b00, "Q": 0b11, "H": 0b10}

# Per version and EC level: (error-correction codewords per block,
# [(block count, data codewords per block), ...]).
_RS_BLOCKS: Sequence[Sequence[Tuple[int, Sequence[Tuple[int, int]]]]] = [
    [(7, [(1, 19)]), (10, [(1, 16)]), (13, [(1, 13)]), (17, [(1, 9)])],
    [(10, [(1, 34)]), (16, [(1, 28)]), (22, [(1, 22)]), (28, [(1, 16)])],
    [(15, [(1, 55)]), (26, [(1, 44)]), (18, [(2, 17)]), (22, [(2, 13)])],
    [(20, [(1, 80)]), (18, [(2, 32)]), (26, [(2, 24)]), (16, [(4, 9)])],
    [(26, [(1, 108)]), (24, [(2, 43)]), (18, [(2, 15), (2, 16)]),
     (22, [(2, 11), (2, 12)])],
    [(18, [(2, 68)]), (16, [(4, 27)]), (24, [(4, 19)]), (28, [(4, 15)])],
    [(20, [(2, 78)]), (18, [(4, 31)]), (18, [(2, 14), (4, 15)]),
     (26, [(4, 13), (1, 14)])],
    [(24, [(2, 97)]), (22, [(2, 38), (2, 39)]), (22, [(4, 18), (2, 19)]),
     (26, [(4, 14), (2, 15)])],
    [(30, [(2, 116)]), (22, [(3, 36), (2, 37)]), (20, [(4, 16), (4, 17)]),
     (24, [(4, 12), (4, 13)])],
    [(18, [(2, 68), (2, 69)]), (26, [(4, 43), (1, 44)]),
     (24, [(6, 19), (2, 20)]), (28, [(6, 15), (2, 16)])],
    [(20, [(4, 81)]), (30, [(1, 50), (4, 51)]), (28, [(4, 22), (4, 23)]),
     (24, [(3, 12), (8, 13)])],
    [(24, [(2, 92), (2, 93)]), (22, [(6, 36), (2, 37)]),
     (26, [(4, 20), (6, 21)]), (28, [(7, 14), (4, 15)])],
    [(26, [(4, 107)]), (22, [(8, 37), (1, 38)]), (24, [(8, 20), (4, 21)]),
     (22, [(12, 11), (4, 12)])],
    [(30, [(3, 115), (1, 116)]), (24, [(4, 40), (5, 41)]),
     (20, [(11, 16), (5, 17)]), (24, [(11, 12), (5, 13)])],
    [(22, [(5, 87), (1, 88)]), (24, [(5, 41), (5, 42)]),
     (30, [(5, 24), (7, 25)]), (24, [(11, 12), (7, 13)])],
    [(24, [(5, 98), (1, 99)]), (28, [(7, 45), (3, 46)]),
     (24, [(15, 19), (2, 20)]), (30, [(3, 15), (13, 16)])],
    [(28, [(1, 107), (5, 108)]), (28, [(10, 46), (1, 47)]),
     (28, [(1, 22), (15, 23)]), (28, [(2, 14), (17, 15)])],
    [(30, [(5, 120), (1, 121)]), (26, [(9, 43), (4, 44)]),
     (28, [(17, 22), (1, 23)]), (28, [(2, 14), (19, 15)])],
    [(28, [(3, 113), (4, 114)]), (26, [(3, 44), (11, 45)]),
     (26, [(17, 21), (4, 22)]), (26, [(9, 13), (16, 14)])],
    [(28, [(3, 107), (5, 108)]), (26, [(3, 41), (13, 42)]),
     (30, [(15, 24), (5, 25)]), (28, [(15, 15), (10, 16)])],
    [(28, [(4, 116), (4, 117)]), (26, [(17, 42)]), (28, [(17, 22), (6, 23)]),
     (30, [(19, 16), (6, 17)])],
    [(28, [(2, 111), (7, 112)]), (28, [(17, 46)]), (30, [(7, 24), (16, 25)]),
     (24, [(34, 13)])],
    [(30, [(4, 121), (5, 122)]), (28, [(4, 47), (14, 48)]),
     (30, [(11, 24), (14, 25)]), (30, [(16, 15), (14, 16)])],
    [(30, [(6, 117), (4, 118)]), (28, [(6, 45), (14, 46)]),
     (30, [(11, 24), (16, 25)]), (30, [(30, 16), (2, 17)])],
    [(26, [(8, 106), (4, 107)]), (28, [(8, 47), (13, 48)]),
     (30, [(7, 24), (22, 25)]), (30, [(22, 15), (13, 16)])],
    [(28, [(10, 114), (2, 115)]), (28, [(19, 46), (4, 47)]),
     (28, [(28, 22), (6, 23)]), (30, [(33, 16), (4, 17)])],
    [(30, [(8, 122), (4, 123)]), (28, [(22, 45), (3, 46)]),
     (30, [(8, 23), (26, 24)]), (30, [(12, 15), (28, 16)])],
    [(30, [(3, 117), (10, 118)]), (28, [(3, 45), (23, 46)]),
     (30, [(4, 24), (31, 25)]), (30, [(11, 15), (31, 16)])],
    [(30, [(7, 116), (7, 117)]), (28, [(21, 45), (7, 46)]),
     (30, [(1, 23), (37, 24)]), (30, [(19, 15), (26, 16)])],
    [(30, [(5, 115), (10, 116)]), (28, [(19, 47), (10, 48)]),
     (30, [(15, 24), (25, 25)]), (30, [(23, 15), (25, 16)])],
    [(30, [(13, 115), (3, 116)]), (28, [(2, 46), (29, 47)]),
     (30, [(42, 24), (1, 25)]), (30, [(23, 15), (28, 16)])],
    [(30, [(17, 115)]), (28, [(10, 46), (23, 47)]), (30, [(10, 24), (35, 25)]),
     (30, [(19, 15), (35, 16)])],
    [(30, [(17, 115), (1, 116)]), (28, [(14, 46), (21, 47)]),
     (30, [(29, 24), (19, 25)]), (30, [(11, 15), (46, 16)])],
    [(30, [(13, 115), (6, 116)]), (28, [(14, 46), (23, 47)]),
     (30, [(44, 24), (7, 25)]), (30, [(59, 16), (1, 17)])],
    [(30, [(12, 121), (7, 122)]), (28, [(12, 47), (26, 48)]),
     (30, [(39, 24), (14, 25)]), (30, [(22, 15), (41, 16)])],
    [(30, [(6, 121), (14, 122)]), (28, [(6, 47), (34, 48)]),
     (30, [(46, 24), (10, 25)]), (30, [(2, 15), (64, 16)])],
    [(30, [(17, 122), (4, 123)]), (28, [(29, 46), (14, 47)]),
     (30, [(49, 24), (10, 25)]), (30, [(24, 15), (46, 16)])],
    [(30, [(4, 122), (18, 123)]), (28, [(13, 46), (32, 47)]),
     (30, [(48, 24), (14, 25)]), (30, [(42, 15), (32, 16)])],
    [(30, [(20, 117), (4, 118)]), (28, [(40, 47), (7, 48)]),
     (30, [(43, 24), (22, 25)]), (30, [(10, 15), (67, 16)])],
    [(30, [(19, 118), (6, 119)]), (28, [(18, 47), (31, 48)]),
     (30, [(34, 24), (34, 25)]), (30, [(20, 15), (61, 16)])],
]

# Row/column centres of the alignment patterns, indexed by version - 1.
_ALIGNMENT_POSITIONS: Sequence[Sequence[int]] = [
    [], [6, 18], [6, 22], [6, 26], [6, 30], [6, 34], [6, 22, 38],
    [6, 24, 42], [6, 26, 46], [6, 28, 50], [6, 30, 54], [6, 32, 58],
    [6, 34, 62], [6, 26, 46, 66], [6, 26, 48, 70], [6, 26, 50, 74],
    [6, 30, 54, 78], [6, 30, 56, 82], [6, 30, 58, 86], [6, 34, 62, 90],
    [6, 28, 50, 72, 94], [6, 26, 50, 74, 98], [6, 30, 54, 78, 102],
    [6, 28, 54, 80, 106], [6, 32, 58, 84, 110], [6, 30, 58, 86, 114],
    [6, 34, 62, 90, 118], [6, 26, 50, 74, 98, 122],
    [6, 30, 54, 78, 102, 126], [6, 26, 52, 78, 104, 130],
    [6, 30, 56, 82, 108, 134], [6, 34, 60, 86, 112, 138],
    [6, 30, 58, 86, 114, 142], [6, 34, 62, 90, 118, 146],
    [6, 30, 54, 78, 102, 126, 150], [6, 24, 50, 76, 102, 128, 154],
    [6, 28, 54, 80, 106, 132, 158], [6, 32, 58, 84, 110, 136, 162],
    [6, 26, 54, 82, 110, 138, 166], [6, 30, 58, 86, 114, 142, 170],
]

# Number of remainder bits appended after the final codeword, by version.
_REMAINDER_BITS = (
    0, 7, 7, 7, 7, 7, 0, 0, 0, 0, 0, 0, 0, 3, 3, 3, 3, 3, 3, 3,
    4, 4, 4, 4, 4, 4, 4, 3, 3, 3, 3, 3, 3, 3, 0, 0, 0, 0, 0, 0,
)

_GF_EXP: List[int] = [0] * 512
_GF_LOG: List[int] = [0] * 256


def _init_tables() -> None:
    value = 1
    for i in range(255):
        _GF_EXP[i] = value
        _GF_LOG[value] = i
        value <<= 1
        if value & 0x100:
            value ^= 0x11D
    for i in range(255, 512):
        _GF_EXP[i] = _GF_EXP[i - 255]


_init_tables()


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _GF_EXP[_GF_LOG[a] + _GF_LOG[b]]


def _generator_polynomial(degree: int) -> List[int]:
    poly = [1]
    for i in range(degree):
        nxt = [0] * (len(poly) + 1)
        for j, coeff in enumerate(poly):
            nxt[j] ^= coeff
            nxt[j + 1] ^= _gf_mul(coeff, _GF_EXP[i])
        poly = nxt
    return poly


def _error_correction_codewords(data: Sequence[int], count: int) -> List[int]:
    generator = _generator_polynomial(count)
    remainder = list(data) + [0] * count
    for i in range(len(data)):
        factor = remainder[i]
        if factor == 0:
            continue
        for j, coeff in enumerate(generator):
            remainder[i + j] ^= _gf_mul(coeff, factor)
    return remainder[len(data):]


def _data_capacity(version: int, level: str) -> int:
    ec_per_block, groups = _RS_BLOCKS[version - 1][ERROR_CORRECTION_LEVELS[level]]
    del ec_per_block
    return sum(count * size for count, size in groups)


def _choose_version(payload_length: int, level: str, minimum: int = 1) -> int:
    for version in range(max(1, minimum), 41):
        count_bits = 8 if version < 10 else 16
        needed = 4 + count_bits + payload_length * 8
        if needed <= _data_capacity(version, level) * 8:
            return version
    raise QRCodeError(
        "payload is too large for a QR code (%d bytes)" % payload_length)


def _encode_codewords(data: bytes, version: int, level: str) -> List[int]:
    capacity = _data_capacity(version, level) * 8
    bits: List[int] = []

    def push(value: int, length: int) -> None:
        for shift in range(length - 1, -1, -1):
            bits.append((value >> shift) & 1)

    push(0b0100, 4)  # byte mode
    push(len(data), 8 if version < 10 else 16)
    for byte in data:
        push(byte, 8)

    push(0, min(4, capacity - len(bits)))  # terminator
    if len(bits) % 8:
        push(0, 8 - len(bits) % 8)

    codewords = [
        int("".join(str(bit) for bit in bits[i:i + 8]), 2)
        for i in range(0, len(bits), 8)
    ]
    for pad in _cycle_padding(capacity // 8 - len(codewords)):
        codewords.append(pad)
    return codewords


def _cycle_padding(count: int) -> List[int]:
    pads = (0xEC, 0x11)
    return [pads[i % 2] for i in range(max(0, count))]


def _interleave(codewords: Sequence[int], version: int, level: str) -> List[int]:
    ec_count, groups = _RS_BLOCKS[version - 1][ERROR_CORRECTION_LEVELS[level]]
    data_blocks: List[List[int]] = []
    ec_blocks: List[List[int]] = []
    offset = 0
    for block_count, block_size in groups:
        for _ in range(block_count):
            block = list(codewords[offset:offset + block_size])
            offset += block_size
            data_blocks.append(block)
            ec_blocks.append(_error_correction_codewords(block, ec_count))

    result: List[int] = []
    for i in range(max(len(block) for block in data_blocks)):
        for block in data_blocks:
            if i < len(block):
                result.append(block[i])
    for i in range(ec_count):
        for block in ec_blocks:
            result.append(block[i])
    return result


def _blank_matrix(size: int) -> List[List[int]]:
    # -1 marks a module that has not been assigned yet.
    return [[-1] * size for _ in range(size)]


def _place_finder(matrix: List[List[int]], row: int, col: int) -> None:
    size = len(matrix)
    for r in range(-1, 8):
        for c in range(-1, 8):
            rr, cc = row + r, col + c
            if not (0 <= rr < size and 0 <= cc < size):
                continue
            dark = (
                (0 <= r <= 6 and c in (0, 6))
                or (0 <= c <= 6 and r in (0, 6))
                or (2 <= r <= 4 and 2 <= c <= 4)
            )
            matrix[rr][cc] = 1 if dark else 0


def _place_function_patterns(matrix: List[List[int]], version: int) -> None:
    size = len(matrix)
    _place_finder(matrix, 0, 0)
    _place_finder(matrix, 0, size - 7)
    _place_finder(matrix, size - 7, 0)

    for position in range(8, size - 8):
        bit = 1 if position % 2 == 0 else 0
        matrix[6][position] = bit
        matrix[position][6] = bit

    centres = _ALIGNMENT_POSITIONS[version - 1]
    last = size - 7
    for row in centres:
        for col in centres:
            # The three corners are occupied by the finder patterns; every
            # other combination gets an alignment pattern (including the ones
            # that sit on top of a timing pattern).
            if (row, col) in ((6, 6), (6, last), (last, 6)):
                continue
            for r in range(-2, 3):
                for c in range(-2, 3):
                    dark = max(abs(r), abs(c)) != 1
                    matrix[row + r][col + c] = 1 if dark else 0

    matrix[size - 8][8] = 1  # dark module

    # Reserve the format information areas.
    for i in range(9):
        if matrix[8][i] == -1:
            matrix[8][i] = 0
        if matrix[i][8] == -1:
            matrix[i][8] = 0
    for i in range(8):
        if matrix[8][size - 1 - i] == -1:
            matrix[8][size - 1 - i] = 0
        if matrix[size - 1 - i][8] == -1:
            matrix[size - 1 - i][8] = 0

    if version >= 7:
        for i in range(18):
            row, col = i // 3, i % 3
            matrix[size - 11 + col][row] = 0
            matrix[row][size - 11 + col] = 0


def _reserved_mask(version: int, size: int) -> List[List[bool]]:
    reserved = _blank_matrix(size)
    _place_function_patterns(reserved, version)
    return [[cell != -1 for cell in row] for row in reserved]


def _place_data(
    matrix: List[List[int]],
    reserved: Sequence[Sequence[bool]],
    bits: Sequence[int],
) -> None:
    size = len(matrix)
    index = 0
    upward = True
    col = size - 1
    while col > 0:
        if col == 6:  # skip the vertical timing pattern column
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for row in rows:
            for offset in (0, 1):
                cc = col - offset
                if reserved[row][cc]:
                    continue
                matrix[row][cc] = bits[index] if index < len(bits) else 0
                index += 1
        upward = not upward
        col -= 2


def _mask_bit(pattern: int, row: int, col: int) -> bool:
    if pattern == 0:
        return (row + col) % 2 == 0
    if pattern == 1:
        return row % 2 == 0
    if pattern == 2:
        return col % 3 == 0
    if pattern == 3:
        return (row + col) % 3 == 0
    if pattern == 4:
        return (row // 2 + col // 3) % 2 == 0
    if pattern == 5:
        return (row * col) % 2 + (row * col) % 3 == 0
    if pattern == 6:
        return ((row * col) % 2 + (row * col) % 3) % 2 == 0
    return ((row + col) % 2 + (row * col) % 3) % 2 == 0


def _apply_mask(
    matrix: Sequence[Sequence[int]],
    reserved: Sequence[Sequence[bool]],
    pattern: int,
) -> List[List[int]]:
    return [
        [
            cell ^ 1 if not reserved[row][col] and _mask_bit(pattern, row, col)
            else cell
            for col, cell in enumerate(line)
        ]
        for row, line in enumerate(matrix)
    ]


_FORMAT_GENERATOR = 0b10100110111
_FORMAT_XOR = 0b101010000010010
_VERSION_GENERATOR = 0b1111100100101


def _bit_length(value: int) -> int:
    return value.bit_length()


def _format_bits(level: str, pattern: int) -> int:
    """15-bit format information (BCH(15, 5) plus the standard mask)."""
    data = (_FORMAT_EC_BITS[level] << 3) | pattern
    value = data << 10
    while _bit_length(value) >= 11:
        value ^= _FORMAT_GENERATOR << (_bit_length(value) - 11)
    return (((data << 10) | value) ^ _FORMAT_XOR) & 0x7FFF


def _version_bits(version: int) -> int:
    """18-bit version information (BCH(18, 6)), used from version 7 on."""
    value = version << 12
    while _bit_length(value) >= 13:
        value ^= _VERSION_GENERATOR << (_bit_length(value) - 13)
    return ((version << 12) | value) & 0x3FFFF


def _place_format_information(
    matrix: List[List[int]], level: str, pattern: int
) -> None:
    size = len(matrix)
    bits = _format_bits(level, pattern)
    for i in range(15):  # i counts from the least significant bit
        bit = (bits >> i) & 1
        # Copy running down the left of the symbol.
        if i < 6:
            matrix[i][8] = bit
        elif i < 8:
            matrix[i + 1][8] = bit
        else:
            matrix[size - 15 + i][8] = bit
        # Copy running along the top of the symbol.
        if i < 8:
            matrix[8][size - 1 - i] = bit
        elif i == 8:
            matrix[8][8] = bit
        else:
            matrix[8][14 - i] = bit


def _place_version_information(matrix: List[List[int]], version: int) -> None:
    if version < 7:
        return
    size = len(matrix)
    bits = _version_bits(version)
    for i in range(18):  # i counts from the least significant bit
        bit = (bits >> i) & 1
        row, col = i // 3, i % 3
        matrix[size - 11 + col][row] = bit
        matrix[row][size - 11 + col] = bit


def _penalty(matrix: Sequence[Sequence[int]]) -> int:
    size = len(matrix)
    score = 0

    # Rule 1: runs of five or more same-coloured modules in a line.
    for line in list(matrix) + [list(col) for col in zip(*matrix)]:
        run_value, run_length = line[0], 1
        for cell in line[1:]:
            if cell == run_value:
                run_length += 1
            else:
                if run_length >= 5:
                    score += run_length - 2
                run_value, run_length = cell, 1
        if run_length >= 5:
            score += run_length - 2

    # Rule 2: 2x2 blocks of the same colour.
    for row in range(size - 1):
        for col in range(size - 1):
            cell = matrix[row][col]
            if (cell == matrix[row][col + 1] == matrix[row + 1][col]
                    == matrix[row + 1][col + 1]):
                score += 3

    # Rule 3: finder-like patterns.
    patterns = ([1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0],
                [0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1])
    for line in list(matrix) + [list(col) for col in zip(*matrix)]:
        line = list(line)
        for start in range(size - 10):
            window = line[start:start + 11]
            if window in patterns:
                score += 40

    # Rule 4: deviation from an even balance of dark and light modules.
    dark = sum(sum(row) for row in matrix)
    percent = dark * 100 / (size * size)
    score += 10 * int(abs(percent - 50) // 5)
    return score


def encode_matrix(
    payload: str,
    *,
    error_correction: str = "M",
    border: int = 4,
    version: int = 0,
) -> List[List[bool]]:
    """Encode ``payload`` and return the module matrix (``True`` == dark).

    ``border`` is the width of the quiet zone added around the symbol.
    ``version`` pins a minimum symbol version; ``0`` picks the smallest one
    that fits.
    """
    level = str(error_correction).upper()
    if level not in ERROR_CORRECTION_LEVELS:
        raise QRCodeError("unknown error correction level: %r" % error_correction)
    if border < 0:
        raise QRCodeError("border must not be negative")

    data = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
    chosen = _choose_version(len(data), level, minimum=max(1, int(version or 1)))

    codewords = _interleave(_encode_codewords(data, chosen, level), chosen, level)
    bits: List[int] = []
    for codeword in codewords:
        bits.extend((codeword >> shift) & 1 for shift in range(7, -1, -1))
    bits.extend([0] * _REMAINDER_BITS[chosen - 1])

    size = chosen * 4 + 17
    reserved = _reserved_mask(chosen, size)
    canvas = _blank_matrix(size)
    _place_function_patterns(canvas, chosen)
    _place_data(canvas, reserved, bits)

    best = None
    for pattern in range(8):
        candidate = _apply_mask(canvas, reserved, pattern)
        _place_format_information(candidate, level, pattern)
        _place_version_information(candidate, chosen)
        score = _penalty(candidate)
        if best is None or score < best[0]:
            best = (score, candidate)
    assert best is not None
    matrix = best[1]

    if not border:
        return [[bool(cell) for cell in row] for row in matrix]
    quiet = [False] * (size + border * 2)
    rows: List[List[bool]] = [list(quiet) for _ in range(border)]
    for row in matrix:
        rows.append([False] * border + [bool(cell) for cell in row]
                    + [False] * border)
    rows.extend(list(quiet) for _ in range(border))
    return rows
