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

from google.cloud import firestore, tasks_v2

import base64
import google.api_core.exceptions
import hashlib
import requests
import typing

db = firestore.Client(project='trans-corpus')
tq = tasks_v2.CloudTasksClient()


def enqueue_entries(links: typing.List[str]) -> None:
    for entry in links:
        _enqueue_app_engine('/scrape_entry', 'livejournal-entries', entry)


def enqueue_entry_list(link: str) -> None:
    _enqueue_app_engine('/scrape_entry_list', 'livejournal-entry-lists', link)


def _enqueue_app_engine(handler: str, queue_name: str, url: str) -> None:
    queue_full_name = tq.queue_path("trans-corpus", "us-central1", queue_name)
    task_name = '{}/tasks/{}'.format(queue_full_name, _generate_task_name(url))
    task = {
        'name': task_name,  # Prevents duplication. see _generate_task_name
        'app_engine_http_request': {
            'relative_uri': handler,
            'body': url.encode()
        }
    }

    try:
        tq.create_task(queue_full_name, task)
    except google.api_core.exceptions.Conflict as _:
        # failed because of dedupe, "intentional"
        print("queue: %s, url: %s failed for dedupe" % (queue_name, url))
        pass


def enqueue_entry_dead_letter(community: str, id: str, url: str) -> None:
    # TODO: easy deletes because docs should be docs not collections
    db.collection("DeadLetter").document(community).collection(
        id).document().set({
            'time': firestore.SERVER_TIMESTAMP,
            'url': url
        })


def _generate_task_name(url: str) -> str:
    # Use a hash to avoid hotspotting Tasks.
    hash = hashlib.sha1()
    # Cloud Tasks continues to reject tasks with the same names as existing ones
    # for some time after the originals are deleted--so in order to rerun after an
    # unrecoverable failure (e.g. a parser bug) within that period, we increment `epoch` below.
    epoch = b'1'
    hash.update(epoch)
    hash.update(url.encode('utf-8'))
    # Encode as hex to guarantee a legal task name.
    return hash.hexdigest()
