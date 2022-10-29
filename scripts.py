import bs4

import unicodescripts


def scripts_of_text(text):
    """Determine the scripts used in a snippet of text.

    The 'Common', 'Inherited' and 'Unknown' scripts are ignored."""
    scripts = {}
    for char in text:
        script = unicodescripts.script(char)
        if script not in {'Common', 'Inherited', 'Unknown'}:
            scripts[script] = scripts.get(script, 0) + 1
    common_scripts = sorted(scripts.items(), key=lambda item: item[1], reverse=True)
    return [script for script, count in common_scripts]


def primary_script_of_diff(html):
    """Determine the primary script of a Wikidata diff.

    Only the scripts of terms, sitelinks, monolingual text values and
    Commons media are considered. For this to work, the diff UI
    (specifically, the headers) must be in English."""
    soup = bs4.BeautifulSoup(html, 'html.parser')
    elements = [content for content in soup.contents if type(content) is bs4.Tag]
    texts = []
    for i in range(0, len(elements), 2):
        lineno = elements[i].get_text()
        if (lineno.startswith('label / ') or
                lineno.startswith('description /') or
                lineno.startswith('aliases /') or
                lineno.startswith('links /')):
            texts += (element.get_text() for element in elements[i + 1].select('.diff-addedline, .diff-deletedline'))
        elif lineno.startswith('Property /'):
            texts += (element.get_text() for element in elements[i + 1].select('.wb-monolingualtext-value'))
            texts += (element.get_text() for element in elements[i + 1].select('a.extiw[href^="//commons.wikimedia.org/"]'))
    scripts = scripts_of_text(char for text in texts for char in text)
    if scripts:
        return scripts[0]
    else:
        return None
