from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Quantity = Annotated[int, Field(strict=True, gt=0, le=1_000_000_000)]
Stage = Literal["planned", "cutting", "sewing", "finishing", "qc", "rework", "reject", "warehouse"]
Role = Literal["admin", "operator", "viewer"]
CapacityStage = Literal["cutting", "sewing", "finishing", "qc", "rework"]
STAGES = ("planned", "cutting", "sewing", "finishing", "qc", "rework", "reject", "warehouse")
# Perpindahan generik yang menyentuh keputusan rework sengaja tidak ada di sini. QC hanya boleh
# mengirim pcs ke rework melalui catatan Final QC, lalu pengembaliannya ke QC hanya boleh melalui
# POST /api/final-qc-records/{id}/rework-completions. Dengan begitu kedua arah menyimpan lineage
# inspeksi asalnya. Pembalikan tidak memakai TRANSITIONS, sehingga koreksi data lama tetap berjalan.
TRANSITIONS = {("planned", "cutting"), ("cutting", "sewing"), ("sewing", "finishing"),
               ("finishing", "qc"), ("qc", "warehouse"), ("qc", "reject")}


def to_utc(value, label):
    """Konversi datetime ke UTC, atau tolak sebagai kesalahan validasi (HTTP 422).

    `datetime.astimezone(timezone.utc)` menjawab `OverflowError` saat hasil konversinya jatuh di
    luar rentang yang dapat diwakili -- 0001-01-01T00:00:00Z sampai 9999-12-31T23:59:59.999999Z.
    Offset yang sah di sisi input tetap dapat mendorong hasilnya melewati batas itu: tengah malam
    1 Januari tahun 1 di zona +14:00 adalah 31 Desember tahun 0 dalam UTC. Pydantic hanya
    menerjemahkan `ValueError` menjadi 422, jadi tanpa penerjemahan ini permintaan yang lolos
    parsing datetime menjawab 500 ke klien.

    Hanya `OverflowError` yang ditangkap, dan hanya di sekitar satu operasi konversi, agar
    kesalahan lain tetap muncul sebagai bug.
    """
    if value.utcoffset() is None:
        raise ValueError(f'{label} harus menyertakan zona waktu.')
    try:
        return value.astimezone(timezone.utc)
    except OverflowError:
        raise ValueError(f'{label} di luar jangkauan setelah dikonversi ke UTC '
                         '(0001-01-01 sampai 9999-12-31).') from None


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProductCreate(Input):
    sku: Text
    name: Text
    color: str = Field(default="", max_length=80)
    size: str = Field(default="", max_length=40)
    # M01 (issue #43): klasifikasi opsional; relasi divalidasi di store
    # (kategori -> subkategori -> tipe harus konsisten).
    category_id: str | None = Field(default=None, max_length=160)
    subcategory_id: str | None = Field(default=None, max_length=160)
    type_id: str | None = Field(default=None, max_length=160)
    series_id: str | None = Field(default=None, max_length=160)
    color_id: str | None = Field(default=None, max_length=160)
    size_id: str | None = Field(default=None, max_length=160)
    uom_code: str = Field(default="PCS", max_length=16)

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value):
        return value.upper()

    @field_validator("uom_code")
    @classmethod
    def normalize_uom(cls, value):
        return value.upper()


class ProductUpdate(Input):
    """Ubah master produk. SKU identitas tidak dapat diubah.

    Field klasifikasi: None = tidak diubah; string kosong = lepas (NULL);
    selain itu harus merujuk master aktif yang relasinya valid.
    """

    name: Text | None = None
    color: str | None = Field(default=None, max_length=80)
    size: str | None = Field(default=None, max_length=40)
    category_id: str | None = Field(default=None, max_length=160)
    subcategory_id: str | None = Field(default=None, max_length=160)
    type_id: str | None = Field(default=None, max_length=160)
    series_id: str | None = Field(default=None, max_length=160)
    color_id: str | None = Field(default=None, max_length=160)
    size_id: str | None = Field(default=None, max_length=160)
    uom_code: str | None = Field(default=None, max_length=16)
    active: bool | None = None

    @field_validator("uom_code")
    @classmethod
    def normalize_uom(cls, value):
        return value.upper() if value else value


# ---------------------------------------------------------------------------
# M01 master katalog (issue #43): satuan, klasifikasi produk, warna/ukuran,
# klasifikasi bahan, dan template BOM. Kode master dinormalisasi UPPERCASE dan
# immutable setelah dibuat (identitas); yang boleh berubah hanya nama,
# relasi induk, atribut deskriptif, dan status aktif.
# ---------------------------------------------------------------------------


class MasterCreate(Input):
    code: Text
    name: Text

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        return value.upper()


class MasterUpdate(Input):
    name: Text | None = None
    active: bool | None = None


class UomCreate(MasterCreate):
    # range_text menyimpan verbatim metadata legacy "Range"; maknanya BELUM
    # terverifikasi dan dilarang dipakai sebagai faktor konversi.
    range_text: str = Field(default="", max_length=160)
    note: str = Field(default="", max_length=1000)


class UomUpdate(MasterUpdate):
    range_text: str | None = Field(default=None, max_length=160)
    note: str | None = Field(default=None, max_length=1000)


class ProductCategoryCreate(MasterCreate):
    pass


class ProductCategoryUpdate(MasterUpdate):
    pass


class ProductSubcategoryCreate(MasterCreate):
    category_id: Text


class ProductSubcategoryUpdate(MasterUpdate):
    category_id: Text | None = None


class ProductTypeCreate(MasterCreate):
    subcategory_id: Text


class ProductTypeUpdate(MasterUpdate):
    subcategory_id: Text | None = None


class ProductSeriesCreate(MasterCreate):
    pass


class ProductSeriesUpdate(MasterUpdate):
    pass


class ColorCreate(MasterCreate):
    pass


class ColorUpdate(MasterUpdate):
    pass


class SizeCreate(MasterCreate):
    sort_order: Annotated[int, Field(strict=True, ge=0, le=9999)] = 0


class SizeUpdate(MasterUpdate):
    sort_order: Annotated[int, Field(strict=True, ge=0, le=9999)] | None = None


class MaterialClassCreate(MasterCreate):
    level: Literal[1, 2, 3]
    parent_id: Text | None = None

    @model_validator(mode="after")
    def check_hierarchy(self):
        if self.level == 1 and self.parent_id is not None:
            raise ValueError("Klasifikasi level 1 tidak memiliki induk.")
        if self.level > 1 and not self.parent_id:
            raise ValueError("Klasifikasi level 2/3 wajib memiliki induk.")
        return self


class MaterialClassUpdate(MasterUpdate):
    # Level tidak dapat diubah setelah dibuat (menjaga hierarki existing);
    # pemindahan induk divalidasi di store terhadap level yang tersimpan.
    parent_id: str | None = Field(default=None, max_length=160)


class UserCreate(Input):
    name: Text
    role: Role
    preset: str | None = Field(default=None, max_length=80)
    permissions: list[str] | None = None
    business_units: list[str] | None = None
    all_units: bool | None = None


class UserPermissionsSet(Input):
    permissions: list[str]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class UserPresetSet(Input):
    preset: str = Field(min_length=1, max_length=80)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class UserUnitsSet(Input):
    business_unit_ids: list[str] = Field(default_factory=list)
    all_units: bool = False
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class BrowserSessionLogin(Input):
    api_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]


class OrderLine(Input):
    product_id: Text
    quantity: Quantity


class OrderCreate(Input):
    reference: Text
    title: Text
    owner_id: Text
    due_date: date
    business_unit_id: Text | None = None
    lines: list[OrderLine] = Field(min_length=1, max_length=100)
    # P02 (issue #49): metadata rencana cutting; plan dibuat otomatis berstatus
    # draft saat order dibuat. Kode rencana = reference order (lihat mapping).
    plan_note: str = Field(default="", max_length=1000)
    plan_start_date: date | None = None

    @field_validator("lines")
    @classmethod
    def unique_products(cls, lines):
        if len({line.product_id for line in lines}) != len(lines):
            raise ValueError("Gabungkan SKU yang sama menjadi satu baris.")
        return lines


class MovementCreate(Input):
    line_id: Text
    from_stage: Stage
    to_stage: Stage
    quantity: Quantity
    reason: str = Field(default="", max_length=1000)


