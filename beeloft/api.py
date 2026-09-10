import sqlite3
from typing import Annotated

from fastapi import Depends, FastAPI, Header, Query
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader

from beeloft.models import MovementCreate, OrderCreate, ProductCreate, ReversalCreate, STAGES, TRANSITIONS
from beeloft.store import DomainError, Store


def create_app(database_path):
    app = FastAPI(title="Beeloft One · Production API", version="0.1.0",
                  description="Fondasi produksi internal. Semua jumlah dalam pcs. Gunakan Authorize untuk API key pengguna.")
    store = Store(database_path)
    app.state.store = store
    auth_header = APIKeyHeader(name="X-API-Key", auto_error=False)

    def actor(api_key=Depends(auth_header)):
        if not api_key:
            raise DomainError(401, "Masukkan X-API-Key pengguna.")
        return store.authenticate(api_key)

    Actor = Annotated[dict, Depends(actor)]
    RequestKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]
    Limit = Annotated[int, Query(ge=1, le=500)]
    Offset = Annotated[int, Query(ge=0)]

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse(status_code=exc.status, content={"detail": exc.message})

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(request, exc):
        return JSONResponse(status_code=409, content={"detail": "Data duplikat atau melanggar aturan database. Periksa SKU dan referensi order."})

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(request, exc):
        if "locked" in str(exc).lower() or "busy" in str(exc).lower():
            return JSONResponse(status_code=503, headers={"Retry-After": "1"},
                                content={"detail": "Database sedang sibuk. Ulangi dengan Idempotency-Key yang sama."})
        raise exc

    @app.get("/health", tags=["System"])
    def health():
        with store.transaction() as db:
            db.execute("SELECT 1").fetchone()
        return {"status": "ok"}

    @app.get("/api/me", tags=["Access"])
    def me(user: Actor):
        return user

    @app.get("/api/users", tags=["Access"])
    def users(user: Actor):
        return store.users()

    @app.get("/api/stages", tags=["Production"])
    def stages(user: Actor):
        return {"stages": STAGES, "transitions": sorted(TRANSITIONS), "quantity_unit": "pcs"}

    @app.post("/api/products", status_code=201, tags=["Products"])
    def create_product(body: ProductCreate, user: Actor, key: RequestKey):
        return store.create_product(body.model_dump(mode="json"), user, key)

    @app.get("/api/products", tags=["Products"])
    def products(user: Actor, limit: Limit = 100, offset: Offset = 0):
        return store.products(limit, offset)

    @app.post("/api/orders", status_code=201, tags=["Production"])
    def create_order(body: OrderCreate, user: Actor, key: RequestKey):
        return store.create_order(body.model_dump(mode="json"), user, key)

    @app.get("/api/orders", tags=["Production"])
    def orders(user: Actor, limit: Limit = 100, offset: Offset = 0):
        return store.orders(limit, offset)

    @app.get("/api/orders/{order_id}", tags=["Production"])
    def order(order_id: str, user: Actor):
        return store.order(order_id)

    @app.get("/api/orders/{order_id}/movements", tags=["Production"])
    def history(order_id: str, user: Actor, limit: Limit = 100, offset: Offset = 0):
        return store.history(order_id, limit, offset)

    @app.post("/api/movements", status_code=201, tags=["Production"])
    def move(body: MovementCreate, user: Actor, key: RequestKey):
        return store.move(body.model_dump(mode="json"), user, key)

    @app.post("/api/movements/{movement_id}/reverse", status_code=201, tags=["Production"])
    def reverse(movement_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse(movement_id, body.model_dump(mode="json"), user, key)

    return app
