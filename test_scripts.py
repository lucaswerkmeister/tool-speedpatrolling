import pytest

import scripts


@pytest.mark.parametrize('text, expected_scripts', [
    ('lorem ipsum dolor sit amet', ['Latin']),
    ('.,-0123456789', []),
    ('', []),
    ('The resistance must not exceed 10 kΩ.', ['Latin', 'Greek']),
    ('αβγАБВГ', ['Cyrillic', 'Greek']),
    ('汉字', ['Han']),
    ('𐐔𐐯𐑅𐐨𐑉𐐯𐐻', ['Deseret']), # Supplementary Multilingual Plane
    ([char for text in ['abc', 'ᚁᚂᚃᚄ'] for char in text], ['Ogham', 'Latin']), # list
    ((char for text in ['ᚠᚡ', '𓀀'] for char in text), ['Runic', 'Egyptian_Hieroglyphs']), # generator
])
def test_scripts_of_text(text, expected_scripts):
    actual_scripts = scripts.scripts_of_text(text)
    assert expected_scripts == actual_scripts


@pytest.mark.parametrize('html, expected_script', [
    # label
    ('<tr><td colspan="2" class="diff-lineno">label / ru</td><td colspan="2" class="diff-lineno">label / ru</td></tr><tr><td colspan="2">&nbsp;</td><td class="diff-marker">+</td><td class="diff-addedline"><div><ins class="diffchange diffchange-inline">рус</ins></div></td></tr>', 'Cyrillic'),
    # description
    ('<tr><td colspan="2" class="diff-lineno">description / zh-hans</td><td colspan="2" class="diff-lineno">description / zh-hans</td></tr><tr><td colspan="2">&nbsp;</td><td class="diff-marker">+</td><td class="diff-addedline"><div><ins class="diffchange diffchange-inline">安徽省合肥市下辖县</ins></div></td></tr>', 'Han'),
    # aliases, description
    ('<tr><td colspan="2" class="diff-lineno">aliases / fr / 0</td><td colspan="2" class="diff-lineno">aliases / fr / 0</td></tr><tr><td colspan="2">&nbsp;</td><td class="diff-marker">+</td><td class="diff-addedline"><div><ins class="diffchange diffchange-inline">Guillaume, Phvango</ins></div></td></tr><tr><td colspan="2" class="diff-lineno">aliases / fr / 1</td><td colspan="2" class="diff-lineno">aliases / fr / 1</td></tr><tr><td class="diff-marker">-</td><td class="diff-deletedline"><div><del class="diffchange diffchange-inline">Louise Gabrielle Bobb</del></div></td></tr><tr><td colspan="2" class="diff-lineno">description / fr</td><td colspan="2" class="diff-lineno">description / fr</td></tr><tr><td class="diff-marker">-</td><td class="diff-deletedline"><div><del class="diffchange diffchange-inline">chanteuse anglaise</del></div></td></tr>', 'Latin'),
    # sitelink
    ('<tr><td colspan="2" class="diff-lineno">links / hywiki / name</td><td colspan="2" class="diff-lineno">links / hywiki / name</td></tr><tr><td colspan="2">&nbsp;</td><td class="diff-marker">+</td><td class="diff-addedline"><div><ins class="diffchange diffchange-inline"><a dir="auto" href="https://hy.wikipedia.org/wiki/%D5%8D%D5%A5%D5%B4%D5%B8%D6%82%D5%B5%D5%A5%D5%AC_%D4%BC%D5%AB%D5%A9%D5%AC" hreflang="hy">Սեմույել Լիթլ</a></ins></div></td></tr>', 'Armenian'),
    # Commons media
    ('<tr><td colspan="2" class="diff-lineno"></td><td colspan="2" class="diff-lineno">Property / <a title="Property:P18" href="/wiki/Property:P18">image</a></td></tr><tr><td colspan="2">&nbsp;</td><td class="diff-marker">+</td><td class="diff-addedline"><div><ins class="diffchange diffchange-inline"><span><a class="extiw" href="//commons.wikimedia.org/wiki/File:Bruno-H.-B%C3%BCrgel-Sternwarte.jpg">Bruno-H.-Bürgel-Sternwarte.jpg</a></span></ins></div></td></tr><tr><td colspan="2" class="diff-lineno"></td><td colspan="2" class="diff-lineno">Property / <a title="Property:P18" href="/wiki/Property:P18">image</a>: <a class="extiw" href="//commons.wikimedia.org/wiki/File:Bruno-H.-B%C3%BCrgel-Sternwarte.jpg">Bruno-H.-Bürgel-Sternwarte.jpg</a> / rank</td></tr><tr><td colspan="2">&nbsp;</td><td class="diff-marker">+</td><td class="diff-addedline"><div><ins class="diffchange diffchange-inline"><span>Normal rank</span></ins></div></td></tr>', 'Latin'),
    # monolingual text
    ('<tr><td colspan="2" class="diff-lineno"></td><td colspan="2" class="diff-lineno">Property / <a title="Property:P1559" href="/wiki/Property:P1559">name in native language</a></td></tr><tr><td colspan="2">&nbsp;</td><td class="diff-marker">+</td><td class="diff-addedline"><div><ins class="diffchange diffchange-inline"><span><span class="wb-monolingualtext-value" lang="it">Pialuisa Bianco</span> <span class="wb-monolingualtext-language-name" dir="auto">(Italian)</span></span></ins></div></td></tr><tr><td colspan="2" class="diff-lineno"></td><td colspan="2" class="diff-lineno">Property / <a title="Property:P1559" href="/wiki/Property:P1559">name in native language</a>: <span class="wb-monolingualtext-value" lang="it">Pialuisa Bianco</span> <span class="wb-monolingualtext-language-name" dir="auto">(Italian)</span> / rank</td></tr><tr><td colspan="2">&nbsp;</td><td class="diff-marker">+</td><td class="diff-addedline"><div><ins class="diffchange diffchange-inline"><span>Normal rank</span></ins></div></td></tr>', 'Latin'),
    # external identifier
    ('<tr><td colspan="2" class="diff-lineno"></td><td colspan="2" class="diff-lineno">Property / <a title="Property:P2949" href="/wiki/Property:P2949">WikiTree person ID</a></td></tr><tr><td colspan="2">&nbsp;</td><td class="diff-marker">+</td><td class="diff-addedline"><div><ins class="diffchange diffchange-inline"><span><a class="wb-external-id" href="https://www.wikitree.com/wiki/Fignol%C3%A9-1">Fignolé-1</a></span></ins></div></td></tr><tr><td colspan="2" class="diff-lineno"></td><td colspan="2" class="diff-lineno">Property / <a title="Property:P2949" href="/wiki/Property:P2949">WikiTree person ID</a>: <a class="wb-external-id" href="https://www.wikitree.com/wiki/Fignol%C3%A9-1">Fignolé-1</a> / rank</td></tr><tr><td colspan="2">&nbsp;</td><td class="diff-marker">+</td><td class="diff-addedline"><div><ins class="diffchange diffchange-inline"><span>Normal rank</span></ins></div></td></tr>', None),
    # item
    ('<tr><td colspan="2" class="diff-lineno"></td><td colspan="2" class="diff-lineno">Property / <a title="Property:P31" href="/wiki/Property:P31">instance of</a></td></tr><tr><td colspan="2">&nbsp;</td><td class="diff-marker">+</td><td class="diff-addedline"><div><ins class="diffchange diffchange-inline"><span><a title="Q5" href="/wiki/Q5">human</a></span></ins></div></td></tr><tr><td colspan="2" class="diff-lineno"></td><td colspan="2" class="diff-lineno">Property / <a title="Property:P31" href="/wiki/Property:P31">instance of</a>: <a title="Q5" href="/wiki/Q5">human</a> / rank</td></tr><tr><td colspan="2">&nbsp;</td><td class="diff-marker">+</td><td class="diff-addedline"><div><ins class="diffchange diffchange-inline"><span>Preferred rank</span></ins></div></td></tr>', None),
])
def test_primary_script_of_diff(html, expected_script):
    actual_script = scripts.primary_script_of_diff(html)
    assert expected_script == actual_script
