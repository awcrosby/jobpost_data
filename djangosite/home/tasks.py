# Create your tasks here
from __future__ import absolute_import, unicode_literals
from celery import shared_task

import pymongo
from .models import ScraperParams
import requests
from bs4 import BeautifulSoup
import urllib
import math
from datetime import datetime
import re
import traceback
from time import sleep


@shared_task
def get_stackoverflow_skills():
    """Celery task that scrapes stackoverflow tags and writes to mongodb.

    Returns: None
    """
    client = pymongo.MongoClient('localhost', 27017)
    db = client.jobpost_data

    skills = []
    base_url = 'https://stackoverflow.com'
    print('starting stackoverflow scrape of tags')
    for n in range(60):
        r = requests.get(base_url + '/tags?page={}&tab=popular'.format(n))
        soup = BeautifulSoup(r.text, 'html.parser')
        tags = [t.text for t in soup.find_all('a', 'post-tag')]
        skills.extend(tags)
        print('.')

    data = {'source': 'stackoverflow', 'skills': skills}
    db.skills.update({'source': 'stackoverflow'}, data, upsert=True)
    print('completed stackoverflow task: {} skill tags'.format(len(skills)))


@shared_task(bind=True)
def scrape_dice(self, query, query_loc, param_id=None):
    """Celery task that scrapes dice jobposts and writes to mongodb.

    Args:
        query: search param for dice, empty string '' searches all
        query_loc: location search param for dice
        param_id: ScraperParams id ties task progress to manual task

    Returns:
        dictionary: has final task result to store in TaskResults
    """
    # setup vars to track progress of task
    current = 0
    interval = 7  # limit db writes
    self.update_state(state='IN_PROGRESS',
                      meta={'progress': 0})

    client = pymongo.MongoClient('localhost', 27017)
    db = client.jobpost_data

    # query format is 'python_developer'
    def page_url(query, query_loc, pagenum):
        q = urllib.parse.urlencode({'q': query}).split('=')[1]
        loc = urllib.parse.urlencode({'loc': query_loc}).split('=')[1]
        url = ('/jobs/q-{}-pc-true-'.format(q) +
               'l-{}-radius-30-startPage-{}-jobs'.format(loc, pagenum))
        return url

    # get initial search results to find num of posts and pages
    base_url = 'https://www.dice.com'
    r = requests.get(base_url + page_url(query, query_loc, 1))
    soup = BeautifulSoup(r.text, 'html.parser')

    # get pagelinks
    npost = int(soup.find('span', {'id': 'posiCountId'}).text.replace(',', ''))
    npage = math.ceil(npost/30)  # dice has 30 posts/page
    pagelinks = [page_url(query, query_loc, n+1) for n in range(npage)]
    total = npost + npage  # used for progress

    # gather joblinks from each page
    joblinks = []
    for page in pagelinks:
        try:
            sleep(0.2)
            r = requests.get(base_url + page)
            soup = BeautifulSoup(r.text, 'html.parser')
            divs = soup.find_all('div', 'complete-serp-result-div')
            joblinks += [d.find('a', 'dice-btn-link')['href'] for d in divs]

            # track and set progress
            current += 1
            if (current % interval) == 0:
                self.update_state(state='IN_PROGRESS',
                                  meta={'progress': (current/total)*100})
        except Exception as e:
            traceback.print_exc()
            print("\nGENERAL SCRAPER ERR page: {}\n".format(page))

    # get all job dicts and put into jobs list
    print('for {}: scraped {}pages of links'.format(query_loc, len(pagelinks)))
    scrape_count = 0
    for count, joblink in enumerate(joblinks):
        # track and set progress
        current += 1
        if (current % interval) == 0:
            self.update_state(state='IN_PROGRESS',
                              meta={'progress': (current/total)*100})
        if (count+1) % 100 == 0:
            print('for {}: {} joblinks processed, {} joblinks scraped'.format(
                query_loc, count+1, scrape_count))

        # exit if url already in database
        job_url = base_url + joblink.split('?')[0]
        if db.posts.find_one({'url': job_url}):
            continue

        scrape_count += 1
        try:
            sleep(0.2)
            r = requests.get(base_url + joblink)
            soup = BeautifulSoup(r.text, 'html.parser')
            job = {}

            # set query data
            job['query'] = query.lower()
            job['query_loc'] = query_loc.lower()
            job['timestamp'] = datetime.utcnow()
            job['url'] = job_url

            # get basic job info
            job['title'] = soup.find('h1', 'jobTitle').getText(' ')
            job['employer'] = (soup.find('li', 'employer')
                               .getText(' ').strip().strip('., '))
            job['location'] = (soup.find('li', 'location')
                               .getText(' ').strip().strip('., '))

            # get datetime when posted, format: "Posted 22 minutes ago"
            text = soup.find('li', 'posted').text.strip().strip('.,')
            deltype = text.split(' ')[-2]
            if deltype == 'moments':
                job['posted'] = datetime.utcnow()
            else:
                N = int(text.split(' ')[1])
                deltype = deltype if deltype[-1] == 's' else deltype + 's'
                if deltype == 'months':
                    deltype = 'days'
                    N = N*30
                delta = eval("timedelta("+deltype+"=N)")
                job['posted'] = datetime.utcnow() - delta

            # get skills
            div = soup.find('div', {'class': 'iconsiblings',
                                    'itemprop': 'skills'})
            job['skills'] = div.getText(' ').strip() if div else ''

            # get icons, if missing an icon then ordered wrong and bad data
            icons = soup.find_all('div', 'iconsiblings')
            try:  # icons[0] is ['skills']
                job['empType'] = icons[1].getText(' ').strip()
                job['baseSalary'] = icons[2].getText(' ').strip()
                job['teleTravel'] = icons[3].getText(' ').strip()
            except IndexError as e:
                pass  # gets info it can get. common that index not exist

            # get job description
            div = soup.find('div', {'id': 'jobdescSec'})
            job['desc'] = div.getText(' ').strip()
            job['desc'] = re.sub('\\xa0+', ' ', job['desc'])

            # get dice and position ids
            diceId, positionId = ('', '')
            id_div = soup.find('div', 'company-header-info')
            for div in id_div.find_all('div', 'col-md-12'):
                if "Dice Id" in div.text:
                    diceId = div.text.split(':')[1].strip()
                elif "Position Id" in div.text:
                    positionId = div.text.split(':')[1].strip()
            job['jobSite'] = 'dice'
            job['diceId'] = diceId
            job['positionId'] = positionId

            # insert or update job into database
            db.posts.update({'url': job['url']}, job, upsert=True)
        except Exception as e:
            traceback.print_exc()
            print("\nGENERAL SCRAPER ERR job['url']: {}\n".format(job['url']))

    print("\nlen(joblinks) = {}".format(len(joblinks)))
    if param_id:
        s = ScraperParams.objects.get(id=param_id)
        s.last_queried = datetime.utcnow()
        s.save()
    return {'jobposts': len(joblinks), 'progress': (current/total)*100}
