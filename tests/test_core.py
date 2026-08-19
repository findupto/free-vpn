import base64
import unittest
from client.vpn_engine import parse_gate, vpnbook_servers

class CoreTests(unittest.TestCase):
 def test_vpngate_parser_accepts_valid_row(self):
  header='#HostName,IP,Score,Ping,Speed,Uptime,CountryLong,CountryShort,City,OpenVPN_ConfigData_Base64'
  cfg=base64.b64encode(b'client\nremote 1.2.3.4 443 tcp-client\n').decode();row='test,1.2.3.4,1000,20,100000000,8640000,Testland,TL,Test City,'+cfg
  result=parse_gate((header+'\n'+row+'\n').encode());self.assertEqual(len(result),1);self.assertEqual(result[0]['ip'],'1.2.3.4')
 def test_vpnbook_catalog_has_current_servers(self):
  ids={s['sid'] for s in vpnbook_servers()};self.assertEqual(len(ids),10);self.assertIn('us16',ids);self.assertIn('fr2311',ids)
 def test_vpnbook_server_bundle_urls_are_https(self):
  for server in vpnbook_servers():self.assertTrue(server['bundle'].startswith('https://www.vpnbook.com/'))
if __name__=='__main__':unittest.main()
