import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "client"))

from client.vpn_engine import _cache_load, parse_gate, vpnbook_servers_from_html
import standalone_engine


class CoreTests(unittest.TestCase):
    def test_vpngate_parser_accepts_valid_row(self):
        header = "#HostName,IP,Score,Ping,Speed,Uptime,CountryLong,CountryShort,City,OpenVPN_ConfigData_Base64"
        cfg = base64.b64encode(
            b"client\nremote 1.2.3.4 443 tcp-client\nauth-user-pass\n"
        ).decode()
        row = (
            "test,1.2.3.4,1000,20,100000000,8640000,"
            "Testland,TL,Test City," + cfg
        )
        result = parse_gate((header + "\n" + row + "\n").encode())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["ip"], "1.2.3.4")
        self.assertEqual(result[0]["source"], "VPN Gate")

    def test_vpnbook_catalog_uses_live_page_data(self):
        html = '<a href="/free-openvpn-account/vpnbook-openvpn-us16.zip">us16.vpnbook.com</a>'
        with patch("client.vpn_engine._resolve_host", return_value="1.2.3.4"):
            servers = vpnbook_servers_from_html(html)
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0]["sid"], "us16")
        self.assertEqual(servers[0]["ip"], "1.2.3.4")

    def test_prepare_forces_full_tunnel_and_modern_windows_options(self):
        with tempfile.TemporaryDirectory() as directory:
            config = standalone_engine._prepare(
                "client\nremote 1.2.3.4 443 tcp\nredirect-gateway def1\n"
                "route-nopull\nauth-user-pass\n",
                "vpn",
                "vpn",
                Path(directory),
                (2, 7, 6),
            )
            text = config.read_text(encoding="utf-8")
            self.assertIn("redirect-gateway def1 bypass-dhcp bypass-dns", text)
            self.assertIn("route 0.0.0.0 128.0.0.0", text)
            self.assertIn("route 128.0.0.0 128.0.0.0", text)
            self.assertIn("route-delay 2 30", text)
            self.assertIn("show-net-up", text)
            self.assertIn("disable-dco", text)
            self.assertNotIn("route-nopull", text)
            self.assertNotIn("auth-user-pass\n", text)

    def test_prepare_uses_forward_slashes_for_auth_path(self):
        with tempfile.TemporaryDirectory() as directory:
            config = standalone_engine._prepare(
                "client\nremote 1.2.3.4 443 tcp\n",
                "vpn",
                "vpn",
                Path(directory),
                (2, 7, 6),
            )
            text = config.read_text(encoding="utf-8")
            auth_line = next(
                line for line in text.splitlines() if line.startswith("auth-user-pass ")
            )
            self.assertIn("/", auth_line)
            self.assertNotIn("\\", auth_line)
            self.assertNotIn("fast-io", text.lower())
            self.assertNotIn("persist-key", text.lower())

    def test_prepare_uses_valid_windows_route_methods(self):
        with tempfile.TemporaryDirectory() as directory:
            config = standalone_engine._prepare(
                "client\nremote 1.2.3.4 443 tcp\n",
                "vpn",
                "vpn",
                Path(directory),
                (2, 7, 6),
                "adaptive",
            )
            text = config.read_text(encoding="utf-8")
            if sys.platform.startswith("win"):
                self.assertIn("route-method adaptive", text)
            else:
                self.assertNotIn("route-method", text)

    def test_prepare_adds_legacy_cipher_compatibility(self):
        with tempfile.TemporaryDirectory() as directory:
            config = standalone_engine._prepare(
                "client\nremote 1.2.3.4 443 tcp\ncipher AES-256-CBC\n",
                "vpn",
                "vpn",
                Path(directory),
                (2, 7, 6),
            )
            text = config.read_text(encoding="utf-8")
            self.assertIn(
                "data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305:AES-256-CBC",
                text,
            )
            self.assertIn("data-ciphers-fallback AES-256-CBC", text)

    def test_full_tunnel_requires_both_windows_half_routes(self):
        one = "128.0.0.0 128.0.0.0 10.0.0.1 10.0.0.2 3"
        both = "0.0.0.0 128.0.0.0 10.0.0.1 10.0.0.2 3 | " + one
        self.assertFalse(standalone_engine.full_tunnel_routes(one))
        self.assertTrue(standalone_engine.full_tunnel_routes(both))

    def test_full_tunnel_survives_many_duplicate_routes(self):
        # Windows may expose many duplicate /1 entries. The validation must
        # not lose one half of the pair merely because it is beyond a tail
        # slice of the route table output.
        first = "128.0.0.0 128.0.0.0 10.102.192.25 10.102.192.26 5"
        duplicates = [
            f"0.0.0.0 128.0.0.0 10.102.{i}.1 10.102.{i}.2 3"
            for i in range(10)
        ]
        snapshot = " | ".join([first] + duplicates)
        self.assertTrue(standalone_engine.full_tunnel_routes(snapshot))

    def test_cache_discards_planted_public_vpn_entries(self):
        payload = {
            "time": 4102444800,
            "servers": [
                {
                    "id": "public-vpn-229",
                    "host": "fake.example",
                    "kind": "gate",
                    "ip": "1.2.3.4",
                    "config": "fake",
                },
                {
                    "id": "gate:1.2.3.4:real",
                    "host": "real.example",
                    "kind": "gate",
                    "ip": "1.2.3.4",
                    "config": "real",
                },
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "servers.json"
            cache.write_text(json.dumps(payload), encoding="utf-8")
            with patch("client.vpn_engine.CACHE", cache):
                servers = _cache_load()
        self.assertEqual([s["id"] for s in servers], ["gate:1.2.3.4:real"])


if __name__ == "__main__":
    unittest.main()
