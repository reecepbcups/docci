import time
from dataclasses import dataclass
from typing import Literal


@dataclass
class DelayManager:
    post_delay: float = 0.0
    cmd_delay: float = 0.0

    def handle_delay(self, delay_type: str):
        """
        Handle delays based on type.
        Args:
            delay_type: Either "cmd" for command delay or "post" for post-execution delay
        """
        if delay_type == "cmd" and self.cmd_delay > 0:
            print(f"Delaying for {self.cmd_delay} seconds")
            time.sleep(self.cmd_delay)
        elif delay_type == "post" and self.post_delay > 0:
            print(f"Delaying for {self.post_delay} seconds")
            time.sleep(self.post_delay)
