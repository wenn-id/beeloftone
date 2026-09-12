import sqlite3
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.security import APIKeyHeader

from beeloft.models import IssueCreate, IssueResolve, MovementCreate, OrderChange, OrderCreate, ProductCreate, ProductionChangeRequestCreate, ReversalCreate, STAGES, TRANSITIONS
from beeloft.models import MaterialCreate, MaterialReceipt, MaterialIssue, MaterialReservation, MaterialConsumption, BomSave
from beeloft.models import PurchaseRequestCreate, PurchaseRequestDecision
from beeloft.models import BundleCreate, CuttingRunCreate, FinalQcRecordCreate, FinishedGoodsAdjustmentCreate, FinishedGoodsReceiptCreate, FinishedGoodsStockCountCreate, FinishingRecordCreate, MarketplacePackCreate, MarketplacePickCreate, MarketplaceReservationCreate, MarketplaceReservationRelease, MarketplaceReturnCreate, MarketplaceShipmentCreate, SewingJobComplete, SewingJobCreate, WarehouseMovementCreate
from beeloft.models import SupplierCreate, PurchaseOrderCreate, PurchaseOrderReceipt, QualityDecision, SupplierPaymentRequestCreate, SupplierReturn
from beeloft.store import DomainError, Store
from beeloft.reports import activity_csv

ActivityKind = Literal["all", "movement", "reversal", "issue_opened", "issue_resolved", "order_created", "order_changed"]
MAX_EXPORT_ROWS = 10_000


