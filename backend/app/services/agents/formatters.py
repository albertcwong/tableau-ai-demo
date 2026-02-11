"""Shared formatter utilities for agent results."""


def format_as_table(columns: list, data: list, max_rows: int = 10) -> str:
    """Format data as a simple text table."""
    if not columns or not data:
        return "No data to display"

    # Limit rows
    display_data = data[:max_rows]

    # Calculate column widths
    col_widths = {}
    for col in columns:
        col_widths[col] = len(str(col))

    for row in display_data:
        for i, col in enumerate(columns):
            if i < len(row):
                val_len = len(str(row[i]))
                col_widths[col] = max(col_widths[col], val_len)

    # Build table
    lines = []
    header = " | ".join(str(col).ljust(col_widths[col]) for col in columns)
    lines.append(header)
    lines.append("-" * len(header))
    for row in display_data:
        row_str = " | ".join(
            str(row[i] if i < len(row) else "").ljust(col_widths[col])
            for i, col in enumerate(columns)
        )
        lines.append(row_str)
    return "\n".join(lines)
