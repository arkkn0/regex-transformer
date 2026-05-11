"""In-memory store for uploaded DataFrames (keyed by file_id)."""

from __future__ import annotations

import uuid
from collections import OrderedDict
from dataclasses import dataclass
from time import time

import pandas as pd
from django.conf import settings


@dataclass
class StoredItem:
    created_at: float
    value: pd.DataFrame | bytes


_STORE: OrderedDict[str, StoredItem] = OrderedDict()
_EXPORT_CSV: OrderedDict[str, StoredItem] = OrderedDict()


def _cleanup(store: OrderedDict[str, StoredItem], max_items: int) -> None:
    now = time()
    expired = [
        key
        for key, item in store.items()
        if now - item.created_at > settings.UPLOAD_STORE_TTL_SECONDS
    ]
    for key in expired:
        store.pop(key, None)
    while len(store) > max_items:
        store.popitem(last=False)


def save_dataframe(df: pd.DataFrame) -> str:
    _cleanup(_STORE, settings.UPLOAD_STORE_MAX_ITEMS)
    file_id = uuid.uuid4().hex
    _STORE[file_id] = StoredItem(time(), df)
    return file_id


def get_dataframe(file_id: str) -> pd.DataFrame | None:
    _cleanup(_STORE, settings.UPLOAD_STORE_MAX_ITEMS)
    item = _STORE.get(file_id)
    if item is None:
        return None
    _STORE.move_to_end(file_id)
    return item.value if isinstance(item.value, pd.DataFrame) else None


def save_export_csv(csv_bytes: bytes) -> str:
    _cleanup(_EXPORT_CSV, settings.EXPORT_STORE_MAX_ITEMS)
    export_id = uuid.uuid4().hex
    _EXPORT_CSV[export_id] = StoredItem(time(), csv_bytes)
    return export_id


def get_export_csv(export_id: str) -> bytes | None:
    _cleanup(_EXPORT_CSV, settings.EXPORT_STORE_MAX_ITEMS)
    item = _EXPORT_CSV.get(export_id)
    if item is None:
        return None
    _EXPORT_CSV.move_to_end(export_id)
    return item.value if isinstance(item.value, bytes) else None
