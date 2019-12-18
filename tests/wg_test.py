#!/usr/bin/env python3
import sys
import unittest
from unittest.mock import patch
import subprocess

sys.path.append('../zerowire')

from zerowire import wg

class Test_wg_proc(unittest.TestCase):
    @patch('subprocess.run')
    def test_wg_proc_basic(self, run) -> None:
        res = wg.wg_proc(['test'])

        run.assert_called_once_with(['wg', 'test'], check=True, input=None, stdout=subprocess.PIPE, text=True)
        assert res == run.return_value.stdout.strip()

    @patch('subprocess.run')
    def test_wg_proc_with_input(self, run) -> None:
        res = wg.wg_proc(['test'], input='Yay my awesome input')

        run.assert_called_once_with(['wg', 'test'], check=True, input='Yay my awesome input', stdout=subprocess.PIPE, text=True)
        assert res == run.return_value.stdout.strip()


class Test_WGProc(unittest.TestCase):
    @patch('zerowire.wg.wg_proc')
    def test_basic(self, wg_proc):
        res = wg.WGProc('my', 'args').run()

        wg_proc.assert_called_once_with(['my', 'args'], input=None)
        assert res == wg_proc.return_value

    @patch('zerowire.wg.wg_proc')
    def test_args(self, wg_proc):
        res = (
            wg.WGProc('yay')
            .args(['these', 'args'], 'will', ['be', 'flattened'])
            .run())

        wg_proc.assert_called_once_with(
            ['yay', 'these', 'args', 'will', 'be', 'flattened'],
            input=None)
        assert res == wg_proc.return_value

    @patch('zerowire.wg.wg_proc')
    def test_input(self, wg_proc):
        res = (
            wg.WGProc('yay')
            .input('yay inputz')
            .run())

        wg_proc.assert_called_once_with(
            ['yay'],
            input='yay inputz')
        assert res == wg_proc.return_value


if __name__ == '__main__':
    unittest.main()
