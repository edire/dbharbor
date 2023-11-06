# setup.py placed at root directory
from setuptools import setup
setup(
    name='dbharbor',
    packages=['dbharbor'],
    version='0.1.4',
    license='MIT',
    author='Eric Di Re',
    author_email='eric.dire@direanalytics.com',
    description='Standardized DB Connections.',
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url='https://github.com/edire/dbharbor.git',
    python_requires='>=3.11',
    package_data={'dbharbor': ['MiscFiles/Microsoft.AnalysisServices.Tabular.DLL']},
    install_requires=['pyodbc', 'sqlalchemy>=2.0', 'numpy', 'pandas>=2.1.1', 'pymysql', 'openpyxl', 'pythonnet', 'google-cloud-bigquery', 'pyarrow', 'db-dtypes']
)