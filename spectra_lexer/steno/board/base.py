""" Module for generating steno board diagram elements and descriptions. """

from typing import Dict, List, Tuple

from .caption import CaptionGenerator
from .layout import ElementLayout
from .matcher import ElementMatcher
from spectra_lexer import Component
from spectra_lexer.steno.rules import StenoRule
from spectra_lexer.utils import delegate_to


class BoardRenderer(Component):
    """ Creates graphics and description strings for the board diagram. """

    show_compound = Option("config", "board:show_compound_keys", True,
                           "Show special labels for compound keys (i.e. `f` instead of TP) and numbers")
    show_links = Option("config", "board:show_links", True,
                        "Show hyperlinks to other examples of the current rule. Requires an index.")

    _captioner: CaptionGenerator     # Generates the caption text above the board diagram.
    _matcher: ElementMatcher         # Generates the list of element IDs for each stroke of a rule.
    _layout: ElementLayout = None    # Calculates drawing bounds for each element.
    _last_ids: List[List[str]] = []  # Last set of element IDs, saved in case of resizing.

    def __init__(self) -> None:
        """ Set up the captioner and matcher with empty dictionaries. """
        super().__init__()
        self._captioner = CaptionGenerator()
        self._matcher = ElementMatcher()

    @pipe("new_svg", "new_board_setup")
    def set_svg(self, xml_dict:dict) -> Tuple[str, Dict[str, dict]]:
        """ Save element ID names to the matcher. """
        raw, ids = xml_dict["raw"], xml_dict["ids"]
        self._matcher.set_ids(ids)
        # Send the raw SVG text data along with all element IDs to the GUI.
        return raw, ids

    set_rules = on("new_rules")(delegate_to("_matcher"))
    set_rules_reversed = on("new_rules_reversed")(delegate_to("_captioner"))
    set_index = on("new_index")(delegate_to("_captioner"))

    @pipe("board_set_layout", "new_board_gfx")
    def set_layout(self, view_box:tuple, width:int, height:int) -> List[tuple]:
        """ Set the viewbox and the layout's max bounds if non-zero. Recompute the current layout and send it. """
        if all(view_box[2:3]) and width and height:
            self._layout = ElementLayout(view_box, width, height)
            return self._layout.make_draw_list(self._last_ids)

    @pipe("new_output", "new_board_gfx")
    @pipe("new_graph_selection", "new_board_gfx")
    def get_info(self, rule:StenoRule) -> List[tuple]:
        """ Generate board diagram graphics from a steno rule and send them along with the description.
            The task is identical whether the rule is from a new output or a user graph selection. """
        self.engine_call("new_board_description", self._captioner.get_text(rule, self.show_links))
        # Create the element ID lists (one list for each stroke) with or without the special elements and draw them.
        self._last_ids = self._matcher.get_element_ids(rule, self.show_compound)
        if self._layout is not None:
            return self._layout.make_draw_list(self._last_ids)
