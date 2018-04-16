#!/bin/bash

# Proceedings of Machine Learning Research

curl http://proceedings.mlr.press | grep -oP 'href="v[0-9]+"' | sed -e 's/href="//;s/"$//;s#^#http://proceedings.mlr.press/#;s#$#/bibliography.bib#' |\
while read -r BIB_URL; do
	echo $BIB_URL
	curl $BIB_URL >> pmlr.bib
done
