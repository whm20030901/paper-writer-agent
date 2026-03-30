from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

CSV_EXPORT_FIELDS = [
    "run_id",
    "task",
    "quality_score",
    "stop_reason",
    "iterations_used",
    "duration_ms",
    "created_at",
]

CSV_EXPORT_ALLOWED_FIELDS = [
    "run_id",
    "parent_run_id",
    "root_run_id",
    "task",
    "quality_score",
    "stop_reason",
    "iterations_used",
    "duration_ms",
    "created_at",
]


def parse_export_fields(fields: str | None) -> list[str]:
    if not fields:
        return CSV_EXPORT_FIELDS
    selected = [field.strip() for field in fields.split(",") if field.strip()]
    if not selected:
        return CSV_EXPORT_FIELDS
    invalid = [field for field in selected if field not in CSV_EXPORT_ALLOWED_FIELDS]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"unsupported export fields: {', '.join(invalid)}",
        )

    deduped: list[str] = []
    for field in selected:
        if field not in deduped:
            deduped.append(field)
    return deduped


def sanitize_csv_cell(value: object) -> object:
    if isinstance(value, str) and value and value[0] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def parse_export_delimiter(delimiter: str) -> str:
    allowed = {
        "comma": ",",
        "tab": "\t",
        "semicolon": ";",
        "pipe": "|",
    }
    value = allowed.get(delimiter)
    if value is None:
        raise HTTPException(status_code=422, detail="unsupported delimiter; use comma|tab|semicolon|pipe")
    return value


def parse_export_line_ending(line_ending: str) -> str:
    allowed = {
        "lf": "\n",
        "crlf": "\r\n",
    }
    value = allowed.get(line_ending)
    if value is None:
        raise HTTPException(status_code=422, detail="unsupported line_ending; use lf|crlf")
    return value


def parse_export_quote_char(quote_char: str) -> str:
    allowed = {
        "double": '"',
        "single": "'",
    }
    value = allowed.get(quote_char)
    if value is None:
        raise HTTPException(status_code=422, detail="unsupported quote_char; use double|single")
    return value


def normalize_csv_cell(
    value: object,
    null_value: str,
    trim_strings: bool,
    empty_as_null: bool,
    max_cell_length: int | None,
) -> object:
    if value is None:
        return null_value
    if trim_strings and isinstance(value, str):
        value = value.strip()
    if empty_as_null and value == "":
        return null_value
    if max_cell_length is not None and isinstance(value, str) and len(value) > max_cell_length:
        return value[:max_cell_length]
    return value


def parse_export_escape_style(escape_style: str) -> tuple[bool, str | None]:
    if escape_style == "double":
        return True, None
    if escape_style == "backslash":
        return False, "\\"
    raise HTTPException(status_code=422, detail="unsupported escape_style; use double|backslash")


