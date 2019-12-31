#!/usr/bin/env python3
import sys
import unittest
from unittest.mock import patch, call
import io
import ipaddress

sys.path.append('../zerowire')

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


class Test_Config(unittest.TestCase):
    def test_load_config_BASIC(self) -> None:
        file = io.StringIO(BASIC_CONFIG)

        res = config.Config.load(file)

        assert isinstance(res, config.Config)
        assert len(res) == 1
        assert 'wg-test' in res
        iface = res['wg-test']
        assert isinstance(iface, config.IfaceConfig)
        assert iface.name == 'wg-test'
        assert iface.addr.compressed == 'fd01:203:405:607:809:a0b:d0e:f10/64'
        assert iface.psk == '1j75n1Zcwp9tUMuFH5H6C5Jn0PVjk66UXqSbY/OTjb8='
        assert iface.privkey == 'aKwoU/4zwKzc89RLS1/ioOGHqqcSQPgTeMNfiPMrbGc='
        assert iface.pubkey == 'h+LAI3+61Va12APH9GXLEy7NZdCLAPIb/ndrj9rsFBI='
        assert iface.port is None
        assert iface.services is None

    def test_load_config_PORT(self) -> None:
        file = io.StringIO(PORT_CONFIG)

        res = config.Config.load(file)

        assert isinstance(res, config.Config)
        assert len(res) == 1
        assert 'wg-test' in res
        iface = res['wg-test']
        assert isinstance(iface, config.IfaceConfig)
        assert iface.name == 'wg-test'
        assert iface.addr.compressed == 'fd01:203:405:607:809:a0b:d0e:f10/64'
        assert iface.psk == '1j75n1Zcwp9tUMuFH5H6C5Jn0PVjk66UXqSbY/OTjb8='
        assert iface.privkey == 'aKwoU/4zwKzc89RLS1/ioOGHqqcSQPgTeMNfiPMrbGc='
        assert iface.pubkey == 'h+LAI3+61Va12APH9GXLEy7NZdCLAPIb/ndrj9rsFBI='
        assert iface.port == 19920
        assert iface.services is None

    def test_load_config_SERVICES(self) -> None:
        file = io.StringIO(SERVICES_CONFIG)

        res = config.Config.load(file)

        assert isinstance(res, config.Config)
        assert len(res) == 1
        assert 'wg-test' in res
        iface = res['wg-test']
        assert isinstance(iface, config.IfaceConfig)
        assert iface.name == 'wg-test'
        assert iface.addr.compressed == 'fd01:203:405:607:809:a0b:d0e:f10/64'
        assert iface.psk == '1j75n1Zcwp9tUMuFH5H6C5Jn0PVjk66UXqSbY/OTjb8='
        assert iface.privkey == 'aKwoU/4zwKzc89RLS1/ioOGHqqcSQPgTeMNfiPMrbGc='
        assert iface.pubkey == 'h+LAI3+61Va12APH9GXLEy7NZdCLAPIb/ndrj9rsFBI='
        assert iface.port == 19920
        assert isinstance(iface.services, list)
        for service in iface.services:
            assert isinstance(service, config.ServiceConfig)


