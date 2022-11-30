#!/usr/bin/env python

# Published 20 May 2022
# https://github.com/hoc-ppu/order-paper-future-business-diff

from pathlib import Path
import webbrowser
import requests
from lxml import etree
from os import path
import os
import re

# Scripts borrowed from the Order Paper production process
# this is the brains of the part 1 operation
import logic.order_paper.get_part1_xml_cmd_v3 as part1_script
# this is the brains of the fba operation
import logic.order_paper.get_fba_xml_cmd_v3 as fba_script
# this is the brains of the announcements operation
import logic.order_paper.get_announcements_xml_cmd_v2 as ann_script
# this is the brains of the questions operation
import logic.order_paper.TransformQuestionsXML_cmd as cmd_version

# GLOBALS

# Order Paper Data Services API key
API_KEY = 'e16ca3cd-8645-4076-aaba-3f1f31028da1'

# Tabled items with date (ie all but Future Business B) endpoint stem
BUSINESS_ENDPOINT_STEM = ('http://services.orderpaper.parliament.uk/'
                          'businessitems/tableditemswithdate.xml')

# EQM endpoint stem
QUESTIONS_ENDPOINT_STEM = ('https://api.eqm.parliament.uk/'
                           'feed/Xml/OrderPaper.xml')

# Path to Temp folder in user's home folder
TEMP_DIR_PATH = str(Path(Path.home(), 'AppData/Local/Temp/').absolute())

# Cache XML in Temp folder in user's home folder
TEMP_FILE_PATH_BUSINESS = f'{TEMP_DIR_PATH}/business_temp.xml'

# Output HTML to Temp folder in user's home folder
OUTPUT_FILE_PATH = f'{TEMP_DIR_PATH}/order_paper_preview.html'

# Output HTML template, we'll populate this later
OUTPUT_HTML_TEMPLATE = '''
<html lang="en">
    <head>
        <meta charset="utf-8">
        <title>Order Paper Future Business diff</title>
        <link rel="stylesheet" href="https://designsystem.parliament.uk/apps/commons-business/v1.0/css/design-system.css">
        <link rel="stylesheet" href="https://designsystem.parliament.uk/apps/commons-business/v1.0/css/businesspapers.css">
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; }}
            .OP-heading-outdent {{ margin-left: -2.5rem; }}
            .unformatted {{ color: #cc0033; }}
        </style>
    </head>
    <body>
        <main id="main-content">
            <article>
                <div class="container-fluid">
                    <div class="block block-page">
                        <div class="row">
                            <div class="col-md-9 js-toc-content">
                                <div class="OP-left-margin">
                                    <div id="content-goes-here" class="section">
                                        <h2 class="OP-heading-outdent">
                                            Order Paper preview
                                        </h2>
                                        <p class="unformatted">
                                            <strong>This is an approximate rendering of Order Paper items.</strong> Some aspects of the Order Paper's layout and content are finialised by PPU at the point of publication. If you have any questions about the limitations of this tool, or notice any issues with the rendering of the information, please contact a member of <a href="https://intranet.parliament.uk/people-offices/offices-departments/commons-departments/chamber-and-participation-team/vote-office1/ppu/" taRGET="_blank">PPU's technology team</a>.
                                        </p>
                                        {CONTENT}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </article>
        </main>
    </body>
</html>
'''

# Generate HTML element for each XML 'node' and return it as a string


