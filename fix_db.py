import sqlite3; conn=sqlite3.connect('data/local_erp.db'); conn.execute('ALTER TABLE PRODUCT_DB ADD COLUMN brand_category VARCHAR DEFAULT ''FOOD'''); conn.commit(); conn.close()
