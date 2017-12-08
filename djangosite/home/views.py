from django.shortcuts import render
from django.http import HttpResponse
from .models import Posts

import requests
from bs4 import BeautifulSoup
import math
from datetime import datetime
import time
import re
import pymongo
import string
#import nltk  # nltk.download('stopwords')
from nltk.corpus import stopwords
import collections


# Create your views here.
def index(request):
    client = pymongo.MongoClient('localhost', 27017)
    db = client.py_posts

    ''' SCRAPING SECTION '''
    #search_dice(query='python', zipcode='27606')


    ''' TEXT PROCCESSING SECTION '''
    # get all skills as one text blob
    start = time.time()
    print('starting db query')
    alltext = {}
    cur = db.posts.find({}, {'desc': 1, 'skills': 1, '_id': 0})
    for i in cur:
        alltext['desc'] = alltext.get('desc', '') + ' ' + i['desc']
        alltext['skills'] = alltext.get('skills', '') + ' ' + i['skills']
    # posts = Posts.objects.all() ... for p in posts: ... p.data['desc']
    print('completed dbquery: {:.3f}s'.format(time.time()-start))

    # create punctation translation
    punctuation = '!"#$%&\'()*,-./:;<=>?@[\\]^_`{|}~'  # not + (ie C++)
    replace_punc = str.maketrans(punctuation, ' '*len(punctuation))

    # turn each dict textblob into list of words
    for text in alltext:
        # do lambda + set edits here: https://gist.github.com/ameyavilankar/10347201
        # see if any benefit here: http://www.cs.duke.edu/courses/spring14/compsci290/assignments/lab02.html
        alltext[text] = alltext[text].lower()
        alltext[text] = alltext[text].translate(replace_punc)
    print('completed replace_punc: {:.3f}s'.format(time.time()-start))

    for text in alltext:
        tokens = alltext[text].split()
        stops = set(stopwords.words('english'))  # speed up from 9s to 9ms
        alltext[text] = [w for w in tokens if not w in stops]
    print('completed split: {:.3f}s'.format(time.time()-start))

    # count each list of words
    results = []
    for words in alltext:
        result = {}
        result['name'] = words
        count = collections.Counter(alltext[words])
        result['data'] = count.most_common(20)
        results += [result]
        result['font_ref'] = result['data'][0][1]

    # skills_count = collections.Counter(alltext['skills'])
    # skills_results = skills_count.most_common(20)
    #
    # desc_count = collections.Counter(alltext['desc'])
    # desc_results = desc_count.most_common(20)
    print('completed counts: {:.3f}s'.format(time.time()-start))


    #import pdb; pdb.set_trace()  #### DEBUG

    context = {'title': 'post subset',
               'results': results}
    return render(request, 'home/index.html', context)



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
        # job['timestamp'] = datetime.utcnow()

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
