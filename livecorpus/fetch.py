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

from requests import Session
from requests.adapters import HTTPAdapter

headers = {
    # FIXME: insert your user agent here
    'User-Agent': 'Trans Corpus Project Crawler; <your email address here>',
    'Accept-Encoding': 'deflate, gzip;q=1.0, *;q=0.5'
}

session = Session()
session.mount('https://ftm.livejournal.com', HTTPAdapter(max_retries=5))
session.mount('https://mtf.livejournal.com', HTTPAdapter(max_retries=5))
session.mount('https://genderqueer.livejournal.com', HTTPAdapter(max_retries=5))
session.mount('https://transgender.livejournal.com', HTTPAdapter(max_retries=5))
session.headers.update(headers)


def fetch_text(url: str) -> str:
    return session.get(url, cookies={'adult_explicit': '1'}).text