class ReversalCreate(Input):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class IssueCreate(Input):
    line_id: Text
    stage: Stage
    owner_id: Text
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class IssueResolve(Input):
    resolution: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class WorkCenterCreate(Input):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    name: Text
    stage: CapacityStage
    daily_minutes: Annotated[int, Field(strict=True, ge=1, le=100_000)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @field_validator('code')
    @classmethod
    def normalize_code(cls,value):
        return value.upper()


class WorkCenterChange(Input):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    name: Text
    daily_minutes: Annotated[int, Field(strict=True, ge=1, le=100_000)]
    active: Annotated[bool, Field(strict=True)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class RoutingStandardSave(Input):
    expected_revision: Annotated[int, Field(strict=True, ge=0)]
    work_center_id: Text
    minutes_per_unit: Annotated[str, StringConstraints(
        pattern=r"^[0-9]{1,5}(\.[0-9]{1,3})?$", max_length=9)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @field_validator('minutes_per_unit')
    @classmethod
    def normalize_minutes(cls,value):
        amount=Decimal(value)
        if not 0 < amount <= 100_000:
            raise ValueError('Menit standar harus lebih dari nol dan maksimal 100.000.')
        return format(amount,'.3f')


class CapacityCalendarSave(Input):
    work_date: date
    expected_revision: Annotated[int, Field(strict=True, ge=0)]
    available_minutes: Annotated[int, Field(strict=True, ge=0, le=100_000)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class EmployeeCreate(Input):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    name: Text
    department: Text
    # M02: tautan opsional ke jabatan dan unit usaha. Wajib divalidasi server-side;
    # department tetap teks bebas dan TIDAK disamakan dengan jabatan/unit.
    position_id: Text | None = None
    business_unit_id: Text | None = None
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @field_validator('code')
    @classmethod
    def normalize_code(cls,value):
        return value.upper()


class EmployeeChange(Input):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    name: Text
    department: Text
    active: Annotated[bool, Field(strict=True)]
    position_id: Text | None = None
    business_unit_id: Text | None = None
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class AttendanceSave(Input):
    work_date: date
    expected_revision: Annotated[int, Field(strict=True, ge=0)]
    status: Literal['present','leave','absent']
    clock_in: time | None = None
    clock_out: time | None = None
    overtime_minutes: Annotated[int, Field(strict=True, ge=0, le=720)] = 0
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] = ''
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @model_validator(mode='after')
    def valid_times(self):
        if self.status=='present':
            if self.clock_in is None or self.clock_out is None:
                raise ValueError('Jam masuk dan pulang wajib untuk status hadir.')
            if self.clock_in.tzinfo is not None or self.clock_out.tzinfo is not None:
                raise ValueError('Jam kehadiran memakai waktu lokal tanpa zona waktu.')
            if self.clock_out<=self.clock_in:
                raise ValueError('Jam pulang harus setelah jam masuk pada hari yang sama.')
        elif self.clock_in is not None or self.clock_out is not None or self.overtime_minutes:
            raise ValueError('Cuti atau absen tidak boleh memuat jam kerja maupun lembur.')
        return self


class WorkforceRequestCreate(Input):
    employee_id: Text
    kind: Literal['leave','overtime']
    start_date: date
    end_date: date
    overtime_minutes: Annotated[int, Field(strict=True, ge=0, le=720)] = 0
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @model_validator(mode='after')
    def valid_request(self):
        if self.start_date>self.end_date:
            raise ValueError('Tanggal selesai tidak boleh sebelum tanggal mulai.')
        if (self.end_date-self.start_date).days>=366:
            raise ValueError('Rentang permintaan maksimal 366 hari.')
        if self.kind=='leave' and self.overtime_minutes:
            raise ValueError('Permintaan cuti tidak boleh memuat menit lembur.')
        if self.kind=='overtime':
            if self.start_date!=self.end_date:
                raise ValueError('Permintaan lembur hanya boleh untuk satu tanggal.')
            if not self.overtime_minutes:
                raise ValueError('Menit lembur harus lebih dari nol.')
        return self


class WorkforceRequestDecision(Input):
    status: Literal['approved','rejected','cancelled']
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class PayrollApprovalRequestCreate(Input):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class PayrollApprovalDecision(Input):
    status: Literal['approved','rejected','cancelled']
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class OrderChange(Input):
    owner_id: Text
    due_date: date
    expected_revision: Annotated[int, Field(strict=True, ge=0)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class ProductionChangeRequestCreate(OrderChange):
    reference: Text


class InvestigationCreate(Input):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=1000)]
    as_of: date = Field(default_factory=date.today)
    window_days: Annotated[int, Field(strict=True, ge=7, le=90)] = 28
    lead_time_days: Annotated[int, Field(strict=True, ge=1, le=180)] = 14
    review_period_days: Annotated[int, Field(strict=True, ge=1, le=180)] = 30
    safety_stock_days: Annotated[int, Field(strict=True, ge=0, le=90)] = 7
    batch_multiple: Annotated[int, Field(strict=True, ge=1, le=100_000)] = 1


class AiInvestigationFeedbackCreate(Input):
    rating: Literal['helpful','not_helpful']
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class AiActionProposalCreate(InvestigationCreate):
    investigation_id: Text | None = None
    action_kind: Literal['create_production_order','create_purchase_request']
    subject_id: Text
    reference: Text
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    title: Text | None = None
    owner_id: Text | None = None
    due_date: date | None = None
    required_date: date | None = None
    estimated_value: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,13}(\.[0-9]{1,2})?$", max_length=16)] | None = None

    @model_validator(mode='after')
    def action_fields(self):
        if self.action_kind=='create_production_order':
            if self.title is None or self.owner_id is None or self.due_date is None:
                raise ValueError('Proposal order produksi memerlukan judul, PIC, dan target selesai.')
            if self.required_date is not None or self.estimated_value is not None:
                raise ValueError('Proposal order produksi tidak memakai tanggal kebutuhan atau estimasi PR.')
        else:
            if self.required_date is None or self.estimated_value is None:
                raise ValueError('Proposal PR memerlukan tanggal kebutuhan dan estimasi nilai.')
            if self.title is not None or self.owner_id is not None or self.due_date is not None:
                raise ValueError('Proposal PR tidak memakai judul, PIC, atau target produksi.')
            amount=Decimal(self.estimated_value)
            if not 0 < amount <= 1_000_000_000_000:
                raise ValueError('Estimasi total harus positif dan maksimal Rp1.000.000.000.000.')
            self.estimated_value=format(amount,'.2f')
        return self


class AiActionProposalDecision(ReversalCreate):
    status: Literal['approved','rejected','cancelled']
    expected_revision: Annotated[int, Field(strict=True, ge=1)]


IntegrationSystem = Literal['jubelio','mekari']
IntegrationScope = Literal['orders','finished_goods','returns','listings',
                           'finance_summary','payables','receivables','payroll']


class IntegrationSyncRunCreate(Input):
    system: IntegrationSystem
    scope: IntegrationScope
    status: Literal['succeeded','failed']
    started_at: datetime
    finished_at: datetime
    records_read: Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
    records_written: Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
    external_cursor: str = Field(default='', max_length=1000)
    error: str = Field(default='', max_length=1000)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @field_validator('started_at','finished_at')
    @classmethod
    def timezone_required(cls, value):
        return to_utc(value, 'Waktu sinkronisasi')

    @model_validator(mode='after')
    def valid_contract(self):
        scopes={'jubelio':{'orders','finished_goods','returns','listings'},
                'mekari':{'finance_summary','payables','receivables','payroll'}}
        if self.scope not in scopes[self.system]:
            raise ValueError('Scope tidak sesuai dengan sistem sumber.')
        if self.finished_at < self.started_at:
            raise ValueError('Waktu selesai tidak boleh sebelum waktu mulai.')
        if self.status=='failed' and not self.error:
            raise ValueError('Sinkronisasi gagal memerlukan pesan error.')
        if self.status=='succeeded' and self.error:
            raise ValueError('Sinkronisasi berhasil tidak boleh memiliki pesan error.')
        return self


class ProductExternalMappingSave(Input):
    expected_revision: Annotated[int, Field(strict=True, ge=0)]
    action: Literal['mapped','unmapped']
    external_id: str = Field(default='', max_length=160)
    external_sku: str = Field(default='', max_length=160)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @model_validator(mode='after')
    def mapping_fields(self):
        if self.action=='mapped' and (not self.external_id or not self.external_sku):
            raise ValueError('Mapping aktif memerlukan ID eksternal dan SKU eksternal.')
        if self.action=='unmapped' and (self.external_id or self.external_sku):
            raise ValueError('Pelepasan mapping tidak boleh membawa ID atau SKU eksternal.')
        return self


class JubelioStockSnapshotItem(Input):
    external_id: Text
    external_sku: Text
    sellable_quantity: Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
    reserved_quantity: Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]

    @model_validator(mode='after')
    def reserved_within_sellable(self):
        if self.reserved_quantity>self.sellable_quantity:
            raise ValueError('Reserved Jubelio tidak boleh melebihi sellable.')
        return self


