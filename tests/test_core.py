import base64
import unittest
from unittest.mock import patch

from client.vpn_engine import _prepare, parse_gate, vpnbook_servers


class CoreTests(unittest.TestCase):
    def test_vpngate_parser_accepts_valid_row(self):
        header = '#HostName,IP,Score,Ping,Speed,Uptime,CountryLong,CountryShort,City,OpenVPN_ConfigData_Base64'
        cfg = base64.b64encode(b'client\nremote 1.2.3.4 443 tcp-client\nauth-user-pass\n').decode()
        row = 'test,1.2.3.4,1000,20,100000000,8640000,Testland,TL,Test City,' + cfg
        result = parse_gate((header + '\n' + row + '\n').encode())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['ip'], '1.2.3.4')
        self.assertEqual(result[0]['source'], 'VPN Gate')

    def test_vpnbook_catalog_is_live_and_does_not_use_hardcoded_password(self):
        html = '''<a href="/free-openvpn-account/vpnbook-openvpn-us16.zip">US Server 1</a>'''
        with patch('client.vpn_engine.http_get', return_value=html.encode()):
            servers = vpnbook_servers()
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0]['sid'], 'us16')
        self.assertTrue(servers[0]['bundle'].startswith('https://www.vpnbook.com/'))

    def test_prepare_forces_full_tunnel_without_route_nopull(self):
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            config = _prepare(
                'client\nremote 1.2.3.4 443 tcp\nredirect-gateway def1\nroute-nopull\nauth-user-pass\n',
                'vpn', 'vpn', Path(directory)
            )
            text = config.read_text(encoding='utf-8')
            self.assertIn('redirect-gateway def1', text)
            self.assertIn('route 0.0.0.0 128.0.0.0', text)
            self.assertNotIn('route-nopull', text)
            self.assertNotIn('auth-user-pass\n', text)


if __name__ == '__main__':
    unittest.main()
