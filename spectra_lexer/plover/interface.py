import itertools
import pkg_resources
from typing import Callable, Iterable, List, Optional, Sequence

from spectra_lexer import SpectraComponent
from spectra_lexer.keys import join_strokes

# Minimum version of Plover required for plugin compatibility.
_PLOVER_VERSION_REQUIRED = "4.0.0.dev8"
_INCOMPATIBLE_MESSAGE = "ERROR: Plover v{} or greater required.".format(_PLOVER_VERSION_REQUIRED)

# Partial class structures that specify a minimum level of functionality for compatibility with Plover.
class PloverStenoDict:
    enabled: bool
    items: Callable

class PloverStenoDictCollection:
    dicts: Sequence[PloverStenoDict]

class PloverAction:
    prev_attach: bool
    text: Optional[str]

class PloverTranslation:
    rtfcre: tuple
    english: Optional[str]

class PloverTranslatorState:
    translations: Sequence[PloverTranslation]

class PloverEngine:
    dictionaries: PloverStenoDictCollection
    translator_state: PloverTranslatorState
    signal_connect: Callable


class PloverPluginInterface(SpectraComponent):
    """ Interface class for Plover plugin. It is the only class that should directly access Plover's objects.
        Receives and processes dictionaries and translations from Plover using callbacks. """

    _plover_engine: PloverEngine = None  # Plover engine, required to access dictionaries and translations.
    _last_strokes: List[str]             # Most recent set of contiguous strokes.
    _last_text: List[str]                # Most recent text output from those strokes.

    def __init__(self):
        self._last_strokes = []
        self._last_text = []

    def engine_commands(self) -> dict:
        """ Individual components must define the signals they respond to and the appropriate callbacks. """
        return {"plover_setup": self.setup_interface}

    def setup_interface(self, *args) -> None:
        """ Perform setup if a compatible version of Plover is detected. """
        # If not, send an error message and prevent any further interaction with Plover.
        if not _compatibility_check():
            self.engine_call("set_status_message", _INCOMPATIBLE_MESSAGE, broadcast=True)
            return
        # If the compatibility check is passed, we should be confident that the only argument is the Plover engine.
        self._plover_engine = args[0]
        # Lock the Plover engine thread, load a fresh copy of the dicts, and connect the callbacks.
        with self._plover_engine as plover:
            self.load_dict_collection(plover.dictionaries)
            plover.signal_connect('dictionaries_loaded', self.load_dict_collection)
            plover.signal_connect('translated', self.on_new_translation)

    def load_dict_collection(self, steno_dc:PloverStenoDictCollection) -> None:
        """ When Plover dictionaries become available, parse and merge them all into a standard dict for search. """
        if steno_dc and steno_dc.dicts:
            parsed = _parse_plover_dicts([d for d in steno_dc.dicts if d and d.enabled])
            self.engine_call("search_set_dict", parsed)

    def on_new_translation(self, _, new:Sequence[PloverAction]) -> None:
        """ When a new translation becomes available, see if it can or should be formatted and sent to the lexer. """
        new_strokes = []
        new_text = []
        # Lock the Plover engine thread to read the translator state.
        with self._plover_engine as plover:
            t_list = plover.translator_state.translations
            t = t_list[-1] if t_list else None
            t_strokes, t_text = (t.rtfcre, t.english) if t else (None, None)
        # Make sure that we have at least one new action and one recent translation.
        # That translation must have an English mapping with at least one alphanumeric character.
        if new and t_text and any(map(str.isalnum, t_text)):
            # If this action attaches to the previous one, start with the strokes and text from the last analysis.
            if new[0].prev_attach:
                new_strokes = self._last_strokes
                new_text = self._last_text
            # Extend lists with all strokes from the given translation and text from all the given actions.
            new_strokes.extend(t_strokes)
            new_text.extend(a.text for a in new if a.text)
            # Combine the strokes and text into single strings, make a lexer query, and display the results.
            result = self.engine_call("lexer_query", join_strokes(new_strokes), "".join(new_text))
            self.engine_call("display_rule", result)
        # Reset the "previous" variables for next time. If we skipped the analysis due to a bad translation
        # or action, the new variables will still be blank, so this resets everything to empty.
        self._last_strokes = new_strokes
        self._last_text = new_text


def _compatibility_check() -> bool:
    """ Return True only if a compatible version of Plover is found in the working set. """
    try:
        pkg_resources.working_set.require("plover>="+_PLOVER_VERSION_REQUIRED)
        return True
    except pkg_resources.ResolutionError:
        return False


def _parse_plover_dicts(d_iter:Iterable[PloverStenoDict]) -> dict:
    """ Merge all Plover dictionaries into a standard dict. They only have a subset of the standard dict methods.
        If strokes are in tuple form, they must be joined with stroke separators into ordinary strings. """
    merged = {}
    for d in d_iter:
        if isinstance(next(iter(d.items()))[0], tuple):
            kv_alt = itertools.chain.from_iterable(d.items())
            merged.update(zip(map(join_strokes, kv_alt), kv_alt))
        else:
            merged.update(d.items())
    return merged
