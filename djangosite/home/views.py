from django.shortcuts import render
from django.http import HttpResponse
from .forms import UserQueryForm, ScraperForm

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


# mongod db init and config
client = pymongo.MongoClient('localhost', 27017)
db = client.py_posts
db.posts.create_index('url', unique=True)
db.posts.create_index('skills')
# db.posts.create_index([('query_loc', 1),('title', pymongo.TEXT),
#                 ('skills', pymongo.TEXT), ('desc', pymongo.TEXT)])
db.posts.create_index([('query_loc', 1),('title', pymongo.TEXT), ('skills', pymongo.TEXT)])
#db.posts.index_information()
#db.posts.drop_index('query_loc_1_title_text_skills_text')
#import pdb; pdb.set_trace()  #### DEBUG
stops = set(stopwords.words('english'))
#stops.add('python')
stops.add('experience')

# Create your views here.
def scraper(request):
    if request.method == 'POST':
        form = ScraperForm(request.POST)  # populate form with data from request
        if form.is_valid():   # process the data in form.cleaned_data
            query_loc = form.cleaned_data['scraper_params'].query_loc.query
            query = form.cleaned_data['scraper_params'].query
            print(form.cleaned_data['scraper_params'])
            if form.cleaned_data['scraper_params'].job_site.name == "Dice":
                num_items = None
                #num_items = search_dice(query=query, query_loc=query_loc)
            if not num_items:
                form.cleaned_data['scraper_params'].last_queried = datetime.utcnow()
        else:
            form = ScraperForm()
    else:  # if not POST, then create a new form
        form = ScraperForm()

    return render(request, 'home/scraper.html', {'form': form})


def index(request):
    if request.method != 'GET':
        return render(request, 'home/name.html')  #fix this
    form = UserQueryForm(request.GET)  # populate form with data from request
    if not form.is_valid():
        form = UserQueryForm()
        context = {'title': 'enter query', 'results': [], 'form': form}
        return render(request, 'home/index.html', context)

    ''' SCRAPING SECTION '''
    #search_dice(query='', query_loc='baltimore, md')
    #get_stackoverflow_skills()

    ''' TEXT PROCCESSING SECTION '''
    query = form.cleaned_data['query']
    query_loc = form.cleaned_data['location']
    dataset = db_text_search(query, query_loc)

    results = []
    results.append({'title': 'single word', 'data': single_word_count(dataset)})
    results.append({'title': 'noun phrases', 'data': get_noun_phrases('skills', dataset)})
    results.append({'title': 'ngram', 'data': get_ngrams('skills', dataset)})
    #
    #
    # relations = skill_relations()
    # sortOrder = [s[0] for s in single_word_count()]
    # color_list = ['#'+str(hex(int(((n+1)/100)*16777215)))[2:] for n in range(100)]
    # print(len(color_list))
    # color_list = ['#ff00ff'] * 60
    # colors = dict(zip(sortOrder, color_list))
    # context = {'title': 'Multi-Processing Results',
    #            'data': relations,
    #            'sortOrder': sortOrder,
    #            'colors': colors}
    # return render(request, 'home/chord.html', context)
    title = '{} job posts matching "{}" in {}'.format(
            len(dataset), query, query_loc)
    context = {'title': title, 'results': results, 'form': form}
    return render(request, 'home/index.html', context)


def db_text_search(query, query_loc):
    cur = db.posts.find({'query_loc': query_loc,
                         '$text': {'$search': query}})
    return [doc for doc in cur]


