
import struct
from collections import namedtuple
from enum import Enum
from math import sin

def nibble_hit(b):
    x, c = 0, len(b) * 2
    while x < c:
        yield (b[x] & 0xf0) >> 4
        yield b[x] & 0xf
        x += 1


def nibble_fee(b):
    if (len(b) & 1) != 0:
        raise ValueError("odd length of nibbles")
    x = 0
    while x < len(b):
        yield b[x] << 4 | b[x]
        x += 2


class Bmp:
    LittleEndian = type(
        'BmpLittleEndian', (object, ), {
            'header_fmt': '<2sIHHI',
            'dib_header_fmt': '<IiiHHIIiiII',
            'dib_header_size_fmt': '<I',
            'color_fmt_template': '>%dI'}
    )
    BigEndian = type(
        'BmpBigEndian', (object, ), {
            'header_fmt': '>2sIHHI',
            'dib_header_fmt': '>IiiHHIIiiII',
            'dib_header_size_fmt': '>I',
            'color_fmt_template': '>%dI'}
    )

    class BMPHeader:
        def __init__(self, **kwargs):
            self.id_field = None
            self.size = None
            self.ua = None
            self.ub = None
            self.offset = None
            for key, value in kwargs.items():
                setattr(self, key, value)

        def tuple(self):
            return Bmp.bh(self.id_field, self.size, self.ua, self.ub, self.offset)

    class DIBHeader:
        def __init__(self, **kwargs):
            self.head_size = None
            self.width = None
            self.height = None
            self.plane_count = None
            self.bits = None
            self.mode = None

            self.raw_size = None
            self.res_hor = None
            self.res_ver = None
            self.color_count = None
            self.icolor_count = None

            for key, value in kwargs.items():
                setattr(self, key, value)

        def tuple(self):
            return Bmp.dh(self.head_size, self.width, self.height, self.plane_count, self.bits, self.mode,
                          self.raw_size, self.res_hor, self.res_ver, self.color_count, self.icolor_count)

    bh = namedtuple('BMPHeader', ['id_field', 'size', 'ua', 'ub', 'offset'])
    dh = namedtuple('DIBHeader', [
        'head_size', 'width', 'height', 'plane_count', 'bits', 'mode',
        'raw_size', 'res_hor', 'res_ver', 'color_count', 'icolor_count'])
    rgba = namedtuple('RGBA', ['b', 'g', 'r', 'a'])

    class BMPMode(Enum):
        BI_RGB = 0
        BI_BLE8 = 1
        BI_BLE4 = 2
        BI_BITFIELDS = 3
        BI_JPEG = 4
        BI_PNG = 5

    def __init__(self, handler):
        self.handler = handler
        self.body = bytearray(handler.read())
        if len(self.body) == 0:
            raise ValueError('empty file is bad bmp format, use create() function to make a new bmp')

        if self.body[0] == ord(b'B'):
            self.endian = Bmp.LittleEndian()
        else:
            self.endian = Bmp.BigEndian()

        self.bmp_header = Bmp.BMPHeader(**Bmp.bh(*struct.unpack_from(self.endian.header_fmt, self.body, 0))._asdict())

        dib_header_size = struct.unpack_from(self.endian.dib_header_size_fmt, self.body, 14)[0]
        if dib_header_size != 40:
            raise ValueError("the size of dib_header is not 40, we don't know hot to explain the header")

        self.dib_header = Bmp.DIBHeader(**Bmp.dh(*struct.unpack_from(self.endian.dib_header_fmt, self.body, 14))._asdict())

        if self.dib_header.mode != Bmp.BMPMode.BI_RGB.value:
            raise ValueError("todo: only support compress mode of BI_RGB now")

        self.colors = list(map(
            lambda r: Bmp.rgba(*r), [self.body[k:k+4] for k in range(54, self.bmp_header.offset, 4)]))

        row_size = (((self.dib_header.width * self.dib_header.bits) + 31) >> 5) << 2
        if self.dib_header.bits != 4 and self.dib_header.bits != 8 and self.dib_header.bits != 16 and\
                self.dib_header.bits != 24 and self.dib_header.bits != 32:
            raise ValueError("todo: self.dib_header.bits must be 4, 8, 16, 24 or 32")
        elif self.dib_header.bits == 4:
            self.content = [
                (lambda renamed_row: [next(renamed_row) for _ in range(self.dib_header.width)])(nibble_hit(row))
                for row in [
                    self.body[self.bmp_header.offset:][i:i + row_size]
                    for i in range(self.dib_header.height)]
            ]
        elif (self.dib_header.bits & 7) == 0:
            pix_size = self.dib_header.bits >> 3
            self.content = [
                [row[j*pix_size:j*pix_size+pix_size] for j in range(self.dib_header.width)]
                for row in [
                    self.body[self.bmp_header.offset:][i * row_size:i * row_size + row_size]
                    for i in range(self.dib_header.height)]
            ]

    def __str__(self):
        return str(self.bmp_header.__dict__) + '\n' + str(self.dib_header.__dict__)

    def get_white(self):
        for i in range(len(self.colors)):
            if self.colors[i].b == 255 and self.colors[i].g == 255 and self.colors[i].r == 255:
                return i
        return -1

    def _recalc(self):

        # will not change
        # self.plane_count = None
        # will not change
        # self.bits = None
        # will not change
        # self.mode = None

        # will not change
        # self.res_hor = None
        # will not change
        # self.res_ver = None
        # will not change
        # self.color_count = None
        # will not change
        # self.icolor_count = None
        # will not change
        # self.bmp_header.offset = None

        self.dib_header.height = len(self.content)
        if self.dib_header.height != 0:
            self.dib_header.width = len(self.content[0])
        else :
            self.dib_header.width = 0
        row_size = (((self.dib_header.width * self.dib_header.bits) + 31) >> 5) << 2

        self.head_size = 40
        if self.dib_header.mode == Bmp.BMPMode.BI_RGB.value:
            self.raw_size = row_size * self.dib_header.height
            self.bmp_header.size = self.bmp_header.offset + self.raw_size
        else:
            raise ValueError("we have not supported bmp mode now")

    def _press_color(self):
        if self.dib_header.bits == 16 or self.dib_header.bits == 24 or self.dib_header.bits == 32:
            return b''
        return struct.pack(self.endian.color_fmt_template % len(self.colors),
                       *map(lambda x: x.b << 24 | x.g << 16 | x.r << 8 | x.a, self.colors))

    def _press_row(self, row):
        row_size = (((self.dib_header.width * self.dib_header.bits) + 31) >> 5) << 2
        if self.dib_header.bits == 4:
            b = bytearray(b'\x00' * row_size)
            nf = nibble_fee(row)
            for k in range(len(row) >> 1):
                b[k] = next(nf)
            return b
        elif (self.dib_header.bits & 7) == 0:
            b = bytearray(b'\x00' * row_size)
            pix_size = self.dib_header.bits >> 3

            for k in range(0, len(row)):
                # print(b[k*pix_size:k*pix_size + pix_size], row[k])
                b[k*pix_size:k*pix_size+pix_size] = row[k]
                # print(k*pix_size+pix_size)
            return b
        else:
            raise AssertionError("todo: we have not support 1-bit bmp yet")

    def _press(self):
        return bytes.join(b'', map(self._press_row, self.content))

    def bytes(self):
        b = bytearray()
        self._recalc()
        b += struct.pack(self.endian.header_fmt, *self.bmp_header.tuple())
        b += struct.pack(self.endian.dib_header_fmt, *self.dib_header.tuple())
        b += self._press_color() + self._press()
        return b

    def save(self, bmpx=None):
        if bmpx is None:
            self.handler.write(self.bytes())
        elif isinstance(bmpx, str):
            with open(bmpx, 'wb+') as new_bmp:
                new_bmp.write(self.bytes())
        else:
            bmpx.write(self.bytes())

    @staticmethod
    def create():
        raise Exception("todo")
