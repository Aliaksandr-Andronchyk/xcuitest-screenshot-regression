"""Minimal dependency-free PNG reader and writer.

Only what a screenshot differ needs: 8-bit grayscale, RGB and RGBA images,
all five scanline filters, interlacing rejected loudly. Images are kept as a
flat bytearray of RGBA pixels plus width and height.
"""

from __future__ import annotations

import struct
import zlib

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


class PngError(ValueError):
    """Raised for anything we refuse to decode."""


class Image:
    """An 8-bit RGBA image."""

    __slots__ = ("width", "height", "pixels")

    def __init__(self, width: int, height: int, pixels: bytearray):
        if len(pixels) != width * height * 4:
            raise PngError(
                "pixel buffer is %d bytes, expected %d" % (len(pixels), width * height * 4)
            )
        self.width = width
        self.height = height
        self.pixels = pixels

    @classmethod
    def blank(cls, width: int, height: int, color=(0, 0, 0, 0)) -> "Image":
        return cls(width, height, bytearray(bytes(color) * (width * height)))

    @property
    def size(self):
        return (self.width, self.height)

    def pixel(self, x: int, y: int):
        i = (y * self.width + x) * 4
        return tuple(self.pixels[i : i + 4])

    def set_pixel(self, x: int, y: int, color) -> None:
        i = (y * self.width + x) * 4
        self.pixels[i : i + 4] = bytes(color)

    def copy(self) -> "Image":
        return Image(self.width, self.height, bytearray(self.pixels))


def _unfilter(raw: bytes, width: int, height: int, bpp: int) -> bytearray:
    """Undo the per-scanline filters, returning raw sample bytes."""
    stride = width * bpp
    out = bytearray(stride * height)
    pos = 0
    prev = bytearray(stride)
    for y in range(height):
        filter_type = raw[pos]
        pos += 1
        line = bytearray(raw[pos : pos + stride])
        pos += stride
        if filter_type == 0:
            pass
        elif filter_type == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif filter_type == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif filter_type == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                if pa <= pb and pa <= pc:
                    pred = a
                elif pb <= pc:
                    pred = b
                else:
                    pred = c
                line[i] = (line[i] + pred) & 0xFF
        else:
            raise PngError("unknown scanline filter %d" % filter_type)
        out[y * stride : (y + 1) * stride] = line
        prev = line
    return out


def _to_rgba(samples: bytearray, width: int, height: int, color_type: int, palette, trns) -> bytearray:
    channels = _CHANNELS[color_type]
    out = bytearray(width * height * 4)
    for i in range(width * height):
        s = i * channels
        o = i * 4
        if color_type == 0:
            v = samples[s]
            out[o : o + 4] = bytes((v, v, v, 255))
        elif color_type == 4:
            v = samples[s]
            out[o : o + 4] = bytes((v, v, v, samples[s + 1]))
        elif color_type == 2:
            out[o : o + 3] = samples[s : s + 3]
            out[o + 3] = 255
        elif color_type == 6:
            out[o : o + 4] = samples[s : s + 4]
        else:  # palette
            idx = samples[s]
            p = idx * 3
            out[o : o + 3] = palette[p : p + 3]
            out[o + 3] = trns[idx] if idx < len(trns) else 255
    return out


def read(data: bytes) -> Image:
    """Decode PNG bytes into an Image."""
    if data[:8] != PNG_MAGIC:
        raise PngError("not a PNG file")
    pos = 8
    width = height = color_type = bit_depth = None
    idat = []
    palette = b""
    trns = b""
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _comp, _filt, interlace = struct.unpack(
                ">IIBBBBB", body
            )
            if interlace:
                raise PngError("interlaced PNG is not supported")
            if bit_depth != 8:
                raise PngError("only 8-bit channels are supported, got %d" % bit_depth)
            if color_type not in _CHANNELS:
                raise PngError("unsupported color type %d" % color_type)
        elif kind == b"PLTE":
            palette = body
        elif kind == b"tRNS":
            trns = body
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
    if width is None:
        raise PngError("PNG has no IHDR chunk")
    samples = _unfilter(zlib.decompress(b"".join(idat)), width, height, _CHANNELS[color_type])
    return Image(width, height, _to_rgba(samples, width, height, color_type, palette, trns))


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))


def write(image: Image) -> bytes:
    """Encode an Image as RGBA PNG bytes."""
    stride = image.width * 4
    raw = bytearray()
    for y in range(image.height):
        raw.append(0)  # filter: none, the diff images compress well enough
        raw += image.pixels[y * stride : (y + 1) * stride]
    return (
        PNG_MAGIC
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", image.width, image.height, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )


def load(path) -> Image:
    with open(path, "rb") as fh:
        return read(fh.read())


def save(image: Image, path) -> None:
    with open(path, "wb") as fh:
        fh.write(write(image))
