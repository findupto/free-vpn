"""Backend integration gateway for VPN clients."""

class BackendGateway:
    def __init__(self, account_service, server_service):
        self.account_service = account_service
        self.server_service = server_service

    def authorize_device(self, user_id, device_id):
        return self.account_service.validate_device(user_id, device_id)

    def get_server_config(self, region=None):
        return self.server_service.select_server(region)
