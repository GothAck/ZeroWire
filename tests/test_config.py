#!/usr/bin/env python3
import unittest
from unittest.mock import patch
import io
import ipaddress

from util import ProcTest

from zerowire import config

BASIC_CONFIG = """
interfaces:
  test:
    addr: fd01:0203:0405:0607:0809:0a0b:0d0e:0f10/64
    psk: 1j75n1Zcwp9tUMuFH5H6C5Jn0PVjk66UXqSbY/OTjb8=
    privkey: aKwoU/4zwKzc89RLS1/ioOGHqqcSQPgTeMNfiPMrbGc=
    pubkey: h+LAI3+61Va12APH9GXLEy7NZdCLAPIb/ndrj9rsFBI=
"""

PORT_CONFIG = """
interfaces:
  test:
    addr: fd01:0203:0405:0607:0809:0a0b:0d0e:0f10/64
    psk: 1j75n1Zcwp9tUMuFH5H6C5Jn0PVjk66UXqSbY/OTjb8=
    privkey: aKwoU/4zwKzc89RLS1/ioOGHqqcSQPgTeMNfiPMrbGc=
    pubkey: h+LAI3+61Va12APH9GXLEy7NZdCLAPIb/ndrj9rsFBI=
    port: 19920
"""

SERVICES_CONFIG = """
interfaces:
  test:
    addr: fd01:0203:0405:0607:0809:0a0b:0d0e:0f10/64
    psk: 1j75n1Zcwp9tUMuFH5H6C5Jn0PVjk66UXqSbY/OTjb8=
    privkey: aKwoU/4zwKzc89RLS1/ioOGHqqcSQPgTeMNfiPMrbGc=
    pubkey: h+LAI3+61Va12APH9GXLEy7NZdCLAPIb/ndrj9rsFBI=
    port: 19920
    services:
    - type: rar
      name: test
      port: 123
      properties:
        yay: yolo
        nay: oh
"""

SERVICES_CONFIG = """
interfaces:
  test:
    addr: fd01:0203:0405:0607:0809:0a0b:0d0e:0f10/64
    psk: 1j75n1Zcwp9tUMuFH5H6C5Jn0PVjk66UXqSbY/OTjb8=
    privkey: aKwoU/4zwKzc89RLS1/ioOGHqqcSQPgTeMNfiPMrbGc=
    pubkey: h+LAI3+61Va12APH9GXLEy7NZdCLAPIb/ndrj9rsFBI=
    port: 19920
    services:
    - type: rar
      name: test
      port: 123
      properties:
        yay: yolo
        nay: oh
"""


class Test_Config(ProcTest, unittest.TestCase):
    def test_load_config_BASIC(self) -> None:
        file = io.StringIO(BASIC_CONFIG)

        res = config.Config.load(file)

        self.assertIsInstance(res, config.Config)
        self.assertEqual(len(res), 1)
        self.assertIn('wg-test', res)
        iface = res['wg-test']
        self.assertIsInstance(iface, config.IfaceConfig)
        self.assertEqual(
            iface.name, 'wg-test')
        self.assertEqual(
            iface.addr.compressed, 'fd01:203:405:607:809:a0b:d0e:f10/64')
        self.assertEqual(
            iface.psk, '1j75n1Zcwp9tUMuFH5H6C5Jn0PVjk66UXqSbY/OTjb8=')
        self.assertEqual(
            iface.privkey, 'aKwoU/4zwKzc89RLS1/ioOGHqqcSQPgTeMNfiPMrbGc=')
        self.assertEqual(
            iface.pubkey, 'h+LAI3+61Va12APH9GXLEy7NZdCLAPIb/ndrj9rsFBI=')
        self.assertIsNone(iface.port)
        self.assertIsNone(iface.services)

    def test_load_config_PORT(self) -> None:
        file = io.StringIO(PORT_CONFIG)

        res = config.Config.load(file)

        self.assertIsInstance(res, config.Config)
        self.assertEqual(len(res), 1)
        self.assertIn('wg-test', res)
        iface = res['wg-test']
        self.assertIsInstance(iface, config.IfaceConfig)
        self.assertEqual(iface.name, 'wg-test')
        self.assertEqual(
            iface.addr.compressed, 'fd01:203:405:607:809:a0b:d0e:f10/64')
        self.assertEqual(
            iface.psk, '1j75n1Zcwp9tUMuFH5H6C5Jn0PVjk66UXqSbY/OTjb8=')
        self.assertEqual(
            iface.privkey, 'aKwoU/4zwKzc89RLS1/ioOGHqqcSQPgTeMNfiPMrbGc=')
        self.assertEqual(
            iface.pubkey, 'h+LAI3+61Va12APH9GXLEy7NZdCLAPIb/ndrj9rsFBI=')
        self.assertEqual(iface.port, 19920)
        self.assertIsNone(iface.services)

    def test_load_config_SERVICES(self) -> None:
        file = io.StringIO(SERVICES_CONFIG)

        res = config.Config.load(file)

        self.assertIsInstance(res, config.Config)
        self.assertEqual(len(res), 1)
        self.assertIn('wg-test', res)
        iface = res['wg-test']
        self.assertIsInstance(iface, config.IfaceConfig)
        self.assertEqual(iface.name, 'wg-test')
        self.assertEqual(
            iface.addr.compressed, 'fd01:203:405:607:809:a0b:d0e:f10/64')
        self.assertEqual(
            iface.psk, '1j75n1Zcwp9tUMuFH5H6C5Jn0PVjk66UXqSbY/OTjb8=')
        self.assertEqual(
            iface.privkey, 'aKwoU/4zwKzc89RLS1/ioOGHqqcSQPgTeMNfiPMrbGc=')
        self.assertEqual(
            iface.pubkey, 'h+LAI3+61Va12APH9GXLEy7NZdCLAPIb/ndrj9rsFBI=')
        self.assertEqual(iface.port, 19920)
        self.assertIsInstance(iface.services, list)

        for service in iface.services or []:
            self.assertIsInstance(service, config.ServiceConfig)


