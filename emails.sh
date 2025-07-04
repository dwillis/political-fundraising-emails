python mbox_converter.py
rm emails.db
sqlite-utils insert emails.db emails emails_with_body.csv --csv
sqlite-utils enable-fts emails.db emails body
