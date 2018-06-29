#!/usr/bin/env python

# Upload files named on ARGV as Slack emoji.
# https://github.com/smashwilson/slack-emojinator

from __future__ import print_function
import subprocess
import argparse
import os
import re
import requests

from bs4 import BeautifulSoup

try:
    raw_input
except NameError:
    raw_input = input

URL = "https://{team_name}.slack.com/customize/emoji"


def _session(args):
    assert args.cookie, "Cookie required"
    assert args.team_name, "Team name required"
    session = requests.session()
    session.headers = {'Cookie': args.cookie}
    session.url = URL.format(team_name=args.team_name)
    return session


def _argparse():
    parser = argparse.ArgumentParser(
        description='Bulk upload emoji to slack'
    )
    parser.add_argument(
        '--team-name', '-t',
        default=os.getenv('SLACK_TEAM'),
        help='Defaults to the $SLACK_TEAM environment variable.'
    )
    parser.add_argument(
        '--message', '-m',
        default="",
        help='original text to send'
    )
    parser.add_argument(
        '--cookie', '-c',
        default=os.getenv('SLACK_COOKIE'),
        help='Defaults to the $SLACK_COOKIE environment variable.'
    )
    args = parser.parse_args()
    if not args.team_name:
        args.team_name = raw_input('Please enter the team name: ').strip()
    if not args.cookie:
        args.cookie = raw_input('Please enter the "/customize/emoji" cookie: ').strip()
    if not args.message:
        args.message = raw_input('please enter message: ').strip()
    return args


def main():
    make_emoji("ok")
    args = _argparse()
    session = _session(args)
    existing_emojis = get_current_emoji_list(session)
    uploaded = 0
    skipped = 0

    words = args.message.split(" ")
    for word in args.message.split(" "):
        filename = make_emoji(word)
        emoji_name = word.lower()
        print("Processing {}.".format(filename))
        if emoji_name in existing_emojis:
            print("Skipping {}. Emoji already exists".format(emoji_name))
            skipped += 1 # ¯\_(ツ)_/¯
        else:
            upload_emoji(session, emoji_name, filename)
            print("{} upload complete.".format(filename))
            uploaded += 1 # ¯\_(ツ)_/¯

        subprocess.run(
            "rm {filename}".format(filename=filename),
            shell=True,
            check=False
        )

    slackmoji_text = " ".join(list(map(":{0}:".format, words)))
    send_slack_msg(slackmoji_text)
    print('\nUploaded {} emojis. ({} already existed)'.format(uploaded, skipped))


def send_slack_msg(msg):
    subprocess.run(
        'osascript paste_in_slack.scpt "{0}"'.format(msg),
        shell=True,
        check=False
    )

def make_emoji(word):
    emoji_text = word.upper()
    emoji_name = word.lower()

    subprocess.run("""
        convert \
            -size 128x128 \
            -gravity center \
            -fill black \
            -kerning -1 \
            -font /System/Library/Fonts/Helvetica.ttc \
            label:{emoji_text} \
            "PNG32:tmp-{emoji_name}.png";
        """.format(emoji_text=emoji_text, emoji_name=emoji_name),
        shell=True,
        check=False
    )

    subprocess.run("""
        convert \
            "tmp-{emoji_name}.png" \
            -transparent white \
            -fuzz 2% \
            "{emoji_name}.png";
        """.format(emoji_text=emoji_text, emoji_name=emoji_name),
        shell=True,
        check=False
    )

    subprocess.run(
        "rm tmp-{emoji_name}.png".format(emoji_name=emoji_name),
        shell=True,
        check=False
    )

    return "{emoji_name}.png".format(emoji_name=emoji_name)



def get_current_emoji_list(session):
    r = session.get(session.url)
    r.raise_for_status()
    x = re.findall("data-emoji-name=\"(.*?)\"", r.text)
    return x


def upload_emoji(session, emoji_name, filename):
    # Fetch the form first, to generate a crumb.
    r = session.get(session.url)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    crumb = soup.find("input", attrs={"name": "crumb"})["value"]

    data = {
        'add': 1,
        'crumb': crumb,
        'name': emoji_name,
        'mode': 'data',
    }
    files = {'img': open(filename, 'rb')}
    r = session.post(session.url, data=data, files=files, allow_redirects=False)
    r.raise_for_status()
    # Slack returns 200 OK even if upload fails, so check for status of 'alert_error' info box
    if b'alert_error' in r.content:
        soup = BeautifulSoup(r.text, "html.parser")
        crumb = soup.find("p", attrs={"class": "alert_error"})
        print("Error with uploading %s: %s" % (emoji_name, crumb.text))


if __name__ == '__main__':
    main()
