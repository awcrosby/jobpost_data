import pymongo
import collections
import time
import textblob
import nltk
import re
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
    cur = db.posts.find({'query_loc': query_loc,
                         '$text': {'$search': query}})
    return [doc for doc in cur]


def get_word_count(dataset):
    # get count of single words
    allwords = []
    start = time.time()
    for i, doc in enumerate(dataset):
        docwords = set()
        for field in ['skills', 'title', 'desc']:
            fieldwords = re.split('\-| |,|\. |; |: |\/|\n|\(|\)', doc[field])
            docwords = docwords.union(set(fieldwords))
        allwords.extend(docwords)
    print('parse {}, TIME: {:.3f}s'.format(len(allwords), time.time()-start))
    allwords = [w.lower() for w in allwords]
    allwords = [w for w in allwords if w not in stops]
    allwords = skill_whitelist(allwords)  # filter by stackoverflow skills
    count = collections.Counter(allwords)
    print('after stop/skills/count, TIME: {:.3f}s'.format(time.time()-start))
    return count.most_common(60)


def skill_whitelist(skills_to_filter):
    whitelist = db.skills.find_one({'source': 'stackoverflow'})['skills']
    whitelist = set(whitelist)
    ''' FYI top skills in 'desc' are design, env, position, client, comm
        using, system, project... if whitelist had only true tech skills
        then could count words in 'desc' field (but takes ~3.7sec) '''
    return [s for s in skills_to_filter if s in whitelist]


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
