# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from dateutil.tz import tzoffset
from functools import reduce
import pytest

from .context import livecorpus, slurp_test_data
from livecorpus import fetch, model, parse
from livecorpus.model import LiveJournalComment, LiveJournalEntry


def test_7224811():
    entry = _slurp_and_parse_entry(7224811).entry

    assert entry.subject == 'Trans in Japan?'
    assert entry.author == 'nickolas_d'
    assert entry.published == datetime.datetime(2013,
                                                3,
                                                26,
                                                17,
                                                19,
                                                tzinfo=tzoffset(None, 10800))
    assert entry.tags == ['travel']
    assert len(entry.comments) == 2  # 2 "roots"
    assert _total_comments(entry) == 10

    deleted = entry.comments[0].children[0].children[1].children[0].children[2]

    assert deleted.deleted
    assert deleted.children[0].author == 'nickolas_d'
    # TODO: test content? (perhaps prefix and suffix?)


def test_7225494():
    entry = _slurp_and_parse_entry(7225494).entry

    assert entry.subject == '(no title)'
    assert entry.author == 'nathus_dorkus'
    assert entry.published == datetime.datetime(2013,
                                                4,
                                                1,
                                                7,
                                                38,
                                                tzinfo=tzoffset(None, 10800))
    assert entry.tags == ['scar treatment']
    assert len(entry.comments) == 6  # only one nested
    assert _total_comments(entry) == 7


def test_7403857():
    entry = _slurp_and_parse_entry(7403857).entry

    assert entry.subject == 'Uncomfortable with being Transgender'
    assert entry.author == 'ivan_ruskarom'
    assert entry.published == datetime.datetime(2015,
                                                12,
                                                5,
                                                19,
                                                35,
                                                tzinfo=tzoffset(None, 10800))
    assert entry.tags == []
    assert len(entry.comments) == 5  # 5 "roots"
    assert _total_comments(entry) == 14

    assert entry.comments[2].deleted
    assert entry.comments[2].children[0].author == 'ivan_ruskarom'
    # TODO: test content? (perhaps prefix and suffix?)


def test_7415315():
    entry = _slurp_and_parse_entry(7415315).entry

    assert entry.subject == 'Scarring'
    assert entry.author == 'ivan_ruskarom'
    assert entry.published == datetime.datetime(2016,
                                                9,
                                                13,
                                                12,
                                                49,
                                                tzinfo=tzoffset(None, 10800))
    assert entry.tags == ['scar treatment']
    assert len(entry.comments) == 2  # 5 "roots"
    assert _total_comments(entry) == 7

    assert entry.comments[0].deleted
    assert entry.comments[0].children[0].author == 'ivan_ruskarom'
    assert entry.comments[0].children[0].children[0].deleted
    assert entry.comments[0].children[0].children[0].children[
        0].author == 'ivan_ruskarom'
    # TODO: test content? (perhaps prefix and suffix?)


def test_7232256():
    entry = _slurp_and_parse_entry(7232256)

    assert _total_comments(entry.entry) == 10  # 10 no-thread comments
    assert entry.threads == {
        '88040448', '88040960', '88041984', '88042240', '88043264', '88043520',
        '88044800', '88045056', '88045568', '88046592'
    }
    assert entry.next_page == 'https://ftm.livejournal.com/7232256.html?page=2#comments'


def test_7232256_88040960():
    entry = _slurp_and_parse_entry('7232256-88040960')

    assert len(entry.entry.comments) == 1
    assert _total_comments(entry.entry) == 4
    assert not entry.threads
    assert not entry.next_page


def test_585122():
    entry = _slurp_and_parse_entry('585122').entry

    assert entry.subject == 'so two things'
    assert entry.author == 'scaryqueen'
    assert entry.published == datetime.datetime(2008, 2, 3, 20, 53)

    assert _total_comments(entry) == 16
    assert _total_children(entry.comments[0]) == 12
    assert entry.comments[0].deleted
    assert entry.comments[0].children[0].author == 'scaryqueen'
    assert entry.comments[0].children[0].published == datetime.datetime(
        2008, 2, 4, 5, 47)


def test_586643():
    entry = _slurp_and_parse_entry('586643').entry

    assert entry.subject == 'Coming Out to Kids'
    assert entry.author == 'stephanie_live'
    assert entry.published == datetime.datetime(2008, 2, 10, 20, 30)
    assert entry.tags == ['kids', 'coming_out']

    assert not entry.comments


def test_738299():
    entry = _slurp_and_parse_entry('738299').entry

    assert entry.subject == 'Pissed off'
    assert entry.author == 'lisaburnham'
    assert entry.published == datetime.datetime(2010, 9, 25, 13, 13)

    assert _total_comments(entry) == 10
    assert entry.comments[2].children[1].deleted
    assert entry.comments[4].author == 'capybyra'

    assert not entry.tags


def _slurp_and_parse_entry(id: str) -> parse.EntryParseResult:
    return parse.parse_entry(slurp_test_data(id), None)


def _total_comments(entry: LiveJournalEntry) -> int:
    return reduce(lambda total, comment: total + _total_children(comment),
                  entry.comments, 0)


def _total_children(comment: LiveJournalComment) -> int:
    # Includes self!
    return reduce(lambda total, child: total + _total_children(child),
                  comment.children, 1)
