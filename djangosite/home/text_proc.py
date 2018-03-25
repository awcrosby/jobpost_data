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
    #cur = db.posts.find({'query_loc': query_loc,
    #                     '$text': {'$search': query}})

    ## speed: 29, 43/hang, 36 for py, j, js... with 8w being 94k
    #total_count =  db.posts.find({
    #    'posted': {'$gte': datetime.utcnow() - timedelta(weeks=8)}
    #}).count()
    #cur = db.posts.find({
    #    'posted': {'$gte': datetime.utcnow() - timedelta(weeks=8)},
    #    '$text': {'$search': query}
    #})
    total_count =  db.posts.find({
        'posted_week': {'$in': [12, 11, 10, 9, 8, 7]}
    }).count()
    cur = db.posts.find({
        'posted_week': {'$in': [12, 11, 10, 9, 8, 7]},
        '$text': {'$search': query}
    })
    #cur = db.posts.find({
    #    'posted_week': 12,
    #    '$text': {'$search': query}
    #})
    result_docs = [doc for doc in cur] 

    # get count of query_loc by week
    locs_counter = collections.Counter()
    for doc in result_docs:
        locs_counter[(doc['query_loc'], doc['posted_week'])] += 1

    return (result_docs, total_count, locs_counter)


def db_query_by_date(query, query_loc):
    """Query mongodb for count of matching docs by groups of n days
    
    Return:
        List: count of docs in last n*1 days, last n*2 days, etc.
    """
    n = 3
    count_by_date = []
    locs = []
    for i in range(6):
        locs.append(['new york, ny', 'seattle, wa', 'dallas, tx', 'chicago, il', 'san jose, ca'])
    print('len(locs):', len(locs))
    for loc in locs:
        for daygroup in range(1, 9):
            c = db.posts.find({
                'posted_week': 12,
                'query_loc': loc,
                '$text': {'$search': query}
            })
            #c = db.posts.find({
            #    'query_loc': loc,
            #    '$text': {'$search': query},
            #    'posted': {
            #        '$lt': datetime.utcnow() - timedelta(days=n*(daygroup-1)),
            #        '$gte': datetime.utcnow() - timedelta(days=n*daygroup)}
            #})
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
