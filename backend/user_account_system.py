class UserAccountSystem:
    def __init__(self):
        self.users = {}

    def create_user(self, user_id, data):
        self.users[user_id] = data
        return True

    def get_user(self, user_id):
        return self.users.get(user_id)
