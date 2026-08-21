import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.billing_system import BillingSystem
from backend.control_plane import ControlPlane, VPNNode
from backend.database import Database
from backend.secure_api import SecureAPI
from client.config_signature import ConfigSignature
from client.config_validator import ConfigValidator
from client.dns_leak_guard import DNSLeakGuard
from client.reconnect_controller import ReconnectController
from client.recovery_manager import RecoveryManager
from client.server_benchmark import ServerBenchmark


class HardeningTests(unittest.TestCase):
    def test_database_persists_server_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vpn.db"
            db = Database(path)
            db.save_server("s1", {"region": "eu", "score": 90})
            db.close()
            reopened = Database(path)
            self.assertEqual(reopened.get_servers()["s1"]["score"], 90)
            reopened.close()

    def test_secure_api_rejects_replay(self):
        api = SecureAPI("secret")
        envelope = api.create_envelope({"node": "n1"})
        self.assertTrue(api.verify_envelope(envelope))
        self.assertFalse(api.verify_envelope(envelope))

    def test_control_plane_marks_stale_nodes(self):
        plane = ControlPlane(stale_after_seconds=1)
        node = VPNNode("n1", "eu", "pub")
        plane.register_node(node)
        node.last_seen = "2000-01-01T00:00:00+00:00"
        self.assertEqual(plane.mark_stale(), ["n1"])
        self.assertEqual(plane.get_available_nodes(), [])

    def test_billing_rejects_expired_activation(self):
        billing = BillingSystem()
        self.assertFalse(billing.activate("u1", "pro", int(time.time()) - 1))
        self.assertIsNone(billing.get_plan("u1"))

    def test_config_validator_rejects_invalid_network(self):
        result = ConfigValidator().validate({"server_public_key": "x" * 32, "endpoint": "1.2.3.4:443", "allowed_ips": ["bad"]})
        self.assertFalse(result.valid)

    def test_config_signature_is_deterministic(self):
        signer = ConfigSignature("key")
        self.assertEqual(signer.sign({"b": 2, "a": 1}), signer.sign({"a": 1, "b": 2}))

    def test_dns_guard_reports_mismatch(self):
        guard = DNSLeakGuard("1.1.1.1")
        guard.enable()
        with patch.object(guard, "_observed_servers", return_value=("8.8.8.8",)):
            self.assertFalse(guard.verify().leak_check_passed)

    def test_benchmark_records_loss_and_jitter(self):
        benchmark = ServerBenchmark()
        calls = iter([0, 1, 0])

        def ping(_):
            if next(calls):
                raise TimeoutError("timeout")

        benchmark.measure_latency("s1", ping, samples=3)
        self.assertEqual(benchmark.results["s1"]["packet_loss"], 1 / 3)
        self.assertIn("jitter_ms", benchmark.results["s1"])

    def test_reconnect_can_cancel(self):
        controller = ReconnectController(max_attempts=5, base_delay=0)
        self.assertFalse(controller.reconnect(lambda: False, cancel_callback=lambda: True))
        self.assertEqual(controller.attempts, 1)

    def test_recovery_quarantines_repeated_failures(self):
        manager = RecoveryManager(max_failures=2, quarantine_seconds=60)
        manager.record_failure("s1", "timeout")
        manager.record_failure("s1", "timeout")
        self.assertTrue(manager.should_block("s1"))


if __name__ == "__main__":
    unittest.main()
