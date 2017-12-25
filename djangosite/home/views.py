from django.shortcuts import render
from django.http import HttpResponse
from .forms import UserQueryForm, ScraperForm, SkillsForm
from .models import ScraperParams

import requests
from bs4 import BeautifulSoup
import math
from datetime import datetime, timedelta
import time
import re
import pymongo
import string
import nltk
nltk.download('stopwords')
from nltk.corpus import stopwords
import collections
import textblob
from operator import itemgetter
import urllib
import itertools
import sys
import traceback

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
              'resources', 'protocols'])

def scraper(request):
    if request.method == 'POST':
        form = ScraperForm(request.POST)  # populate form with data from request
        if form.is_valid():   # process the data in form.cleaned_data
            query_loc = form.cleaned_data['params'].query_loc.query
            query = form.cleaned_data['params'].query
            db_id = form.cleaned_data['params'].id
            if form.cleaned_data['params'].job_site.name == "Dice":
                num_items = search_dice(query=query, query_loc=query_loc)
            if num_items:
                s = ScraperParams.objects.get(id=db_id)
                s.last_queried = datetime.utcnow()
                s.save()
        else:
            form = ScraperForm()
    else:  # if not POST, then create a new form
        form = ScraperForm()
    return render(request, 'home/scraper.html', {'form': form})

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
    # print(form.cleaned_data['test'].query)
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

    # append top noun_phrases
    allphrases = []
    for doc in dataset:
        docphrases = textblob.TextBlob(doc['skills']).lower().noun_phrases
        allphrases.extend(docphrases)
    count += collections.Counter(allphrases)
    print('after phrases, TIME: {:.3f}s'.format((time.time()-start)))
    print(collections.Counter(allphrases).most_common(20))

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

def search_dice(query, query_loc):
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

    # gather joblinks from each page
    joblinks = []
    for page in pagelinks:
        r = requests.get(base_url + page)
        soup = BeautifulSoup(r.text, 'html.parser')
        divs = soup.find_all('div', 'complete-serp-result-div')
        joblinks += [d.find('a', 'dice-btn-link')['href'] for d in divs]
        print(page)

    # get all job dicts and put into jobs list
    for joblink in joblinks:
        try:
            r = requests.get(base_url + joblink)
            soup = BeautifulSoup(r.text, 'html.parser')
            job = {}

            # set query data
            job['query'] = query.lower()
            job['query_loc'] = query_loc.lower()
            job['timestamp'] = datetime.utcnow()
            job['url'] = base_url + joblink.split('?')[0]

            # get basic job info
            job['title'] = soup.find('h1', 'jobTitle').getText(' ')
            job['employer'] = soup.find('li', 'employer').getText(' ').strip().strip('., ')
            job['location'] = soup.find('li', 'location').getText(' ').strip().strip('., ')

            # get datetime when posted, format: "Posted 22 minutes ago"
            try:
                text = soup.find('li', 'posted').text.strip().strip('.,')
                deltatype = text.split(' ')[-2]
                if deltatype == 'moments':
                    job['posted'] = datetime.utcnow()
                else:
                    N = int(text.split(' ')[1])
                    deltatype = deltatype if deltatype[-1] == 's' else deltatype + 's'
                    if deltatype == 'months':
                        deltatype = 'days'
                        N = N*30
                    delta = eval("timedelta("+deltatype+"=N)")
                    job['posted'] = datetime.utcnow() - delta
            except Exception as e:
                print('EXCEPTION, FOR [posted]. ERROR INFO: {}'.format(e))
                print("job['url']: {}".format(job['url']))

            # get skills
            div = soup.find('div', {'class': 'iconsiblings', 'itemprop': 'skills'})
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
            db.posts.update( {'url': job['url'] }, job, upsert=True )
            print('.', end='', flush=True)
        except Exception as e:
            traceback.print_exc()
            print("GENERAL SCRAPER ERROR job['url']: {}\n".format(job['url']))

    print("\nlen(joblinks) = {}".format(len(joblinks)))
    return len(joblinks)
