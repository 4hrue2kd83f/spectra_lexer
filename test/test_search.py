#!/usr/bin/env python3

""" Unit tests for search dictionary package. """

import re

import pytest

from spectra_lexer.search import SimilarKeyDict, ReverseDict, StenoSearchDict


def test_skdict_basic():
    """ Basic unit tests for init, getitem, setitem, delitem, len, contains, and eq on SimilarKeyDict. """
    d = SimilarKeyDict({1: "a", 2: "b", 3: "c"})
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


def test_skdict_aux():
    """ Unit tests for get, setdefault, pop, popitem, copy, and fromkeys on SimilarKeyDict. """
    d = SimilarKeyDict({1: "a", 2: "b", 3: "c", 4: "d", 5: "e"}, simfn=abs)
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
    d = SimilarKeyDict.fromkeys([1, 2, 3, 4, 5])
    assert sum(list(d.keys())) == 15
    assert all(v is None for v in d.values())
    d = SimilarKeyDict.fromkeys([1, 2, 3, 4, 5], 6)
    assert all(v == 6 for v in d.values())
    d = SimilarKeyDict.fromkeys([-4, 2, 9, -1, -6], 0, simfn=abs)
    assert d.popitem() == (9, 0)
    # Both the current dict items and similarity function should copy.
    assert d.copy().popitem() == (-6, 0)


def test_skdict_iter():
    """ Unit tests for iter, keys, values, and items in SimilarKeyDict. """
    # Iterators should behave like an ordinary dictionary, independent of the key tracking capabilities.
    d = SimilarKeyDict({48: "0", 65: "A", 124: "|", 97: "a"}, simfn=chr)
    for (k, v, item) in zip(d.keys(), d.values(), d.items()):
        assert any(k_iter == k for k_iter in d)
        assert (k, v) == item


def test_skdict_update():
    """ Unit tests for bool, clear, and update in SimilarKeyDict. Handles args and kwargs from init. """
    # Make a blank dict, add new stuff from (k, v) tuples and keywords, and test it.
    d = SimilarKeyDict(simfn=bool)
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


def test_skdict_values():
    """ Exotic values (functions, nested sequences, self-references) shouldn't break anything. """
    d = SimilarKeyDict({"x" * i: i for i in range(10)}, simfn=str.upper)
    d["func"] = len
    assert d["func"](d) == 11
    d["unwrap me!"] = [([("and get the prize",)],)]
    assert d["unwrap me!"][0][0][0][0] == "and get the prize"
    d["recurse me!"] = d
    assert d["recurse me!"]["recurse me!"]["recurse me!"] is d


def test_skdict_similar():
    """
    For these tests, the similarity function will remove everything but a's in the string.
    This means strings with equal numbers of a's will compare as "similar".
    In the key lists, they are sorted by this measure, then standard string sort order applies second.
    """
    def just_a(key):
        return "".join(c for c in key if c is "a")

    # Keys are restricted to whatever type the similarity function takes, so just use strings for now.
    # The values don't matter; just have them be the number of a's for reference.
    data = {"a": 1, "Canada": 3, "a man!?": 2, "^hates^": 1, "lots\nof\nlines": 0,
            "": 0,  "A's don't count, just a's": 1, "AaaAaa, Ʊnićodə!": 4}
    d = SimilarKeyDict(simfn=just_a, **data)

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


def test_rdict():
    """ Unit tests for the reverse dict class. """
    # A reverse dict must add items to a list rather than overwrite them.
    rd = ReverseDict()
    rd.append_key('beautiful', ('WAOUFL',))
    rd.append_key('BEAUTIFUL', ('PWAOUT', '-FL'))
    rd.append_key('beautiful', ('PWAOUFL',))
    assert rd  == {'beautiful': [('WAOUFL',), ('PWAOUFL',)],
                  'BEAUTIFUL': [('PWAOUT', '-FL')]}
    # Items can be removed from any list; the leftovers will stay in their original order.
    rd.append_key('ugly', ('LUG',))
    rd.append_key('ugly', ('ULG',))
    rd.append_key('ugly', ('UG', 'LY'))
    rd.append_key('ugly', ('UG', 'HREU'))
    rd.remove_key('ugly', ('LUG',))
    rd.remove_key('ugly', ('UG', 'LY'))
    assert rd  == {'beautiful': [('WAOUFL',), ('PWAOUFL',)],
                  'BEAUTIFUL': [('PWAOUT', '-FL')],
                  'ugly':      [('ULG',), ('UG', 'HREU')]}
    # Any list with all entries removed should be totally removed from the dict (don't leave an empty list).
    rd.remove_key('ugly', ('ULG',))
    rd.remove_key('ugly', ('UG', 'HREU'))
    assert rd  == {'beautiful': [('WAOUFL',), ('PWAOUFL',)],
                  'BEAUTIFUL': [('PWAOUT', '-FL')]}
    # A reverse dict should be able to invert any mapping at the most basic level.
    fd = SimilarKeyDict({1: "a", 2: "b", 3: "a", 4: "c", 5: "a", 6: "b", 7: "a", 8: "d"}, simfn=id)
    rd.match_forward(fd)
    assert rd == {"a": [1, 3, 5, 7],
                 "b": [2, 6],
                 "c": [4],
                 "d": [8]}


