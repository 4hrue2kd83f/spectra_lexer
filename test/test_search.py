#!/usr/bin/env python3

""" Unit tests for structures in search dictionary package. """

import pickle
import re

import pytest

from .base import TEST_TRANSLATIONS
from spectra_lexer.search.dict import RegexError, SimilarKeyDict, StringSearchDict
from spectra_lexer.search.engine import SearchEngine


def class_hierarchy_tester(*test_classes:type):
    """ Using a series of relevant test classes, create a decorator which configures test functions to run
        not only on the designated classes, but also on any derived classes that appear in the test set. """
    def using_bases(*bases:type):
        """ Decorator to define the base classes for a class test, so that it may also be run on subclasses.
            Make sure the test is still run on the defined bases at minimum even if they aren't in the list. """
        targets = {c for cls in bases for c in test_classes if issubclass(c, cls)}
        return pytest.mark.parametrize("cls", targets.union(bases))
    return using_bases


# Each test is designed for a specific class, but subclasses should be substitutable, so run the tests on them too.
class_test = class_hierarchy_tester(SimilarKeyDict, StringSearchDict)


@class_test(SimilarKeyDict)
def test_skdict_basic(cls) -> None:
    """ Basic unit tests for init, getitem, setitem, delitem, len, contains, and eq on SimilarKeyDict. """
    d = cls({1: "a", 2: "b", 3: "c"})
    assert 1 in d
    assert 2 in d
    assert 5 not in d
    assert len(d) == 3
    del d[1]
    assert 1 not in d
    assert len(d) == 2
    d[1] = "x"
    assert d[1] == "x"
    assert len(d) == 3
    d[1] = "y"
    assert len(d) == 3
    plain_d = {2: "b", 1: "y", 3: "c"}
    assert d == plain_d
    with pytest.raises(KeyError):
        del d["key not here"]


@class_test(SimilarKeyDict)
def test_skdict_aux(cls) -> None:
    """ Unit tests for get, setdefault, pop, popitem, copy, and fromkeys on SimilarKeyDict. """
    d = cls({1: "a", 2: "b", 3: "c", 4: "d", 5: "e"}, simfn=abs)
    assert d.get(1) == "a"
    assert d.get(5) == "e"
    assert d.get(10) is None
    assert d.get("?", "default") == "default"
    assert d.setdefault(1) == "a"
    assert d.setdefault(-10) is None
    assert d[-10] is None
    assert d.setdefault(0, "default") == "default"
    assert d[0] == "default"
    assert d.pop(5) == "e"
    assert 5 not in d
    with pytest.raises(KeyError):
        d.pop(20)
    assert d.pop(10, "default") == "default"
    # The greatest absolute value key (sorted last in the list) should be -10 here.
    assert d.popitem() == (-10, None)
    d.clear()
    with pytest.raises(KeyError):
        d.popitem()
    d = cls.fromkeys([1, 2, 3, 4, 5])
    assert sum(list(d.keys())) == 15
    assert all(v is None for v in d.values())
    d = cls.fromkeys([1, 2, 3, 4, 5], 6)
    assert all(v == 6 for v in d.values())
    d = cls.fromkeys([-4, 2, 9, -1, -6], 0, simfn=abs)
    assert d.popitem() == (9, 0)
    # Both the current dict items and similarity function should copy.
    assert d.copy().popitem() == (-6, 0)


@class_test(SimilarKeyDict)
def test_skdict_iter(cls) -> None:
    """ Unit tests for iter, keys, values, and items in SimilarKeyDict. """
    # Iterators should behave like an ordinary dictionary, independent of the key tracking capabilities.
    d = cls({48: "0", 65: "A", 124: "|", 97: "a"}, simfn=chr)
    keys_from_iter = set(iter(d))
    for (k, v, item) in zip(d.keys(), d.values(), d.items()):
        assert k in keys_from_iter
        assert (k, v) == item


