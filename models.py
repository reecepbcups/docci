
from enum import Enum


class Tags(Enum):
    IGNORE = 'docs-ci-ignore'
    BACKGROUND = 'docs-ci-background'
    POST_DELAY = 'docs-ci-post-delay'
    CMD_DELAY = 'docs-ci-cmd-delay'

    def __str__(self):
        return self.value

    def __call__(self):
        return self.value
