from typing import (
    Any,
    Callable,
    Iterable,
    List,
    NoReturn,
    Optional,
    Tuple,
    Union,
)

import sys

from unittest.mock import patch, Mock, MagicMock, call
import unittest.mock as mock
import subprocess

sys.path.append('../zerowire')

TSideEffect = Union[
    str,
    Mock,
    Callable[..., str],
    Callable[..., Mock],
    Callable[..., NoReturn],
]


class ProcTest:
    __run: Optional[mock._patch] = None
    __run_returns: Optional[List[Mock]] = None
    __run_side_effects: Optional[List[TSideEffect]] = None

    def assertSubprocess(
        self,
        args: Iterable[str],
        input: Optional[str] = None,
    ) -> MagicMock:
        return self.assertSubprocesses((args, input))[0]

    def assertSubprocesses(
        self,
        *calls: Tuple[Iterable[str], Optional[str]]
    ) -> List[Mock]:
        self.run.assert_has_calls([
            call(
                ['wg', *args],
                stdout=subprocess.PIPE,
                text=True,
                input=input,
                check=True,
            )
            for (args, input)
            in calls
        ])
        assert self.__run_returns is not None, 'setUp was not called correctly'
        return self.__run_returns

    def setRunSideEffects(self, *args: TSideEffect) -> None:
        self.__run_side_effects = list(args)

    def __generateReturn(self, *args: Any, **kwargs: Any) -> Mock:
        if self.__run_side_effects is None:
            o = Mock()
        else:
            assert self.__run_side_effects, 'Run out of side effects'
            o = self.__run_side_effects[0]
            del self.__run_side_effects[0]
            # Mock objects are callable
            if callable(o) and not isinstance(o, mock.Mock):
                o = o(*args, **kwargs)
            if isinstance(o, str):
                o = Mock(stdout=o)

        assert self.__run_returns is not None, 'setUp was not called correctly'

        self.__run_returns.append(o.stdout.strip())
        return o

    def setUp(self) -> None:
        self.__run_returns = []
        self.__run_side_effects = None
        self.__run = patch('subprocess.run', side_effect=self.__generateReturn)
        self.run = self.__run.start()

    def tearDown(self) -> None:
        self.__run_returns = None
        self.__run_side_effects = None
        if self.__run:
            self.__run.stop()
            self.__run = None
