#!/usr/local/bin/python3

# module needed to parse command line arguments
import sys

# module for working with XML
from lxml import etree
from lxml.etree import Element
from lxml.etree import SubElement

# working with file paths
from os import path

# regular expresions
# import re


# import utility functions
try:
    import get_op_utility_functions2 as op_functions
except ImportError:
    import package.get_op_utility_functions2 as op_functions


fileextension = "-announcements-for-InDesign.xml"


def main():
    if len(sys.argv) != 3:
        print(
            "\nThis script takes 2 arguments.\n",
            "1:\tthe url for the XML you wish to process.\n",
            "3:\tthe date in the for the OP you want to make in the form YYYY-MM-DD, i.e.'2016-09-12'\n",
        )
        exit()

    input_xml = sys.argv[1]
    input_date = sys.argv[2]

    process_xml(input_xml, input_date)


def process_xml(input_xml, input_date):

    laying_minister_lookup = {}
    laying_minister_lookup = op_functions.get_mnis_data(laying_minister_lookup)

    input_root = etree.parse(str(input_xml)).getroot()

    op_functions.dropns(input_root)
    # print(input_root.tag)
    # get the day we are interested
    date_elements = input_root.xpath(
        'Days/Day/Date[text()[contains(.,"' + input_date + '")]]'
    )

    output_root = etree.fromstring("<root></root>")

    if len(date_elements) > 0:

        day_element = date_elements[0].getparent()
        # print(day_element[1].tag)
        # build up output tree
        output_root = Element("root")
        # output root Add element for Annoincements Title
        SubElement(output_root, "OPHeading1").text = "Announcements"

        # get all the DayItem in the day
        announcement_dayItems = day_element.xpath(
            './Sections/Section/Name[text()="Announcements"]/../DayItems/DayItem'
        )

        for dayItem in announcement_dayItems:
            # get the day item type or None
            day_item_type = dayItem.find("DayItemType")
            # we need the day item type to not be None
            if day_item_type is None:
                continue
            # check if this item is a child of another day item
            if dayItem.getparent().tag == "ChildDayItems":
                day_item_is_child = True
            else:
                day_item_is_child = False
            # check if this item has children
            if (
                dayItem.find("BusinessItemDetail/ChildDayItems") is not None
                and len(dayItem.find("BusinessItemDetail/ChildDayItems")) > 0
            ):
                has_children = True
            else:
                has_children = False
            # find the title if it exists
            title = dayItem.find("Title")
            # find the title text if it exists
            title_text = dayItem.findtext("Title", default="")

            # first test to see if the day item is a heading and then update the section to append to

            if day_item_type.text == "SectionDayDivider":
                # now add any section day divider title to the XML for InDesign
                SubElement(output_root, "OPHeading2").text = title_text

                # also add any notes
                if dayItem.find("Notes") is not None:
                    SubElement(
                        output_root, "DebateTimingRubric"
                    ).text = dayItem.findtext("Notes", default="")

            # if this is a business item
            elif day_item_type.text == "BusinessItem":
                if title_text.upper().strip() != "NO TITLE NEEDED":
                    SubElement(
                        output_root, "BusinessItemHeadingBulleted"
                    ).text = title_text

                op_functions.append_timing_so(output_root, dayItem)
                # make sure we get announcement stuff
                businessItemType = dayItem.find("BusinessItemDetail/BusinessItemType")
                # get the sponsor info
                op_functions.append_motion_sponosrs(
                    dayItem, output_root, laying_minister_lookup
                )
                if businessItemType is not None:
                    motionText = Element("MotionText")
                    motionText.append(
                        op_functions.process_CDATA(
                            dayItem.findtext("BusinessItemDetail/ItemText", default="")
                        )
                    )
                    output_root.append(motionText)
                    # add Relevant Documents
                    op_functions.notes_relevant_docs(
                        dayItem, output_root, has_children, day_item_is_child
                    )

    # get the path to input file
    pwd = path.dirname(path.abspath(input_xml))
    # write out the file
    filename = path.basename(input_xml).replace("as-downloaded-", "").split(".")[0]
    filepath = path.join(pwd, filename)

    # loop through output
    # replace any non breaking spaces with ordinary spaces
    # replace single quotes with double quotes
    op_functions.clean_up_text(output_root)

    # and new line after `The following Departments will answer:`
    for element in output_root.iterdescendants(tag="from_cdata"):
        to_replace = "The following Departments will answer: "
        replace_with = "The following Departments will answer:\n"
        if isinstance(element.text, str) and element.text.startswith(to_replace):
            element.text = element.text.replace(to_replace, replace_with, 1)

    # write out an xml file
    et = etree.ElementTree(output_root)
    try:
        et.write(filepath + fileextension)  # , pretty_print=True
        print("\nOutput file is located at:\n", path.abspath(filepath + fileextension))
    except Exception:
        # make sure it works even if we dont have permision to modify the file
        try:
            et.write(filepath + "2" + fileextension)
            print(
                "\nOutput file is located at:\n",
                path.abspath(filepath + "2" + fileextension),
            )
        except Exception:
            print(
                "Error:\tThe file "
                + path.abspath(filepath + "2" + fileextension)
                + " dose not seem to be writable."
            )


if __name__ == "__main__":
    main()
