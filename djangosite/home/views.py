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


def get_task_progress(request):
    data = 'error'
    if request.is_ajax():  # ajax view to get progress of task
        if 'task_id' in request.GET.keys() and request.GET['task_id']:
            task_id = request.GET['task_id']
            task = AsyncResult(task_id)
            progress = 100
            if 'progress' in task.result:
                progress = task.result['progress']

            data = {
                'status': task.status,
                'progress': progress,
                'display_result': helper_get_display_results(task_id)
            }
    json_data = json.dumps(data)
    return HttpResponse(json_data, content_type='application/json')

def helper_get_display_results(task_id):
    print(task_id)
    display_result = ''
    task = TaskResult.objects.get(task_id=task_id)
    if task.status == 'FAILURE':
        display_result = json.loads(task.result)['exc_type']
    elif task.status == 'SUCCESS':
        display_result = '{} posts scraped on {}'.format(
            json.loads(task.result)['jobposts'],
            task.date_done.strftime('%Y-%m-%d %H:%M'))
    print(display_result)
    return display_result

def scraper(request):
    if request.method == 'POST':
        form = ScraperForm(request.POST)  # populate form with request data
        if form.is_valid():   # process the data in form.cleaned_data
            if form.cleaned_data['params'].job_site.name == "Dice":
                s = ScraperParams.objects.get(id=form.cleaned_data['params'].id)
                if s.status != 'PENDING' and s.status != 'PROGRESS':
                    task = scrape_dice.delay(  # send task to celery to manage
                        query=form.cleaned_data['params'].query,
                        query_loc=form.cleaned_data['params'].query_loc.query,
                        param_id=form.cleaned_data['params'].id)
                    task = TaskResult(task_id=task.task_id)
                    task.save()
                    s.task_id = task.task_id
                    s.save()  # write task_id to scraper_params obj
                form = ScraperForm()  # clear form selection
        else:
            form = ScraperForm()
    else:  # if not POST, then create a new form
        form = ScraperForm()

    # create scraper list with scraper info for display
    scraper_list = []
    scraper_params = ScraperParams.objects.all()
    for scraper in scraper_params:
        status = {'status': 'NOT QUERIED YET',
                  'display_result': '',
                  'progress': 0}
        if scraper.task_id:
            task = TaskResult.objects.get(task_id=scraper.task_id)
            display_result = helper_get_display_results(scraper.task_id)
            status['status'] = task.status
            status['display_result'] = display_result
        scraper_list.append((scraper, status))

    context = {
        'form': form,
        'scraper_list': scraper_list,
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
