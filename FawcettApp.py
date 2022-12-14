#!/usr/bin/env python3

__version__ = "6.0.0"

import argparse
from copy import deepcopy
from datetime import datetime, date
import json
from json import JSONDecodeError
import logging
from logging.handlers import RotatingFileHandler
import os
from os import system as os_system
from os import name as OS_NAME
from pathlib import Path
import platform
import re
from socket import timeout
import ssl
import sys
from tempfile import mkstemp
from typing import Optional, Any
from threading import Thread
import urllib.request
from urllib.error import HTTPError, URLError
import webbrowser

from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui  # noqa: F401
from lxml import html
from lxml.html.builder import H3, H4, CLASS, P, SPAN, STRONG
from lxml.etree import _Element, Element, iselement

# from lxml.etree import Element

# v6: Import v6 version of UI (with tabbed panels)
from package.MainWindow_ui import Ui_MainWindow

# v6: Import order paper scripts
from package.order_paper import order_paper

# print(sys.version)

# default ssl context
CONTEXT = ssl.create_default_context()

NOQ_URI_BASE = (
    "https://api.eqm.parliament.uk/feed/NoticeOfQuestions.json?preview=true&tabledDate="
)
MNIS_ANSWERING_BODIES_URI = "http://data.parliament.uk/membersdataplatform/services/mnis/ReferenceData/AnsweringBodies/"

logger = logging.getLogger("fawcett_app")
logger.setLevel(logging.DEBUG)

LOG_FILE_PATH = Path("logs", os.getlogin(), "fawcett_app.log").absolute()
LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

#
# Create logger
#
# create file handler which logs even debug messages
fh = RotatingFileHandler(str(LOG_FILE_PATH), mode="a", maxBytes=1024 * 1024)
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.WARNING)
# create formatter and add it to the handlers
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
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
    logger.error(msg)


warning = cmd_warning
error = cmd_error


class StartWordInBackground(Thread):
    def __init__(self, path_to_word_file):
        self.path_to_word_file = path_to_word_file
        super().__init__()

    def run(self):
        # fist try opening a copy of the word file using the winword.exe
        # assume winword is in default location
        winword = r'"C:\Program Files (x86)\Microsoft Office\root\Office16\winword.exe"'
        option = " /f "  # supposed to tell word to open a copy
        os_system(winword + option + self.path_to_word_file)


def main():

    # get today's date as a date object
    today = date.today()

    if len(sys.argv) > 1:
        # do cmd line version
        parser = argparse.ArgumentParser(
            description="Create Questions Tabled On Quick Proof"
        )

        today_str = today.strftime("%Y-%m-%d")

        parser.add_argument(
            "date",
            type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
            help=f"Enter the date in the form YYYY-MM-DD. E.g. {today_str}",
        )

        args = parser.parse_args(sys.argv[1:])

        run(args.date)

    else:
        # run the GUI version
        app = QtWidgets.QApplication(sys.argv)

        # window = QtWidgets.QMainWindow()
        window = MainWindow()

        def gui_warning(msg: str):
            cmd_warning(msg)
            QtWidgets.QMessageBox.warning(window, "Warning", msg)

        def gui_error(msg: str):
            cmd_error(msg)
            QtWidgets.QMessageBox.critical(window, "Error", msg)

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

        # set the icon in the Windows taskbar
        if hasattr(sys, "_MEIPASS"):  # if we are using the bundled app

            # when creating the bundled app use --add-data=.\icons\Icon.ico;.
            # the above assumes we have an Icon.ico file in an icons folder
            # logger.info(sys._MEIPASS)

            if platform.system() == "Windows":
                path_to_icon = Path(sys._MEIPASS) / "Icon.ico"  # type: ignore
                self.setWindowIcon(QtGui.QIcon(str(path_to_icon)))

        # set the dates to today
        self.dateEdit.setDate(QtCore.QDate.currentDate())
        self.dateEdit_OP.setDate(QtCore.QDate.currentDate())

        # create buttons
        self.create_proof_btn.clicked.connect(self.run_script)

        # create word button
        self.create_proof_word_btn.clicked.connect(self.run_word_script)
        # v6: Create order paper proof button
        self.create_proof_btn_OP.clicked.connect(self.run_script_op)

        # log button
        self.logBtn.clicked.connect(self.open_log)

    def run_word_script(self):
        _date = self.dateEdit.date().toPyDate()

        run(_date, word=True)

    # v6: Handle click of order papaer proof button
    def run_script_op(self):

        # Get sitting date as python Date object
        _date = self.dateEdit_OP.date().toPyDate()

        # Create 'shopping list' of sections to proof based on checkboxes
        _shopping_list = []

        if self.checkBox_1_OP.isChecked():
            _shopping_list.append("effectives")

        if self.checkBox_2_OP.isChecked():
            _shopping_list.append("announcements")

        if self.checkBox_3_OP.isChecked():
            _shopping_list.append("futurea")

        order_paper(str(_date), _shopping_list)

    def run_script(self):

        _date = self.dateEdit.date().toPyDate()

        # QtWidgets.QMessageBox.critical(self, "Error", _date.strftime('%Y-%m-%d'))

        run(_date)

    def open_log(self):
        if platform.system() == "Darwin":  # macOS
            # a bit hacky, use subprocess instead?
            os.system(f'open "{LOG_FILE_PATH}"')

        elif platform.system() == "Windows":  # Windows
            # os.system(f'start " {str(LOG_FILE_PATH)}"')
            # os.startfile(str(LOG_FILE_PATH))
            webbrowser.open(str(LOG_FILE_PATH))


