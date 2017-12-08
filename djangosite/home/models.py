from django.db import models
from datetime import datetime
from django.contrib.postgres.fields import JSONField

# Create your models here.
class SqlTest(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    created_at = models.DateTimeField(default=datetime.now, blank=True)


class Posts(models.Model):
    data = JSONField()
    created_at = models.DateTimeField(default=datetime.now, blank=True)
    def __str__(self):
        return self.data['title']
    class Meta:
        verbose_name_plural = "Posts"