class JubelioStockSnapshotImport(Input):
    started_at: datetime
    finished_at: datetime
    snapshot_at: datetime
    external_cursor: str = Field(default='', max_length=1000)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    items: list[JubelioStockSnapshotItem] = Field(max_length=500)

    @field_validator('started_at','finished_at','snapshot_at')
    @classmethod
    def timezone_required(cls, value):
        return to_utc(value, 'Waktu snapshot')

    @model_validator(mode='after')
    def valid_snapshot(self):
        if self.finished_at<self.started_at:
            raise ValueError('Waktu selesai tidak boleh sebelum waktu mulai.')
        ids=[item.external_id for item in self.items]
        skus=[item.external_sku.casefold() for item in self.items]
        if len(ids)!=len(set(ids)) or len(skus)!=len(set(skus)):
            raise ValueError('Snapshot tidak boleh memuat ID atau SKU eksternal ganda.')
        return self


class JubelioOrderSnapshotLine(Input):
    external_id: Text
    external_sku: Text
    quantity: Quantity
    gross_revenue: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,13}(\.[0-9]{1,2})?$", max_length=16)]

    @field_validator('gross_revenue')
    @classmethod
    def normalize_revenue(cls, value):
        amount=Decimal(value)
        if amount>1_000_000_000_000:
            raise ValueError('Pendapatan kotor maksimal Rp1.000.000.000.000 per baris.')
        return format(amount,'.2f')


class JubelioOrderSnapshotRecord(Input):
    external_order_id: Text
    external_order_reference: Text
    marketplace: Text
    status: Literal['pending','processing','completed','cancelled']
    ordered_at: datetime
    lines: list[JubelioOrderSnapshotLine] = Field(min_length=1, max_length=100)

    @field_validator('ordered_at')
    @classmethod
    def timezone_required(cls, value):
        return to_utc(value, 'Waktu order')

    @model_validator(mode='after')
    def unique_products(self):
        ids=[line.external_id for line in self.lines]
        skus=[line.external_sku.casefold() for line in self.lines]
        if len(ids)!=len(set(ids)) or len(skus)!=len(set(skus)):
            raise ValueError('Satu order tidak boleh memuat ID atau SKU eksternal ganda.')
        return self


class JubelioOrderSnapshotImport(Input):
    started_at: datetime
    finished_at: datetime
    snapshot_at: datetime
    external_cursor: str = Field(default='', max_length=1000)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    orders: list[JubelioOrderSnapshotRecord] = Field(max_length=500)

    @field_validator('started_at','finished_at','snapshot_at')
    @classmethod
    def timezone_required(cls, value):
        return to_utc(value, 'Waktu snapshot')

    @model_validator(mode='after')
    def valid_snapshot(self):
        if self.finished_at<self.started_at:
            raise ValueError('Waktu selesai tidak boleh sebelum waktu mulai.')
        ids=[order.external_order_id for order in self.orders]
        refs=[order.external_order_reference.casefold() for order in self.orders]
        if len(ids)!=len(set(ids)) or len(refs)!=len(set(refs)):
            raise ValueError('Snapshot tidak boleh memuat ID atau referensi order ganda.')
        return self


class JubelioReturnSnapshotLine(Input):
    external_id: Text
    external_sku: Text
    quantity: Quantity


class JubelioReturnSnapshotRecord(Input):
    external_return_id: Text
    external_return_reference: Text
    external_order_id: Text
    external_order_reference: Text
    marketplace: Text
    status: Literal['requested','in_transit','received','refunded','rejected','cancelled']
    updated_at: datetime
    refund_amount: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,13}(\.[0-9]{1,2})?$", max_length=16)]
    lines: list[JubelioReturnSnapshotLine] = Field(min_length=1, max_length=100)

    @field_validator('updated_at')
    @classmethod
    def timezone_required(cls, value):
        return to_utc(value, 'Waktu pembaruan retur')

    @model_validator(mode='after')
    def valid_return(self):
        amount=Decimal(self.refund_amount)
        if amount>1_000_000_000_000:
            raise ValueError('Refund maksimal Rp1.000.000.000.000 per retur.')
        if (self.status=='refunded') != (amount>0):
            raise ValueError('Hanya retur refunded yang membawa nilai refund positif.')
        self.refund_amount=format(amount,'.2f')
        ids=[line.external_id for line in self.lines]
        skus=[line.external_sku.casefold() for line in self.lines]
        if len(ids)!=len(set(ids)) or len(skus)!=len(set(skus)):
            raise ValueError('Satu retur tidak boleh memuat ID atau SKU eksternal ganda.')
        return self


class JubelioReturnSnapshotImport(Input):
    started_at: datetime
    finished_at: datetime
    snapshot_at: datetime
    external_cursor: str = Field(default='', max_length=1000)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    returns: list[JubelioReturnSnapshotRecord] = Field(max_length=500)

    @field_validator('started_at','finished_at','snapshot_at')
    @classmethod
    def timezone_required(cls, value):
        return to_utc(value, 'Waktu snapshot')

    @model_validator(mode='after')
    def valid_snapshot(self):
        if self.finished_at<self.started_at:
            raise ValueError('Waktu selesai tidak boleh sebelum waktu mulai.')
        ids=[record.external_return_id for record in self.returns]
        refs=[record.external_return_reference.casefold() for record in self.returns]
        if len(ids)!=len(set(ids)) or len(refs)!=len(set(refs)):
            raise ValueError('Snapshot tidak boleh memuat ID atau referensi retur ganda.')
        return self


class JubelioListingSnapshotRecord(Input):
    external_listing_id: Text
    listing_reference: Text
    external_id: Text
    external_sku: Text
    marketplace: Text
    listing_title: Text
    status: Literal['active','inactive','draft','blocked']
    listed_price: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,13}(\.[0-9]{1,2})?$", max_length=16)]
    updated_at: datetime

    @field_validator('listed_price')
    @classmethod
    def normalize_price(cls, value):
        amount=Decimal(value)
        if not 0 < amount <= 1_000_000_000_000:
            raise ValueError('Harga listing harus positif dan maksimal Rp1.000.000.000.000.')
        return format(amount,'.2f')

    @field_validator('updated_at')
    @classmethod
    def timezone_required(cls, value):
        return to_utc(value, 'Waktu pembaruan listing')


class JubelioListingSnapshotImport(Input):
    started_at: datetime
    finished_at: datetime
    snapshot_at: datetime
    external_cursor: str = Field(default='', max_length=1000)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    listings: list[JubelioListingSnapshotRecord] = Field(max_length=1000)

    @field_validator('started_at','finished_at','snapshot_at')
    @classmethod
    def timezone_required(cls, value):
        return to_utc(value, 'Waktu snapshot')

    @model_validator(mode='after')
    def valid_snapshot(self):
        if self.finished_at<self.started_at:
            raise ValueError('Waktu selesai tidak boleh sebelum waktu mulai.')
        ids=[record.external_listing_id for record in self.listings]
        references=[(record.marketplace.casefold(),record.listing_reference.casefold()) for record in self.listings]
        if len(ids)!=len(set(ids)) or len(references)!=len(set(references)):
            raise ValueError('Snapshot tidak boleh memuat ID atau referensi listing marketplace ganda.')
        return self


FinanceAmount = Annotated[str, StringConstraints(pattern=r"^[0-9]{1,15}(\.[0-9]{1,2})?$", max_length=18)]


class MekariFinanceSnapshotPeriod(Input):
    source_report_id: Text
    period_start: date
    period_end: date
    currency: Literal['IDR'] = 'IDR'
    gross_revenue: FinanceAmount
    sales_returns: FinanceAmount
    cost_of_goods_sold: FinanceAmount
    operating_expenses: FinanceAmount
    other_income: FinanceAmount
    other_expenses: FinanceAmount
    cash_balance: FinanceAmount
    receivables_balance: FinanceAmount
    payables_balance: FinanceAmount

    @field_validator('gross_revenue','sales_returns','cost_of_goods_sold','operating_expenses',
                     'other_income','other_expenses','cash_balance','receivables_balance','payables_balance')
    @classmethod
    def normalize_amount(cls, value):
        amount=Decimal(value)
        if amount>1_000_000_000_000_000:
            raise ValueError('Nilai keuangan maksimal Rp1.000.000.000.000.000.')
        return format(amount,'.2f')

    @model_validator(mode='after')
    def valid_period(self):
        if self.period_end<self.period_start:
            raise ValueError('Akhir periode tidak boleh sebelum awal periode.')
        if Decimal(self.sales_returns)>Decimal(self.gross_revenue):
            raise ValueError('Retur penjualan tidak boleh melebihi pendapatan kotor.')
        return self