def build_export_headers(
    *,
    total: int,
    limit: int,
    offset: int,
    returned: int,
    selected_fields: list[str],
    default_fields_used: bool,
    delimiter: str,
    quote_all: bool,
    quote_char: str,
    include_header: bool,
    line_ending: str,
    null_value: str,
    trim_strings: bool,
    empty_as_null: bool,
    sanitize_cells: bool,
    include_bom: bool,
    compress: bool,
    sort_by: str,
    sort_order: str,
    stop_reason: str | None,
    parent_run_id: str | None,
    root_run_id: str | None,
    lineage_scope: str | None,
    query: str | None,
    created_after: datetime | None,
    created_before: datetime | None,
    min_quality_score: int | None,
    max_quality_score: int | None,
    min_duration_ms: int | None,
    max_duration_ms: int | None,
    escape_style: str,
    max_cell_length: int | None,
) -> dict[str, str]:
    has_data = returned > 0
    offset_end = offset + returned
    remaining = max(total - offset_end, 0)
    limit_reached = returned == limit
    has_more = offset_end < total
    is_last_page = not has_more
    next_offset = str(offset_end) if has_more else ""
    page_index = (offset // limit) + 1
    total_pages = max(1, (total + limit - 1) // limit)
    next_page_index = str(page_index + 1) if has_more else ""

    filter_values = {
        "stop_reason": stop_reason,
        "parent_run_id": parent_run_id,
        "root_run_id": root_run_id,
        "lineage_scope": lineage_scope,
        "q": query,
        "created_after": created_after,
        "created_before": created_before,
        "min_quality_score": min_quality_score,
        "max_quality_score": max_quality_score,
        "min_duration_ms": min_duration_ms,
        "max_duration_ms": max_duration_ms,
    }
    active_filters = [value for value in filter_values.values() if value is not None and value != ""]
    active_filter_keys = [key for key, value in filter_values.items() if value is not None and value != ""]
    has_filters = len(active_filters) > 0

    return {
        "Content-Disposition": "attachment; filename=runs_export.csv",
        "X-Export-Generated-At": datetime.now(timezone.utc).isoformat(),
        "X-Export-Total": str(total),
        "X-Export-Limit": str(limit),
        "X-Export-Offset": str(offset),
        "X-Export-Returned": str(returned),
        "X-Export-Has-Data": str(has_data).lower(),
        "X-Export-Offset-End": str(offset_end),
        "X-Export-Remaining": str(remaining),
        "X-Export-Limit-Reached": str(limit_reached).lower(),
        "X-Export-Page-Index": str(page_index),
        "X-Export-Total-Pages": str(total_pages),
        "X-Export-Next-Page-Index": next_page_index,
        "X-Export-Is-Last-Page": str(is_last_page).lower(),
        "X-Export-Has-More": str(has_more).lower(),
        "X-Export-Next-Offset": next_offset,
        "X-Export-Has-Filters": str(has_filters).lower(),
        "X-Export-Filter-Count": str(len(active_filters)),
        "X-Export-Filter-Keys": ",".join(active_filter_keys),
        "X-Export-Delimiter": delimiter,
        "X-Export-Quote-All": str(quote_all).lower(),
        "X-Export-Quote-Char": quote_char,
        "X-Export-Include-Header": str(include_header).lower(),
        "X-Export-Line-Ending": line_ending,
        "X-Export-Null-Value": null_value,
        "X-Export-Trim-Strings": str(trim_strings).lower(),
        "X-Export-Empty-As-Null": str(empty_as_null).lower(),
        "X-Export-Sanitize-Cells": str(sanitize_cells).lower(),
        "X-Export-Include-Bom": str(include_bom).lower(),
        "X-Export-Compressed": str(compress).lower(),
        "X-Export-Fields": ",".join(selected_fields),
        "X-Export-Field-Count": str(len(selected_fields)),
        "X-Export-Default-Fields": str(default_fields_used).lower(),
        "X-Export-Sort-By": sort_by,
        "X-Export-Sort-Order": sort_order,
        "X-Export-Stop-Reason": stop_reason or "",
        "X-Export-Parent-Run-Id": parent_run_id or "",
        "X-Export-Root-Run-Id": root_run_id or "",
        "X-Export-Lineage-Scope": lineage_scope or "",
        "X-Export-Query": query or "",
        "X-Export-Created-After": created_after.isoformat() if created_after else "",
        "X-Export-Created-Before": created_before.isoformat() if created_before else "",
        "X-Export-Min-Quality-Score": "" if min_quality_score is None else str(min_quality_score),
        "X-Export-Max-Quality-Score": "" if max_quality_score is None else str(max_quality_score),
        "X-Export-Min-Duration-Ms": "" if min_duration_ms is None else str(min_duration_ms),
        "X-Export-Max-Duration-Ms": "" if max_duration_ms is None else str(max_duration_ms),
        "X-Export-Escape-Style": escape_style,
        "X-Export-Max-Cell-Length": "" if max_cell_length is None else str(max_cell_length),
    }
