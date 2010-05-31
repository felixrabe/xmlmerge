#!/usr/bin/env python
# -*- coding: utf-8 -*-

# XML Merge 2.0.1.git

# Copyright 2008,2009  Felix Rabe  <public@felixrabe.net>

# The main() function (search "def main") is a good starting point for
# understanding the code.


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


# Developed (i.e. tested) mainly on Win32 using Python 2.6.4 + lxml 2.2.2,
# and to a lesser extent also with Python 2.5.4 + lxml 2.1.1.

"""
The purpose of XML Merge is to preprocess any kind of XML file with great
flexibility.

XML Merge performs (among other things) recursive XML file inclusion and
XML element and attribute modification.

XML Merge is a Python module. It is normally invoked as a program from the
command line, but can equally well be used from within another Python
program or module.
"""

__version_info__ = (2, 0, 1, "git")
__version__ = ".".join(str(n) for n in __version_info__[:2])

## IMPORTS AND CONSTANTS

import copy
import itertools
import optparse
import os
import re
import sys
import textwrap

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

    def error(self, *a, **kw):
        self.print_help()
        return optparse.OptionParser.error(self, *a, **kw)


def parse_command_line(argv):
    """
    parse_command_line(argv) -> optparse.Values
    
    Parse argv and return an optparse.Values object containing the options.

    This function performs all the necessary checks and conversions to make
    sure all necessary options are given.  The resulting options are provided in
    a normalized format.

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
        if el.text and not el.text.strip():
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


## VARIOUS FUNCTIONS

def print_xml_error(xml_element, code=None):
    print >>sys.stderr, "*** XML ERROR ***"
    tree = xml_element.getroottree()
    print >>sys.stderr, "File URL:", tree.docinfo.URL
    xpath = tree.getpath(xml_element)
    print >>sys.stderr, "Line:", xml_element.sourceline, " XPath:", xpath
    if code is not None:
        print >>sys.stderr, "Offending Python code / expression:"
        print >>sys.stderr, "    %s" % code.replace("\n", "\n    ")


_brace_substitution_regex = re.compile(r"\{(.*?)\}")

def brace_substitution(string, xml_element=None, namespace=None):
    """
    Evaluate Python expressions within strings.

    This internal method substitutes Python expressions embedded in strings for
    their evaluated (string) values, like {x} -> str(eval(x)).  Example:

    >>> self._eval_substitution("3 + 5 = {3 + 5} in Python")
    '3 + 5 = 8 in Python'

    Multiple Python expressions in one string are supported as well.  Nested
    Python expressions are not supported.
    """
    if namespace is None: namespace = {}
    new_str = []  # faster than continuously concatenating strings
    last_index = 0
    for match in _brace_substitution_regex.finditer(string):
        new_str.append(string[last_index:match.start()])
        expression = match.group(1)
        try:
            result = str(eval(expression, namespace))
        except:
            if xml_element is not None:
                print_xml_error(xml_element, code=expression)
                print >>sys.stderr
            raise
        new_str.append(result)
        last_index = match.end()
    new_str.append(string[last_index:])
    return "".join(new_str)


## XML PREPROCESS CLASS

class XMLPreprocess(object):
    """
    Use:

    >>> proc = XMLPreprocess()
    >>> output_xml = proc(options, input_xml)  # input_xml may change
    """

    def __init__(self, initial_namespace={}):
        super(XMLPreprocess, self).__init__()
        self._namespace_stack = [initial_namespace]
    
    def __call__(self, xml_element, namespace=None,
                 trace_includes=False, xml_filename=None):
        """
        XMLPreprocess()(...)
    
        Preprocess the input XML Element, xml_element. The element tree of
        xml_element will be modified in-place.

        The namespace given should be a dict that can be used as a Python
        namespace. This namespace will be used in XML attribute
        substitution.

        If trace_includes is True, the output will contain tags that
        surround included sections of the file. The xml_filename argument
        is then required.

        Processing tags will recursively call this method (__call__) for
        preprocessing the included file and for recursive inclusion.
        """
        if namespace is not None:
            self._namespace_stack.append(namespace)
        self.namespace = self._namespace_stack[-1]
        self.trace_includes = trace_includes
        self.xml_filename = xml_filename
        
        ns = "{%s}" % xmns["xm"]
        len_ns = len(ns)

        # Evaluate Python expressions in the attributes of xml_element:
        for attr_name, attr_value in xml_element.items():  # attr map
            v = brace_substitution(attr_value, xml_element, self.namespace)
            xml_element.set(attr_name, v)

        # If xml_element has xmns["xm"] as its namespace, proceed with the
        # appropriate method of this class:
        if xml_element.nsmap.get(xml_element.prefix) == xmns["xm"]:
            tag = xml_element.tag[len_ns:]  # just the tag without namespc
            method = "_xm_" + tag.lower()  # tolerate any case
            if not hasattr(self, method):
                raise Exception, "cannot process <xm:%s/>" % tag
            getattr(self, method)(xml_element)  # call the method
            # Preserve tail text:
            tail = xml_element.tail
            if tail is not None:
                prev = xml_element.getprevious()
                parent = xml_element.getparent()
                if prev is not None:
                    prev.tail = (prev.tail or "") + tail
                else:
                    parent.text = (parent.text or "") + tail
            xml_element.getparent().remove(xml_element)

        # If not, recurse:
        else:
            self._recurse_into(xml_element)

        return None

    def _recurse_into(self, xml_element, namespace=None):
        if namespace is not None:
            self._namespace_stack.append(namespace)
        for xml_sub_element in xml_element.xpath("*"):
            self(xml_sub_element, None,
                 self.trace_includes, self.xml_filename)
        if namespace is not None:
            self._namespace_stack.pop()
            self.namespace = self._namespace_stack[-1]

    def _xm_addelements(self, xml_element):
        """
        Add subelements to, before, or after the element selected by XPath
        (@to, @before or @after).

        Exactly one of (@to, @before, @after) must be specified.  And the
        XPath expression must return exactly one element.  These conditions
        are checked by assertions and will raise an exception if not met.
        """
        to     = xml_element.get("to")
        before = xml_element.get("before")
        after  = xml_element.get("after")
        
        assert sum((to is None, before is None, after is None)) == 2
        select = to or before or after
        
        selected_context_nodes = xml_element.xpath(select)
        assert len(selected_context_nodes) == 1
        
        context_node = selected_context_nodes[0]
        replace_context_node = False
        
        if to is not None:
            f = "append"
        if before is not None:
            f = "addprevious"
        if after is not None:
            f = "addnext"
            replace_context_node = True

        for xml_sub_element in xml_element:
            getattr(context_node, f)(xml_sub_element)
            if replace_context_node:
                context_node = xml_sub_element

    def _xm_block(self, xml_element):
        """
        Create a scope to contain visibility of newly assigned Python
        variables.  This works the same way that Python itself scopes
        variables, i.e. by creating a shallow copy of the Python namespace.
        E.g. assignments to list items will be visible to outside scopes!
        """
        self._recurse_into(xml_element, self.namespace.copy())
        for xml_sub_node in xml_element[::-1]:  # get children reversed
            xml_element.addnext(xml_sub_node)

    def _xm_comment(self, xml_element):
        """
        A comment that is removed by XML Merge.
        """
        pass  # that's it

    def _xm_defaultvar(self, xml_element):
        """
        Set (zero or more) variables in the active Python namespace, if not
        already set.
        """
        ns = self.namespace
        for attr_name, attr_value in xml_element.items():  # attr map
            if not attr_name in ns:
                try:
                    ns[attr_name] = eval(attr_value, ns)
                except:
                    print_xml_error(xml_element, code=attr_value)
                    print >>sys.stderr
                    raise

    def _xm_include(self, xml_element):
        """
        Include from the specified file (@file) the elements selected by
        XPath (@select) after preprocessing said file.

        The @file attribute is the only required attribute.

        Items can be imported from the included (and preprocessed) file's
        Python namespace into the current file's namespace using the
        @import attribute, which may either be a comma-separated list of
        identifiers, or '*' to import the complete namespace.

        Remaining attributes will be treated as variable assignments and
        put in the Python namespace used for processing the included file.
        """
        attrib = xml_element.attrib
        file_   = attrib.pop("file", None)
        select  = attrib.pop("select", None)
        import_ = attrib.pop("import", None)
        assert file_ is not None
        remaining_attribs = dict(attrib.items())

        # Load the to-be-included file:
        p = os.path

        xml_input_dirname = p.dirname(self.xml_filename)
        xml_incl_filename = p.join(xml_input_dirname, file_)
        xml_incl_filename = p.normpath(xml_incl_filename)
        # Always use '/' for normalized tracing information:
        xml_incl_filename = xml_incl_filename.replace("\\", "/")

        xml_incl = ET.parse(xml_incl_filename).getroot()

        # Build the initial namespace from a copy of the current namespace
        # plus the remaining attributes of the <xm:Include/> element:
        current_ns = self.namespace
        initial_namespace = current_ns.copy()
        for attr_name, attr_value in remaining_attribs.items():  # attr map
            try:
                initial_namespace[attr_name] = eval(attr_value, current_ns)
            except:
                print_xml_error(xml_element, code=attr_value)
                print >>sys.stderr
                raise

        # Preprocess the to-be-included file:
        proc = XMLPreprocess(initial_namespace=initial_namespace)
        proc(xml_incl, trace_includes=self.trace_includes,
             xml_filename=xml_incl_filename)

        # Select elements to include:
        included_elements = []
        if select is not None:
            included_elements = xml_incl.xpath(select)

        # Include the elements:
        context_node = xml_element
        for inc_elem in included_elements:
            context_node.addnext(inc_elem)
            context_node = inc_elem

        # Import from included namespace:
        imported_namespace = {}
        if import_ is not None:
            import_ = [x.strip() for x in import_.split(",")]
            if "*" in import_:  # import all
                imported_namespace = proc.namespace
            else:
                ns = proc.namespace
                imported_namespace = dict((x, ns[x]) for x in import_)
        self.namespace.update(imported_namespace)

    def _xm_loop(self, xml_element):
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
        loop_counter_name = xml_element.keys()[0]
        loop_counter_expr = xml_element.get(loop_counter_name)
        try:
            loop_counter_list = eval(loop_counter_expr, self.namespace)
        except:
            print_xml_error(xml_element, code=loop_counter_expr)
            print >>sys.stderr
            raise

        # Loop:
        context_node = xml_element  # for new elements
        for loop_counter_value in loop_counter_list:
            self.namespace[loop_counter_name] = loop_counter_value
            tailtext = xml_element.tail
            xml_element.tail = None  # xml_element regarded as document
            # xml_element_copy = copy.copy(xml_element)  # CRASH
            # The following line is the workaround for the preceeding one:
            xml_element_copy = ET.XML(ET.tostring(xml_element))
            xml_element.addnext(xml_element_copy)  # temporarily
            xml_element.tail = xml_element_copy.tail = tailtext
            self._recurse_into(xml_element_copy)
            xml_element_copy.getparent().remove(xml_element_copy)
            if xml_element_copy.text is not None:
                if context_node.tail is None:
                    context_node.tail = u""
                context_node.tail += xml_element_copy.text
            for xml_sub_node in xml_element_copy[:]:
                context_node.addnext(xml_sub_node)
                context_node = xml_sub_node

    def _xm_pythoncode(self, xml_element):
        """
        Execute Python code in the current namespace.

        'self' and 'xml_element' are supplied temporarily. They are added
        to the current namespace before the 'exec' statement, and removed
        again afterwards.
        """
        code = textwrap.dedent(xml_element.text).strip()
        self.namespace["self"] = self
        self.namespace["xml_element"] = xml_element
        try:
            exec code in self.namespace
        except:
            print_xml_error(xml_element, code=code)
            print >>sys.stderr
            raise
        del self.namespace["self"], self.namespace["xml_element"]

    def _xm_removeattributes(self, xml_element):
        """
        Remove the attributes (@name) from the (zero or more) elements
        selected by XPath (@from or @select).

        It is not considered an error if an attribute cannot be found on a
        selected element.
        """
        attr_name = xml_element.get("name")
        select_xpath = xml_element.get("from") or xml_element.get("select")
        for xml_element_selected in xml_element.xpath(select_xpath):
            # Can't find another way to remove an attribute than by using
            # 'attrib':
            attrib = xml_element_selected.attrib
            if attr_name in attrib:
                del xml_element_selected.attrib[attr_name]

    def _xm_removeelements(self, xml_element):
        """
        Remove (zero or more) elements selected by XPath (@select).
        """
        select = xml_element.get("select")
        assert select is not None
        elements = xml_element.xpath(select)
        for el in elements:
            el.getparent().remove(el)

    def _xm_setattribute(self, xml_element):
        """
        Assign the value (@value) to the attribute (@name) of the element
        selected by XPath (@of or @select).

        Example:
            <Object index="0x1234"/>
            <xm:SetAttribute of="../Object" name="otherattr" value="hallo"/>

        Leads to:
            <Object index="0x1234" otherattr="hello"/>
        """
        select  = xml_element.get("select", xml_element.get("of"))
        name    = xml_element.get("name")
        value   = xml_element.get("value")
        assert sum((select is None, name is None, value is None)) == 0
        elements = xml_element.xpath(select)
        for el in elements:
            el.set(name, value)

    def _xm_text(self, xml_element):
        """
        Perform '{}' substitution on text.
        """
        text = xml_element.text
        if text is None: return
        tail = brace_substitution(text, xml_element, self.namespace)
        tail += xml_element.tail or ""
        xml_element.tail = tail

    def _xm_var(self, xml_element):
        """
        Set (zero or more) variables in the active Python namespace.
        """
        ns = self.namespace
        for attr_name, attr_value in xml_element.items():  # attr map
            try:
                ns[attr_name] = eval(attr_value, ns)
            except:
                print_xml_error(xml_element, code=attr_value)
                print >>sys.stderr
                raise


## MAIN FUNCTION

def main(argv, **kargs):
    """
    main(argv, **kargs) -> int
    
    Process the input file to produce an output file according to the command
    line options, given in argv.  These keyword arguments (**kargs) are
    recognized:

    initial_namespace
      Gets passed on as the initial Python namespace to XMLPreprocess().

    After the XML Merge Manual, the code of this function is the first part of
    XML Merge any new developer should read.  So keep this code as simple as
    possible if you change it in any way.

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
    xml = read_input_file(options.input)
    proc = XMLPreprocess(**kargs)
    proc(xml, trace_includes=options.trace_includes,
         xml_filename=options.input)
    xml = postprocess_xml(xml)
    write_output_file(xml, options.output)

    # If -s: Compare output to XML Schema file:
    matches_schema = True  # False means: match requested and negative
    if options.xml_schema is not None:
        xml_schema = read_xml_schema_file(options.xml_schema)
        matches_schema = match_against_schema(options, xml, xml_schema)
    
    # If -r: Compare output to reference:
    matches_reference = True  # False means: match requested and negative
    if options.reference is not None:
        matches_reference = match_against_reference(options, xml)

    # Calculate and return the mismatch bitmap:
    mismatch_bitmap = 0
    mismatch_bitmap |= int(not matches_schema)    << 1  # 2 on mismatch
    mismatch_bitmap |= int(not matches_reference) << 2  # 4 on mismatch
    return mismatch_bitmap


if __name__ == "__main__":
    sys.exit(main(sys.argv))
