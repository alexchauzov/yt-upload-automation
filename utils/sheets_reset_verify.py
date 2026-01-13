#!/usr/bin/env python3
"""Reset runtime spreadsheet from template and verify data match.

Uses Sheets API copyTo to sync sheets from template to runtime spreadsheet.
This approach works with service accounts that cannot create new spreadsheets.

Env vars:
    GOOGLE_APPLICATION_CREDENTIALS - path to service account JSON
    TEMPLATE_SPREADSHEET_ID - source spreadsheet (readonly)
    RUNTIME_SPREADSHEET_ID - destination spreadsheet (will be overwritten)
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build


def get_sheets_service():
    """Build Google Sheets API service."""
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        print("ERROR: GOOGLE_APPLICATION_CREDENTIALS env var not set", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(creds_path):
        print(f"ERROR: Credentials file not found: {creds_path}", file=sys.stderr)
        sys.exit(1)

    credentials = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=credentials)


def get_spreadsheet_sheets(service, spreadsheet_id: str) -> list[dict]:
    """Get list of sheets with their sheetId and title."""
    result = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets.properties(sheetId,title)"
    ).execute()
    return [
        {"sheetId": s["properties"]["sheetId"], "title": s["properties"]["title"]}
        for s in result.get("sheets", [])
    ]


def get_sheet_values(service, spreadsheet_id: str, sheet_title: str) -> list[list[str]]:
    """Get all values from a sheet."""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_title}'",
            valueRenderOption="UNFORMATTED_VALUE"
        ).execute()
        return result.get("values", [])
    except Exception:
        return []


def normalize_values(values: list[list]) -> list[list[str]]:
    """Normalize values for comparison: trim strings, convert None to empty."""
    if not values:
        return []

    normalized = []
    for row in values:
        norm_row = []
        for cell in row:
            if cell is None:
                norm_row.append("")
            elif isinstance(cell, str):
                norm_row.append(cell.strip())
            else:
                norm_row.append(str(cell))
        normalized.append(norm_row)

    while normalized and all(c == "" for c in normalized[-1]):
        normalized.pop()

    if not normalized:
        return []

    max_col = 0
    for row in normalized:
        while row and row[-1] == "":
            row.pop()
        max_col = max(max_col, len(row))

    for row in normalized:
        while len(row) < max_col:
            row.append("")

    return normalized


def reset_runtime(service, template_id: str, runtime_id: str) -> bool:
    """Reset runtime spreadsheet by copying all sheets from template."""
    print(f"Resetting runtime spreadsheet...")
    print(f"  Template: {template_id}")
    print(f"  Runtime:  {runtime_id}")
    print()

    template_sheets = get_spreadsheet_sheets(service, template_id)
    runtime_sheets = get_spreadsheet_sheets(service, runtime_id)

    print(f"Template sheets: {[s['title'] for s in template_sheets]}")
    print(f"Runtime sheets (before): {[s['title'] for s in runtime_sheets]}")
    print()

    if not template_sheets:
        print("ERROR: Template spreadsheet has no sheets", file=sys.stderr)
        return False

    old_sheet_ids = [s["sheetId"] for s in runtime_sheets]

    new_sheets = []
    for ts in template_sheets:
        print(f"  Copying sheet '{ts['title']}'...")
        result = service.spreadsheets().sheets().copyTo(
            spreadsheetId=template_id,
            sheetId=ts["sheetId"],
            body={"destinationSpreadsheetId": runtime_id}
        ).execute()
        new_sheets.append({
            "sheetId": result["sheetId"],
            "desiredTitle": ts["title"]
        })
        print(f"    -> Created sheet ID {result['sheetId']} ('{result.get('title', 'unknown')}')")

    print()
    print("Applying batch update (delete old + rename new)...")

    requests = []

    for old_id in old_sheet_ids:
        requests.append({"deleteSheet": {"sheetId": old_id}})

    for ns in new_sheets:
        requests.append({
            "updateSheetProperties": {
                "properties": {
                    "sheetId": ns["sheetId"],
                    "title": ns["desiredTitle"]
                },
                "fields": "title"
            }
        })

    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=runtime_id,
            body={"requests": requests}
        ).execute()

    final_sheets = get_spreadsheet_sheets(service, runtime_id)
    print(f"Runtime sheets (after): {[s['title'] for s in final_sheets]}")
    print()
    print("Reset complete.")
    return True


def verify_match(service, template_id: str, runtime_id: str) -> bool:
    """Verify that runtime spreadsheet matches template."""
    print("Verifying spreadsheet match...")
    print()

    template_sheets = get_spreadsheet_sheets(service, template_id)
    runtime_sheets = get_spreadsheet_sheets(service, runtime_id)

    template_titles = {s["title"] for s in template_sheets}
    runtime_titles = {s["title"] for s in runtime_sheets}

    if template_titles != runtime_titles:
        print("FAIL: Sheet names mismatch", file=sys.stderr)
        print(f"  Template: {sorted(template_titles)}", file=sys.stderr)
        print(f"  Runtime:  {sorted(runtime_titles)}", file=sys.stderr)
        only_in_template = template_titles - runtime_titles
        only_in_runtime = runtime_titles - template_titles
        if only_in_template:
            print(f"  Missing in runtime: {sorted(only_in_template)}", file=sys.stderr)
        if only_in_runtime:
            print(f"  Extra in runtime: {sorted(only_in_runtime)}", file=sys.stderr)
        return False

    print(f"Sheet names match: {sorted(template_titles)}")
    print()

    all_match = True
    for title in sorted(template_titles):
        print(f"  Checking sheet '{title}'...")

        template_values = get_sheet_values(service, template_id, title)
        runtime_values = get_sheet_values(service, runtime_id, title)

        template_norm = normalize_values(template_values)
        runtime_norm = normalize_values(runtime_values)

        if template_norm == runtime_norm:
            rows = len(template_norm)
            cols = max((len(r) for r in template_norm), default=0)
            print(f"    OK ({rows} rows, {cols} cols)")
        else:
            print(f"    FAIL: Data mismatch", file=sys.stderr)
            print(f"      Template: {len(template_norm)} rows", file=sys.stderr)
            print(f"      Runtime:  {len(runtime_norm)} rows", file=sys.stderr)

            for i, (t_row, r_row) in enumerate(zip(template_norm, runtime_norm)):
                if t_row != r_row:
                    print(f"      First diff at row {i + 1}:", file=sys.stderr)
                    print(f"        Template: {t_row[:5]}...", file=sys.stderr)
                    print(f"        Runtime:  {r_row[:5]}...", file=sys.stderr)
                    break

            all_match = False

    print()
    return all_match


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Reset runtime spreadsheet from template and verify match"
    )
    parser.add_argument(
        "--template-id",
        default=os.getenv("TEMPLATE_SPREADSHEET_ID"),
        help="Template spreadsheet ID (default: TEMPLATE_SPREADSHEET_ID env)"
    )
    parser.add_argument(
        "--runtime-id",
        default=os.getenv("RUNTIME_SPREADSHEET_ID"),
        help="Runtime spreadsheet ID (default: RUNTIME_SPREADSHEET_ID env)"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify, skip reset"
    )
    parser.add_argument(
        "--reset-only",
        action="store_true",
        help="Only reset, skip verify"
    )

    args = parser.parse_args()

    if not args.template_id:
        print("ERROR: Template spreadsheet ID not provided", file=sys.stderr)
        print("Set TEMPLATE_SPREADSHEET_ID env var or use --template-id", file=sys.stderr)
        sys.exit(1)

    if not args.runtime_id:
        print("ERROR: Runtime spreadsheet ID not provided", file=sys.stderr)
        print("Set RUNTIME_SPREADSHEET_ID env var or use --runtime-id", file=sys.stderr)
        sys.exit(1)

    service = get_sheets_service()

    success = True

    if not args.verify_only:
        print("=" * 60)
        print("RESET")
        print("=" * 60)
        if not reset_runtime(service, args.template_id, args.runtime_id):
            success = False
        print()

    if not args.reset_only:
        print("=" * 60)
        print("VERIFY")
        print("=" * 60)
        if not verify_match(service, args.template_id, args.runtime_id):
            success = False
        print()

    print("=" * 60)
    if success:
        print("SUCCESS")
    else:
        print("FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
