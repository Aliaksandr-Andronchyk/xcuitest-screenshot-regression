"""Minimal PNG reader and writer, standard library only.

Screenshots that come out of a simulator are 8-bit RGB or RGBA, not interlaced,
so that is exactly the subset supported here. Anything else raises PngError with
a message that says what was found, instead of guessing.
"""

import struct
import zlib

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class PngError(Exception):
    pass


class Image:
    """8-bit RGB raster. Pixels live in one flat bytearray, 3 bytes per pixel."""

    __slots__ = ("width", "height", "pixels")

    def __init__(self, width, height, pixels):
        if len(pixels) != width * height * 3:
            raise PngError(
                "pixel buffer is %d bytes, expected %d"
                % (len(pixels), width * height * 3)
            )
        self.width = width
        self.height = height
        self.pixels = pixels

    @classmethod
    def blank(cls, width, height, color=(0, 0, 0)):
        return cls(width, height, bytearray(bytes(color) * width * height))

    @property
    def size(self):
        return (self.width, self.height)

    def get(self, x, y):
        i = (y * self.width + x) * 3
        return (self.pixels[i], self.pixels[i + 1], self.pixels[i + 2])

    def set(self, x, y, color):
        i = (y * self.width + x) * 3
        self.pixels[i] = color[0]
        self.pixels[i + 1] = color[1]
        self.pixels[i + 2] = color[2]


def _chunks(data):
    if data[:8] != PNG_MAGIC:
        raise PngError("not a PNG file: bad signature")
    pos = 8
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if len(body) != length:
            raise PngError("truncated %s chunk" % kind.decode("ascii", "replace"))
        yield kind, body
        pos += 12 + length  # length, type, body, crc


def _unfilter(raw, width, height, channels):
    """Undo the per-scanline filters described in the PNG spec, section 9."""
    stride = width * channels
    out = bytearray(stride * height)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        filter_type = raw[pos]
        pos += 1
        line = bytearray(raw[pos : pos + stride])
        pos += stride
        if filter_type == 0:
            pass
        elif filter_type == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif filter_type == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif filter_type == 4:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                up = prev[i]
                up_left = prev[i - channels] if i >= channels else 0
                p = left + up - up_left
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - up_left)
                if pa <= pb and pa <= pc:
                    pred = left
                elif pb <= pc:
                    pred = up
                else:
                    pred = up_left
                line[i] = (line[i] + pred) & 0xFF
        else:
            raise PngError("unknown scanline filter %d on row %d" % (filter_type, y))
        out[y * stride : (y + 1) * stride] = line
        prev = line
    return out


def read(path):
    """Read a PNG file into an Image, dropping the alpha channel if present."""
    with open(path, "rb") as fh:
        data = fh.read()

    header = None
    idat = bytearray()
    for kind, body in _chunks(data):
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break

    if header is None:
        raise PngError("no IHDR chunk in %s" % path)
    width, height, depth, color_type, compression, filter_method, interlace = header
    if depth != 8:
        raise PngError("only 8-bit PNGs are supported, got %d-bit" % depth)
    if color_type not in (2, 6):
        raise PngError(
            "only truecolour PNGs are supported (colour type 2 or 6), got %d"
            % color_type
        )
    if compression != 0 or filter_method != 0:
        raise PngError("unsupported compression or filter method")
    if interlace != 0:
        raise PngError("interlaced PNGs are not supported")

    channels = 3 if color_type == 2 else 4
    raw = _unfilter(zlib.decompress(bytes(idat)), width, height, channels)
    if channels == 3:
        return Image(width, height, bytearray(raw))

    rgb = bytearray(width * height * 3)
    rgb[0::3] = raw[0::4]
    rgb[1::3] = raw[1::4]
    rgb[2::3] = raw[2::4]
    return Image(width, height, rgb)


def write(path, image):
    """Write an Image as an 8-bit RGB PNG."""
    stride = image.width * 3
    raw = bytearray()
    for y in range(image.height):
        raw.append(0)  # filter type 0: store the scanline as is
        raw += image.pixels[y * stride : (y + 1) * stride]

    def chunk(kind, body):
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", image.width, image.height, 8, 2, 0, 0, 0)
    with open(path, "wb") as fh:
        fh.write(PNG_MAGIC)
        fh.write(chunk(b"IHDR", header))
        fh.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        fh.write(chunk(b"IEND", b""))
