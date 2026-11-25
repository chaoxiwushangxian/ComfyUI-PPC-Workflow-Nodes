"""Match VRGDG_PythonCodeRunner result packing without executing user code.

The runner returns ``(result_text, result_json, has_error)``. On success a
string result is copied and a dict/list is ``json.dumps(..., ensure_ascii=False,
indent=2)``. On any Exception the text is ``f"{type(e).__name__}: {e}"``, the
JSON output is empty, and ``has_error`` is true. Tracebacks are not included.
"""

from __future__ import annotations

import json


def pack_success(result_value):
    if isinstance(result_value, str):
        result_text = result_value
    else:
        try:
            result_text = json.dumps(result_value, ensure_ascii=False, indent=2)
        except Exception:
            result_text = str(result_value)

    result_json = ""
    if isinstance(result_value, (dict, list)):
        result_json = json.dumps(result_value, ensure_ascii=False, indent=2)
    elif isinstance(result_text, str) and result_text.strip():
        try:
            parsed = json.loads(result_text)
            result_json = json.dumps(parsed, ensure_ascii=False, indent=2)
        except Exception:
            result_json = ""
    return (result_text, result_json, False)


def pack_error(exc: BaseException):
    return (f"{type(exc).__name__}: {exc}", "", True)
