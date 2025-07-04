from emailnetwork.extract import *
from datetime import datetime
from email.utils import getaddresses
from mailbox import mbox
import html2text
import csv
import re

from mailbox import mboxMessage

from emailnetwork.utils import clean_subject, clean_body
from emailnetwork.emails import EmailAddress, EmailMeta, EmailBody
from emailnetwork.summary import DomainSummary
from emailnetwork.extract import extract_body, extract_meta

from emailnetwork.header import HeaderCounter

from urlextract import URLExtract
extractor = URLExtract()

reader = MBoxReader("PATH TO MBOX FILE")

textmaker = html2text.HTML2Text()
textmaker.ignore_links = True

urls = []

# Load domain to party mapping from file
domain_party_map = {}
with open("domain_party_mapping.csv", "r") as mapping_file:
    mapping_reader = csv.reader(mapping_file)
    next(mapping_reader)  # Skip header
    for row in mapping_reader:
        domain, party = row
        domain_party_map[domain] = party

with open("emails_with_body.csv", "w") as output_file:
    writer = csv.writer(output_file)
    writer.writerow(['name', 'email', 'subject', 'date', 'year', 'month', 'day', 'hour', 'minute', 'domain', 'body', 'party', 'disclaimer'])
    for email in reader.mbox:
        meta = extract_meta(email)
        try:
            body = extract_body(email)
            body = " ".join(body.body.split())
            body = textmaker.handle(body).replace('\u200c','').replace('  ',' ').replace('\n','')
            url_list = list(set(re.findall('https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+', body)))
            for url in url_list:
                if url not in urls:
                    urls.append(url)
            if "paid for by" in body.lower() or "paid for and" in body.lower():
                disclaimer = True
            else:
                disclaimer = False
            if 'actblue.com' in body:
                party = 'D'
            elif 'ngpvan.com' in body:
                party = 'D'
            elif 'winred.com' in body:
                party = 'R'
            elif 'anedot.com' in body:
                party = 'R'
            elif meta.origin_domain.strip() in domain_party_map:
                party = domain_party_map[meta.origin_domain]
            else:
                party = None

        except:
            body = None
            party = None
            disclaimer = None
        if meta.date:
            writer.writerow([meta.sender.name, meta.sender.email, meta.subject, str(meta.date), meta.date.year, meta.date.month, meta.date.day, meta.date.hour, meta.date.minute, meta.origin_domain, body, party, disclaimer])
        else:
            writer.writerow([meta.sender.name, meta.sender.email, meta.subject, None, None, None, None, None, None, meta.origin_domain, body, party, disclaimer])
