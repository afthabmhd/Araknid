from fastapi import FastAPI
from .services.payments import PaymentService, refund

app = FastAPI()


@app.post("/charge")
def charge(amount: int):
    svc = PaymentService()
    return svc.charge_card(amount)


@app.post("/refund")
def do_refund(charge_id: str):
    return refund(charge_id)


if __name__ == "__main__":
    print("run")
