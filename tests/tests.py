


import os
import unittest

from config_types import Config
from main import do_logic


class TestSomething(unittest.TestCase) :

    def test_config_run_1(self):
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        # load in config1.json
        config1_file = os.path.join(curr_dir, "config1.json")
        print(config1_file)

        err = do_logic(Config.load_from_file(config1_file))
        self.assertEqual(err, None)
