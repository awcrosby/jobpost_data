from django.contrib import admin

# Register your models here.
from .models import SqlTest, Posts

admin.site.register(SqlTest)
admin.site.register(Posts)
