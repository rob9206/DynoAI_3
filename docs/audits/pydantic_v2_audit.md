# Pydantic v2 Audit

**Audit date:** 2026-05-07  
**Scope:** `api/`, `dynoai/`, dependency manifests, and schema modules

---

## Summary

This repository currently has **no active Pydantic runtime dependency or BaseModel usage** in backend source paths audited.

Key outcome:

- **Migration risk from Pydantic v1 to v2 is currently near-zero**, because the codebase is not using Pydantic model APIs that changed in v2.
- The one ingestion schema module that references Pydantic in comments is implemented with **stdlib dataclasses + custom validation**, not Pydantic.

Counts:

- `from pydantic import ...`: 0 matches in backend code
- `BaseModel` subclasses: 0 matches in backend code
- `model_dump` / `model_validate` / `field_validator` / `ConfigDict`: 0 matches in backend code
- `.dict()` / `.json()` / `parse_obj` / `from_orm` on Pydantic models: 0 matches in backend code

---

## Method (Context7 + static scan)

Context7 library used:

- `/pydantic/pydantic`

Topics pulled from current docs:

- v2 serialization API (`model_dump`, `model_dump_json`)
- migration deltas (`.dict()`/`.json()` replacements)
- validator migration (`validator` to `field_validator`)
- ORM migration (`from_orm` to `model_validate` with `from_attributes=True`)
- pydantic dataclasses behavior in v2

Repository scan coverage:

- Dependency manifests: `pyproject.toml`, `requirements.txt`, `api/requirements.txt`
- Backend/runtime paths: `api/`, `dynoai/`
- Ingestion schema module: `api/services/ingestion/schemas.py`

---

## Findings

### OK

- **No Pydantic v1 surface area detected in backend code.**  
  No imports or model APIs were found that would trigger v1-to-v2 breakage.

- **Ingestion validation is explicitly dataclass-based.**  
  `api/services/ingestion/schemas.py` uses stdlib `@dataclass`, custom `validate()` methods, and custom `ValidationError`, not `pydantic.BaseModel`.

- **No hidden v1 method usage found.**  
  No callsites using typical v1 migration hotspots (`.dict()`, `.json()`, `parse_obj`, `from_orm`, `class Config`) on Pydantic models.

### Drifted

- **Documentation/comment drift in ingestion schemas.**  
  The module header in `api/services/ingestion/schemas.py` says it "Uses Pydantic for validation", while the implementation intentionally avoids Pydantic and notes "pydantic may not be installed."

  This is not a runtime defect, but it can mislead maintainers and future audits.

### Risky

- None found for v1-to-v2 migration risk, because no active Pydantic model layer is present.

---

## Dependency Reality Check

From scanned manifests:

- `api/requirements.txt`: no `pydantic` dependency
- root `requirements.txt`: no `pydantic` dependency
- `pyproject.toml`: no `pydantic` dependency

Conclusion: the repository currently behaves as a **non-Pydantic backend** for the audited paths.

---

## Could-Adopt (if team chooses to standardize on Pydantic v2)

If the backend later adopts Pydantic v2 for request/response validation, use v2-native patterns from day one:

1. Prefer `BaseModel` with `model_validate()` and `model_dump()`
2. Use `field_validator` (not legacy `validator`)
3. Use `model_config = ConfigDict(...)` (not `class Config`)
4. For ORM objects, enable `from_attributes=True` and call `model_validate()`
5. Use `model_dump_json()` (not `.json()`)

Suggested low-risk first target:

- Ingestion payload boundary objects in `api/services/ingestion/` where schema definitions are already centralized.

---

## Recommendation

**No migration action required now.**

The useful action here is documentation alignment:

- Update wording in `api/services/ingestion/schemas.py` to reflect current dataclass-based validation strategy.

If a future feature introduces Pydantic, adopt v2 APIs directly and avoid any v1 compatibility layer.

