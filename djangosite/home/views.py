from __future__ import absolute_import, unicode_literals

from django.shortcuts import render
from django.http import HttpResponse
from .forms import UserQueryForm, ScraperForm, SkillsForm
from .models import ScraperParams

from djangosite.celery import app
from .tasks import scrape_dice
from django_celery_results.models import TaskResult

## Moved these items to tasks.py for scrape_dice
# import requests
# from bs4 import BeautifulSoup
# import urllib
# import math
# from datetime import datetime, timedelta
# import re

import time
import pymongo
import string
import nltk
nltk.download('stopwords')
from nltk.corpus import stopwords
import collections
import textblob
from operator import itemgetter
import itertools
import sys
import traceback
from pprint import pprint

# mongod db init and config
client = pymongo.MongoClient('localhost', 27017)
db = client.jobpost_data
db.posts.create_index('url', unique=True)
db.posts.create_index([('query_loc', 1), ('title', pymongo.TEXT), ('skills', pymongo.TEXT), ('desc', pymongo.TEXT)])
# db.posts.index_information()
# db.posts.drop_index('query_loc_1_title_text_skills_text')
#import pdb; pdb.set_trace()  #### DEBUG
stops = set(stopwords.words('english'))

# extra stopwords needed when including job 'desc' along with 'skills'/'title'
stops |= set(['experience', 'client', 'position', 'include', 'time',
              'service', 'apply', 'design', 'build', 'system', 'testing',
              'integration', 'field', 'documentation', 'architecture',
              'dynamic', 'project', 'join', 'standards', 'email', 'location',
              'performance', 'key', 'focus', 'object', 'process', 'center',
              'server', 'components', 'scale', 'user', 'external', 'global',
              'local', 'processing', 'call', 'configuration', 'networking',
              'resources', 'protocols', 'frameworks'])

def scraper(request):
    if request.method == 'POST':
        form = ScraperForm(request.POST)  # populate form with data from request
        if form.is_valid():   # process the data in form.cleaned_data
            query_loc = form.cleaned_data['params'].query_loc.query
            query = form.cleaned_data['params'].query
            param_id = form.cleaned_data['params'].id
            if form.cleaned_data['params'].job_site.name == "Dice":
                res_obj = scrape_dice.delay(query=query,
                                            query_loc=query_loc,
                                            param_id=param_id)
                print('res_obj: {}'.format(res_obj))
                print('type(res_obj): {}'.format(type(res_obj)))
        else:
            form = ScraperForm()
    else:  # if not POST, then create a new form
        form = ScraperForm()

    results = TaskResult.objects.all().order_by('-date_done')[:5]

    # celery inspection
    i = app.control.inspect()
    active_tasks = [x for x in i.active()['celery@ubuntu-xenial']]
    [x.update({'status': 'active'}) for x in active_tasks]
    reserved_tasks = [x for x in i.reserved()['celery@ubuntu-xenial']]
    [x.update({'status': 'reserved'}) for x in reserved_tasks]
    scheduled_tasks = [x for x in i.scheduled()['celery@ubuntu-xenial']]
    [x.update({'status': 'scheduled'}) for x in scheduled_tasks]
    tasks = active_tasks + reserved_tasks + scheduled_tasks

    context = {
        'form': form,
        'results': results,
        'tasks': tasks,
    }
    return render(request, 'home/scraper.html', context)

def skills(request):
    if request.method == 'POST':
        form = SkillsForm(request.POST)  # populate form with data from request
        if form.is_valid():   # process the data in form.cleaned_data
            get_stackoverflow_skills()
        else:
            form = SkillsForm()
    else:  # if not POST, then create a new form
        form = SkillsForm()
    return render(request, 'home/skills.html', {'form': form})

def index(request):
    ''' GET FORM DATA '''
    if request.method != 'GET':
        form = UserQueryForm()  # create new form
        context = {'title': 'enter query', 'results': [], 'form': form}
        return render(request, 'home/index.html', context)
    form = UserQueryForm(request.GET)  # populate form with data from request
    if not form.is_valid():
        form = UserQueryForm()
        context = {'title': 'enter query', 'results': [], 'form': form}
        return render(request, 'home/index.html', context)

    ''' QUERY DATABASE VIA USER KEYWORDS '''
    query = form.cleaned_data['query']
    query_loc = form.cleaned_data['location'].query
    dataset = db_text_search(query, query_loc)
    post_count = db.posts.find({'query_loc': query_loc}).count()

    ''' TEXT PROCESSING '''
    data = get_word_count(dataset)

    ''' PREPARE DATA FOR TEMPLATE '''
    title = '{} job posts matching "{}" out of {} posts in {}'.format(
            len(dataset), query, post_count, query_loc)
    context = {'title': title, 'data': data, 'form': form}
    return render(request, 'home/index.html', context)

