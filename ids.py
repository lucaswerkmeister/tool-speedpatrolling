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
            yield change['revid']
