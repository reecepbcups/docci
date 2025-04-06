
import os
from dataclasses import dataclass
from logging import getLogger
from typing import List, Optional, Tuple

from src.config import Config


@dataclass
class FileOperations:
    file_name: Optional[str] = None
    content: str = ""
    insert_at_line: Optional[int] = None
    replace_lines: Optional[Tuple[int, Optional[int]]] = None
    file_reset: bool = False
    if_file_not_exists: str = ""

    def handle_file_content(self, config: Config) -> bool:
        if not self.file_name:
            return False

        file_path = os.path.join(config.working_dir, self.file_name) if config.working_dir else self.file_name

        if self._should_skip_execution(config, file_path):
            return False

        # Ensure content ends with newline for proper line operations
        content_with_newline = self.content if self.content.endswith('\n') else self.content + '\n'

        if not os.path.exists(file_path) or self.file_reset:

            msg = f"Refreshing file: {file_path}", "since file reset is on" if self.file_reset else ""
            getLogger(__name__).debug(msg)

            with open(file_path, 'w') as f:
                f.write(content_with_newline)

        # read and insert at the given line
        with open(file_path, 'r') as f:
            lines = f.readlines()

        if self.insert_at_line:
            # if insert at line is negative, then it is relative to the end of the file
            insert_line = self.insert_at_line if self.insert_at_line > 0 else len(lines) + self.insert_at_line + 1
            # Ensure we don't go out of bounds
            insert_line = max(0, min(insert_line, len(lines)))
            lines.insert(insert_line, content_with_newline)

        lines = self._replace_lines(lines, content_with_newline)

        with open(file_path, 'w') as f:
            f.write(''.join(lines))

        return True

    def _should_skip_execution(self, config: Config, file_path: str) -> bool:
        # Check if_file_not_exists condition
        if self.if_file_not_exists and os.path.exists(file_path):
            getLogger(__name__).debug(f"Skipping file operation since {file_path} exists and if_file_not_exists is set")
            return True
        return False

    def _replace_lines(self, lines: List[str], content: str) -> List[str]:
        if self.replace_lines:
            start, end = self.replace_lines
            # line based, not index :)
            start = start - 1 if start > 0 else 0
            end = end - 1 if end and end > 0 else None

            if end:
                if end >= len(lines):
                    end = len(lines)
                lines[start:end] = [content]
            else:
                if start >= len(lines):
                    lines.append(content)
                else:
                    lines[start] = content

        return lines
