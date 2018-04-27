#!/usr/bin/env python3

import sys
import bibtexparser


def main():
    input_str = sys.stdin.read()
    try:
        bibtexparser.loads(input_str)
        print(input_str)
    except:
        pass


if __name__ == "__main__":
    main()
