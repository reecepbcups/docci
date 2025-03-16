from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Tags(Enum):
    IGNORE = 'docs-ci-ignore'
    BACKGROUND = 'docs-ci-background'
    POST_DELAY = 'docs-ci-delay-after'
    CMD_DELAY = 'docs-ci-delay-per-cmd'
    HTTP_POLLING = 'docs-ci-wait-for-endpoint'
    IGNORE_IF_INSTALLED = 'docs-ci-if-not-installed'

    # file related
    FILE_NAME = 'title' # maybe we also alias with a docs-ci-title or -filename or something?
    INSERT_AT_LINE = 'docs-ci-insert-at-line'

    def __str__(self):
        return self.value

    def __call__(self):
        return self.value

@dataclass
class Endpoint:
    url: str
    max_timeout: int

def handle_http_polling_input(input: str | None) -> Optional[Endpoint]:
    '''
    Parse the input for the HTTP_POLLING tag.
    The input should be in the format of `http://localhost:44881|30`.
        - The first part is the endpoint URL.
        - (optional) The second part is the maximum timeout in seconds.
    '''
    if input is None: return None

    if '|' in input:
        endpoint, timeout = input.split('|')
    else:
        endpoint = input
        timeout = 30
    return Endpoint(url=endpoint, max_timeout=int(timeout))
