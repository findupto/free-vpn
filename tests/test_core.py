import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from client.vpn_engine import _prepare, parse_gate, vpnbook_servers, vpnbook_servers_from_html


class CoreTests(unittest.TestCase):
    def test_vpngate_parser_accepts_valid_row(self):
        header = '#HostName,IP,Score,Ping,Speed,Uptime,CountryLong,CountryShort,City,OpenVPN_ConfigData_Base64'
        cfg = base64.b64encode(b'client\nremote 1.2.3.4 443 tcp-client\nauth-user-pass\n').decode()
        row = 'test,1.2.3.4,1000,20,100000000,8640000,Testland,TL,Test City,' + cfg
        result = parse_gate((header + '\n' + row + '\n').encode())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['ip'], '1.2.3.4')
        self.assertEqual(result[0]['source'], 'VPN Gate')

    def test_vpnbook_catalog_uses_live_page_data(self):
        html = '<a href="/free-openvpn-account/vpnbook-openvpn-us16.zip">us16.vpnbook.com</a>'
        with patch('client.vpn_engine._resolve_host', return_value='1.2.3.4'):
            servers = vpnbook_servers_from_html(html)
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0]['sid'], 'us16')
        self.assertEqual(servers[0]['ip'], '1.2.3.4')
        self.assertTrue(servers[0]['bundle'].startswith('https://www.vpnbook.com/'))

    def test_vpnbook_servers_does_not_use_hardcoded_password(self):
        html = '<a href="/free-openvpn-account/vpnbook-openvpn-us16.zip">us16.vpnbook.com</a>'
        with patch('client.vpn_engine.http_get', return_value=html.encode()):
            servers = vpnbook_servers()
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0]['sid'], 'us16')

    def test_prepare_forces_full_tunnel_without_route_nopull(self):
        with tempfile.TemporaryDirectory() as directory:
            config = _prepare(
                'client\nremote 1.2.3.4 443 tcp\nredirect-gateway def1\nroute-nopull\nauth-user-pass\n',
                'vpn', 'vpn', Path(directory), (2, 6, 0)
            )
            text = config.read_text(encoding='utf-8')
            self.assertIn('redirect-gateway def1', text)
            self.assertIn('route 0.0.0.0 128.0.0.0', text)
            self.assertIn('disable-dco', text)
            self.assertNotIn('route-nopull', text)
            self.assertNotIn('auth-user-pass\n', text)

    def test_prepare_adds_legacy_cipher_compatibility(self):
        with tempfile.TemporaryDirectory() as directory:
            config = _prepare(
                'client\nremote 1.2.3.4 443 tcp\ncipher AES-256-CBC\n',
                'vpn', 'vpn', Path(directory), (2, 6, 0)
            )
            text = config.read_text(encoding='utf-8')
            self.assertIn('disable-dco', text)
            self.assertIn('data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305:AES-256-CBC', text)
            self.assertIn('data-ciphers-fallback AES-256-CBC', text)


if __name__ == '__main__':
    unittest.main()
