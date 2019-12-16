from __future__ import annotations
from typing import (
    Any,
    List,
    Dict,
    Union,
    Optional,
)

import subprocess

def wg_proc(args: List[str], input: Optional[str] = None) -> str:
    ret: subprocess.CompletedProcess[str] = subprocess.run(['wg', *args], stdout=subprocess.PIPE, text=True, input=input, check=True)
    stdout = ret.stdout
    return stdout.strip()
