#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2008,2009  Felix Rabe  <public@felixrabe.net>


# This file is part of XML Merge.

# XML Merge is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at
# your option) any later version.

# XML Merge is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with XML Merge.  If not, see <http://www.gnu.org/licenses/>.


# Developed (i.e. tested) using Python 2.6.3 and lxml 2.2.2.

"""
The purpose of XML Merge is to preprocess any kind of XML file with great
flexibility.

XML Merge performs (among other things) recursive XML file inclusion and
XML element and attribute modification.

XML Merge is a Python module. It is normally run as a program from the
command line, but can equally well be used from within another Python
program or module.
"""

## IMPORTS AND CONSTANTS

import optparse
import sys
import lxml.etree as ET

# Namespace mapping (can be directly used for lxml nsmap arguments)
xmns = {"xm":   "urn:felixrabe:xmlns:xmlmerge:preprocess",
        "xmt":  "urn:felixrabe:xmlns:xmlmerge:inctrace"}


## OPTION PARSING CLASS

class OptionParser(optparse.OptionParser):

    def __init__(self, *a, **kw):
        optparse.OptionParser.__init__(self, *a, **kw)
        self.add_option("-i", "--input",
                        help="(REQUIRED) input XML file")
        self.add_option("-o", "--output",
                        help="output XML file")
        self.add_option("-r", "--reference",
                        help=("reference XML file to compare output " +
                              "against (for debugging / regression " +
                              "testing purposes)"))
        self.add_option("-D", "--no-diff", action="store_true",
                        help=("if output differs from reference, do " +
                              "not produce a difference HTML file"))
        self.add_option("-t", "--trace-includes", action="store_true",
                        help=("Add xmt: namespace tags to output to " +
                              "trace origins of elements to included " +
                              "files"))
        self.add_option("-v", "--verbose", action="store_const",
                        dest="verbose", const=3,
                        help=("show debugging messages (only useful " +
                              "when changing the program)"))
        self.add_option("-q", "--quiet", action="store_const",
                        dest="verbose", const=1,
                        help="only show error messages")
        self.set_defaults(verbose=2)


## MAIN FUNCTION

def main(argv):
    pass

if __name__ == "__main__":
    main(sys.argv)
