""" Module for generating steno board diagram elements and SVG documents. """

from typing import Dict, Iterator, List

from . import OffsetSequence
from .path import ArrowPathGenerator, ChainPathGenerator
from .svg import SVGElement, SVGElements, SVGElementFactory, SVGPathCanvas, \
    SVGStyle, SVGTransform, SVGTranslation, SVGViewbox
from .tfrm import TextOrientation, TextOrientations, TextTransformer

SVGIterator = Iterator[SVGElement]


class Group:
    """ A group of SVG steno board elements with metadata. """

    center = 0j           # Tracks the approximate center of the element in the current stroke.
    iter_overlays = None  # Reserved for special elements that add overlays covering multiple strokes.

    def __iter__(self) -> SVGIterator:
        """ Iterate over all SVG elements, positioned correctly within the context of a single stroke. """
        return iter(())


GroupIter = Iterator[Group]
GroupList = List[Group]


class SimpleGroup(Group):
    """ Sequence-based group of SVG steno board elements. """

    def __init__(self, elems:SVGElements=(), x=0.0, y=0.0) -> None:
        self._elems = elems
        self.center = x + y*1j

    def __iter__(self) -> SVGIterator:
        return iter(self._elems)


class InversionGroup(Group):
    """ Group of curved arrow paths connecting other element groups. """

    PATH_GENERATOR = ArrowPathGenerator()
    LAYER_STYLES = [SVGStyle(fill="none", stroke="#800000", stroke_width="1.5px"),
                    SVGStyle(fill="none", stroke="#FF0000", stroke_width="1.5px")]
    LAYER_SHIFT = -1j

    def __init__(self, factory:SVGElementFactory, *groups:Group) -> None:
        self._factory = factory
        self._groups = groups   # Element groups in order of connection.

    def _iter_layers(self, start:complex, end:complex) -> SVGIterator:
        """ Yield SVG path elements that compose an arrow pointing between <start> and <end>.
            Layers are shifted by an incremental offset to create a drop shadow appearance. """
        for style in self.LAYER_STYLES:
            path = SVGPathCanvas()
            self.PATH_GENERATOR.connect(start, end, path)
            yield self._factory.path(path, style)
            start += self.LAYER_SHIFT
            end += self.LAYER_SHIFT

    def __iter__(self) -> SVGIterator:
        """ Yield arrow paths connecting each pair of groups in both directions. """
        p1 = None
        for grp in self._groups:
            p2 = grp.center
            if p1 is not None:
                yield from self._iter_layers(p1, p2)
                yield from self._iter_layers(p2, p1)
            p1 = p2


class LinkedGroup(Group):
    """ Overlays chains connecting groups which are independent of the main stroke groupings.
        This group does not produce any elements in the normal manner. """

    PATH_GENERATOR = ChainPathGenerator()
    LAYER_STYLES = [SVGStyle(fill="none", stroke="#000000", stroke_width="5.0px"),
                    SVGStyle(fill="none", stroke="#B0B0B0", stroke_width="2.0px")]

    def __init__(self, factory:SVGElementFactory, *strokes:GroupList) -> None:
        self._factory = factory
        self._strokes = strokes  # Element group containers from one or more strokes.

    def _iter_layers(self, p1:complex, p2:complex) -> SVGIterator:
        """ Yield SVG paths that compose half of a chain between the endpoints. """
        path = SVGPathCanvas()
        self.PATH_GENERATOR.connect(p1, p2, path)
        for style in self.LAYER_STYLES:
            yield self._factory.path(path, style)

    def _transformed_stroke(self, stroke:GroupList, x:float, y:float) -> SVGElement:
        """ Create a new SVG group with every element in <stroke> at offset <x, y>. """
        elems = []
        for g in stroke:
            elems += g
        trans = SVGTranslation(x, y)
        return self._factory.group(elems, trans)

    def iter_overlays(self, offsets:OffsetSequence) -> SVGIterator:
        """ For multi-element rules, connect each element group to the next. """
        pairs = [*zip(self._strokes, offsets)]
        p1 = None
        for stroke, offset in pairs:
            for grp in stroke:
                p2 = grp.center + complex(*offset)
                if p1 is not None:
                    yield from self._iter_layers(p1, p2)
                    yield from self._iter_layers(p2, p1)
                p1 = p2
        for stroke, offset in pairs:
            yield self._transformed_stroke(stroke, *offset)


SEPARATOR = Group()  # Stroke separator sentinel group.


