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

from dataclasses import dataclass, field
import datetime
from functools import reduce
from typing import List, Optional


@dataclass
class LiveJournalEntry:
    published: datetime.datetime
    author: str
    subject: str
    content: str
    comments: List['LiveJournalComment']
    tags: List[str]

    def __repr__(self) -> str:
        rep = "Entry: '%s' by %s, published %s\n" % (self.subject, self.author,
                                                     self.published)
        comments = reduce(lambda x, y: x + str(y), self.comments, "")
        # This is hacky, but it obviates a second traversal.
        num_comments = comments.count("\n")
        rep += "%s comments total" % num_comments
        rep += comments
        rep += f"\nTags: {self.tags}"
        return rep


@dataclass
class LiveJournalComment:
    id: str
    deleted: bool
    published: Optional[datetime.datetime] = None
    author: Optional[str] = None
    content: Optional[str] = None
    # TODO: subject: Optional[str] = None

    children: List['LiveJournalComment'] = field(default_factory=list)
    parent: Optional['LiveJournalComment'] = None

    def __repr__(self) -> str:
        return reduce(lambda x, y: "%s\n%s" % (x, y), self._repr_helper(1), "")

    def _repr_helper(self, indent: int) -> List[str]:
        rep = '* ' * indent
        if self.deleted:
            rep += "(deleted)"
        else:
            rep += "%s on %s" % (self.author, self.published)
        result = [rep]
        for child in self.children:
            result.extend(child._repr_helper(indent + 1))
        return result

    @classmethod
    def live(cls, id: str, published: datetime.datetime, author: str,
             content: str) -> 'LiveJournalComment':
        return cls(id, False, published, author, content)

    @classmethod
    def dead(cls, id: str) -> 'LiveJournalComment':
        return cls(id, True)

    @classmethod
    def zipped(cls, id: str) -> 'LiveJournalComment':
        return cls(id, False)

    def add_child(self, child: 'LiveJournalComment') -> None:
        # Either of these indicates a bug in the parser.
        if child.id == self.id:
            raise Exception('Comment %s: cannot add self as child' % child.id)
        if child in self.children:
            raise Exception('Comment %s: attempt to add duplicate child %s',
                            self.id, child.id)

        self.children.append(child)

    def set_parent(self, parent: 'LiveJournalComment') -> None:
        if parent.id == self.id:
            raise Exception('Comment %s: cannot add self as parent' % parent.id)

        self.parent = parent
