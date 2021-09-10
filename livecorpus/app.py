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

from flask import Flask, request
import re
from urllib import parse as urlparse
import traceback

from . import fetch, parse, quirks, store, task_queue

app = Flask(__name__)

try:
    import os
    # if os.environ.get('NODE_ENV') == 'production':
    import googleclouddebugger
    googleclouddebugger.enable()
except ImportError:
    pass

try:
    import googlecloudprofiler
    googlecloudprofiler.start(verbose=1)
except (ValueError, NotImplementedError) as exc:
    print(exc)  # Handle errors here


@app.route('/')
def hello():
    return 'Hello from livecorpus!'


# Cloud Tasks uses this API to schedule parsing tasks. Though the payloads we
# supply to it are base64-encoded, they're automatically *decoded* by the time
# they make it here, so this looks like a "normal" REST API.
# TODO(wsh): implement authentication, first locking down to Tasks then manual?


@app.route('/scrape_entry_list', methods=['POST'])
def scrape_entry_list():
    url = request.get_data(as_text=True)
    raw_entry_list = fetch.fetch_text(url)
    parsed_entry_list = parse.parse_entry_list(raw_entry_list)
    task_queue.enqueue_entries(parsed_entry_list.entry_links)
    if parsed_entry_list.prev_link:
        task_queue.enqueue_entry_list(parsed_entry_list.prev_link)
    else:
        _handle_missing_prev_link(url)
    return "OK"


@app.route('/scrape_entry', methods=['POST'])
def scrape_entry():
    url = request.get_data(as_text=True)
    parsed_url = urlparse.urlparse(url)
    community = parsed_url.netloc
    qs = urlparse.parse_qs(parsed_url.query)
    if 'thread' in qs:
        reparse_root = qs['thread'][0]
    else:
        reparse_root = None
    store_comments_only = 'thread' in qs or 'page' in qs
    id = re.fullmatch(r'\/(\d+)\.html', parsed_url.path).group(1)
    raw_entry = fetch.fetch_text(url)
    try:
        parsed_entry = parse.parse_entry(raw_entry, reparse_root)
        if 'thread' in qs and qs['thread'][0] in parsed_entry.threads:
            # TODO: descend from top until (expand)?
            raise quirks.SnowflakeError('zipped again!')
        store.store_entry(community, id, parsed_entry.entry,
                          store_comments_only)
        thread_urls = [
            urlparse.urljoin(url, '?thread=%s' % thread)
            for thread in parsed_entry.threads
        ]
        task_queue.enqueue_entries(thread_urls)
        next_page = parsed_entry.next_page
        if next_page:
            task_queue.enqueue_entries([next_page])
    except Exception as e:
        # TODO punt to dead letter queue, include counter for retries for transient issues
        print("Scrape failed: community %s, entry %s\nURL %s" %
              (community, id, url))
        print(e)
        task_queue.enqueue_entry_dead_letter(community, id, url)
    finally:
        return "OK"


def _handle_missing_prev_link(url: str) -> None:
    parsed_url = urlparse.urlparse(url)
    qs = urlparse.parse_qs(parsed_url.query)
    print("Missing prev link for %s" % url)


if __name__ == '__main__':
    # Only for local development.
    app.run(host='0.0.0.0', port=8080, debug=True)
