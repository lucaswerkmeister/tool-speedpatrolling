import cachetools
import threading


class MyLRUCache(cachetools.LRUCache):
    """An LRU cache that does not consider item assignment as use."""

    def __setitem__(self, key, value, cache_setitem=cachetools.Cache.__setitem__):
        cache_setitem(self, key, value)
        # no self.__update(key)


rev_id_to_page_id_cache = MyLRUCache(maxsize=1024*1024)
rev_id_to_page_id_cache_lock = threading.RLock()


def get(dict, name):
    """Get a list of IDs by name from a container.

    The list is automatically limited to the 1000 highest IDs.
    """
    ids = dict.get(name, [])
    ids.sort(reverse=True)
    del ids[1000:]
    dict[name] = ids
    return ids


def append(dict, name, id):
    """Append an ID to a list of IDs by that name in a container."""
    ids = dict.get(name, [])
    ids.append(id)
    dict[name] = ids


@cachetools.cached(cache=rev_id_to_page_id_cache,
                   key=lambda rev_id, session: rev_id,
                   lock=rev_id_to_page_id_cache_lock)
def rev_id_to_page_id(rev_id, session):
    return session.get(action='query',
                       revids=[rev_id],
                       formatversion=2)['query']['pages'][0]['pageid']


def unpatrolled_changes(session):
    for result in session.get(action='query',
                              list='recentchanges',
                              rcprop=['ids'],
                              rcshow='unpatrolled',
                              rctype=['edit'], # TODO consider including 'new' as well
                              rclimit='max',
                              continuation=True):
        for change in result['query']['recentchanges']:
            with rev_id_to_page_id_cache_lock:
                rev_id_to_page_id_cache[change['revid']] = change['pageid']
            yield change['revid']
