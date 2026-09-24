import sqlite3
import secrets
import string
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.security import APIKeyHeader

from beeloft.models import AiActionProposalCreate, AiActionProposalDecision, AiInvestigationFeedbackCreate, AttendanceSave, BrowserSessionLogin, BundleHandoffCreate, CapacityCalendarSave, EmployeeChange, EmployeeCreate, IntegrationSyncRunCreate, InvestigationCreate, IssueCreate, IssueResolve, JubelioListingSnapshotImport, JubelioOrderSnapshotImport, JubelioReturnSnapshotImport, JubelioStockSnapshotImport, MekariFinanceSnapshotImport, MekariPayableSnapshotImport, MekariPayrollSnapshotImport, MekariReceivableSnapshotImport, MovementCreate, OrderChange, OrderCreate, PayrollApprovalDecision, PayrollApprovalRequestCreate, ProductCreate, ProductExternalMappingSave, ProductionChangeRequestCreate, ReversalCreate, RoutingStandardSave, STAGES, TRANSITIONS, WorkforceRequestCreate, WorkforceRequestDecision, WorkCenterChange, WorkCenterCreate
from beeloft.models import MaterialCreate, MaterialReceipt, MaterialIssue, MaterialReservation, MaterialConsumption, BomSave
from beeloft.models import PurchaseRequestCreate, PurchaseRequestDecision
from beeloft.models import BundleCreate, CuttingRunCreate, FinalQcRecordCreate, FinishedGoodsAdjustmentCreate, FinishedGoodsReceiptCreate, FinishedGoodsStockCountCreate, FinishingRecordCreate, MarketplacePackCreate, MarketplacePickCreate, MarketplaceReservationCreate, MarketplaceReservationRelease, MarketplaceReturnCreate, MarketplaceSaleSettlementCreate, MarketplaceShipmentCreate, ReworkCompletionCreate, SewingJobComplete, SewingJobCreate, WarehouseMovementCreate
from beeloft.models import MarketingBudgetRequestCreate, SupplierCreate, PurchaseOrderCreate, PurchaseOrderReceipt, QualityDecision, SupplierPaymentRequestCreate, SupplierReturn
from beeloft.store import DomainError, Store
from beeloft.brain import investigate
from beeloft.command_center import build_command_center
from beeloft.labels import bundle_label_svg, finished_goods_label_svg, material_batch_label_svg
from beeloft.oidc import OidcClient, OidcConfig, OidcError
from beeloft.reports import activity_csv

ActivityKind = Literal["all", "movement", "reversal", "issue_opened", "issue_resolved", "order_created", "order_changed"]
MAX_EXPORT_ROWS = 10_000
JAKARTA = timezone(timedelta(hours=7))
# `OidcClient.authorization_request` menerbitkan state lewat `secrets.token_urlsafe`, sehingga state
# yang sah hanya memuat karakter Base64 URL-safe.
OIDC_STATE_CHARACTERS = frozenset(string.ascii_letters + string.digits + '-_')


def oidc_state_bytes(value):
    """Representasi byte state OIDC, atau None bila state di luar alfabet yang aplikasi terbitkan.

    `secrets.compare_digest` menolak `str` yang memuat karakter non-ASCII dengan `TypeError`, dan
    kedua state yang dibandingkan pada callback sepenuhnya dikendalikan pengirim request: parameter
    `state` pada query dan cookie `beeloft_oidc_state`. Membandingkannya mentah membuat
    `/api/sso/callback?code=x&state=%C3%A9` — dan juga state sah yang datang bersama cookie ber-byte
    non-ASCII — dijawab HTTP 500 dengan traceback, padahal state seperti itu tidak pernah diterbitkan
    aplikasi dan semestinya ditolak sebagai state tidak sah.

    State karena itu diperiksa terhadap alfabet `secrets.token_urlsafe` lebih dahulu, lalu
    dibandingkan sebagai byte ASCII. Yang di luar alfabet tidak pernah mencapai perbandingan,
    tidak pernah mencapai `consume_oidc_login_attempt`, dan tidak dapat menghabiskan attempt yang
    tersimpan. Panjangnya tetap dibatasi `Query(max_length=512)` seperti sebelumnya.
    """
    if not value or not OIDC_STATE_CHARACTERS.issuperset(value):
        return None
    return value.encode('ascii')

# Batas atas integer signed 64-bit SQLite. Parameter offset/cursor yang dibind langsung ke SQL
# wajib dibatasi di bawah ini: nilai 2**63 atau lebih memicu OverflowError saat binding dan
# menjawab HTTP 500, bukan 422. Lihat issue #33.
SQLITE_MAX_INTEGER = 9223372036854775807


def jakarta_today():
    """Tanggal berjalan menurut zona operasional Jakarta.

    Seluruh tanggal bisnis pada domain ini dihitung di Jakarta: validasi kehadiran, filter audit,
    tanggal pencatatan PO pada material price insights, dan command center. Memakai `date.today()`
    milik proses membuat `as_of` default tertinggal satu hari setiap kali server berjalan antara
    17:00 dan 24:00 UTC, sehingga catatan yang baru dibuat jatuh di luar jendela laporannya sendiri.
    """
    return datetime.now(JAKARTA).date()