class Test_IfaceConfig_BASIC(unittest.TestCase):
    def setUp(self) -> None:
        file = io.StringIO(BASIC_CONFIG)
        self.ifconfig = config.Config.load(file)['wg-test']

    def test_prefix(self) -> None:
        prefix = self.ifconfig.prefix

        assert isinstance(prefix, ipaddress.IPv6Network)
        assert self.ifconfig.addr in prefix

    @patch('zerowire.wg.wg_proc')
    @patch('zerowire.config.IPDB')
    def test_configure_iface_exists(self, IPDB, wg_proc) -> None:
        ctx = IPDB.return_value.__enter__.return_value
        ctx.interfaces.__contains__.return_value = True
        ctxiface = ctx.interfaces.__getitem__.return_value

        wg_proc.side_effect = ['', 'test\trar\t1234\tnone']

        self.ifconfig.configure()

        IPDB.assert_called_once_with()

        # Remove current iface
        ctx.interfaces.__contains__.assert_called_once_with('wg-test')
        ctx.interfaces.__getitem__.assert_called_once_with('wg-test')
        ctxiface.remove.assert_called_once_with()
        ctxiface.remove.return_value.commit.assert_called_once_with()

        wg_proc.assert_has_calls([
            call([
                'set',
                'wg-test',
                'private-key',
                '/dev/stdin',
            ], input=self.ifconfig.privkey),
            call(['show', 'wg-test', 'dump'], input=None),
        ])

        assert self.ifconfig.port == 1234

    @patch('zerowire.wg.wg_proc')
    @patch('zerowire.config.IPDB')
    def test_configure_iface_not_exists(self, IPDB, wg_proc) -> None:
        ctx = IPDB.return_value.__enter__.return_value
        ctx.interfaces.__contains__.return_value = False
        ctxiface = ctx.interfaces.__getitem__.return_value

        wg_proc.side_effect = ['', 'test\trar\t1234\tnone']

        self.ifconfig.configure()

        IPDB.assert_called_once_with()

        # Remove current iface
        ctx.interfaces.__contains__.assert_called_once_with('wg-test')
        ctx.interfaces.__getitem__.assert_not_called()
        ctxiface.remove.assert_not_called()
        ctxiface.remove.return_value.commit.assert_not_called()

        wg_proc.assert_has_calls([
            call([
                'set',
                'wg-test',
                'private-key',
                '/dev/stdin',
            ], input=self.ifconfig.privkey),
            call(['show', 'wg-test', 'dump'], input=None),
        ])

        assert self.ifconfig.port == 1234


class Test_IfaceConfig_PORT(unittest.TestCase):
    def setUp(self) -> None:
        file = io.StringIO(PORT_CONFIG)
        self.ifconfig = config.Config.load(file)['wg-test']

    def test_prefix(self) -> None:
        prefix = self.ifconfig.prefix

        assert isinstance(prefix, ipaddress.IPv6Network)
        assert self.ifconfig.addr in prefix

    @patch('zerowire.wg.wg_proc')
    @patch('zerowire.config.IPDB')
    def test_configure_iface_exists(self, IPDB, wg_proc) -> None:
        ctx = IPDB.return_value.__enter__.return_value
        ctx.interfaces.__contains__.return_value = True
        ctxiface = ctx.interfaces.__getitem__.return_value

        wg_proc.side_effect = ['', 'test\trar\t1234\tnone']

        self.ifconfig.configure()

        IPDB.assert_called_once_with()

        # Remove current iface
        ctx.interfaces.__contains__.assert_called_once_with('wg-test')
        ctx.interfaces.__getitem__.assert_called_once_with('wg-test')
        ctxiface.remove.assert_called_once_with()
        ctxiface.remove.return_value.commit.assert_called_once_with()

        wg_proc.assert_has_calls([
            call([
                'set',
                'wg-test',
                'listen-port',
                '19920',
                'private-key',
                '/dev/stdin',
            ], input=self.ifconfig.privkey),
        ])

        assert self.ifconfig.port == 19920

    @patch('zerowire.wg.wg_proc')
    @patch('zerowire.config.IPDB')
    def test_configure_iface_not_exists(self, IPDB, wg_proc) -> None:
        ctx = IPDB.return_value.__enter__.return_value
        ctx.interfaces.__contains__.return_value = False
        ctxiface = ctx.interfaces.__getitem__.return_value

        wg_proc.side_effect = ['', 'test\trar\t1234\tnone']

        self.ifconfig.configure()

        IPDB.assert_called_once_with()

        # Remove current iface
        ctx.interfaces.__contains__.assert_called_once_with('wg-test')
        ctx.interfaces.__getitem__.assert_not_called()
        ctxiface.remove.assert_not_called()
        ctxiface.remove.return_value.commit.assert_not_called()

        wg_proc.assert_has_calls([
            call([
                'set',
                'wg-test',
                'listen-port',
                '19920',
                'private-key',
                '/dev/stdin'
            ], input=self.ifconfig.privkey),
        ])

        assert self.ifconfig.port == 19920


if __name__ == '__main__':
    unittest.main()
