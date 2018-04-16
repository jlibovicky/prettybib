#!/bin/bash

# Download all bibtex files from Journal of Machine Learning Research

curl http://jmlr.org/papers/ | grep -oP 'href="((v[0-9]+)|(topic)|(special))[^"]+"' | sed -e 's#href="#http://jmlr.org/papers/#;s#"$#/#' |\
while read -r ISSUE_URL; do
	echo $ISSUE_URL
	curl $ISSUE_URL | grep -oP 'href="[^"]+\.bib"' | sed -e 's#href="#http://www.jmlr.org/#;s#"$##' |\
	while read -r BIB_URL; do
		curl $BIB_URL >> jmlr.bib
		echo >> jmlr.bib
	done
done
