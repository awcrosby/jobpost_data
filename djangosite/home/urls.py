from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('scraper/', views.scraper, name='scraper'),
    path('skills/', views.skills, name='skills'),
]
