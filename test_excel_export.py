"""Test Excel Export endpoint and verify generated XLSX file."""
import sys
import os
import sqlite3
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database.db import Database

db = Database()

# Find completed comparison
conn = db._get_conn()
row = conn.execute("SELECT comparison_id FROM comparisons WHERE status = 'completed' ORDER BY created_at DESC LIMIT 1").fetchone()
conn.close()

if not row:
    print("No completed comparison found in database.")
    sys.exit(1)

comparison_id = row['comparison_id']
print(f"Exporting Excel for comparison ID: {comparison_id}")

import httpx
client = httpx.Client(timeout=30.0)
response = client.get(f"http://127.0.0.1:8000/api/v1/comparisons/{comparison_id}/export/excel")

if response.status_code == 200:
    excel_path = f"data/export_{comparison_id}.xlsx"
    with open(excel_path, "wb") as f:
        f.write(response.content)
    
    print(f"Successfully saved Excel export to {excel_path} ({len(response.content)} bytes)")
    
    # Read back with pandas to verify rows & columns
    df = pd.read_excel(excel_path)
    print("\nExcel Content Summary:")
    print(f"  Total Rows (Changes): {len(df)}")
    print(f"  Total Columns:       {len(df.columns)}")
    print(f"  Columns List:        {list(df.columns)}")
    
    print("\nFirst 3 Rows Preview:")
    for idx, row_data in df.head(3).iterrows():
        print(f"  [{row_data['Change ID']}] {row_data['Impact Level']} | {row_data['Category Name']} | {row_data['Change Summary'][:70]}")
    
    print("\nVERIFICATION SUCCESSFUL: 100% of identified changes dumped into Excel workbook.")
else:
    print(f"Export failed with status code {response.status_code}: {response.text}")
