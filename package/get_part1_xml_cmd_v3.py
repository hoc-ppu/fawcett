#!/usr/bin/env python3

# standard library imports
import sys
from typing import List
from os import path

# module for working with XML
from lxml import etree
from lxml.etree import Element
from lxml.etree import _Element
from lxml.etree import SubElement

# for getting files form urls
import urllib.request
import urllib.error
import ssl


# import utility functions
try:
    import get_op_utility_functions2 as op_functions
except ImportError:
    import package.get_op_utility_functions2 as op_functions


fileextension = "-effectives-for-InDesign.xml"

WS_SORT_ORDER = [
    "Attorney General",
    "Secretary of State for Business, Energy and Industrial Strategy",
    "Minister for the Cabinet Office",
    "The Chancellor of the Exchequer",
    "Secretary of State for Defence",
    "Secretary of State for Digital, Culture, Media and Sport",
    "Deputy Prime Minister",
    "Secretary of State for Education",
    "Secretary of State for Energy and Climate Change",
    "Secretary of State for Environment, Food and Rural Affairs",
    "Secretary of State for Exiting the European Union",
    "Secretary of State for Foreign and Commonwealth Affairs",
    "Secretary of State for Health and Social Care",
    "Secretary of State for the Home Department",
    "Secretary of State for Housing, Communities and Local Government",
    "House of Commons Commission",
    "Secretary of State for International Development",
    "Secretary of State for International Trade",
    "Secretary of State for Justice",
    "Leader of the House",
    "Secretary of State for Northern Ireland",
    "Prime Minister",
    "Secretary of State for Scotland",
    "Speaker's Committee on the Electoral Commission",
    "Speaker's Committee for the Independent Parliamentary Standards Authority",
    "Secretary of State for Transport",
    "Secretary of State for Wales",
    "Minister for Women and Equalities",
    "Secretary of State for Work and Pensions",
]


def main():
    if len(sys.argv) != 3:
        print(
            "\nThis script takes 2 arguments.\n",
            "1:\tthe url for the XML you wish to process.\n",
            "2:\tthe date for the OP you want to make in the form YYYY-MM-DD, i.e.'2016-09-12'\n",
        )
        exit()

    process_xml(sys.argv[1], sys.argv[2])


