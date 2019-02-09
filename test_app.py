import flask
import pytest
import urllib.request

import app as speedpatrolling


def test_ids_fit_in_session():
    base_rev_id = 850000000
    base_page_id = 60000000
    with speedpatrolling.app.test_client() as client:
        with client.session_transaction() as session:
            for rev_id in range(base_rev_id, base_rev_id + 10000):
                speedpatrolling.ids.append(session, 'skipped_rev_ids', rev_id)
            for page_id in range(base_page_id, base_page_id + 10000):
                speedpatrolling.ids.append(session, 'acted_page_ids', page_id)
            for page_id in range(base_page_id, base_page_id + 10000):
                speedpatrolling.ids.append(session, 'skipped_page_ids', page_id)
            for page_id in range(base_page_id, base_page_id + 10000):
                speedpatrolling.ids.append(session, 'ignored_page_ids', page_id)
        request = urllib.request.Request('http://localhost' + speedpatrolling.app.config.get('APPLICATION_ROOT', '/'))
        client.cookie_jar.add_cookie_header(request)
        header = request.get_header('Cookie')
        assert len(header) <= 4093


@pytest.mark.parametrize('val, expected', [
    ('Lucas Werkmeister', False),
    ('127.0.0.1', True),
    ('::1', True),
])
def test_is_ip_address(val, expected):
    actual = speedpatrolling.is_ip_address(val)
    assert expected == actual


@pytest.mark.parametrize('input, expected', [
    ('<a href="/wiki/Q42">Douglas Adams</a>', '<a href="https://www.wikidata.org/wiki/Q42">Douglas Adams</a>'),
    ('<a href="//en.wikipedia.org/wiki/Douglas_Adams">Douglas Adams</a>', '<a href="//en.wikipedia.org/wiki/Douglas_Adams">Douglas Adams</a>'),
])
def test_fix_markup(input, expected):
    actual = speedpatrolling.fix_markup(input)
    assert expected == actual
