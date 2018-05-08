import pymongo
import collections
import time
import re
from datetime import datetime, timedelta
from .models import QueryLoc
from operator import itemgetter
import sys
import logging

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)

client = pymongo.MongoClient('localhost', 27017)
db = client.jobpost_data

# nltk stopwords
stops = set(['how', 'be', 'me', 'all', 'own', 'those', "mightn't", 'needn',
    'which', 'it', 'to', 'hers', 'my', 'then', 'other', 'mustn', 't', 'isn',
    'wasn', 'myself', 'further', 'now', "isn't", 'from', 'more', "hadn't",
    'whom', 'hadn', "shouldn't", 'theirs', 'what', 'has', 'if', 'because',
    'same', 'don', 'm', 'each', 'had', 'where', 'doesn', 'again', 'not',
    'will', 'couldn', "wouldn't", 'herself', 'are', 'itself', "you'd", 'on',
    'that', 'a', 'haven', 'been', 'once', 'do', 'was', 'after', "don't",
    'into', 'under', 'mightn', 'down', 'too', 'wouldn', "you'll", 'against',
    'but', "hasn't", 'her', 'y', 'such', "she's", 'while', 'very', "aren't",
    'they', 'and', 'should', "you're", 'nor', 'is', "you've", 've', 'over',
    'themselves', 'were', 'at', 'yours', "won't", 'before', 'himself', 'ain',
    "should've", 'am', 'any', "needn't", 'shan', 'few', 'i', 'the', 'most',
    'below', 'by', "weren't", 'for', 'll', 'we', "mustn't", 'he', 'or', 'didn',
    'hasn', 'just', 'won', 'you', 'shouldn', 'who', 'here', 'yourself', 'them',
    're', "haven't", 'there', 'only', 'ours', 'having', 'his', 'during',
    'until', 'being', 'its', 'can', 'this', 'through', 'aren', 'off', 'your',
    'between', 'as', 'why', 'some', 'so', 'these', 'did', "shan't", 'with',
    'ourselves', 'up', 'in', 'their', 'when', 'both', 'o', 'yourselves',
    'above', "wasn't", "it's", 'than', 'him', "that'll", 'does', "doesn't",
    'ma', 'doing', 'weren', 'out', 's', 'about', 'she', 'an', 'd', "didn't",
    'of', "couldn't", 'have', 'our', 'no'])

# extra stopwords needed for common words in job post data
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
    logger.info('starting db_text_search() for list_of_weeks: {}'.format(list_of_weeks))
    total_count =  db.posts.find({
        'posted_week': {'$in': list_of_weeks}
    }).count()

    start = time.time()
    match_count = db.posts.find({
        'posted_week': {'$in': list_of_weeks},
        '$text': {'$search': query}
    }).count()
    logger.info('got match_count of {} in TIME: {:.3f}s'.format(match_count, time.time()-start))

    start = time.time()
    cur = db.posts.aggregate([
        {'$match': {
            'posted_week': {'$in': list_of_weeks},
            '$text': {'$search': query}}
        },
        {'$sample': {'size': 10}}
    ])
    docs = list(cur)
    logger.info('sampled query matches in TIME: {:.3f}s'.format(time.time()-start))

    return {'match_count': match_count,
            'total_count': total_count,
            'docs': docs}


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
        for week in range(min(list_of_weeks), max(list_of_weeks)+1):
            post_count = loc_post.get(week, 0)
            loc_post['posts'].append(post_count)
        loc_post['total'] = sum(loc_post['posts'])

    loc_posts = sorted(loc_posts, key=itemgetter('total'), reverse=True)

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
            logger.error('timeout while scanning mongo docs')
            return 'timeout'

    allwords = [w.lower() for w in allwords]
    allwords = [w for w in allwords if w not in stops]

    # filter by stackoverflow skill tags
    whitelist = db.skills.find_one({'source': 'stackoverflow'})['skills']
    whitelist = set(whitelist)
    allwords = [w for w in allwords if w in whitelist]

    count = collections.Counter(allwords)
    return count.most_common(80)


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
