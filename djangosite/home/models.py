from django.db import models
from datetime import datetime
from django.contrib.postgres.fields import JSONField

# Create your models here.
class QueryLoc(models.Model):
    # Model representing the locations that can can be queried
    name = models.CharField(max_length=50)
    query = models.CharField(max_length=50)
    def __str__(self):  # string to represent Model object in admin
        return self.name

class JobSite(models.Model):
    # Model representing the job sites that can scraper can query
    name = models.CharField(max_length=50)
    url = models.CharField(max_length=50)
    def __str__(self):  # string to represent Model object in admin
        return self.name

class ScraperParams(models.Model):
    # Model representing params used to scrape for job postings
    query = models.CharField(max_length=50, blank=True)
    job_site = models.ForeignKey(JobSite, on_delete=models.SET_NULL, null=True)
    query_loc = models.ForeignKey(QueryLoc, on_delete=models.SET_NULL, null=True)
    last_queried = models.DateTimeField(null=True, blank=True)
    task_id = models.CharField(max_length=50, blank=True)
    status = models.TextField(blank=True)
    def __str__(self):  # string to represent Model object in admin
        return '{} q="{}" in "{}", {}'.format(self.job_site.name,
            self.query, self.query_loc.query, self.status)
    class Meta:
        verbose_name_plural = "Scraper params"