def generate_html_element(node) -> str:

    # Map tags from source XML to HTML
    tag_mapping = [
        ['OPHeading1', 'paraBusinessTodayChamberHeading', 'h3'],
        ['OPHeading2', 'paraBusinessSub-SectionHeading', 'h4'],
        ['DebateTimingRubric', 'paraOrderofBusinessItemTiming', 'p'],
        ['Times', 'paraOrderofBusinessItemTiming', 'p'],
        ['BusinessItemHeadingBulleted', 'paraBusinessItemHeading-bulleted', 'p'],
        ['NoteHeading', 'paraNotesTag', 'p'],
        ['NoteText', 'paraNotesText', 'p'],
        ['BusinessItemHeadingNumbered', 'paraBusinessItemHeading', 'p'],
        ['Bulleted', 'paraBusinessItemHeading-bulleted', 'p'],
        ['QuestionRestart', 'paraQuestion', 'p'],
        ['Question', 'paraQuestion', 'p'],
        ['TopicalQuestionRestart', 'paraQuestion', 'p'],
        ['TopicalQuestion', 'paraQuestion', 'p'],
        ['Number', 'number-span', 'span'],
        ['Member', 'charMember', 'span'],
        ['Constit', 'charConstituency', 'span'],
        ['QnText', 'charQuestion', 'span'],
        ['UIN', 'charUIN', 'span'],
        ['MotionSponsor', 'paraMotionSponsor', 'p'],
        ['from_cdata', 'from_cdata', 'span'],
        ['BusinessListItem', 'paraBusinessListItem', 'p'],
        ['PresenterSponsor', 'charPresenterSponsor', 'strong'],
        ['MotionCrossHeading', 'paraOrderofBusinessItemTiming', 'p'],
        ['MinisterialStatement', 'paraMinisterialStatement', 'p'],
        ['SOReference', 'charStandingOrderReference', 'span'],
        ['MotionText', 'paraMotionText', 'p'],
        ['FbaLocation', 'FbaLocation', 'p'],
        ['BusinessItemHeading', 'paraBusinessItemHeading', 'p'],
        ['QuestionTimeing', 'paraFutureBusinessItemHeadingwithTiming', 'p'],
        ['SponsorNotes', 'SponsorNotes', 'span'],
    ]

    # Output HTML element (default is empty)
    html = ''

    # If 'node' has children or text content...
    if (len(node) > 0) or (node.text is not None):

        # Catch-all HTML output (hopefully this will get overwritten in a moment...)
        html = f'<p class="unformatted">{node.text}</p>\n'

        # Loop over 'tag_mapping'...
        for tag in tag_mapping:

            # If the 'tag[0]' matches the tag name of 'node'...
            if tag[0] == node.tag:

                # Open an HTML tag based on the corresponding tagname and class in 'tag'
                html = f'<{tag[2]} class="{tag[1]}">\n'

                # If 'node' has a 'number' attribute, it's part of a numbered list...
                if 'number' in node.attrib:
                    html += f'<span class="number-span"><span class="charBallotNumber">{node.attrib["number"]}</span></span>\n'

                # If the tag name of 'node' is 'QnText' it needs to be followed by a line break...
                if node.tag == 'QnText':
                    html += '<br />'

                # If 'node' has text content...
                if node.text is not None:

                    # Get the text
                    text = node.text

                    # If the tag name of 'node' is 'NoteText' split into new parasgraphs where there's a semi-colon...
                    if node.tag == 'NoteText':
                        text = re.sub(
                            ';', '</p><p class="paraNotesText">', node.text)

                    # Add 'text' to 'html'
                    html += text

                # Loop over any child nodes of 'node'...
                for child_node in node:

                    # Recursively call this function on any child nodes
                    html += generate_html_element(child_node)

                # Close the HTML tag
                html += f'</{tag[2]}>\n'

    return html

# Generate HTML fragment from XML


def generate_html(requested_date) -> str:

    html_fragment = ''

    business_xml = etree.parse(TEMP_FILE_PATH_BUSINESS).getroot()

    business_questions_element = business_xml.find('QUESTIONS')
    if (business_questions_element is not None):
        questions_xml = etree.parse(
            f'{TEMP_DIR_PATH}/for_InDesign_Qs_{requested_date}.xml').getroot()
        business_questions_element_parent = business_questions_element.getparent()
        i = 1
        for node in questions_xml.xpath('/root/*'):
            business_questions_element_parent.insert(business_questions_element_parent.index(
                business_questions_element) + i, node)
            i = i + 1

        print(etree.tostring(business_xml))

    for node in business_xml.xpath('/root/*'):
        html_fragment += generate_html_element(node)

    return html_fragment

