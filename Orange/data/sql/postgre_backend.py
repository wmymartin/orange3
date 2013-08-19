import math
import psycopg2
import numpy as np


class PostgreBackend(object):
    def connect(self,
                database,
                table,
                hostname=None,
                username=None,
                password=None):
        self.connection = psycopg2.connect(
            host=hostname,
            user=username,
            password=password,
            database=database,
        )
        self.table_name = table
        self.table_info = self._get_table_info()

    def _get_table_info(self):
        cur = self.connection.cursor()
        return TableInfo(
            fields=self._get_field_list(cur),
        )

    def _get_field_list(self, cur):
        cur.execute("""
            SELECT column_name, data_type
              FROM INFORMATION_SCHEMA.COLUMNS
             WHERE table_name = %s;""", (self.table_name,))
        self.connection.commit()
        return tuple(
            (fname, ftype, self._get_field_values(fname, ftype, cur))
            for fname, ftype in cur.fetchall()
        )

    def _get_field_values(self, field_name, field_type, cur):
        if 'double' in field_type:
            return ()
        elif 'char' in field_type:
            return self._get_distinct_values(field_name, cur)

    def _get_distinct_values(self, field_name, cur):
        cur.execute("""SELECT DISTINCT "%s" FROM "%s" ORDER BY %s LIMIT 21""" %
                    (field_name, self.table_name, field_name))
        self.connection.commit()
        values = cur.fetchall()

        if len(values) > 20:
            return ()
        else:
            return tuple(x[0] for x in values)

    def _get_nrows(self, cur):
        cur.execute("""SELECT COUNT(*) FROM "%s" """ % self.table_name)
        self.connection.commit()
        return cur.fetchone()[0]

    def query(self, attributes=None, filters=(), rows=None):
        if attributes is not None:
            fields = []
            for attr in attributes:
                assert hasattr(attr, 'to_sql'), \
                    "Cannot use ordinary attributes with sql backend"
                field_str = '(%s) AS "%s"' % (attr.to_sql(), attr.name)
                fields.append(field_str)
            if not fields:
                raise ValueError("No fields selected.")
        else:
            fields = ["*"]

        sql = """SELECT %s FROM "%s" """ % (', '.join(fields), self.table_name)
        filters = [f for f in filters if f]
        if filters:
            sql += " WHERE %s " % " AND ".join(filters)
        if rows is not None:
            if isinstance(rows, slice):
                start = rows.start or 0
                stop = rows.stop or self.table_info.nrows
                size = stop - start
            else:
                rows = list(rows)
                start, stop = min(rows), max(rows)
                size = stop - start + 1
            sql += " OFFSET %d LIMIT %d" % (start, size)
        cur = self.connection.cursor()
        cur.execute(sql)
        self.connection.commit()
        while True:
            row = cur.fetchone()
            if row is None:
                break
            yield row

    def stats(self, columns, where=""):
        stats = []
        for column in columns:
            if column.var_type == column.VarTypes.Continuous:
                column = column.to_sql()
                stats.append(", ".join((
                    "MIN(%s)" % column,
                    "MAX(%s)" % column,
                    "AVG(%s)" % column,
                    "STDDEV(%s)" % column,
                    #"0",
                    "SUM(CASE TRUE"
                    "       WHEN %s IS NULL THEN 1"
                    "       ELSE 0"
                    "END)" % column,
                    #"0",
                    "SUM(CASE TRUE"
                    "       WHEN %s IS NULL THEN 0"
                    "       ELSE 1"
                    "END)" % column,
                )))
            else:
                column = column.to_sql()
                stats.append(", ".join((
                    "NULL",
                    "NULL",
                    "NULL",
                    "NULL",
                    "SUM(CASE TRUE"
                    "       WHEN %s IS NULL THEN 1"
                    "       ELSE 0"
                    "END)" % column,
                    "SUM(CASE TRUE"
                    "       WHEN %s IS NULL THEN 0"
                    "       ELSE 1"
                    "END)" % column,
                )))

        stats_sql = ", ".join(stats)
        cur = self.connection.cursor()
        cur.execute("""SELECT %s FROM "%s" %s""" % (stats_sql,
                                                    self.table_name,
                                                    where))
        self.connection.commit()
        results = cur.fetchone()
        stats = []
        for i in range(len(columns)):
            stats.append(results[6*i:6*(i+1)])
        return stats

    def distributions(self, columns, where):
        dists = []
        cur = self.connection.cursor()
        for col in columns:
            cur.execute("""
                SELECT %(col)s, COUNT(%(col)s)
                  FROM "%(table)s"
                    %(where)s
              GROUP BY %(col)s
              ORDER BY %(col)s""" %
                        dict(col=col.to_sql(),
                             table=self.table_name,
                             where=where))
            dist = np.array(cur.fetchall())
            if col.var_type == col.VarTypes.Continuous:
                dists.append((dist.T, []))
            else:
                dists.append((dist[:, 1].T, []))
        self.connection.commit()
        return dists


class TableInfo(object):
    def __init__(self, fields):
        self.fields = fields
        self.field_names = tuple(name for name, _, _ in fields)
        self.values = {
            name: values
            for name, _, values in fields
        }