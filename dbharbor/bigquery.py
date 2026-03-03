

import os
import numpy as np
import pandas as pd
from google.cloud import bigquery


#%% BigQuery

class SQL:
    def __init__(self
                 , credentials_filepath = os.getenv('BIGQUERY_CRED')
                 ):

        if credentials_filepath != None:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_filepath

        self.client = bigquery.Client()


    def read(self, sql):
        return self.client.query(sql).to_dataframe(create_bqstorage_client=True)


    def run(self, sql):
        for query in sql.strip().split(';'):
            if len(query) > 0:
                query_job = self.client.query(query)
                query_job.result()


    def __update_dtype(self, column, dtype):
        dict_dtype = {
            'object':           'STRING',
            'string':           'STRING',
            'int32':            'INT64',
            'int64':            'INT64',
            'Int64':            'INT64',    # pandas nullable integer
            'float32':          'FLOAT64',
            'float64':          'FLOAT64',
            'Float64':          'FLOAT64',  # pandas nullable float
            'bool':             'BOOL',
            'boolean':          'BOOL',     # pandas nullable boolean
            'datetime64':       'DATETIME',
            'datetime64[ns]':   'DATETIME',
            'datetime64[us]':   'DATETIME',
        }
        sql_type = dict_dtype.get(str(dtype), 'STRING')
        return f'`{column}` {sql_type}'


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
            RowLoadDateTime DATETIME NOT NULL
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

        obj_cols = df_copy.select_dtypes(include='object').columns.tolist()
        df_copy = df_copy.replace({np.nan: None})

        for col in obj_cols:
            df_copy[col] = df_copy[col].apply(lambda x: str(x) if x is not None else None)

        job = self.client.load_table_from_dataframe(df_copy, name)
        job.result()

        return True