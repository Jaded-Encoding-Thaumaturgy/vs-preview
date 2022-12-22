"""Previewer for VapourSynth scripts"""

__version__ = '0.4.0'

__author__ = 'Endilll <>'
__maintainer__ = 'Setsugen no ao <setsugen@setsugen.dev>'

__author_name__, __author_email__ = [x[:-1] for x in __author__.split('<')]
__maintainer_name__, __maintainer_email__ = [x[:-1] for x in __maintainer__.split('<')]

if __name__ == '__github__':
    print(__version__)