# Rename XML files generated by Order Paper scripts (for compatibility with the 'generate_html()' function)


def rename_xml_file(source_file_name_suffix) -> None:

    source_file_name = path.basename(TEMP_FILE_PATH_BUSINESS).split('.')[0]
    source_file_path = path.join(TEMP_DIR_PATH, source_file_name)

    # Delete any existing temp file with the same generic name
    os.remove(TEMP_FILE_PATH_BUSINESS)

    # Rename source temp XML file with generic name so it is compatible with the 'generate_html()' function
    os.rename(path.abspath(source_file_path +
              source_file_name_suffix), TEMP_FILE_PATH_BUSINESS)

# The nuts and bolts of the Order Paper production


def order_paper(requested_date, shopping_list) -> None:

    # We'll populate this as we go...
    html_fragment = ''

    # Loop over 'shopping_list'...
    for requested_data in shopping_list:

        # Build appropriate url for API call
        url = (f'{BUSINESS_ENDPOINT_STEM}'
               f'?key={API_KEY}&fromDate={requested_date}'
               f'&type={requested_data}')

        # If the shopping list item is not 'futurea'...
        if (requested_data != 'futurea'):

            # Limit to querying for a single day's information
            url += (f'&toDate={requested_date}')

        # Get data from the API
        data = requests.get(url)

        # Write data to temporary file
        output_file = open(TEMP_FILE_PATH_BUSINESS, 'wb')
        output_file.write(data.text.encode('utf-8'))
        output_file.close()

        # If the shopping list item is 'effectives'...
        if (requested_data == 'effectives'):

            # Transform the XML into InDesign-friendly format
            part1_script.process_xml(TEMP_FILE_PATH_BUSINESS, requested_date)

            # This is the file name suffix given to the temporary XML file by the above function
            # We'll need this later
            file_name_suffix = '-effectives-for-InDesign.xml'

            # Build URL for another API call, this time to EQM for the day's questions
            url = (f'{QUESTIONS_ENDPOINT_STEM}'
                   f'?sittingDate={requested_date}')

            # Get data from the API
            data = requests.get(url, verify=False)

            # Write data to temporary file
            output_file = open(f'{TEMP_DIR_PATH}/questions.xml', 'wb')
            output_file.write(data.text.encode('utf-8'))
            output_file.close()

            # Transform the XML into InDesign-friendly format
            cmd_version.transform_xml(
                f'{TEMP_DIR_PATH}/questions.xml',
                output_folder=TEMP_DIR_PATH,
                sitting_date=requested_date)

        if (requested_data == 'announcements'):

            # Transform the XML into InDesign-friendly format
            ann_script.process_xml(TEMP_FILE_PATH_BUSINESS, requested_date)

            # This is the file name suffix given to the temporary XML file by the above function
            # We'll need this later
            file_name_suffix = '-announcements-for-InDesign.xml'

        if (requested_data == 'futurea'):

            # Transform the XML into InDesign-friendly format
            fba_script.process_xml(TEMP_FILE_PATH_BUSINESS, requested_date)

            # This is the file name suffix given to the temporary XML file by the above function
            # We'll need this later
            file_name_suffix = '-FBA-for-InDesign.xml'

        # Rename temporary XML files for compatibility with 'generate_html()'
        rename_xml_file(file_name_suffix)

        # Generate HTML fragment based on the InDesign-friendly XML
        html_fragment += generate_html(requested_date)

    # Merge generated HTML fragments into OUTPUT_HTML_TEMPLATE
    output_html = OUTPUT_HTML_TEMPLATE.format(CONTENT=html_fragment)

    # Create/write HTML file
    with open(OUTPUT_FILE_PATH, 'w', encoding='utf-8') as output_file:
        output_file.write(output_html)

    # Open HTML in new browser tab
    webbrowser.get().open(OUTPUT_FILE_PATH, new=2)