def single_word_count(dataset):
    allwords = []
    start = time.time()
    for doc in dataset:
        docwords = set()
        for field in ['skills', 'title']:  # 'desc' adds 3.7sec + clutter
            fieldwords = textblob.TextBlob(doc[field]).lower().words
            fieldwords = [i for w in fieldwords for i in w.split('/')]
            fieldwords = [i for w in fieldwords for i in w.split('-')]
            docwords = docwords.union(set(fieldwords))
        allwords.extend(docwords)
    print('for {} words, TIME: {:.3f}s'.format(len(allwords), (time.time()-start)))
    allwords = [w for w in allwords if not w in stops]
    allwords = skill_whitelist(allwords)  # filter by stackoverflow skills
    count = collections.Counter(allwords)
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
    top_skills = [s[0] for s in single_word_count('skills')]
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
    top_skills = [s[0] for s in single_word_count('skills')]
    top_employers = get_top_employers()
    return None

def title_skill_relations():
    top_skills = [s[0] for s in single_word_count('skills')]
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


def get_ngrams(field, dataset):
    # cur = db.posts.find({}, {'desc': 1, 'skills': 1, '_id': 0})
    # all_text = [i[field].replace(',', '.') for i in cur]
    all_text = [i[field].replace(',', '.') for i in dataset]

    # make sentences out of all_text
    all_sentences = []
    for text in all_text:
        blob = textblob.TextBlob(text).lower()
        sentences = blob.split('.')
        for sentence in sentences:
            wordlist = textblob.TextBlob(sentence).words
            wordlist = [w for w in wordlist if not w in stops]
            sentence = ' '.join(wordlist)
            all_sentences.append(sentence)

    # make ngrams out of all_sentences
    all_bigrams = []
    all_trigrams = []
    for sentence in all_sentences:
        blob = textblob.TextBlob(sentence)
        bigrams = blob.ngrams(2)
        for wordlist in bigrams:
            all_bigrams.append(' '.join(wordlist))
        trigrams = blob.ngrams(3)
        for wordlist in trigrams:
            all_trigrams.append(' '.join(wordlist))

    # count combine and sort ngrams
    bicount = collections.Counter(all_bigrams).most_common(15)
    tricount = collections.Counter(all_trigrams).most_common(15)

    return sorted(bicount + tricount, key=itemgetter(1), reverse=True)


def get_noun_phrases(field, dataset):
    # cur = db.posts.find({}, {'desc': 1, 'skills': 1, '_id': 0})
    phrases = []
    for i in dataset:
        blob = textblob.TextBlob(i[field]).lower()
        wordlist = blob.noun_phrases
        phrases.extend(wordlist)

    count = collections.Counter(phrases)
    return count.most_common(30)


def get_stackoverflow_skills():
    skills = []
    base_url = 'https://stackoverflow.com'
    for n in range(100):
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

        # get datetime when posted
        try:
            x = soup.find('li', 'posted').text.strip().strip('.,')
            N = int(x.split(' ')[1])
            deltatype = x.split(' ')[2]
            deltatype = deltatype if deltatype[-1] == 's' else deltatype + 's'
            if deltatype == 'months':
                deltatype = 'days'
                N = N*30
            delta = eval("timedelta("+deltatype+"=N)")
            job['posted'] = datetime.utcnow() - delta
        except Exception as e:
            print('Exception, for [posted]. Error info: {}'.format(e))
            print("job['url']: {}".format(job['url']))

        # get skills
        div = soup.find('div', {'class': 'iconsiblings', 'itemprop': 'skills'})
        job['skills'] = div.getText(' ').strip()

        # get icons, if missing an icon then ordered wrong and bad data
        icons = soup.find_all('div', 'iconsiblings')
        try:  # icons[0] is ['skills']
            job['empType'] = icons[1].getText(' ').strip()
            job['baseSalary'] = icons[2].getText(' ').strip()
            job['teleTravel'] = icons[3].getText(' ').strip()
        except IndexError as e:
            print('IndexError, in icon area. Error info: {}'.format(e))
            print("job['url']: {}".format(job['url']))

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
        try:
            db.posts.update( {'url': job['url'] }, job, upsert=True )
            print('jobpost written to database')
        except pymongo.errors.WriteError as e:
            print('WriteError, likely [skills] key too large: {}'.format(e))
            print("job['url']: {}".format(job['url']))

    return len(joblinks)
