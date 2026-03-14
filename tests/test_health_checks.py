import asyncio

import pytest

from networks.universal_network_manager import UniversalNetworkManager
from scanners.scan_director import ScanDirector
from core.health_check import HealthStatus


class DummyEth:
    async def chain_id(self):
        return 1

    async def get_block(self, arg):
        class B:
            pass

        b = B()
        b.number = 123
        b.timestamp = 1700000000
        return b


class DummyClient:
    def __init__(self):
        self.eth = DummyEth()


@pytest.mark.asyncio
async def test_enhanced_network_manager_ping_test_with_and_without_clients():
    enm = UniversalNetworkManager({'networks': {}}, private_key='')

    # No clients => ping_test should be False
    assert not await enm.ping_test()

    # Add dummy client => ping_test should be True
    enm.clients['ethereum'] = DummyClient()
    assert await enm.ping_test()


@pytest.mark.asyncio
async def test_scan_director_health_check_and_probe():
    nm = type('NM', (), {'clients': {'ethereum': None}})()

    sd = ScanDirector(network_manager=nm, memory=None, config={'scanners': {}}, critical_scanners=[])

    class DummyScanner:
        async def scan_network(self, chain):
            await asyncio.sleep(0.01)
            return [{'token': '0x1'}]

    sd.scanners = [DummyScanner()]
    sd.enabled_networks = ['ethereum']
    sd.total_scans = 1
    sd.successful_scans = 1

    hs = await sd.health_check()
    assert isinstance(hs, HealthStatus)
    assert hs.metrics['scanners'] == 1
    assert 'probe' in hs.metrics

    probe = await sd.scanner_probe()
    assert probe['chain'] == 'ethereum'
    assert 'DummyScanner' in probe['results']
    assert probe['results']['DummyScanner']['tokens_found'] == 1
