"""
Canonical schema and column mapping.

Every page works on canonical field names (order_date, revenue, ...), never on
whatever the uploaded file called them. Users confirm a mapping on the Data
page; suggest_mapping() pre-fills it from a synonym table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str  # "date" | "number" | "text" | "id"
    required: bool = False
    help: str = ""


FIELDS: list[Field] = [
    Field("order_date", "Order date", "date", True, "When the sale happened."),
    Field("revenue", "Revenue", "number", True, "Sales amount for the line or order."),
    Field("order_id", "Order ID", "id", help="Groups lines into orders (for order counts and AOV)."),
    Field("customer_id", "Customer ID", "id", help="Unlocks customer analytics."),
    Field("customer_name", "Customer name", "text"),
    Field("product", "Product", "text"),
    Field("category", "Category", "text"),
    Field("sub_category", "Sub-category", "text"),
    Field("region", "Region", "text"),
    Field("state", "State / province", "text"),
    Field("city", "City", "text"),
    Field("segment", "Customer segment", "text"),
    Field("quantity", "Quantity", "number"),
    Field("discount", "Discount", "number", help="As a fraction (0.2) or percent (20)."),
    Field("profit", "Profit", "number"),
    Field("cost", "Cost", "number", help="Used to derive profit when profit isn't present."),
    Field("ship_date", "Ship date", "date"),
    Field("ship_mode", "Ship mode", "text"),
]

FIELD_BY_KEY = {f.key: f for f in FIELDS}
REQUIRED = [f.key for f in FIELDS if f.required]

# Lower-cased, punctuation-stripped synonyms. First match wins, so put the most
# specific names first.
SYNONYMS: dict[str, list[str]] = {
    "order_date": ["order date", "orderdate", "date", "invoice date", "transaction date",
                   "sale date", "sales date", "purchase date", "order datetime", "created at"],
    "revenue": ["sales", "revenue", "amount", "sales amount", "total", "total sales",
                "net sales", "gross sales", "line total", "order value", "value", "price total"],
    "order_id": ["order id", "orderid", "order number", "order no", "invoice", "invoice id",
                 "invoice no", "transaction id", "receipt id"],
    "customer_id": ["customer id", "customerid", "client id", "customer code", "customer number",
                    "buyer id", "user id"],
    "customer_name": ["customer name", "customer", "client", "client name", "buyer"],
    "product": ["product name", "product", "item", "item name", "sku name", "description",
                "product description"],
    "category": ["category", "product category", "department", "product line"],
    "sub_category": ["sub category", "subcategory", "sub-category", "product subcategory",
                     "product type"],
    "region": ["region", "sales region", "territory", "area", "zone"],
    "state": ["state", "province", "state province", "county"],
    "city": ["city", "town"],
    "segment": ["segment", "customer segment", "customer type", "channel"],
    "quantity": ["quantity", "qty", "units", "units sold", "quantity ordered"],
    "discount": ["discount", "discount rate", "discount pct", "discount percent"],
    "profit": ["profit", "net profit", "gross profit", "margin amount"],
    "cost": ["cost", "cogs", "cost of goods", "unit cost total", "total cost"],
    "ship_date": ["ship date", "shipdate", "shipping date", "delivery date", "dispatch date"],
    "ship_mode": ["ship mode", "shipping mode", "shipping method", "delivery method", "carrier"],
}

# Which canonical fields each feature needs. Pages use this to show a locked state.
CAPABILITIES: dict[str, list[str]] = {
    "trend": ["order_date", "revenue"],
    "profit": ["profit"],
    "orders": ["order_id"],
    "customers": ["customer_id"],
    "products": ["product"],
    "categories": ["category"],
    "regions": ["region"],
    "geo": ["state"],
    "discounts": ["discount"],
    "shipping": ["ship_date"],
    "ship_mode": ["ship_mode"],
    "segments": ["segment"],
}

DIMENSIONS = ["region", "category", "segment", "sub_category", "state", "ship_mode"]


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(name).lower()).strip()


def suggest_mapping(columns) -> dict[str, str | None]:
    """
    Returns {canonical_key: source_column or None}. Exact synonym matches beat
    partial ones, and a source column is never assigned to two fields.
    """
    normalized = {col: _norm(col) for col in columns}
    taken: set[str] = set()
    mapping: dict[str, str | None] = {}

    # Pass 1: exact synonym matches, in field order.
    for field in FIELDS:
        mapping[field.key] = None
        for synonym in SYNONYMS.get(field.key, []):
            match = next((c for c, n in normalized.items() if n == synonym and c not in taken), None)
            if match is not None:
                mapping[field.key] = match
                taken.add(match)
                break

    # Pass 2: whole-word containment for still-empty fields (e.g. "Net Sales USD").
    for field in FIELDS:
        if mapping[field.key] is not None:
            continue
        for synonym in SYNONYMS.get(field.key, []):
            if len(synonym) < 4:
                continue
            pattern = re.compile(rf"\b{re.escape(synonym)}\b")
            match = next((c for c, n in normalized.items() if c not in taken and pattern.search(n)), None)
            if match is not None:
                mapping[field.key] = match
                taken.add(match)
                break

    return mapping


def validate_mapping(mapping: dict, df: pd.DataFrame) -> list[str]:
    """Human-readable problems that block applying the mapping."""
    problems = []
    for key in REQUIRED:
        if not mapping.get(key):
            problems.append(f"{FIELD_BY_KEY[key].label} is required.")
    used = [c for c in mapping.values() if c]
    duplicates = {c for c in used if used.count(c) > 1}
    for col in sorted(duplicates):
        problems.append(f"Column “{col}” is mapped to more than one field.")
    for key, col in mapping.items():
        if not col or col not in df.columns:
            continue
        kind = FIELD_BY_KEY[key].kind
        series = df[col]
        if kind == "date":
            parsed = series if pd.api.types.is_datetime64_any_dtype(series) else pd.to_datetime(series, errors="coerce", format="mixed")
            if parsed.notna().mean() < 0.8:
                problems.append(f"“{col}” doesn't look like a date column ({FIELD_BY_KEY[key].label}).")
        elif kind == "number":
            numeric = pd.to_numeric(series, errors="coerce")
            if numeric.notna().mean() < 0.8:
                problems.append(f"“{col}” doesn't look numeric ({FIELD_BY_KEY[key].label}).")
    return problems


def available_fields(df: pd.DataFrame) -> set[str]:
    return {f.key for f in FIELDS if f.key in df.columns}


def has_capability(df: pd.DataFrame, capability: str) -> bool:
    return all(field in df.columns for field in CAPABILITIES[capability])


def missing_for(df: pd.DataFrame, *capabilities: str) -> list[str]:
    missing = []
    for cap in capabilities:
        for field in CAPABILITIES[cap]:
            if field not in df.columns and FIELD_BY_KEY[field].label not in missing:
                missing.append(FIELD_BY_KEY[field].label)
    return missing
