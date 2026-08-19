import base64
import unittest

from client.app import parse_gate, variants, VPNBOOK_SERVERS


class CoreTests(unittest.TestCase):
    def test_vpngate_parser_accepts_valid_row(self):
        header = "#HostName,IP,Score,Ping,Speed,Uptime,CountryLong,CountryShort,City,OpenVPN_ConfigData_Base64"
        cfg = base64.b64encode(b"client\nremote 1.2.3.4 443 tcp-client\n").decode()
        row = "test,1.2.3.4,1000,20,100000000,8640000,Testland,TL,Test City," + cfg
        result = parse_gate((header + "\n" + row + "\n").encode())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["ip"], "1.2.3.4")

    def test_openvpn_variants_have_multiple_transports(self):
        config = "client\nremote example.com 1194\nproto udp\n"
        result = variants(config, "example.com")
        self.assertGreaterEqual(len(result), 5)
        self.assertTrue(any("proto tcp-client" in x and "remote example.com 443" in x for x in result))
        self.assertTrue(any("proto udp" in x and "remote example.com 53" in x for x in result))

    def test_vpnbook_catalog_has_real_current_bundle_names(self):
        self.assertEqual(len(VPNBOOK_SERVERS), 10)
        self.assertIn("us16", VPNBOOK_SERVERS)
        self.assertIn("fr2311", VPNBOOK_SERVERS)


if __name__ == "__main__":
    unittest.main()
