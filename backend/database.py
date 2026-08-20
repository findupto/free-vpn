"""Database persistence abstraction foundation."""


class Database:
    def __init__(self):
        self.servers = {}
        self.devices = {}

    def save_server(self, server_id, data):
        self.servers[server_id] = data

    def get_servers(self):
        return self.servers

    def register_device(self, device_id, data):
        self.devices[device_id] = data
