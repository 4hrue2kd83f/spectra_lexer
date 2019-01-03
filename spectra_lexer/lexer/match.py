from typing import Dict, List

from spectra_lexer.keys import StenoKeys
from spectra_lexer.lexer.prefix import OrderedKeyPrefixTree
from spectra_lexer.rules import StenoRule
from spectra_lexer.utils import str_prefix

# TODO: Only attempt RARE matches after failing with the normal set of rules.
# Acceptable rule flags that indicate special behavior for the lexer's matching system.
MATCH_FLAGS = {"SPEC": "Special rule used internally (in other rules). The lexer should not match these at all.",
               "WORD": "Exact word match. The parser only does a simple dict lookup for these before trying"
                       "to break a word down, so these entries do not adversely affect lexer performance.",
               "STRK": "Only matches an entire stroke, not part of one. Handled by exact stroke match.",
               "RARE": "Rule applies to very few words. The lexer should try these last, after failing with others."}

# Steno order is not enforced for any keys in this set. This has a large performance and accuracy cost.
# Only the asterisk is used in such a way that this treatment is worth it.
KEY_STAR = "*"
_UNORDERED_KEYS = [KEY_STAR]


class LexerRuleMatcher:
    """ A master dictionary of steno rules. Each component maps strings to steno rules in some way. """

    _special_dict: Dict[str, StenoRule]       # Rules that match by reference name.
    _stroke_dict: Dict[StenoKeys, StenoRule]  # Rules that match by full stroke only.
    _word_dict: Dict[str, StenoRule]          # Rules that match by exact word only (whitespace-separated).
    _prefix_tree: OrderedKeyPrefixTree        # Rules that match by starting with a certain number of keys in order.

    def __init__(self, rules_dict:Dict[str, StenoRule]):
        """ Construct a specially-structured series of dictionaries from a dict of finished rules. """
        special_dict = {}
        stroke_dict = {}
        word_dict = {}
        prefix_tree = OrderedKeyPrefixTree(_UNORDERED_KEYS)
        # Sort rules into specific dictionaries based on their flags.
        for (n, r) in rules_dict.items():
            flags = r.flags
            # Internal rules are only used in special cases, by name.
            if "SPEC" in flags:
                special_dict[n] = r
            # Filter stroke and word rules into their own dicts.
            elif "STRK" in flags:
                stroke_dict[r.keys] = r
            elif "WORD" in flags:
                word_dict[r.letters] = r
            # Everything else gets added to the tree-based prefix dictionary.
            else:
                prefix_tree.add_entry(r.keys, r.letters, r)
        # All internal dictionaries required for active lexer operation go into instance attributes.
        self._special_dict = special_dict
        self._stroke_dict = stroke_dict
        self._word_dict = word_dict
        self._prefix_tree = prefix_tree

    def match(self, keys:StenoKeys, letters:str, is_full_stroke:bool=False, is_full_word:bool=False) -> List[StenoRule]:
        """ Return a list of rules that match the given keys and letters in any of the dictionaries. """
        match_list = self._prefix_tree.prefix_match(keys, letters)
        if is_full_stroke:
            match_list += self._stroke_match(keys, letters)
        if is_full_word:
            match_list += self._word_match(keys, letters)
        return match_list

    def _stroke_match(self, keys:StenoKeys, letters:str) -> List[StenoRule]:
        """ For the stroke dictionary, the rule must match the next full stroke and a subset of the given letters. """
        r = self._stroke_dict.get(keys.first_stroke())
        if r and r.letters in letters:
            return [r]
        return []

    def _word_match(self, keys:StenoKeys, letters:str) -> List[StenoRule]:
        """ For the word dictionary, the rule must match a prefix of the given keys and the next full word."""
        r = self._word_dict.get(str_prefix(letters.lstrip()))
        if r and keys.startswith(r.keys):
            return [r]
        return []

    def special_match(self, name:str) -> StenoRule:
        """ Return a special rule matched explicitly by name (such as a key rule), or None if not found. """
        return self._special_dict.get(name)
