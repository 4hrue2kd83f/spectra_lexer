from operator import attrgetter
from typing import Iterable, List, MutableSequence, NamedTuple

from spectra_lexer.keys import StenoKeys, KEY_SEP

# Acceptable rule flags that provide specific meanings to a key (usually the asterisk).
# Each of these will be transformed into a special rule that appears at the end of a result.
KEY_FLAGS = {"*:??":  "purpose unknown\nPossibly resolves a conflict",
             "*:CF":  "resolves conflict between words",
             "*:PR":  "indicates a proper noun\n(names, places, etc.)",
             "*:AB":  "indicates an abbreviation",
             "*:PS":  "indicates a prefix or suffix stroke",
             "*:OB":  "indicates an obscenity\n(and make it harder to be the result of a misstroke)",
             "*:FS":  "indicates fingerspelling",
             "p:FS":  "use to capitalize fingerspelled letters",
             "#:NM":  "use to shift to number mode",
             "EU:NM": "use to invert the order of two digits",
             "d:NM":  "use to double a digit"}
KEY_FLAG_SET = set(KEY_FLAGS.keys())


class RuleMap(List['_MapItem']):
    """ List subclass meant to hold a series of (rule, start, length) tuples indicating
        the various rules that make up a word and their starting/ending positions. """

    class _MapItem(NamedTuple):
        rule: 'StenoRule'
        start: int
        length: int

    def add_child(self, rule:'StenoRule', start:int, length:int) -> None:
        """ Add a single rule to the end of the map. """
        self.append(self._MapItem(rule, start, length))

    def add_key_rules(self, flags:MutableSequence[str], start:int, remove_flags:bool=False) -> None:
        """ Add key rules to the end of the rulemap from the given flags (only if they are key flags).
            If remove_flags is True, remove the key flags we used from the source container. """
        key_flags = KEY_FLAG_SET.intersection(flags)
        for f in key_flags:
            self.append(self._MapItem(_KEY_RULES[f], start, 0))
            if remove_flags:
                flags.remove(f)

    def add_separator(self, start:int) -> None:
        """ Add a stroke separator rule to the rulemap at the given position. """
        self.append(self._MapItem(_RULE_SEP, start, 0))

    def ends_with_separator(self) -> bool:
        """ Is the final rule a stroke separator? """
        return self[-1].rule.is_separator()

    def get_word_coverage(self) -> int:
        """ Return the number of characters between the start of the first child rule and the end of the last. """
        if self:
            start_item = self[0]
            end_item = self[-1]
            return end_item.start + end_item.length - start_item.start
        return 0

    def keys_matched(self, agetter=attrgetter("rule.keys")) -> int:
        """ Get the total number of keys matched by mapped rules. """
        return sum(map(len, map(agetter, self)))

    def letters_matched(self,  agetter=attrgetter("rule.letters")) -> int:
        """ Get the total number of characters matched by mapped rules. """
        return sum(map(len, map(agetter, self)))

    def rules(self, agetter=attrgetter("rule")) -> Iterable['StenoRule']:
        """ Iterator that returns every rule in sequence. """
        return map(agetter, self)


class StenoRule(NamedTuple):
    """ A general rule mapping a set of steno keys to a set of letters.
        May include flags, a description, and/or a submapping of rules that compose it. """

    name: str          # Reference name used for compound rules.
    keys: StenoKeys    # String of steno keys that make up the rule, pre-parsed and sorted.
    letters: str       # Raw English text of the word.
    flags: tuple       # Tuple of strings describing flags that apply to the rule.
    desc: str          # Textual description of the rule.
    rulemap: RuleMap   # List of tuples mapping child rules to letter positions. Must be copied from the source.

    def is_separator(self) -> bool:
        """ Is the current rule a stroke separator? """
        return self is _RULE_SEP


# Rule constants governing separators and star flags.
_RULE_SEP = StenoRule(KEY_SEP, StenoKeys(KEY_SEP), "", ("SPEC",), "Stroke separator", RuleMap())
_KEY_RULES = {k: StenoRule(k, StenoKeys(k.split(":", 1)[0]), "", ("KEY",), v, RuleMap()) for (k, v) in KEY_FLAGS.items()}
