import unittest

from client.session_controller import SessionController, SessionState


class FakeProcess:
    def __init__(self):
        self.alive = True
        self.terminated = False
        self.killed = False

    def poll(self):
        return None if self.alive else 0

    def terminate(self):
        self.terminated = True
        self.alive = False

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.killed = True
        self.alive = False


class SessionControllerTests(unittest.TestCase):
    def test_connect_lifecycle(self):
        controller = SessionController()
        server = {"host": "vpn-a.example"}
        self.assertTrue(controller.begin_connect(server))
        self.assertEqual(controller.state, SessionState.CONNECTING)
        process = FakeProcess()
        controller.mark_connected(process, "203.0.113.10")
        self.assertEqual(controller.state, SessionState.CONNECTED)
        self.assertEqual(controller.session.public_ip, "203.0.113.10")

    def test_disconnect_is_idempotent(self):
        controller = SessionController()
        process = FakeProcess()
        controller.begin_connect({"host": "vpn-a.example"})
        controller.mark_connected(process, "203.0.113.10")
        controller.disconnect()
        controller.disconnect()
        self.assertEqual(controller.state, SessionState.DISCONNECTED)
        self.assertTrue(process.terminated)

    def test_alternate_servers_excludes_current(self):
        current = {"host": "vpn-a.example", "ip": "198.51.100.1"}
        servers = [
            current,
            {"host": "vpn-b.example", "ip": "198.51.100.2"},
            {"host": "vpn-c.example", "ip": "198.51.100.3", "status": "offline"},
        ]
        candidates = SessionController.alternate_servers(servers, current)
        self.assertEqual([s["host"] for s in candidates], ["vpn-b.example"])

    def test_change_ip_retries_same_ip_and_uses_next_server(self):
        controller = SessionController()
        old = {"host": "vpn-a.example", "ip": "198.51.100.1"}
        controller.begin_connect(old)
        old_process = FakeProcess()
        controller.mark_connected(old_process, "203.0.113.10")
        servers = [old, {"host": "vpn-b.example"}, {"host": "vpn-c.example"}]
        calls = []

        def connect(server):
            calls.append(server["host"])
            process = FakeProcess()
            return process, "203.0.113.10" if len(calls) == 1 else "203.0.113.20"

        server, process, ip = controller.run_change_ip(servers, old, connect)
        self.assertEqual(server["host"], "vpn-c.example")
        self.assertEqual(ip, "203.0.113.20")
        self.assertEqual(controller.state, SessionState.CONNECTED)
        self.assertEqual(calls, ["vpn-b.example", "vpn-c.example"])


if __name__ == "__main__":
    unittest.main()
