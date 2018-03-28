import pymongo
import collections
import time
import nltk
import re
from datetime import datetime, timedelta
from .models import QueryLoc
# nltk.download('stopwords')
from nltk.corpus import stopwords

client = pymongo.MongoClient('localhost', 27017)
db = client.jobpost_data

# extra stopwords needed when including job 'desc' along with 'skills'/'title'
stops = set(stopwords.words('english'))
stops |= set(['', 'experience', 'client', 'position', 'include', 'time',
              'service', 'apply', 'design', 'build', 'system', 'testing',
              'integration', 'field', 'documentation', 'architecture',
              'dynamic', 'project', 'join', 'standards', 'email', 'location',
              'performance', 'key', 'focus', 'object', 'process', 'center',
              'server', 'components', 'scale', 'user', 'external', 'global',
              'local', 'processing', 'call', 'configuration', 'networking',
              'resources', 'protocols', 'frameworks', 'click'])


def db_text_search(query, total_weeks=6):
    """Return mongo docs via text search for given number of weeks """
    list_of_weeks = get_list_of_weeks(total_weeks)
    total_count =  db.posts.find({
        'posted_week': {'$in': list_of_weeks}
    }).count()

    cur = db.posts.find({
        'posted_week': {'$in': list_of_weeks},
        '$text': {'$search': query}
    })

    result_docs = list(cur)
    return (result_docs, total_count)


def get_loc_week_counts(query, total_weeks=6):
    """Gets counts of posts by location and week

    Return:
        List of dicts with 'loc' string and 'posts' list of plot values
    """
    # find the docs based on query
    list_of_weeks = get_list_of_weeks(total_weeks)
    pipeline = [
        {'$match': {
            'posted_week': {'$in': list_of_weeks},
            '$text': {'$search': query}}
        },
        {'$project': {
            '_id': 0,
            'query_loc': 1,
            'posted_week': 1}
        }
    ]

    # count num of posts by query_loc + week number
    pipeline.append(
        {
            '$group': {
                '_id': {'loc': '$query_loc', 'week_num': '$posted_week'},
                'count': {'$sum': 1}
            }
        }
    )
    cursor = db.posts.aggregate(pipeline)

    # change data format so graph can display it
    locs = [l.lower() for l in QueryLoc.objects.values_list('query', flat=True)]
    loc_posts = []
    for loc in locs:
        loc_posts.append({'loc': loc, 'posts': []})

    for d in cursor:
        loc = d['_id']['loc']
        week = d['_id']['week_num']
        posts = d['count']
        loc_post = list(filter(lambda loc_post: loc_post['loc'] == loc, loc_posts))[0]
        loc_post[week] = posts

    for loc_post in loc_posts:
        for week in range(7, 13):
            post_count = loc_post.get(week, 0)
            loc_post['posts'].append(post_count)

    return loc_posts


def get_word_count(mongo_docs):
    """Return Counter of most common words in passed docs"""
    allwords = []
    start = time.time()
    for i, doc in enumerate(mongo_docs):
        docwords = set()
        for field in ['skills', 'title', 'desc']:
            fieldwords = re.split('\-| |,|\. |; |: |\/|\n|\(|\)', doc[field])
            docwords = docwords.union(set(fieldwords))
        allwords.extend(docwords)
        if time.time()-start > 30:
            print('timeout while scanning mongo docs')
            return 'timeout'
    #print('parse {}, TIME: {:.3f}s'.format(len(allwords), time.time()-start))

    allwords = [w.lower() for w in allwords]
    allwords = [w for w in allwords if w not in stops]

    # filter by stackoverflow skill tags
    whitelist = db.skills.find_one({'source': 'stackoverflow'})['skills']
    whitelist = set(whitelist)
    allwords = [w for w in allwords if w in whitelist]

    count = collections.Counter(allwords)
    #print('counter TIME: {:.3f}s'.format(time.time()-start))
    return count.most_common(60)


def get_list_of_weeks(total_weeks=6):
    """Helper func, returns list of previous week numbers from today

    Assumes no more than 11 months of data in the database
    """
    current_week = datetime.utcnow().isocalendar()[1]
    list_of_weeks = []
    for i in range(current_week-1, current_week-1-total_weeks, -1):
        if i > 0:
            list_of_weeks.append(i)
        else:
            list_of_weeks.append(i+52)
    return list_of_weeks


# def get_top_employers():
#     cur = db.posts.find({}, {'employer': 1, '_id': 0})
#     employers = [i['employer'].lower() for i in cur]
#     return collections.Counter(employers).most_common(10)
#
#
# def get_top_titles():
#     cur = db.posts.find({}, {'title': 1, '_id': 0})
#     titles = [i['title'].lower() for i in cur]
#     return collections.Counter(titles).most_common(10)