class MekariFinanceSnapshotImport(Input):
    started_at: datetime
    finished_at: datetime
    snapshot_at: datetime
    external_cursor: str = Field(default='', max_length=1000)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    periods: list[MekariFinanceSnapshotPeriod] = Field(max_length=120)

    @field_validator('started_at','finished_at','snapshot_at')
    @classmethod
    def timezone_required(cls, value):
        return to_utc(value, 'Waktu snapshot')

    @model_validator(mode='after')
    def valid_snapshot(self):
        if self.finished_at<self.started_at:
            raise ValueError('Waktu selesai tidak boleh sebelum waktu mulai.')
        report_ids=[period.source_report_id for period in self.periods]
        ranges=[(period.period_start,period.period_end) for period in self.periods]
        if len(report_ids)!=len(set(report_ids)) or len(ranges)!=len(set(ranges)):
            raise ValueError('Snapshot tidak boleh memuat ID laporan atau periode ganda.')
        return self


class MekariPayableSnapshotRecord(Input):
    external_payable_id: Text
    reference: Text
    external_supplier_id: Text
    supplier_name: Text
    invoice_date: date
    due_date: date
    status: Literal['open','partially_paid','paid','void']
    currency: Literal['IDR'] = 'IDR'
    original_amount: FinanceAmount
    paid_amount: FinanceAmount
    updated_at: datetime

    @field_validator('original_amount','paid_amount')
    @classmethod
    def normalize_amount(cls, value):
        amount=Decimal(value)
        if amount>1_000_000_000_000_000:
            raise ValueError('Nilai utang maksimal Rp1.000.000.000.000.000.')
        return format(amount,'.2f')

    @field_validator('updated_at')
    @classmethod
    def timezone_required(cls, value):
        return to_utc(value, 'Waktu pembaruan utang')

    @model_validator(mode='after')
    def valid_payable(self):
        original=Decimal(self.original_amount);paid=Decimal(self.paid_amount)
        if original<=0:
            raise ValueError('Nilai invoice harus positif.')
        if self.due_date<self.invoice_date:
            raise ValueError('Jatuh tempo tidak boleh sebelum tanggal invoice.')
        if paid>original:
            raise ValueError('Nilai dibayar tidak boleh melebihi nilai invoice.')
        valid=(self.status=='open' and paid==0) or (self.status=='partially_paid' and 0<paid<original) \
            or (self.status=='paid' and paid==original) or (self.status=='void' and paid==0)
        if not valid:
            raise ValueError('Status utang tidak konsisten dengan nilai yang sudah dibayar.')
        return self


class MekariPayableSnapshotImport(Input):
    started_at: datetime
    finished_at: datetime
    snapshot_at: datetime
    as_of: date
    external_cursor: str = Field(default='', max_length=1000)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    payables: list[MekariPayableSnapshotRecord] = Field(max_length=1000)

    @field_validator('started_at','finished_at','snapshot_at')
    @classmethod
    def timezone_required(cls, value):
        return to_utc(value, 'Waktu snapshot')

    @model_validator(mode='after')
    def valid_snapshot(self):
        if self.finished_at<self.started_at:
            raise ValueError('Waktu selesai tidak boleh sebelum waktu mulai.')
        ids=[record.external_payable_id for record in self.payables]
        references=[(record.external_supplier_id,record.reference.casefold()) for record in self.payables]
        if len(ids)!=len(set(ids)) or len(references)!=len(set(references)):
            raise ValueError('Snapshot tidak boleh memuat ID atau referensi utang supplier ganda.')
        return self


class MekariReceivableSnapshotRecord(Input):
    external_receivable_id: Text
    reference: Text
    external_customer_id: Text
    customer_name: Text
    invoice_date: date
    due_date: date
    status: Literal['open','partially_paid','paid','void']
    currency: Literal['IDR'] = 'IDR'
    original_amount: FinanceAmount
    received_amount: FinanceAmount
    updated_at: datetime

    @field_validator('original_amount','received_amount')
    @classmethod
    def normalize_amount(cls, value):
        amount=Decimal(value)
        if amount>1_000_000_000_000_000:
            raise ValueError('Nilai piutang maksimal Rp1.000.000.000.000.000.')
        return format(amount,'.2f')

    @field_validator('updated_at')
    @classmethod
    def timezone_required(cls, value):
        return to_utc(value, 'Waktu pembaruan piutang')

    @model_validator(mode='after')
    def valid_receivable(self):
        original=Decimal(self.original_amount);received=Decimal(self.received_amount)
        if original<=0:
            raise ValueError('Nilai invoice harus positif.')
        if self.due_date<self.invoice_date:
            raise ValueError('Jatuh tempo tidak boleh sebelum tanggal invoice.')
        if received>original:
            raise ValueError('Nilai diterima tidak boleh melebihi nilai invoice.')
        valid=(self.status=='open' and received==0) or (self.status=='partially_paid' and 0<received<original) \
            or (self.status=='paid' and received==original) or (self.status=='void' and received==0)
        if not valid:
            raise ValueError('Status piutang tidak konsisten dengan nilai yang sudah diterima.')
        return self


class MekariReceivableSnapshotImport(Input):
    started_at: datetime
    finished_at: datetime
    snapshot_at: datetime
    as_of: date
    external_cursor: str = Field(default='', max_length=1000)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    receivables: list[MekariReceivableSnapshotRecord] = Field(max_length=1000)

    @field_validator('started_at','finished_at','snapshot_at')
    @classmethod
    def timezone_required(cls, value):
        return to_utc(value, 'Waktu snapshot')

    @model_validator(mode='after')
    def valid_snapshot(self):
        if self.finished_at<self.started_at:
            raise ValueError('Waktu selesai tidak boleh sebelum waktu mulai.')
        ids=[record.external_receivable_id for record in self.receivables]
        references=[(record.external_customer_id,record.reference.casefold()) for record in self.receivables]
        if len(ids)!=len(set(ids)) or len(references)!=len(set(references)):
            raise ValueError('Snapshot tidak boleh memuat ID atau referensi piutang pelanggan ganda.')
        return self


class MekariPayrollAccounting(Input):
    status: Literal['draft','posted','reversed']
    journal_reference: Text
    posting_date: date | None = None
    debit_total: FinanceAmount
    credit_total: FinanceAmount
    updated_at: datetime

    @field_validator('debit_total','credit_total')
    @classmethod
    def normalize_amount(cls, value):
        amount=Decimal(value)
        if not 0<amount<=1_000_000_000_000_000:
            raise ValueError('Nilai posting payroll harus positif dan maksimal Rp1.000.000.000.000.000.')
        return format(amount,'.2f')

    @field_validator('updated_at')
    @classmethod
    def timezone_required(cls, value):
        return to_utc(value, 'Waktu pembaruan posting payroll')

    @model_validator(mode='after')
    def valid_posting(self):
        if (self.status=='draft')!=(self.posting_date is None):
            raise ValueError('Tanggal posting hanya wajib untuk jurnal posted atau reversed.')
        return self


class MekariPayrollSnapshotPeriod(Input):
    external_payroll_id: Text
    period_start: date
    period_end: date
    status: Literal['draft','reviewing','approved','paid','cancelled']
    currency: Literal['IDR'] = 'IDR'
    employee_count: int = Field(ge=0, le=1_000_000)
    gross_pay: FinanceAmount
    employee_deductions: FinanceAmount
    employer_contributions: FinanceAmount
    payment_date: date | None = None
    updated_at: datetime
    accounting: MekariPayrollAccounting | None = None

    @field_validator('gross_pay','employee_deductions','employer_contributions')
    @classmethod
    def normalize_amount(cls, value):
        amount=Decimal(value)
        if amount>1_000_000_000_000_000:
            raise ValueError('Nilai payroll maksimal Rp1.000.000.000.000.000.')
        return format(amount,'.2f')

    @field_validator('updated_at')
    @classmethod
    def timezone_required(cls, value):
        return to_utc(value, 'Waktu pembaruan payroll')

    @model_validator(mode='after')
    def valid_period(self):
        if self.period_end<self.period_start:
            raise ValueError('Akhir periode payroll tidak boleh sebelum awal periode.')
        if Decimal(self.employee_deductions)>Decimal(self.gross_pay):
            raise ValueError('Potongan karyawan tidak boleh melebihi gaji bruto.')
        if (self.status=='paid')!=(self.payment_date is not None):
            raise ValueError('Tanggal pembayaran hanya wajib untuk payroll berstatus dibayar.')
        if self.payment_date is not None and self.payment_date<self.period_start:
            raise ValueError('Tanggal pembayaran tidak boleh sebelum awal periode payroll.')
        if self.accounting and self.accounting.posting_date and self.accounting.posting_date<self.period_start:
            raise ValueError('Tanggal posting tidak boleh sebelum awal periode payroll.')
        return self


