class CloudOrchestrator:
    def deploy_node(self, region):
        return {"region": region, "status": "provisioning"}

    def scale(self, count):
        return count