def run(chosen_date: date, word=False):

    logger.info(f"{word=}")

    if not isinstance(chosen_date, date):
        logger.warning(
            f"{chosen_date}  seems  not to be a valid date. Please try again."
        )
        return

    # testing
    # with open('test-2021-11-25.json', 'r') as f:
    #     eqm_data = json.load(f)
    eqm_data = json_from_uri(NOQ_URI_BASE + chosen_date.strftime("%Y-%m-%d"))
    if not eqm_data:
        return

    mnis_data = json_from_uri(MNIS_ANSWERING_BODIES_URI)
    if not mnis_data:
        return

    html_template = buildUpHTML(eqm_data, mnis_data, chosen_date)

    if word is False:
        suffix = ".html"
    else:
        suffix = ".doc"

    # create new tempfile
    tempfile, tempfilepath = mkstemp(suffix=suffix, prefix="QsTabled")

    # output html to tempfile
    with open(tempfile, "wb") as file:
        html_template.write(
            file, encoding="UTF-8", method="html", doctype="<!DOCTYPE html>"
        )

    logger.info(f"Created: {tempfilepath}")

    if word is False:
        # try to open in a web browser
        try:
            if os.name == "posix":
                webbrowser.open("file://" + tempfilepath)
            else:
                webbrowser.open(tempfilepath)
        except Exception:
            warning(
                f"The following HTML file was created:\n{tempfilepath}\n"
                "but could not be opened automatically."
            )
    else:
        # output an HTML file but pretend it's a word file

        logger.info("Trying to open in Word...")
        open_Word(tempfilepath)
        logger.info("Opened Word")


def open_Word(filepath):
    """
    Attempts to open filepath in Microsoft Word in the background
    """
    # print(str(filepath))
    if OS_NAME == "nt":
        # windows system
        try:
            thread = StartWordInBackground(filepath)
            thread.daemon = True
            thread.start()
        except Exception:
            # if there is any problem with the above just do a gineric `start` and hope for the best
            os_system("start " + filepath)
    else:
        # not a windows system
        os_system("open " + filepath)  # `open` works on macOS, not sure about Linux

def json_from_uri(uri: str, showerror=True) -> Optional[Any]:
    headers = {"Content-Type": "application/json"}
    request = urllib.request.Request(uri, headers=headers)
    try:
        response = urllib.request.urlopen(request, context=CONTEXT, timeout=30)
        json_obj = json.load(response)
    except (HTTPError, URLError, timeout, JSONDecodeError) as e:
        if showerror:
            error(
                f"Error getting data from:\n{uri}\n{e}\n\n"
                "Make sure you are connected to the parliament network."
            )
        return None
    else:
        return json_obj