@class_test(SimilarKeyDict)
def test_skdict_update(cls) -> None:
    """ Unit tests for bool, clear, and update in SimilarKeyDict. Handles args and kwargs from init. """
    # Make a blank dict, add new stuff from (k, v) tuples and keywords, and test it.
    d = cls(simfn=bool)
    d.update([("a list", "yes"), ("of tuples", "okay")], but="add", some="keywords")
    assert d
    assert len(d) == 4
    assert d["a list"] == "yes"
    assert d["some"] == "keywords"
    # Add more items (some overwriting others) and see if it behaves correctly, then clear it.
    d.update([("a list", "still yes"), ("of sets", "nope")])
    assert len(d) == 5
    assert d["a list"] == "still yes"
    d.clear()
    assert not d
    assert len(d) == 0


@class_test(SimilarKeyDict)
def test_skdict_values(cls) -> None:
    """ Exotic values (functions, nested sequences, self-references) shouldn't break anything. """
    d = cls({"x" * i: i for i in range(10)}, simfn=str.upper)
    d["func"] = len
    assert d["func"](d) == 11
    d["unwrap me!"] = [([("and get the prize",)],)]
    assert d["unwrap me!"][0][0][0][0] == "and get the prize"
    d["recurse me!"] = d
    assert d["recurse me!"]["recurse me!"]["recurse me!"] is d


@class_test(SimilarKeyDict)
def test_skdict_pickle(cls) -> None:
    """ Unit tests for reduce and setstate. """
    d = cls({'++++': "a", '++': "b", '+': "c"}, simfn=len)
    assert d.get_similar_keys("test") == ['++++']
    s = pickle.dumps(d)
    new_d = pickle.loads(s)
    assert new_d == d
    assert new_d.get_similar_keys("test") == ['++++']


@class_test(SimilarKeyDict)
def test_skdict_similar(cls) -> None:
    """
    For these tests, the similarity function will remove everything but a's in the string.
    This means strings with equal numbers of a's will compare as "similar".
    In the key lists, they are sorted by this measure, then standard string sort order applies second.
    """
    def just_a(key:str) -> int:
        return key.count("a")

    # Keys are restricted to whatever type the similarity function takes, so just use strings for now.
    # The values don't matter; just have them be the number of a's for reference.
    data = {"a": 1, "Canada": 3, "a man!?": 2, "^hates^": 1, "lots\nof\nlines": 0,
            "": 0,  "A's don't count, just a's": 1, "AaaAaa, Ʊnićodə!": 4}
    d = cls(simfn=just_a, **data)

    # "Similar keys", should be all keys with the same number of a's as the input.
    assert d.get_similar_keys("a") == ["A's don't count, just a's", "^hates^", "a"]
    assert d.get_similar_keys("none in here") == ["", "lots\nof\nlines"]
    assert d.get_similar_keys("Havana") == ["Canada"]
    assert d.get_similar_keys("lalalalala") == []

    # Restrict the number of returned values.
    assert d.get_similar_keys("add", 2) == ["A's don't count, just a's", "^hates^"]
    assert d.get_similar_keys("still none of the first English letter", 1) == [""]

    # Add/delete/mutate individual items and make sure order is maintained for search.
    del d["^hates^"]
    assert d.get_similar_keys("a") == ["A's don't count, just a's", "a"]
    d["----I shall be first!---"] = 1
    assert d.get_similar_keys("a") == ["----I shall be first!---", "A's don't count, just a's", "a"]
    d["^hates^"] = 1
    assert d.get_similar_keys("a") == ["----I shall be first!---", "A's don't count, just a's", "^hates^", "a"]
    del d["----I shall be first!---"]

    # For nearby keys, the number of a's don't have to match exactly; just return keys near the one we want.
    assert d.get_nearby_keys("Canada", 2) == ["a man!?", "Canada"]
    assert d.get_nearby_keys("Canada", 5) == ["^hates^", "a", "a man!?", "Canada", "AaaAaa, Ʊnićodə!"]
    assert d.get_nearby_keys("b", 4) == ["", "lots\nof\nlines", "A's don't count, just a's", "^hates^"]
    assert set(d.get_nearby_keys("EVERYTHING", 100)) == set(d)


