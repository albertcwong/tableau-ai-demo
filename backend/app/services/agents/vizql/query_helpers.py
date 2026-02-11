"""Shared query transformation helpers for VizQL agents."""
import logging
import re
from typing import Any, Dict, Optional, Set

from difflib import get_close_matches

logger = logging.getLogger(__name__)


def detect_and_apply_date_functions(
    query_draft: Dict[str, Any],
    user_query: str,
    enriched_schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Detect temporal grouping keywords and apply date functions to date fields."""
    user_query_lower = user_query.lower()
    temporal_patterns = {
        "trunc_month": ["by month", "monthly", "per month", "each month", "every month"],
        "trunc_year": ["by year", "yearly", "per year", "each year", "every year", "annually"],
        "trunc_quarter": ["by quarter", "quarterly", "per quarter", "each quarter", "every quarter"],
        "trunc_week": ["by week", "weekly", "per week", "each week", "every week"],
        "trunc_day": ["by day", "daily", "per day", "each day", "every day"],
    }
    detected_function = None
    for func_name, keywords in temporal_patterns.items():
        if any(kw in user_query_lower for kw in keywords):
            detected_function = func_name.upper()
            logger.info(f"Detected temporal grouping keyword, will apply {detected_function} function")
            break
    if not detected_function:
        return query_draft

    date_field_names: Set[str] = set()
    if enriched_schema and isinstance(enriched_schema, dict):
        for field in enriched_schema.get("fields", []):
            if field.get("dataType", "").upper() in ["DATE", "DATETIME", "TIMESTAMP"]:
                cap = field.get("fieldCaption")
                if cap:
                    date_field_names.add(cap)
    if not date_field_names:
        patterns = ["date", "time", "datetime", "timestamp", "created", "modified", "order date", "ship date", "purchase date"]
        date_field_names = set(p.title() for p in patterns) | set(p.upper() for p in patterns) | {"Order Date", "Ship Date"}

    fields = query_draft.get("query", {}).get("fields", [])
    modified = False
    for field in fields:
        cap = field.get("fieldCaption", "")
        if not field.get("function") and "calculation" not in field:
            if any(dn.lower() in cap.lower() for dn in date_field_names) or cap in date_field_names:
                field["function"] = detected_function
                logger.warning(f"🔧 AUTO-FIX: Added '{detected_function}' to date field '{cap}'")
                modified = True
    if modified:
        logger.info("Applied automatic date function fixes to query")
    return query_draft


def detect_and_apply_count_functions(
    query_draft: Dict[str, Any],
    user_query: str,
    enriched_schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Detect 'how many' queries and apply COUNTD function."""
    user_query_lower = user_query.lower()
    count_patterns = ["how many", "count of", "number of", "count distinct", "unique count"]
    if not any(p in user_query_lower for p in count_patterns):
        return query_draft

    fields = query_draft.get("query", {}).get("fields", [])
    if len(fields) == 1:
        f = fields[0]
        if not f.get("function") and f.get("fieldCaption"):
            f["function"] = "COUNTD"
            logger.warning(f"🔧 AUTO-FIX: Added 'COUNTD' to '{f.get('fieldCaption')}'")
            return query_draft

    for field in fields:
        cap = field.get("fieldCaption", "")
        if not field.get("function") and cap:
            for word in cap.lower().split():
                if word in ["customer", "order", "product", "region", "category", "state", "city", "country"]:
                    for p in count_patterns:
                        idx = user_query_lower.find(p)
                        if idx >= 0 and word in user_query_lower[idx:]:
                            field["function"] = "COUNTD"
                            logger.warning(f"🔧 AUTO-FIX: Added 'COUNTD' to '{cap}'")
                            return query_draft
    return query_draft


def detect_and_apply_context_filters(query_draft: Dict[str, Any], user_query: str) -> Dict[str, Any]:
    """Detect hierarchical filter dependencies and apply context:true."""
    user_query_lower = user_query.lower()
    hierarchical_patterns = [
        (r"given\s+(?:the\s+)?(?:top|best|largest|highest|biggest)\s+(\d+\s+)?(\w+)(?:.*?)(?:,|\band\b|\bthen\b)?\s*(?:show|find|give|get|what|which)", "given X, show Y"),
        (r"for\s+(?:the\s+)?(?:top|best|largest|highest|biggest)\s+(\d+\s+)?(\w+)(?:.*?)(?:,|\band\b|\bthen\b)?\s*(?:show|find|give|get|what|which)", "for X, find Y"),
        (r"within\s+(?:the\s+)?(?:top|best|largest|highest|biggest)?\s*(\d+\s+)?(\w+)(?:.*?)(?:,|\band\b|\bthen\b)?\s*(?:show|find|give|get|what|which)", "within X, show Y"),
        (r"in\s+(?:the\s+)?(?:top|best|largest|highest|biggest)?\s*(\d+\s+)?(\w+)(?:.*?)(?:,|\band\b|\bthen\b)?\s*(?:show|find|give|get|what|which)", "in X, what are Y"),
        (r"first\s+(?:find|get|show|the)?\s*(?:top|best|largest|highest|biggest)?\s*(\d+\s+)?(\w+)(?:.*?)(?:,|\band\b)?\s*(?:then|after|next)", "first X, then Y"),
    ]
    if not any(re.search(pat, user_query_lower) for pat, _ in hierarchical_patterns):
        return query_draft

    filters = query_draft.get("query", {}).get("filters", [])
    if len(filters) < 2 or any(f.get("context") for f in filters):
        return query_draft

    modified = False
    if len(filters) == 2:
        ft = filters[0].get("filterType", "")
        if ft in ["SET", "TOP", "QUANTITATIVE_NUMERICAL", "DATE"]:
            filters[0]["context"] = True
            logger.warning(f"🔧 AUTO-FIX: Applied context:true to first filter (type: {ft})")
            modified = True
    else:
        for i, f in enumerate(filters):
            if f.get("filterType") in ["SET", "DATE"] and not f.get("context"):
                f["context"] = True
                logger.warning(f"🔧 AUTO-FIX: Applied context:true to filter at position {i}")
                modified = True
                break
        if not modified:
            top_filters = [(i, f) for i, f in enumerate(filters) if f.get("filterType") == "TOP"]
            if len(top_filters) >= 2:
                top_filters.sort(key=lambda x: x[1].get("howMany", 999))
                top_filters[0][1]["context"] = True
                modified = True
    if modified:
        logger.info("Applied automatic context filter fixes to query")
    return query_draft


def adjust_calculated_field_names(
    query_draft: Dict[str, Any],
    enriched_schema: Optional[Dict[str, Any]] = None,
    schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Adjust calculated field names to avoid conflicts with existing schema fields."""
    existing_fields: Set[str] = set()
    if enriched_schema and isinstance(enriched_schema, dict):
        for field_info in (enriched_schema.get("field_map") or {}).values():
            cap = field_info.get("fieldCaption", "")
            if cap:
                existing_fields.add(cap.lower())
    elif schema and isinstance(schema, dict):
        for col in schema.get("columns", []):
            name = col.get("name", "")
            if name:
                existing_fields.add(name.lower())
    if not existing_fields:
        return query_draft

    fields = query_draft.get("query", {}).get("fields", [])
    modified = False
    for field in fields:
        if "calculation" not in field:
            continue
        cap = field.get("fieldCaption", "")
        if not cap or cap.lower() not in existing_fields:
            continue
        suffixes = [" (Calculated)", " Calculated", " Ratio", " Margin", " Rate"]
        new_name = None
        for suffix in suffixes:
            candidate = cap + suffix
            if candidate.lower() not in existing_fields:
                new_name = candidate
                break
        if not new_name:
            for i in range(1, 101):
                candidate = f"{cap} (Calculated {i})"
                if candidate.lower() not in existing_fields:
                    new_name = candidate
                    break
        if new_name:
            field["fieldCaption"] = new_name
            logger.warning(f"🔧 AUTO-FIX: Renamed calculated field '{cap}' to '{new_name}'")
            modified = True
    if modified:
        logger.info("Applied automatic calculated field name adjustments to query")
    return query_draft


def remove_fieldcaption_from_calculated_filters(query_draft: Dict[str, Any]) -> Dict[str, Any]:
    """Remove fieldCaption from filter field objects that have a calculation key."""
    if not query_draft or not isinstance(query_draft, dict):
        return query_draft
    filters = query_draft.get("query", {}).get("filters", [])
    if not filters:
        return query_draft
    modified = False
    for f in filters:
        if isinstance(f, dict):
            field = f.get("field")
            if isinstance(field, dict) and "calculation" in field and "fieldCaption" in field:
                del field["fieldCaption"]
                modified = True
    if modified:
        logger.info("Removed fieldCaption from calculated filter fields")
    return query_draft


def validate_and_correct_filter_values(
    query_draft: Dict[str, Any],
    enriched_schema: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Validate SET filter values against enriched schema sample_values. Correct when possible."""
    if not enriched_schema or not enriched_schema.get("fields"):
        return query_draft
    field_map = enriched_schema.get("field_map") or {
        f.get("fieldCaption", "").lower(): f for f in enriched_schema.get("fields", []) if f.get("fieldCaption")
    }
    filters = query_draft.get("query", {}).get("filters", [])
    modified = False
    for f in filters:
        if f.get("filterType") != "SET":
            continue
        field_obj = f.get("field")
        if not isinstance(field_obj, dict):
            continue
        cap = field_obj.get("fieldCaption")
        if not cap:
            continue
        field_info = field_map.get(cap.lower())
        if not field_info:
            continue
        sample_values = field_info.get("sample_values", [])
        cardinality = field_info.get("cardinality")
        if not sample_values or (cardinality is not None and cardinality > len(sample_values)):
            continue
        values = f.get("values", [])
        if not values:
            continue
        valid_set = set(str(v) for v in sample_values)
        corrected = []
        filter_modified = False
        for v in values:
            v_str = str(v)
            if v_str in valid_set:
                corrected.append(v)
                continue
            matches = get_close_matches(v_str, [str(s) for s in sample_values], n=1, cutoff=0.6)
            if matches:
                corrected.append(matches[0])
                logger.warning(f"Corrected SET filter value '{v_str}' -> '{matches[0]}'")
                filter_modified = True
            else:
                corrected.append(v)
        if filter_modified:
            f["values"] = corrected
            modified = True
    if modified:
        logger.info("Applied filter value corrections against enriched schema")
    return query_draft
