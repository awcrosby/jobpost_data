import pymongo
import collections
import time
import nltk
import re
from datetime import datetime, timedelta
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


def db_text_search(query, query_loc):
    """Return mongo docs via text search for given location"""
    cur = db.posts.find({'query_loc': query_loc,
                         '$text': {'$search': query}})
    return [doc for doc in cur]


def db_query_by_date(query, query_loc):
    """Query mongodb for count of matching docs by groups of n days
    
    Return:
        List: count of docs in last n*1 days, last n*2 days, etc.
    """
    n = 3
    count_by_date = []
    for daygroup in range(1, 9):
        c = db.posts.find({
            'query_loc': query_loc,
            '$text': {'$search': query},
            'posted': {
                '$lt': datetime.utcnow() - timedelta(days=n*(daygroup-1)),
                '$gte': datetime.utcnow() - timedelta(days=n*daygroup)}
        })
        count_by_date.append(c.count())

    return count_by_date


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
    print('parse {}, TIME: {:.3f}s'.format(len(allwords), time.time()-start))

    allwords = [w.lower() for w in allwords]
    allwords = [w for w in allwords if w not in stops]

    # filter by stackoverflow skill tags
    whitelist = db.skills.find_one({'source': 'stackoverflow'})['skills']
    whitelist = set(whitelist)
    allwords = [w for w in allwords if w in whitelist]

    count = collections.Counter(allwords)
    print('after stop/skills/count, TIME: {:.3f}s'.format(time.time()-start))
    return count.most_common(60)


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
