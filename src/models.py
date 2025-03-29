import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Generator, Optional, Tuple

import requests


@dataclass
class Endpoint:
    url: str
    max_timeout: int

    @staticmethod
    def handle_http_polling_input(input: str | None) -> Optional["Endpoint"]:
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

    def poll(self, poll_speed: float = 1.0) -> Generator[Tuple[bool, str], None, None]:
        start_time = time.time()
        attempt = 1
        url = self.url
        while True:
            try:
                requests.get(url)
                yield True, f"Success: endpoint is up: {url}"
                break
            except requests.exceptions.RequestException:
                if time.time() - start_time > self.max_timeout: # half second buffer
                    break
                yield False, f"Error: endpoint not up yet: {url}, trying again. Try number: {attempt}"
                time.sleep(poll_speed)
            attempt += 1

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
    MACHINE_OS = "docci-os"

    # file related
    IF_FILE_DOES_NOT_EXISTS = "docci-if-file-not-exists"
    FILE_NAME = 'docci-file'
    INSERT_AT_LINE = 'docci-line-insert'
    REPLACE_AT_LINE= 'docci-line-replace' # docci-line-replace=2-4 or docci-line-replace=2 works
    RESET_FILE = 'docci-reset-file'

    def __str__(self):
        return self.value

    def __call__(self):
        return self.value

    # Map of aliases to canonical tags
    @staticmethod
    def get_aliases() -> Dict[str, 'Tags']:
        return {
            'docci-contains-output': Tags.OUTPUT_CONTAINS,
            'docci-expected-output': Tags.OUTPUT_CONTAINS,
            'docci-contains': Tags.OUTPUT_CONTAINS,
            'docci-after-delay': Tags.POST_DELAY,
            'docci-cmd-delay': Tags.CMD_DELAY,
            'docci-expect-failure': Tags.ASSERT_FAILURE,
            'docci-should-fail': Tags.ASSERT_FAILURE,
            'docci-machine': Tags.MACHINE_OS,
            'docci-bg': Tags.BACKGROUND,
            # file related
            'docci-file-name': Tags.FILE_NAME,
            'docci-insert-at-line': Tags.INSERT_AT_LINE,
            'docci-replace-at-line': Tags.REPLACE_AT_LINE,
            'docci-insert-line': Tags.INSERT_AT_LINE,
            'docci-replace-line': Tags.REPLACE_AT_LINE,
        }

    @staticmethod
    def get_all_tags() -> list[str]:
        output = []
        for tag in Tags:
            if tag == Tags.TAGS_PREFIX: continue
            output.append(tag.value)
        return output

    @staticmethod
    def list_tags_with_aliases() -> Dict[str, list[str]]:
        """
        Returns a dictionary mapping each canonical tag to a list of its aliases.
        The canonical tag itself is included as the first item in each list.
        """
        result = {tag.value: [tag.value] for tag in Tags}

        # Add aliases to their respective canonical tags
        aliases = Tags.get_aliases()
        for alias, canonical_tag in aliases.items():
            result[canonical_tag.value].append(alias)

        return result

    @staticmethod
    def print_tags_with_aliases():
        """
        Prints all tags and their aliases in a readable format.
        """
        tag_mapping = Tags.list_tags_with_aliases()

        print("Tags and their aliases:")
        print("=======================")

        for canonical, aliases in tag_mapping.items():
            if canonical == Tags.TAGS_PREFIX.value: continue

            if len(aliases) > 1:
                print(f"- {canonical} (Aliases: {', '.join(aliases[1:])})")
            else:
                print(f"- {canonical}")

    @staticmethod
    def extract_tag_value(tags, tag_type, default=None, converter=None):
        """
        Extract value from a tag of format 'tag_type=value' or 'tag_type="value with spaces"'
        Also supports aliases for tag_type and handles escaped quotes.
        """
        matching_tags = []

        # Get all possible tag variants (canonical + aliases)
        possible_tags = [tag_type]

        # Add aliases for this tag type
        tag_enum = None
        for tag in Tags:
            if tag.value == tag_type:
                tag_enum = tag
                break

        if tag_enum:
            aliases = Tags.get_aliases()
            possible_tags.extend([alias for alias, canonical in aliases.items() if canonical == tag_enum])

        # Check for any matching tag
        for tag in tags:
            for possible_tag in possible_tags:
                if tag.startswith(f"{possible_tag}="):
                    # Find the position of the equals sign
                    equals_pos = tag.find('=')
                    if equals_pos != -1:
                        # Get everything after the equals sign
                        value = tag[equals_pos + 1:]

                        # Check if the value starts with a quote
                        if value and (value[0] == '"' or value[0] == "'"):
                            quote_char = value[0]
                            value = value[1:]  # Remove opening quote

                            # Process the value character by character
                            processed_value = []
                            i = 0
                            while i < len(value):
                                if value[i] == '\\' and i + 1 < len(value):
                                    # Handle escaped characters
                                    if value[i + 1] == quote_char:
                                        processed_value.append(quote_char)
                                        i += 2  # Skip both the backslash and the quote
                                        continue
                                    elif value[i + 1] == '\\':
                                        processed_value.append('\\')
                                        i += 2  # Skip both backslashes
                                        continue
                                elif value[i] == quote_char:
                                    # Found unescaped closing quote
                                    break
                                processed_value.append(value[i])
                                i += 1

                            value = ''.join(processed_value)

                        matching_tags.append(value)
                        break  # Found a match, no need to check other possible tags

        if not matching_tags:
            return default

        value = matching_tags[0]
        return converter(value) if converter else value

    @staticmethod
    def from_str(tag: str) -> 'Tags':
        aliases = Tags.get_aliases()
        if tag in aliases:
            return aliases[tag]
        return Tags(tag)

    @staticmethod
    def is_valid(tag: str) -> bool:
        # Strip parameter part if present
        if '=' in tag:
            tag = tag.split('=')[0]

        # Check if it's a canonical tag
        for member in Tags:
            if member.value == tag:
                return True

        return tag in Tags.get_aliases()

    @staticmethod
    def has_tag(tags: list[str], tag: 'Tags') -> bool:
        """
        Checks if the specified tag or any of its aliases are present in the tags list.
        """
        # Get the canonical tag value
        canonical_value = tag.value

        # Check if the canonical tag is in the list
        if canonical_value in tags:
            return True

        # Get all aliases for this tag
        aliases = Tags.get_aliases()
        alias_values = [alias for alias, canonical in aliases.items() if canonical == tag]

        # Check if any alias is in the list
        return any(alias in tags for alias in alias_values)

    @staticmethod
    def validate(tags: list[str]) -> Tuple[bool, str | None]:
        for tag in tags:
            if not tag.startswith(Tags.TAGS_PREFIX()): continue
            if not Tags.is_valid(tag):
                print(tags, tag)
                return False, tag
        return True, None

def alias_operating_systems(os: str) -> str:
    '''
    Aliases the operating systems to a common name.
    '''
    if os.lower() in ['ubuntu', 'debian', 'wsl']:
        return 'linux'
    elif os.lower() in ['macos', 'mac']:
        return 'darwin'
    return os.lower()
