
import os
from sqlalchemy import create_engine, text
import pandas as pd
import numpy as np
from  urllib.parse import quote_plus


#%% MySQL

class SQL:
    def __init__(self
                 , server = os.getenv('MYSQL_SERVER')
                 , db = os.getenv('MYSQL_DB')
                 , uid = os.getenv('MYSQL_UID')
                 , pwd = os.getenv('MYSQL_PWD')
                 , port = os.getenv('MYSQL_PORT', 3306)
                 ):

        try:
            self.con = create_engine(
                f'mysql+pymysql://{uid}:{pwd}@{server}:{port}/{db}',
                isolation_level="AUTOCOMMIT",
                pool_pre_ping=True
            )
            self.run('SELECT 1')
        except:
            pwd = quote_plus(pwd)
            self.con = create_engine(
                f'mysql+pymysql://{uid}:{pwd}@{server}:{port}/{db}',
                isolation_level="AUTOCOMMIT",
                pool_pre_ping=True
            )
            self.run('SELECT 1')


    def read(self, sql):
        sql = sql.replace('\ufeff', '')
        sql_list = sql.split(';')
        for ele in range(len(sql_list)):
            sql_list[ele] = sql_list[ele].strip()
            if len(sql_list[ele]) == 0:
                del(sql_list[ele])
        with self.con.connect() as connection:
            for ele in range(len(sql_list) - 1):
                connection.execute(text(sql_list[ele]))
            df = pd.read_sql_query(sql=sql_list[-1], con=connection)
        return df


    def run(self, sql):
        con_pymysql = self.con.raw_connection()
        with con_pymysql.cursor() as cursor:
            for query in sql.strip().split(';'):
                if len(query) > 0:
                    cursor.execute(query + ';')


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
            if max_len_a > 16383:
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
        sql_column = f'`{column}` {sql_type}'
        return sql_column


    def create_table(self, df, name, replace=False, extras=False, **kwargs):
        column_list = []
        for column, dtype in df.dtypes.items():
            if column == 'RowLoadDateTime' and extras == True:
                pass
            else:
                column_list.append(self.__update_dtype(df, column, dtype))
        columns = ',\n'.join(column_list)
        sql_create = ''
        if replace == True:
            sql_create += f"DROP TABLE IF EXISTS {name};\n"
        sql_create += f"CREATE TABLE {name} ("
        if extras == True:
            sql_create += f"""
            ID{name} INT AUTO_INCREMENT NOT NULL,
            {columns},
            RowLoadDateTime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            RowModifiedDateTime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (ID{name})
            );"""
        else:
            sql_create += f"{columns});"
        self.run(sql_create)


    def to_sql(self, df, name, if_exists='fail', index=True, **kwargs):
        df_copy = df.copy()
        if index == True:
            df_copy.reset_index(inplace=True)

        if if_exists == 'replace':
            self.create_table(df_copy, name, replace=True, **kwargs)
        elif if_exists == 'fail':
            self.create_table(df_copy, name, replace=False, **kwargs)
        elif if_exists == 'append':
            try:
                self.create_table(df_copy, name, replace=False, **kwargs)
            except:
                pass
        else:
            raise(Exception('if_exists value is invalid, please choose between (fail, replace, append)'))

        df_copy = df_copy.replace({np.nan: None})
        df_copy.to_sql(name, if_exists='append', index=False, con=self.con, method='multi')
        
        return True