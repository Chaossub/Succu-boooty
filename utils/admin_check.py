# utils/admin_check.py
from __future__ import annotations
import os
import re
from functools import lru_cache
from typing import Set

_SPLIT_RE = re.compile(r"[,\s;]+")

def _split_ids(raw: str) -> Set[int]:
    if not raw:
        return set()
    parts = [p.strip().strip("'").strip('"') for p in _SPLIT_RE.split(raw) if p.strip()]
    out: Set[int] = set()
    for p in parts:
        if p.isdigit():
            out.add(int(p))
    return out

@lru_cache(maxsize=1)
def _owner_ids() -> Set[int]:
    """
    Supports BOTH:
      - OWNER_IDS=1,2,3
      - OWNER_ID=1               (single)
    """
    ids = _split_ids(os.getenv("OWNER_IDS", ""))
    single = (os.getenv("OWNER_ID", "") or "").strip()
    if single.isdigit():
        ids.add(int(single))
    return ids

@lru_cache(maxsize=1)
def _super_admin_ids() -> Set[int]:
    """
    Supports BOTH:
      - SUPER_ADMIN_IDS=1,2,3
      - SUPER_ADMINS=1,2,3      (alternate spelling)
    """
    ids = _split_ids(os.getenv("SUPER_ADMIN_IDS", ""))
    ids |= _split_ids(os.getenv("SUPER_ADMINS", ""))
    return ids

@lru_cache(maxsize=1)
def _admin_ids_only() -> Set[int]:
    # Optional extra role: ADMIN_IDS=...
    return _split_ids(os.getenv("ADMIN_IDS", ""))

@lru_cache(maxsize=1)
def all_admin_ids() -> Set[int]:
    return _owner_ids() | _super_admin_ids() | _admin_ids_only()

def is_owner(user_id: int) -> bool:
    return user_id in _owner_ids()

def is_super_admin(user_id: int) -> bool:
    # Owners count as super admins as well.
    return user_id in (_super_admin_ids() | _owner_ids())

def is_admin(user_id: int) -> bool:
    """Owner OR Super Admin OR Admin."""
    return user_id in all_admin_ids()

