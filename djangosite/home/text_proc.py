import pymongo
import collections
import time
import textblob
import nltk
# nltk.download('stopwords')
from nltk.corpus import stopwords

client = pymongo.MongoClient('localhost', 27017)
db = client.jobpost_data

# extra stopwords needed when including job 'desc' along with 'skills'/'title'
stops = set(stopwords.words('english'))
stops |= set(['experience', 'client', 'position', 'include', 'time',
              'service', 'apply', 'design', 'build', 'system', 'testing',
              'integration', 'field', 'documentation', 'architecture',
              'dynamic', 'project', 'join', 'standards', 'email', 'location',
              'performance', 'key', 'focus', 'object', 'process', 'center',
              'server', 'components', 'scale', 'user', 'external', 'global',
              'local', 'processing', 'call', 'configuration', 'networking',
              'resources', 'protocols', 'frameworks'])


def get_word_count(dataset):
    # get count of single words
    allwords = []
    start = time.time()
    for doc in dataset:
        docwords = set()
        for field in ['skills', 'title', 'desc']:
            fieldwords = textblob.TextBlob(doc[field]).lower().words
            fieldwords = [i for w in fieldwords for i in w.split('/')]
            fieldwords = [i for w in fieldwords for i in w.split('-')]
            docwords = docwords.union(set(fieldwords))
        allwords.extend(docwords)
    print('after {} words, TIME: {:.3f}s'.format(len(allwords),
                                                 time.time()-start))
    allwords = [w for w in allwords if w not in stops]
    allwords = skill_whitelist(allwords)  # filter by stackoverflow skills
    count = collections.Counter(allwords)

    # # append top noun_phrases
    # allphrases = []
    # for doc in dataset:
    #     docphrases = textblob.TextBlob(doc['skills']).lower().noun_phrases
    #     allphrases.extend(docphrases)
    # count += collections.Counter(allphrases)
    # print('after phrases, TIME: {:.3f}s'.format((time.time()-start)))
    # print(collections.Counter(allphrases).most_common(20))

    return count.most_common(40)


def db_text_search(query, query_loc):
    cur = db.posts.find({'query_loc': query_loc,
                         '$text': {'$search': query}})
    return [doc for doc in cur]


def skill_whitelist(skills_to_filter):
    whitelist = db.skills.find_one({'source': 'stackoverflow'})['skills']
    whitelist = set(whitelist)
    ''' FYI top skills in 'desc' are design, env, position, client, comm
        using, system, project... if whitelist had only true tech skills
        then could count words in 'desc' field (but takes ~3.7sec) '''
    return [s for s in skills_to_filter if s in whitelist]


# def skill_relations():
#     # create a map from skill to jobpost in database
#     start = time.time()
#     skill_map = {}
#     for job in db.posts.find({}, {'skills': 1, '_id': 1}):
#         words = textblob.TextBlob(job['skills']).lower().words
#         words = [w for w in words if w not in stops]
#         for word in words:
#             skill_map[word] = skill_map.get(word, []) + [job['_id']]
#
#     # get top_skills
#     top_skills = [s[0] for s in get_word_count('skills')]
#     top_skills = list(itertools.combinations(top_skills, 2))
#
#     # compare top skills to map
#     relations = []
#     for s1, s2 in top_skills:
#         set1 = set(skill_map[s1])
#         set2 = set(skill_map[s2])
#         relations.append([s1, s2, len(set1.intersection(set2))])
#         relations.append([s2, s1, len(set1.intersection(set2))])
#
#     # relations.sort(key=lambda x: x[2], reverse=True)
#     print('for {} combos, TIME: {:.3f}s'.format(len(relations),
#                                                 time.time()-start))
#     return relations
#
#
# def employer_skill_relations():
#     top_skills = [s[0] for s in get_word_count('skills')]
#     top_employers = get_top_employers()
#     return None
#
#
# def title_skill_relations():
#     top_skills = [s[0] for s in get_word_count('skills')]
#     top_titles = get_top_titles()
#     return None
#
#
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
