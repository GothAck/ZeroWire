#!/usr/bin/env python3
import unittest
from unittest.mock import Mock
from util import ProcTest

from zerowire import wg


class Test_WGProc(ProcTest, unittest.TestCase):

    def test_basic(self) -> None:
        res = wg.WGProc('my', 'args').run()

        subprocess_res = self.assertSubprocess(
            ['my', 'args'])

        self.assertEqual(res, subprocess_res)

    def test_args(self) -> None:
        res = (
            wg.WGProc('yay')
            .args(['these', 'args'], 'will', ['be', 'flattened'])
            .run())

        subprocess_res = self.assertSubprocess(
            ['yay', 'these', 'args', 'will', 'be', 'flattened'])
        self.assertEqual(res, subprocess_res)

    def test_input(self) -> None:
        res = (
            wg.WGProc('yay')
            .input('yay inputz')
            .run())

        subprocess_res = self.assertSubprocess(
            ['yay'], 'yay inputz')
        self.assertEqual(res, subprocess_res)

    def test_stdout_strip(self) -> None:
        mock = Mock()
        self.setRunSideEffects(mock)
        res = wg.WGProc().run()

        self.assertEqual(res, mock.stdout.strip())


if __name__ == '__main__':
    unittest.main()
