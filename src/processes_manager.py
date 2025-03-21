import os
import signal
from typing import List


class _ProcessManager:
    """Manages background processes for cleanup."""

    def __init__(self):
        self.background_processes: List[int] = []

    def add_process(self, pid: int) -> None:
        """Add a process ID to the tracked list."""
        self.background_processes.append(pid)

    def cleanup(self) -> None:
        """Kill all saved background processes."""
        if not self.background_processes:
            return

        print(f"\nCleaning up {len(self.background_processes)} background processes...")
        for pid in self.background_processes:
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"Terminated process with PID: {pid}")
            except OSError:
                # Process might have already terminated
                pass

        # Clear the list
        self.background_processes.clear()

# Create a singleton instance for global access
process_manager = _ProcessManager()
