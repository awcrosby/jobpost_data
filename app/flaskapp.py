#!/usr/bin/env python
# -*- coding: utf-8 -*-
# flaskapp.py

import requests
from bs4 import BeautifulSoup
import math
from datetime import datetime
import re
import pymongo
import string
import nltk
from nltk.corpus import stopwords

def main():
    client = pymongo.MongoClient('localhost', 27017)
    db = client.py_posts
    nltk.download('stopwords')

    ''' Scraping Section '''
    #search_dice(query='python', zipcode='27601')

    ''' Text Processing Section '''
    # get all skills as one text blob
    cur = db.posts.find({}, {'desc': 1, 'skills': 1, '_id': 0})
    text = ''
    for i in cur:
        text += ' ' + i['desc']
    text = text.lower()
    text = text.replace('/', ' ') #TODO need period and most punc as space not del
    translator = str.maketrans('', '', string.punctuation)  #TODO fix: c++ into c
    text = text.translate(translator)
    words = [w for w in text.split() if not w in stopwords.words('english')]

    from collections import Counter
    count = Counter(words)
    count.most_common(10)

    counts = {}
    for word in text.split():
        counts[word] = counts.get(word, 0) + 1 #(this creates or updates)

    import pdb; pdb.set_trace()  #### DEBUG

    # do word count on each

    #clean punctation, stopwords, see if better to treat as csv

    #http://www.geeksforgeeks.org/removing-stop-words-nltk-python/

def search_dice(query, zipcode):
    # query format is 'python_developer'
    def page_url(query, zipcode, pagenum):
        url = ('/jobs/q-{}-pc-true-'.format(query) +
               'l-{}-radius-30-startPage-{}-jobs'.format(zipcode, pagenum))
        return url

    # get initial search results to find num of posts and pages
    base_url = 'https://www.dice.com'
    r = requests.get(base_url + page_url(query, zipcode, 1))
    soup = BeautifulSoup(r.text, 'html.parser')

    # get pagelinks
    numposts = int(soup.find('span', {'id': 'posiCountId'}).text)
    numpages = math.ceil(numposts/30)  # dice has 30 posts/page
    pagelinks = [page_url(query, zipcode, n+1) for n in range(numpages)]

    # gather joblinks from each page
    joblinks = []
    for page in pagelinks:
        r = requests.get(base_url + page)
        soup = BeautifulSoup(r.text, 'html.parser')
        divs = soup.find_all('div', 'complete-serp-result-div')
        joblinks += [d.find('a', 'dice-btn-link')['href'] for d in divs]

    # get all job dicts and put into jobs list
    jobs = []
    for joblink in joblinks:
        r = requests.get(base_url + joblink)
        text = re.sub('</br>', ' ', r.text)
        text = re.sub('<br>', ' ', text)
        soup = BeautifulSoup(text, 'html.parser')
        job = {}

        # get title and company, set basic info
        job['title'] = soup.find('h1', 'jobTitle').text
        job['company'] = soup.find('span', {'itemprop': 'name'}).text
        job['query'] = query
        job['zipcode'] = zipcode
        job['timestamp'] = datetime.utcnow()

        # get summary info in icons
        icons = soup.find_all('div', 'iconsiblings')
        job['skills'] = icons[0].text.strip()
        job['empType'] = icons[1].text.strip()
        job['baseSalary'] = icons[2].text.strip()
        job['teleTravel'] = " ".join(
            [s.text for s in icons[3].find_all('span')])

        # get job description
        div = soup.find('div', {'id': 'jobdescSec'})
        job['desc'] = div.text.strip()
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
        job['url'] = base_url + joblink.split('?')[0]

        # append job dict to jobs list
        jobs += [job]

    db.posts.insert_many(jobs)

if __name__ == "__main__":
    main()
