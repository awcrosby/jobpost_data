# jobpost_data

Framework to run manual tasks (click to start), and automated tasks (scheduled) configurable via the database. Applied to task of gathering job postings... Jobpost user interface displays skills found in user query, and ____

## Setting up the project

Locally use ansible to configure a remote Ubuntu 16.04 box (add remote ip to `inventory`)
```
$ ssh-agent bash
$ ssh-add /path/to/private/key
$ cd config/ansible
$ ansible-playbook -i inventory site_init_clone.yml
```

Edit `vars.yml` on local and remote to set postres password and secret key
```
$ vim config/ansible/vars.yml
```

Locally finish ansible configuration
```
$ ansible-playbook -i inventory site_db_celery.yml
```

On remote add server ip to ALLOWED_HOSTS
```
$ vim djangosite/settings.py
```

On remote create your admin superuser
```
$ source venv/bin/activate
$ python manage.py createsuperuser
```
