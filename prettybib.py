#!/usr/bin/env python

"""BibTex checker and formater.

This is a scripts that formats bibtex in a uniform way, orders it by the
authors surnames and checkes the records have all they need.
"""

import argparse
import datetime
from difflib import SequenceMatcher
import re
import string
import urllib.request
import sys

import bs4
from termcolor import colored
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
import isbnlib
from SPARQLWrapper import SPARQLWrapper, JSON
import pycountry

# pylint: disable=fixme

CITATION_DATABASE = {}

def get_bibparser():
    return bibtexparser.bparser.BibTexParser(
        ignore_nonstandard_types=False,
        homogenize_fields=True,
        common_strings=True)


def normalize_title(title):
    return title.lower().translate(str.maketrans(
        '', '', string.whitespace + '}{'))


def load_anthologies(anthologies):
    for anthology in anthologies:
        with open(anthology, "r", encoding="utf-8") as f_anth:
            sys.stderr.write("Loading {} ... ".format(anthology))
            sys.stderr.flush()

            bib_database = bibtexparser.load(f_anth, get_bibparser())
            for entry in bib_database.entries:
                if 'title' in entry:
                    norm_title = normalize_title(entry['title'])
                    CITATION_DATABASE[norm_title] = entry
            print("done, {} items".format(
                len(bib_database.entries)), file=sys.stderr)


def log_message(entry, message, color='green'):
    """Print colored log message."""
    sys.stderr.write(colored("{} ({}): {}\n".format(
        entry['ID'], entry['ENTRYTYPE'], message), color=color))


def err_message(entry, message):
    """Print red error message."""
    log_message(entry, message, color='red')


def similarity(str_1, str_2):
    matcher = SequenceMatcher(None, str_1, str_2)
    return matcher.ratio()


NUM_REGEX = re.compile(r"[0-9]+(st|nd|rd|th)?")
ORDINALS = re.compile("(" + "|".join([
    "First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh",
    "Eighth", "Ninth", "Tenth", "Eleventh", "Twelfth", "Thirteenth",
    "Fourteenth", "Fifteenth", "Sixteenth", "Seventeenth"]) + ")")
PAPERS_VOLUME = re.compile("(Long|Short|Research|Shared Task) Papers")


def norm_booktitle(title):
    title = NUM_REGEX.sub("XX", title)
    title = ORDINALS.sub("XX", title)
    title = PAPERS_VOLUME.sub("YY Papers", title)

    return title


def check_year(entry, _):
    """Check the sanitiy of a year."""
    try:
        year = int(entry['year'])

        current_year = datetime.datetime.now().year

        if year < 0:
            err_message(entry, "year '{}' is negative.".format(year))
        if year > current_year:
            err_message(entry, "year '{}' is in the future.".format(year))
        if year < 1800:
            err_message(entry, "year '{}' is before 1800".format(year))
    except ValueError:
        if entry['year'] != 'TODO':
            err_message(entry,
                        "year '{}' is not an integer".format(entry['year']))