def process_xml(input_xml, input_date):

    laying_minister_lookup = {}
    laying_minister_lookup = op_functions.get_mnis_data(laying_minister_lookup)

    # sections included in this script (Written Statements will be sorted separatly)
    section_names = ("Chamber", "Westminster Hall", "Deferred Divisions")
    input_root = etree.parse(str(input_xml)).getroot()

    op_functions.dropns(input_root)

    # get the day we are interested
    xpath = f'Days/Day/Date[text()[contains(.,"{input_date}")]]'
    date_elements: List[_Element]
    date_elements = input_root.xpath(xpath)  # type: ignore
    if len(date_elements) != 1:
        input(
            "Error:\tCan't seem to find the date you are after."
            " Check it appears in the XML, Press any key to exit."
        )
        exit()
    else:
        day_element = date_elements[0].getparent()
        # print(day_element[1].tag)
    # build up output tree
    output_root = Element("root")

    # create a variable to store a reference to the heading as where
    # a business item falls determins its style
    last_gray_heading_text = ""

    # question placeholder added
    questions_done = False
    # weather or not the no debate and (Standing Order No 57)
    presentation_of_bills_nodebate_so = False

    # get all the sections in this day
    sections: List[_Element]
    sections = day_element.xpath("./Sections/Section")  # type: ignore

    # loop through all the sections
    for section in sections:

        # get the section name from the XML
        section_name = section.findtext("Name", default="")
        # skip any sections that are not in the section names defined above
        if section_name not in section_names:
            continue

        # stuff for the chamber section
        if section_name == "Chamber":
            # output root Add element for Business Today Chamber
            SubElement(output_root, "OPHeading1").text = "Business Today: Chamber"

            # default if there is no prayers in input XML
            prayers_e = SubElement(output_root, "DebateTimingRubric")
            prayers_e.text = "XX.XXam/pm Prayers"
            SubElement(output_root, "DebateTimingRubric").text = "Followed by"

            # section.find will return the first match which should be the prayers
            dayItem_prayers = section.find("./DayItems/DayItem")
            # fist check if the first element is Prayers
            if (
                dayItem_prayers is not None
                and dayItem_prayers.find("Title").text.upper().strip() == "PRAYERS"
            ):
                prayer_time = dayItem_prayers.findtext("BusinessItemDetail/Time")
                prayer_time = op_functions.format_time(prayer_time)

                prayers_e.text = f"{prayer_time} Prayers"

                # delete the day item
                dayItem_prayers.getparent().remove(dayItem_prayers)

        elif section_name == "Deferred Divisions":
            # do special stuff for Deferred Divisions
            SubElement(output_root, "OPHeading1").text = "Deferred Divisions"

        elif section_name == "Westminster Hall":
            SubElement(
                output_root, "OPHeading1"
            ).text = "Business Today: Westminster Hall"
            # do special stuff for westminster hall

        # get all the DayItem in the section
        dayItem_all: List[_Element]
        dayItem_all = section.xpath(".//DayItem")  # type: ignore

        for dayItem in dayItem_all:
            # get the day item type or None
            day_item_type = dayItem.find("DayItemType")
            # we need the day item type to not be None
            # so if it in None we will just skip over
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
            # get the title_text if it exists
            day_item_title_text = dayItem.findtext("Title", default="")

            # first test to see if the day item is a heading
            if day_item_type.text == "SectionDayDivider":
                # Set up the last gray heading variable.
                # This is because elements take different styles based on wich section they are in
                last_gray_heading_text = day_item_title_text.upper()

                # now add any section day divider title to the XML for InDesign
                SubElement(output_root, "OPHeading2").text = day_item_title_text
                # also add any notes
                if dayItem.find("Notes") is not None:
                    SubElement(
                        output_root, "DebateTimingRubric"
                    ).text = dayItem.findtext("Notes", default="")

                # if urgent questions and statements add time
                if (
                    title is not None
                    and day_item_title_text.upper() == "URGENT QUESTIONS AND STATEMENTS"
                ):
                    time_in_op_form = op_functions.format_time(
                        dayItem.getnext().findtext(
                            "BusinessItemDetail/Time", default=""
                        )
                    )
                    if time_in_op_form is not None:
                        SubElement(
                            output_root, "DebateTimingRubric"
                        ).text = time_in_op_form

            # do things relating to the chamber section first
            if section_name == "Chamber":
                # if this is a business item
                if day_item_type.text == "BusinessItem":
                    # print(title_above_text(dayItem).upper())
                    if last_gray_heading_text == "BUSINESS OF THE DAY":
                        if day_item_is_child is False:
                            SubElement(
                                output_root, "BusinessItemHeadingNumbered"
                            ).text = day_item_title_text
                        else:
                            SubElement(
                                output_root, "Bulleted"
                            ).text = day_item_title_text

                        # next get timing and so reference
                        op_functions.append_timing_so(output_root, dayItem)

                        # get the sponsor info
                        op_functions.append_motion_sponosrs(
                            dayItem, output_root, laying_minister_lookup
                        )

                        # get the main item text
                        motionText = Element("MotionText")
                        motionText.append(
                            op_functions.process_CDATA(
                                dayItem.findtext(
                                    "BusinessItemDetail/ItemText", default=""
                                )
                            )
                        )
                        output_root.append(motionText)

                        # make sure we get any amendments
                        op_functions.append_amendments(
                            dayItem, output_root, laying_minister_lookup
                        )
                        # add Relevant Documents
                        op_functions.notes_relevant_docs(
                            dayItem, output_root, has_children, day_item_is_child
                        )

                    # if questions add a place holder xml element to add the xml from the question system
                    elif last_gray_heading_text == "QUESTIONS":
                        if questions_done is False:
                            questions_element = Element("QUESTIONS")
                            questions_element.tail = "\n"
                            output_root.append(questions_element)
                            questions_done = True
                    elif last_gray_heading_text == "PRESENTATION OF BILLS":
                        # only add the so and 'No debate (Standing Order No. 57)' once
                        if presentation_of_bills_nodebate_so is False:
                            op_functions.append_timing_so(output_root, dayItem)
                            # check the above line to see if it is (Standing Order No. 57). if it is then add No debate before
                            if (
                                output_root[-1].find("SOReference") is not None
                                and output_root[-1].find("SOReference").text
                                == "(Standing Order No. 57)"
                            ):
                                output_root[-1].text = "No debate "
                                presentation_of_bills_nodebate_so = True
                        if day_item_title_text.upper().strip() != "NO TITLE NEEDED":
                            SubElement(
                                output_root, "BusinessItemHeadingBulleted"
                            ).text = day_item_title_text

                        # make sure we get announcement stuff
                        businessItemType = dayItem.find(
                            "BusinessItemDetail/BusinessItemType"
                        )
                        # get the sponsor info
                        op_functions.append_motion_sponosrs(
                            dayItem, output_root, laying_minister_lookup
                        )
                        if businessItemType is not None:
                            motionText = Element("MotionText")
                            motionText.append(
                                op_functions.process_CDATA(
                                    dayItem.findtext(
                                        "BusinessItemDetail/ItemText", default=""
                                    )
                                )
                            )
                            output_root.append(motionText)
                            # add notes
                            # add Relevant Documents
                            op_functions.notes_relevant_docs(
                                dayItem, output_root, has_children, day_item_is_child
                            )

                    elif (
                        last_gray_heading_text == "ADJOURNMENT DEBATE"
                        or last_gray_heading_text == "PRESENTATION OF PUBLIC PETITIONS"
                    ):
                        op_functions.append_timing_so(output_root, dayItem)
                        # for public petitions add No debate of decision before SO 153.
                        if (
                            output_root[-1].find("SOReference") is not None
                            and output_root[-1].find("SOReference").text
                            == "(Standing Order No. 153)"
                        ):
                            output_root[-1].text = "No debate or decision "
                        bus_list_item = SubElement(output_root, "BusinessListItem")
                        bus_list_item.text = day_item_title_text + ": "

                        # also need to append the sponsor
                        op_functions.append_presenter_sponsor(dayItem, bus_list_item)
                    else:
                        if day_item_title_text.upper().strip() != "NO TITLE NEEDED":
                            SubElement(
                                output_root, "BusinessItemHeadingBulleted"
                            ).text = day_item_title_text

                        op_functions.append_timing_so(output_root, dayItem)
                        # make sure we get announcement stuff
                        businessItemType = dayItem.find(
                            "BusinessItemDetail/BusinessItemType"
                        )
                        # get the sponsor info
                        op_functions.append_motion_sponosrs(
                            dayItem, output_root, laying_minister_lookup
                        )
                        if businessItemType is not None:
                            motionText = Element("MotionText")
                            motionText.append(
                                op_functions.process_CDATA(
                                    dayItem.findtext(
                                        "BusinessItemDetail/ItemText", default=""
                                    )
                                )
                            )
                            output_root.append(motionText)
                            # add Relevant Documents
                            op_functions.notes_relevant_docs(
                                dayItem, output_root, has_children, day_item_is_child
                            )

            elif section_name == "Deferred Divisions":
                if day_item_type.text == "BusinessItem":
                    SubElement(
                        output_root, "BusinessItemHeadingBulleted"
                    ).text = day_item_title_text

                    op_functions.append_motion_sponosrs(
                        dayItem, output_root, laying_minister_lookup
                    )
                    motionText = SubElement(output_root, "MotionText")
                    motionText.append(
                        op_functions.process_CDATA(
                            dayItem.findtext("BusinessItemDetail/ItemText", default="")
                        )
                    )
                    op_functions.notes_relevant_docs(
                        dayItem, output_root, has_children, day_item_is_child
                    )

            # stuff for the westminster hall section
            elif section_name == "Westminster Hall":

                if day_item_type.text == "BusinessItem":

                    time_in_op_form = op_functions.format_time(
                        dayItem.findtext("BusinessItemDetail/Time", default="")
                    )
                    if time_in_op_form is not None:
                        SubElement(
                            output_root, "DebateTimingRubric"
                        ).text = time_in_op_form

                    # Very annoyingly, some users put westminster hall items in as adjournment
                    # debates while others put them in as motions. Further, when motions are
                    # entered sometimes the title mathces the ItemText ane other times it doesnt.
                    # when the westminster hall item is a motion use the motion text when it is
                    # an adjournment debate use the title
                    business_list_item = SubElement(output_root, "BusinessListItem")
                    if (
                        dayItem.findtext(
                            "BusinessItemDetail/BusinessItemType", default=""
                        )
                        == "Motion"
                    ):

                        motion_text_cdata = op_functions.process_CDATA(
                            dayItem.findtext("BusinessItemDetail/ItemText", default="")
                        )
                        if motion_text_cdata.text:
                            # use the motion text
                            business_list_item.text = motion_text_cdata.text + ": "
                        else:
                            # use motion title
                            business_list_item.text = day_item_title_text + ": "
                    # else we probably have an announcement section
                    else:
                        business_list_item.text = day_item_title_text + ": "

                    # also need to append the sponsor
                    op_functions.append_presenter_sponsor(dayItem, business_list_item)

                    # get relevant documents and notes
                    op_functions.notes_relevant_docs(
                        dayItem, output_root, has_children, day_item_is_child
                    )

    # get the witten statements section
    xpath = './Sections/Section[Name="Written Statements"]/DayItems/DayItem'
    written_s_day_items = day_element.xpath(xpath)

    # get all written statement day items
    if len(written_s_day_items) > 1:
        # the first day item will be `STATEMENTS TO BE MADE TODAY` and we don't want that on its own.
        sort_and_append_written_statemetns(written_s_day_items, output_root)

    # loop through output
    # replace any non breaking spaces with ordinary spaces
    # replace single quotes with double quotes
    op_functions.clean_up_text(output_root)
    # op_functions.

    # get the path to input file
    pwd = path.dirname(path.abspath(input_xml))
    # write out the file
    filename = path.basename(input_xml).replace("as-downloaded-", "").split(".")[0]
    filepath = path.join(pwd, filename)

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


