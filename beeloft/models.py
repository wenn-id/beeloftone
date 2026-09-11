from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

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


class MaterialReceipt(MaterialQuantity):
    material_id: Text
    reference: Text
    supplier: Text
    location: Text
    received_date: date
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class MaterialIssue(MaterialQuantity):
    batch_id: Text
    order_id: Text
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class BomComponent(MaterialQuantity):
    material_id: Text


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