MONTHS = [
    "January", "Feburay", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December"]


def check_month(entry, _):
    month = entry["month"]
    if month not in MONTHS:
        err_message(entry, "'{}' is not valid month name.".format(month))
        return False
    return True


PAGE_REGEX = re.compile(r"^([1-9][0-9]*)[\W_]+([1-9][0-9]*)$")


def check_pages(entry, _):
    """Check range and fix punctuation."""
    pages = entry['pages']
    pages_match = PAGE_REGEX.match(pages)
    if pages_match:
        start, end = pages_match.groups()
        if int(end) < int(start):
            err_message(entry,
                        "the end page ({}) is before the start page ({})".
                        format(end, start))
    elif pages != 'TODO':
        err_message(entry, "pages field looks strange: '{}'".format(pages))


def check_isbn(entry, try_fix):
    """Check and format ISBN.

    More information about ISBN:
    https://en.wikipedia.org/wiki/International_Standard_Book_Number
    """
    isbn_string = entry['isbn']
    # is_valid_isbn = False
    if isbnlib.is_isbn10(isbn_string):
        # is_valid_isbn = True
        try:
            if int(entry['year']) >= 2007:
                err_message(entry,
                            ("ISBN10 ({}) were issued only before 2007," +
                             " year is actually {}").
                            format(isbn_string, entry['year']))
                return False
            return True
        # pylint: disable=bare-except
        except:
            return False
    elif isbnlib.is_isbn13(isbn_string):
        # is_valid_isbn = True
        try:
            if int(entry['year']) < 2007 and isbn_string.starstwith('978'):
                err_message(entry,
                            ("ISBN13 ({}) were issued only after 2007," +
                             " year is actually {}").
                            format(isbn_string, entry['year']))
            return True
        # pylint: disable=bare-except
        except:
            return False
    else:
        if isbn_string != 'TODO':
            err_message(entry, "Invalid ISBN {}".format(isbn_string))
        # TODO try to look up isbn using isbnlib.goom()
        # intitle:Understanding+inauthor:McLuhan&tbs=,
        #        cdr:1,cd_min:Jan+1_2+1964,cd_max:Dec+31_2+1974&num=10
        return False

    if try_fix:
        _fix_based_on_isbn(isbn_string, entry)

    entry['isbn'] = isbnlib.mask(isbn_string)
    return True


def _fix_based_on_isbn(isbn_string, entry):
    """Try to find publlisher and year based ISBN."""
    publisher = None
    year = None
    if 'publisher' in entry and entry['publisher'] != 'TODO':
        publisher = entry['publisher']
    if 'year' in entry and entry['year'] != 'TODO':
        year = entry['year']

    try:
        if not publisher or not year:
            meta_data = isbnlib.meta(isbn_string)

            if 'Year' in meta_data and entry['year'] == 'TODO':
                entry['year'] = meta_data['Year']
                log_message(entry, "year found based on ISBN: {}".
                            format(meta_data['Year']))
            if 'Publisher' in meta_data and entry['publisher'] == 'TODO':
                entry['publisher'] = meta_data['Publisher']
                log_message(entry, "publisher found based on ISBN: '{}'".
                            format(meta_data['Publisher']))
    # pylint: disable=bare-except
    except:
        pass
    # pylint: enable=bare-except


ISSN_REGEX = re.compile(r"^\d{4}-?\d{3}[\dxX]$")


def check_issn(entry, try_fix):
    """Check ISSN number."""
    issn_str = entry['issn']
    if ISSN_REGEX.match(issn_str):
        # TODO get journal infomation and check
        return True

    if issn_str != 'TODO':
        err_message(entry, "Ivalid ISSN format ({}).")

    if 'journal' in entry and try_fix:
        journal = entry['journal']

        if journal in CACHED_JOURNALS:
            entry['issn'] = CACHED_JOURNALS[journal]
            return True

        sparql = SPARQLWrapper("http://dbpedia.org/sparql")
        sparql.setReturnFormat(JSON)
        sparql.setQuery("""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX type: <http://dbpedia.org/ontology/>
            SELECT ?journal ?issn
            WHERE {{
                     ?journal a type:AcademicJournal ;
                     rdfs:label ?journal_name ;
                     dbo:issn ?issn .
                     FILTER(str(?journal_name)="{}")
        }}""".format(journal))
        try:
            results = sparql.query().convert()
        except:
            return False

        if results['results']['bindings']:
            issn = results['results']['bindings'][0]['issn']['value']
            entry['issn'] = issn
            log_message(entry, "ISSN for '{}' found: {}".
                        format(journal, issn))
            return True

        err_message(entry, "ISSN for '{}' not found.".format(journal))
        return False
    return False


def check_booktitle(entry, try_fix):
    if entry['booktitle'].endswith("Conference on"):
        err_message(entry,
            "Book title should not end with 'Conference on', rephrase")
        return False
    return True


US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "D.C."]


