from __future__ import absolute_import, unicode_literals

from django.shortcuts import render
from .forms import UserQueryForm, ScraperForm, SkillsForm
from .models import ScraperParams
from django.http import HttpResponse

from djangosite.celery import app
from django_celery_results.models import TaskResult
from celery.result import AsyncResult
from .tasks import scrape_dice, get_stackoverflow_skills
from .text_proc import get_word_count, db_text_search
from .utils import get_display_results
import pymongo
import json


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
    form = ScraperForm()
    scraper_list = []  # create scraper list with scraper info for display
    scraper_params = ScraperParams.objects.all().order_by('id')
    for scraper in scraper_params:
        status = {'status': 'NOT QUERIED YET',
                  'display_result': '',
                  'progress': 0}
        if scraper.task_id:
            task = TaskResult.objects.get(task_id=scraper.task_id)
            display_result = get_display_results(scraper.task_id)
            status['status'] = task.status
            status['display_result'] = display_result
        scraper_list.append((scraper, status))

    context = {
        'form': form,
        'scraper_list': scraper_list,
    }
    return render(request, 'home/scraper.html', context)


def start_scraper(request):
    data = 'error'
    if request.is_ajax():  # ajax view to get progress of task
        if 'scraper_id' in request.POST.keys() and request.POST['scraper_id']:
            s = ScraperParams.objects.get(id=request.POST['scraper_id'])
            task = scrape_dice.delay(query=s.query,  # send task to celery
                                     query_loc=s.query_loc.query,
                                     param_id=s.id)
            task = TaskResult(task_id=task.task_id)
            task.save()  # makes obj able to query right away
            s.task_id = task.task_id
            s.save()  # write task_id to scraper_params obj
            data = { 'task_id': task.task_id }
    json_data = json.dumps(data)
    return HttpResponse(json_data, content_type='application/json')


def get_task_progress(request):
    data = 'error'
    if request.is_ajax():  # ajax view to get progress of task
        if 'task_id' in request.GET.keys() and request.GET['task_id']:
            task_id = request.GET['task_id']
            task = AsyncResult(task_id)  #TODO try except if celery is down, log it

            progress = 0
            if task.status == 'IN_PROGRESS' or task.status == 'SUCCESS':
                if 'progress' in task.result:
                    progress = task.result['progress']

            data = {
                'status': task.status,
                'progress': progress,
                'display_result': get_display_results(task_id)
            }
    json_data = json.dumps(data)
    return HttpResponse(json_data, content_type='application/json')


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
    data = [tup for tup in data if tup[0] != query]
    words = [{'text': tup[0], 'size': tup[1]} for tup in data]

    ''' PREPARE DATA FOR TEMPLATE '''
    title = '{} job posts matching "{}" out of {} posts in {}. Highest matching skills:'.format(
            'len(dataset)', query, post_count, query_loc)
    context = {'title': title, 'data': data, 'form': form, 'words': words}
    return render(request, 'home/index.html', context)