class Test_IfaceConfig_BASIC(ProcTest, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        file = io.StringIO(BASIC_CONFIG)
        self.ifconfig = config.Config.load(file)['wg-test']
        self.__IPDB = patch('zerowire.config.IPDB')
        self.IPDB = self.__IPDB.start()

    def tearDown(self) -> None:
        super().tearDown()
        self.__IPDB.stop()

    def test_prefix(self) -> None:
        prefix = self.ifconfig.prefix

        self.assertIsInstance(prefix, ipaddress.IPv6Network)
        self.assertIn(self.ifconfig.addr, prefix)

    def test_configure_iface_exists(self) -> None:
        ctx = self.IPDB.return_value.__enter__.return_value
        ctx.interfaces.__contains__.return_value = True
        ctxiface = ctx.interfaces.__getitem__.return_value

        self.setRunSideEffects('', 'test\trar\t1234\tnone')

        self.ifconfig.configure()

        self.IPDB.assert_called_once_with()

        # Remove current iface
        ctx.interfaces.__contains__.assert_called_once_with('wg-test')
        ctx.interfaces.__getitem__.assert_called_once_with('wg-test')
        ctxiface.remove.assert_called_once_with()
        ctxiface.remove.return_value.commit.assert_called_once_with()

        self.assertSubprocesses(
            ([
                'set',
                'wg-test',
                'private-key',
                '/dev/stdin',
            ], self.ifconfig.privkey),
            (['show', 'wg-test', 'dump'], None)
        )

        self.assertEqual(self.ifconfig.port, 1234)

    def test_configure_iface_not_exists(self) -> None:
        ctx = self.IPDB.return_value.__enter__.return_value
        ctx.interfaces.__contains__.return_value = False
        ctxiface = ctx.interfaces.__getitem__.return_value

        self.setRunSideEffects('', 'test\trar\t1234\tnone')

        self.ifconfig.configure()

        self.IPDB.assert_called_once_with()

        # Remove current iface
        ctx.interfaces.__contains__.assert_called_once_with('wg-test')
        ctx.interfaces.__getitem__.assert_not_called()
        ctxiface.remove.assert_not_called()
        ctxiface.remove.return_value.commit.assert_not_called()

        self.assertSubprocesses(
            ([
                'set',
                'wg-test',
                'private-key',
                '/dev/stdin',
            ], self.ifconfig.privkey),
            (['show', 'wg-test', 'dump'], None),
        )

        self.assertEqual(self.ifconfig.port, 1234)


class Test_IfaceConfig_PORT(ProcTest, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        file = io.StringIO(PORT_CONFIG)
        self.ifconfig = config.Config.load(file)['wg-test']
        self.__IPDB = patch('zerowire.config.IPDB')
        self.IPDB = self.__IPDB.start()

    def tearDown(self) -> None:
        super().tearDown()
        self.__IPDB.stop()

    def test_prefix(self) -> None:
        prefix = self.ifconfig.prefix

        self.assertIsInstance(prefix, ipaddress.IPv6Network)
        self.assertIn(self.ifconfig.addr, prefix)

    def test_configure_iface_exists(self) -> None:
        ctx = self.IPDB.return_value.__enter__.return_value
        ctx.interfaces.__contains__.return_value = True
        ctxiface = ctx.interfaces.__getitem__.return_value

        self.setRunSideEffects('', 'test\trar\t1234\tnone')

        self.ifconfig.configure()

        self.IPDB.assert_called_once_with()

        # Remove current iface
        ctx.interfaces.__contains__.assert_called_once_with('wg-test')
        ctx.interfaces.__getitem__.assert_called_once_with('wg-test')
        ctxiface.remove.assert_called_once_with()
        ctxiface.remove.return_value.commit.assert_called_once_with()

        self.assertSubprocess(
            [
                'set',
                'wg-test',
                'listen-port',
                '19920',
                'private-key',
                '/dev/stdin',
            ],
            input=self.ifconfig.privkey
        )

        self.assertEqual(self.ifconfig.port, 19920)

    def test_configure_iface_not_exists(self) -> None:
        ctx = self.IPDB.return_value.__enter__.return_value
        ctx.interfaces.__contains__.return_value = False
        ctxiface = ctx.interfaces.__getitem__.return_value

        self.setRunSideEffects('', 'test\trar\t1234\tnone')

        self.ifconfig.configure()

        self.IPDB.assert_called_once_with()

        # Remove current iface
        ctx.interfaces.__contains__.assert_called_once_with('wg-test')
        ctx.interfaces.__getitem__.assert_not_called()
        ctxiface.remove.assert_not_called()
        ctxiface.remove.return_value.commit.assert_not_called()

        self.assertSubprocesses(
            ([
                'set',
                'wg-test',
                'listen-port',
                '19920',
                'private-key',
                '/dev/stdin'
            ], self.ifconfig.privkey)
        )

        self.assertEqual(self.ifconfig.port, 19920)


if __name__ == '__main__':
    unittest.main()
