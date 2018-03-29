from __future__ import absolute_import, unicode_literals

from django.shortcuts import render
from django.http import HttpResponse
from .forms import UserQueryForm, ScraperForm
from .models import ScraperParams
from .text_proc import get_word_count, db_text_search, get_loc_week_counts
from .utils import get_display_results
from djangosite.celery import app
from django_celery_results.models import TaskResult
from django_celery_beat.models import PeriodicTask
import pymongo
import time
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# mongod db init and config
client = pymongo.MongoClient('localhost', 27017)
db = client.jobpost_data
db.posts.create_index('url', unique=True)
# db.posts.create_index([('posted_week', 1), ('query_loc', 1)])
# db.posts.create_index([('posted_week', 1), ('title', pymongo.TEXT),
#                       ('skills', pymongo.TEXT), ('desc', pymongo.TEXT)])
#db.posts.create_index([('title', pymongo.TEXT),
#                       ('skills', pymongo.TEXT), ('desc', pymongo.TEXT)])
# db.posts.index_information()
# db.posts.drop_index('query_loc_1_title_text_skills_text')
# import pdb; pdb.set_trace()  #### DEBUG


def all_tasks(request):
    """HTTP endpoint that lists running tasks and auto-scheduled tasks.

    Returns:
        Object for django html template
    """
    auto_tasks = PeriodicTask.objects.all().select_related('crontab')

    i = app.control.inspect()
    running_tasks = list(i.active().values())[0]
    running_tasks.extend(list(i.reserved().values())[0])

    form = ScraperForm()
    scraper_list = []  # create manual tasks list of scrapers
    scraper_params = ScraperParams.objects.all().order_by('id')
    for scraper in scraper_params:
        status = {'status': 'NOT QUERIED YET',
                  'display_result': '',
                  'progress': 0}
        if scraper.task_id:
            task = TaskResult.objects.filter(task_id=scraper.task_id)
            if task.count() > 0:
                status['display_result'] = get_display_results(scraper.task_id)
                status['status'] = task[0].status
        scraper_list.append((scraper, status))

    context = {'auto_tasks': auto_tasks,
               'running_tasks': running_tasks,
               'scraper_list': scraper_list,
               'form': form}
    return render(request, 'home/all_tasks.html', context)


def manual_tasks(request):
    """HTTP endpoint that lists manual tasks in ScraperParams table,
    with ability to start tasks and view progress.

    Returns:
        Object for django html template
    """
    form = ScraperForm()
    scraper_list = []  # create scraper list with scraper info for display
    scraper_params = ScraperParams.objects.all().order_by('id')
    for scraper in scraper_params:
        status = {'status': 'NOT QUERIED YET',
                  'display_result': '',
                  'progress': 0}
        if scraper.task_id:
            task = TaskResult.objects.filter(task_id=scraper.task_id)
            if task.count() > 0:
                status['display_result'] = get_display_results(scraper.task_id)
                status['status'] = task[0].status
        scraper_list.append((scraper, status))

    context = {
        'form': form,
        'scraper_list': scraper_list,
    }
    return render(request, 'home/manual_tasks.html', context)


def index(request):
    """HTTP endpoint that allows user to query jobposts with a keyword,
    displays a wordcloud and graph.

    Returns:
        Object for django html template
    """
    # GET FORM DATA
    if request.method != 'GET':
        form = UserQueryForm()  # create new form
        context = {'title': 'enter query', 'results': [], 'form': form}
        return render(request, 'home/index.html', context)
    form = UserQueryForm(request.GET)  # populate form with data from request
    if not form.is_valid():
        form = UserQueryForm()
        context = {'title': 'enter query', 'results': [], 'form': form}
        return render(request, 'home/index.html', context)

    # QUERY DATABASE VIA USER KEYWORDS
    start = time.time()
    query = form.cleaned_data['query']
    data = db_text_search(query)

    query_locs = ['raleigh, nc', 'chicago, il', 'dallas, tx']
    loc_posts = []
    for loc in query_locs:
        loc_posts.append({'loc': loc, 'posts': []})

    # TEXT PROCESSING
    start = time.time()
    word_counts = get_word_count(data['docs'])
    word_counts = [tup for tup in word_counts if tup[0] != query.lower()]
    words = [{'text': tup[0], 'size': tup[1]} for tup in word_counts]
    print('get_word_count() TIME: {:.3f}s'.format(time.time()-start))

    start = time.time()
    loc_graph_data = get_loc_week_counts(query)
    print('get_loc_week_counts() TIME: {:.3f}s'.format(time.time()-start))

    # PREPARE DATA FOR TEMPLATE
    context = {'query': query, 'res_count': data['match_count'],
               'all_posts': data['total_count'], 'form': form, 'words': words,
               'word_counts': word_counts, 'loc_graph_data': loc_graph_data}
    return render(request, 'home/index.html', context)

