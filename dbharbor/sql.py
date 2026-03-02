
import os
import urllib
from sqlalchemy import create_engine
import pandas as pd
import numpy as np


#%% Microsoft SQL

class SQL:
    def __init__(self
                 , server = os.getenv('SQL_SERVER', 'localhost')
                 , db = os.getenv('SQL_DB')
                 , uid = os.getenv('SQL_UID')
                 , pwd = os.getenv('SQL_PWD')
                 , driver = os.getenv('SQL_DRIVER', 'ODBC Driver 17 for SQL Server')
                 ):

        driver_str = f'DRIVER={driver};'
        server_str = f'SERVER={server};'
        db_str = f'DATABASE={db};'

        try:
            uid_str = ''
            pwd_str = ''
            trusted_conn_str = 'trusted_connection=yes'
            con_str_write = urllib.parse.quote_plus(driver_str + server_str + db_str + trusted_conn_str + uid_str + pwd_str)
            self.con = create_engine(
                'mssql+pyodbc:///?odbc_connect={}'.format(con_str_write),
                fast_executemany=True,
                isolation_level="AUTOCOMMIT",
                pool_pre_ping=True
            )
            self.run('SELECT 1')

        except:
            uid_str = f'UID={uid};'
            pwd_str = f'PWD={pwd};'
            trusted_conn_str = ''
            con_str_write = urllib.parse.quote_plus(driver_str + server_str + db_str + trusted_conn_str + uid_str + pwd_str)
            self.con = create_engine(
                'mssql+pyodbc:///?odbc_connect={}'.format(con_str_write),
                fast_executemany=True,
                isolation_level="AUTOCOMMIT",
                pool_pre_ping=True
            )
            self.run('SELECT 1')


    def read(self, sql):
        with self.con.connect() as connection:
            return pd.read_sql_query(sql=sql, con=connection)


    def run(self, sql):
        con_pyodbc = self.con.raw_connection()
        with con_pyodbc.cursor() as cursor:
            cursor.execute(sql)
            while cursor.nextset():
                pass


    def __update_dtype(self, df, column, dtype):
        dict_dtype = {
            'object':'varchar(max_len_a)',
            'string':'varchar(max_len_a)',
            'int64':'max_len_aint',
            'float64':'decimal(max_len_a, max_len_b)',
            'bool':'bit',
            'boolean':'bit',
            'datetime64':'datetime',
            'datetime64[ns]':'datetime',
            'datetime64[us]':'datetime',
            }
        dtype = str(dtype).lower()
        max_len_a = ''
        max_len_b = ''
        if dtype == 'object' or dtype == 'string':
            max_len_a = df[column].dropna().astype(str).str.len().max() + 5
            if max_len_a > 8000:
                max_len_a = 'max'
        elif dtype == 'float64':
            parts = df[column].dropna().astype(str).str.split('.')
            front_len = parts.str[0].str.len().max()
            back_len = parts.str[1].str.len().fillna(0).astype(int).max()
            max_len_a = int(front_len) + int(back_len) + 2
            max_len_b = int(back_len)
        elif dtype == 'int64':
            dtype_max = df[column].dropna().abs().max()
            if dtype_max <= 99:
                max_len_a = 'tiny'
            elif dtype_max <= 9999:
                max_len_a = 'small'
            elif dtype_max > 999999999:
                max_len_a = 'big'
        sql_type = dict_dtype[str(dtype)]
        sql_type = sql_type.replace('max_len_a', str(max_len_a))
        sql_type = sql_type.replace('max_len_b', str(max_len_b))
        sql_column = f'[{column}] {sql_type}'
        return sql_column


    def create_table(self, df, name, schema='dbo', replace=False, extras=False, **kwargs):
        column_list = []
        for column, dtype in df.dtypes.items():
            if column == 'RowLoadDateTime' and extras == True:
                pass
            else:
                column_list.append(self.__update_dtype(df, column, dtype))
        columns = ',\n'.join(column_list)
        sql_create = ''
        if replace == True:
            sql_create += f"DROP TABLE IF EXISTS {schema}.{name}\n"
        sql_create += f"CREATE TABLE {schema}.{name} ("
        if extras == True:
            sql_create += f"""
            ID{name} INT IDENTITY(1, 1) NOT NULL,
            {columns},
            RowLoadDateTime DATETIME NOT NULL CONSTRAINT DF_{name}_RowLoad DEFAULT (GETDATE()),
            CONSTRAINT PK_{name} PRIMARY KEY (ID{name})
            )"""
        else:
            sql_create += f"{columns})"
        self.run(sql_create)


    def to_sql(self, df, name, schema='dbo', if_exists='fail', index=True, **kwargs):
        df_copy = df.copy()
        if index == True:
            df_copy.reset_index(inplace=True)

        if if_exists == 'replace':
            self.create_table(df_copy, name, schema, replace=True, **kwargs)
        elif if_exists == 'fail':
            self.create_table(df_copy, name, schema, replace=False, **kwargs)
        elif if_exists == 'append':
            try:
                self.create_table(df_copy, name, schema, replace=False, **kwargs)
            except:
                pass
        else:
            raise(Exception('if_exists value is invalid, please choose between (fail, replace, append)'))

        df_copy = df_copy.replace({np.nan: None})
        df_copy.to_sql(name, schema=schema, if_exists='append', index=False, con=self.con)

        return True