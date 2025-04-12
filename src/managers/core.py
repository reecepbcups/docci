from dataclasses import dataclass
from logging import getLogger
from typing import List, Optional

from src.config import Config
from src.managers.cmd import CommandExecutor
from src.managers.delay import DelayManager
from src.managers.file_operations import FileOperations
from src.models import Endpoint


@dataclass
class CodeBlockCore:
    language: str
    tags: List[str]
    content: str
    ignored: bool
    delay_manager: DelayManager
    file_ops: Optional[FileOperations] = None
    command_executor: Optional[CommandExecutor] = None
    endpoint: Optional[Endpoint] = None

    def run_commands(self, config: Config) -> str:
        if self.endpoint:
            getLogger(__name__).debug(f"Waiting for endpoint: {self.endpoint}")
            lastRes = (False, "")
            for res in self.endpoint.poll(poll_speed=1):
                lastRes = res
            if not lastRes[0]:
                return f"Error: endpoint not up in timeout period: {self.endpoint.url}"

        if self.file_ops and self.file_ops.handle_file_content(config):
            return ""

        if self.command_executor:
            response = self.command_executor.run_commands(config)

            # With our updated cmd.py logic, if the command was supposed to fail:
            # - When it did fail, success will be True and response will have the failure output
            # - When it succeeded unexpectedly, success will be False and we'll get an empty response

            # Handle expected failures (docci-assert-failure)
            if self.command_executor.expect_failure:
                # If the command successfully failed as expected (status != 0 or command not found),
                # we don't need to report it as an error
                return response

            # Normal command (not expecting failure)
            return response

        return ""

    def __str__(self):
        return f"DocsValue(language={self.language}, tags={self.tags}, ignored={self.ignored}, delay_manager={self.delay_manager})"

    def print(self):
        print(self.__str__())
