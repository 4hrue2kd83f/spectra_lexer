from math import cos, pi, sin
from typing import Iterator, Sequence


class AffineTransform:
    """ 2D affine transformation.
        Any transform with scaling, rotation, translation, etc. can be composed into at most six coefficients.
        [ax, bx, cx]
        [ay, by, cy]
        [ 0,  0,  1] """

    __slots__ = ("_coefs",)

    def __init__(self) -> None:
        """ Start with the identity transform. """
        self._coefs = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # Transform coefficients [ax, ay, bx, by, cx, cy].

    def _mul(self, x1:float, y1:float, x2:float, y2:float, x3:float, y3:float) -> None:
        """ Apply a transform by matrix multiplication.
            [x1, x2, x3][ax, bx, cx]   [ax*x1+ay*x2, bx*x1+by*x2, cx*x1+cy*x2+x3]
            [y1, y2, y3][ay, by, cy] = [ax*y1+ay*y2, bx*y1+by*y2, cx*y1+cy*y2+y3]
            [ 0,  0,  1][ 0,  0,  1]   [          0,           0,              1] """
        ax, ay, bx, by, cx, cy = self._coefs
        self._coefs = (ax*x1+ay*x2, ax*y1+ay*y2, bx*x1+by*x2, bx*y1+by*y2, cx*x1+cy*x2+x3, cx*y1+cy*y2+y3)

    def rotate(self, degrees:float) -> None:
        """ Rotate the system <degrees> counterclockwise. """
        theta = degrees * pi / 180.0
        c = cos(theta)
        s = sin(theta)
        self._mul(c, -s, s, c, 0.0, 0.0)

    def scale(self, scale_x:float, scale_y:float) -> None:
        """ Grow or shrink the system by decimal scaling factors. """
        self._mul(scale_x, 0.0, 0.0, scale_y, 0.0, 0.0)

    def translate(self, x:float, y:float) -> None:
        """ Translate (move) the system by an additional offset of <x, y>. """
        self._mul(1.0, 0.0, 0.0, 1.0, x, y)

    def compose(self, other:'AffineTransform') -> None:
        """ Combine the effects of another transform with this one. """
        self._mul(*other._coefs)

    def coefs(self) -> Sequence[float]:
        """ Return all six transform coefficients in standard order. """
        return self._coefs


class TextOrientation:
    """ Possible orientation for fitting text inside a shape. """

    def __init__(self, width:float, height:float, angle:float) -> None:
        self._width = width    # Available width in pixels at this orientation.
        self._height = height  # Available height in pixels at this orientation.
        self._angle = angle    # Rotation angle in degrees, CCW positive from horizontal.

    def _max_scale(self, w:float, h:float) -> float:
        """ Return the maximum scale factor that fits a rectangular area of <w, h> inside this shape. """
        return min(self._width / w, self._height / h)

    def legibility(self, w:float, h:float) -> float:
        """ Return a 'legibility' score based on both the scale and tilt angle for text inside this shape.
            Relative legibility by angle is: horizontal=1, vertical=1/2, upside down=0. """
        return self._max_scale(w, h) * (180.0 - abs(self._angle))

    def apply(self, tfrm:AffineTransform, w:float, h:float) -> None:
        """ Apply transformations that will fit text with an area of <w, h> inside this shape.
            The y-axis must be inverted since typography defines +y=up, but computer graphics is +y=down. """
        scale = self._max_scale(w, h)
        tfrm.scale(scale, -scale)
        tfrm.rotate(self._angle)


TextOrientations = Sequence[TextOrientation]


class TextTransformer:
    """ Generates transforms to fit monospaced text glyphs inside irregular shapes.
        Glyphs are defined using standard typography conventions and units. """

    def __init__(self, em_size:int, tracking:int, baseline:int) -> None:
        self._em_size = em_size    # Total line height in native transform units (1000 is common).
        self._tracking = tracking  # Spacing between glyphs in native units.
        self._baseline = baseline  # Baseline height above the origin in native units.

    def iter_char_tfrms(self, n:int) -> Iterator[AffineTransform]:
        """ Yield an unscaled transform for each character of an origin-centered string of length <n>. """
        y = self._baseline - (self._em_size / 2)
        for i in range(n):
            x = (i - n / 2) * self._tracking
            tfrm = AffineTransform()
            tfrm.translate(x, y)
            yield tfrm

    def orient_tfrm(self, n:int, orients:TextOrientations) -> AffineTransform:
        """ Return an affine transform for a complete string of length <n> centered at the origin.
            Use the best-fitting overall transform from the given sequence of orientations. """
        tfrm = AffineTransform()
        if n > 0 and orients:
            w_max = n * self._tracking
            h_max = self._em_size
            best_orient = max(orients, key=lambda o: o.legibility(w_max, h_max))
            best_orient.apply(tfrm, w_max, h_max)
        return tfrm