class MekariPayrollSnapshotImport(Input):
    started_at: datetime
    finished_at: datetime
    snapshot_at: datetime
    external_cursor: str = Field(default='', max_length=1000)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    periods: list[MekariPayrollSnapshotPeriod] = Field(max_length=120)

    @field_validator('started_at','finished_at','snapshot_at')
    @classmethod
    def timezone_required(cls, value):
        return to_utc(value, 'Waktu snapshot')

    @model_validator(mode='after')
    def valid_snapshot(self):
        if self.finished_at<self.started_at:
            raise ValueError('Waktu selesai tidak boleh sebelum waktu mulai.')
        payroll_ids=[period.external_payroll_id for period in self.periods]
        ranges=[(period.period_start,period.period_end) for period in self.periods]
        if len(payroll_ids)!=len(set(payroll_ids)) or len(ranges)!=len(set(ranges)):
            raise ValueError('Snapshot tidak boleh memuat ID payroll atau periode ganda.')
        return self


MaterialAmount = Annotated[str, StringConstraints(pattern=r"^[0-9]{1,7}(\.[0-9]{1,3})?$", max_length=11)]


class MaterialCreate(Input):
    code: Text
    name: Text
    unit: Literal['m', 'kg', 'pcs']
    # M01 (issue #43): klasifikasi, deskripsi, dan harga referensi opsional.
    # Harga referensi terpisah dari harga aktual PO/receipt dan histori biaya.
    class_id: str | None = Field(default=None, max_length=160)
    description: str = Field(default="", max_length=1000)
    reference_price: Annotated[str, StringConstraints(
        pattern=r"^[0-9]{1,10}(\.[0-9]{1,2})?$", max_length=13)] | None = None

    @field_validator('code')
    @classmethod
    def normalize_code(cls, value):
        return value.upper()

    @field_validator('reference_price')
    @classmethod
    def normalize_reference_price(cls, value):
        if value is None:
            return value
        amount = Decimal(value)
        if amount <= 0:
            raise ValueError('Harga referensi harus positif.')
        return format(amount, '.2f')


class MaterialUpdate(Input):
    """Ubah master bahan. Kode/nama/satuan identitas tidak dapat diubah
    (ditegakkan trigger materials_identity_immutable).

    class_id: None = tidak diubah; string kosong = lepas (NULL).
    """

    class_id: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    reference_price: Annotated[str, StringConstraints(
        pattern=r"^[0-9]{1,10}(\.[0-9]{1,2})?$", max_length=13)] | None = None
    clear_reference_price: bool = False
    active: bool | None = None

    @field_validator('reference_price')
    @classmethod
    def normalize_reference_price(cls, value):
        if value is None:
            return value
        amount = Decimal(value)
        if amount <= 0:
            raise ValueError('Harga referensi harus positif.')
        return format(amount, '.2f')


class MaterialQuantity(Input):
    quantity: MaterialAmount

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, value):
        quantity = Decimal(value)
        if not 0 < quantity <= 1_000_000:
            raise ValueError('Jumlah harus lebih dari nol dan maksimal 1.000.000 satuan.')
        return format(quantity, '.3f')


class PurchaseOrderReceipt(MaterialQuantity):
    material_id: Text
    reference: Text
    location: Text
    received_date: date
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class MaterialReceipt(PurchaseOrderReceipt):
    supplier: Text
    # M02: tautan opsional ke identitas lokasi/pemasok. Bila diisi, teks
    # location/supplier harus cocok dengan master yang dipilih.
    storage_id: Text | None = None
    supplier_id: Text | None = None


class SupplierReturn(MaterialQuantity):
    reference: Text
    returned_date: date
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class QualityDecision(MaterialQuantity):
    kind: Literal['accept','reject']
    reference: Text | None = None
    location: Text | None = None
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @model_validator(mode='after')
    def require_batch_for_acceptance(self):
        if self.kind=='accept' and (not self.reference or not self.location):
            raise ValueError('Isi referensi batch dan lokasi stok layak pakai.')
        if self.kind=='reject' and (self.reference is not None or self.location is not None):
            raise ValueError('Keputusan reject tidak membuat batch stok.')
        return self


class MaterialIssue(MaterialQuantity):
    batch_id: Text
    order_id: Text
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class MaterialReservation(MaterialIssue):
    action: Literal['reserve', 'release']


class MaterialConsumption(Input):
    issue_id: Text
    used: MaterialAmount
    waste: MaterialAmount
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @field_validator('used','waste')
    @classmethod
    def validate_amount(cls,value):
        amount=Decimal(value)
        if not 0 <= amount <= 1_000_000:
            raise ValueError('Jumlah harus antara nol dan 1.000.000 satuan.')
        return format(amount,'.3f')


class CuttingOutput(Input):
    line_id: Text
    quantity: Quantity


def validate_cutting_weight(value, message):
    if value is None:
        return None
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise ValueError(message) from None
    if not amount.is_finite() or not 0 < amount <= 1_000_000 \
            or amount * 1000 != (amount * 1000).to_integral_value():
        raise ValueError(message)
    return format(amount, '.3f')


class CuttingRollCreate(Input):
    # Detail satu rol: berat (kg) dan/atau lembar — minimal satu terisi.
    # Keduanya input manual; TIDAK ada konversi otomatis antar satuan.
    roll_no: Annotated[int, Field(strict=True, gt=0, le=1000)]
    weight_kg: str | None = Field(default=None, max_length=20)
    sheets: Annotated[int, Field(strict=True, gt=0)] | None = None
    note: str = Field(default="", max_length=500)

    @field_validator('weight_kg')
    @classmethod
    def validate_weight_kg(cls, value):
        return validate_cutting_weight(
            value, 'Berat rol harus positif, maksimal 1.000.000 kg dengan tiga desimal.')

    @model_validator(mode='after')
    def require_weight_or_sheets(self):
        if self.weight_kg is None and self.sheets is None:
            raise ValueError('Isi berat rol (kg) atau jumlah lembar rol.')
        return self


class CuttingOutputParamCreate(Input):
    # Parameter operasional per baris output.
    # setelan_per_lembar: DEMO_ASSUMPTION — jumlah potongan (pcs) per lembar,
    # input manual; dipakai hanya untuk ESTIMASI, bukan angka aktual.
    line_id: Text
    setelan_per_lembar: Annotated[int, Field(strict=True, gt=0)] | None = None
    product_weight_gram: str | None = Field(default=None, max_length=20)
    material_used_gram: str | None = Field(default=None, max_length=20)

    @field_validator('product_weight_gram', 'material_used_gram')
    @classmethod
    def validate_gram(cls, value):
        return validate_cutting_weight(
            value, 'Berat gram harus positif, maksimal 1.000.000 dengan tiga desimal.')


class CuttingRunCreate(MaterialConsumption):
    reference: Text
    outputs: list[CuttingOutput] = Field(min_length=1, max_length=100)
    # P02 (issue #49): parameter operasional cutting. cut_date wajib (input
    # manual); sisanya opsional. Estimasi (lembar x setelan) dihitung di
    # detail dan SELALU berlabel asumsi — bukan pengganti angka aktual.
    cut_date: date
    po_reference: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)] | None = None
    weight_kg: str | None = Field(default=None, max_length=20)
    rolls: list[CuttingRollCreate] = Field(default_factory=list, max_length=200)
    output_params: list[CuttingOutputParamCreate] = Field(default_factory=list, max_length=100)

    @field_validator('outputs')
    @classmethod
    def unique_output_lines(cls, outputs):
        if len({row.line_id for row in outputs}) != len(outputs):
            raise ValueError('Gabungkan hasil untuk SKU yang sama menjadi satu baris.')
        return sorted(outputs, key=lambda row: row.line_id)

    @field_validator('weight_kg')
    @classmethod
    def validate_weight_kg(cls, value):
        return validate_cutting_weight(
            value, 'Berat bahan harus positif, maksimal 1.000.000 kg dengan tiga desimal.')

    @field_validator('rolls')
    @classmethod
    def unique_roll_numbers(cls, rolls):
        numbers = [row.roll_no for row in rolls]
        if len(set(numbers)) != len(numbers):
            raise ValueError('Nomor rol tidak boleh duplikat dalam satu hasil cutting.')
        return sorted(rolls, key=lambda row: row.roll_no)

    @field_validator('output_params')
    @classmethod
    def unique_param_lines(cls, params):
        if len({row.line_id for row in params}) != len(params):
            raise ValueError('Parameter output tiap SKU cukup satu baris.')
        return sorted(params, key=lambda row: row.line_id)

    @model_validator(mode='after')
    def require_used_material(self):
        if Decimal(self.used) <= 0:
            raise ValueError('Hasil cutting memerlukan bahan terpakai lebih dari nol.')
        return self

    @model_validator(mode='after')
    def params_match_outputs(self):
        line_ids = {row.line_id for row in self.outputs}
        for param in self.output_params:
            if param.line_id not in line_ids:
                raise ValueError('Parameter output harus merujuk SKU pada hasil cutting ini.')
        return self


