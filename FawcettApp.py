#!/usr/bin/env python3

__version__ = '5.0.0'

import argparse
from datetime import datetime, date
import json
from json import JSONDecodeError
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import platform
import re
from socket import timeout
import ssl
import sys
# import subprocess
from tempfile import mkstemp
from typing import Optional, Any
import urllib.request
from urllib.error import HTTPError, URLError
import webbrowser

from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui  # noqa: F401
from lxml import html
from lxml.html.builder import H3, H4, CLASS, P, SPAN, STRONG
from lxml.etree import _Element, iselement
# from lxml.etree import Element

from package.MainWindow_ui import Ui_MainWindow


# default ssl context
CONTEXT = ssl.create_default_context()

NOQ_URI_BASE = 'https://api.eqm.parliament.uk/feed/NoticeOfQuestions.json?preview=true&tabledDate='
MNIS_ANSWERING_BODIES_URI = 'http://data.parliament.uk/membersdataplatform/services/mnis/ReferenceData/AnsweringBodies/'

logger = logging.getLogger('fawcett_app')
logger.setLevel(logging.DEBUG)

LOG_FILE_PATH = Path('logs', os.getlogin(), 'fawcett_app.log').absolute()
LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

#
# Create logger
#
# create file handler which logs even debug messages
fh = RotatingFileHandler(str(LOG_FILE_PATH), mode='a', maxBytes=1024 * 1024)
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.WARNING)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)

#
# warning and error functions. These are redefined later if using GUI.
#
def cmd_warning(msg: str):
    logger.warning(msg)

def cmd_error(msg: str):
    logger.warning(msg)


warning = cmd_warning
error = cmd_error


def main():

    # get today's date as a date object
    today = date.today()

    if len(sys.argv) > 1:
        # do cmd line version
        parser = argparse.ArgumentParser(
            description='Create Questions Tabled On Quick Proof')

        today_str = today.strftime("%Y-%m-%d")

        parser.add_argument('date', type=lambda s: datetime.strptime(s, '%Y-%m-%d'),
                            help=f'Enter the date in the form YYYY-MM-DD. E.g. {today_str}')

        args = parser.parse_args(sys.argv[1:])

        run(args.date)

    else:
        # run the GUI version
        app = QtWidgets.QApplication(sys.argv)

        # window = QtWidgets.QMainWindow()
        window = MainWindow()

        def gui_warning(msg: str):
            cmd_warning(msg)
            QtWidgets.QMessageBox.warning(window, 'Warning', msg)

        def gui_error(msg: str):
            cmd_error(msg)
            QtWidgets.QMessageBox.error(window, 'Warning', msg)

        # redefine global function
        global warning
        warning = gui_warning
        global error
        error = gui_error


        window.show()

        app.exec_()


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, *args, obj=None, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)


        # set the dates to today
        self.dateEdit.setDate(QtCore.QDate.currentDate())

        # create button
        self.create_proof_btn.clicked.connect(self.run_script)

        # log button
        self.logBtn.clicked.connect(self.open_log)


    def run_script(self):

        _date = self.dateEdit.date().toPyDate()

        # QtWidgets.QMessageBox.critical(self, "Error", _date.strftime('%Y-%m-%d'))

        run(_date)

    def open_log(self):
        if platform.system() == 'Darwin':       # macOS
            os.system(f'open "{LOG_FILE_PATH}"')  # a bit hacky, use subprocess instead?

        elif platform.system() == 'Windows':    # Windows
            # os.system(f'start " {str(LOG_FILE_PATH)}"')
            # os.startfile(str(LOG_FILE_PATH))
            webbrowser.open(str(LOG_FILE_PATH))




def run(chosen_date: date):

    if not isinstance(chosen_date, date):
        print(f'{chosen_date}  seems  not to be a valid date. Please try again.')
        return

    eqm_data = json_from_uri(NOQ_URI_BASE + chosen_date.strftime('%Y-%m-%d'))
    if not eqm_data:
        return

    mnis_data = json_from_uri(MNIS_ANSWERING_BODIES_URI)
    if not mnis_data:
        return

    buildUpHTML(eqm_data, mnis_data, chosen_date)



