from dataclasses import dataclass
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

    def run_commands(self, config: Config) -> str | None:
        if self.endpoint:
            print(f"waiting for endpoint: {self.endpoint}")
            lastRes = (False, "")
            for res in self.endpoint.poll(poll_speed=1):
                lastRes = res
            if not lastRes[0]:
                return f"Error: endpoint not up in timeout period: {self.endpoint.url}"

        if self.file_ops and self.file_ops.handle_file_content(config):
            return None

        if self.command_executor:
            response = self.command_executor.run_commands(config)
            if response and self.command_executor.expect_failure:
                return None
            elif not response and self.command_executor.expect_failure:
                return "Error: expected failure but command succeeded"
            return response

        return None

    def __str__(self):
        return f"DocsValue(language={self.language}, tags={self.tags}, ignored={self.ignored}, delay_manager={self.delay_manager})"

    def print(self):
        print(self.__str__())
