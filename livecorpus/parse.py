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

from bs4 import BeautifulSoup, element
from dataclasses import dataclass
from datetime import datetime
from dateutil import parser as dtparse
import re
import tinycss2
from typing import Dict, List, Optional, Set, Tuple
from urllib import parse as urlparse

from . import quirks
from .model import LiveJournalComment, LiveJournalEntry
from .quirks import SnowflakeError


@dataclass
class EntryListParseResult:
    entry_links: Set[str]
    prev_link: Optional[str] = None


@dataclass
class EntryParseResult:
    entry: LiveJournalEntry
    threads: Set[str]
    next_page: Optional[str]


def parse_entry_list(raw_entry_list: str) -> EntryListParseResult:
    tree = BeautifulSoup(raw_entry_list, 'lxml')
    community = quirks.find_community(tree)
    entry_link_pattern = re.compile(
        rf'^https\://{community.netloc}.livejournal.com/(\d+).html')
    links = set(
        community.to_entry_url(
            re.match(entry_link_pattern, a['href']).group(1))
        for a in tree.find_all('a', href=entry_link_pattern))
    maybe_prev_link = community.entry_list_prev_link(tree)
    return EntryListParseResult(links, maybe_prev_link)


def parse_entry(raw_entry_text: str,
                reparse_root: Optional[str]) -> EntryParseResult:
    tree = BeautifulSoup(raw_entry_text, 'lxml')
    community = quirks.find_community(tree)

    subject = tree.select_one('meta[property="og:title"]')['content']

    published = community.entry_published(tree)
    # TODO: perhaps edited when available?

    username = community.entry_username(tree)
    content = community.entry_content(tree)
    tags = [t['content'] for t in tree.select('meta[property="article:tag"]')]

    root_comments, threads = _parse_entry_comments(tree, community,
                                                   reparse_root)
    next_page = _search_next_comment_page(tree)
    comments = filter(lambda r: r.id not in threads, root_comments)

    ent = LiveJournalEntry(published, username, subject, content,
                           list(comments), tags)

    return EntryParseResult(ent, threads, next_page)


def _search_next_comment_page(entry_tree: element.Tag) -> Optional[str]:
    next_page = entry_tree.select_one('.comments-pages-next a')
    if next_page:
        return next_page['href']
    else:
        return None


def _parse_entry_comments(
    entry_tree: element.Tag, community: quirks.Community,
    reparse_root: Optional[str]
) -> Tuple[List[LiveJournalComment], Set[str]]:

    comment_wraps = entry_tree.find_all(id=re.compile('ljcmt*'))
    if not comment_wraps:
        comment_wraps = entry_tree.select('article .b-tree-twig')
    if not comment_wraps:
        # No comments, at least that we know of.
        return [], set()
    # TODO: should we just *always* use the thread page view of comments
    # might simplify parsing logic
    # TODO: handle too many (paging?)
    parsed: Dict[str, LiveJournalComment] = dict()
    roots: List[LiveJournalComment] = list()
    threads: Set[str] = set()
    for comment in comment_wraps:
        if comment.has_attr('data-tid'):
            id = comment['data-tid'][1:]  # t...
            if not id:
                # surprising hidden stuff
                foo = comment.find_all(class_=re.compile('b-leaf-seemore'),
                                       attrs={'data-parent': True})
                if not foo:
                    raise SnowflakeError('fart')
                threads.add(foo[0]['data-parent'])
                continue
        elif comment.has_attr('id'):
            id = comment['id'][5:]  # ljcmt...
        else:
            raise SnowflakeError('poop')

        if community.is_comment_deleted(comment):
            # TODO: No reparse root: are we missing threads whose original post has been deleted?
            _parse_deleted_comment(id, community, comment, roots, parsed)
        else:
            _parse_live_comment(id, community, comment, roots, parsed, threads,
                                reparse_root)
    return roots, threads


def _parse_live_comment(id: str, community: quirks.Community,
                        comment: element.Tag, roots: List[LiveJournalComment],
                        parsed: Dict[str, LiveJournalComment],
                        threads: Set[str], reparse_root: Optional[str]) -> None:
    if community.is_comment_zipped(comment):
        # Happens when comments are hidden (i.e. deep nesting).
        zipped = LiveJournalComment.zipped(id)
        thread_id = id
        parsed[id] = zipped
        parent_id = _search_parent(community, comment)
        if parent_id:  # If not present, this may be a root.
            parent = parsed[parent_id]
            zipped.set_parent(parent)
            while parent:
                thread_id = parent.id
                if thread_id in threads:
                    # We've already marked this for reparsing.
                    return
                parent = parent.parent
            # thread_id should be a *root*.
            root_ids = [r.id for r in roots]
            if thread_id not in root_ids:
                raise SnowflakeError('thread_id was not root: %s' % thread_id)
            if reparse_root and reparse_root == thread_id:
                # We were here to parse this page, anyway. Unfortunate zipped-zipped scenario.
                # To resolve, we enqueue the immediate parent rather than the zipped.
                thread_id = parent_id
        threads.add(thread_id)
        return

    published = community.comment_published(comment)
    probable_author = comment.select_one('.i-ljuser-username b')
    if probable_author:
        author = probable_author.text
    else:
        author = '(Anonymous)'
    content = community.comment_content(comment)
    modeled = LiveJournalComment.live(id, published, author, content)
    parsed[id] = modeled
    if reparse_root and reparse_root == id:
        # if we try to look up the parent, we'll blow up
        roots.append(modeled)
        return
    # look for a parent if present
    parent_id = _search_parent(community, comment)
    if parent_id:
        if parent_id not in parsed:
            print(f'{id}, {parent_id}, {parsed}')
        parent_model = parsed[parent_id]
        parent_model.add_child(modeled)
        modeled.set_parent(parent_model)
    else:
        roots.append(modeled)