def check_address(entry, _):
    address = entry["address"]
    tokens = address.split(", ")

    if len(tokens) != 2 and (len(tokens) != 3 or tokens[-1] != "USA"):
        err_message(
            entry,
            "Adrress should be comma-separated city "
            "and country, was '{}'".format(address))
        return False

    country = tokens[-1]
    if country == "USA":
        if len(tokens) != 3:
            err_message(entry, "USA cities must have state.")
            return False

        if tokens[1] not in US_STATES:
            err_message(
                entry,
                "'{}' is not existing U.S. state abreviation.".format(
                    tokens[1]))
            return False

        return True

    if country == "Taiwan" or country == "Czech Republic":
        return True

    if country == "Czechia":
        err_message(entry, "Use 'Czech Republic' instead of 'Czechia'.")
        return False

    country_lookup = None
    try:
        country_lookup = pycountry.countries.lookup(country)
    except LookupError:
        pass

    if country_lookup is None:
        err_message(entry, "Unknown country: '{}'".format(country))
        return False

    if country != country_lookup.name:
        err_message(entry, "Use '{}' instead of '{}'.".format(
            country_lookup.name, country))

    return True


def check_author(entry, _):
    authors = entry["author"].split(" and ")
    problem = False
    for author in authors:
        names = author.split()
        if re.match(r"^[A-Z]\.?$", names[0]):
            err_message(
                entry,
                "'{}' seem to have only initial, not full name.".format(
                    author))
            problem = True

        if any(n.endswith(".") for n in names):
            err_message(
                entry,
                "Initials should not contain dot: '{}'".format(author))
            problem = True
    return not problem


NON_APLHNUM = re.compile(r"[^A-Za-z0-9]+")


def search_crossref_for_doi(title):
    keywords = title.lower().replace(" ", "+")
    title_signature = NON_APLHNUM.sub("", title.lower())

    searchurl = 'http://search.crossref.org/?q='
    requrl = searchurl+keywords
    s = bs4.BeautifulSoup(urllib.request.urlopen(requrl).read(), 'lxml')
    item_list = s.findAll('td', {'class':'item-data'})

    titles = [i.find('p', {'class':'lead'}).text.strip() for i in item_list]
    doiurls = [
        i.find('div', {'class':'item-links'}).find('a')['href']
        for i in item_list]

    assert len(titles) == len(doiurls)

    found_dois = []
    for found_title, doi_url in zip(titles, doiurls):
        if 'itationsBox' in doi_url:
            continue
        found_title_signature = NON_APLHNUM.sub("", found_title.lower())
        if title_signature == found_title_signature:
            found_dois.append(doi_url[16:])
    return found_dois


DOI_PREFIX = re.compile(r"^[0-9]{2}\.[0-9]{4,5}$")


def check_doi(entry, try_fix):
    doi_ok = True
    doi = entry['doi']

    if doi == "TODO":
        doi_ok = False
    elif "/" not in doi:
        doi_ok = False
        err_message(
            entry,
            "doi should contain '/', was '{}'".format(doi))
    else:
        doi_parts = doi.split('/')

        doi_prefix = doi_parts[0]
        if DOI_PREFIX.match(doi_prefix) is None:
            err_message(
                entry,
                "doi prefix must be in format '10.XXXX', was '{}'".format(
                    doi_prefix))
            doi_ok = False

    if doi_ok:
        # TODO: try retrieve bib by doi
        return True

    if try_fix and not doi_ok:
        lookup = search_crossref_for_doi(entry['title'])

        if not lookup:
            return False

        if len(lookup) > 1:
            err_message(entry, "Found multiple dois: {}".format(", ".join(lookup)))
            return False

        entry['doi'] = lookup[0]
        log_message(entry, 'doi found on crossref.org')
        return True
    return False


FIELD_CHECKS = {
    'year': check_year,
    'pages': check_pages,
    'isbn': check_isbn,
    'issn': check_issn,
    'booktitle': check_booktitle,
    'month': check_month,
    'address': check_address,
    'author': check_author,
    'doi': check_doi,
}


def check_field(entry, field, try_fix, try_find=False):
    """Check if a field in in the entry, if not add a TODO."""
    if field not in entry or entry[field] == 'TODO':
        entry[field] = 'TODO'
        if try_fix and try_find and 'title' in entry:
            norm_title = normalize_title(entry['title'])
            if norm_title in CITATION_DATABASE:
                database_entry = CITATION_DATABASE[norm_title]
                if field in database_entry:
                    value = database_entry[field]
                    entry[field] = value
                    log_message(
                        entry,
                        "Field {} copied from database as: '{}'.".format(
                            field, value))
        err_message(entry, "Missing field '{}'".format(field))
        if field in FIELD_CHECKS:
            return FIELD_CHECKS[field](entry, try_fix)
        return False
    if field in FIELD_CHECKS:
        return FIELD_CHECKS[field](entry, try_fix)
    return True


