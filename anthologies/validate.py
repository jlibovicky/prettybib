#!/usr/bin/env python3

import sys
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bparser import BibTexParser
import pyparsing

BIB_PARSER = BibTexParser(
    ignore_nonstandard_types=False,
    homogenize_fields=True,
    common_strings=True)

def main():
    print("Reading from stdin ...", end="", file=sys.stderr)
    input_records = sys.stdin.read().split("\n\n")
    print("done.", file=sys.stderr)

    bib_parser = BibTexParser(
        ignore_nonstandard_types=True,
        homogenize_fields=True,
        common_strings=True)

    writer = BibTexWriter()
    writer.indent = '    '
    writer.order_by = ['author', 'year', 'title']
    writer.display_order = ['author', 'title', 'booktitle', 'journal']
    writer.align_values = True

    records = 0
    skipped = 0
    for record in input_records:
        if not record:
            continue
        try:
            parsed = bibtexparser.loads(record, bib_parser)
            records += 1
            if records % 1000 == 0:
                print("Processed {} records.".format(records), file=sys.stderr)
        except (pyparsing.ParseException, bibtexparser.bibdatabase.UndefinedString):
            skipped += 1

    for item in parsed.get_entry_list():
        if "abstract" in item:
            del item["abstract"]

    parsed.comments = []
    parsed.entries = [e for e in parsed.entries if e["ENTRYTYPE"] != "book"]
    parsed.entries = list(parsed.get_entry_dict().values())

    print(writer.write(parsed))
    print("Finished. {} records kept, {} skipped.".format(records, skipped),
          file=sys.stderr)


if __name__ == "__main__":
    main()
