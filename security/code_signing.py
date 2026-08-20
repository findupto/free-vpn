class CodeSigner:
    def sign(self, artifact):
        return {"artifact": artifact, "signed": True}

    def verify(self, artifact):
        return True
