


import os
import unittest
from typing import List

from config_types import Config
from main import (
    DocsValue,
    Tags,
    do_logic,
    execute_substitution_commands,
    parse_env,
    parse_markdown_code_blocks,
)

curr_dir = os.path.dirname(os.path.abspath(__file__))

class TestSomething(unittest.TestCase):
    def test_config_run_1(self):
        err = do_logic(Config.load_from_file(os.path.join(curr_dir, "config1.json")))
        self.assertEqual(err, None)

    def test_config_bad_output_check(self):
        err = do_logic(Config.from_json({"paths":["tests/README1.md"],"env_vars": {},"pre_cmds": [],"cleanup_cmds": [],"final_output_contains": "incorrectValueNotFoundHere"}))
        self.assertNotEqual(err, None)

    def test_execute_substitution_commands(self):
        # nothing to exec, leave as is
        self.assertEqual(execute_substitution_commands('123'), '123')
        # exec's within the backticks and performs the substitution
        self.assertEqual(execute_substitution_commands('SOME_VAR=`echo 123`'), 'SOME_VAR=123')
        self.assertEqual(execute_substitution_commands('SOME_VAR=`echo 123`'), 'SOME_VAR=123')
        self.assertEqual(execute_substitution_commands('SOME_VAR=$(echo 123)'), 'SOME_VAR=123')
        # double nested
        self.assertEqual(execute_substitution_commands('SOME_VAR=`echo $(echo 123)`'), 'SOME_VAR=123')
        self.assertEqual(execute_substitution_commands('SOME_VAR=$(echo `echo 123`)'), 'SOME_VAR=123')

    def test_parse_env(self):
        self.assertEqual(parse_env('export MY_VARIABLE=`echo 123`'), {'MY_VARIABLE': '123'})
        self.assertEqual(parse_env('export MY_OTHER_VAR=hello'), {'MY_OTHER_VAR': 'hello'})
        self.assertEqual(parse_env('SERVICE_CONFIG_FILE=service_config.json make deploy-service'), {'SERVICE_CONFIG_FILE': 'service_config.json'})

    def test_parse_markdown_code_blocks(self):
        # basic
        dv: DocsValue = parse_markdown_code_blocks(config=None, content='```bash\nexport MY_VARIABLE=`echo 123`\n```')[0]
        self.assertEqual(dv.language, 'bash')
        self.assertEqual(dv.tags, [])
        self.assertEqual(dv.content, 'export MY_VARIABLE=`echo 123`')
        self.assertEqual(dv.commands, ['export MY_VARIABLE=`echo 123`'])
        self.assertEqual(dv.background, False)
        self.assertEqual(dv.post_delay, 0)
        self.assertEqual(dv.cmd_delay, 0)

        # ignore block
        dv: DocsValue = parse_markdown_code_blocks(config=None, content='# header\nhere is some text\n\n```bash docs-ci-ignore\nexport MY_VARIABLE=`echo 123`\n```')[0]
        self.assertEqual(dv.ignored, True)
        self.assertEqual(dv.tags, [Tags.IGNORE()])

        # multiple tags
        dv: DocsValue = parse_markdown_code_blocks(config=None, content='''# header
                here is some text\n\n
                ```bash docs-ci-post-delay=5 docs-ci-cmd-delay=1
                    export MY_VARIABLE=`echo 123`
                    echo 12345
                ```
                other more text `echo example`
                ## section 2
        ''')[0]
        self.assertEqual(dv.ignored, False)
        self.assertEqual(dv.tags, [f"{Tags.POST_DELAY()}=5",f"{Tags.CMD_DELAY()}=1"])
