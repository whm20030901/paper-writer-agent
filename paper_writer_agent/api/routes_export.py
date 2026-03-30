from __future__ import annotations

import csv
import gzip
import io
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, Query, Response

from ..core.config import Settings
from ..services.paper_service import PaperService
from .csv_export import (
    CSV_EXPORT_FIELDS,
    build_export_headers,
    normalize_csv_cell,
    parse_export_delimiter,
    parse_export_escape_style,
    parse_export_fields,
    parse_export_line_ending,
    parse_export_quote_char,
    sanitize_csv_cell,
)
from .run_query import build_run_query_filters
from .security import extract_api_key_header, verify_api_key


def register_export_routes(app: FastAPI, cfg: Settings, paper_service: PaperService) -> None:
    @app.get("/v1/papers/runs/export.csv")
    def export_runs_csv(
        limit: int = Query(default=1000, ge=1, le=5000),
        offset: int = Query(default=0, ge=0),
        stop_reason: str | None = Query(default=None),
        parent_run_id: str | None = Query(default=None, min_length=1, max_length=200),
        root_run_id: str | None = Query(default=None, min_length=1, max_length=200),
        lineage_scope: Literal["root", "derived"] | None = Query(default=None),
        q: str | None = Query(default=None, min_length=1, max_length=200),
        created_after: datetime | None = Query(default=None),
        created_before: datetime | None = Query(default=None),
        min_quality_score: int | None = Query(default=None, ge=0, le=10),
        max_quality_score: int | None = Query(default=None, ge=0, le=10),
        min_duration_ms: int | None = Query(default=None, ge=0),
        max_duration_ms: int | None = Query(default=None, ge=0),
        sort_by: Literal["created_at", "quality_score", "duration_ms"] = Query(default="created_at"),
        sort_order: Literal["asc", "desc"] = Query(default="desc"),
        fields: str | None = Query(default=None, description="comma-separated export columns"),
        include_bom: bool = Query(default=False, description="prepend UTF-8 BOM for spreadsheet tools"),
        compress: bool = Query(default=False, description="gzip-compress CSV response payload"),
        sanitize_cells: bool = Query(default=True, description="escape formula-like cells for spreadsheet safety"),
        delimiter: Literal["comma", "tab", "semicolon", "pipe"] = Query(default="comma", description="csv delimiter style"),
        quote_all: bool = Query(default=False, description="quote all CSV fields"),
        quote_char: Literal["double", "single"] = Query(default="double", description="CSV quote character"),
        include_header: bool = Query(default=True, description="include CSV header row"),
        line_ending: Literal["lf", "crlf"] = Query(default="lf", description="line ending style"),
        null_value: str = Query(default="", max_length=32, description="replacement text for null fields"),
        trim_strings: bool = Query(default=False, description="trim leading/trailing spaces for string fields"),
        empty_as_null: bool = Query(default=False, description="replace empty string with null_value"),
        escape_style: Literal["double", "backslash"] = Query(default="double", description="CSV quote escaping strategy"),
        max_cell_length: int | None = Query(default=None, ge=1, le=100000, description="max length for exported string cells"),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> Response:
        verify_api_key(cfg.api_key, x_api_key)
        filters = build_run_query_filters(
            stop_reason=stop_reason,
            parent_run_id=parent_run_id,
            root_run_id=root_run_id,
            lineage_scope=lineage_scope,
            query=q,
            created_after=created_after,
            created_before=created_before,
            min_quality_score=min_quality_score,
            max_quality_score=max_quality_score,
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
        )

        filter_kwargs = filters.as_service_kwargs()
        total = paper_service.count_runs(**filter_kwargs)
        runs = paper_service.list_runs(
            limit=limit,
            offset=offset,
            **filter_kwargs,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        selected_fields = parse_export_fields(fields)
        using_default_fields = selected_fields == CSV_EXPORT_FIELDS
        delimiter_value = parse_export_delimiter(delimiter)
        line_ending_value = parse_export_line_ending(line_ending)
        quote_char_value = parse_export_quote_char(quote_char)
        doublequote_value, escapechar_value = parse_export_escape_style(escape_style)

        output = io.StringIO()
        writer = csv.writer(
            output,
            delimiter=delimiter_value,
            quotechar=quote_char_value,
            lineterminator=line_ending_value,
            quoting=csv.QUOTE_ALL if quote_all else csv.QUOTE_MINIMAL,
            doublequote=doublequote_value,
            escapechar=escapechar_value,
        )
        if include_header:
            writer.writerow(selected_fields)
        for run in runs:
            row = [
                normalize_csv_cell(getattr(run, field), null_value, trim_strings, empty_as_null, max_cell_length)
                for field in selected_fields
            ]
            if sanitize_cells:
                row = [sanitize_csv_cell(value) for value in row]
            writer.writerow(row)

        returned = len(runs)
        csv_text = output.getvalue()
        if include_bom:
            csv_text = "﻿" + csv_text

        content: bytes | str = csv_text
        media_type = "text/csv; charset=utf-8"
        headers = build_export_headers(
            total=total,
            limit=limit,
            offset=offset,
            returned=returned,
            selected_fields=selected_fields,
            default_fields_used=using_default_fields,
            delimiter=delimiter,
            quote_all=quote_all,
            quote_char=quote_char,
            include_header=include_header,
            line_ending=line_ending,
            null_value=null_value,
            trim_strings=trim_strings,
            empty_as_null=empty_as_null,
            sanitize_cells=sanitize_cells,
            include_bom=include_bom,
            compress=compress,
            sort_by=sort_by,
            sort_order=sort_order,
            stop_reason=stop_reason,
            parent_run_id=parent_run_id,
            root_run_id=root_run_id,
            lineage_scope=lineage_scope,
            query=q,
            created_after=created_after,
            created_before=created_before,
            min_quality_score=min_quality_score,
            max_quality_score=max_quality_score,
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
            escape_style=escape_style,
            max_cell_length=max_cell_length,
        )
        if compress:
            content = gzip.compress(csv_text.encode("utf-8"))
            media_type = "application/gzip"
            headers["Content-Disposition"] = "attachment; filename=runs_export.csv.gz"

        return Response(content=content, media_type=media_type, headers=headers)
