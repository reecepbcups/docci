from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


# from uname --operating-system
class MachineOS(Enum):
    LINUX = 'linux'
    WINDOWS = 'windows'
    MACOS = 'macos'

    def __str__(self):
        return self.value

    def __call__(self):
        return self.value

    @staticmethod
    def from_str(os: str) -> 'MachineOS':
        return MachineOS(os)

class Tags(Enum):
    TAGS_PREFIX = 'docci-'

    IGNORE = 'docci-ignore'
    BACKGROUND = 'docci-background'
    POST_DELAY = 'docci-delay-after'
    CMD_DELAY = 'docci-delay-per-cmd'
    HTTP_POLLING = 'docci-wait-for-endpoint'
    IGNORE_IF_INSTALLED = 'docci-if-not-installed'
    OUTPUT_CONTAINS = 'docci-output-contains'
    ASSERT_FAILURE = 'docci-assert-failure'
    MACHINE_OS = "docci-machine-os"

    # file related
    TITLE = 'title' # maybe we also alias with a docci-title or -filename or something?
    INSERT_AT_LINE = 'docci-line-insert'
    REPLACE_AT_LINE= 'docci-line-replace' # docci-line-replace=2-4 or docci-line-replace=2 works
    RESET_FILE = 'docci-reset-file'

    def __str__(self):
        return self.value

    def __call__(self):
        return self.value

    @staticmethod
    def from_str(tag: str) -> 'Tags':
        return Tags(tag)

    @staticmethod
    def is_valid(tag: str) -> bool:
        for member in Tags:
            if '=' in tag:
                tag = tag.split('=')[0]
            if member.value == tag:
                return True
        return False

    # validate an array of tags
    @staticmethod
    def validate(tags: list[str]) -> Tuple[bool, str | None]:
        for tag in tags:
            if not tag.startswith(Tags.TAGS_PREFIX()): continue
            if not Tags.is_valid(tag):
                print(tags, tag)
                return False, tag
        return True, None

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