class SVGBoardFactory:
    """ Factory for SVG steno board diagrams.
        Elements are added by proc_* methods, which are executed in order according to an external file. """

    FONT_STYLE = SVGStyle(fill="#000000")

    def __init__(self, text_tf:TextTransformer, key_positions:Dict[str, List[int]],
                 shape_defs:Dict[str, dict], glyph_table:Dict[str, str]) -> None:
        self._factory = SVGElementFactory()  # Standard SVG element factory.
        self._text_tf = text_tf              # Transform generator for shape text.
        self._key_positions = key_positions  # Contains offsets of the board layout.
        self._shape_defs = shape_defs        # Defines paths forming the shape and inside area of steno keys.
        self._glyph_table = glyph_table      # Defines paths for each valid text glyph (and a default).
        self._defs_elems = []                # Base definitions to add to every document
        self._base_elems = []                # Base elements to add to every diagram

    def _shape_path(self, x:float, y:float, path_data:str, bg:str) -> SVGElement:
        """ Return an SVG path shape with the given path string, fill, and offset. """
        style = SVGStyle(fill=bg, stroke="#000000")
        trans = SVGTranslation(x, y)
        return self._factory.path(path_data, style, trans)

    def _iter_text_paths(self, x:float, y:float, text:str, orients:TextOrientations) -> SVGIterator:
        """ SVG fonts are not supported on major browsers, so we must draw text using paths. """
        n = len(text)
        orient_tfrm = self._text_tf.orient_tfrm(n, orients)
        char_tfrms = self._text_tf.iter_char_tfrms(n)
        for k, tfrm in zip(text, char_tfrms):
            glyph = self._glyph_table.get(k) or self._glyph_table["DEFAULT"]
            tfrm.compose(orient_tfrm)
            tfrm.translate(x, y)
            coefs = tfrm.coefs()
            svg_transform = SVGTransform(*coefs)
            yield self._factory.path(glyph, self.FONT_STYLE, svg_transform)

    def processed_group(self, bg="#FFFFFF", pos=None, shape=None, text=None) -> Group:
        """ Each keyword defines data that positions and/or constructs SVG elements. """
        if pos is None or shape is None:
            return SimpleGroup()
        x, y = self._key_positions[pos]
        attrs = self._shape_defs[shape]
        path_data = attrs["d"]
        elems = [self._shape_path(x, y, path_data, bg)]
        # Add center offsets for any following text and annotations (such as inversion arrows).
        cx, cy = attrs["center"]
        x += cx
        y += cy
        if text is not None:
            orients = [TextOrientation(*item) for item in attrs["orients"]]
            elems += self._iter_text_paths(x, y, text, orients)
        return SimpleGroup(elems, x, y)

    def inversion_group(self, *groups:Group) -> Group:
        """ Return a group with arrow paths connecting the elements in other groups. """
        return InversionGroup(self._factory, *groups)

    def linked_group(self, *strokes:GroupList) -> Group:
        """ Return a group with chains connecting one or more strokes. """
        return LinkedGroup(self._factory, *strokes)

    def set_base(self, *groups:Group, base_id="_BASE") -> None:
        """ Set the base definitions with all elements in <groups>. """
        elems = [elem for grp in groups for elem in grp]
        ref_base = self._factory.group(elems, elem_id=base_id)
        self._defs_elems = [self._factory.defs(ref_base)]
        self._base_elems = [self._factory.use(base_id)]

    def build_svg(self, groups:GroupList, offsets:OffsetSequence, viewbox:SVGViewbox) -> str:
        """ Separate elements in <groups> into strokes using SEPARATOR as a delimiter sentinel.
            Translate each stroke group using data at the matching index from <offsets>.
            Add overlays (if any), put it all in a new SVG document, and return it in string form. """
        root_elems = [*self._defs_elems]
        if groups:
            overlays = []
            elems = []
            i = 0
            if groups[-1] is not SEPARATOR:
                groups.append(SEPARATOR)
            for grp in groups:
                if grp is SEPARATOR:
                    x, y = offsets[i]
                    trans = SVGTranslation(x, y)
                    stroke = self._factory.group(self._base_elems + elems, trans)
                    root_elems.append(stroke)
                    elems = []
                    i += 1
                else:
                    elems += grp
                    if grp.iter_overlays is not None:
                        overlays += grp.iter_overlays(offsets[i:])
            root_elems += overlays
        document = self._factory.svg(root_elems, viewbox)
        return str(document)
