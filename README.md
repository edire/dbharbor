# dbharbor

A Python library by Dire Analytics to standardize database connections across platforms for more efficient data engineering.

## Installation

```
pip install dbharbor
pip install git+https://github.com/edire/dbharbor.git
```

---

## Connections

All connection parameters default to environment variables. Instantiate once and reuse across `read`, `run`, and `to_sql` calls.

### Microsoft SQL Server

```python
from dbharbor.sql import SQL

con = SQL(
    server='localhost',        # env: SQL_SERVER (default: 'localhost')
    db='MyDatabase',           # env: SQL_DB
    uid='myuser',              # env: SQL_UID
    pwd='mypassword',          # env: SQL_PWD
    driver='ODBC Driver 17 for SQL Server'  # env: SQL_DRIVER
)
```

Attempts Windows trusted connection first; falls back to UID/PWD if that fails. Uses `fast_executemany=True` for high-throughput bulk inserts.

### MySQL

```python
from dbharbor.mysql import SQL

con = SQL(
    server='localhost',   # env: MYSQL_SERVER
    db='MyDatabase',      # env: MYSQL_DB
    uid='myuser',         # env: MYSQL_UID
    pwd='mypassword',     # env: MYSQL_PWD
    port=3306             # env: MYSQL_PORT (default: 3306)
)
```

Automatically URL-encodes passwords with special characters.

### Google BigQuery

```python
from dbharbor.bigquery import SQL

con = SQL(
    credentials_filepath='/path/to/service_account.json'  # env: BIGQUERY_CRED
)
```

Pass a service account JSON file path, or omit to use Application Default Credentials (e.g. when running on GCP). Reads use the BigQuery Storage API for fast parallel data transfer.

### Snowflake

```python
from dbharbor.snowflake import SQL

# Service account (RSA key pair — recommended for pipelines)
con = SQL(
    account='xy12345.us-east-1',   # env: SNOWFLAKE_ACCOUNT
    user='myuser',                  # env: SNOWFLAKE_UID
    private_key_path='/path/to/rsa_key.p8',  # env: SNOWFLAKE_CRED
    warehouse='MY_WH',              # env: SNOWFLAKE_WAREHOUSE (optional)
    database='MY_DB',               # env: SNOWFLAKE_DB       (optional)
    schema='MY_SCHEMA',             # env: SNOWFLAKE_SCHEMA   (optional)
    role='MY_ROLE'                  # env: SNOWFLAKE_ROLE     (optional)
)

# Password auth (dev/interactive use)
con = SQL(
    account='xy12345.us-east-1',
    user='myuser',
    password='mypassword'           # env: SNOWFLAKE_PWD
)
```

`warehouse`, `database`, `schema`, and `role` are all optional at connection time — omit them and use fully qualified `DB.SCHEMA.TABLE` names in your queries and `to_sql` calls instead.

### SQLite

```python
from dbharbor.sqlite import SQL

con = SQL(db='/path/to/database.db')
```

---

## Core Methods

All connection types share a consistent API.

### `read(sql)` — Query to DataFrame

```python
df = con.read("SELECT * FROM my_table WHERE active = 1")
```

Returns a pandas DataFrame. Multi-statement queries are supported in MySQL (all statements before the last are executed as setup; the final statement is returned as a DataFrame).

### `run(sql)` — Execute DDL / DML

```python
con.run("DROP TABLE IF EXISTS my_table")

con.run("""
    CREATE TABLE staging.load_log (id INT, loaded_at DATETIME);
    INSERT INTO staging.load_log VALUES (1, GETDATE());
""")
```

Splits on `;` and executes each statement. Use for DDL, stored procedures, INSERT/UPDATE/DELETE, and multi-statement scripts.

### `to_sql(df, name, ...)` — Write DataFrame to Table