def create_app(database_path, oidc_config=None, oidc_transport=None):
    app = FastAPI(title="Beeloft One · Production API", version="0.104.0",
                  description="Produksi dalam pcs; bahan baku dalam satuan master (m/kg/pcs). Gunakan Authorize untuk API key pengguna.")
    store = Store(database_path)
    oidc_config = oidc_config or OidcConfig.from_env()
    oidc = OidcClient(oidc_config, oidc_transport) if oidc_config else None
    app.state.store = store
    app.state.oidc = oidc
    static = Path(__file__).with_name("static")
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(static / "index.html", headers={"Cache-Control": "no-store"})
    auth_header = APIKeyHeader(name="X-API-Key", auto_error=False)

    def actor(request: Request, api_key=Depends(auth_header)):
        # Prioritas kredensial dicatat, bukan hanya dipakai. X-API-Key tetap menang atas cookie
        # seperti sebelumnya, dan `request.state.browser_session` menyimpan token session hanya bila
        # cookie itulah yang benar-benar meng-autentikasi request ini. Logout memerlukan fakta
        # tersebut: satu-satunya session yang boleh dicabutnya adalah session yang memberinya akses,
        # dan jalur cookie itu sudah lewat pemeriksaan CSRF di bawah.
        request.state.browser_session = None
        if api_key:
            resolved = store.authenticate(api_key)
        else:
            session=request.cookies.get('beeloft_session')
            if not session:
                raise DomainError(401,"Masukkan X-API-Key atau login melalui browser.")
            resolved = store.authenticate_browser_session(session,request.headers.get('X-CSRF-Token'),
                                                          request.method not in ('GET','HEAD','OPTIONS'))
            request.state.browser_session = session
        # Binding aktor. Cookie session dipakai bersama seluruh tab pada satu origin, sedangkan akun
        # yang membuka sebuah form hanya diketahui tab tersebut. Klien menyatakan akun yang
        # dipakainya saat menyusun request, dan pernyataan itu wajib cocok dengan akun yang
        # benar-benar ter-autentikasi. Header ini tidak pernah memberi akses: nilainya hanya dapat
        # menolak request, bukan meloloskannya, sehingga klien API key tanpa header tidak berubah.
        asserted = request.headers.get('X-Beeloft-Actor')
        if asserted and asserted != resolved['id']:
            raise DomainError(403, "Session browser ini sudah berpindah ke akun lain. Masuk ulang "
                                   "sebagai akun yang membuka form ini; tidak ada pencatatan yang "
                                   "dijalankan.")
        return resolved

    Actor = Annotated[dict, Depends(actor)]
    # Daftar dan ringkasan approval harus menerima filter yang sama persis, jadi kedua literal
    # ini dipakai bersama oleh /api/approvals dan /api/approvals/summary.
    ApprovalStatus = Literal['all','pending','approved','rejected','cancelled']
    ApprovalKind = Literal['all','purchase_request','purchase_order','supplier_payment',
                           'marketing_budget','production_change','workforce_leave',
                           'workforce_overtime','payroll_batch','ai_action']
    RequestKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]
    Limit = Annotated[int, Query(ge=1, le=500)]
    Offset = Annotated[int, Query(ge=0, le=SQLITE_MAX_INTEGER)]
    Before = Annotated[int | None, Query(ge=1, le=SQLITE_MAX_INTEGER)]

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse(status_code=exc.status, content={"detail": exc.message})

    @app.exception_handler(OidcError)
    async def oidc_error(request, exc):
        return JSONResponse(status_code=exc.status, headers={'Cache-Control':'no-store'},
                            content={"detail": exc.message})

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

    def session_cookies(request, response, token, csrf):
        secure=request.url.scheme=='https'
        response.set_cookie('beeloft_session',token,max_age=8*60*60,httponly=True,
                            secure=secure,samesite='strict',path='/')
        response.set_cookie('beeloft_csrf',csrf,max_age=8*60*60,httponly=False,
                            secure=secure,samesite='strict',path='/')
        response.headers['Cache-Control']='no-store'

    @app.post('/api/session', tags=['Access'])
    def create_session(body: BrowserSessionLogin, request: Request, response: Response):
        user,token,csrf=store.create_browser_session(body.api_key)
        session_cookies(request,response,token,csrf)
        return user

    @app.get('/api/sso', tags=['Access'])
    def sso_status():
        return {'enabled':bool(oidc),'label':oidc.config.label if oidc else '',
                'login_url':'/api/sso/login' if oidc else ''}

    @app.get('/api/sso/login', tags=['Access'])
    def sso_login(request: Request):
        if not oidc:
            raise OidcError(404,'Login SSO belum dikonfigurasi.')
        url,state,nonce,verifier=oidc.authorization_request()
        store.create_oidc_login_attempt(state,nonce,verifier)
        response=RedirectResponse(url,status_code=302,headers={'Cache-Control':'no-store'})
        response.set_cookie('beeloft_oidc_state',state,max_age=10*60,httponly=True,
                            secure=request.url.scheme=='https',samesite='lax',path='/api/sso/callback')
        return response

    @app.get('/api/sso/callback', tags=['Access'])
    def sso_callback(request: Request,
                     code: Annotated[str | None, Query(min_length=1,max_length=4096)] = None,
                     state: Annotated[str | None, Query(min_length=1,max_length=512)] = None,
                     error: Annotated[str | None, Query(max_length=160)] = None):
        if not oidc:
            raise OidcError(404,'Login SSO belum dikonfigurasi.')
        if error or not code or not state:
            raise OidcError(401,'Login dibatalkan atau ditolak oleh penyedia identitas.')
        browser_state=oidc_state_bytes(request.cookies.get('beeloft_oidc_state',''))
        callback_state=oidc_state_bytes(state)
        if browser_state is None or callback_state is None or not secrets.compare_digest(browser_state,callback_state):
            raise OidcError(401,'State login OIDC tidak cocok dengan browser.')
        attempt=store.consume_oidc_login_attempt(state)
        identity=oidc.exchange(code,attempt['code_verifier'],attempt['nonce_hash'])
        user=store.authenticate_oidc_identity(identity['issuer'],identity['subject'])
        user,token,csrf=store.create_browser_session_for_user(user['id'])
        response=RedirectResponse('/',status_code=303)
        session_cookies(request,response,token,csrf)
        response.delete_cookie('beeloft_oidc_state',path='/api/sso/callback')
        return response

    @app.post('/api/session/logout', tags=['Access'])
    def close_session(request: Request, response: Response, user: Actor):
        """Menutup session browser yang memberi akses pada request ini.

        Kredensial API key tidak membawa session browser, jadi tidak ada yang dicabut dan
        jawabannya tetap 200 `signed_out`. API key itu sendiri tidak pernah dicabut di sini.
        """
        # Sebelumnya endpoint ini membaca `request.cookies['beeloft_session']` langsung. Autentikasi
        # bersama boleh lolos lewat X-API-Key tanpa cookie sama sekali, sehingga klien API key yang
        # sah dijawab HTTP 500 oleh KeyError. Yang dicabut sekarang adalah session yang benar-benar
        # meng-autentikasi request ini, bukan cookie apa pun yang ikut terkirim:
        #
        # * Cookie session hanya sampai ke sini setelah `actor()` memeriksanya beserta token CSRF,
        #   jadi pencabutan tetap terlindung CSRF persis seperti sebelumnya dan tidak ada jalan baru
        #   untuk melewatinya.
        # * Cookie yang menempel pada request ber-API-key tidak pernah ter-autentikasi, jadi tidak
        #   dicabut. Sebuah API key tidak boleh mengakhiri session browser akun mana pun tanpa bukti
        #   kepemilikan token CSRF-nya; sebelum perbaikan, request seperti itu mencabut session akun
        #   lain tanpa pemeriksaan apa pun.
        #
        # Kegagalan penyimpanan tidak ditangkap, sehingga logout yang gagal tidak pernah terlihat
        # sebagai logout yang berhasil.
        response.headers['Cache-Control']='no-store'
        session=request.state.browser_session
        if session is None:
            return {'status':'signed_out'}
        store.revoke_browser_session(session)
        response.delete_cookie('beeloft_session',path='/')
        response.delete_cookie('beeloft_csrf',path='/')
        return {'status':'signed_out'}

    @app.get("/api/me", tags=["Access"])
    def me(user: Actor):
        return user

    @app.get("/api/users", tags=["Access"])
    def users(user: Actor):
        return store.users()

    @app.get('/api/command-center', tags=['Management'])
    def command_center(user: Actor):
        return build_command_center(store)

    @app.get('/api/audit-events', tags=['Audit'])
    def audit_events(user: Actor, limit: Limit = 50,
                     before: Before = None,
                     category: Literal['all','master_data','production','materials','purchasing',
                                       'warehouse','marketplace','approval','ai','integration'] = 'all',
                     actor_id: Annotated[str, Query(max_length=500)] = '',
                     q: Annotated[str, Query(max_length=160)] = '',
                     start_date: date | None = None, end_date: date | None = None):
        if user['role']!='admin':
            raise DomainError(403,'Hanya admin yang dapat membaca global audit trail.')
        return store.audit_events(limit,before,category,actor_id,q,start_date,end_date)

    @app.get('/api/audit-events/{event_id}', tags=['Audit'])
    def audit_event(event_id: str, user: Actor):
        if user['role']!='admin':
            raise DomainError(403,'Hanya admin yang dapat membaca global audit trail.')
        return store.audit_event(event_id)

    @app.get("/api/approvals", tags=["Approvals"])
    def approvals(user: Actor, limit: Limit = 100, offset: Offset = 0,
                  status: ApprovalStatus = 'pending', kind: ApprovalKind = 'all'):
        return store.approvals(limit, offset, status, kind)

    @app.get('/api/approvals/summary', tags=['Approvals'])
    def approvals_summary(user: Actor, status: ApprovalStatus = 'pending',
                          kind: ApprovalKind = 'all'):
        """Jumlah dan nominal seluruh populasi approval yang cocok dengan filter.

        Dibaca terpisah dari daftar `/api/approvals` supaya total tidak pernah dibatasi oleh
        limit/offset halaman. Filter status dan kind memakai populasi yang sama dengan daftar.
        """
        return store.approvals_summary(status, kind)

    @app.get('/api/ai/action-proposals', tags=['AI Brain','Approvals'])
    def ai_action_proposals(user: Actor, limit: Limit = 100,
                            before: Before = None,
                            status: Literal['all','submitted','approved','rejected','cancelled'] = 'all'):
        return store.ai_action_proposals(limit,before,status)

    @app.post('/api/ai/action-proposals', status_code=201, tags=['AI Brain','Approvals'])
    def create_ai_action_proposal(body: AiActionProposalCreate, user: Actor, key: RequestKey):
        return store.create_ai_action_proposal(body.model_dump(mode='json'),user,key)

    @app.get('/api/ai/action-proposals/{proposal_id}', tags=['AI Brain','Approvals'])
    def ai_action_proposal(proposal_id: str, user: Actor):
        return store.ai_action_proposal(proposal_id)

    @app.post('/api/ai/action-proposals/{proposal_id}/decisions', status_code=201,
              tags=['AI Brain','Approvals'])
    def decide_ai_action_proposal(proposal_id: str, body: AiActionProposalDecision,
                                  user: Actor, key: RequestKey):
        return store.decide_ai_action_proposal(proposal_id,body.model_dump(mode='json'),user,key)

    @app.get('/api/marketing-budget-requests', tags=['Marketing','Approvals'])
    def marketing_budget_requests(user: Actor, limit: Limit = 100,
                                  before: Before = None,
                                  status: Literal['all','submitted','approved','rejected','cancelled'] = 'all'):
        return store.marketing_budget_requests(limit, before, status)

    @app.post('/api/marketing-budget-requests', status_code=201, tags=['Marketing','Approvals'])
    def create_marketing_budget_request(body: MarketingBudgetRequestCreate, user: Actor, key: RequestKey):
        return store.create_marketing_budget_request(body.model_dump(mode='json'), user, key)

    @app.get('/api/marketing-budget-requests/{request_id}', tags=['Marketing','Approvals'])
    def marketing_budget_request(request_id: str, user: Actor):
        return store.marketing_budget_request(request_id)

    @app.post('/api/marketing-budget-requests/{request_id}/decisions', status_code=201,
              tags=['Marketing','Approvals'])
    def decide_marketing_budget_request(request_id: str, body: PurchaseRequestDecision,
                                        user: Actor, key: RequestKey):
        return store.decide_marketing_budget_request(request_id, body.model_dump(mode='json'), user, key)

    @app.get("/api/stages", tags=["Production"])
    def stages(user: Actor):
        return {"stages": STAGES, "transitions": sorted(TRANSITIONS), "quantity_unit": "pcs"}

    @app.post('/api/ai/investigate', tags=['AI Brain'])
    def ai_investigate(body: InvestigationCreate, user: Actor):
        return investigate(store, body.model_dump(mode='json'))

    @app.get('/api/ai/investigations', tags=['AI Brain'])
    def ai_investigations(user: Actor, limit: Limit = 100,
                          before: Before = None,
                          intent: Literal['all','overview','production','stockout','approvals','margin'] = 'all',
                          q: Annotated[str, Query(max_length=160)] = ''):
        return store.ai_investigations(limit,before,intent,q)

    @app.post('/api/ai/investigations', status_code=201, tags=['AI Brain'])
    def create_ai_investigation(body: InvestigationCreate, user: Actor, key: RequestKey):
        return store.create_ai_investigation(body.model_dump(mode='json'),user,key)

    @app.get('/api/ai/investigations/{investigation_id}', tags=['AI Brain'])
    def ai_investigation(investigation_id: str, user: Actor):
        return store.ai_investigation(investigation_id)

    @app.post('/api/ai/investigations/{investigation_id}/feedback', status_code=201,
              tags=['AI Brain'])
    def create_ai_investigation_feedback(investigation_id: str,
                                         body: AiInvestigationFeedbackCreate,
                                         user: Actor, key: RequestKey):
        return store.create_ai_investigation_feedback(
            investigation_id,body.model_dump(mode='json'),user,key)

    @app.get('/api/integrations', tags=['Integrations'])
    def integrations(user: Actor,
                     stale_after_minutes: Annotated[int, Query(ge=5,le=10_080)] = 1440):
        return store.integrations(stale_after_minutes)

    @app.get('/api/integration-sync-runs', tags=['Integrations'])
    def integration_sync_runs(user: Actor, limit: Limit = 100,
                              before: Before = None,
                              system: Literal['all','jubelio','mekari'] = 'all',
                              scope: Annotated[str, Query(max_length=40)] = '',
                              status: Literal['all','succeeded','failed'] = 'all'):
        return store.integration_sync_runs(limit,before,system,scope,status)

    @app.post('/api/integration-sync-runs', status_code=201, tags=['Integrations'])
    def create_integration_sync_run(body: IntegrationSyncRunCreate, user: Actor, key: RequestKey):
        return store.create_integration_sync_run(body.model_dump(mode='json'),user,key)

    @app.get('/api/integration-sync-runs/{run_id}', tags=['Integrations'])
    def integration_sync_run(run_id: str, user: Actor):
        return store.integration_sync_run(run_id)

    @app.post('/api/integrations/jubelio/finished-goods-snapshots', status_code=201, tags=['Integrations'])
    def import_jubelio_stock_snapshot(body: JubelioStockSnapshotImport, user: Actor, key: RequestKey):
        return store.import_jubelio_stock_snapshot(body.model_dump(mode='json'),user,key)

    @app.get('/api/integrations/jubelio/finished-goods-snapshots', tags=['Integrations'])
    def jubelio_stock_snapshots(user: Actor, limit: Limit = 100,
                                before: Before = None):
        return store.jubelio_stock_snapshots(limit,before)

    @app.get('/api/integrations/jubelio/finished-goods-snapshots/{batch_id}', tags=['Integrations'])
    def jubelio_stock_snapshot(batch_id: str, user: Actor):
        return store.jubelio_stock_snapshot(batch_id)

    @app.get('/api/integrations/jubelio/finished-goods-reconciliation', tags=['Integrations'])
    def jubelio_stock_reconciliation(user: Actor):
        return store.jubelio_stock_reconciliation()

    @app.post('/api/integrations/jubelio/order-snapshots', status_code=201, tags=['Integrations'])
    def import_jubelio_order_snapshot(body: JubelioOrderSnapshotImport, user: Actor, key: RequestKey):
        return store.import_jubelio_order_snapshot(body.model_dump(mode='json'),user,key)

    @app.get('/api/integrations/jubelio/order-snapshots', tags=['Integrations'])
    def jubelio_order_snapshots(user: Actor, limit: Limit = 100,
                                before: Before = None):
        return store.jubelio_order_snapshots(limit,before)

    @app.get('/api/integrations/jubelio/order-snapshots/{batch_id}', tags=['Integrations'])
    def jubelio_order_snapshot(batch_id: str, user: Actor):
        return store.jubelio_order_snapshot(batch_id)

    @app.get('/api/integrations/jubelio/order-summary', tags=['Integrations'])
    def jubelio_order_summary(user: Actor):
        return store.jubelio_order_summary()

    @app.post('/api/integrations/jubelio/return-snapshots', status_code=201, tags=['Integrations'])
    def import_jubelio_return_snapshot(body: JubelioReturnSnapshotImport, user: Actor, key: RequestKey):
        return store.import_jubelio_return_snapshot(body.model_dump(mode='json'),user,key)

    @app.get('/api/integrations/jubelio/return-snapshots', tags=['Integrations'])
    def jubelio_return_snapshots(user: Actor, limit: Limit = 100,
                                 before: Before = None):
        return store.jubelio_return_snapshots(limit,before)

    @app.get('/api/integrations/jubelio/return-snapshots/{batch_id}', tags=['Integrations'])
    def jubelio_return_snapshot(batch_id: str, user: Actor):
        return store.jubelio_return_snapshot(batch_id)

    @app.get('/api/integrations/jubelio/return-summary', tags=['Integrations'])
    def jubelio_return_summary(user: Actor):
        return store.jubelio_return_summary()

    @app.post('/api/integrations/jubelio/listing-snapshots', status_code=201, tags=['Integrations'])
    def import_jubelio_listing_snapshot(body: JubelioListingSnapshotImport, user: Actor, key: RequestKey):
        return store.import_jubelio_listing_snapshot(body.model_dump(mode='json'),user,key)

    @app.get('/api/integrations/jubelio/listing-snapshots', tags=['Integrations'])
    def jubelio_listing_snapshots(user: Actor, limit: Limit = 100,
                                  before: Before = None):
        return store.jubelio_listing_snapshots(limit,before)

    @app.get('/api/integrations/jubelio/listing-snapshots/{batch_id}', tags=['Integrations'])
    def jubelio_listing_snapshot(batch_id: str, user: Actor):
        return store.jubelio_listing_snapshot(batch_id)

    @app.get('/api/integrations/jubelio/listing-summary', tags=['Integrations'])
    def jubelio_listing_summary(user: Actor):
        return store.jubelio_listing_summary()

    @app.post('/api/integrations/mekari/finance-snapshots', status_code=201, tags=['Integrations'])
    def import_mekari_finance_snapshot(body: MekariFinanceSnapshotImport, user: Actor, key: RequestKey):
        return store.import_mekari_finance_snapshot(body.model_dump(mode='json'),user,key)

    @app.get('/api/integrations/mekari/finance-snapshots', tags=['Integrations'])
    def mekari_finance_snapshots(user: Actor, limit: Limit = 100,
                                 before: Before = None):
        return store.mekari_finance_snapshots(limit,before)

    @app.get('/api/integrations/mekari/finance-snapshots/{batch_id}', tags=['Integrations'])
    def mekari_finance_snapshot(batch_id: str, user: Actor):
        return store.mekari_finance_snapshot(batch_id)

    @app.get('/api/integrations/mekari/finance-summary', tags=['Integrations'])
    def mekari_finance_summary(user: Actor):
        return store.mekari_finance_summary()

    @app.post('/api/integrations/mekari/payable-snapshots', status_code=201, tags=['Integrations'])
    def import_mekari_payable_snapshot(body: MekariPayableSnapshotImport, user: Actor, key: RequestKey):
        return store.import_mekari_payable_snapshot(body.model_dump(mode='json'),user,key)

    @app.get('/api/integrations/mekari/payable-snapshots', tags=['Integrations'])
    def mekari_payable_snapshots(user: Actor, limit: Limit = 100,
                                 before: Before = None):
        return store.mekari_payable_snapshots(limit,before)

    @app.get('/api/integrations/mekari/payable-snapshots/{batch_id}', tags=['Integrations'])
    def mekari_payable_snapshot(batch_id: str, user: Actor):
        return store.mekari_payable_snapshot(batch_id)

    @app.get('/api/integrations/mekari/payables-summary', tags=['Integrations'])
    def mekari_payables_summary(user: Actor):
        return store.mekari_payables_summary()

    @app.post('/api/integrations/mekari/receivable-snapshots', status_code=201, tags=['Integrations'])
    def import_mekari_receivable_snapshot(body: MekariReceivableSnapshotImport, user: Actor, key: RequestKey):
        return store.import_mekari_receivable_snapshot(body.model_dump(mode='json'),user,key)

    @app.get('/api/integrations/mekari/receivable-snapshots', tags=['Integrations'])
    def mekari_receivable_snapshots(user: Actor, limit: Limit = 100,
                                    before: Before = None):
        return store.mekari_receivable_snapshots(limit,before)

    @app.get('/api/integrations/mekari/receivable-snapshots/{batch_id}', tags=['Integrations'])
    def mekari_receivable_snapshot(batch_id: str, user: Actor):
        return store.mekari_receivable_snapshot(batch_id)

    @app.get('/api/integrations/mekari/receivables-summary', tags=['Integrations'])
    def mekari_receivables_summary(user: Actor):
        return store.mekari_receivables_summary()

    @app.post('/api/integrations/mekari/payroll-snapshots', status_code=201, tags=['Integrations'])
    def import_mekari_payroll_snapshot(body: MekariPayrollSnapshotImport, user: Actor, key: RequestKey):
        return store.import_mekari_payroll_snapshot(body.model_dump(mode='json'),user,key)

    @app.get('/api/integrations/mekari/payroll-snapshots', tags=['Integrations'])
    def mekari_payroll_snapshots(user: Actor, limit: Limit = 100,
                                 before: Before = None):
        return store.mekari_payroll_snapshots(limit,before)

    @app.get('/api/integrations/mekari/payroll-snapshots/{batch_id}', tags=['Integrations'])
    def mekari_payroll_snapshot(batch_id: str, user: Actor):
        return store.mekari_payroll_snapshot(batch_id)

    @app.get('/api/integrations/mekari/payroll-summary', tags=['Integrations'])
    def mekari_payroll_summary(user: Actor):
        return store.mekari_payroll_summary()

    @app.post('/api/integrations/mekari/payroll-periods/{period_id}/approval-requests',
              status_code=201, tags=['Integrations','People','Approvals'])
    def create_payroll_approval_request(period_id: str, body: PayrollApprovalRequestCreate,
                                        user: Actor, key: RequestKey):
        return store.create_payroll_approval_request(period_id,body.model_dump(mode='json'),user,key)

    @app.get('/api/payroll-approval-requests', tags=['People','Approvals'])
    def payroll_approval_requests(user: Actor, limit: Limit = 100,
                                  before: Before = None,
                                  status: Literal['all','submitted','approved','rejected','cancelled'] = 'all'):
        return store.payroll_approval_requests(status,limit,before)

    @app.get('/api/payroll-approval-requests/{request_id}', tags=['People','Approvals'])
    def payroll_approval_request(request_id: str, user: Actor):
        return store.payroll_approval_request(request_id)

    @app.post('/api/payroll-approval-requests/{request_id}/decisions', status_code=201,
              tags=['People','Approvals'])
    def decide_payroll_approval_request(request_id: str, body: PayrollApprovalDecision,
                                        user: Actor, key: RequestKey):
        return store.decide_payroll_approval_request(request_id,body.model_dump(mode='json'),user,key)

    @app.get('/api/payroll-payment-reconciliation', tags=['People','Finance'])
    def payroll_payment_reconciliation(user: Actor, limit: Limit = 100, offset: Offset = 0,
                                       status: Literal['all','awaiting_payment','paid','exception'] = 'all',
                                       q: Annotated[str, Query(max_length=160)] = ''):
        return store.payroll_payment_reconciliation(status,q,limit,offset)

    @app.get('/api/payroll-accounting-reconciliation', tags=['People','Finance'])
    def payroll_accounting_reconciliation(user: Actor, limit: Limit = 100, offset: Offset = 0,
                                          status: Literal['all','waiting_payment','awaiting_posting',
                                                          'posted','exception'] = 'all',
                                          q: Annotated[str, Query(max_length=160)] = ''):
        return store.payroll_accounting_reconciliation(status,q,limit,offset)

    @app.post("/api/products", status_code=201, tags=["Products"])
    def create_product(body: ProductCreate, user: Actor, key: RequestKey):
        return store.create_product(body.model_dump(mode="json"), user, key)

    @app.get("/api/products", tags=["Products"])
    def products(user: Actor, limit: Limit = 100, offset: Offset = 0):
        return store.products(limit, offset)

    @app.get('/api/work-centers', tags=['Production Capacity'])
    def work_centers(user: Actor, status: Literal['all','active','inactive'] = 'all'):
        return store.work_centers(status)

    @app.get('/api/workforce/employees', tags=['People'])
    def employees(user: Actor, status: Literal['all','active','inactive'] = 'all',
                  department: Annotated[str, Query(max_length=160)] = '',
                  q: Annotated[str, Query(max_length=160)] = '',
                  limit: Limit = 100, offset: Offset = 0):
        return store.employees(status,department,q,limit,offset)

    @app.post('/api/workforce/employees', status_code=201, tags=['People'])
    def create_employee(body: EmployeeCreate, user: Actor, key: RequestKey):
        return store.create_employee(body.model_dump(mode='json'),user,key)

    @app.get('/api/workforce/employees/{employee_id}', tags=['People'])
    def employee(employee_id: str, user: Actor):
        return store.employee(employee_id)

    @app.post('/api/workforce/employees/{employee_id}/changes', status_code=201, tags=['People'])
    def change_employee(employee_id: str, body: EmployeeChange, user: Actor, key: RequestKey):
        return store.change_employee(employee_id,body.model_dump(mode='json'),user,key)

    @app.get('/api/workforce/employees/{employee_id}/history', tags=['People'])
    def employee_history(employee_id: str, user: Actor, limit: Limit = 100,
                         before: Before = None):
        return store.employee_history(employee_id,limit,before)

    @app.get('/api/workforce/attendance', tags=['People'])
    def attendance_records(user: Actor, start_date: date | None = None, end_date: date | None = None,
                           status: Literal['all','present','leave','absent'] = 'all',
                           employee_id: Annotated[str, Query(max_length=160)] = '',
                           department: Annotated[str, Query(max_length=160)] = '',
                           q: Annotated[str, Query(max_length=160)] = '',
                           limit: Limit = 100, offset: Offset = 0):
        start=start_date or end_date or jakarta_today();end=end_date or start
        return store.attendance_records(start,end,status,employee_id,department,q,limit,offset)

    @app.post('/api/workforce/employees/{employee_id}/attendance', status_code=201, tags=['People'])
    def save_attendance(employee_id: str, body: AttendanceSave, user: Actor, key: RequestKey):
        return store.save_attendance(employee_id,body.model_dump(mode='json'),user,key)

    @app.get('/api/workforce/attendance/{attendance_id}/history', tags=['People'])
    def attendance_history(attendance_id: str, user: Actor, limit: Limit = 100,
                           before: Before = None):
        return store.attendance_history(attendance_id,limit,before)

    @app.get('/api/workforce/requests', tags=['People','Approvals'])
    def workforce_requests(user: Actor,
                           status: Literal['all','submitted','approved','rejected','cancelled'] = 'all',
                           kind: Literal['all','leave','overtime'] = 'all',
                           q: Annotated[str, Query(max_length=160)] = '',
                           limit: Limit = 100, offset: Offset = 0):
        return store.workforce_requests(status,kind,q,limit,offset)

    @app.post('/api/workforce/requests', status_code=201, tags=['People','Approvals'])
    def create_workforce_request(body: WorkforceRequestCreate, user: Actor, key: RequestKey):
        return store.create_workforce_request(body.model_dump(mode='json'),user,key)

    @app.get('/api/workforce/requests/{request_id}', tags=['People','Approvals'])
    def workforce_request(request_id: str, user: Actor):
        return store.workforce_request(request_id)

    @app.post('/api/workforce/requests/{request_id}/decisions', status_code=201,
              tags=['People','Approvals'])
    def decide_workforce_request(request_id: str, body: WorkforceRequestDecision,
                                 user: Actor, key: RequestKey):
        return store.decide_workforce_request(request_id,body.model_dump(mode='json'),user,key)

    @app.post('/api/work-centers', status_code=201, tags=['Production Capacity'])
    def create_work_center(body: WorkCenterCreate, user: Actor, key: RequestKey):
        return store.create_work_center(body.model_dump(mode='json'),user,key)

    @app.post('/api/work-centers/{work_center_id}/changes', status_code=201,
              tags=['Production Capacity'])
    def change_work_center(work_center_id: str, body: WorkCenterChange, user: Actor, key: RequestKey):
        return store.change_work_center(work_center_id,body.model_dump(mode='json'),user,key)

    @app.get('/api/routing-standards', tags=['Production Capacity'])
    def routing_standards(user: Actor, product_id: Annotated[str, Query(max_length=160)] = '',
                          stage: Literal['all','cutting','sewing','finishing','qc','rework'] = 'all',
                          limit: Limit = 100, offset: Offset = 0):
        return store.routing_standards(product_id,stage,limit,offset)

    @app.get('/api/products/{product_id}/routing-standards/{stage}', tags=['Production Capacity'])
    def routing_standard(product_id: str,
                         stage: Literal['cutting','sewing','finishing','qc','rework'], user: Actor):
        return store.routing_standard(product_id,stage)

    @app.post('/api/products/{product_id}/routing-standards/{stage}', status_code=201,
              tags=['Production Capacity'])
    def save_routing_standard(product_id: str,
                              stage: Literal['cutting','sewing','finishing','qc','rework'],
                              body: RoutingStandardSave, user: Actor, key: RequestKey):
        return store.save_routing_standard(product_id,stage,body.model_dump(mode='json'),user,key)

    @app.get('/api/work-centers/{work_center_id}/calendar', tags=['Production Capacity'])
    def capacity_calendar(work_center_id: str, user: Actor, start_date: date | None = None,
                          end_date: date | None = None):
        start=start_date or jakarta_today();return store.capacity_calendar(work_center_id,start,end_date or start)

    @app.post('/api/work-centers/{work_center_id}/calendar', status_code=201,
              tags=['Production Capacity'])
    def save_capacity_calendar(work_center_id: str, body: CapacityCalendarSave,
                               user: Actor, key: RequestKey):
        return store.save_capacity_calendar(work_center_id,body.model_dump(mode='json'),user,key)

    @app.get('/api/product-external-mappings', tags=['Products','Integrations'])
    def product_external_mappings(user: Actor, system: Literal['jubelio'],
                                  status: Literal['all','mapped','unmapped'] = 'all',
                                  limit: Limit = 100, offset: Offset = 0):
        return store.product_external_mappings(system,status,limit,offset)

    @app.get('/api/products/{product_id}/external-mappings/{system}', tags=['Products','Integrations'])
    def product_external_mapping(product_id: str, system: Literal['jubelio'], user: Actor):
        return store.product_external_mapping(product_id,system)

    @app.post('/api/products/{product_id}/external-mappings/{system}', status_code=201,
              tags=['Products','Integrations'])
    def save_product_external_mapping(product_id: str, system: Literal['jubelio'],
                                      body: ProductExternalMappingSave, user: Actor, key: RequestKey):
        return store.save_product_external_mapping(product_id,system,body.model_dump(mode='json'),user,key)

    @app.get('/api/products/{product_id}/external-mappings/{system}/history',
             tags=['Products','Integrations'])
    def product_external_mapping_history(product_id: str, system: Literal['jubelio'], user: Actor,
                                         limit: Limit = 100,
                                         before: Before = None):
        return store.product_external_mapping_history(product_id,system,limit,before)

    @app.get('/api/products/{product_id}/bom', tags=['BOM'])
    def bom(product_id: str, user: Actor):
        return store.bom(product_id)

    @app.post('/api/products/{product_id}/bom', status_code=201, tags=['BOM'])
    def save_bom(product_id: str, body: BomSave, user: Actor, key: RequestKey):
        return store.save_bom(product_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/products/{product_id}/bom-history', tags=['BOM'])
    def bom_history(product_id: str, user: Actor, limit: Limit = 100,
                    before: Before = None):
        return store.bom_history(product_id, limit, before)

    @app.get('/api/orders/{order_id}/material-requirements', tags=['BOM'])
    def material_requirements(order_id: str, user: Actor):
        return store.material_requirements(order_id)

    @app.get('/api/orders/{order_id}/production-cost', tags=['Economics'])
    def production_cost(order_id: str, user: Actor):
        return store.production_cost(order_id)

    @app.get('/api/suppliers', tags=['Purchasing'])
    def suppliers(user: Actor, limit: Limit = 100, offset: Offset = 0):
        return store.suppliers(limit, offset)

    @app.post('/api/suppliers', status_code=201, tags=['Purchasing'])
    def create_supplier(body: SupplierCreate, user: Actor, key: RequestKey):
        return store.create_supplier(body.model_dump(mode='json'), user, key)

    @app.get('/api/purchase-orders', tags=['Purchasing'])
    def purchase_orders(user: Actor, limit: Limit = 100, before: Before = None,
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
                                  before: Before = None):
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
                          before: Before = None,
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

    @app.get('/api/material-batches/scan', tags=['Materials'])
    def scan_material_batch(user: Actor, code: Annotated[str, Query(min_length=1,max_length=200)]):
        return store.scan_material_batch(code)

    @app.get('/api/material-batches/{batch_id}/label.svg', tags=['Materials'], response_class=Response)
    def material_batch_label(batch_id: str, user: Actor):
        batch=store.material_batch(batch_id)
        if batch['status']!='active':
            raise DomainError(409,'Label batch yang penerimaannya sudah dikoreksi tidak dapat dicetak.')
        return Response(material_batch_label_svg(batch),media_type='image/svg+xml',headers={
            'Cache-Control':'private, max-age=300','X-Content-Type-Options':'nosniff',
            'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'"})

    @app.post('/api/material-reservations', status_code=201, tags=['Materials'])
    def reserve_material(body: MaterialReservation, user: Actor, key: RequestKey):
        return store.reserve_material(body.model_dump(mode='json'), user, key)

    @app.post('/api/orders/{order_id}/cutting-runs', status_code=201, tags=['Cutting'])
    def create_cutting_run(order_id: str, body: CuttingRunCreate, user: Actor, key: RequestKey):
        return store.create_cutting_run(order_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/cutting-runs', tags=['Cutting'])
    def cutting_runs(order_id: str, user: Actor, limit: Limit = 100,
                     before: Before = None):
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
                before: Before = None):
        return store.bundles(order_id, limit, before)

    @app.get('/api/bundles/scan', tags=['Bundling'])
    def scan_bundle(user: Actor, code: Annotated[str, Query(min_length=1,max_length=200)]):
        return store.scan_bundle(code)

    @app.get('/api/bundles/{bundle_id}', tags=['Bundling'])
    def bundle(bundle_id: str, user: Actor):
        return store.bundle(bundle_id)

    @app.get('/api/bundles/{bundle_id}/label.svg', tags=['Bundling'], response_class=Response)
    def bundle_label(bundle_id: str, user: Actor):
        bundle=store.bundle(bundle_id)
        if bundle['status']!='active':
            raise DomainError(409,'Label bundle yang sudah dikoreksi tidak dapat dicetak.')
        return Response(bundle_label_svg(bundle),media_type='image/svg+xml',headers={
            'Cache-Control':'private, max-age=300','X-Content-Type-Options':'nosniff',
            'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'"})

    @app.get('/api/bundles/{bundle_id}/handoffs', tags=['Bundling'])
    def bundle_handoffs(bundle_id: str, user: Actor, limit: Limit = 100,
                        before: Before = None):
        return store.bundle_handoffs(bundle_id,limit,before)

    @app.post('/api/bundles/{bundle_id}/handoffs', status_code=201, tags=['Bundling'])
    def create_bundle_handoff(bundle_id: str, body: BundleHandoffCreate, user: Actor, key: RequestKey):
        return store.create_bundle_handoff(bundle_id,body.model_dump(mode='json'),user,key)

    @app.post('/api/bundle-handoffs/{handoff_id}/accept', status_code=201, tags=['Bundling'])
    def accept_bundle_handoff(handoff_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.accept_bundle_handoff(handoff_id,body.model_dump(mode='json'),user,key)

    @app.post('/api/bundle-handoffs/{handoff_id}/cancel', status_code=201, tags=['Bundling'])
    def cancel_bundle_handoff(handoff_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.cancel_bundle_handoff(handoff_id,body.model_dump(mode='json'),user,key)

    @app.post('/api/bundles/{bundle_id}/reverse', status_code=201, tags=['Bundling'])
    def reverse_bundle(bundle_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_bundle(bundle_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/bundles/{bundle_id}/sewing-jobs', status_code=201, tags=['Sewing'])
    def create_sewing_job(bundle_id: str, body: SewingJobCreate, user: Actor, key: RequestKey):
        return store.create_sewing_job(bundle_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/sewing-jobs', tags=['Sewing'])
    def sewing_jobs(order_id: str, user: Actor, limit: Limit = 100,
                    before: Before = None):
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
                          before: Before = None):
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
                         before: Before = None):
        return store.final_qc_records(order_id, limit, before)

    @app.get('/api/final-qc-records/{record_id}', tags=['Final QC'])
    def final_qc_record(record_id: str, user: Actor):
        return store.final_qc_record(record_id)

    @app.post('/api/final-qc-records/{record_id}/reverse', status_code=201, tags=['Final QC'])
    def reverse_final_qc_record(record_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_final_qc_record(record_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/final-qc-records/{record_id}/rework-completions', status_code=201, tags=['Final QC'])
    def create_rework_completion(record_id: str, body: ReworkCompletionCreate, user: Actor, key: RequestKey):
        return store.create_rework_completion(record_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/final-qc-records/{record_id}/rework-completions', tags=['Final QC'])
    def final_qc_rework_completions(record_id: str, user: Actor, limit: Limit = 100,
                                    before: Before = None):
        return store.final_qc_rework_completions(record_id, limit, before)

    @app.get('/api/orders/{order_id}/rework-completions', tags=['Final QC'])
    def rework_completions(order_id: str, user: Actor, limit: Limit = 100,
                           before: Before = None):
        return store.rework_completions(order_id, limit, before)

    @app.get('/api/rework-completions/{completion_id}', tags=['Final QC'])
    def rework_completion(completion_id: str, user: Actor):
        return store.rework_completion(completion_id)

    @app.post('/api/rework-completions/{completion_id}/qc-records', status_code=201, tags=['Final QC'])
    def create_rework_reinspection_record(completion_id: str, body: FinalQcRecordCreate,
                                          user: Actor, key: RequestKey):
        return store.create_rework_reinspection_record(completion_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/rework-completions/{completion_id}/reverse', status_code=201, tags=['Final QC'])
    def reverse_rework_completion(completion_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_rework_completion(completion_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/final-qc-records/{record_id}/finished-goods-receipts', status_code=201, tags=['Finished Goods'])
    def create_finished_goods_receipt(record_id: str, body: FinishedGoodsReceiptCreate, user: Actor, key: RequestKey):
        return store.create_finished_goods_receipt(record_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/finished-goods-receipts', tags=['Finished Goods'])
    def finished_goods_receipts(order_id: str, user: Actor, limit: Limit = 100,
                                before: Before = None):
        return store.finished_goods_receipts(order_id, limit, before)

    @app.get('/api/finished-goods-receipts/scan', tags=['Finished Goods'])
    def scan_finished_goods_receipt(user: Actor,
                                    code: Annotated[str, Query(min_length=1,max_length=200)]):
        return store.scan_finished_goods_receipt(code)

    @app.get('/api/finished-goods-receipts/{receipt_id}', tags=['Finished Goods'])
    def finished_goods_receipt(receipt_id: str, user: Actor):
        return store.finished_goods_receipt(receipt_id)

    @app.get('/api/finished-goods-receipts/{receipt_id}/traceability', tags=['Finished Goods'])
    def finished_goods_traceability(receipt_id: str, user: Actor, limit: Limit = 100,
            before_time: Annotated[str | None, Query(min_length=1,max_length=50)] = None,
            before_event: Annotated[str | None, Query(min_length=1,max_length=100)] = None):
        return store.finished_goods_traceability(receipt_id, limit, before_time, before_event)

    @app.get('/api/finished-goods-receipts/{receipt_id}/label.svg', tags=['Finished Goods'],
             response_class=Response)
    def finished_goods_receipt_label(receipt_id: str, user: Actor):
        receipt=store.finished_goods_receipt(receipt_id)
        if receipt['status']!='active':
            raise DomainError(409,'Label penerimaan barang jadi yang sudah dikoreksi tidak dapat dicetak.')
        return Response(finished_goods_label_svg(receipt),media_type='image/svg+xml',headers={
            'Cache-Control':'private, max-age=300','X-Content-Type-Options':'nosniff',
            'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'"})

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
                            before: Before = None):
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
                                 before: Before = None):
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
                          before: Before = None):
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
                          before: Before = None):
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
                              before: Before = None):
        return store.marketplace_shipments(order_id, limit, before)

    @app.get('/api/marketplace-shipments/{shipment_id}', tags=['Marketplace'])
    def marketplace_shipment(shipment_id: str, user: Actor):
        return store.marketplace_shipment(shipment_id)

    @app.post('/api/marketplace-shipments/{shipment_id}/reverse', status_code=201, tags=['Marketplace'])
    def reverse_marketplace_shipment(shipment_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_marketplace_shipment(shipment_id, body.model_dump(mode='json'), user, key)

    @app.post('/api/marketplace-shipments/{shipment_id}/sale-settlements', status_code=201, tags=['Economics'])
    def create_marketplace_sale_settlement(shipment_id: str, body: MarketplaceSaleSettlementCreate,
                                           user: Actor, key: RequestKey):
        return store.create_marketplace_sale_settlement(shipment_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/sale-settlements', tags=['Economics'])
    def marketplace_sale_settlements(order_id: str, user: Actor, limit: Limit = 100,
                                     before: Before = None):
        return store.marketplace_sale_settlements(order_id, limit, before)

    @app.get('/api/marketplace-sale-settlements/{settlement_id}', tags=['Economics'])
    def marketplace_sale_settlement(settlement_id: str, user: Actor):
        return store.marketplace_sale_settlement(settlement_id)

    @app.post('/api/marketplace-sale-settlements/{settlement_id}/reverse', status_code=201, tags=['Economics'])
    def reverse_marketplace_sale_settlement(settlement_id: str, body: ReversalCreate,
                                            user: Actor, key: RequestKey):
        return store.reverse_marketplace_sale_settlement(settlement_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/contribution-margin', tags=['Economics'])
    def contribution_margin(order_id: str, user: Actor):
        return store.contribution_margin(order_id)

    @app.get('/api/demand-forecast', tags=['Economics'])
    def demand_forecast(user: Actor, as_of: date | None = None,
                        window_days: Annotated[int, Query(ge=7, le=90)] = 28,
                        horizon_days: Annotated[int, Query(ge=1, le=180)] = 30,
                        query: Annotated[str, Query(max_length=160)] = '',
                        marketplace: Annotated[str, Query(max_length=160)] = '',
                        limit: Limit = 100, offset: Offset = 0):
        return store.demand_forecast(as_of or jakarta_today(), window_days, horizon_days,
                                     query, marketplace, limit, offset)

    @app.get('/api/return-insights', tags=['Economics'])
    def return_insights(user: Actor, as_of: date | None = None,
                        window_days: Annotated[int, Query(ge=7, le=365)] = 90,
                        query: Annotated[str, Query(max_length=160)] = '',
                        marketplace: Annotated[str, Query(max_length=160)] = '',
                        limit: Limit = 100, offset: Offset = 0):
        return store.return_insights(as_of or jakarta_today(), window_days, query, marketplace, limit, offset)

    @app.get('/api/size-demand-insights', tags=['Economics'])
    def size_demand_insights(user: Actor, as_of: date | None = None,
                             window_days: Annotated[int, Query(ge=7, le=90)] = 28,
                             lookahead_days: Annotated[int, Query(ge=1, le=180)] = 30,
                             query: Annotated[str, Query(max_length=160)] = '',
                             marketplace: Annotated[str, Query(max_length=160)] = '',
                             limit: Limit = 100, offset: Offset = 0):
        return store.size_demand_insights(as_of or jakarta_today(), window_days, lookahead_days,
                                          query, marketplace, limit, offset)

    @app.get('/api/dead-stock-insights', tags=['Economics'])
    def dead_stock_insights(user: Actor, as_of: date | None = None,
                            inactivity_days: Annotated[int, Query(ge=7, le=730)] = 90,
                            query: Annotated[str, Query(max_length=160)] = '',
                            marketplace: Annotated[str, Query(max_length=160)] = '',
                            status: Literal['all','dead_stock_candidate','aging_no_sales','moving'] =
                                'dead_stock_candidate',
                            limit: Limit = 100, offset: Offset = 0):
        return store.dead_stock_insights(as_of or jakarta_today(), inactivity_days, query,
                                         marketplace, status, limit, offset)

    @app.get('/api/stock-adjustment-insights', tags=['Economics'])
    def stock_adjustment_insights(user: Actor, as_of: date | None = None,
                                  window_days: Annotated[int, Query(ge=7, le=365)] = 30,
                                  quantity_threshold: Annotated[int, Query(ge=1, le=1_000_000_000)] = 5,
                                  percentage_threshold: Annotated[int, Query(ge=1, le=100)] = 20,
                                  repeat_threshold: Annotated[int, Query(ge=2, le=100)] = 3,
                                  query: Annotated[str, Query(max_length=160)] = '',
                                  location: Annotated[str, Query(max_length=160)] = '',
                                  stock_status: Literal['all','sellable','hold','damaged'] = 'all',
                                  source: Literal['all','manual','stock_count'] = 'all',
                                  record_status: Literal['all','active','corrected'] = 'all',
                                  classification: Literal['flagged','high','review','normal','all'] = 'flagged',
                                  limit: Limit = 100, offset: Offset = 0):
        return store.stock_adjustment_insights(as_of or jakarta_today(),window_days,quantity_threshold,
            percentage_threshold,repeat_threshold,query,location,stock_status,source,record_status,
            classification,limit,offset)

    @app.get('/api/supplier-performance-insights', tags=['Economics'])
    def supplier_performance_insights(user: Actor, as_of: date | None = None,
                                      window_days: Annotated[int, Query(ge=7, le=730)] = 90,
                                      query: Annotated[str, Query(max_length=160)] = '',
                                      status: Literal['all','attention','healthy'] = 'attention',
                                      limit: Limit = 100, offset: Offset = 0):
        return store.supplier_performance_insights(as_of or jakarta_today(),window_days,query,status,
                                                   limit,offset)

    @app.get('/api/material-price-insights', tags=['Economics'])
    def material_price_insights(user: Actor, as_of: date | None = None,
                                window_days: Annotated[int, Query(ge=7, le=730)] = 90,
                                query: Annotated[str, Query(max_length=160)] = '',
                                status: Literal['all','changed','increased','decreased','stable',
                                                'single_observation'] = 'changed',
                                limit: Limit = 100, offset: Offset = 0):
        return store.material_price_insights(as_of or jakarta_today(),window_days,query,status,
                                             limit,offset)

    @app.get('/api/purchase-commitment-insights', tags=['Economics'])
    def purchase_commitment_insights(user: Actor, as_of: date | None = None,
                                     due_soon_days: Annotated[int, Query(ge=1, le=90)] = 7,
                                     query: Annotated[str, Query(max_length=160)] = '',
                                     status: Literal['all','open','overdue','due_soon','scheduled',
                                                     'fulfilled'] = 'open',
                                     limit: Limit = 100, offset: Offset = 0):
        return store.purchase_commitment_insights(as_of or jakarta_today(),due_soon_days,query,status,
                                                  limit,offset)

    @app.get('/api/wip-ageing-insights', tags=['Production'])
    def wip_ageing_insights(user: Actor, as_of: date | None = None,
                            idle_days: Annotated[int, Query(ge=1, le=365)] = 7,
                            query: Annotated[str, Query(max_length=160)] = '',
                            owner_id: Annotated[str, Query(max_length=160)] = '',
                            stage: Literal['all','planned','cutting','sewing','finishing','qc','rework'] = 'all',
                            status: Literal['all','attention','stalled','overdue','blocked','rework','moving'] =
                                'attention',
                            limit: Limit = 100, offset: Offset = 0):
        return store.wip_ageing_insights(as_of or jakarta_today(),idle_days,query,owner_id,stage,
                                         status,limit,offset)

    @app.get('/api/capacity-plan', tags=['Production Capacity'])
    def capacity_plan(user: Actor, as_of: date | None = None,
                      horizon_days: Annotated[int, Query(ge=1, le=90)] = 14,
                      warning_percent: Annotated[int, Query(ge=1, le=100)] = 80,
                      work_center_id: Annotated[str, Query(max_length=160)] = '',
                      stage: Literal['all','cutting','sewing','finishing','qc','rework'] = 'all',
                      status: Literal['all','attention','overloaded','deadline_risk','near_capacity',
                                      'available','idle'] = 'attention',
                      limit: Limit = 100, offset: Offset = 0):
        return store.capacity_plan(as_of or jakarta_today(),horizon_days,warning_percent,
                                   work_center_id,stage,status,limit,offset)

    @app.get('/api/production-quality-insights', tags=['Production','Quality'])
    def production_quality_insights(user: Actor, as_of: date | None = None,
                                    window_days: Annotated[int, Query(ge=7, le=365)] = 30,
                                    warning_percent: Annotated[int, Query(ge=1, le=100)] = 5,
                                    change_threshold: Annotated[int, Query(ge=1, le=100)] = 1,
                                    query: Annotated[str, Query(max_length=160)] = '',
                                    assignment_type: Literal['all','internal','makloon'] = 'all',
                                    status: Literal['all','attention','healthy'] = 'attention',
                                    limit: Limit = 100, offset: Offset = 0):
        return store.production_quality_insights(as_of or jakarta_today(),window_days,
            warning_percent,change_threshold,query,assignment_type,status,limit,offset)

    @app.get('/api/replenishment-recommendations', tags=['Economics'])
    def replenishment_recommendations(user: Actor, as_of: date | None = None,
                                      window_days: Annotated[int, Query(ge=7, le=90)] = 28,
                                      lead_time_days: Annotated[int, Query(ge=1, le=180)] = 14,
                                      review_period_days: Annotated[int, Query(ge=1, le=180)] = 30,
                                      safety_stock_days: Annotated[int, Query(ge=0, le=90)] = 7,
                                      batch_multiple: Annotated[int, Query(ge=1, le=100_000)] = 1,
                                      query: Annotated[str, Query(max_length=160)] = '',
                                      marketplace: Annotated[str, Query(max_length=160)] = '',
                                      limit: Limit = 100, offset: Offset = 0):
        return store.replenishment_recommendations(as_of or jakarta_today(), window_days,
            lead_time_days, review_period_days, safety_stock_days, batch_multiple,
            query, marketplace, limit, offset)

    @app.post('/api/marketplace-shipments/{shipment_id}/returns', status_code=201, tags=['Marketplace'])
    def create_marketplace_return(shipment_id: str, body: MarketplaceReturnCreate, user: Actor, key: RequestKey):
        return store.create_marketplace_return(shipment_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/orders/{order_id}/marketplace-returns', tags=['Marketplace'])
    def marketplace_returns(order_id: str, user: Actor, limit: Limit = 100,
                            before: Before = None):
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
                                   before: Before = None):
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
                                    before: Before = None):
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
                            before: Before = None):
        return store.consumption_history(order_id, limit, before)

    @app.get('/api/orders/{order_id}/material-reservations', tags=['Materials'])
    def order_reservations(order_id: str, user: Actor, limit: Limit = 100, offset: Offset = 0):
        return store.order_reservations(order_id, limit, offset)

    @app.get('/api/orders/{order_id}/reservation-history', tags=['Materials'])
    def reservation_history(order_id: str, user: Actor, limit: Limit = 100,
                            before: Before = None):
        return store.reservation_history(order_id, limit, before)

    @app.get('/api/material-batches/{batch_id}', tags=['Materials'])
    def material_batch(batch_id: str, user: Actor):
        return store.material_batch(batch_id)

    @app.get('/api/material-batches/{batch_id}/traceability', tags=['Materials'])
    def material_batch_traceability(batch_id: str, user: Actor, limit: Limit = 100,
            before_time: Annotated[str | None, Query(min_length=1,max_length=50)] = None,
            before_event: Annotated[str | None, Query(min_length=1,max_length=100)] = None):
        return store.material_batch_traceability(batch_id, limit, before_time, before_event)

    @app.post('/api/material-issues', status_code=201, tags=['Materials'])
    def issue_material(body: MaterialIssue, user: Actor, key: RequestKey):
        return store.issue_material(body.model_dump(mode='json'), user, key)

    @app.post('/api/material-movements/{movement_id}/reverse', status_code=201, tags=['Materials'])
    def reverse_material(movement_id: str, body: ReversalCreate, user: Actor, key: RequestKey):
        return store.reverse_material(movement_id, body.model_dump(mode='json'), user, key)

    @app.get('/api/material-batches/{batch_id}/movements', tags=['Materials'])
    def batch_material_history(batch_id: str, user: Actor, limit: Limit = 100,
                               before: Before = None):
        return store.material_history(batch_id=batch_id, limit=limit, before=before)

    @app.get('/api/orders/{order_id}/material-movements', tags=['Materials'])
    def order_material_history(order_id: str, user: Actor, limit: Limit = 100,
                               before: Before = None):
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
               before: Before = None):
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
                      before: Before = None):
        return store.order_changes(order_id, limit, before)

    @app.post("/api/orders/{order_id}/change-requests", status_code=201, tags=["Approvals"])
    def create_production_change_request(order_id: str, body: ProductionChangeRequestCreate,
                                         user: Actor, key: RequestKey):
        return store.create_production_change_request(order_id, body.model_dump(mode="json"), user, key)

    @app.get("/api/orders/{order_id}/change-requests", tags=["Approvals"])
    def production_change_requests(order_id: str, user: Actor, limit: Limit = 100,
                                   before: Before = None):
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