@class_test(StringSearchDict)
def test_string_dict(cls) -> None:
    """ Unit tests for the added functionality of the string-based search dict class. """
    # Similarity is based on string equality after removing case and stripping certain characters from the ends.
    d = cls.fromkeys(['beautiful', 'Beautiful', '{^BEAUTIFUL}  ', 'ugly'], simfn=lambda s: s.strip(' #{^}').lower())
    assert d.get_similar_keys('beautiful') == ['Beautiful', 'beautiful', '{^BEAUTIFUL}  ']
    assert d.get_similar_keys('{#BEAUtiful}{^}') == ['Beautiful', 'beautiful', '{^BEAUTIFUL}  ']
    assert d.get_similar_keys('') == []

    # Prefix search will return words in sorted order which are supersets of the input starting from
    # the beginning after applying the similarity function. Also stops at the end of the dictionary.
    keys = {'beau', 'beautiful', 'Beautiful', 'beautifully', 'BEAUTIFULLY', 'ugly', 'ugliness'}
    d.clear()
    d.update(dict.fromkeys(keys))
    assert d.prefix_match_keys('beau',   count=4) == ['beau', 'Beautiful', 'beautiful', 'BEAUTIFULLY']
    assert d.prefix_match_keys('UGLY',   count=2) == ['ugly']
    assert d.prefix_match_keys('beauty', count=1) == []

    # Even if a prefix isn't present by itself, the search will return words that contain it
    # going forward from the index where it *would* be found if it was there.
    assert d.prefix_match_keys('beaut', count=3) == ['Beautiful', 'beautiful', 'BEAUTIFULLY']
    assert d.prefix_match_keys('',      count=1) == ['beau']

    # If count is None or not given, prefix search will return all possible supersets in the dictionary.
    assert d.prefix_match_keys('beaut', count=None) == ['Beautiful', 'beautiful', 'BEAUTIFULLY', 'beautifully']
    assert set(d.prefix_match_keys('')) == keys

    # If raw is False, the similarity keys (case-stripped) will be directly returned.
    assert d.prefix_match_keys('beautiful', raw=False) == ['beautiful', 'beautiful', 'beautifully', 'beautifully']

    # Regex search is straightforward; return up to count entries in order that match the given regular expression.
    # If no regex metacharacters are present, should just be a case-sensitive prefix search.
    assert d.regex_match_keys('beau',          count=4) == ['beau', 'beautiful', 'beautifully']
    assert d.regex_match_keys('beautiful.?.?', count=2) == ['beautiful', 'beautifully']
    assert d.regex_match_keys(' beautiful',    count=3) == []
    assert d.regex_match_keys('(b|u).{3}$',    count=2) == ['beau', 'ugly']
    assert d.regex_match_keys('B',             count=9) == ['Beautiful', 'BEAUTIFULLY']
    assert d.regex_match_keys('.*ly',          count=5) == ['beautifully', 'ugly']

    # If count is None or not given, regex search should just go through the entire list in order.
    assert d.regex_match_keys('.*u.+y', count=None) == ['beautifully', 'ugly']
    assert set(d.regex_match_keys('')) == keys

    # If raw is False, the similarity keys (case-stripped) will be searched instead.
    assert d.regex_match_keys('.*y$',      raw=False) == ['beautifully', 'beautifully', 'ugly']
    assert d.regex_match_keys('Beautiful', raw=False) == []

    # Regex errors won't raise if the algorithm short circuits a pattern with no possible matches.
    assert d.regex_match_keys('an open group that doesn\'t raise(', count=5) == []
    with pytest.raises(RegexError):
        d.regex_match_keys('beautiful...an open group(', count=1)


def test_translations_search() -> None:
    """ Go through each loaded test translation and check all search methods. """
    engine = SearchEngine()
    engine.set_translations(TEST_TRANSLATIONS)
    for keys, word in TEST_TRANSLATIONS.items():
        assert engine.search(word, count=2) == {word: [keys]}
        assert engine.search(keys, count=2, mode_strokes=True) == {keys: [word]}
        assert word in engine.search_regex(re.escape(word), count=2)
        assert keys in engine.search_regex(re.escape(keys), count=2, mode_strokes=True)
