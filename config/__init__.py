"""Configuration package for Admón Almacén SSIT 2.0."""
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass
