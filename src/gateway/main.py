from fastapi.responses import Response
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
from datetime import datetime

app = FastAPI()

CARS_SERVICE = "http://cars-service:8070"
RENTAL_SERVICE = "http://rental-service:8060"
PAYMENT_SERVICE = "http://payment-service:8050"


@app.get("/manage/health")
def health():
    return JSONResponse(content={"status": "OK"})


@app.get("/api/v1/cars")
async def get_cars(page: int = Query(1, ge=1), size: int = Query(10, ge=1), showAll: bool = Query(False)):
    async with httpx.AsyncClient() as client:
        params = {"page": page, "size": size, "showAll": str(showAll).lower()}
        r = await client.get(f"{CARS_SERVICE}/api/v1/cars", params=params)
        r.raise_for_status()
        return r.json()


@app.get("/api/v1/rental")
async def get_rentals(username: str = Header(..., alias="X-User-Name")):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{RENTAL_SERVICE}/api/v1/rental", headers={"X-User-Name": username})
        r.raise_for_status()
        rentals = r.json()

        aggregated = []
        for rental in rentals:
            car_resp = await client.get(f"{CARS_SERVICE}/api/v1/cars/{rental['carUid']}")
            car_resp.raise_for_status()
            car = car_resp.json()

            payment_resp = await client.get(f"{PAYMENT_SERVICE}/api/v1/payment/{rental['paymentUid']}")
            payment_resp.raise_for_status()
            payment = payment_resp.json()

            aggregated.append({
                "rentalUid": rental["rentalUid"],
                "status": rental["status"],
                "dateFrom": rental["dateFrom"],
                "dateTo": rental["dateTo"],
                "car": {
                    "carUid": car["carUid"],
                    "brand": car["brand"],
                    "model": car["model"],
                    "registrationNumber": car["registrationNumber"]
                },
                "payment": {
                    "paymentUid": payment["paymentUid"],
                    "status": payment["status"],
                    "price": payment["price"]
                }
            })

        return JSONResponse(content=aggregated)


@app.get("/api/v1/rental/{rental_uid}")
async def get_rental(rental_uid: str, username: str = Header(..., alias="X-User-Name")):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{RENTAL_SERVICE}/api/v1/rental/{rental_uid}", headers={"X-User-Name": username})
        r.raise_for_status()
        rental = r.json()

        car_resp = await client.get(f"{CARS_SERVICE}/api/v1/cars/{rental['carUid']}")
        car_resp.raise_for_status()
        car = car_resp.json()

        payment_resp = await client.get(f"{PAYMENT_SERVICE}/api/v1/payment/{rental['paymentUid']}")
        payment_resp.raise_for_status()
        payment = payment_resp.json()

        return JSONResponse(content={
            "rentalUid": rental["rentalUid"],
            "status": rental["status"],
            "dateFrom": rental["dateFrom"],
            "dateTo": rental["dateTo"],
            "car": {
                "carUid": car["carUid"],
                "brand": car["brand"],
                "model": car["model"],
                "registrationNumber": car["registrationNumber"]
            },
            "payment": {
                "paymentUid": payment["paymentUid"],
                "status": payment["status"],
                "price": payment["price"]
            }
        })


class RentalRequest(BaseModel):
    carUid: str
    dateFrom: str
    dateTo: str


@app.post("/api/v1/rental")
async def create_rental(req: RentalRequest, username: str = Header(..., alias="X-User-Name")):
    async with httpx.AsyncClient(timeout=10.0) as client:
        r_cars = await client.get(f"{CARS_SERVICE}/api/v1/cars?showAll=true&page=1&size=1000")
        r_cars.raise_for_status()
        cars_list = r_cars.json().get("items", [])
        car = next((c for c in cars_list if c["carUid"] == req.carUid), None)
        if not car:
            raise HTTPException(status_code=404, detail="Car not found")

        date_from = datetime.strptime(req.dateFrom, "%Y-%m-%d")
        date_to = datetime.strptime(req.dateTo, "%Y-%m-%d")
        days = (date_to - date_from).days
        if days <= 0:
            raise HTTPException(status_code=400, detail="Invalid rental period")
        total_price = car["price"] * days

        payment = await client.post(f"{PAYMENT_SERVICE}/api/v1/payment", json={"price": total_price})
        payment.raise_for_status()
        payment_data = payment.json()
        payment_uid = payment_data["paymentUid"]

        rental = await client.post(
            f"{RENTAL_SERVICE}/api/v1/rental",
            json={
                "carUid": req.carUid,
                "dateFrom": req.dateFrom,
                "dateTo": req.dateTo,
                "paymentUid": payment_uid
            },
            headers={"X-User-Name": username}
        )
        rental.raise_for_status()
        rental_data = rental.json()
        rental_uid = rental_data["rentalUid"]

        await client.put(f"{CARS_SERVICE}/api/v1/cars/{req.carUid}/reserve")

        return JSONResponse(content={
            "rentalUid": rental_uid,
            "carUid": req.carUid,
            "dateFrom": req.dateFrom,
            "dateTo": req.dateTo,
            "status": "IN_PROGRESS",
            "car": {
                "carUid": car["carUid"],
                "brand": car["brand"],
                "model": car["model"],
                "registrationNumber": car["registrationNumber"]
            },
            "payment": {
                "paymentUid": payment_data["paymentUid"],
                "status": payment_data["status"],
                "price": payment_data["price"]
            }
        })


@app.post("/api/v1/rental/{rental_uid}/finish")
async def finish_rental(rental_uid: str, username: str = Header(..., alias="X-User-Name")):
    async with httpx.AsyncClient() as client:
        rental = await client.get(f"{RENTAL_SERVICE}/api/v1/rental/{rental_uid}", headers={"X-User-Name": username})
        rental.raise_for_status()
        rental_data = rental.json()
        car_uid = rental_data["carUid"]

        await client.put(f"{CARS_SERVICE}/api/v1/cars/{car_uid}/release")
        r = await client.post(f"{RENTAL_SERVICE}/api/v1/rental/{rental_uid}/finish", headers={"X-User-Name": username})
        r.raise_for_status()
        return Response(status_code=204)


@app.delete("/api/v1/rental/{rental_uid}")
async def cancel_rental(rental_uid: str, username: str = Header(..., alias="X-User-Name")):
    async with httpx.AsyncClient() as client:
        rental = await client.get(f"{RENTAL_SERVICE}/api/v1/rental/{rental_uid}", headers={"X-User-Name": username})
        rental.raise_for_status()
        rental_data = rental.json()
        car_uid = rental_data["carUid"]
        payment_uid = rental_data["paymentUid"]

        await client.delete(f"{PAYMENT_SERVICE}/api/v1/payment/{payment_uid}")
        await client.put(f"{CARS_SERVICE}/api/v1/cars/{car_uid}/release")
        r = await client.delete(f"{RENTAL_SERVICE}/api/v1/rental/{rental_uid}", headers={"X-User-Name": username})
        r.raise_for_status()
        return Response(status_code=204)