def json_from_uri(uri: str, showerror=True) -> Optional[Any]:
    headers = {'Content-Type': 'application/json'}
    request = urllib.request.Request(uri, headers=headers)
    try:
        response = urllib.request.urlopen(request, context=CONTEXT, timeout=30)
        json_obj = json.load(response)
    except (HTTPError, URLError, timeout, JSONDecodeError) as e:
        if showerror:
            error(f'Error getting data from:\n{uri}\n{e}\n\n'
                  'Make sure you are connected to the parliament network.')
        return None
    else:
        return json_obj


def buildUpHTML(eqm_data, mnis_data, chosen_date: date):

    # list to be populated with answering bodies from MNIS
    answers_list = []

    # put mnis data in array
    if mnis_data:
        answering_bodies = mnis_data.get('AnsweringBodies', {}).get('AnsweringBody', [])
        # build up a list of answering bodies
        for answering_body in answering_bodies:
            answers_list.append(answering_body.get('Target'))

    # variables for totals info
    ordinary_written: int  = 0
    name_day_written: int  = 0
    topical_questions: int = 0
    substantive_Qs: int    = 0

    dateText = ''


    question_html_elements: list[_Element] = []

    # loop through each question block
    for question_block in eqm_data:
        questionBlockDateText = question_block.get('Date')
        # we don't wast today's date in the list
        if questionBlockDateText != chosen_date:
            if questionBlockDateText != dateText:
                dateText = questionBlockDateText
                _date = datetime.strptime(dateText, '%Y-%m-%d')
                formattedDate = _date.strftime('%A %d %B %Y')

                h3 = H3(f'Questions for Answer on {formattedDate}')

                question_html_elements.append(h3)

            question_html_elements.append(H4(question_block.get('Description')))

            # loop through each question
            questions = question_block.get('Questions', [])
            for j, question in enumerate(questions):
                qn_number = j + 1
                # now look for Topical Questions and named days
                question_type = question.get('Type')
                topical = ''
                name_day = ''

                if question_type == 'TOPICAL':
                    topical = 'T'
                elif question_type == 'NAMEDDAY':
                    name_day = ' N'


                # variables for question data
                memberText       = question.get('Member')
                constituencyText = question.get('Constituency')
                qnText           = question.get('Text')
                uinText          = question.get('UIN')
                transferred      = question.get('IsTransfer')
                hasInterest      = question.get('DeclaredInterest')

                if transferred:
                    transferred = '[Transferred] '
                else:
                    transferred = ''
                if hasInterest != '':
                    hasInterest = '[R] '
                else:
                    hasInterest = ''

                # create a container para for the whole question
                questions_item = P(CLASS('questionContainer'),
                                   SPAN(
                                       CLASS('questionNumber'),
                                       f'{topical}{qn_number}{name_day}'),
                                   STRONG(
                                       CLASS('memberName'),
                                       f'{memberText} '),
                                   SPAN(
                                       CLASS('memberConstituency'),
                                       f'({constituencyText}): '),
                                   SPAN(
                                       CLASS('questionText')),
                                   SPAN(
                                       CLASS('uin'),
                                       f'{hasInterest}{transferred}({uinText})'))


                if question_type != 'TOPICAL' or j == 0:
                    old_questionText_span = questions_item.find('.//span[@class="questionText"]')
                    if iselement(old_questionText_span):
                        questionText_span = addYellowHighlight(qnText, question_type, answers_list)
                        questions_item.replace(old_questionText_span, questionText_span)
                        # old_questionText_span.text = qnText


                # append the created question
                question_html_elements.append(questions_item)

                # Running totals of each question type
                if question_type == 'SUBSTANTIVE':
                    substantive_Qs += 1
                elif question_type == 'TOPICAL':
                    topical_questions += 1
                elif question_type == 'NAMEDDAY':
                    name_day_written += 1
                else:
                    ordinary_written += 1

    # read the HTML template
    html_template_file_Path = Path('FawcettApp_template.html')
    print('Attempting to read: ', str(html_template_file_Path.absolute()))
    html_template = html.parse(str(html_template_file_Path.absolute()))
    html_root = html_template.getroot()

    # get the questions dix
    questions_div = html_root.find('body//div[@class="questions"]')
    if not iselement(questions_div):
        error('The template HTML file is missing the following required element:\n'
              '<div class="questions">\nNo output can be created. '
              'Amend the HTML template and try again.')
        return

    # add all the questions and headings
    questions_div.extend(question_html_elements)

    total_writtens = ordinary_written + name_day_written
    total_orals = substantive_Qs + topical_questions
    grand_total = total_writtens + total_orals

    # add questions tabled on heading
    h1 = html_root.find('.//h1[@id="main_title"]')
    if iselement(h1):
        h1.text = f'Questions tabled on {chosen_date.strftime("%A %d %B %Y")}'



    # tuples of xpath to element and total to be inserted into element
    pairs: list[tuple[str, int]] = [
        ('.//*[@id="ordinary"]', ordinary_written),
        ('.//*[@id="nameDay"]', name_day_written),
        ('.//*[@id="totalWrittens"]', total_writtens),
        ('.//*[@id="substantive"]', substantive_Qs),
        ('.//*[@id="topical"]', topical_questions),
        ('.//*[@id="totalOrals"]', total_orals),
        ('.//*[@id="grandTotal"]', grand_total),
    ]

    # populate the totals table
    for xpath, total in pairs:
        html_element = html_root.find(xpath)
        if iselement(html_element):
            html_element.text = str(total)
        else:
            print(f'{xpath} not found')
            print(html_element)


    # create new tempfile
    tempfile, tempfilepath = mkstemp(suffix='.html', prefix='QsTabled')

    # output html to tempfile
    with open(tempfile, 'wb') as file:
        html_template.write(file, encoding='UTF-8', method="html", doctype='<!DOCTYPE html>')

    logger.info(f'Created: {tempfilepath}')
    # try to open in a web browser
    try:
        if os.name == 'posix':
            webbrowser.open('file://' + tempfilepath)
        else:
            webbrowser.open(tempfilepath)
    except Exception:
        warning('The following HTML file was created:\n{tempfilepath}\n'
                'but could not be opened automatically.')


