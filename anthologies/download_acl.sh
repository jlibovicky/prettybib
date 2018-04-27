#!/bin/bash

# Download all bibtex files from ACL anthology.

curl http://aclweb.org/anthology/ | sed 's#<[Aa] [Hh][Rr][Ee][Ff]="#\n<a href="#g' | grep -P 'href="[A-Z]/[A-Z][0-9]+' | sed -e 's/<a href="//;s/".*//;s#^#http://aclweb.org/anthology/#' |\
while read -r URL; do
	echo $URL
	sleep 1
	curl $URL | grep -oP 'href="[^"]*\.bib"' | sed -e "s#href=\"##;s/\"$//;s#^#${URL}#" | while read -r BIB_URL; do
		sleep 1
		curl $BIB_URL | uconv -t utf-8 | ./validate.py >> acl.bib
        echo >> acl.bib
        echo >> acl.bib
	done
done
