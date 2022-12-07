#!/usr/local/bin/python3

# module needed to parse command line arguments
import sys
# stuff needed for working with file paths
from os import path
import datetime

# stuff needed for parsing and manipulating XML
# This moduel does not come with python and needs to be installed with pip e.g. pip install lxml
from lxml import etree

# some variables used throughout
file_name_start = 'for_InDesign_Qs'
fileextension = '.xml'


def transform_xml(inputfile, output_folder=None, sitting_date=None):
    # convert the sitting_date str into a datatime.date
    if sitting_date:
        try:
            sitting_date_obj = datetime.datetime.strptime(
                sitting_date, '%Y-%m-%d')
            date_formatted = sitting_date_obj.strftime('%A %d %B')
            print(date_formatted)
        except (ValueError, TypeError):
            date_formatted = ''
    # parse and build up a tree for the input file
    input_root = etree.parse(inputfile).getroot()  # LXML element object for the root
    # create an output root element
    output_root = etree.Element('root')

    # get all the TargetGroup elements as an iterable
    target_groups = input_root.xpath('//TargetGroup')

    for target_group in target_groups:
        # find the target head for each group
        target_head = target_group.find('TargetHead')
        # add timeing info to the output if exits in the input
        if len(target_group.xpath('./Time')) != 0:
            times_ele = etree.SubElement(output_root, 'Times')
            times_ele.text = 'At {}'.format(
                target_group.findtext('Time', default='')
                .replace(' ', '')
                .replace(':', '.')
                .replace('12.00pm', '12 noon')
            )
        # create an element for the bulleted questions title
        bullet_tag = etree.SubElement(output_root, 'Bulleted')

        # find all the questions in this target group and store them in a list
        questions = target_group.findall('OralQn')
        # default question tag
        Question_tag_name = 'Question'
        # default question number prefix
        number_prefix = ''
        # ordinary oral questions
        if target_head.get('IsTopical') == 'N' and target_head.text != 'the Prime Minister':
            bullet_tag.text = 'Oral Questions to ' + target_head.text
            Question_tag_name = 'Question'
            number_prefix = ''

        # topical questions
        elif target_head.get('IsTopical') == 'Y':
            # add the questions to bullet point
            bullet_tag.text = 'Topical Questions to ' + target_head.text
            Question_tag_name = 'TopicalQuestion'
            number_prefix = 'T'

        # Prime Ministers Questions
        elif target_head.get('IsTopical') == 'N' and target_head.text == 'the Prime Minister':
            # add the questions to bullet point
            bullet_tag.text = 'Oral Questions to the Prime Minister'
            Question_tag_name = 'PMQ'
            number_prefix = 'Q'

        else:
            print('Error: check the input file contains TargetHead elements and that these '
                  'elements all have the attribute "IsTopical" and that the value of the '
                  'IsTopical attribute is either an "Y" or an "N" and if there are PMQs that '
                  'the text of the TargetHead element is "the Prime Minister".')
            exit()
        # engagements text printed
        engagements_printed = False
        # for i in range(len(questions)):
        for i, question in enumerate(questions):
            # make sure questions start at 1
            if i == 0:
                if Question_tag_name != 'PMQ':
                    restart = 'Restart'
            else:
                restart = ''
            # create different Question parent element depending on type of q
            Question_Element     = etree.SubElement(output_root, Question_tag_name + restart)
            # create child elements needed
            Member_Element       = etree.SubElement(Question_Element, 'Member')
            Constituency_Element = etree.SubElement(Question_Element, 'Constit')
            qn_text_Element      = etree.SubElement(Question_Element, 'QnText')
            uin_Element          = etree.SubElement(Question_Element, 'UIN')

            # put in the question number in an attribute. This is not necessary for InDesign.
            Question_Element.set('number', number_prefix + str(i + 1))
            # build up member name element from constituent parts
            member_Title_text  = question.findtext('Member/Title', default='').strip()
            member_Fnames_text = question.findtext('Member/Fnames', default='').strip()
            member_Sname_text  = question.findtext('Member/Sname', default='').strip()
            Member_Element.text = '{} {} {}'.format(
                member_Title_text, member_Fnames_text,
                member_Sname_text
            ).strip()  # strip start space if no title

            # has the question got an associated relevant interest

            relevant_interest = question.find('QnRubric').get('RID', default='')
            # if the RID attribute is anything other than 'N' - assume there is an interest
            if relevant_interest != 'N':
                relevant_interest = '[R] '
            else:
                relevant_interest = ''


            # constituency element and UIN
            Constituency_Element.text = ' ({})'.format(
                question.findtext('Member/Constit', default='').strip())
            uin_Element.text = ' {}({})'.format(
                relevant_interest,
                question.findtext('UIN', default='').strip())
            # get the QnText element from the input question
            qn_text = question.find('QnText')

            Constituency_Element.tail = '\u2028'
            qn_text_Element.text = qn_text.text.strip()
            if engagements_printed is False and qn_text.text and qn_text.text.strip().lower() in (
                    f'If she will list her official engagements for {date_formatted}.'.lower(),
                    f'If he will list his official engagements for {date_formatted}.'.lower()):
                # When doing PMQs, the text `If she/he will list his/her official engagements for [date]`
                # must appear exactly once. Unfortunately, if the first question is substantive (i.e. something other
                # then the engagements text) then the XML (from the API) will be wrong. The first instance fo the
                # engagements text should always have the PrintText attribute set to `Y` but unfortunately it doesn't.
                # We will get round that here.
                engagements_printed = True
            elif qn_text.get('PrintText') != 'Y':
                Constituency_Element.tail = None
                qn_text_Element.text = None


    # loop through each top level element in output_root and a new line to tail
    # this is to allow InDesign to put new paragraphs in
    for element in output_root:
        if element.tail is not None:
            element.tail += '\n'
        else:
            element.tail = '\n'

    # output the XML
    if output_folder is None:
        # get the path to input file
        output_folder = path.dirname(path.abspath(inputfile))
    if sitting_date:
        filename = '{}_{}{}'.format(file_name_start, sitting_date, fileextension)
    else:
        filename = '{}{}'.format(file_name_start, fileextension)
    filepath = path.join(output_folder, filename)
    # write out the file
    et = etree.ElementTree(output_root)
    try:
        et.write(filepath)  # , pretty_print=True
        print('\nOutput, transformed XML is located at: \n', filepath)
    except:
        # make sure it works even if we don't have permission to modify the file
        et.write(filename)
        print('\nOutput, transformed XML is located at: \n', path.abspath(filename))


def main():
    if len(sys.argv) != 2:
        print("\nThis script takes 1 argument.\n",
              "1:\tthe path to the file you wish to process.\n",)
        exit()

    infilename = sys.argv[1]
    print('Input file is located at: ' + path.abspath(infilename))
    transform_xml(infilename)
    print('\nAll Done Chum!')


if __name__ == "__main__": main()
