from __future__ import annotations
from typing import (
    List,
    Union,
    Optional,
)

import subprocess
import logging

logger = logging.getLogger(__name__)

def wg_proc(args: List[str], input: Optional[str] = None) -> str:
    ret: subprocess.CompletedProcess[str] = subprocess.run(['wg', *args], stdout=subprocess.PIPE, text=True, input=input, check=True)
    stdout = ret.stdout
    return stdout.strip()

class WGProc:
    _args: List[str]
    _input: Optional[str] = None

    def __init__(self, *args: str):
        self._args = list(args)

    def args(self, *args: Union[str, List[str]]) -> WGProc:
        for arg in args:
            if isinstance(arg, list):
                self._args.extend(arg)
            else:
                self._args.append(arg)
        return self

    def input(self, input: str) -> WGProc:
        self._input = input
        return self

    def run(self) -> str:
        return wg_proc(self._args, input=self._input)
