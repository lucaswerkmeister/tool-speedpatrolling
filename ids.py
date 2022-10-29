import cachetools
import hashlib
import threading


class MyLRUCache(cachetools.LRUCache):
    """An LRU cache that does not consider item assignment as use."""

    def __setitem__(self, key, value, cache_setitem=cachetools.Cache.__setitem__):
        cache_setitem(self, key, value)
        # no self.__update(key)


rev_id_to_page_id_and_title_cache = MyLRUCache(maxsize=1024 * 1024)
rev_id_to_page_id_and_title_cache_lock = threading.RLock()
rev_id_to_user_fake_id_cache = MyLRUCache(maxsize=1024 * 1024)
rev_id_to_user_fake_id_cache_lock = threading.RLock()
title_to_show_patrol_footer_cache = cachetools.TTLCache(maxsize=1024 * 1024, ttl=5 * 60)  # time-to-live is in seconds
title_to_show_patrol_footer_cache_lock = threading.RLock()


def id_limit(name):
    if name.endswith('_user_fake_ids'):
        return 25
    elif name.endswith('_page_ids'):
        return 100
    else:
        return 250


def get(dict, name):
    """Get a list of IDs by name from a container."""
    ids = dict.get(name, [])
    return ids


def append(dict, name, id):
    """Append an ID to a list of IDs by that name in a container.

    The list is automatically limited to the most recent IDs,
    with the limit depending on the ID type (see id_limit).
    """
    ids = dict.get(name, [])
    ids = [id] + ids[:id_limit(name)]
    dict[name] = ids


def user_fake_id(user_name):
    return int.from_bytes(hashlib.sha256(user_name.encode('utf8')).digest()[:4], 'big')


@cachetools.cached(cache=rev_id_to_page_id_and_title_cache,
                   key=lambda rev_id, session: rev_id,
                   lock=rev_id_to_page_id_and_title_cache_lock)
def rev_id_to_page_id_and_title(rev_id, session):
    response = session.get(action='query',
                           revids=[rev_id],
                           formatversion=2)
    page = response['query']['pages'][0]
    return (page['pageid'], page['title'])

def rev_id_to_page_id(rev_id, session):
    return rev_id_to_page_id_and_title(rev_id, session)[0]

def rev_id_to_title(rev_id, session):
    return rev_id_to_page_id_and_title(rev_id, session)[1]


@cachetools.cached(cache=rev_id_to_user_fake_id_cache,
                   key=lambda rev_id, session: rev_id,
                   lock=rev_id_to_user_fake_id_cache_lock)
def rev_id_to_user_fake_id(rev_id, session):
    return user_fake_id(session.get(action='query',
                                    revids=[rev_id],
                                    prop=['revisions'],
                                    rvprop=['user'],
                                    formatversion=2)['query']['pages'][0]['revisions'][0]['user'])


def unpatrolled_changes(session):
    for result in session.get(action='query',
                              list='recentchanges',
                              rcprop=['ids', 'title', 'user'],
                              rcshow='unpatrolled',
                              rctype=['edit'],  # TODO consider including 'new' as well
                              rcnamespace=[
                                  0,  # Main (Item)
                                  120,  # Property
                                  146,  # Lexeme
                              ],
                              rclimit='max',
                              continuation=True):
        for change in result['query']['recentchanges']:
            with rev_id_to_page_id_and_title_cache_lock:
                rev_id_to_page_id_and_title_cache[change['revid']] = (change['pageid'], change['title'])
            with rev_id_to_user_fake_id_cache_lock:
                rev_id_to_user_fake_id_cache[change['revid']] = user_fake_id(change['user'])
            yield change['revid']


@cachetools.cached(cache=title_to_show_patrol_footer_cache,
                   key=lambda title, session: title,
                   lock=title_to_show_patrol_footer_cache_lock)
def title_to_show_patrol_footer(title, session):
    # roughly equivalent to Article::showPatrolFooter() –
    # if that returns true, iframe embedding is disabled to prevent clickjacking,
    # so we don’t want to show such pages to the user
    return bool(session.get(action='query',
                            list='recentchanges',
                            rctitle=title,
                            rctype=['new'],
                            rclimit=1,
                            rcshow=['!patrolled'],
                            rcprop=[])['query']['recentchanges'])

def rev_id_to_show_patrol_footer(rev_id, session):
    return title_to_show_patrol_footer(rev_id_to_title(rev_id, session), session)
