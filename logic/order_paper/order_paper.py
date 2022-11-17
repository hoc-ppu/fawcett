#!/usr/bin/env python

# Published 20 May 2022
# https://github.com/hoc-ppu/order-paper-future-business-diff

from pathlib import Path
from typing import List
import webbrowser
import requests
from lxml import etree
from os import path
import os
import re


# this is the brains of the part 1 operation
import logic.order_paper.get_part1_xml_cmd_v3 as part1_script
# this is the brains of the fba operation
import logic.order_paper.get_fba_xml_cmd_v3 as fba_script
# this is the brains of the announcements operation
import logic.order_paper.get_announcements_xml_cmd_v2 as ann_script
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

TEMP_DIR_PATH = str(Path(Path.home(), 'AppData/Local/Temp/').absolute())

TEMP_FILE_PATH_BUSINESS = f'{TEMP_DIR_PATH}/business_temp.xml'

# Output HTML to Temp folder in user's home folder
OUTPUT_FILE_PATH = str(Path(Path.home(),
                            'AppData/Local/Temp/order_paper_preview.html').absolute())

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


def generate_html_element(node) -> str:

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

    html = ''

    if (len(node) > 0) or (node.text is not None):

        html = f'<p class="unformatted">{node.text}</p>\n'

        for tag in tag_mapping:
            if tag[0] == node.tag:
                html = f'<{tag[2]} class="{tag[1]}">\n'
                if 'number' in node.attrib:
                    html += f'<span class="number-span"><span class="charBallotNumber">{node.attrib["number"]}</span></span>\n'
                if node.tag == 'QnText':
                    html += '<br />'
                if node.text is not None:
                    text = node.text
                    if node.tag == 'NoteText':
                        text = re.sub(
                            ';', '</p><p class="paraNotesText">', node.text)
                    html += text
                for child_node in node:
                    html += generate_html_element(child_node)
                html += f'</{tag[2]}>\n'

    return html


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


def rename_xml_file(file_suffix) -> None:

    pwd = path.dirname(path.abspath(TEMP_FILE_PATH_BUSINESS))
    filename = path.basename(TEMP_FILE_PATH_BUSINESS).split('.')[0]
    filepath = path.join(pwd, filename)
    os.remove(TEMP_FILE_PATH_BUSINESS)
    os.rename(path.abspath(filepath + file_suffix), TEMP_FILE_PATH_BUSINESS)


def order_paper(requested_date, shopping_list) -> None:

    html_fragment = ''

    for requested_data in shopping_list:

        if (requested_data == 'effectives') or (requested_data == 'announcements'):
            url = (f'{BUSINESS_ENDPOINT_STEM}'
                   f'?key={API_KEY}&fromDate={requested_date}'
                   f'&toDate={requested_date}'
                   f'&type={requested_data}')

        if (requested_data == 'futurea'):
            url = (f'{BUSINESS_ENDPOINT_STEM}'
                   f'?key={API_KEY}&fromDate={requested_date}'
                   f'&type={requested_data}')

        data = requests.get(url)

        output_file = open(TEMP_FILE_PATH_BUSINESS, 'wb')
        output_file.write(data.text.encode('utf-8'))
        output_file.close()

        if (requested_data == 'effectives'):
            part1_script.process_xml(TEMP_FILE_PATH_BUSINESS, requested_date)
            file_suffix = '-effectives-for-InDesign.xml'
            url = (f'{QUESTIONS_ENDPOINT_STEM}'
                   f'?sittingDate={requested_date}')
            data = requests.get(url, verify=False)
            output_file = open(f'{TEMP_DIR_PATH}/questions.xml', 'wb')
            output_file.write(data.text.encode('utf-8'))
            output_file.close()
            cmd_version.transform_xml(
                f'{TEMP_DIR_PATH}/questions.xml', output_folder=TEMP_DIR_PATH, sitting_date=requested_date)

        if (requested_data == 'announcements'):
            ann_script.process_xml(TEMP_FILE_PATH_BUSINESS, requested_date)
            file_suffix = '-announcements-for-InDesign.xml'

        if (requested_data == 'futurea'):
            fba_script.process_xml(TEMP_FILE_PATH_BUSINESS, requested_date)
            file_suffix = '-FBA-for-InDesign.xml'

        rename_xml_file(file_suffix)

        html_fragment += generate_html(requested_date)

    output_html = OUTPUT_HTML_TEMPLATE.format(CONTENT=html_fragment)

    # Create/write the file
    with open(OUTPUT_FILE_PATH, 'w', encoding='utf-8') as output_file:
        output_file.write(output_html)

    # Open in browser
    webbrowser.get().open(OUTPUT_FILE_PATH, new=2)

    print('\nAll done: \'order_paper_preview.html\''
          'should have opened in your web browser automatically.')