def test_search():
    """ Unit tests for the main steno search dict class and its special search methods. """
    # Similarity is based on string equality after removing case and stripping certain characters from the ends.
    d = StenoSearchDict(strip_chars=' #{^}')
    d.append_key('beautiful', ('WAOUFL',))
    d.append_key('Beautiful', ('PWAOUFL',))
    d.append_key('{^BEAUTIFUL}  ', ('PWAOUT', '-FL'))
    d.append_key('ugly', ('ULG',))
    assert d.get_similar_keys('beautiful') == ['Beautiful', 'beautiful', '{^BEAUTIFUL}  ']
    assert d.get_similar_keys('{#BEAUtiful}{^}') == ['Beautiful', 'beautiful', '{^BEAUTIFUL}  ']
    assert d.get_similar_keys('') == []

    # Prefix search will return words in sorted order which are supersets of the input starting from
    # the beginning after applying the similarity function. Also stops at the end of the dictionary.
    d.clear()
    d.append_key('beau', ('PWAOU',))
    d.append_key('beautiful', ('WAOUFL',))
    d.append_key('Beautiful', ('PWAOUFL',))
    d.append_key('beautifully', ('PWAOUFL', 'HREU'))
    d.append_key('beautifully', ('PWAOUFL', 'KWREU'))
    d.append_key('ugly', ('ULG',))
    d.append_key('ugliness', ('UG', 'HREU', '-PBS'))
    assert d.prefix_match_keys('beau',   count=4) == ['beau', 'Beautiful', 'beautiful', 'beautifully']
    assert d.prefix_match_keys('UGLY',   count=2) == ['ugly']
    assert d.prefix_match_keys('beauty', count=1) == []

    # Even if a prefix isn't present by itself, the search will return words that contain it
    # going forward from the index where it *would* be found if it was there.
    assert d.prefix_match_keys('beaut', count=5) == ['Beautiful', 'beautiful', 'beautifully']
    assert d.prefix_match_keys('',      count=1) == ['beau']

    # If count is None or not given, prefix search will return all possible supersets in the dictionary.
    assert d.prefix_match_keys('beaut', count=None) == ['Beautiful', 'beautiful', 'beautifully']
    assert d.prefix_match_keys('') == ['beau', 'Beautiful', 'beautiful', 'beautifully', 'ugliness', 'ugly']

    # Regex search is straightforward; return up to count entries in order that match the given regular expression.
    # If no regex metacharacters are present, should just be a case-sensitive starts-with search.
    assert d.regex_match_keys('beau',          count=4) == ['beau', 'beautiful', 'beautifully']
    assert d.regex_match_keys('beautiful.?.?', count=2) == ['beautiful', 'beautifully']
    assert d.regex_match_keys(' beautiful',    count=3) == []
    assert d.regex_match_keys('(b|u).{3}$',    count=2) == ['beau', 'ugly']
    assert d.regex_match_keys('B',             count=9) == ['Beautiful']
    assert d.regex_match_keys('.*ly',          count=5) == ['beautifully', 'ugly']

    # If count is None or not given, regex search should just go through the entire list in order.
    assert d.regex_match_keys('.*u.+y', count=None) == ['beautifully', 'ugly']
    assert d.regex_match_keys('') == ['beau', 'Beautiful', 'beautiful', 'beautifully', 'ugliness', 'ugly']

    # Regex errors won't raise if the algorithm short circuits a pattern with no possible matches.
    assert d.regex_match_keys('an open group that doesn\'t raise(', count=5) == []
    with pytest.raises(re.error):
        d.regex_match_keys('beautiful...an open group(', count=1)