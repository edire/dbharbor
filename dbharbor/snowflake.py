
import os
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from cryptography.hazmat.primitives.serialization import load_pem_private_key, Encoding, PrivateFormat, NoEncryption
import pandas as pd
import numpy as np


#%% Snowflake

class SQL:
    def __init__(self
                 , account = os.getenv('SNOWFLAKE_ACCOUNT')
                 , user = os.getenv('SNOWFLAKE_UID')
                 , private_key_path = os.getenv('SNOWFLAKE_CRED')
                 , password = os.getenv('SNOWFLAKE_PWD')
                 , warehouse = os.getenv('SNOWFLAKE_WAREHOUSE')
                 , database = os.getenv('SNOWFLAKE_DB')
                 , schema = os.getenv('SNOWFLAKE_SCHEMA')
                 , role = os.getenv('SNOWFLAKE_ROLE')
                 ):

        params = dict(account=account, user=user)
        if private_key_path:
            with open(private_key_path, 'rb') as f:
                private_key = load_pem_private_key(f.read(), password=None)
            params['private_key'] = private_key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
        else:
            params['password'] = password
        for k, v in dict(warehouse=warehouse, database=database, schema=schema, role=role).items():
            if v:
                params[k] = v
        self.con = snowflake.connector.connect(**params)


    def read(self, sql):
        cursor = self.con.cursor()
        cursor.execute(sql)
        return cursor.fetch_pandas_all()


    def run(self, sql):
        for query in sql.strip().split(';'):
            if len(query.strip()) > 0:
                self.con.cursor().execute(query)


    def __update_dtype(self, column, dtype):
        dict_dtype = {
            'object':'VARCHAR',
            'string':'VARCHAR',
            'int32':'INTEGER',
            'int64':'INTEGER',
            'float64':'FLOAT',
            'bool':'BOOLEAN',
            'boolean':'BOOLEAN',
            'datetime64':'TIMESTAMP_NTZ',
            'datetime64[ns]':'TIMESTAMP_NTZ',
            'datetime64[us]':'TIMESTAMP_NTZ',
            }
        dtype = str(dtype).lower()
        sql_type = dict_dtype[dtype]
        sql_column = f'"{column}" {sql_type}'
        return sql_column


    def create_table(self, df, name, replace=False, extras=False, **kwargs):
        column_list = []
        for column, dtype in df.dtypes.items():
            if column == 'RowLoadDateTime' and extras == True:
                pass
            else:
                column_list.append(self.__update_dtype(column, dtype))
        columns = ',\n'.join(column_list)
        sql_create = ''
        if replace == True:
            sql_create += f"DROP TABLE IF EXISTS {name};\n"
        sql_create += f"CREATE TABLE {name} ("
        if extras == True:
            sql_create += f"""
            {columns},
            RowLoadDateTime TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
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

        for col in df_copy.select_dtypes(include='object').columns:
            df_copy[col] = df_copy[col].apply(lambda x: str(x) if x is not None else None)

        parts = name.split('.')
        if len(parts) == 3:
            db, sch, tbl = parts
        elif len(parts) == 2:
            db, sch, tbl = None, parts[0], parts[1]
        else:
            db, sch, tbl = None, None, name
        write_pandas(self.con, df_copy, tbl, database=db, schema=sch)

        return True
