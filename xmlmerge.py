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


import copy
import optparse
import os
import posixpath
import re
import sys
import traceback

import lxml.etree as ET


xmns = {"xm":   "urn:felixrabe:xmlns:xmlmerge:preprocess",
        "xmt":  "urn:felixrabe:xmlns:xmlmerge:inctrace"}


class OptionParser(optparse.OptionParser):

    def __init__(self, *a, **kw):
        optparse.OptionParser.__init__(self, *a, **kw)
        self.add_option("-r", "--reference",
                        help="original XML file for reference")
        self.add_option("-i", "--input",
                        help="(REQUIRED) input XML file")
        self.add_option("-o", "--output",
                        help="output XML file")
        self.add_option("-t", "--trace-includes", action="store_true",
                        help=("Add xmt: namespace tags to output to " +
                              "trace origins of elements to included " +
                              "files"))
        self.add_option("-D", "--no-diff", action="store_true",
                        help=("if output differs from reference, do " +
                              "not produce a difference HTML file"))
        self.add_option("-v", "--verbose", action="store_const",
                        dest="verbose", const=3,
                        help=("show debugging messages (only useful " +
                              "when changing the program)"))
        self.add_option("-q", "--quiet", action="store_const",
                        dest="verbose", const=1,
                        help="only show error messages")
        self.set_defaults(verbose=2)


def numstr2hexstr(number_string, padding_size=2):
    number_string = number_string.strip()
    format_string = "%%0%uX" % padding_size

    if not number_string:
        hex_number = 0
    elif number_string.lower().endswith("h"):
        hex_number = int(number_string[:-1], 16)
    elif number_string.lower().startswith("0x"):
        hex_number = int(number_string[2:], 16)
    else:
        hex_number = int(number_string)

    hex_string = format_string % hex_number
    if len(hex_string) % 2:
        hex_string = "0" + hex_string
    return hex_string


def hex2int(s):
    return int(numstr2hexstr(s), 16)


def int2hex(n):
    return "0x" + numstr2hexstr(str(n))


def remove_indent(block):
    indent = ""
    for line in block.split("\n"):
        if not line.strip(): continue
        match = re.match(r"\s*", line)
        if match is None: raise Exception, "Weirdo regexp"
        indent = match.group()
        break
    
    len_indent = len(indent)
    new_block = []
    for line in block.split("\n"):
        if not line.strip():
            new_block.append("")
            continue
        if not line.startswith(indent):
            print "Code:"
            print block
            raise Exception, "Bad code indentation (see above)"
        new_block.append(line[len_indent:])
    return "\n".join(new_block)


class App(object):

    def __init__(self, argv):
        super(App, self).__init__()

        option_parser = OptionParser()
        options, args = option_parser.parse_args(argv[1:])
        try:
            assert args == []
            assert options.input is not None
        except:
            traceback.print_exc()
            print
            option_parser.print_help()
            sys.exit(1)
        self.options = options

        if options.output is None:
            if options.input.lower().endswith(".xml"):
                options.output  = options.input[:-4] + ".out.xml"
            else:
                options.output  = options.input      + ".out.xml"

        for n in "reference input output".split():
            if getattr(options, n) is None: continue  # for "reference"
            setattr(options, n, os.path.abspath(getattr(options, n)))

        if options.verbose >= 3:
            print "Reference: %s" % options.reference
            print "Input:     %s" % options.input
            print "Output:    %s" % options.output

        try:
            os.makedirs(os.path.dirname(options.output))
        except:
            pass

        xml_tree = self.read_xml(options.input)
        XMLCommands(xml_tree, options)
        self.write_xml(xml_tree, options.output)
        if options.reference is not None:
            self.check_against_reference(options.reference, options.output)

    def read_xml(self, filename):
        return ET.parse(filename)

    def write_xml(self, xml_tree, filename):
        # Hack to make the following code work - probably an lxml bug
        xml_tree._setroot(ET.XML(ET.tostring(xml_tree, encoding="utf-8")))
        # xml_tree.write(filename, xml_declaration=True, encoding="utf-8")
        # xml_tree._setroot(ET.parse(filename).getroot())
        
        # Remove unused namespaces from root element
        root = xml_tree.getroot()
        new_root = ET.Element(root.tag, root.attrib)
        new_root.text = root.text
        new_root.tail = root.tail
        for x in root: new_root.append(copy.copy(x))
        xml_tree._setroot(new_root)
        
        # Make pretty-printing work
        for el in xml_tree.iter():
            if len(el) and el.text and not el.text.strip():
                el.text = None
            if el.tail and not el.tail.strip():
                el.tail = None

        # Write XML file
        xml_tree.write(filename, pretty_print=True, xml_declaration=True,
                       encoding="utf-8")

    def check_against_reference(self, reference, output):
        ref = file(reference).read()
        out = file(output).read()
        if ref == out:
            print "Output matches reference."
        elif self.options.no_diff:
            print "Output and reference differ."
        else:
            print "Output and reference differ - generating '%s.diff.html'..." % output
            import difflib
            h = difflib.HtmlDiff(wrapcolumn=75)
            ref = ref.split("\n")
            out = out.split("\n")
            file(output + ".diff.html", "w").write(h.make_file(ref, out, "Ref", "Out"))


