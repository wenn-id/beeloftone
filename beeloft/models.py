from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Quantity = Annotated[int, Field(strict=True, gt=0, le=1_000_000_000)]
Stage = Literal["planned", "cutting", "sewing", "finishing", "qc", "rework", "reject", "warehouse"]
Role = Literal["admin", "operator", "viewer"]
STAGES = ("planned", "cutting", "sewing", "finishing", "qc", "rework", "reject", "warehouse")
TRANSITIONS = {("planned", "cutting"), ("cutting", "sewing"), ("sewing", "finishing"),
               ("finishing", "qc"), ("qc", "warehouse"), ("qc", "rework"),
               ("qc", "reject"), ("rework", "qc")}


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProductCreate(Input):
    sku: Text
    name: Text
    color: str = Field(default="", max_length=80)
    size: str = Field(default="", max_length=40)

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value):
        return value.upper()


class UserCreate(Input):
    name: Text
    role: Role


class OrderLine(Input):
    product_id: Text
    quantity: Quantity


class OrderCreate(Input):
    reference: Text
    title: Text
    owner_id: Text
    due_date: date
    lines: list[OrderLine] = Field(min_length=1, max_length=100)

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
        if value.utcoffset() is None:
            raise ValueError('Waktu sinkronisasi harus menyertakan zona waktu.')
        return value.astimezone(timezone.utc)

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


MaterialAmount = Annotated[str, StringConstraints(pattern=r"^[0-9]{1,7}(\.[0-9]{1,3})?$", max_length=11)]


class MaterialCreate(Input):
    code: Text
    name: Text
    unit: Literal['m', 'kg', 'pcs']

    @field_validator('code')
    @classmethod
    def normalize_code(cls, value):
        return value.upper()


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


class CuttingRunCreate(MaterialConsumption):
    reference: Text
    outputs: list[CuttingOutput] = Field(min_length=1, max_length=100)

    @field_validator('outputs')
    @classmethod
    def unique_output_lines(cls, outputs):
        if len({row.line_id for row in outputs}) != len(outputs):
            raise ValueError('Gabungkan hasil untuk SKU yang sama menjadi satu baris.')
        return sorted(outputs, key=lambda row: row.line_id)

    @model_validator(mode='after')
    def require_used_material(self):
        if Decimal(self.used)<=0:
            raise ValueError('Hasil cutting memerlukan bahan terpakai lebih dari nol.')
        return self


class BundleCreate(Input):
    reference: Text
    output_movement_id: Text
    quantity: Quantity
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class SewingJobCreate(ReversalCreate):
    reference: Text
    assignment_type: Literal['internal','makloon']
    assignee: Text
    quantity_out: Quantity
    cost: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,13}(\.[0-9]{1,2})?$", max_length=16)]
    sent_date: date

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

    @field_validator('prices')
    @classmethod
    def unique_prices(cls, prices):
        if len({price.material_id for price in prices}) != len(prices):
            raise ValueError('Harga setiap bahan harus diisi tepat satu kali.')
        return sorted(prices, key=lambda price: price.material_id)


class SupplierPaymentRequestCreate(ReversalCreate):
    reference: Text
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