def buildUpHTML(eqm_data, mnis_data, chosen_date: date):

    # list to be populated with answering bodies from MNIS
    answers_dict: dict[str, str] = {}

    # put mnis data in array
    if mnis_data:
        answering_bodies = mnis_data.get("AnsweringBodies", {}).get("AnsweringBody", [])
        # build up a list of answering bodies
        for answering_body in answering_bodies:
            ab_name = answering_body.get("Name")
            target = answering_body.get("Target")
            answers_dict[ab_name] = target

    # variables for totals info
    ordinary_written: int = 0
    name_day_written: int = 0
    topical_questions: int = 0
    substantive_Qs: int = 0

    dateText = ""

    question_html_elements: list[_Element] = []

    # loop through each question block
    for question_block in eqm_data:
        questionBlockDateText = question_block.get("Date")
        # we don't wast today's date in the list
        if questionBlockDateText != chosen_date:
            if questionBlockDateText != dateText:
                dateText = questionBlockDateText
                _date = datetime.strptime(dateText, "%Y-%m-%d")
                formattedDate = _date.strftime("%A %d %B %Y")

                h3 = H3(f"Questions for Answer on {formattedDate}")

                question_html_elements.append(h3)

            question_html_elements.append(H4(question_block.get("Description", "")))

            # loop through each question
            questions = question_block.get("Questions", [])
            for j, question in enumerate(questions):
                qn_number = j + 1
                # now look for Topical Questions and named days
                question_type = question.get("Type")
                topical = ""
                name_day = ""

                if question_type == "TOPICAL":
                    topical = "T"
                elif question_type == "NAMEDDAY":
                    name_day = " N"

                # variables for question data
                memberText = question.get("Member")
                constituencyText = question.get("Constituency")
                qnText = question.get("Text")
                uinText = question.get("UIN")
                transferred = question.get("IsTransfer")
                hasInterest = question.get("DeclaredInterest")
                answering_body = question.get("AnsweringBody", "")

                if transferred:
                    transferred = "[Transferred] "
                else:
                    transferred = ""
                if hasInterest != "":
                    hasInterest = "[R] "
                else:
                    hasInterest = ""

                # create a container para for the whole question
                questions_item = P(
                    CLASS("questionContainer"),
                    SPAN(
                        CLASS("questionNumber"), f"{topical}{qn_number}{name_day} "
                    ),  # space at end for word version
                    STRONG(CLASS("memberName"), f"{memberText} "),
                    SPAN(CLASS("memberConstituency"), f"({constituencyText}): "),
                )

                qn_text_ele = SPAN(CLASS("questionText"))
                # qn_text_ele.set('spellcheck', 'true')
                # qn_text_ele.set('contenteditable', '')
                qn_text_ele.text = qnText

                if question_type != "TOPICAL" or j == 0:

                    qn_text_ele_copy = deepcopy(qn_text_ele)

                    try:
                        addHighlights(
                            qn_text_ele, answering_body, question_type, answers_dict
                        )
                        # questionText_span = addYellowHighlight(qnText, question_type, answers_dict)
                        # questions_item.replace(old_questionText_span, questionText_span)
                        # old_questionText_span.text = qnText
                    except Exception as e:
                        qn_text_ele = qn_text_ele_copy
                        error(str(e))

                uin_ele = SPAN(CLASS("uin"), f"{hasInterest}{transferred}({uinText})")

                questions_item.extend([qn_text_ele, uin_ele])

                # append the created question
                question_html_elements.append(questions_item)

                # Running totals of each question type
                if question_type == "SUBSTANTIVE":
                    substantive_Qs += 1
                elif question_type == "TOPICAL":
                    topical_questions += 1
                elif question_type == "NAMEDDAY":
                    name_day_written += 1
                else:
                    ordinary_written += 1

    # read the HTML template
    html_template_file_Path = Path(__file__).with_name("FawcettApp_template.html")
    if hasattr(sys, "executable") and hasattr(sys, "_MEIPASS"):
        # only here if using the bundled version
        html_template_file_Path = Path(sys.executable).with_name(
            "FawcettApp_template.html"
        )
    try:
        html_template_file_Path = html_template_file_Path.absolute().resolve(
            strict=True
        )
    except Exception:
        error(
            "An HTML template file must be present in the same folder as this program.\n"
            "Specifically, the following file must be present:\n"
            f"{html_template_file_Path.absolute().resolve(strict=False)}"
        )
        return

    logger.info(f"Attempting to read: {html_template_file_Path}")
    try:
        html_template = html.parse(str(html_template_file_Path))
    except Exception as e:
        error(
            "An error occurred while trying to read the following file\n"
            + str(html_template_file_Path)
            + f"\n{e}\nCan not continue"
        )
        return
    html_root = html_template.getroot()

    # get the questions div
    questions_div = html_root.find('body//div[@class="questions"]')
    if not iselement(questions_div):
        error(
            "The template HTML file is missing the following required element:\n"
            '<div class="questions">\nNo output can be created. '
            "Amend the HTML template and try again."
        )
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
            logger.warning(f"{xpath} not found")
            logger.warning(str(html_element))

    return html_template


