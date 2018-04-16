#!/bin/bash

# Download all bibtex files from NIPS Proceedings

curl "https://papers.nips.cc/" | grep -oP 'href="/book[^"]*"' | sed -e 's/href="//;s/"$//;s#^#https://papers.nips.cc/#' |\
while read -r BOOK_URL; do
    echo $BOOK_URL
	curl $BOOK_URL | grep -oP 'href="/paper/[^"]*"' | sed -e 's/href="//;s/"$//;s#^#https://papers.nips.cc#;s#$#/bibtex#' |\
	while read -r BIB_URL; do
        echo $BIB_URL
        sleep 1
        curl $BIB_URL >> nips.bib
        echo "" >> nips.bib
    done
done