def addYellowHighlight(qn_text: str, question_type, answersList) -> _Element:
    # HIGHLIGHT
    # 1. any repetitions of the initial text of the question marked up e.g.
    # ‘To ask The Chancellor of the Exchequer, To ask The Chancellor of the Exchequer’
    # 2. any instances where the initial word after the first comma is upper cased
    # (it should be lower cased) e.g. ‘To ask The Chancellor of the Exchequer, How many’
    # 3. any absences of the initial text marked up e.g. missing
    # ‘To ask The Chancellor of the Exchequer’
    # 4. any absences of the initial comma marked up e.g.
    # ‘To ask The Chancellor of the Exchequer how many’

    questionHasStart = False
    markerAdded = False

    # This will only work on written questions
    if question_type == 'NAMEDDAY' or question_type == 'ORDINARY':

        for answering_body in answersList:

            # Regular expression to find the 'To ask the...' part of a question
            pattern = answering_body + ','
            reQnStart = re.findall(pattern, qn_text)

            if len(reQnStart) == 1:
                questionHasStart = True
                # Test for capital after initial part of question.
                # e.g. ‘To ask The Chancellor of the Exchequer, How many’
                pattern = answering_body + '(, [A-Z])'

                if re.search(pattern, qn_text):

                    # add yellows
                    qn_text = re.sub(pattern, r'<span class="marker">$1</span>', qn_text)
                    markerAdded = True
                break

        # if the question doesn't start properly
        # (so long as we could determin how questions should start from MNIS)
        if not questionHasStart and len(answersList) > 0:
            qn_text = '<span class="marker">' + qn_text + '</span>'
            markerAdded = True

    # Highlight and questions that do not end in a full stop
    # first make sure question is not already highlighted
    if not markerAdded:
        if qn_text[-1] != '.':
            qn_text = qn_text[:-1] + '<span class="marker">' + qn_text[-1] + '</span>'

    # replace suggested redraft in the qn_text.
    qn_text = qn_text.replace('suggested redraft', '<span class="marker">SUGGESTED REDRAFT</span>')

    html_element = html.fromstring(
        f'<span class="questionText">{qn_text}</span>'
    )
    return html_element


if __name__ == "__main__":
    main()
