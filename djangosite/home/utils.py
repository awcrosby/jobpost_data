from django_celery_results.models import TaskResult
from django.http import HttpResponse
from .tasks import scrape_dice, get_stackoverflow_skills
import json
from .forms import ScraperForm
from .models import ScraperParams, QueryLoc
from celery.result import AsyncResult


def get_display_results(task_id):
    display_result = ''
    task = TaskResult.objects.get(task_id=task_id)
    if task.status == 'FAILURE':
        display_result = json.loads(task.result)['exc_type']
    elif task.status == 'SUCCESS':
        display_result = '{} posts scraped on {} UTC'.format(
            json.loads(task.result)['jobposts'],
            task.date_done.strftime('%Y-%m-%d %H:%M'))
    return display_result


def reload_locations(request):  ## add city locations from file
    data = 'error'
    if request.is_ajax():  # ajax view to get progress of task
        #QueryLoc.objects.all().delete()
        #with open(os.path.join(BASE_DIR, 'locs.json')) as f:
        #    locs = json.loads(f.read())
        #for loc in locs:
        #    QueryLoc.objects.create(
        #        name=loc,
        #        query=loc
        #    )
        data = {'response': 'query locations successfully reloaded'}
    json_data = json.dumps(data)
    return HttpResponse(json_data, content_type='application/json')


def skills_update(request):
    data = 'error'
    if request.is_ajax():  # ajax view to get progress of task
        get_stackoverflow_skills.delay()
        data = {'response': 'skills update task started'}
    json_data = json.dumps(data)
    return HttpResponse(json_data, content_type='application/json')


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
