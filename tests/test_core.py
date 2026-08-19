import base64
import unittest

from client.app import make_variants, parse_vpngate


class CoreTests(unittest.TestCase):
    def test_vpngate_parser_accepts_valid_row(self):
        header = "#HostName,IP,Score,Ping,Speed,Uptime,CountryLong,CountryShort,City,OpenVPN_ConfigData_Base64"
        cfg = base64.b64encode(b"client\nremote 1.2.3.4 443 tcp-client\n").decode()
        row = "test,1.2.3.4,1000,20,100000000,8640000,Testland,TL,Test City," + cfg
        result = parse_vpngate((header + "\n" + row + "\n").encode())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["ip"], "1.2.3.4")

    def test_openvpn_variants_have_multiple_transports(self):
        config = "client\nremote example.com 1194\nproto udp\n"
        variants = make_variants(config, "example.com")
        self.assertGreaterEqual(len(variants), 5)
        self.assertTrue(any("proto tcp-client" in x and "remote example.com 443" in x for x in variants))
        self.assertTrue(any("proto udp" in x and "remote example.com 53" in x for x in variants))


if __name__ == "__main__":
    unittest.main()