class XMLCommands(object):

    def __init__(self, xml_tree, options):
        super(XMLCommands, self).__init__()
        self.options = options
        ns = "{%s}" % xmns["xm"]
        len_ns = len(ns)

        root = xml_tree.getroot()
        while True:
            # This "unnecessary conversion" is a hack to prevent lxml from
            # segfaulting Python (2.5 and 2.6, tested with lxml 2.1.1 on
            # Win32), probably caused by copying and moving elements within
            # the Loop method.
            root = ET.XML(ET.tostring(root))
            loop = root.xpath("//xm:Loop[1]", namespaces=xmns)
            if not loop: break
            loop = loop[0]
            self.Loop(loop)
            loop.getparent().remove(loop)
        xml_tree._setroot(root)

        if self.options.trace_includes:
            root = xml_tree.getroot()
            new_root = ET.Element(root.tag, attrib=root.attrib, nsmap=xmns)
            new_root.text = root.text
            new_root.tail = root.tail
            for x in root: new_root.append(copy.copy(x))
            xml_tree._setroot(root)

        for e in xml_tree.xpath("//xm:Include", namespaces=xmns):
            self.Include(e)
            e.getparent().remove(e)
            
        for e in xml_tree.xpath("//xm:*", namespaces=xmns):
            tag = e.tag[len_ns:]
            getattr(self, tag)(e)
            e.getparent().remove(e)

    _loop_replace_re = re.compile(r"\{(.*?)\}")

    def Loop(self, e):
        """
        Loop over a range of integer values.
        """
        master_var = None
        format = None
        var = {}
        for k, v in e.attrib.iteritems():
            if k == "format":
                format = v
                del e.attrib[k]
                continue
            if master_var is None:
                master_var = k
            var[k] = v
        lower, upper = map(eval, var[master_var].split(".."))
        e_addnext = e
        for i in range(lower, upper+1):
            ns = {master_var: i}
            for k, v in var.iteritems():
                if k == master_var: continue
                ns[k] = eval(v, ns, ns)
            e_copy = copy.copy(e)
            for sub_e in e_copy.xpath("descendant::*"):
                for k, v in sub_e.attrib.iteritems():
                    last_index = 0
                    new_v = []
                    for m in self._loop_replace_re.finditer(v):
                        new_v.append(v[last_index:m.start()])
                        result = eval(m.group(1), ns, ns)
                        if format is None:
                            result = str(result)
                        else:
                            result = format % result
                        new_v.append(result)
                        last_index = m.end()
                    new_v.append(v[last_index:])
                    sub_e.attrib[k] = "".join(new_v)
            for sub_e in e_copy:
                e_addnext.addnext(sub_e)
                e_addnext = sub_e

    def Include(self, e):
        """
        Include from the specified file the elements selected by XPath.

        If objectIndexBase is specified, add the given integer number
        to each included Object/@offset and store as Object/@index, and
        remove the Object/@offset attributes.
        """
        p = os.path
        pp = posixpath
        input_dirpath = p.dirname(self.options.input)
        file_ = p.normpath(p.join(input_dirpath, e.attrib["file"]))
        rel_path = pp.relpath(file_, input_dirpath)
        if self.options.trace_includes:
            e.addnext(ET.Element("{%s}Start" % xmns["xmt"], nsmap=xmns))
        select = e.attrib["select"]
        objectIndexBase = e.attrib.get("objectIndexBase")
        elements = ET.parse(file_).xpath(select)
        for e_inc in elements:
            e.addnext(e_inc)
            e = e_inc
        if self.options.trace_includes:
            e.addnext(ET.Element("{%s}End" % xmns["xmt"], nsmap=xmns))
        if objectIndexBase is not None:
            objectIndexBase = eval(objectIndexBase)
            for e_inc in elements:
                index = hex2int(e_inc.attrib.pop("offset")) + objectIndexBase
                e_inc.attrib["index"] = int2hex(index)

    def AddElements(self, e):
        """
        Add elements within to or before the element selected by XPath.
        """
        to = e.attrib.get("to")
        before = e.attrib.get("before")
        assert (to is None) ^ (before is None)
        select = to or before
        if to is not None:
            f = "append"
        if before is not None:
            f = "addprevious"
        elements = e.xpath(select)
        assert len(elements) == 1
        elem = elements[0]
        for sub_e in e:
            getattr(elem, f)(sub_e)

    def RemoveElements(self, e):
        """
        Remove elements selected by XPath.
        """
        select = e.attrib["select"]
        elements = e.xpath(select)
        for elem in elements:
            elem.getparent().remove(elem)

    def SetAttribute(self, e):
        """
        Set attribute of element selected by XPath.
        """
        select = e.attrib["select"]
        name = e.attrib["name"]
        value = e.attrib["value"]
        elements = e.xpath(select)
        assert len(elements) == 1
        elements[0].attrib[name] = value

    def RemoveAttribute(self, e):
        """
        Remove attribute from element selected by XPath.
        """
        select = e.attrib["select"]
        name = e.attrib["name"]
        elements = e.xpath(select)
        assert len(elements) == 1
        del elements[0].attrib[name]

    def PythonCode(self, e):
        """
        Execute Python code.
        """
        print "PythonCode", attrib


if __name__ == "__main__":
    App(sys.argv)