def _parse_deleted_comment(id: str, community: quirks.Community,
                           comment: element.Tag, roots: list,
                           parsed: dict) -> None:
    modeled = LiveJournalComment.dead(id)
    parsed[id] = modeled
    parent_id = _search_parent(community, comment)

    if parent_id:
        parent = parsed[parent_id]
        if not parent:
            raise SnowflakeError(
                'We got an invalid parent (%s) for comment %s' %
                (parent_id, id))
        parent.add_child(modeled)
        modeled.set_parent(parent)
    else:
        # If we don't have a parent, this must be a root.
        roots.append(modeled)


def _search_parent(community: quirks.Community,
                   comment: element.Tag) -> Optional[str]:
    # This first method only works for "live" comments, and it should
    # *always* work for them. (Spoiler alert: it doesn't for genderqueer.)
    from_href = _parent_id_from_href(community, comment)
    if from_href:
        return from_href

    indent = _comment_indent_from_style(comment)

    if indent == 0:
        # This is a root, so it has no parent.
        return None

    def is_comment(tag: element.Tag) -> bool:
        return tag.name == 'div' and (
            (tag.has_attr('id') and bool(re.match('ljcmt*', tag['id']))) or
            (tag.has_attr('class') and 'b-tree-twig' in tag['class']))

    # try two divs before
    # TODO: this varies by template
    # previous = comment.previous_sibling

    previous_siblings = [p for p in comment.previous_siblings if is_comment(p)]

    # if previous and not is_comment(previous):
    #     previous = previous.previous_sibling

    if not previous_siblings:
        raise SnowflakeError('no previous siblings found')

    previous = previous_siblings.pop(0)

    if not previous or not is_comment(previous):
        # We found something, but it's not a comment.
        # double-dead *should* already be handled
        raise SnowflakeError('previous sibling was a non-comment: %s' %
                             previous)

    previous_indent = _comment_indent_from_style(previous)
    while previous_indent > indent:
        # The previous comment was a subcomment of another thread.
        # TODO: varies by template
        previous = previous_siblings.pop(0)

        if not previous or not is_comment(previous):
            previous = previous_siblings.pop(0)

        if not previous:
            raise SnowflakeError(
                'ran out of retries looking for parent for %s' % comment)

        if not is_comment(previous):
            # We don't know what's going on.
            raise SnowflakeError('previous sibling was a non-comment')

        previous_indent = _comment_indent_from_style(previous)

    if previous_indent == indent:
        # This comment is at the same level as the one before it,
        # so they presumably have the same parent.
        previous_parent_id = _search_parent(community, previous)
        if not previous_parent_id:
            # We always expect the previous comment to have a parent,
            # unless it's a root, in which case either:
            # *this* is a parent, which should have been caught with
            # the indent == 0 check above, *or* it's our parent (see
            # logic below)
            raise SnowflakeError('Expected a previous parent, none found')
        return previous_parent_id
    elif previous_indent == indent - 25 or previous_indent == indent - 30:
        # the previous element *is* our parent
        # the deleted comment is the first reply
        # TODO: FIX THIS
        if previous.has_attr('data-tid'):
            tid = re.match(r't(\d+)', previous['data-tid'])
            return tid.group(1)  # t...
        else:
            return previous['id'][5:]  # ljcmt...
    else:
        print(f'indent: {indent}, previous_indent: {previous_indent}')
        raise SnowflakeError('Could not find parent for %s' % comment)


def _parent_id_from_href(community: quirks.Community,
                         comment: element.Tag) -> Optional[str]:
    parent = [
        a for a in comment.select('a[href]') if a.text == 'Parent' and
        re.match(f'http[s]*://{community.netloc}.livejournal.com', a['href'])
    ]
    if parent:
        if not len(parent) == 1:
            raise SnowflakeError('Multiple parents?!')
        return _comment_id_from_url(parent[0]['href'])
    else:
        return None


def _comment_id_from_url(url: str) -> str:
    parsed_url = urlparse.urlparse(url)
    return parsed_url.fragment[1:]  # t...


def _comment_indent_from_style(comment: element.Tag) -> int:
    for declaration in tinycss2.parse_declaration_list(comment['style']):
        if declaration.name == 'margin-left':
            for token in declaration.value:
                if token.type == 'dimension':
                    return token.int_value

    raise SnowflakeError('Could not determine indent: %s' % comment)