def check_article(entry, try_fix):
    """Check and fix article entries."""
    if 'journal' not in entry:
        err_message(entry, "Journal title is missing.")
        # TODO try to recover from ISSN or paper name
    else:
        journal = entry['journal']
        if journal == 'CoRR' or journal.startswith('arXiv'):
            if try_fix and 'title' in entry:
                norm_title = normalize_title(entry['title'])
                if norm_title in CITATION_DATABASE:
                    log_message(
                        entry,
                        "Preprint found as a proper publication, replacing.")
                    entry.clear()
                    entry.update(CITATION_DATABASE[norm_title])

            if try_fix:
                entry['journal'] = 'CoRR'
                entry['issn'] = '2331-8422'

                if 'volume' in entry and entry['volume'].startswith('abs/'):
                    entry['url'] = "https://arxiv.org/{}".format(
                        entry['volume'])

            check_field(entry, 'url', try_fix)
            check_field(entry, 'volume', try_fix)
            # TODO check whether link and volume agree
        else:
            check_field(entry, 'doi', try_fix, try_find=True)
            check_field(entry, 'issn', try_fix)
            if 'volume' not in entry:
                check_field(entry, 'number', try_fix)
            check_field(entry, 'pages', try_fix)
            check_field(entry, 'publisher', try_fix)
            check_field(entry, 'address', try_fix)
            check_field(entry, 'url', try_fix)


def check_book(entry, try_fix):
    """Check and fix book entries."""
    check_field(entry, 'isbn', try_fix)
    check_field(entry, 'publisher', try_fix)
    check_field(entry, 'year', try_fix)
    check_field(entry, 'url', try_fix)


def check_inproceedings(entry, try_fix):
    """Check and fix inproceedings entries."""
    check_field(entry, 'doi', try_fix, try_find=True)
    check_field(entry, 'booktitle', try_fix, try_find=True)
    check_field(entry, 'month', try_fix, try_find=True)
    check_field(entry, 'year', try_fix, try_find=True)
    check_field(entry, 'address', try_fix, try_find=True)
    check_field(entry, 'pages', try_fix, try_find=True)
    check_field(entry, 'publisher', try_fix, try_find=True)
    check_field(entry, 'url', try_fix)


def check_techreport(entry, try_fix):
    """Check and fix inproceedings entries."""
    check_field(entry, 'month', try_fix, try_find=True)
    check_field(entry, 'year', try_fix, try_find=True)
    check_field(entry, 'address', try_fix, try_find=True)
    check_field(entry, 'institution', try_fix, try_find=True)
    check_field(entry, 'url', try_fix)


ENTRY_CHECKS = {
    'article': check_article,
    'inproceedings': check_inproceedings,
    'book': check_book,
    'techreport': check_techreport
}


CACHED_JOURNALS = {}


def cache_journal_issn(database):
    for entry in database.entries:
        if entry['ENTRYTYPE'] == "article":
            name = entry["journal"]
            if "issn" in entry:
                if name not in CACHED_JOURNALS:
                    CACHED_JOURNALS[name] = entry["issn"]
                elif entry["issn"] != CACHED_JOURNALS[name]:
                    print(
                        "Journal '{}' has more differens ISSNs.".format(name),
                        file=sys.stderr)


def cache_field(entry, field, cache_dict):
    """Cache a field for later similarity search."""
    if field in entry:
        values = (
            entry[field].split(' and ') if field == 'author'
            else [entry[field]])

        if field == 'booktitle':
            values = [norm_booktitle(v) for v in values]

        for value in values:
            if value not in cache_dict:
                cache_dict[value] = []
            cache_dict[value].append(entry['ID'])


def normalize_authors(author_field):
    orig_authors = author_field.split(" and ")
    new_authors = []
    for author in orig_authors:
        if "," not in author:
            names = re.split(r"\s+", author)
            if len(names) == 1:
                new_authors.append(author)
            else:
                new_authors.append("{}, {}".format(
                    names[-1], " ".join(names[:-1])))
        else:
            new_authors.append(author)
    return " and ".join(new_authors)


