from __future__ import absolute_import, unicode_literals

from django.shortcuts import render
from .forms import UserQueryForm, ScraperForm, SkillsForm
from .models import ScraperParams

from djangosite.celery import app
from django_celery_results.models import TaskResult
from .tasks import scrape_dice, get_stackoverflow_skills
from .text_proc import get_word_count, db_text_search
import pymongo


# mongod db init and config
client = pymongo.MongoClient('localhost', 27017)
db = client.jobpost_data
db.posts.create_index('url', unique=True)
db.posts.create_index([('query_loc', 1), ('title', pymongo.TEXT),
                       ('skills', pymongo.TEXT), ('desc', pymongo.TEXT)])
# db.posts.index_information()
# db.posts.drop_index('query_loc_1_title_text_skills_text')
# import pdb; pdb.set_trace()  #### DEBUG


def scraper(request):
    if request.method == 'POST':
        form = ScraperForm(request.POST)  # populate form with request data
        if form.is_valid():   # process the data in form.cleaned_data
            query_loc = form.cleaned_data['params'].query_loc.query
            query = form.cleaned_data['params'].query
            param_id = form.cleaned_data['params'].id
            if form.cleaned_data['params'].job_site.name == "Dice":
                s = ScraperParams.objects.get(id=param_id)
                if s.status != 'SCRAPE IN PROGRESS':
                    # send task to celery to manage
                    task_obj = scrape_dice.delay(query=query,
                                                 query_loc=query_loc,
                                                 param_id=param_id)
                    # write result identifier to scraper params obj
                    s.task_id = str(task_obj)
                    s.save()
                form = ScraperForm()  # clear form selection
        else:
            form = ScraperForm()
    else:  # if not POST, then create a new form
        form = ScraperForm()

    # current tasks via celery inspection, takes about 3 seconds
    i = app.control.inspect()
    current_tasks = ([x for x in i.active()['celery@ubuntu-xenial']] +
                     [x for x in i.reserved()['celery@ubuntu-xenial']] +
                     [x for x in i.scheduled()['celery@ubuntu-xenial']])
    current_task_ids = [x['id'] for x in current_tasks]

    # set status of every scraper_params object
    scraper_params = ScraperParams.objects.all()
    for s in scraper_params:
        s.status = 'NOT QUERIED YET'
        results = TaskResult.objects.filter(task_id=s.task_id)
        if len(results) > 0:
            if results[0].status == 'SUCCESS':
                s.status = '{} posts scraped on {}'.format(results[0].result,
                           s.last_queried.strftime('%Y-%m-%d %H:%M'))
            else:
                s.status = (results[0].status + ' ...' +
                            results[0].traceback[-100:])
        if s.task_id in current_task_ids:
            s.status = 'SCRAPE IN PROGRESS'
        s.save()

    context = {
        'form': form,
    }
    return render(request, 'home/scraper.html', context)


def skills(request):
    if request.method == 'POST':
        form = SkillsForm(request.POST)  # populate form with data from request
        if form.is_valid():   # process the data in form.cleaned_data
            get_stackoverflow_skills.delay()
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
