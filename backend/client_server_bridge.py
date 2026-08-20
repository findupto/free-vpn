"""Client to server control integration foundation."""


class ClientServerBridge:
    def __init__(self, api, control_plane):
        self.api = api
        self.control_plane = control_plane

    def get_server_config(self, device_id):
        return self.control_plane.get_servers()

    def report_status(self, device_id, status):
        return {"device": device_id, "status": status}
