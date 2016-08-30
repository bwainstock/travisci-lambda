"""Collection of functions to scrape various concert calendars"""

from datetime import datetime
import json
import os
import re
import requests

import boto3
from bs4 import BeautifulSoup
import MySQLdb

basedir = os.path.abspath(os.path.dirname(__file__))

bucket, key = ('radradrad', 'config.json')
s3client = boto3.client('s3')
s3client.download_file(bucket, key, key)
with open(key) as f:
    creds = json.load(f)

db = MySQLdb.connect(host=creds['host'],
                         port=3306,
                         passwd=creds['password'],
                         user=creds['username'],
                         db=creds['db'])
cur = db.cursor()

def _get_soup(url):
    """
    Return soup of calendar
    """
    headers = {'User-Agent': 'radradrad Concert Calendar v0.1 (radradrad.com)'}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.content)
    return soup


def insert_show(show_info):
    """
    Insert concert if not in database, else skip it
    """
    show_location = show_info['show_location']
#    concert = Concert.query.filter_by(headliner=show_info['show_headliner'],
#                                      date=show_info['show_date'],
#                                      time=show_info['show_time']).first()

    concert_query = 'SELECT * FROM concert WHERE headliner = %s AND date = %s AND time = %s;'
    cur.execute(concert_query, (show_info['show_headliner'],
                                show_info['show_date'],
                                show_info['show_time']))
    print((show_info['show_headliner'],
                                show_info['show_date'],
                                show_info['show_time']))

    concert = cur.fetchall()
    print(concert)

    if concert is tuple():
        venue_id_query = "SELECT id FROM venue WHERE name = %s"
        cur.execute(venue_id_query, (show_info['show_location'],))
        print(show_info['show_location'])
        venue_id = cur.fetchone()[0]

        concert_query = """INSERT INTO concert (date, time, url, headliner, supports, age, cost, venue_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
        cur.execute(concert_query, (show_info['show_date'],
                                    show_info['show_time'],
                                    show_info['show_url'],
                                    show_info['show_headliner'],
                                    ','.join(show_info['show_supports']) if show_info['show_supports'] else None,
                                    show_info['show_age'],
                                    show_info['show_cost'],
                                    venue_id))
        print('{} inserted'.format(show_info['show_headliner']))


def parse_chapel(show_date, raw_show):
    """
    Parses shows for The Chapel SF
    """
    show = raw_show
    base_url = 'http://www.thechapelsf.com'
    show_url = show.find(class_='url')
    if show_url:
        show_headliner = show_url.text
    else:
        show_headliner = None
    show_url = ''.join([base_url, show_url.get('href')])
    show_supports = show.findAll(class_='supports')
    if show_supports:
        show_supports = [supports.text for supports in show_supports]
    show_time = show.find(class_='start-time')
    if show_time:
        show_time = show_time.text
    show_location = show.find(class_='venue')
    if show_location:
        show_location = show_location.text
    show_age = show.find(class_='age-restriction')
    if show_age:
        show_age = show_age.text
    show_cost = show.find(class_='free')
    if show_cost:
        show_cost = 'Free'

    show_info = {
        'show_date': show_date,
        'show_time': show_time,
        'show_url': show_url,
        'show_headliner': show_headliner,
        'show_supports': show_supports,
        'show_location': show_location,
        'show_age': show_age,
        'show_cost': show_cost
        }

    return show_info


def chapel():
    """
    Scrapes calendar information from The Chapel SF website.
    """
    chapel_shows = []
    base_url = 'http://www.thechapelsf.com'
    calendar_url = ''.join([base_url, '/calendar/'])

    soup = _get_soup(calendar_url)

    show_calendar = soup.findAll(class_='vevent')
    for day in show_calendar:
        show_date = day.find('span', class_='value-title').get('title')
        show_date = re.search(r"([0-9-])+", show_date).group()
        show_date = datetime.strptime(show_date, '%Y-%m-%d').date().isoformat()

        shows = day.findAll('div', class_='one-event')
        for show in shows:
            show_info = parse_chapel(show_date, show)
            chapel_shows.append(show_info)
            insert_show(show_info)

#    db.session.commit()


    return chapel_shows


def parse_both(raw_show):
    """
    Parse show information for Bottom of the Hill
    """

    regex = r'vertical-align: top; background-color'
    show = raw_show.find(style=re.compile(regex))

    bands = show.findAll(class_='band')
    if bands:
        show_headliner = bands[0].text
        print(show_headliner)
        if len(bands) > 1:
            show_supports = [band.text for band in bands[1:]]
        else:
            show_supports = None
    else:
        show_headliner = None
        show_supports = None
    show_url = show.find('a')
    if show_url:
        show_url = show_url.get('href')

    show_date = [date.text for date in show.findAll(class_='date')]
    if show_date:
        show_date = ''.join(show_date).strip('\n')
        show_date = datetime.strptime(show_date, '%A %B %d %Y').date().isoformat()

    show_time = ''.join([x.text for x in show.findAll(class_='time')])
    if show_time:
        show_time = show_time.replace('\n', ' ')

    show_location = 'Bottom of the Hill'

    show_age = show.findAll(class_='age')
    if show_age:
        show_age = [x.text for x in show_age if '\n' not in x.text]
        show_age = ''.join(show_age)

    show_cost = show.findAll(class_='cover')
    if show_cost:
        show_cost = ''.join([x.text for x in show_cost])
        show_cost = show_cost.replace('\n', ' ')

    show_info = {
        'show_date': show_date,
        'show_time': show_time,
        'show_url': show_url,
        'show_headliner': show_headliner,
        'show_supports': show_supports,
        'show_location': show_location,
        'show_age': show_age,
        'show_cost': show_cost
        }

    return show_info


def both():
    """
    Scrapes calendar information from Bottom of the Hill website.
    """

    both_shows = []
    base_url = 'http://www.bottomofthehill.com'
    calendar_url = ''.join([base_url, '/calendar.html'])

    soup = _get_soup(calendar_url)

    show_calendar = soup.find('table', id='listings').findAll('tr')
    for show in show_calendar:
        if show.find(class_='date'):
            show_info = parse_both(show)
            both_shows.append(show_info)
            insert_show(show_info)

    #db.session.commit()
    return both_shows


def init_db():
    db.create_all()
    Venue.create_all()


def lambda_handler(event, context):
    chapel()
    both()
    db.commit()
    db.close()

def main():
    chapel()
    both()
    db.commit()
    db.close()

if __name__ == '__main__':
    main()