class PlanDecision(Input):
    # Keputusan approval/closure rencana: revision guard + alasan wajib.
    revision: Annotated[int, Field(strict=True, ge=0)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class BundleCreate(Input):
    reference: Text
    output_movement_id: Text
    quantity: Quantity
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class BundleHandoffCreate(ReversalCreate):
    to_location: Text


class SewingJobCreate(ReversalCreate):
    reference: Text
    assignment_type: Literal['internal','makloon']
    assignee: Text
    quantity_out: Quantity
    cost: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,13}(\.[0-9]{1,2})?$", max_length=16)]
    sent_date: date
    # M02: employee_id hanya untuk job internal. Makloon/vendor tetap memakai
    # assignee teks dan tidak boleh ditautkan ke employee.
    employee_id: Text | None = None

    @model_validator(mode='after')
    def employee_only_internal(self):
        if self.employee_id is not None and self.assignment_type != 'internal':
            raise ValueError('Tautan employee hanya untuk job internal. '
                             'Makloon memakai nama assignee teks.')
        return self

    @field_validator('cost')
    @classmethod
    def normalize_cost(cls, value):
        amount = Decimal(value)
        if not 0 <= amount <= 1_000_000_000_000:
            raise ValueError('Biaya total harus antara Rp0 dan Rp1.000.000.000.000.')
        return format(amount, '.2f')


class SewingJobComplete(ReversalCreate):
    completed_quantity: Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
    defect_quantity: Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
    missing_quantity: Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
    returned_date: date


class FinishingRecordCreate(ReversalCreate):
    reference: Text
    quantity: Quantity
    thread_trimmed: Annotated[bool, Field(strict=True)]
    ironed: Annotated[bool, Field(strict=True)]
    labels_attached: Annotated[bool, Field(strict=True)]
    hangtags_attached: Annotated[bool, Field(strict=True)]
    packaged: Annotated[bool, Field(strict=True)]
    completed_date: date

    @model_validator(mode='after')
    def completed_checklist(self):
        if not all((self.thread_trimmed, self.ironed, self.labels_attached,
                    self.hangtags_attached, self.packaged)):
            raise ValueError('Semua langkah finishing harus dikonfirmasi sebelum masuk QC.')
        return self


class FinalQcRecordCreate(ReversalCreate):
    reference: Text
    measurement_notes: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    visual_notes: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    defect_type: Text
    responsible_source: Text
    disposition: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    accepted_quantity: Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
    rework_quantity: Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
    reject_quantity: Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
    inspection_date: date

    @model_validator(mode='after')
    def positive_total(self):
        if self.accepted_quantity + self.rework_quantity + self.reject_quantity < 1:
            raise ValueError('Isi setidaknya satu hasil QC dengan jumlah lebih dari nol.')
        return self


class ReworkCompletionCreate(ReversalCreate):
    reference: Text
    quantity: Quantity
    completed_date: date


class FinishedGoodsReceiptCreate(ReversalCreate):
    reference: Text
    scanned_sku: Text
    location: Text
    sellable_quantity: Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
    hold_quantity: Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
    received_date: date

    @model_validator(mode='after')
    def positive_total(self):
        if self.sellable_quantity + self.hold_quantity < 1:
            raise ValueError('Jumlah sellable + hold harus lebih dari nol.')
        return self


class WarehouseMovementCreate(ReversalCreate):
    reference: Text
    scanned_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    kind: Literal['transfer', 'hold_release', 'hold_damage']
    from_location: Text
    to_location: Text
    stock_status: Literal['sellable', 'hold', 'damaged'] | None = None
    quantity: Quantity
    moved_date: date

    @model_validator(mode='after')
    def valid_route(self):
        if self.kind == 'transfer':
            if self.stock_status is None:
                raise ValueError('Status stok wajib dipilih untuk transfer lokasi.')
            if self.from_location.casefold() == self.to_location.casefold():
                raise ValueError('Lokasi tujuan transfer harus berbeda dari lokasi asal.')
        elif self.stock_status is not None:
            raise ValueError('Status stok ditentukan otomatis untuk keputusan hold.')
        return self


class MarketplaceReservationCreate(ReversalCreate):
    reference: Text
    marketplace: Text
    external_order_reference: Text
    location: Text
    quantity: Quantity
    reserved_date: date


class MarketplaceReservationRelease(ReversalCreate):
    released_date: date


class MarketplacePickCreate(ReversalCreate):
    reference: Text
    scanned_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    quantity: Quantity
    staging_location: Text
    picked_date: date


class MarketplacePackCreate(ReversalCreate):
    reference: Text
    quantity: Quantity
    packed_date: date


class MarketplaceShipmentCreate(ReversalCreate):
    reference: Text
    quantity: Quantity
    carrier: Text
    tracking_number: Text
    shipped_date: date


class MarketplaceSaleSettlementCreate(ReversalCreate):
    reference: Text
    gross_revenue: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,13}(\.[0-9]{1,2})?$", max_length=16)]
    seller_discount: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,13}(\.[0-9]{1,2})?$", max_length=16)]
    customer_refund: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,13}(\.[0-9]{1,2})?$", max_length=16)]
    marketplace_fee: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,13}(\.[0-9]{1,2})?$", max_length=16)]
    shipping_cost: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,13}(\.[0-9]{1,2})?$", max_length=16)]
    other_variable_cost: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,13}(\.[0-9]{1,2})?$", max_length=16)]
    settled_date: date

    @field_validator('gross_revenue','seller_discount','customer_refund','marketplace_fee',
                     'shipping_cost','other_variable_cost')
    @classmethod
    def normalize_money(cls, value, info):
        amount = Decimal(value)
        minimum = Decimal('0.01') if info.field_name == 'gross_revenue' else Decimal('0')
        if not minimum <= amount <= 1_000_000_000_000:
            raise ValueError('Nominal harus antara Rp0 dan Rp1.000.000.000.000; omzet wajib positif.')
        return format(amount, '.2f')


class MarketplaceReturnCreate(ReversalCreate):
    reference: Text
    quantity: Quantity
    return_reason: Literal['too_small', 'too_big', 'wrong_item', 'defect', 'color_mismatch', 'other']
    return_location: Text
    stock_status: Literal['sellable', 'hold', 'damaged']
    returned_date: date


class FinishedGoodsAdjustmentCreate(ReversalCreate):
    reference: Text
    location: Text
    stock_status: Literal['sellable', 'hold', 'damaged']
    quantity_delta: Annotated[int, Field(strict=True, ge=-1_000_000_000, le=1_000_000_000)]
    adjusted_date: date

    @field_validator('quantity_delta')
    @classmethod
    def nonzero_delta(cls, value):
        if value == 0:
            raise ValueError('Selisih adjustment tidak boleh nol.')
        return value


class FinishedGoodsStockCountCreate(ReversalCreate):
    reference: Text
    scanned_sku: Text
    location: Text
    stock_status: Literal['sellable', 'hold', 'damaged']
    counted_quantity: Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
    counted_date: date


class BomComponent(MaterialQuantity):
    material_id: Text


class PurchaseRequestCreate(Input):
    reference: Text
    order_id: Text | None = None
    required_date: date
    estimated_value: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,13}(\.[0-9]{1,2})?$", max_length=16)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    lines: list[BomComponent] = Field(min_length=1, max_length=100)

    @field_validator('estimated_value')
    @classmethod
    def normalize_value(cls, value):
        amount = Decimal(value)
        if not 0 < amount <= 1_000_000_000_000:
            raise ValueError('Estimasi total harus positif dan maksimal Rp1.000.000.000.000.')
        return format(amount, '.2f')

    @field_validator('lines')
    @classmethod
    def unique_lines(cls, lines):
        if len({line.material_id for line in lines}) != len(lines):
            raise ValueError('Gabungkan bahan yang sama menjadi satu baris.')
        return sorted(lines, key=lambda line: line.material_id)


