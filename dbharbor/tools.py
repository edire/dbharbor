
import io
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
    if index_prename == None:
        df_copy.index.name = 'index'
    index_name = df_copy.index.names

    buf = io.StringIO()
    df_copy.to_csv(buf, index=True)
    buf.seek(0)
    df_copy = pd.read_csv(buf, index_col=index_name)

    df_copy.index.name = index_prename
    df_copy = df_copy.convert_dtypes()
    return df_copy


