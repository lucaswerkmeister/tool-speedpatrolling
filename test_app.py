import mwoauth  # type: ignore
import pytest
import random
import string
import urllib.request

import app as speedpatrolling
import unicodescripts


def test_session_fits_in_cookie():
    base_rev_id = 850000000
    base_page_id = 60000000
    with speedpatrolling.app.test_client() as client:
        with client.session_transaction() as session:
            for rev_id in range(base_rev_id, base_rev_id + 10000):
                speedpatrolling.ids.append(session, 'skipped_rev_ids', rev_id)
            for page_id in range(base_page_id, base_page_id + 10000):
                speedpatrolling.ids.append(session, 'acted_page_ids', page_id)
            for page_id in range(base_page_id + 10000, base_page_id + 20000):
                speedpatrolling.ids.append(session, 'skipped_page_ids', page_id)
            for page_id in range(base_page_id + 20000, base_page_id + 30000):
                speedpatrolling.ids.append(session, 'ignored_page_ids', page_id)
            for user_number in range(1000):
                user_name = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
                speedpatrolling.ids.append(session, 'acted_user_fake_ids', speedpatrolling.ids.user_fake_id(user_name))
            for user_number in range(1000):
                user_name = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
                speedpatrolling.ids.append(session, 'skipped_user_fake_ids', speedpatrolling.ids.user_fake_id(user_name))
            for user_number in range(1000):
                user_name = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
                speedpatrolling.ids.append(session, 'ignored_user_fake_ids', speedpatrolling.ids.user_fake_id(user_name))
            session['csrf_token'] = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(64))
            access_token = mwoauth.AccessToken('%x' % random.getrandbits(128), '%x' % random.getrandbits(128))
            session['oauth_access_token'] = dict(zip(access_token._fields, access_token))
            # oauth_request_token not tested
            session['supported_scripts'] = list(unicodescripts.all_scripts())

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


def test_settings_anonymous():
    with speedpatrolling.app.test_request_context():
        speedpatrolling.settings()
    # did not throw
