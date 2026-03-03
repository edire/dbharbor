
import io
import datetime
import numpy as np
import pandas as pd
from datetime import datetime as dt


#%% Functions

def clean(df, rowloadtime=False, drop_cols=True):
    df.dropna(how='all', axis=0, inplace=True)
    if drop_cols == True:
        df.dropna(how='all', axis=1, inplace=True)
    df = clean_column_names(df)
    df = clean_data(df)
    df = clean_dtypes(df)
    if rowloadtime == True:
        df['RowLoadDateTime'] = dt.now()
    return df


def clean_data(df):
    for col in df.select_dtypes(include='number').columns:
        df[col] = df[col].replace(0, np.nan)
    for col in df.select_dtypes(include='object').columns:
        df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x).replace('', np.nan)
    return df


def clean_column_names(df):
    df.columns = [clean_string(el) for el in df.columns]
    return df


def clean_string(str_input):
    str_input = str(str_input)
    for sc in [' ', '\\n']:
        str_input = str_input.replace(sc, '_')

    str_new = ''
    for ch in str_input:
        if ((ch.lower()>='a' and ch.lower()<='z') or (ch>='0' and ch<='9') or ch=='_'):
            str_new += ch

    while '__' in str_new:
        str_new = str_new.replace('__', '_')
    if len(str_new) > 1:
        if str_new[0] == '_':
            str_new = str_new[1:]
        if str_new[-1] == '_':
            str_new = str_new[:-1]

    return str_new


def clean_dtypes(df):
    df_copy = df.copy()
    index_prename = df_copy.index.name
    if index_prename is None:
        df_copy.index.name = 'index'
    index_name = df_copy.index.names

    # CSV round-trip normalizes mixed-type object columns to consistent text
    # representations so convert_dtypes() can infer the best type cleanly.
    buf = io.StringIO()
    df_copy.to_csv(buf, index=True)
    buf.seek(0)
    df_copy = pd.read_csv(buf, index_col=index_name, low_memory=False)

    df_copy.index.name = index_prename
    df_copy = df_copy.convert_dtypes()

    # Datetime inference: convert string columns where every non-null value
    # parses successfully (null count unchanged — no data is ever lost).
    for col in df_copy.select_dtypes(include='string').columns:
        if df_copy[col].isna().all():
            continue
        parsed = pd.to_datetime(df_copy[col], format='mixed', errors='coerce')
        if parsed.isna().sum() == df_copy[col].isna().sum():
            df_copy[col] = parsed

    # Resolve any remaining object-dtype columns (e.g. Python date/datetime
    # objects or mixed-numeric objects that survived the round-trip).
    # Same null-count-unchanged rule applies throughout.
    for col in df_copy.select_dtypes(include='object').columns:
        if df_copy[col].isna().all():
            df_copy[col] = df_copy[col].astype('string')
            continue

        sample = df_copy[col].dropna().iloc[0]

        if isinstance(sample, (datetime.date, datetime.datetime)):
            parsed = pd.to_datetime(df_copy[col], errors='coerce')
            if parsed.isna().sum() == df_copy[col].isna().sum():
                df_copy[col] = parsed
            else:
                df_copy[col] = df_copy[col].apply(lambda x: str(x) if pd.notna(x) else None).astype('string')

        elif isinstance(sample, (int, float, np.integer, np.floating)):
            converted = pd.to_numeric(df_copy[col], errors='coerce')
            if converted.isna().sum() == df_copy[col].isna().sum():
                df_copy[col] = converted
            else:
                df_copy[col] = df_copy[col].apply(lambda x: str(x) if pd.notna(x) else None).astype('string')

        else:
            df_copy[col] = df_copy[col].apply(lambda x: str(x) if pd.notna(x) else None).astype('string')

    return df_copy