def db_text_search(query, query_loc):
    cur = db.posts.find({'query_loc': query_loc,
                         '$text': {'$search': query}})
    return [doc for doc in cur]

def get_word_count(dataset):
    # get count of single words
    allwords = []
    start = time.time()
    for doc in dataset:
        docwords = set()
        for field in ['skills', 'title', 'desc']:  # 'desc' adds 3.7sec + clutter
            fieldwords = textblob.TextBlob(doc[field]).lower().words
            fieldwords = [i for w in fieldwords for i in w.split('/')]
            fieldwords = [i for w in fieldwords for i in w.split('-')]
            docwords = docwords.union(set(fieldwords))
        allwords.extend(docwords)
    print('after {} words, TIME: {:.3f}s'.format(len(allwords), (time.time()-start)))
    allwords = [w for w in allwords if not w in stops]
    allwords = skill_whitelist(allwords)  # filter by stackoverflow skills
    count = collections.Counter(allwords)

    # # append top noun_phrases
    # allphrases = []
    # for doc in dataset:
    #     docphrases = textblob.TextBlob(doc['skills']).lower().noun_phrases
    #     allphrases.extend(docphrases)
    # count += collections.Counter(allphrases)
    # print('after phrases, TIME: {:.3f}s'.format((time.time()-start)))
    # print(collections.Counter(allphrases).most_common(20))

    return count.most_common(40)


def skill_whitelist(skills_to_filter):
    whitelist = db.skills.find_one({'source': 'stackoverflow'})['skills']
    whitelist = set(whitelist)
    ''' FYI top skills in 'desc' are design, env, position, client, comm
        using, system, project... if whitelist had only true tech skills
        then could count words in 'desc' field (but takes ~3.7sec) '''
    return [s for s in skills_to_filter if s in whitelist]


def skill_relations():
    # create a map from skill to jobpost in database
    start = time.time()
    skill_map = {}
    for job in db.posts.find({}, {'skills': 1, '_id': 1}):
        words = textblob.TextBlob(job['skills']).lower().words
        words = [w for w in words if not w in stops]
        for word in words:
            skill_map[word] = skill_map.get(word, []) + [job['_id']]

    # get top_skills
    top_skills = [s[0] for s in get_word_count('skills')]
    top_skills = list(itertools.combinations(top_skills,2))

    # compare top skills to map
    relations = []
    for s1, s2 in top_skills:
        set1 = set(skill_map[s1])
        set2 = set(skill_map[s2])
        relations.append([s1, s2, len(set1.intersection(set2))])
        relations.append([s2, s1, len(set1.intersection(set2))])

    # relations.sort(key=lambda x: x[2], reverse=True)
    print('for {} combos, TIME: {:.3f}s'.format(len(relations), (time.time()-start)))
    return relations

def employer_skill_relations():
    top_skills = [s[0] for s in get_word_count('skills')]
    top_employers = get_top_employers()
    return None

def title_skill_relations():
    top_skills = [s[0] for s in get_word_count('skills')]
    top_titles = get_top_titles()
    return None

def get_top_employers():
    cur = db.posts.find({}, {'employer': 1, '_id': 0})
    employers = [i['employer'].lower() for i in cur]
    return collections.Counter(employers).most_common(10)

def get_top_titles():
    cur = db.posts.find({}, {'title': 1, '_id': 0})
    titles = [i['title'].lower() for i in cur]
    return collections.Counter(titles).most_common(10)

def get_stackoverflow_skills():
    skills = []
    base_url = 'https://stackoverflow.com'
    for n in range(60):
        r = requests.get(base_url + '/tags?page={}&tab=popular'.format(n))
        soup = BeautifulSoup(r.text, 'html.parser')
        tags = [t.text for t in soup.find_all('a', 'post-tag')]
        skills.extend(tags)

    data = {'source': 'stackoverflow', 'skills': skills}
    db.skills.update( {'source': 'stackoverflow'}, data, upsert=True )
