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


# Developed (i.e. tested) using Python 2.6.4 and lxml 2.2.2.

"""
The purpose of XML Merge is to preprocess any kind of XML file with great
flexibility.

XML Merge performs (among other things) recursive XML file inclusion and
XML element and attribute modification.

XML Merge is a Python module. It is normally invoked as a program from the
command line, but can equally well be used from within another Python
program or module.
"""

## IMPORTS AND CONSTANTS

import copy
import itertools
import optparse
import os
import re
import sys

import lxml.etree as ET

# Namespace mapping (can be directly used for lxml nsmap arguments):
xmns = {"xm":   "urn:felixrabe:xmlns:xmlmerge:preprocess",
        "xmt":  "urn:felixrabe:xmlns:xmlmerge:inctrace"}


## COMMAND LINE OPTION PARSING

class OptionParser(optparse.OptionParser):

    def __init__(self, *a, **kw):
        optparse.OptionParser.__init__(self, *a, **kw)
        self.add_option("-i", "--input",
                        help=("(REQUIRED) input XML file"))
        self.add_option("-o", "--output",
                        help=("output XML file (.out.xml if not given)"))
        self.add_option("-s", "--xml-schema",
                        help=("XML Schema (.xsd) to validate output " +
                              "against"))
        self.add_option("-r", "--reference",
                        help=("reference XML file to compare output " +
                              "against"))
        self.add_option("-d", "--html-diff", action="store_true",
                        help=("only with -r; if output and reference " +
                              "differ, produce a HTML file showing the " +
                              "differences"))
        self.add_option("-t", "--trace-includes", action="store_true",
                        help=("add tracing information to included " +
                              "XML fragments"))
        self.add_option("-v", "--verbose", action="store_const",
                        dest="verbose", const=3,
                        help=("show debugging messages"))
        self.add_option("-q", "--quiet", action="store_const",
                        dest="verbose", const=1,
                        help=("only show error messages"))
        self.set_defaults(verbose=2)

        # Explanation: levels of verbosity
        # --quiet   -> self.verbose == 1  # only show error messages
        #           -> self.verbose == 2  # no verbosity option given
        # --verbose -> self.verbose == 3  # show debugging messages


def parse_command_line(argv):
    """
    parse_command_line(argv) -> optparse.Values
    
    Parse argv and return an optparse.Values object containing the options.

    This function performs all the necessary checks and conversions to make
    sure all necessary options are given, and that all options are
    available in a normalized format.

    It also tries to create the containing directory for the output file if
    it does not exist already.
    """
    # Parse options using OptionParser:
    option_parser = OptionParser()
    options, args = option_parser.parse_args(argv[1:])

    # Make sure only options, and no other arguments, are passed on the
    # command line:
    try:
        assert args == []
        assert options.input is not None
    except:
        option_parser.error("Error: invalid argument list")

    # If the output option has been omitted, build the output filename from
    # the input filename, resulting in the file extension ".out.xml":
    if options.output is None:
        if options.input.lower().endswith(".xml"):
            options.output = options.input[:-4] + ".out.xml"
        else:
            options.output = options.input      + ".out.xml"

    # Convert all filename options to normalized absolutized pathnames:
    for n in "input output reference".split():
        if getattr(options, n) is None: continue  # if "-r" was not given
        setattr(options, n, os.path.abspath(getattr(options, n)))

    # When --verbose, print all filename options:
    if options.verbose >= 3:
        print "Input:     %s" % options.input
        print "Output:    %s" % options.output
        print "Reference: %s" % options.reference

    # Make sure there is a directory where the output XML file should go:
    try:
        os.makedirs(os.path.dirname(options.output))
    except:
        pass  # fail later if there still is no output directory now

    return options


## XML PROCESSING AND COMPARISON

def read_input_file(input_filename):
    """
    read_input_file(input_filename) -> ET._Element
    
    Read the input file, and return the corresponding XML Element object,
    the element tree root.
    """
    input_xml = ET.parse(input_filename).getroot()
    return input_xml

def postprocess_xml(output_xml):
    """
    postprocess_xml(output_xml) -> ET._Element

    Remove unnecessary namespace declarations and whitespace. Returns a
    modified copy of output_xml. The argument may be modified by calling
    this function.
    """
    # Remove unused namespace declarations:
    # (http://codespeak.net/pipermail/lxml-dev/2009-September/004888.html)
    ns_root = ET.Element("NS_ROOT", nsmap=xmns)
    ns_root.append(output_xml)
    ns_root.remove(output_xml)
    # If you don't perform this copy, each output_xml element's
    # getroottree() will report the temporary tree containing the empty
    # NS_ROOT element. This is not a hack, this is about how lxml works.
    output_xml = ET.ElementTree(copy.copy(output_xml)).getroot()
    
    # Make pretty-printing work by removing unnecessary whitespace:
    for el in output_xml.iter():
        if len(el) and el.text and not el.text.strip():
            el.text = None
        if el.tail and not el.tail.strip():
            el.tail = None

    return output_xml