class PurchaseRequestDecision(ReversalCreate):
    status: Literal['approved', 'rejected', 'cancelled']
    expected_revision: Annotated[int, Field(strict=True, ge=1)]


class SupplierCreate(ReversalCreate):
    code: Text
    name: Text
    contact: str = Field(default='', max_length=500)
    address: str = Field(default='', max_length=1000)

    @field_validator('code')
    @classmethod
    def normalize_code(cls, value):
        return value.upper()


class PurchasePrice(Input):
    material_id: Text
    unit_price: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,10}(\.[0-9]{1,2})?$", max_length=13)]

    @field_validator('unit_price')
    @classmethod
    def normalize_price(cls, value):
        amount = Decimal(value)
        if not 0 < amount <= 1_000_000_000:
            raise ValueError('Harga satuan harus positif dan maksimal Rp1.000.000.000.')
        return format(amount, '.2f')


class PurchaseOrderCreate(ReversalCreate):
    reference: Text
    request_id: Text
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    supplier_id: Text
    expected_date: date
    terms: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    prices: list[PurchasePrice] = Field(min_length=1, max_length=100)
    # M02: unit usaha pemilik PO. Opsional agar payload lama tetap diterima.
    business_unit_id: Text | None = None

    @field_validator('prices')
    @classmethod
    def unique_prices(cls, prices):
        if len({price.material_id for price in prices}) != len(prices):
            raise ValueError('Harga setiap bahan harus diisi tepat satu kali.')
        return sorted(prices, key=lambda price: price.material_id)


class SupplierPaymentRequestCreate(ReversalCreate):
    reference: Text
    invoice_id: Text
    invoice_reference: Text
    invoice_date: date
    due_date: date
    amount: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,13}(\.[0-9]{1,2})?$", max_length=16)]

    @field_validator('amount')
    @classmethod
    def normalize_amount(cls, value):
        amount = Decimal(value)
        if not 0 < amount <= 1_000_000_000_000:
            raise ValueError('Nominal pembayaran harus positif dan maksimal Rp1.000.000.000.000.')
        return format(amount, '.2f')

    @model_validator(mode='after')
    def valid_dates(self):
        if self.invoice_date > self.due_date:
            raise ValueError('Tanggal jatuh tempo tidak boleh sebelum tanggal invoice.')
        return self


class SupplierInvoiceLine(Input):
    # B01 (#50): satu baris alokasi tagihan ke baris PO. Harga wajib sama
    # dengan harga aktual baris PO (divalidasi server); bukan harga master.
    purchase_order_id: Text
    material_id: Text
    quantity: MaterialAmount
    unit_price: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,10}(\.[0-9]{1,2})?$", max_length=13)]

    @field_validator('quantity')
    @classmethod
    def normalize_quantity(cls, value):
        quantity = Decimal(value)
        if not 0 < quantity <= 1_000_000:
            raise ValueError('Jumlah harus lebih dari nol dan maksimal 1.000.000 satuan.')
        return format(quantity, '.3f')

    @field_validator('unit_price')
    @classmethod
    def normalize_price(cls, value):
        amount = Decimal(value)
        if not 0 < amount <= 1_000_000_000:
            raise ValueError('Harga satuan harus positif dan maksimal Rp1.000.000.000.')
        return format(amount, '.2f')


class SupplierInvoiceCreate(ReversalCreate):
    # B01 (#50) fondasi minimal: identitas global (supplier_id, reference),
    # tanggal invoice/jatuh tempo, dan alokasi ke PO. Bukan scope #50:
    # credit note, multi-mata uang, posting AP otomatis, settlement/kas/bank.
    reference: Text
    supplier_id: Text
    invoice_date: date
    due_date: date
    lines: Annotated[list[SupplierInvoiceLine], Field(min_length=1, max_length=100)]

    @field_validator('lines')
    @classmethod
    def unique_lines(cls, lines):
        keys = [(line.purchase_order_id, line.material_id) for line in lines]
        if len(set(keys)) != len(keys):
            raise ValueError('Satu bahan pada satu PO hanya boleh dialokasikan satu baris per tagihan.')
        return lines

    @model_validator(mode='after')
    def valid_dates(self):
        if self.invoice_date > self.due_date:
            raise ValueError('Tanggal jatuh tempo tidak boleh sebelum tanggal invoice.')
        return self


class MarketingBudgetRequestCreate(ReversalCreate):
    reference: Text
    campaign_name: Text
    channel: Text
    start_date: date
    end_date: date
    amount: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,13}(\.[0-9]{1,2})?$", max_length=16)]
    objective: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @field_validator('amount')
    @classmethod
    def normalize_amount(cls, value):
        amount = Decimal(value)
        if not 0 < amount <= 1_000_000_000_000:
            raise ValueError('Nominal budget harus positif dan maksimal Rp1.000.000.000.000.')
        return format(amount, '.2f')

    @model_validator(mode='after')
    def valid_dates(self):
        if self.start_date > self.end_date:
            raise ValueError('Tanggal selesai kampanye tidak boleh sebelum tanggal mulai.')
        return self


class BomSave(Input):
    expected_revision: Annotated[int, Field(strict=True, ge=0)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    components: list[BomComponent] = Field(min_length=1, max_length=100)

    @field_validator('components')
    @classmethod
    def unique_materials(cls, components):
        if len({c.material_id for c in components}) != len(components):
            raise ValueError('Gabungkan bahan yang sama menjadi satu baris BOM.')
        return sorted(components, key=lambda c: c.material_id)


# ---------------------------------------------------------------------------
# M02 — Master: unit usaha, lokasi, pelanggan, jabatan, metode pembayaran.
# Semua memakai pola identity + events: kolom active hidup di event sehingga
# histori tetap terbaca setelah master dinonaktifkan.
# ---------------------------------------------------------------------------

class BusinessUnitCreate(Input):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    name: Text
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @field_validator('code')
    @classmethod
    def normalize_code(cls, value):
        return value.upper()


class BusinessUnitChange(Input):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    name: Text
    active: Annotated[bool, Field(strict=True)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


StorageKind = Literal['warehouse', 'retail', 'production', 'other']


class StorageCreate(Input):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    name: Text
    kind: StorageKind
    business_unit_id: Text
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @field_validator('code')
    @classmethod
    def normalize_code(cls, value):
        return value.upper()


class StorageChange(Input):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    name: Text
    kind: StorageKind
    active: Annotated[bool, Field(strict=True)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class CustomerCreate(Input):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    name: Text
    contact: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ''
    address: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] = ''
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @field_validator('code')
    @classmethod
    def normalize_code(cls, value):
        return value.upper()


class CustomerChange(Input):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    name: Text
    contact: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ''
    address: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] = ''
    active: Annotated[bool, Field(strict=True)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class PositionCreate(Input):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    name: Text
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @field_validator('code')
    @classmethod
    def normalize_code(cls, value):
        return value.upper()


class PositionChange(Input):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    name: Text
    active: Annotated[bool, Field(strict=True)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


PaymentMethodKind = Literal['cash', 'bank_transfer', 'qris', 'ewallet', 'other']


class PaymentMethodCreate(Input):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    name: Text
    kind: PaymentMethodKind
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @field_validator('code')
    @classmethod
    def normalize_code(cls, value):
        return value.upper()


class PaymentMethodChange(Input):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    name: Text
    kind: PaymentMethodKind
    active: Annotated[bool, Field(strict=True)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class SupplierChange(Input):
    # Identitas pemasok immutable (kontrak F02). Hanya status aktif yang diubah.
    active: Annotated[bool, Field(strict=True)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class EmployeeLegacyIdCreate(Input):
    # employee_id diambil dari path endpoint, bukan body, sehingga permintaan
    # tidak dapat menulis legacy ID milik karyawan lain.
    legacy_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    source_system: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class StorageLocationMapping(Input):
    # Pemetaan eksplisit admin untuk kasus pending/ambiguous. Teks asli tidak
    # berubah; hanya identitas storage yang ditautkan.
    storage_id: Text
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

class BomTemplateCreate(MasterCreate):
    """Template bahan: cetakan komponen untuk menerbitkan revisi BOM baru.

    Tidak menggantikan mekanisme BOM berversi; apply selalu INSERT revisi baru.
    """

    product_type_id: Text | None = None
    components: list[BomComponent] = Field(min_length=1, max_length=100)

    @field_validator('components')
    @classmethod
    def unique_materials(cls, components):
        if len({c.material_id for c in components}) != len(components):
            raise ValueError('Gabungkan bahan yang sama menjadi satu baris template.')
        return sorted(components, key=lambda c: c.material_id)


class BomTemplateUpdate(MasterUpdate):
    product_type_id: str | None = Field(default=None, max_length=160)
    components: list[BomComponent] | None = Field(default=None, min_length=1, max_length=100)

    @field_validator('components')
    @classmethod
    def unique_materials(cls, components):
        if components is not None and len({c.material_id for c in components}) != len(components):
            raise ValueError('Gabungkan bahan yang sama menjadi satu baris template.')
        return sorted(components, key=lambda c: c.material_id) if components else components


class BomTemplateApply(Input):
    product_id: Text
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    expected_revision: Annotated[int, Field(strict=True, ge=0)]


# ---------------------------------------------------------------------------
# A01 (#46): Ledger keuangan dan kontrak posting
# ---------------------------------------------------------------------------

AccountType = Literal["asset", "liability", "equity", "revenue", "expense"]
MoneyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1,
                                             max_length=18, pattern=r"^[0-9]{1,15}(\.[0-9]{1,2})?$")]
DateText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=10,
                                            pattern=r"^\d{4}-\d{2}-\d{2}$")]


class CoaAccountCreate(Input):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    type: AccountType


class AccountingPeriodCreate(Input):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
    start_date: DateText
    end_date: DateText


class PeriodDecision(Input):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    expected_revision: Annotated[int, Field(strict=True, ge=1)] | None = None


class JournalSource(Input):
    system: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    account: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    entity_type: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    line_id: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] = ""
    revision: Annotated[int, Field(strict=True, ge=1)] = 1


