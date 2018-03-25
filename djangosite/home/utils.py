from .models import ScraperParams, QueryLoc
from .tasks import scrape_dice, get_stackoverflow_skills
from django.http import HttpResponse
from celery.result import AsyncResult
from django_celery_results.models import TaskResult
from django_celery_beat.models import CrontabSchedule, PeriodicTask
from random import randint
import json
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_display_results(task_id):
    """Get a task result to display to user.

    Args:
        task_id (int): task id to look up in TaskResult table

    Returns:
        string: Result string to display
    """
    display_result = ''
    task = TaskResult.objects.get(task_id=task_id)
    if task.status == 'FAILURE':
        display_result = json.loads(task.result)['exc_type']
    elif task.status == 'SUCCESS':
        display_result = '{} posts scraped on {} UTC'.format(
            json.loads(task.result)['jobposts'],
            #task.date_done.strftime('%Y-%m-%d %H:%M'))
            task.date_done.strftime('%B %d, %Y %I:%M %p'))
    return display_result


def reload_locations(request):
    """Add or reload query locations from file. Allows location list to be stored in file.
    This deletes all existing locations before adding.
    All ScraperParams are deleted since they rely on locations.

    Function callable via http / ajax request.

    Returns:
        HttpResponse with json: simple success or error text
    """
    data = 'error'
    if request.is_ajax():
        ScraperParams.objects.all().delete()
        QueryLoc.objects.all().delete()
        with open(os.path.join(BASE_DIR, 'locs.json')) as f:
            locs = json.loads(f.read())
        for loc in locs:
            QueryLoc.objects.create(
                name=loc,
                query=loc
            )
        data = {'response': 'query locations successfully reloaded'}
    json_data = json.dumps(data)
    return HttpResponse(json_data, content_type='application/json')


def reset_scraper_schedule(request):
    """Sets/resets many Crontab entries at random times for specified days.
    Sets/resets a PeriodicTask for each QueryLoc + specified day combination,
    with a random Crontab.

    Function callable via http / ajax request.

    Returns:
        HttpResponse with json: simple success or error text
    """
    data = 'error'
    if request.is_ajax():  
        # set/reset Crontab with many entries
        CrontabSchedule.objects.all().delete()
        days_to_scrape = [1, 3, 5]
        for day in days_to_scrape:
            for hour in range(1,24):
                CrontabSchedule.objects.create(
                    minute=randint(1,59),
                    hour=hour,
                    day_of_week=day
                )

        # set/reset PeriodicTask based on QueryLoc, days_to_scrape, and random Crontab
        PeriodicTask.objects.all().delete()
        for loc in QueryLoc.objects.all():
            for day in days_to_scrape:
                PeriodicTask.objects.create(
                    crontab=CrontabSchedule.objects.filter(day_of_week=day).order_by('?').first(),
                    name='scrape dice day#{} for: {}'.format(day, loc.query),
                    task='djangosite.home.tasks.scrape_dice',
                    kwargs=json.dumps({'query': '', 'query_loc': loc.query})
                )
        data = {'response': 'auto scraper crontabs and periodic tasks successfully reset'}
    json_data = json.dumps(data)
    return HttpResponse(json_data, content_type='application/json')


def skills_update(request):
    """Starts get_stackoverflow_skills task.

    Function callable via http / ajax request.

    Returns:
        HttpResponse with json: simple success or error text
    """
    data = 'error'
    if request.is_ajax():
        get_stackoverflow_skills.delay()
        data = {'response': 'skills update task started'}
    json_data = json.dumps(data)
    return HttpResponse(json_data, content_type='application/json')


def start_scraper(request):
    """Starts scrape_dice task based on ScraperParams manaual scrape object clicked.

    Args:
        request (POST): includes scraper_id
        Function callable via http / ajax request.

    Returns:
        HttpResponse with json: task_id associated with this scraper_id
    """
    data = 'error'
    if request.is_ajax():
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
    """Get active task's status, percentage, and display result.

    Args:
        request (POST): includes task_id
        Function callable via http / ajax request.

    Returns:
        HttpResponse with json: dictionary with progress key value pairs
    """
    data = 'error'
    if request.is_ajax():
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
