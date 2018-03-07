from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('scraper/', views.scraper, name='scraper'),
    path('skills/', views.skills, name='skills'),
    path('auto_scraper/', views.auto_scraper, name='auto_scraper'),
    path('reset_scraper_schedule/', views.reset_scraper_schedule, name='reset_scraper_schedule'),
    path('ajax/get_task_progress/', views.get_task_progress, name='get_task_progress'),
    path('ajax/start_scraper/', views.start_scraper, name='start_scraper'),
]
