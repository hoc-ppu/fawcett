#!/usr/local/bin/python3

# module needed to parse command line arguments
import sys

# module for working with XML
from lxml import etree
from lxml.etree import Element
from lxml.etree import _Element
from lxml.etree import SubElement

# working with file paths
from os import path
from typing import List

# import datetime
from datetime import date

# import utility functions
try:
    import get_op_utility_functions2 as op_functions
except ImportError:
    import package.get_op_utility_functions2 as op_functions

fileextension = "-FBA-for-InDesign.xml"


def main():
    if len(sys.argv) != 3:
        print(
            "\nThis script takes 2 arguments.\n",
            "1:\tthe url for the XML you wish to process.\n",
            "3:\tthe effective date after witch items will appear in FBA, e.g.'2016-09-12'\n",
        )
        exit()

    process_xml(sys.argv[1], sys.argv[2])


def process_xml(input_xml, input_date):

    laying_minister_lookup = {}
    laying_minister_lookup = op_functions.get_mnis_data(laying_minister_lookup)

    input_root = etree.parse(input_xml).getroot()
    input_date_object = date(
        int(input_date.split("-")[0]),
        int(input_date.split("-")[1]),
        int(input_date.split("-")[2]),
    )
    op_functions.dropns(input_root)
    # get the day we are interested
    day_elements: List[_Element]
    day_elements = input_root.xpath("Days/Day")  # type: ignore
    (day_elements)
    date_to_remove = []
    for day_element in day_elements:
        time_stamp_text = day_element.findtext("Date", default="")
        time_stamp_text = time_stamp_text.replace("T00:00:00", "")
        splits = time_stamp_text.split("-")
        date_timestamp = date(int(splits[0]), int(splits[1]), int(splits[2]))
        if date_timestamp <= input_date_object:
            date_to_remove.append(day_element)
    for day_element in date_to_remove:
        day_elements.remove(day_element)
    if len(day_elements) < 1:
        input(
            "Error:\tCan't seem to find the date you are after. "
            "Check it appears in the XML, Press any key to exit."
        )
        exit()

    # build up output tree
    output_root = Element("root")
    # add the FBA title
    SubElement(output_root, "OPHeading1").text = "A. Calendar of Business"

    for day_element in day_elements:
        # get all the sections
        sections: List[_Element]
        sections = day_element.xpath("Sections/Section")  # type: ignore
        sections_in_day_list = []
        for section in sections:
            sections_in_day_list.append(
                section.findtext("Name", default="").strip().upper()
            )

        # Add the date in a level 2 gray heading
        date_elelemnt = day_element.find("Date")
        if date_elelemnt is not None and (
            "CHAMBER" in sections_in_day_list
            or "WESTMINSTER HALL" in sections_in_day_list
        ):
            formatted_date = op_functions.format_date(date_elelemnt.text)
            if formatted_date is not None:
                SubElement(output_root, "OPHeading2").text = formatted_date

        # create a variable to store a reference to the heading
        # as where a business item falls determins its style
        last_gray_heading_text = ""
        # print(sections)
        for section in sections:
            section_name = section.findtext("Name")
            if section_name is not None:
                section_name = section_name.strip().upper()
            if section_name in ("CHAMBER", "WESTMINSTER HALL"):
                SubElement(output_root, "FbaLocation").text = section_name
            else:
                continue
            # get all the DayItem in the day
            dayItems: List[_Element]
            dayItems = section.xpath(".//DayItem")  # type: ignore

            for dayItem in dayItems:
                # get the day item type or None
                day_item_type = dayItem.find("DayItemType")
                # we need the day item type to not be None
                if day_item_type is None:
                    continue
                # check if this item is a child of another day item
                day_item_parent = dayItem.getparent()
                if day_item_parent is not None and day_item_parent == "ChildDayItems":
                    day_item_is_child = True
                else:
                    day_item_is_child = False
                # check if this item has children
                child_day_items = dayItem.find("BusinessItemDetail/ChildDayItems")
                if child_day_items is not None and len(child_day_items) > 0:
                    has_children = True
                else:
                    has_children = False
                # find the title if it exists
                title_element = dayItem.find("Title")
                title = ""
                if title_element is not None and title_element.text:
                    title = title_element.text.strip()

                # first test to see if the day item is a heading
                # and then update the section to append to

                if (
                    day_item_type.text == "SectionDayDivider"
                    and dayItem.find("Title") is not None
                ):
                    last_gray_heading_text = dayItem.findtext(
                        "Title", default=""
                    ).upper()
                    if last_gray_heading_text.upper() not in (
                        "BUSINESS OF THE DAY",
                        "URGENT QUESTIONS AND STATEMENTS",
                        "ORDER OF BUSINESS",
                    ):
                        # only add Questions and Adjournment debate heading if
                        # not followed by another heading
                        if last_gray_heading_text.upper() in (
                            "QUESTIONS",
                            "ADJOURNMENT DEBATE",
                        ):
                            next_day_item = dayItem.getnext()
                            if (
                                next_day_item is not None
                                and next_day_item.findtext("DayItemType", default="")
                                != "SectionDayDivider"
                            ):
                                SubElement(
                                    output_root, "BusinessItemHeading"
                                ).text = title

                        else:
                            SubElement(output_root, "BusinessItemHeading").text = title

                # Do different things based on what business item type
                business_item_type = dayItem.find("BusinessItemDetail/BusinessItemType")

                if business_item_type is not None:
                    # PRIVATE BUSINESS
                    if business_item_type.text == "Private Business":
                        SubElement(
                            output_root, "BusinessItemHeadingBulleted"
                        ).text = title

                    # QUESTIONS
                    if business_item_type.text == "Substantive Question":
                        time_ele = dayItem.find("BusinessItemDetail/Time")
                        formatted_time = ""  # default to empty str
                        if time_ele is not None:
                            formatted_time = op_functions.format_time(time_ele.text)
                        SubElement(
                            output_root, "QuestionTimeing"
                        ).text = f"{formatted_time}\t{title}"

                    if business_item_type.text in ("Motion", "Legislation"):
                        # legislation and motion types appear differently if they are in business today
                        if (
                            last_gray_heading_text == "BUSINESS OF THE DAY"
                            and day_item_is_child is False
                        ):
                            SubElement(output_root, "BusinessItemHeading").text = title
                        else:
                            SubElement(output_root, "Bulleted").text = title

                    # Adjournment Debate type is displayed differently in the chamber vs westminster hall
                    if business_item_type.text == "Adjournment Debate":
                        # get the sponsor
                        sponsor_name = dayItem.find(
                            "BusinessItemDetail/Sponsors/Sponsor/Name"
                        )
                        if sponsor_name is None or sponsor_name.text is None:
                            sponsor_name = ""
                        else:
                            sponsor_name = sponsor_name.text
                        sponsor_ele = Element("PresenterSponsor")
                        sponsor_ele.text = sponsor_name
                        # title without end punctuation
                        title_no_end_punctuation = title
                        if title[-1] == ".":
                            title_no_end_punctuation = title_no_end_punctuation[:-1]
                        # Adjournment Debate type is displayed differently in the chamber vs westminster hall
                        if section_name == "CHAMBER":
                            adjourn_ele = Element("BusinessListItem")
                            adjourn_ele.text = title_no_end_punctuation + ": "
                        # westminster hall
                        elif section_name == "WESTMINSTER HALL":
                            adjourn_ele = Element("WHItemTiming")
                            adjourn_ele.text = (
                                op_functions.format_time(
                                    dayItem.findtext(
                                        "BusinessItemDetail/Time", default=""
                                    )
                                )
                                + "\t"
                                + title_no_end_punctuation
                                + ": "
                            )
                        else:
                            continue
                        adjourn_ele.append(sponsor_ele)
                        output_root.append(adjourn_ele)

                    # Petitions
                    if business_item_type.text == "Petition":
                        # get the sponsor
                        sponsor_name = dayItem.find(
                            "BusinessItemDetail/Sponsors/Sponsor/Name"
                        )
                        if sponsor_name is None or sponsor_name.text is None:
                            sponsor_name = ""
                        else:
                            sponsor_name = sponsor_name.text
                        sponsor_ele = Element("PresenterSponsor")
                        sponsor_ele.text = sponsor_name
                        # title without end punctuation
                        title_no_end_punctuation = title
                        if title[-1] == ".":
                            title_no_end_punctuation = title_no_end_punctuation[:-1]
                        petition_ele = Element("BusinessListItem")
                        petition_ele.text = title_no_end_punctuation + ": "
                        petition_ele.append(sponsor_ele)
                        output_root.append(petition_ele)

                    # get the sponsor info
                    if business_item_type.text not in (
                        "Adjournment Debate",
                        "Petition",
                    ):
                        op_functions.append_motion_sponosrs(
                            dayItem, output_root, laying_minister_lookup
                        )

                # get the motion text and sponsors. Sponsors are included even when there is no text for PMBs
                if dayItem.findtext("BusinessItemDetail/ItemText", default="") != "":

                    # get the main item text
                    motionText = Element("MotionText")
                    motionText.append(
                        op_functions.process_CDATA(
                            dayItem.findtext("BusinessItemDetail/ItemText", default="")
                        )
                    )
                    output_root.append(motionText)

                # make sure we get any amendments
                op_functions.append_amendments(
                    dayItem, output_root, laying_minister_lookup
                )

                # get relevant documents and notes
                op_functions.notes_relevant_docs(
                    dayItem, output_root, has_children, day_item_is_child
                )

    # get the path to input file
    pwd = path.dirname(path.abspath(input_xml))
    # write out the file
    filename = path.basename(input_xml).replace("as-downloaded-", "").split(".")[0]
    filepath = path.join(pwd, filename)

    # clean up
    op_functions.clean_up_text(output_root)

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
