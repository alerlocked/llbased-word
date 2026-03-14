import sys
sys.path.insert(0, '.')
from app.services.csv_export_service import CSVExportService
import pandas as pd

service = CSVExportService()
df = pd.DataFrame({'A': ['  text1  ', None, 'text3']})
print('Step 1 - original:', repr(df.iloc[0]['A']))

df = df.dropna(how='all')
print('Step 2 - after dropna:', repr(df.iloc[0]['A']))

df = df.dropna(axis=1, how='all')
print('Step 3 - after dropna cols:', repr(df.iloc[0]['A']))

df = df.fillna('')
print('Step 4 - after fillna:', repr(df.iloc[0]['A']))

for col in df.columns:
    print('Column:', col, 'dtype:', df[col].dtype)
    if df[col].dtype == object:
        df[col] = df[col].apply(lambda x: str(x).strip() if isinstance(x, str) else x)
        print('Step 5 - after apply:', repr(df.iloc[0]['A']))