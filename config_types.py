import json
import os
import subprocess
from typing import Dict, List


class Config:
    paths: List[str] = [] # this will be loaded with the prefix of the absolute path of the repo
    env_vars: Dict[str, str] = {}
    pre_cmds: List[str] = []
    cleanup_cmds: List[str] = []
    only_run_bash: bool = True
    ignore_commands: List[str] = []
    final_output_contains: str = ''
    supported_file_extensions = ["md", "mdx"]
    followed_languages = ["shell", "bash", "sh", "zsh","ksh"] # https://github.com/rouge-ruby/rouge/wiki/List-of-supported-languages-and-lexers
    working_dir: str | None = None
    debug = False

    def __init__(self, paths: List[str], env_var: Dict[str, str], cleanup_cmds: List[str], pre_cmds: List[str] = [], final_output_contains: str = ''):
        self.paths = paths
        self.env_vars = env_var
        self.cleanup_cmds = cleanup_cmds
        self.pre_cmds = pre_cmds
        self.final_output_contains = final_output_contains

    def iterate_paths(self):
        for path in self.paths:
            yield path

    def get_all_possible_paths(self) -> Dict[str, List[str]]:
        collected_files = {} # parent path -> list of files

        for path in self.iterate_paths():
            parent_path = path  # Use the original path as the key
            if parent_path not in collected_files:
                collected_files[parent_path] = []

            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for file in files:
                        if any(file.endswith(ext) for ext in self.supported_file_extensions):
                            collected_files[parent_path].append(os.path.join(root, file))
            else:
                # For non-directory paths, just add the file directly
                collected_files[parent_path].append(path)

        # sort all collected_files values
        for key in collected_files:
            collected_files[key].sort()

        return collected_files


    def __run_cmd(self, cmd: str, hide_output: bool, cwd: str | None = None):
        subprocess.run(cmd, shell=True, cwd=cwd, stdout=subprocess.DEVNULL if hide_output else None, stderr=subprocess.DEVNULL if hide_output else None)

    def run_pre_cmds(self, hide_output: bool = False):
        for cmd in self.pre_cmds:
            self.__run_cmd(cmd, hide_output)

    def run_cleanup_cmds(self, hide_output: bool = False):
        for cmd in self.cleanup_cmds:
            self.__run_cmd(cmd, hide_output)

    @classmethod
    def from_json(cls, json: Dict) -> "Config":
        c = Config(json['paths'], json.get('env_vars', {}), json.get('cleanup_cmds', []), json.get('pre_cmds', []), json.get('final_output_contains', ''))
        c.working_dir = json.get('working_dir', None)
        return c

    def to_json(self):
        return {
            'paths': self.paths,
            'env_vars': self.env_vars,
            'cleanup_cmds': self.cleanup_cmds,
            'pre_cmds': self.pre_cmds,
            'working_dir': self.working_dir,
            'final_output_contains': self.final_output_contains
        }

    @staticmethod
    def load_from_file(absolute_path: str) -> "Config":
        with open(absolute_path) as f:
            return Config.from_json(json.load(f))


