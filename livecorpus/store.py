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

from google.cloud import exceptions, firestore
from typing import Optional

from .model import LiveJournalComment, LiveJournalEntry

db = firestore.Client(project='trans-corpus')


def store_entry(community: str, id: str, entry: LiveJournalEntry,
                comments_only: bool) -> None:
    docref = db.collection(community).document(id)

    if not comments_only:
        doc = {
            'published': entry.published,
            'author': entry.author,
            'subject': entry.subject,
            'content': entry.content,
            'tags': entry.tags
        }
        docref.set(doc)

    comments_collection = docref.collection('Comments')
    for comment in entry.comments:
        store_comment(comment, comments_collection, comments_only)


# store_comment takes comments_only for the zipped-zipped case, in which we
# re-store the parent comment


def store_comment(comment: LiveJournalComment,
                  collection: firestore.CollectionReference,
                  comments_only: bool,
                  parent: Optional[firestore.DocumentReference] = None) -> None:
    # The parent property is a little surprising. Its use is only
    # so that we can reconstruct the comment *tree* without having to
    # store the comments hierarchically (which would suck for threads
    # with lots of replies).
    docref = collection.document(comment.id)
    if comment.deleted:
        doc = {'deleted': True}
    else:
        doc = {
            'published': comment.published,
            'author': comment.author,
            'content': comment.content
        }
    if comments_only and not parent:
        try:
            snapshot = docref.get(['parent'])
            if snapshot.exists:
                # Don't overwrite a parent if we already have one.
                doc['parent'] = snapshot.get('parent')
            else:
                doc['parent'] = parent
        except exceptions.NotFound:
            doc['parent'] = parent
    else:
        doc['parent'] = parent
    docref.set(doc)
    for subcomment in comment.children:
        store_comment(subcomment, collection, comments_only, docref)
