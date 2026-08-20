class BillingSystem:
    def __init__(self):
        self.subscriptions = {}

    def activate(self, user_id, plan):
        self.subscriptions[user_id] = plan
        return True

    def get_plan(self, user_id):
        return self.subscriptions.get(user_id)
