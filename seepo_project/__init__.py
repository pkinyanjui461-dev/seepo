"""Project package initialization."""

try:
	import pymysql

	pymysql.install_as_MySQLdb()
except Exception:
	# Allow non-MySQL environments to run without PyMySQL.
	pass
