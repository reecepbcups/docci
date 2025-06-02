import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add the project root to the path to make imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.execute import execute_command


class TestSourceCommand(unittest.TestCase):
    def test_source_command_handling(self):
        """Test that source commands are handled correctly"""
        # Test with a source command
        status, _ = execute_command("source tests/test_source_file.sh")
        self.assertEqual(status, 0)

    #     # Test with a source command with spaces
        status, _ = execute_command("  source  tests/test_source_file.sh  ")
        self.assertEqual(status, 0)

    def test_execute_source_command_update(self):
        """Test the execute_source_command function directly"""

        os.environ["MY_SECRET_VAR"] = "890"
        status, _ = execute_command("source tests/test_source_file.sh")
        self.assertEqual(status, 0)
        self.assertEqual(os.environ["MY_SECRET_VAR"], "123")


if __name__ == "__main__":
    unittest.main()
