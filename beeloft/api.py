import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.security import APIKeyHeader

from beeloft.models import IssueCreate, IssueResolve, MovementCreate, OrderChange, OrderCreate, ProductCreate, ReversalCreate, STAGES, TRANSITIONS
from beeloft.store import DomainError, Store
from beeloft.reports import activity_csv

ActivityKind = Literal["all", "movement", "reversal", "issue_opened", "issue_resolved", "order_created", "order_changed"]
MAX_EXPORT_ROWS = 10_000


def create_app(database_path):
    app = FastAPI(title="Beeloft One · Production API", version="0.6.0",
                  description="Fondasi produksi internal. Semua jumlah dalam pcs. Gunakan Authorize untuk API key pengguna.")
    store = Store(database_path)
    app.state.store = store
    static = Path(__file__).with_name("static")
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(static / "index.html", headers={"Cache-Control": "no-store"})
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

    @app.get("/api/production-board", tags=["Production"])
    def production_board(user: Actor, limit: Limit = 25, offset: Offset = 0,
                         q: Annotated[str, Query(max_length=160)] = "",
                         status: Literal["all", "active", "overdue", "closed", "blocked"] = "all"):
        return store.production_board(limit, offset, q, status)

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

    @app.get("/api/orders/{order_id}/issues", tags=["Issues"])
    def issues(order_id: str, user: Actor, limit: Limit = 100, offset: Offset = 0,
               before: Annotated[int | None, Query(ge=1)] = None):
        return store.issues(order_id, limit, offset, before)

    @app.post("/api/issues", status_code=201, tags=["Issues"])
    def create_issue(body: IssueCreate, user: Actor, key: RequestKey):
        return store.create_issue(body.model_dump(mode="json"), user, key)

    @app.post("/api/issues/{issue_id}/resolve", status_code=201, tags=["Issues"])
    def resolve_issue(issue_id: str, body: IssueResolve, user: Actor, key: RequestKey):
        return store.resolve_issue(issue_id, body.model_dump(mode="json"), user, key)

    @app.post("/api/orders/{order_id}/changes", status_code=201, tags=["Production"])
    def change_order(order_id: str, body: OrderChange, user: Actor, key: RequestKey):
        return store.change_order(order_id, body.model_dump(mode="json"), user, key)

    @app.get("/api/orders/{order_id}/changes", tags=["Production"])
    def order_changes(order_id: str, user: Actor, limit: Limit = 100,
                      before: Annotated[int | None, Query(ge=1)] = None):
        return store.order_changes(order_id, limit, before)

    @app.get("/api/activity", tags=["Reports"])
    def activity(user: Actor, day: date | None = None, limit: Limit = 50, kind: ActivityKind = "all",
                 start_date: date | None = None, end_date: date | None = None,
                 before_time: datetime | None = None,
                 before_id: Annotated[str | None, Query(min_length=1, max_length=100)] = None):
        if before_time:
            if before_time.utcoffset() is None:
                raise DomainError(422, "Waktu cursor harus menyertakan zona waktu.")
            try:
                before_time = before_time.astimezone(timezone.utc).isoformat()
            except (OverflowError, ValueError):
                raise DomainError(422, "Waktu cursor di luar jangkauan.")
        return store.activity(day, kind, limit, before_time, before_id, start_date, end_date)

    @app.get("/api/activity.csv", tags=["Reports"], response_class=Response,
             responses={200: {"content": {"text/csv": {}}, "description": "CSV UTF-8, seluruh hasil filter (maksimal 10.000 catatan)."}})
    def export_activity(user: Actor, day: date | None = None, kind: ActivityKind = "all",
                        start_date: date | None = None, end_date: date | None = None):
        report = store.activity(day, kind, MAX_EXPORT_ROWS, start_date=start_date, end_date=end_date)
        if report["next_before"]:
            raise DomainError(422, "Hasil melebihi 10.000 catatan. Persempit tanggal atau jenis aktivitas, lalu unduh lagi.")
        filename = f'beeloft-aktivitas-{report["start_date"]}-{report["end_date"]}-{kind}.csv'
        return Response(activity_csv(report["items"]), media_type="text/csv", headers={
            "Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})

    return app