def sort_and_append_written_statemetns(day_items, output_root):
    # we need to get Answering bodies information from MNIS
    url = "http://data.parliament.uk/membersdataplatform/services/mnis/ReferenceData/AnsweringBodies/"
    # ignore the ssl certificate
    context = ssl._create_unverified_context()

    answering_bodies_lookup = {}
    try:
        response = urllib.request.urlopen(url, context=context)
    except urllib.error.HTTPError as e:
        # 404 and other HTTP errors will be caught here.
        print(
            "WARNING: There is a error in getting the written statement names from MNIS\n"
            + "\tCheck the following URL is working, {}\n".format(url)
            +
            # actually output the error
            "\t{}".format(e)
        )
    else:
        mnis_root = etree.parse(response).getroot()

        for answering_body in mnis_root.xpath("/AnsweringBodies/AnsweringBody"):
            short_name = answering_body.findtext("ShortName").strip()
            target = answering_body.findtext("Target").strip()
            answering_bodies_lookup[short_name] = target

    SubElement(output_root, "OPHeading1").text = "Written Statements"

    # this will usually be `STATEMENTS TO BE MADE TODAY`
    SubElement(output_root, "OPHeading2").text = f"{day_items[0].findtext('Title')}"

    # create written statements object
    statements = {}
    for day_item in day_items[1:]:
        title = day_item.findtext("Title")
        answering_body_name = day_item.findtext("BusinessItemDetail/AnsweringBodyName")
        if answering_body_name:
            answering_body_name = answering_body_name.strip()
            # some answering bodies should be left alone...
            leave_alone = (
                "Speaker's Committee on the Electoral Commission",
                "Speaker's Committee for the Independent Parliamentary Standards Authority",
                "House of Commons Commission",
            )
            if answering_body_name not in leave_alone:
                # replace the answering body name as provided by the portal with the `Target` as provided by mnis
                answering_body_name = answering_bodies_lookup.get(
                    answering_body_name, answering_body_name
                )
                # We do not want `the ` at the begining except for The Chancellor of the Exchequer
                if answering_body_name[0:4] == "the ":
                    answering_body_name = answering_body_name[4:].replace(
                        "Chancellor of the Exchequer", "The Chancellor of the Exchequer"
                    )

            statements.setdefault(answering_body_name, []).append(title)

    for key in sorted(statements.keys(), key=statement_sort):
        SubElement(output_root, "MotionCrossHeading").text = f"{key}"
        for item in sorted(statements[key]):
            SubElement(
                output_root,
                "MinisterialStatement",
            ).text = f"{item}"

    # remember to add a static note to the bottom on written statements
    SubElement(output_root, "NoteHeading").text = "Notes:"
    SubElement(output_root, "NoteText").text = (
        "Texts of Written Statements are available from the Vote Office and on the internet at "
        "https://questions-statements.parliament.uk/ ."
    )


def statement_sort(key):
    try:
        return WS_SORT_ORDER.index(key)
    except ValueError:
        return -2


if __name__ == "__main__":
    main()