```python
con.to_sql(df, 'my_table', if_exists='replace', index=False)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `df` | — | pandas DataFrame to write |
| `name` | — | Table name. Supports qualified names: `schema.table`, `db.schema.table` |
| `if_exists` | `'fail'` | `'fail'` raises if table exists; `'replace'` drops and recreates; `'append'` creates if missing then inserts |
| `index` | `True` | If `True`, resets index and writes it as a column |
| `extras` | `False` | If `True`, adds audit columns (see `create_table`) |

**Schema parameter** (SQL Server and MySQL only):
```python
con.to_sql(df, 'my_table', schema='dbo', if_exists='append', index=False)
```

**Bulk load internals by platform:**
- SQL Server: `pandas.DataFrame.to_sql` with `fast_executemany=True`
- MySQL: `pandas.DataFrame.to_sql` with `method='multi'` (batched multi-row INSERT)
- BigQuery: `load_table_from_dataframe` (Parquet via PyArrow)
- Snowflake: `write_pandas` (Parquet → temp stage → COPY INTO)

### `create_table(df, name, ...)` — DDL from DataFrame

Called automatically by `to_sql`, but available directly to pre-create tables.

```python
con.create_table(df, 'my_table', replace=True, extras=True)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `replace` | `False` | If `True`, issues `DROP TABLE IF EXISTS` first |
| `extras` | `False` | If `True`, adds audit columns (see below) |

**`extras=True` adds per platform:**

| Platform | Columns Added |
|----------|---------------|
| SQL Server | `ID{name} INT IDENTITY(1,1) PK`, `RowLoadDateTime DATETIME DEFAULT GETDATE()` |
| MySQL | `ID{name} INT AUTO_INCREMENT PK`, `RowLoadDateTime DATETIME DEFAULT CURRENT_TIMESTAMP`, `RowModifiedDateTime DATETIME ON UPDATE CURRENT_TIMESTAMP` |
| BigQuery | `RowLoadDateTime DATETIME NOT NULL` |
| Snowflake | `RowLoadDateTime TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP()` |

**Pandas → SQL type mapping:**

| pandas dtype | SQL Server | MySQL | BigQuery | Snowflake |
|---|---|---|---|---|
| object / string | `varchar(n)` / `varchar(max)` | `varchar(n)` / `TEXT` | `STRING` | `VARCHAR` |
| int64 | `tinyint` / `smallint` / `int` / `bigint` | same | `INT64` | `INTEGER` |
| float64 | `decimal(p, s)` | `decimal(p, s)` | `FLOAT64` | `FLOAT` |
| bool / boolean | `bit` | `bit` | `BOOL` | `BOOLEAN` |
| datetime64 | `datetime` | `datetime` | `DATETIME` | `TIMESTAMP_NTZ` |

SQL Server and MySQL inspect the actual column values to size `varchar` and `decimal` precisely. BigQuery and Snowflake use fixed types.

---

## SQL Server & MySQL — Additional Methods

### `where_not_exists(df, name, columns)` — Deduplicate Before Insert

Returns only the rows in `df` that are not already present in the table, matched on `columns`. Useful for incremental loads.

```python
# SQL Server
new_rows = con.where_not_exists(df, 'my_table', schema='dbo', columns=['order_id', 'customer_id'])

# MySQL / BigQuery
new_rows = con.where_not_exists(df, 'my_schema.my_table', columns=['order_id', 'customer_id'])

con.to_sql(new_rows, 'my_table', if_exists='append', index=False)
```

### `add_missing_columns(df, name)` — Schema Evolution

Adds any columns present in `df` but missing from the existing table. Safe to call before an append load when the source schema may have grown.

```python
# SQL Server
con.add_missing_columns(df, 'my_table', schema='dbo')

# MySQL
con.add_missing_columns(df, 'my_schema.my_table')
```

---

## Tools

Cleaning utilities for DataFrames before loading. Import directly from `dbharbor`.

```python
import dbharbor
```

### `clean(df, rowloadtime=False, drop_cols=True)` — Full Pipeline

Runs all cleaning steps in sequence: drops empty rows/columns, normalizes column names, scrubs values, and infers dtypes.

```python
df = dbharbor.clean(df)

# Keep a load timestamp column
df = dbharbor.clean(df, rowloadtime=True)

# Preserve columns that are entirely empty
df = dbharbor.clean(df, drop_cols=False)
```

### `clean_column_names(df)` — Normalize Column Names

Converts column names to safe identifiers: alphanumeric and underscores only, no leading/trailing underscores, no consecutive underscores.