def write_output_file(output_xml, output_filename):
    """
    Write the output XML Element to the specified output filename.
    """
    output_xmltree = output_xml.getroottree()
    output_xmltree.write(output_filename, pretty_print=True,
                         xml_declaration=True, encoding="utf-8")

def read_xml_schema_file(xml_schema_filename):
    """
    read_xml_schema_file(xml_schema_filename) -> ET.XMLSchema

    Read the XML Schema file, and return the corresponding XML Schema
    object.
    """
    xml_schema_xmltree = ET.parse(xml_schema_filename)
    xml_schema = ET.XMLSchema(xml_schema_xmltree)
    return xml_schema

def match_against_schema(options, output_xml, xml_schema):
    """
    match_against_schema(options, output_xml, xml_schema) -> bool
    
    Validate output against XML Schema.

    The result is True if the output XML Element (tree) matches the XML
    Schema, otherwise the result is False.
    """
    is_valid = xml_schema.validate(output_xml.getroottree())
    if options.verbose >= 2:
        if is_valid:
            print "Output matches XML Schema."
        else:
            print "Output invalid according to XML Schema."
            print xml_schema.error_log.last_error
    return is_valid

def match_against_reference(options, output_xml):
    """
    match_against_reference(options, output_xml) -> bool
    
    Compare the output string (read from file options.output) to the
    reference string (read from options.reference). If they are not the
    same (bytewise), and if options.html_diff is True, create an HTML file
    showing the differences.

    The result is True if output and reference are the same (bytewise),
    otherwise the result is False.
    """
    reference_filename = options.reference
    output_filename = options.output
    do_html_diff = options.html_diff
    
    reference_str = file(reference_filename, "rb").read()
    output_str = file(output_filename, "rb").read()
    is_valid = (reference_str == output_str)
    if options.verbose >= 2:
        if is_valid:
            print "Output matches reference."
        elif not do_html_diff:
            print "Output and reference differ."
    if do_html_diff and not is_valid:
        html_filename = "%s.diff.html" % output_filename
        if options.verbose >= 2:
            print ("Output and reference differ - " +
                   "generating '%s'..." % html_filename)
        create_reference_diff_html(html_filename, reference_str,
                                   output_str)
    return is_valid

def create_reference_diff_html(html_filename, reference_str, output_str):
    """
    Create an HTML file (created at html_filename) showing the differrences
    between the reference string and the output string side-by-side.
    """
    reference_lines = reference_str.splitlines()
    output_lines    = output_str   .splitlines()
    
    import difflib
    html_diff = difflib.HtmlDiff(wrapcolumn=75)
    html_str = html_diff.make_file(reference_lines, output_lines,
                                   "Reference",     "Output")
    file(html_filename, "w").write(html_str)


## XML PREPROCESS CLASS

