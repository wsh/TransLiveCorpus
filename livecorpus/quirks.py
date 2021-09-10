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

from abc import ABCMeta, abstractmethod
from bs4 import BeautifulSoup
from bs4.element import Tag
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from dateutil import parser as dtparse
from enum import Enum
import re
import typing
from urllib import parse as urlparse


class SnowflakeError(Exception):
    pass


# ignore comment for mypy: https://github.com/python/mypy/issues/5374
@dataclass  # type: ignore[misc]
class Community(metaclass=ABCMeta):
    netloc: str

    @classmethod
    def __all_subclasses__(cls) -> typing.List['Community']:
        # TODO make this real
        return [FTM(), MTF(), Genderqueer(), Transgender()]

    @classmethod
    def from_netloc(cls, netloc: str) -> 'Community':
        communities: typing.List[Community] = cls.__all_subclasses__()
        result: typing.List[Community] = [
            c for c in communities if c.netloc == netloc
        ]
        if not result:
            raise SnowflakeError('Unknown community')
        return result[0]

    @abstractmethod
    def comment_content(self, comment: Tag) -> str:
        pass

    @abstractmethod
    def comment_published(self, comment: Tag) -> datetime:
        pass

    @abstractmethod
    def entry_content(self, tree: BeautifulSoup) -> str:
        pass

    @abstractmethod
    def entry_list_prev_link(self, tree: BeautifulSoup) -> typing.Optional[str]:
        pass

    @abstractmethod
    def entry_published(self, tree: BeautifulSoup) -> datetime:
        pass

    @abstractmethod
    def entry_username(self, tree: BeautifulSoup) -> str:
        pass

    @abstractmethod
    def is_comment_deleted(self, comment: Tag) -> bool:
        pass

    @abstractmethod
    def is_comment_zipped(self, comment: Tag) -> bool:
        pass

    def to_entry_url(self, id: str) -> str:
        return f'https://{self.netloc}.livejournal.com/{id}.html'


@dataclass
class FTM(Community):
    netloc: str = 'ftm'

    def comment_content(self, comment: Tag) -> str:
        return comment.select_one('.comment-text').text

    def comment_published(self, comment: Tag) -> datetime:
        return datetime.strptime(
            comment.select_one('.comment-permalink').text,
            '%Y-%m-%d %I:%M %p (UTC)')

    def entry_content(self, tree: BeautifulSoup) -> str:
        return tree.select_one('.entry-text .entry-content').text

    def entry_list_prev_link(self, tree: BeautifulSoup) -> typing.Optional[str]:
        ul = tree.find('ul', class_=re.compile('page-nav'))
        if not ul:
            return None
        link = ul.find('a', text='Next 10')
        return link['href'] if link else None

    def entry_published(self, tree: BeautifulSoup) -> datetime:
        return dtparse.parse(
            tree.select_one('.entry-text .entry-date abbr')['title'])

    def entry_username(self, tree) -> str:
        return tree.select_one('.entry-text .username b').text

    def is_comment_deleted(self, comment: Tag) -> bool:
        return 'deleted' in comment['class']

    def is_comment_zipped(self, comment: Tag) -> bool:
        return not comment.select_one('.comment-permalink')


@dataclass
class MTF(Community):
    netloc: str = 'mtf'

    def comment_content(self, comment: Tag) -> str:
        return comment.select('div')[1].text

    def comment_published(self, comment: Tag) -> datetime:
        return datetime.strptime(
            comment.find(title=re.compile('journal')).text,
            '%Y-%m-%d %I:%M %p (UTC)')

    def entry_content(self, tree: BeautifulSoup) -> str:
        st = tree.select('article.entry-content')
        if st:
            return st[0].text

        raw = tree.select_one('table.s2-entrytext tr:nth-child(2)').text
        return re.sub(rf'{self.netloc}\[\S+\]', '', raw, count=1)

    def entry_list_prev_link(self, tree: BeautifulSoup) -> typing.Optional[str]:
        el = tree.find("a", href=True, text="earlier")
        return el['href'] if el else None

    def entry_published(self, tree: BeautifulSoup) -> datetime:
        st = tree.select('article time')
        if st:
            return dtparse.parse(st[0].text)

        contents = tree.select_one('table.s2-entrytext td.index').contents
        raw = "%s %s" % (contents[0], contents[1])
        raw = re.sub(r'\<\/?b\>', '', raw)
        return dtparse.parse(re.sub(r'\[|\|', '', raw))

    def entry_username(self, tree: BeautifulSoup) -> str:
        st = tree.select('article dl.author dt')
        if st:
            return st[0]['lj:user']

        return tree.select('table.s2-entrytext td font')[1].text

    def is_comment_deleted(self, comment: Tag) -> bool:
        return ((not comment.has_attr('class') or
                 'ljcmt_full' not in comment['class']) and
                comment.text == '(Deleted comment)') or bool(
                    comment.select('.b-leaf-deleted'))

    def is_comment_zipped(self, comment: Tag) -> bool:
        return (not comment.has_attr('class') or
                'ljcmt_full' not in comment['class'])


@dataclass
class Genderqueer(MTF):
    netloc: str = 'genderqueer'

    def to_entry_url(self, id: str) -> str:
        return f'https://{self.netloc}.livejournal.com/{id}.html?nojs=1'

    def comment_content(self, comment: Tag) -> str:
        return comment.select_one('.b-leaf-article').text

    def comment_published(self, comment: Tag) -> datetime:
        ts = comment.select_one('div.comment[data-updated-ts]')
        if ts:
            return datetime.fromtimestamp(int(ts['data-updated-ts']))
        raise SnowflakeError(f'no timestamp: {comment}')

    def is_comment_zipped(self, comment: Tag) -> bool:
        return bool(comment.select('.b-leaf-collapsed'))


@dataclass
class Transgender(Genderqueer):
    netloc: str = 'transgender'

    def entry_list_prev_link(self, tree: BeautifulSoup) -> typing.Optional[str]:
        el = tree.select_one('.j-page-nav-item-prev a[href]')
        return el['href'] if el else None


def find_community(html: Tag) -> Community:
    self_url = html.select_one('meta[property="og:url"]')['content']
    parsed = urlparse.urlparse(self_url)
    return Community.from_netloc(parsed.netloc.split(".")[0])
