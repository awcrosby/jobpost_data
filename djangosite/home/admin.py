from django.contrib import admin

# Register your models here.
from .models import JobSite, QueryLoc, ScraperParams

admin.site.register(ScraperParams)
admin.site.register(JobSite)
admin.site.register(QueryLoc)
