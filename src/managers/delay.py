import time
from dataclasses import dataclass
from typing import Literal


@dataclass
class DelayManager:
    post_delay: int = 0
    cmd_delay: int = 0

    def handle_delay(self, delay_type: Literal["post", "cmd"]) -> None:
        delay = self.post_delay if delay_type == "post" else self.cmd_delay
        if delay > 0:
            print(f"Sleeping for {delay} seconds after running ({delay_type}_delay)...")
            for i in range(delay, 0, -1):
                print(f"Sleep: {i} seconds remaining...")
                time.sleep(1)
