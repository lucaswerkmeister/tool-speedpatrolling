#!/usr/bin/python3

import intervaltree
import urllib.request


print("""#!/usr/bin/python3

import intervaltree


_tree = intervaltree.IntervalTree()
""")

with urllib.request.urlopen('https://www.unicode.org/Public/UNIDATA/Scripts.txt') as r:
    prior_begin = None
    prior_end = None
    prior_script = None
    for line in r:
        line = line.decode('utf-8')
        line = line.split('#', 1)[0]
        line = line.strip()
        if not line:
            continue
        chars, script = line.split(';')
        chars = chars.strip()
        script = script.strip()
        first, sep, last = chars.partition('..')
        if not sep:
            last = first
        begin = int(first, base=16)
        end = int(last, base=16) + 1
        if begin == prior_end:
            # merge adjacent ranges (only differ in comment)
            prior_end = end
        else:
            # new range, print the prior one (unless this is the first one)
            if prior_script:
                print("_tree[%d:%d] = %s" % (prior_begin, prior_end, repr(prior_script)))
            prior_begin, prior_end, prior_script = begin, end, script

# print the final range
if prior_script:
    print("_tree[%d:%d] = %s" % (prior_begin, prior_end, repr(prior_script)))

print('''

def script(chr):
    """Return the script of the given character.

    If the script for the character is not known,
    'Unknown' is returned."""
    intervals = _tree[ord(chr)]
    if len(intervals) == 1:
        return intervals.pop().data
    elif not intervals:
        return 'Unknown'
    else:
        # this should never happen
        raise ValueError('more than one script for character ' + chr)


def all_scripts():
    """Return a set of all scripts known to this module.

    This does not include the 'Unknown' default script."""
    return set(i.data for i in _tree)''')
