class Base:
    def log(self, msg):
        pass


class PaymentService(Base):
    def charge_card(self, amount):
        self.validate(amount)
        return {"ok": True}

    def validate(self, amount):
        if amount <= 0:
            raise ValueError("bad")


def refund(charge_id):
    raise NotImplementedError
