# jobpost_data

Framework to run manual tasks (click to start), and automated tasks (scheduled) configurable via the database. Applied to task of gathering job postings... Jobpost user interface displays skills found in user query, and query result counts across US tech cities.

## Technical

### Stack
Linux, Nginx/Gunicorn, PostgreSQL/MongoDB, Python/Django

### Additional Details
* Webserver + framework: Nginx/Gunicorn, Python/Django
* Task management: Celery, RabbitMQ message broker, celery beat scheduler
* Database: PostgreSQL for Celery results, MongoDB for document storage
* DevOps: AWS, Ansible, ufw, fail2ban
* Dev Environment: Ubuntu, vim/tmux, github
* UI Presentation: Bootstrap, some custom CSS

## Setting up the project

Locally, set remote IP in `nginx_config_pre_ssl` and ansible `inventory`, and edit `vars.yml` to set postgres password and secret key which will be copied to remote
```
$ vim config/nginx_config_pre_ssl
$ vim config/ansible/inventory
$ vim config/ansible/vars.yml
```

Locally, use ansible to configure a remote Ubuntu 16.04 box
```
$ ssh-agent bash
$ ssh-add /path/to/private/key
$ cd config/ansible
$ ansible-playbook -i inventory site_init_clone.yml
$ ansible-playbook -i inventory site_db_celery.yml
```

On remote, add server IP to ALLOWED_HOSTS
```
$ cd ~/jobpost_data
$ vim djangosite/settings.py
```

On remote, create your admin superuser
```
$ source venv/bin/activate
$ python manage.py createsuperuser
$ sudo service gunicorn restart
$ sudo service nginx restart
```

Go to web site in browser, go to Settings, and login with Django superuser account. Under Settings, click the 3 buttons to initialize data
* Skills list is set by scraping Stackoverflow tags
* City query locations are set from file `djangosite/locs.json`
* Auto Scraper Crontabs and Scheduled Tasks are set for random times on various days via `djangosite/home/utils.py`

Add entry to Admin > Scraper Params table to create a new manual task. Go to Tasks > Manual Tasks to start

You can now go to Jobposts and query the dataset, which looks at data posted from 6 weeks ago to 1 week ago

___

##### Wordcloud libraries used:
* https://github.com/wvengen/d3-wordcloud
* https://github.com/jasondavies/d3-cloud