def addHighlights(
    qn_ele: _Element,
    q_answering_body: str,
    question_type: str,
    answers_dict: dict[str, str],
) -> None:

    # HIGHLIGHT IN YELLOW
    # 1. any repetitions of the initial text of the question marked up e.g.
    # ‘To ask The Chancellor of the Exchequer, To ask The Chancellor of the Exchequer’
    # 2. any instances where the initial word after the first comma is upper cased
    # (it should be lower cased) e.g. ‘To ask The Chancellor of the Exchequer, How many’
    # 3. any absences of the initial text marked up e.g. missing
    # ‘To ask The Chancellor of the Exchequer’
    # 4. any absences of the initial comma marked up e.g.
    # ‘To ask The Chancellor of the Exchequer how many’

    # HIGHLIGHT IN PINK
    # where To ask The... does not match the answering body

    # sometimes the answering_body does not match the to ask the text
    # here is what paul had to say about it:
    # - occasionally we change the department a question is directed to but forget to change the title in the question or vice versa
    # The heading does not show up in the app but I wonder whether the intro ‘To ask the ….’ could get highlighted (in a different colour to yellow) if it does not correspond with the department it has been allocated to.

    if not qn_ele.text:
        # we   wont do anything if there is no text
        return

    qn_text = qn_ele.text
    # delete the text
    qn_ele.text = ""

    # This will only work on written questions
    if question_type != "NAMEDDAY" and question_type != "ORDINARY":
        return

    '<span class="marker" data-toggle="tooltip" title="More than one space">&#160;&#160;</span>'

    marker_tamplate = '<span class="marker">{text}</span>'
    marker_with_pop_template = '<span class="marker" data-toggle="tooltip" title="{tool_tip_title}">{text}</span>'
    pink_maker_template = '<span class="marker-pink" data-toggle="tooltip" title="{tool_tip_title}">{text}</span>'

    strings = []

    target_not_found = False

    # pink heighlight first
    expected_target = answers_dict.get(q_answering_body, "")
    to_ask = f"To ask {expected_target}"
    if expected_target and qn_text.startswith(to_ask):
        strings.append(to_ask)

        # remove this now
        qn_text = re.sub(f"^{to_ask}", "", qn_text)
    else:
        # not proper so we'll highlight in pink
        # search for the (wrong) target used
        for target in answers_dict.values():
            to_ask = f"To ask {target}"
            if qn_text.startswith(to_ask):
                qn_text = re.sub(f"^{to_ask}", "", qn_text)

                pink_marker = pink_maker_template.format(
                    tool_tip_title=f"Expected {expected_target}", text=to_ask
                )

                strings.append(pink_marker)

                break
        else:  # loop exited normally i.e. didn't break
            # we need to add something here as the question doesn't
            # start with a target
            target_not_found = True
            if len(qn_text) > 6:
                first_chars = qn_text[0:6]
                qn_text = qn_text[6:]
            else:
                first_chars = qn_text[0]
                qn_text = qn_text[1:]
            pink_marker = pink_maker_template.format(
                tool_tip_title=f"Expected {expected_target}", text=first_chars
            )

            strings.append(pink_marker)

    if qn_text:  # if there is any qn txt left

        # match_obj = re.search(r'^, ?[A-Z0-9]', qn_text)
        match_obj = re.search(r"^,", qn_text)
        if not match_obj and not target_not_found:
            first_char = qn_text[0]
            qn_text = qn_text[1:]

            yellow_marker = marker_with_pop_template.format(
                tool_tip_title="Expected comma", text=first_char
            )

            strings.append(yellow_marker)

    if qn_text:
        # now do several replaces.
        # pattern = re.compile( )
        srf = "suggested redraft"
        spaces = r"\s\s+"
        splits = re.split(f"({srf}|{spaces})", qn_text, re.IGNORECASE)

        for string in splits:
            if re.fullmatch(srf, string, re.IGNORECASE):
                marker = marker_tamplate.format(text=string.upper())
                strings.append(marker)
            elif re.fullmatch(spaces, string):
                marker = marker_with_pop_template.format(
                    text="&nbsp;&nbsp;", tool_tip_title="More than one space"
                )
                strings.append(marker)
            else:
                strings.append(string)

    # join the strings
    q_inner = "".join(strings)

    if q_inner[-1] != ".":
        marker = marker_with_pop_template.format(
            text=q_inner[-1], tool_tip_title="Expected full stop"
        )
        q_inner = q_inner[:-1] + marker

    temp_element = html.fromstring(f'<span class="temporary">{q_inner}</span>')

    qn_ele.append(temp_element)
    # print(html.tostring(qn_ele))
    temp_element.drop_tag()


if __name__ == "__main__":
    main()
