"""Language pack discovery.

Packs are looked up by ISO code and constructed lazily, so importing the core
never drags in a pack's data files.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

from bhashasetu.core.protocols import LanguagePack

_BUILTIN: dict[str, str] = {
    "bn": "bhashasetu.language_packs.bn",
    # "hi" ships in Phase 5 purely to prove the abstraction holds.
}

_cache: dict[str, LanguagePack] = {}
_extra: dict[str, Callable[[], LanguagePack]] = {}


class UnknownLanguageError(KeyError):
    pass


def register(code: str, factory: Callable[[], LanguagePack]) -> None:
    _extra[code] = factory
    _cache.pop(code, None)


def available() -> list[str]:
    return sorted(set(_BUILTIN) | set(_extra))


def get_pack(code: str) -> LanguagePack:
    code = code.lower()
    if code in _cache:
        return _cache[code]

    if code in _extra:
        pack = _extra[code]()
    elif code in _BUILTIN:
        module: Any = importlib.import_module(_BUILTIN[code])
        if not hasattr(module, "build_pack"):
            raise UnknownLanguageError(
                f"{_BUILTIN[code]} does not expose build_pack()"
            )
        pack = module.build_pack()
    else:
        raise UnknownLanguageError(
            f"no language pack '{code}'; available: {', '.join(available())}"
        )

    if pack.code != code:
        raise ValueError(f"pack registered as '{code}' reports code '{pack.code}'")
    _cache[code] = pack
    return pack
