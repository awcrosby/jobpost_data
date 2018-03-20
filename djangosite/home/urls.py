from django.urls import path
from . import views, utils

urlpatterns = [
    path('', views.index, name='index'),
    path('manual_tasks/', views.manual_tasks, name='manual_tasks'),
    path('all_tasks/', views.all_tasks, name='all_tasks'),
    path('ajax/reset_scraper_schedule/', utils.reset_scraper_schedule, name='reset_scraper_schedule'),
    path('ajax/skills_update/', utils.skills_update, name='skills_update'),
    path('ajax/reload_locations/', utils.reload_locations, name='reload_locations'),
    path('ajax/get_task_progress/', utils.get_task_progress, name='get_task_progress'),
    path('ajax/start_scraper/', utils.start_scraper, name='start_scraper'),
]