class XMLPreprocess(object):
    """
    Use:

    >>> proc = XMLPreprocess()
    >>> output_xml = proc(options, input_xml)  # input_xml may change
    """
    
    def __call__(self, xml_element, namespace=None,
                 trace_includes=False, xml_filename=None):
        """
        XMLPreprocess()(...) -> ET._Element
    
        Preprocess the input XML Element to produce an output XML Element.
        The xml_element argument may be modified.

        The namespace given should be a dict that can be used as a Python
        namespace. This namespace will be used in XML attribute
        substitution, and modified by the xm:Loop and xm:Var elements.

        If trace_includes is True, the output will contain tags that
        surround included sections of the file. The xml_filename argument
        is then required.

        Inclusion will recursively call this method (__call__) for
        preprocessing the included file and for recursive inclusion.
        """
        self.namespace = namespace or {}
        self.trace_includes = trace_includes
        self.xml_filename = xml_filename
        
        ns = "{%s}" % xmns["xm"]
        len_ns = len(ns)

        # for el in doc.xpath("//xm:*", **n): print el.tag, (el.xpath("(.//xm:*|following::xm:*)[1]", **n) or [ET.Element("NULL")])[0].tag

        # if False:
        #     child_list = loop_copy.xpath(".//*")
        #     lower_loop_child_set = set(loop_copy.xpath(".//xm:Loop/*",
        #                                                namespaces=xmns))
        #     interesting_set = set(child_list) - lower_loop_child_set
        #     child_list = sorted(interesting_set, key=child_list.index)

        return xml_element

    _eval_substitution_regex = re.compile(r"\{(.*?)\}")

    def _eval_substitution(self, attr_value, namespace):
        """
        Evaluate Python expressions within strings.

        Internal method to perform substitution of Python expressions
        within attribute values, {x} -> str(eval(x)).  Example:

        >>> self._attr_substitution("3 + 5 = {3 + 5} in Python", {})
        '3 + 5 = 8 in Python'

        Multiple Python expressions in one string are supported as well.
        """
        new_a_value = []  # faster than always concatenating strings
        last_index = 0
        for match in self._eval_substitution_regex.finditer(attr_value):
            new_a_value.append(attr_value[last_index:match.start()])
            result = str(eval(match.group(1), namespace, namespace))
            new_a_value.append(result)
            last_index = match.end()
        new_a_value.append(attr_value[last_index:])
        return "".join(new_a_value)

    def Var(self, var_element):
        pass

    def Loop(self, loop_element):
        """
        Loop over a range of integer values.

        The first attribute is evaluated as the loop counter.  Example:

            i="range(5, 9)"  =>  iterates with i being 5, 6, 7, 8

        WARNING: The loop counter attribute, as well as all substitutions
        in subelement attributes (XPath ".//@*": "...{foo_bar}...") will
        (wholly or partially) be evaluated as Python expressions using
        eval().
        """
        # Get the loop counter name and list:
        loop_counter_name = loop_element.keys()[0]
        loop_counter_list = eval(loop_element.get(loop_counter_name))

        # Loop:
        addnext_to_node = loop_element  # for new elements
        for loop_counter_value in loop_counter_list:
            pass

    def Include(self, el):
        """
        Include from the specified file (@file) the elements selected by
        XPath (@select).
        """

    def AddElements(self, el):
        """
        Add subelements to, before, or after the element selected by XPath
        (@to, @before or @after).
        """
        to = el.get("to")
        before = el.get("before")
        after = el.get("after")
        assert sum((to is None, before is None, after is None)) == 2
        select = to or before or after

    def RemoveElements(self, el):
        """
        Remove elements selected by XPath (@select).
        """

    def SetAttribute(self, el):
        """
        Assign the value (@value) to the attribute (@name) of the element
        selected by XPath (@select).
        """

    def RemoveAttribute(self, el):
        """
        Remove the attribute (@name) from the element selected by XPath
        (@select).
        """

    def PythonCode(self, el):
        """
        Execute Python code.
        """


## MAIN FUNCTION

def main(argv):
    """
    main(argv) -> int
    
    Process input to produce output according to the command line options.

    After the XML Merge Manual, this is the first piece of the code a new
    developer will read. Keep this code as simple as possible if you change
    it in any way.

    These are all possible exit status codes returned or raised (using
    SystemExit) by main or the functions it calls:
        - On success, and if all requested validations (-s, -r) match:
            return 0
        - On error, e.g. wrong options (see parse_command_line()):
            return 1
        - On mismatch (either XML Schema (-s) or reference (-r)):
            return mismatch_bitmap  # see end of main()
        - To aid understanding the bitmap: If N matching functions are
          provided, and all are requested and all fail to match the output
          file:
            return (2 ** N - 1) * 2  # mismatch_bitmap
    """
    # Parse command line to get options:
    options = parse_command_line(argv)

    # Input file => preprocessing => output file:
    input_xml = read_input_file(options.input)
    proc = XMLPreprocess()
    output_xml = proc(input_xml, trace_includes=options.trace_includes, xml_filename=options.input)
    output_xml = postprocess_xml(output_xml)
    write_output_file(output_xml, options.output)

    # If -s: Compare output to XML Schema file:
    matches_schema = True  # False means: match requested and negative
    if options.xml_schema is not None:
        xml_schema = read_xml_schema_file(options.xml_schema)
        matches_schema = match_against_schema(options, output_xml,
                                              xml_schema)
    
    # If -r: Compare output to reference:
    matches_reference = True  # False means: match requested and negative
    if options.reference is not None:
        matches_reference = match_against_reference(options, output_xml)

    # Calculate and return the mismatch bitmap:
    mismatch_bitmap = 0
    mismatch_bitmap |= int(not matches_schema)    << 1  # 2 on mismatch
    mismatch_bitmap |= int(not matches_reference) << 2  # 4 on mismatch
    return mismatch_bitmap


if __name__ == "__main__":
    sys.exit(main(sys.argv))
