from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('scraper/', views.scraper, name='scraper'),
    path('skills/', views.skills, name='skills'),
    path('ajax/get_task_progress/', views.get_task_progress, name='get_task_progress'),
    path('ajax/start_scraper/', views.start_scraper, name='start_scraper'),
]
