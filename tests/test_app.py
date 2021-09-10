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

import pytest
from unittest import mock

from .context import livecorpus, slurp_test_data
from livecorpus.app import app


@pytest.fixture
def client():
    app.testing = True
    return app.test_client()


def test_hello(client):
    resp = client.get('/')
    assert resp.get_data() == b'Hello from livecorpus!'


fetch_text = mock.MagicMock(name='fetch_text')
enqueue_entries = mock.MagicMock(name='enqueue_entries')

parse_entry_list = mock.MagicMock(name='parse_entry_list')
enqueue_entry_list = mock.MagicMock(name='enqueue_entry_list')


@mock.patch('livecorpus.fetch.fetch_text', fetch_text)
@mock.patch('livecorpus.parse.parse_entry_list', parse_entry_list)
@mock.patch('livecorpus.task_queue.enqueue_entries', enqueue_entries)
@mock.patch('livecorpus.task_queue.enqueue_entry_list', enqueue_entry_list)
def test_scrape_entry_list(client):
    fetch_text.return_value = 'fetched_text'
    parse_entry_list.return_value.entry_links = ['http://entry.link']
    parse_entry_list.return_value.prev_link = 'http://prev.link'

    url = 'http://entry.list'
    client.post('/scrape_entry_list', data=url)
    fetch_text.assert_called_once_with(url)
    # This is crappy, effectively testing mock wiring, but it's > 0.
    parse_entry_list.assert_called_once_with('fetched_text')
    enqueue_entries.assert_called_once_with(['http://entry.link'])
    enqueue_entry_list.assert_called_once_with('http://prev.link')


store_entry = mock.MagicMock(name='store_entry')


@mock.patch('livecorpus.fetch.fetch_text', fetch_text)
@mock.patch('livecorpus.store.store_entry', store_entry)
@mock.patch('livecorpus.task_queue.enqueue_entries', enqueue_entries)
def test_scrape_entry(client):
    enqueue_entries.reset_mock()
    fetch_text.return_value = slurp_test_data(7232256)

    client.post('/scrape_entry',
                data='https://ftm.livejournal.com/7232256.html')
    args, _ = store_entry.call_args
    assert args[0] == 'ftm.livejournal.com'
    assert args[1] == '7232256'
    assert args[2].author == 'bixligat'
    assert not args[3]  # comments_only

    expected_threads = {
        '88040448', '88040960', '88041984', '88042240', '88043264', '88043520',
        '88044800', '88045056', '88045568', '88046592'
    }
    thread_urls = [
        'https://ftm.livejournal.com/7232256.html?thread=%s' % thread
        for thread in expected_threads
    ]
    calls = enqueue_entries.call_args_list
    assert calls[0][0][0] == thread_urls
    assert calls[1][0][0] == [
        'https://ftm.livejournal.com/7232256.html?page=2#comments'
    ]


@mock.patch('livecorpus.fetch.fetch_text', fetch_text)
@mock.patch('livecorpus.store.store_entry', store_entry)
@mock.patch('livecorpus.task_queue.enqueue_entries', enqueue_entries)
def test_scrape_entry_thread(client):
    enqueue_entries.reset_mock()

    fetch_text.return_value = slurp_test_data('7232256-88040960')

    client.post('/scrape_entry',
                data='https://ftm.livejournal.com/7232256.html?thread=88040960')
    args, _ = store_entry.call_args
    assert len(args[2].comments) == 1  # 1 root
    assert args[3]  # comments_only

    # our dumbass equivalent of assert_not_called
    assert len(enqueue_entries.mock_calls) == 1
    assert enqueue_entries.call_args[0] == ([],)
    assert enqueue_entries.call_args[1] == {}


@mock.patch('livecorpus.fetch.fetch_text', fetch_text)
@mock.patch('livecorpus.store.store_entry', store_entry)
@mock.patch('livecorpus.task_queue.enqueue_entries', enqueue_entries)
def test_scrape_entry_second_page_comments(client):
    enqueue_entries.reset_mock()

    fetch_text.return_value = slurp_test_data('7232256-2')

    client.post('/scrape_entry',
                data='https://ftm.livejournal.com/7232256.html?page=2#comments')
    args, _ = store_entry.call_args
    assert len(args[2].comments) == 3  # 1 root
    assert args[3]  # comments_only

    # our dumbass equivalent of assert_not_called
    assert len(enqueue_entries.mock_calls) == 1
    assert enqueue_entries.call_args[0] == ([],)
    assert enqueue_entries.call_args[1] == {}