class JournalLineCreate(Input):
    account_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1,
                                                  max_length=20)] | None = None
    account_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1,
                                                max_length=160)] | None = None
    debit: MoneyText = "0"
    credit: MoneyText = "0"
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] = ""

    @model_validator(mode="after")
    def account_ref(self):
        if not (self.account_code or self.account_id):
            raise ValueError("account_code atau account_id wajib diisi.")
        return self


class JournalCreate(Input):
    period_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    journal_date: DateText
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    business_unit_id: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None = None
    policy_ref: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    source: JournalSource
    lines: list[JournalLineCreate] = Field(min_length=2, max_length=200)


class JournalReverse(Input):
    period_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    journal_date: DateText
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class PoReceiptJournalCreate(Input):
    period_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    journal_date: DateText
    receipts: list[dict] = Field(min_length=1, max_length=200)


# ---------------------------------------------------------------------------
# P01 (#48): jenis pekerjaan, kelompok jasa, template jasa berversi, tarif
# upah berversi dengan tanggal berlaku, dan penerapan template ke SKU.
#
# Kontrak resolver tarif dan snapshot: docs/p01-rate-resolver.md. Aritmatika
# uang/qty eksak memakai beeloft.contracts (minor integer + Fraction); nominal
# tarif disimpan SATU kali (amount + rate_basis) dan nilai lawan selalu derived.
# Menit standar (RoutingStandardSave) tetap terpisah dari tarif upah.
# ---------------------------------------------------------------------------

class WorkTypeCreate(Input):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    name: Text
    # Kelompok jasa opsional; None = tanpa kelompok.
    service_group_id: Text | None = None
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        return value.upper()


class WorkTypeChange(Input):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    name: Text
    # None = lepaskan dari kelompok; kirim id untuk menetapkan/memindahkan.
    service_group_id: Text | None = None
    active: Annotated[bool, Field(strict=True)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class ServiceGroupCreate(Input):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    name: Text
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        return value.upper()


class ServiceGroupChange(Input):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    name: Text
    active: Annotated[bool, Field(strict=True)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class ServiceComponent(Input):
    work_type_id: Text


class ServiceTemplateCreate(Input):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    name: Text
    note: str = Field(default="", max_length=1000)
    components: list[ServiceComponent] = Field(min_length=1, max_length=100)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        return value.upper()

    @field_validator('components')
    @classmethod
    def unique_work_types(cls, components):
        if len({c.work_type_id for c in components}) != len(components):
            raise ValueError('Gabungkan jenis pekerjaan yang sama menjadi satu baris template.')
        return sorted(components, key=lambda c: c.work_type_id)


class ServiceTemplateChange(Input):
    # Revisi template menyimpan state lengkap (append-only): UI mengirim nama,
    # catatan, status aktif dan komponen penuh. Revisi lama tidak diubah.
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    name: Text
    note: str = Field(default="", max_length=1000)
    active: Annotated[bool, Field(strict=True)]
    components: list[ServiceComponent] = Field(min_length=1, max_length=100)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @field_validator('components')
    @classmethod
    def unique_work_types(cls, components):
        if len({c.work_type_id for c in components}) != len(components):
            raise ValueError('Gabungkan jenis pekerjaan yang sama menjadi satu baris template.')
        return sorted(components, key=lambda c: c.work_type_id)


class ServiceRateSave(Input):
    # expected_revision = revisi tarif saat ini untuk work type ini; 0 jika
    # belum ada tarif sama sekali. Guard mencegah dua penyimpan paralel.
    expected_revision: Annotated[int, Field(strict=True, ge=0)]
    rate_basis: Literal['lusin', 'pcs']
    # SATU nominal authoritative sesuai rate_basis; mengirim nominal pcs dan
    # lusin sekaligus dilarang (extra="forbid"). Nilai lawan derived eksak.
    amount: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,13}(\.[0-9]{1,2})?$", max_length=16)]
    effective_from: date
    # NULL/None = interval terbuka [effective_from, tak terhingga).
    effective_to: date | None = None
    active: bool = True
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @field_validator('amount')
    @classmethod
    def normalize_amount(cls, value):
        amount = Decimal(value)
        if not 0 < amount <= 1_000_000_000:
            raise ValueError('nominal tarif harus lebih besar dari 0 dan maksimal 1.000.000.000.')
        return format(amount, '.2f')

    @model_validator(mode='after')
    def effective_order(self):
        if self.effective_to is not None and self.effective_from >= self.effective_to:
            raise ValueError('tanggal berakhir harus setelah tanggal mulai berlaku.')
        return self


class ServiceRateDeactivate(Input):
    # Nonaktifkan tarif: revisi baru active=0 dengan interval yang sama persis
    # dengan revisi aktif saat ini, sehingga resolve pada tanggal yang dicakup
    # melaporkan "tarif nonaktif" alih-alih memakai fallback.
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class ServiceTemplateApply(Input):
    product_id: Text
    # Template bahan opsional (#43): diterapkan dalam transaksi yang sama dan
    # revisi BOM yang diterbitkannya ditautkan ke penerapan ini. Tidak membuat
    # ledger bahan kedua.
    bom_template_id: Text | None = None
    bom_expected_revision: Annotated[int, Field(strict=True, ge=0)] | None = None
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @model_validator(mode='after')
    def bom_revision_required(self):
        if self.bom_template_id is not None and self.bom_expected_revision is None:
            raise ValueError('bom_expected_revision wajib saat bom_template_id diisi.')
        return self


# P03 (#52): employee jobs — penugasan kerja karyawan per pcs, realisasi,
# persetujuan realisasi, dan service charges upah.
class EmployeeJobCreate(Input):
    employee_id: Text
    sku: Text
    work_type_id: Text
    bundle_id: Text | None = None
    target_qty_pcs: Annotated[int, Field(strict=True, gt=0)]
    work_date: DateText
    notes: str | None = Field(default=None, max_length=1000)
    unit_id: Text | None = None


class EmployeeJobUpdate(Input):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    target_qty_pcs: Annotated[int, Field(strict=True, gt=0)] | None = None
    status: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=1000)


class JobRealizationCreate(Input):
    qty_pcs: Annotated[int, Field(strict=True, gt=0)]
    work_date: DateText | None = None
    notes: str | None = Field(default=None, max_length=1000)


class JobRealizationUpdate(Input):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    qty_pcs: Annotated[int, Field(strict=True, gt=0)] | None = None
    work_date: DateText | None = None
    notes: str | None = Field(default=None, max_length=1000)


class RealizationReject(Input):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class ChargeReverse(Input):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
class ImportDryRunRequest(Input):
    """Permintaan dry-run impor X01 (#51). Satu request = satu adapter,
    satu sumber (system, account), satu strategi histori/opening balance."""
    adapter: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    source_system: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    source_account: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    strategy: str = Field(default="active_only", max_length=32)
    filename: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    csv_text: str = Field(min_length=1, max_length=5 * 1024 * 1024 + 1024)
    column_map: dict[str, str] = Field(default_factory=dict)
    id_map: dict[str, dict[str, str]] = Field(default_factory=dict)
    reference_mode: dict[str, str] = Field(default_factory=dict)
    auto_apply_revisions: bool = False
    watermark: dict = Field(default_factory=dict)
