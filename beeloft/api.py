import sqlite3
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.security import APIKeyHeader

from beeloft.models import IssueCreate, IssueResolve, MovementCreate, OrderChange, OrderCreate, ProductCreate, ReversalCreate, STAGES, TRANSITIONS
from beeloft.models import MaterialCreate, MaterialReceipt, MaterialIssue, MaterialReservation, MaterialConsumption, BomSave
from beeloft.models import PurchaseRequestCreate, PurchaseRequestDecision
from beeloft.models import SupplierCreate, PurchaseOrderCreate, PurchaseOrderReceipt
from beeloft.store import DomainError, Store
from beeloft.reports import activity_csv

ActivityKind = Literal["all", "movement", "reversal", "issue_opened", "issue_resolved", "order_created", "order_changed"]
MAX_EXPORT_ROWS = 10_000


def create_app(database_path):
    app = FastAPI(title="Beeloft One · Production API", version="0.15.0",
                  description="Produksi dalam pcs; bahan baku dalam satuan master (m/kg/pcs). Gunakan Authorize untuk API key pengguna.")
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
        return JSONResponse(status_code=409, content={"detail": "Data duplikat atau melanggar aturan database. Periksa kode SKU/bahan dan referensi order/batch."})

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

    @app.get('/api/products/{product_id}/bom', tags=['BOM'])
    def bom(product_id: str, user: Actor):
        return store.bom(product_id)

    @app.post('/api/products/{product_id}/bom', status_code=201, tags=['BOM'])
    def save_bom(product_id: str, body: BomSave, user: Actor, key: RequestKey):
        return store.save_bom(product_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/products/{product_id}/bom-history', tags=['BOM'])
    def bom_history(product_id: str, user: Actor, limit: Limit = 100,
                    before: Annotated[int | None, Query(ge=1)] = None):
        return store.bom_history(product_id, limit, before)

    @app.get('/api/orders/{order_id}/material-requirements', tags=['BOM'])
    def material_requirements(order_id: str, user: Actor):
        return store.material_requirements(order_id)

    @app.get('/api/suppliers', tags=['Purchasing'])
    def suppliers(user: Actor, limit: Limit = 100, offset: Offset = 0):
        return store.suppliers(limit, offset)

    @app.post('/api/suppliers', status_code=201, tags=['Purchasing'])
    def create_supplier(body: SupplierCreate, user: Actor, key: RequestKey):
        return store.create_supplier(body.model_dump(mode='json'), user, key)

    @app.get('/api/purchase-orders', tags=['Purchasing'])
    def purchase_orders(user: Actor, limit: Limit = 100, before: Annotated[int | None, Query(ge=1)] = None,
                        status: Literal['all','issued','cancelled'] = 'all',
                        request_id: Annotated[str | None, Query(min_length=1,max_length=160)] = None):
        return store.purchase_orders(limit, before, status, request_id)

    @app.get('/api/purchase-orders/{order_id}', tags=['Purchasing'])
    def purchase_order(order_id: str, user: Actor):
        return store.purchase_order(order_id)

    @app.post('/api/purchase-orders', status_code=201, tags=['Purchasing'])
    def create_purchase_order(body: PurchaseOrderCreate, user: Actor, key: RequestKey):
        return store.create_purchase_order(body.model_dump(mode='json'), user, key)

    @app.post('/api/purchase-orders/{order_id}/cancel', status_code=201, tags=['Purchasing'])
    def cancel_purchase_order(order_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.cancel_purchase_order(order_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/purchase-orders/{order_id}/receipts', status_code=201, tags=['Purchasing'])
    def receive_purchase_order(order_id: str, body: PurchaseOrderReceipt, user: Actor, key: RequestKey):
        return store.receive_purchase_order(order_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/purchase-requests', status_code=201, tags=['Purchasing'])
    def create_purchase_request(body: PurchaseRequestCreate, user: Actor, key: RequestKey):
        return store.create_purchase_request(body.model_dump(mode='json'), user, key)

    @app.get('/api/purchase-requests', tags=['Purchasing'])
    def purchase_requests(user: Actor, limit: Limit = 100,
                          before: Annotated[int | None, Query(ge=1)] = None,
                          status: Literal['all','submitted','approved','rejected','cancelled'] = 'all',
                          order_id: Annotated[str | None, Query(min_length=1,max_length=160)] = None):
        return store.purchase_requests(limit, before, status, order_id)

    @app.get('/api/purchase-requests/{request_id}', tags=['Purchasing'])
    def purchase_request(request_id: str, user: Actor):
        return store.purchase_request(request_id)

    @app.post('/api/purchase-requests/{request_id}/decisions', status_code=201, tags=['Purchasing'])
    def decide_purchase_request(request_id: str, body: PurchaseRequestDecision, user: Actor, key: RequestKey):
        return store.decide_purchase_request(request_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/materials', status_code=201, tags=['Materials'])
    def create_material(body: MaterialCreate, user: Actor, key: RequestKey):
        return store.create_material(body.model_dump(mode='json'), user, key)

    @app.get('/api/materials', tags=['Materials'])
    def materials(user: Actor, limit: Limit = 100, offset: Offset = 0):
        return store.materials(limit, offset)

    @app.post('/api/material-batches', status_code=201, tags=['Materials'])
    def receive_material(body: MaterialReceipt, user: Actor, key: RequestKey):
        return store.receive_material(body.model_dump(mode='json'), user, key)

    @app.get('/api/material-batches', tags=['Materials'])
    def material_batches(user: Actor, limit: Limit = 100, offset: Offset = 0,
                         material_id: Annotated[str, Query(max_length=160)] = '',
                         order_id: Annotated[str | None, Query(min_length=1,max_length=160)] = None):
        return store.material_batches(limit, offset, material_id, order_id)

    @app.post('/api/material-reservations', status_code=201, tags=['Materials'])
    def reserve_material(body: MaterialReservation, user: Actor, key: RequestKey):
        return store.reserve_material(body.model_dump(mode='json'), user, key)

    @app.post('/api/material-consumption', status_code=201, tags=['Materials'])
    def consume_material(body: MaterialConsumption, user: Actor, key: RequestKey):
        return store.consume_material(body.model_dump(mode='json'), user, key)

    @app.post('/api/material-consumption/{consumption_id}/reverse', status_code=201, tags=['Materials'])
    def reverse_consumption(consumption_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_consumption(consumption_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/material-consumption', tags=['Materials'])
    def order_consumption(order_id: str, user: Actor, limit: Limit = 100, offset: Offset = 0):
        return store.order_consumption(order_id, limit, offset)

    @app.get('/api/orders/{order_id}/consumption-history', tags=['Materials'])
    def consumption_history(order_id: str, user: Actor, limit: Limit = 100,
                            before: Annotated[int | None, Query(ge=1)] = None):
        return store.consumption_history(order_id, limit, before)

    @app.get('/api/orders/{order_id}/material-reservations', tags=['Materials'])
    def order_reservations(order_id: str, user: Actor, limit: Limit = 100, offset: Offset = 0):
        return store.order_reservations(order_id, limit, offset)

    @app.get('/api/orders/{order_id}/reservation-history', tags=['Materials'])
    def reservation_history(order_id: str, user: Actor, limit: Limit = 100,
                            before: Annotated[int | None, Query(ge=1)] = None):
        return store.reservation_history(order_id, limit, before)

    @app.get('/api/material-batches/{batch_id}', tags=['Materials'])
    def material_batch(batch_id: str, user: Actor):
        return store.material_batch(batch_id)

    @app.post('/api/material-issues', status_code=201, tags=['Materials'])
    def issue_material(body: MaterialIssue, user: Actor, key: RequestKey):
        return store.issue_material(body.model_dump(mode='json'), user, key)

    @app.post('/api/material-movements/{movement_id}/reverse', status_code=201, tags=['Materials'])
    def reverse_material(movement_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_material(movement_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/material-batches/{batch_id}/movements', tags=['Materials'])
    def batch_material_history(batch_id: str, user: Actor, limit: Limit = 100,
                               before: Annotated[int | None, Query(ge=1)] = None):
        return store.material_history(batch_id=batch_id, limit=limit, before=before)

    @app.get('/api/orders/{order_id}/material-movements', tags=['Materials'])
    def order_material_history(order_id: str, user: Actor, limit: Limit = 100,
                               before: Annotated[int | None, Query(ge=1)] = None):
        return store.material_history(order_id=order_id, limit=limit, before=before)

    @app.post("/api/orders", status_code=201, tags=["Production"])
    def create_order(body: OrderCreate, user: Actor, key: RequestKey):
        return store.create_order(body.model_dump(mode="json"), user, key)

    @app.get("/api/orders", tags=["Production"])
    def orders(user: Actor, limit: Limit = 100, offset: Offset = 0):
        return store.orders(limit, offset)

    @app.get("/api/production-board", tags=["Production"])
    def production_board(user: Actor, limit: Limit = 25, offset: Offset = 0,
                         q: Annotated[str, Query(max_length=160)] = "",
                         status: Literal["all", "active", "overdue", "closed", "blocked"] = "all",
                         owner_id: Annotated[str, Query(max_length=160)] = "",
                         stage: Literal["all", "planned", "cutting", "sewing", "finishing", "qc", "rework", "reject", "warehouse"] = "all"):
        return store.production_board(limit, offset, q, status, owner_id, stage)

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

    @app.get("/api/backup", tags=["System"], response_class=Response,
             responses={200: {"content": {"application/vnd.sqlite3": {}}, "description": "Salinan database konsisten; khusus admin."}})
    def download_backup(user: Actor):
        if user["role"] != "admin":
            raise DomainError(403, "Hanya admin yang dapat mengunduh cadangan database.")
        try:
            with tempfile.TemporaryDirectory(prefix="beeloft-backup-") as folder:
                target = Path(folder) / "backup.sqlite3"
                store.backup(target)
                content = target.read_bytes()
        except (OSError, sqlite3.Error):
            raise DomainError(503, "Cadangan belum dapat dibuat. Periksa ruang penyimpanan server lalu coba lagi.")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        return Response(content, media_type="application/vnd.sqlite3", headers={
            "Content-Disposition": f'attachment; filename="beeloft-backup-{stamp}.sqlite3"',
            "Cache-Control": "no-store"})

    return app