```python
# "First Name", "sales $", "__total__" → "First_Name", "sales", "total"
df = dbharbor.clean_column_names(df)
```

### `clean_data(df)` — Scrub Cell Values

- Strings: strips leading/trailing whitespace; converts empty strings to `NaN`
- Numbers: converts `0` to `NaN`

```python
df = dbharbor.clean_data(df)
```

### `clean_dtypes(df)` — Infer Proper dtypes

Performs a CSV round-trip in memory to force pandas to re-infer column types, then calls `convert_dtypes()`. Converts columns that appear numeric but were loaded as `object` to their proper int/float/bool types.

```python
df = dbharbor.clean_dtypes(df)
```

### `clean_string(str_input)` — Normalize a Single String

Same rules as `clean_column_names` but for a single string value. Useful for sanitizing table names or tags.

```python
dbharbor.clean_string("Total Sales $$ 2024")  # → "Total_Sales_2024"
```

---

## End-to-End Example

```python
import pandas as pd
import dbharbor
from dbharbor.sql import SQL

# Connect (reads credentials from environment variables)
con = SQL()

# Read source data
df = con.read("SELECT * FROM raw.customer_export")

# Clean before loading
df = dbharbor.clean(df, rowloadtime=True)

# Load to destination — create if missing, skip rows already present
new_rows = con.where_not_exists(df, 'clean_customers', schema='dbo', columns=['customer_id'])
con.to_sql(new_rows, 'clean_customers', schema='dbo', if_exists='append', index=False)
```

```python
import dbharbor
from dbharbor.snowflake import SQL

# Connect with private key; use fully qualified table names
con = SQL(account='xy12345.us-east-1', user='etl_user')

df = con.read("SELECT * FROM MYDB.RAW.ORDERS")
df = dbharbor.clean(df)
con.to_sql(df, 'MYDB.ANALYTICS.ORDERS_CLEAN', if_exists='replace', index=False)
```

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

MIT License

## Updates

03/02/2026 - v1.0.0: Added Snowflake module (RSA key auth, `write_pandas` bulk load). Vectorized `__update_dtype` and `clean_data`. BigQuery reads now use Storage API. MySQL loads use multi-row INSERT batching. `clean_dtypes` replaced temp file with in-memory StringIO.<br>
09/30/2025 - Added pandas-gbq to install list for BigQuery.<br>
12/22/2024 - Added pool_pre_ping for long running connections.<br>
09/13/2024 - Updated NaN to nan for Numpy 2.0.<br>
09/09/2024 - Update SQL Varchar datatype to use max when greater than 8000 characters.<br>
08/12/2024 - Added datetime_us datatype and BigQuery storage library to setup for faster API.<br>
11/06/2023 - Fixed dtype missing lower function in sql and mysql and now use python tempfile module.<br>
11/03/2023 - Fixed index name bigquery to_sql issue.<br>
11/03/2023 - Added clean_dtypes function and updated create_table dtypes.<br>
10/20/2023 - Updated clean tool for empty column names, replaced empty strings with NaN.<br>
10/04/2023 - Updated BigQuery data type mapping.<br>
09/19/2023 - Added port option for MySQL.<br>
08/12/2023 - Update for applymap deprecation and upper env vars.<br>
07/07/2023 - Reverted MSSQL and MySQL Run logic in order to pick up proc errors.<br>
06/16/2023 - Updated SQL and MySQL modules for SQLAlchemy 2.0.<br>
04/23/2023 - Updated BigQuery to remove string length restrictions. Added pyarrow and db-dtypes to required libraries.<br>
03/14/2023 - Updated data type amounts for float columns in sql and mysql.<br>
02/22/2023 - Fixed run logic in SQL and MySQL to use autocommit appropriately.<br>
02/20/2023 - Updated BigQuery module to allow connections from cloud resources.<br>
02/17/2023 - Updated MySQL for reading multiple statement queries into DataFrame.<br>
02/10/2023 - Added full functionality to BigQuery module.<br>
01/08/2023 - Fixed duplicate RowLoadDateTime issue in create_table function for sql and mysql.<br>
01/06/2023 - Added BigQuery module with read function.<br>
12/14/2022 - Added MySQL module.
