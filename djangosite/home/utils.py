from django_celery_results.models import TaskResult
import json

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