def create_app(database_path):
    app = FastAPI(title="Beeloft One · Production API", version="0.32.0",
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

    @app.get("/api/approvals", tags=["Approvals"])
    def approvals(user: Actor, limit: Limit = 100, offset: Offset = 0,
                  status: Literal['all','pending','approved','rejected','cancelled'] = 'pending',
                  kind: Literal['all','purchase_request','purchase_order','supplier_payment','production_change'] = 'all'):
        return store.approvals(limit, offset, status, kind)

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
                        status: Literal['all','pending','issued','rejected','cancelled','closed'] = 'all',
                        request_id: Annotated[str | None, Query(min_length=1,max_length=160)] = None):
        return store.purchase_orders(limit, before, status, request_id)

    @app.get('/api/purchase-orders/{order_id}', tags=['Purchasing'])
    def purchase_order(order_id: str, user: Actor):
        return store.purchase_order(order_id)

    @app.post('/api/purchase-orders', status_code=201, tags=['Purchasing'])
    def create_purchase_order(body: PurchaseOrderCreate, user: Actor, key: RequestKey):
        return store.create_purchase_order(body.model_dump(mode='json'), user, key)

    @app.post('/api/purchase-orders/{order_id}/decisions', status_code=201, tags=['Approvals'])
    def decide_purchase_order(order_id: str, body: PurchaseRequestDecision, user: Actor, key: RequestKey):
        return store.decide_purchase_order(order_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/purchase-orders/{order_id}/payment-requests', tags=['Supplier Payments'])
    def supplier_payment_requests(order_id: str, user: Actor, limit: Limit = 100,
                                  before: Annotated[int | None, Query(ge=1)] = None):
        return store.supplier_payment_requests(order_id, limit, before)

    @app.post('/api/purchase-orders/{order_id}/payment-requests', status_code=201, tags=['Supplier Payments'])
    def create_supplier_payment_request(order_id: str, body: SupplierPaymentRequestCreate,
                                        user: Actor, key: RequestKey):
        return store.create_supplier_payment_request(order_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/supplier-payment-requests/{request_id}', tags=['Supplier Payments'])
    def supplier_payment_request(request_id: str, user: Actor):
        return store.supplier_payment_request(request_id)

    @app.post('/api/supplier-payment-requests/{request_id}/decisions', status_code=201,
              tags=['Supplier Payments','Approvals'])
    def decide_supplier_payment_request(request_id: str, body: PurchaseRequestDecision,
                                        user: Actor, key: RequestKey):
        return store.decide_supplier_payment_request(request_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/purchase-orders/{order_id}/cancel', status_code=201, tags=['Purchasing'])
    def cancel_purchase_order(order_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.cancel_purchase_order(order_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/purchase-orders/{order_id}/close', status_code=201, tags=['Purchasing'])
    def close_purchase_order(order_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.close_purchase_order(order_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/qc-intakes/{intake_id}/returns', status_code=201, tags=['Incoming QC'])
    def return_supplier(intake_id: str, body: SupplierReturn, user: Actor, key: RequestKey):
        return store.return_supplier(intake_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/supplier-returns/{return_id}/reverse', status_code=201, tags=['Incoming QC'])
    def reverse_supplier_return(return_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_supplier_return(return_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/purchase-orders/{order_id}/receipts', status_code=201, tags=['Purchasing'])
    def receive_purchase_order(order_id: str, body: PurchaseOrderReceipt, user: Actor, key: RequestKey):
        return store.receive_purchase_order(order_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/purchase-orders/{order_id}/qc-intakes', status_code=201, tags=['Incoming QC'])
    def create_quality_intake(order_id: str, body: PurchaseOrderReceipt, user: Actor, key: RequestKey):
        return store.create_quality_intake(order_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/qc-intakes/{intake_id}', tags=['Incoming QC'])
    def quality_intake(intake_id: str, user: Actor):
        return store.quality_intake(intake_id)

    @app.post('/api/qc-intakes/{intake_id}/decisions', status_code=201, tags=['Incoming QC'])
    def decide_quality(intake_id: str, body: QualityDecision, user: Actor, key: RequestKey):
        return store.decide_quality(intake_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/qc-decisions/{decision_id}/reverse', status_code=201, tags=['Incoming QC'])
    def reverse_quality(decision_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_quality(decision_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/qc-intakes/{intake_id}/cancel', status_code=201, tags=['Incoming QC'])
    def cancel_quality_intake(intake_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.cancel_quality_intake(intake_id, body.model_dump(mode='json'), user, key)

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

    @app.post('/api/orders/{order_id}/cutting-runs', status_code=201, tags=['Cutting'])
    def create_cutting_run(order_id: str, body: CuttingRunCreate, user: Actor, key: RequestKey):
        return store.create_cutting_run(order_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/cutting-runs', tags=['Cutting'])
    def cutting_runs(order_id: str, user: Actor, limit: Limit = 100,
                     before: Annotated[int | None, Query(ge=1)] = None):
        return store.cutting_runs(order_id, limit, before)

    @app.get('/api/cutting-runs/{run_id}', tags=['Cutting'])
    def cutting_run(run_id: str, user: Actor):
        return store.cutting_run(run_id)

    @app.post('/api/cutting-runs/{run_id}/reverse', status_code=201, tags=['Cutting'])
    def reverse_cutting_run(run_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_cutting_run(run_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/cutting-runs/{run_id}/bundles', status_code=201, tags=['Bundling'])
    def create_bundle(run_id: str, body: BundleCreate, user: Actor, key: RequestKey):
        return store.create_bundle(run_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/bundles', tags=['Bundling'])
    def bundles(order_id: str, user: Actor, limit: Limit = 100,
                before: Annotated[int | None, Query(ge=1)] = None):
        return store.bundles(order_id, limit, before)

    @app.get('/api/bundles/{bundle_id}', tags=['Bundling'])
    def bundle(bundle_id: str, user: Actor):
        return store.bundle(bundle_id)

    @app.post('/api/bundles/{bundle_id}/reverse', status_code=201, tags=['Bundling'])
    def reverse_bundle(bundle_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_bundle(bundle_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/bundles/{bundle_id}/sewing-jobs', status_code=201, tags=['Sewing'])
    def create_sewing_job(bundle_id: str, body: SewingJobCreate, user: Actor, key: RequestKey):
        return store.create_sewing_job(bundle_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/sewing-jobs', tags=['Sewing'])
    def sewing_jobs(order_id: str, user: Actor, limit: Limit = 100,
                    before: Annotated[int | None, Query(ge=1)] = None):
        return store.sewing_jobs(order_id, limit, before)

    @app.get('/api/sewing-jobs/{job_id}', tags=['Sewing'])
    def sewing_job(job_id: str, user: Actor):
        return store.sewing_job(job_id)

    @app.post('/api/sewing-jobs/{job_id}/complete', status_code=201, tags=['Sewing'])
    def complete_sewing_job(job_id: str, body: SewingJobComplete, user: Actor, key: RequestKey):
        return store.complete_sewing_job(job_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/sewing-jobs/{job_id}/reverse', status_code=201, tags=['Sewing'])
    def reverse_sewing_job(job_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_sewing_job(job_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/sewing-jobs/{job_id}/finishing-records', status_code=201, tags=['Finishing'])
    def create_finishing_record(job_id: str, body: FinishingRecordCreate, user: Actor, key: RequestKey):
        return store.create_finishing_record(job_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/finishing-records', tags=['Finishing'])
    def finishing_records(order_id: str, user: Actor, limit: Limit = 100,
                          before: Annotated[int | None, Query(ge=1)] = None):
        return store.finishing_records(order_id, limit, before)

    @app.get('/api/finishing-records/{record_id}', tags=['Finishing'])
    def finishing_record(record_id: str, user: Actor):
        return store.finishing_record(record_id)

    @app.post('/api/finishing-records/{record_id}/reverse', status_code=201, tags=['Finishing'])
    def reverse_finishing_record(record_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_finishing_record(record_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/finishing-records/{record_id}/qc-records', status_code=201, tags=['Final QC'])
    def create_final_qc_record(record_id: str, body: FinalQcRecordCreate, user: Actor, key: RequestKey):
        return store.create_final_qc_record(record_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/final-qc-records', tags=['Final QC'])
    def final_qc_records(order_id: str, user: Actor, limit: Limit = 100,
                         before: Annotated[int | None, Query(ge=1)] = None):
        return store.final_qc_records(order_id, limit, before)

    @app.get('/api/final-qc-records/{record_id}', tags=['Final QC'])
    def final_qc_record(record_id: str, user: Actor):
        return store.final_qc_record(record_id)

    @app.post('/api/final-qc-records/{record_id}/reverse', status_code=201, tags=['Final QC'])
    def reverse_final_qc_record(record_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_final_qc_record(record_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/final-qc-records/{record_id}/finished-goods-receipts', status_code=201, tags=['Finished Goods'])
    def create_finished_goods_receipt(record_id: str, body: FinishedGoodsReceiptCreate, user: Actor, key: RequestKey):
        return store.create_finished_goods_receipt(record_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/finished-goods-receipts', tags=['Finished Goods'])
    def finished_goods_receipts(order_id: str, user: Actor, limit: Limit = 100,
                                before: Annotated[int | None, Query(ge=1)] = None):
        return store.finished_goods_receipts(order_id, limit, before)

    @app.get('/api/finished-goods-receipts/{receipt_id}', tags=['Finished Goods'])
    def finished_goods_receipt(receipt_id: str, user: Actor):
        return store.finished_goods_receipt(receipt_id)

    @app.post('/api/finished-goods-receipts/{receipt_id}/reverse', status_code=201, tags=['Finished Goods'])
    def reverse_finished_goods_receipt(receipt_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_finished_goods_receipt(receipt_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/finished-goods-inventory', tags=['Finished Goods'])
    def finished_goods_inventory(user: Actor, limit: Limit = 100, offset: Offset = 0):
        return store.finished_goods_inventory(limit, offset)

    @app.post('/api/finished-goods-receipts/{receipt_id}/warehouse-movements', status_code=201, tags=['Warehouse'])
    def create_warehouse_movement(receipt_id: str, body: WarehouseMovementCreate, user: Actor, key: RequestKey):
        return store.create_warehouse_movement(receipt_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/warehouse-movements', tags=['Warehouse'])
    def warehouse_movements(order_id: str, user: Actor, limit: Limit = 100,
                            before: Annotated[int | None, Query(ge=1)] = None):
        return store.warehouse_movements(order_id, limit, before)

    @app.get('/api/warehouse-movements/{movement_id}', tags=['Warehouse'])
    def warehouse_movement(movement_id: str, user: Actor):
        return store.warehouse_movement(movement_id)

    @app.post('/api/warehouse-movements/{movement_id}/reverse', status_code=201, tags=['Warehouse'])
    def reverse_warehouse_movement(movement_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_warehouse_movement(movement_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/warehouse-inventory', tags=['Warehouse'])
    def warehouse_inventory(user: Actor, limit: Limit = 100, offset: Offset = 0):
        return store.warehouse_inventory(limit, offset)

    @app.post('/api/finished-goods-receipts/{receipt_id}/marketplace-reservations', status_code=201, tags=['Marketplace'])
    def create_marketplace_reservation(receipt_id: str, body: MarketplaceReservationCreate, user: Actor, key: RequestKey):
        return store.create_marketplace_reservation(receipt_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/marketplace-reservations', tags=['Marketplace'])
    def marketplace_reservations(order_id: str, user: Actor, limit: Limit = 100,
                                 before: Annotated[int | None, Query(ge=1)] = None):
        return store.marketplace_reservations(order_id, limit, before)

    @app.get('/api/marketplace-reservations/{reservation_id}', tags=['Marketplace'])
    def marketplace_reservation(reservation_id: str, user: Actor):
        return store.marketplace_reservation(reservation_id)

    @app.post('/api/marketplace-reservations/{reservation_id}/release', status_code=201, tags=['Marketplace'])
    def release_marketplace_reservation(reservation_id: str, body: MarketplaceReservationRelease,
                                        user: Actor, key: RequestKey):
        return store.release_marketplace_reservation(reservation_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/marketplace-reservations/{reservation_id}/picks', status_code=201, tags=['Marketplace'])
    def create_marketplace_pick(reservation_id: str, body: MarketplacePickCreate, user: Actor, key: RequestKey):
        return store.create_marketplace_pick(reservation_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/marketplace-picks', tags=['Marketplace'])
    def marketplace_picks(order_id: str, user: Actor, limit: Limit = 100,
                          before: Annotated[int | None, Query(ge=1)] = None):
        return store.marketplace_picks(order_id, limit, before)

    @app.get('/api/marketplace-picks/{pick_id}', tags=['Marketplace'])
    def marketplace_pick(pick_id: str, user: Actor):
        return store.marketplace_pick(pick_id)

    @app.post('/api/marketplace-picks/{pick_id}/reverse', status_code=201, tags=['Marketplace'])
    def reverse_marketplace_pick(pick_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_marketplace_pick(pick_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/marketplace-picks/{pick_id}/packs', status_code=201, tags=['Marketplace'])
    def create_marketplace_pack(pick_id: str, body: MarketplacePackCreate, user: Actor, key: RequestKey):
        return store.create_marketplace_pack(pick_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/marketplace-packs', tags=['Marketplace'])
    def marketplace_packs(order_id: str, user: Actor, limit: Limit = 100,
                          before: Annotated[int | None, Query(ge=1)] = None):
        return store.marketplace_packs(order_id, limit, before)

    @app.get('/api/marketplace-packs/{pack_id}', tags=['Marketplace'])
    def marketplace_pack(pack_id: str, user: Actor):
        return store.marketplace_pack(pack_id)

    @app.post('/api/marketplace-packs/{pack_id}/reverse', status_code=201, tags=['Marketplace'])
    def reverse_marketplace_pack(pack_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_marketplace_pack(pack_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/marketplace-packs/{pack_id}/shipments', status_code=201, tags=['Marketplace'])
    def create_marketplace_shipment(pack_id: str, body: MarketplaceShipmentCreate, user: Actor, key: RequestKey):
        return store.create_marketplace_shipment(pack_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/marketplace-shipments', tags=['Marketplace'])
    def marketplace_shipments(order_id: str, user: Actor, limit: Limit = 100,
                              before: Annotated[int | None, Query(ge=1)] = None):
        return store.marketplace_shipments(order_id, limit, before)

    @app.get('/api/marketplace-shipments/{shipment_id}', tags=['Marketplace'])
    def marketplace_shipment(shipment_id: str, user: Actor):
        return store.marketplace_shipment(shipment_id)

    @app.post('/api/marketplace-shipments/{shipment_id}/reverse', status_code=201, tags=['Marketplace'])
    def reverse_marketplace_shipment(shipment_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_marketplace_shipment(shipment_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/marketplace-shipments/{shipment_id}/returns', status_code=201, tags=['Marketplace'])
    def create_marketplace_return(shipment_id: str, body: MarketplaceReturnCreate, user: Actor, key: RequestKey):
        return store.create_marketplace_return(shipment_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/marketplace-returns', tags=['Marketplace'])
    def marketplace_returns(order_id: str, user: Actor, limit: Limit = 100,
                            before: Annotated[int | None, Query(ge=1)] = None):
        return store.marketplace_returns(order_id, limit, before)

    @app.get('/api/marketplace-returns/{return_id}', tags=['Marketplace'])
    def marketplace_return(return_id: str, user: Actor):
        return store.marketplace_return(return_id)

    @app.post('/api/marketplace-returns/{return_id}/reverse', status_code=201, tags=['Marketplace'])
    def reverse_marketplace_return(return_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_marketplace_return(return_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/finished-goods-receipts/{receipt_id}/adjustments', status_code=201, tags=['Warehouse'])
    def create_finished_goods_adjustment(receipt_id: str, body: FinishedGoodsAdjustmentCreate,
                                         user: Actor, key: RequestKey):
        return store.create_finished_goods_adjustment(receipt_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/finished-goods-adjustments', tags=['Warehouse'])
    def finished_goods_adjustments(order_id: str, user: Actor, limit: Limit = 100,
                                   before: Annotated[int | None, Query(ge=1)] = None):
        return store.finished_goods_adjustments(order_id, limit, before)

    @app.get('/api/finished-goods-adjustments/{adjustment_id}', tags=['Warehouse'])
    def finished_goods_adjustment(adjustment_id: str, user: Actor):
        return store.finished_goods_adjustment(adjustment_id)

    @app.post('/api/finished-goods-adjustments/{adjustment_id}/reverse', status_code=201, tags=['Warehouse'])
    def reverse_finished_goods_adjustment(adjustment_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_finished_goods_adjustment(adjustment_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/finished-goods-receipts/{receipt_id}/stock-counts', status_code=201, tags=['Warehouse'])
    def create_finished_goods_stock_count(receipt_id: str, body: FinishedGoodsStockCountCreate,
                                          user: Actor, key: RequestKey):
        return store.create_finished_goods_stock_count(receipt_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/finished-goods-stock-counts', tags=['Warehouse'])
    def finished_goods_stock_counts(order_id: str, user: Actor, limit: Limit = 100,
                                    before: Annotated[int | None, Query(ge=1)] = None):
        return store.finished_goods_stock_counts(order_id, limit, before)

    @app.get('/api/finished-goods-stock-counts/{count_id}', tags=['Warehouse'])
    def finished_goods_stock_count(count_id: str, user: Actor):
        return store.finished_goods_stock_count(count_id)

    @app.post('/api/finished-goods-stock-counts/{count_id}/reverse', status_code=201, tags=['Warehouse'])
    def reverse_finished_goods_stock_count(count_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_finished_goods_stock_count(count_id, body.model_dump(mode='json'), user, key)

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

    @app.post("/api/orders/{order_id}/change-requests", status_code=201, tags=["Approvals"])
    def create_production_change_request(order_id: str, body: ProductionChangeRequestCreate,
                                         user: Actor, key: RequestKey):
        return store.create_production_change_request(order_id, body.model_dump(mode="json"), user, key)

    @app.get("/api/orders/{order_id}/change-requests", tags=["Approvals"])
    def production_change_requests(order_id: str, user: Actor, limit: Limit = 100,
                                   before: Annotated[int | None, Query(ge=1)] = None):
        return store.production_change_requests(order_id, limit, before)

    @app.get("/api/production-change-requests/{request_id}", tags=["Approvals"])
    def production_change_request(request_id: str, user: Actor):
        return store.production_change_request(request_id)

    @app.post("/api/production-change-requests/{request_id}/decisions", status_code=201, tags=["Approvals"])
    def decide_production_change_request(request_id: str, body: PurchaseRequestDecision,
                                         user: Actor, key: RequestKey):
        return store.decide_production_change_request(request_id, body.model_dump(mode="json"), user, key)

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