def check_database(database, try_fix):
    """Check the database entries.

    Goes through the bib database and checks if everyting is
    as it shoudl be.

    Returns:
        Dictionaries of chached author, journal and proceedings names, so they
        can be later checked for near duplicites.
    """

    authors, journals, booktitles = {}, {}, {}

    titles = {}

    for entry in database.entries:
        # normalize the vaues
        for key, value in entry.items():
            entry[key] = re.sub(r"\s+", " ", value)

        if 'author' in entry:
            entry['author'] = normalize_authors(entry['author'])

        cache_field(entry, 'author', authors)
        cache_field(entry, 'journal', journals)
        cache_field(entry, 'booktitle', booktitles)

        check_field(entry, 'author', try_fix)

        if 'title' in entry:
            norm_title = entry['title'].lower().translate(
                str.maketrans('', '', string.whitespace + '}{'))
            if norm_title in titles:
                msg = ("Reference with this title is already "
                       "in the database as {}.").format(
                           ", ".join(titles[norm_title]))
                err_message(entry, msg)
                titles[norm_title].append(entry['ID'])
            else:
                titles[norm_title] = [entry['ID']]
        check_field(entry, 'title', try_fix)

        entry_type = entry['ENTRYTYPE']
        if entry_type in ENTRY_CHECKS:
            ENTRY_CHECKS[entry_type](entry, try_fix)

    return authors, journals, booktitles


def look_for_misspellings(values, name, threshold=0.8):
    """Check for values with minor differences in spelling."""
    collision_groups = {}
    for value1 in values:
        for value2 in values:
            if value1 == value2:
                continue

            if threshold < similarity(value1, value2):
                if (value1 not in collision_groups
                        and value2 in collision_groups):
                    collision_groups[value1] = collision_groups[value2]
                    collision_groups[value2].add(value1)
                elif (value2 not in collision_groups
                      and value1 in collision_groups):
                    collision_groups[value2] = collision_groups[value1]
                    collision_groups[value1].add(value2)
                elif (value1 in collision_groups
                      and value2 in collision_groups):
                    collision_groups[value1] = collision_groups[value1].union(
                        collision_groups[value2])
                    collision_groups[value2] = collision_groups[value1]
                else:
                    new_group = set([value1, value2])
                    collision_groups[value1] = new_group
                    collision_groups[value2] = new_group

    used_values = set()
    for group in collision_groups.values():
        if used_values.intersection(group):
            continue
        used_values.update(group)
        formatted_values = [
            "'{}' ({})".format(a, ", ".join(values[a]))
            for a in group]
        print(colored("{} might be the same.".format(name), color='yellow'),
              file=sys.stderr)
        for val in formatted_values:
            print(colored(" * {}".format(val), color='yellow'),
                  file=sys.stderr)


def main():
    """Main function of the script.

    Loads the bib file, does the chcecking on it and prints out
    sorted and formated database.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input", type=argparse.FileType('r'), default=sys.stdin,
        help="Input file, default is stdin.")
    parser.add_argument(
        "--output", type=argparse.FileType('w'), default=sys.stdout,
        help="Optional output file.")
    parser.add_argument(
        "--try-fix", default=False, action="store_true",
        help="Flag to search information to fix the dtabase.")
    parser.add_argument(
        "--anthologies", type=str, nargs='+',
        help="List of BibTeX files with know papers.")
    args = parser.parse_args()

    if args.anthologies is not None:
        load_anthologies(args.anthologies)
    bib_database = bibtexparser.load(args.input, get_bibparser())
    cache_journal_issn(bib_database)
    authors, journals, booktitles = check_database(bib_database, args.try_fix)

    look_for_misspellings(authors, 'Authors')
    look_for_misspellings(journals, 'Journals')
    look_for_misspellings(booktitles, 'Booktitles (proceedings)', threshold=0.9)

    writer = BibTexWriter()
    writer.indent = '    '
    writer.order_by = ['author', 'year', 'title']
    writer.display_order = ['author', 'title', 'booktitle', 'journal']
    writer.align_values = True
    args.output.write(writer.write(bib_database))


if __name__ == "__main__":
    main()
