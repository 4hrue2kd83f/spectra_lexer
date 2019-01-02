from __future__ import annotations
from typing import FrozenSet, Iterable, List, NamedTuple, Tuple

from spectra_lexer.keys import StenoKeys

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


class StenoRule(NamedTuple):
    """ A general rule mapping a set of steno keys to a set of letters. All contents are immutable.
        Includes flags, a description, and a submapping of rules that compose it. """

    keys: StenoKeys          # String of steno keys that make up the rule, pre-parsed and sorted.
    letters: str             # Raw English text of the word.
    flags: FrozenSet[str]    # Immutable set of strings describing flags that apply to the rule.
    desc: str                # Textual description of the rule.
    rulemap: _FrozenRuleMap  # Tuple of tuples mapping child rules to letter positions.

    @staticmethod
    def separator() -> StenoRule:
        return RULE_SEP

    @staticmethod
    def key_rules(flags:Iterable[str]) -> List[StenoRule]:
        """ Get key rules from the given flags (only if they are key flags). """
        return [KEY_RULES[f] for f in KEY_FLAG_SET.intersection(flags)]

    def __str__(self) -> str:
        return "{} → {}".format(self.keys.to_rtfcre(), self.letters)


class RuleMapItem(NamedTuple):
    """ Immutable data structure specifying the parent attach positions for a rule. """
    rule: StenoRule
    start: int
    length: int


class RuleMap(List[RuleMapItem]):
    """ List-based rulemap: a sequence meant to hold a series of (rule, start, length) tuples
        indicating the various rules that make up a word and their starting/ending positions.
        Map items should be in sequential order by starting position within the word.
        Must be frozen before inclusion in a rule. """

    def add(self, rule:StenoRule, start:int, length:int) -> None:
        """ Add a single rule to the end of the map. """
        self.append(RuleMapItem(rule, start, length))

    def add_special(self, rule:StenoRule, start:int) -> None:
        """ Add a single special zero-length rule to the end of the map. """
        self.append(RuleMapItem(rule, start, 0))

    def freeze(self):
        """ Freeze the rule map for inclusion in an immutable rule. """
        return _FrozenRuleMap(self)


class _FrozenRuleMap(Tuple[RuleMapItem]):
    """ Immutable tuple-based rulemap for steno rules that require hashability. """


# Rule constants governing key flags and the separator.
RULE_SEP = StenoRule(StenoKeys.separator(), "", frozenset({"SEP"}), "Stroke separator", _FrozenRuleMap())
KEY_RULES = {k: StenoRule(StenoKeys(k.split(":", 1)[0]), "", frozenset({"KEY"}), v, _FrozenRuleMap())
             for (k, v) in KEY_FLAGS.items()}
