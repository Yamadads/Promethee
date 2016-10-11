#!../promethee python

"""
PrometheeSRF - computes weights of criteria using the revised Simos procedure

Usage:
    PrometheeSRF.py -i DIR -o DIR

Options:
    -i DIR     Specify input directory. It should contain the following files:
                   method_parameters.xml
                   criteria.xml
                   criteria_ranking.xml
    -o DIR     Specify output directory. Files generated as output:
                   weights.xml
                   messages.xml
    --version  Show version.
    -h --help  Show this screen.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import sys
import traceback
import os
from unicodedata import decimal
from docopt import docopt
from common import comparisons_to_xmcda, create_messages_file, get_dirs, \
    get_error_message, get_input_data, get_linear, omega, write_xmcda, Vividict, weights_to_xmcda
from networkx.classes.function import non_edges
from math import floor, ceil

__version__ = '0.2.0'

filenames = [
    # every tuple below == (filename, is_optional)
    ('method_parameters.xml', False),
    ('criteria.xml', False),
    ('criteria_ranking.xml', False),
]

params = [
    'criteria',
    'method',
    'criteria_ranking',
]

def get_equal_weights(ranking):
    weights = {}
    result = 1 / len(ranking)
    for i in ranking:
        weights[i] = result
    return weights

def get_rank_sum(ranking):
    weights = {}
    n = len(ranking)
    d = n*(n+1)
    for i in ranking:
        weights[i] = (2*(n+1-ranking[i]))/d
    return weights

def get_rank_reciprocal(ranking):
    weights = {}
    n = len(ranking)
    d = 0
    for i in ranking.values():
        d += 1/i
    for i in ranking:
        weights[i] = (1/ranking[i])/d
    return weights

def get_rank_order_centroid(ranking):
    weights = {}
    n = len(ranking)
    d = 0
    for i in ranking.values():
        d += 1/i
    result = (1/n)*d
    for i in ranking:
        weights[i] = result
    return weights

def get_weights(ranking, method):
    weights = {}
    if (method == 'equal_weights'):
        weights = get_equal_weights(ranking)
    if method == 'rank_sum':
        weights = get_rank_sum(ranking)
    if method == 'rank_reciprocal':
        weights = get_rank_reciprocal(ranking)
    if method == 'rank_ordered_centroid':
        weights = get_rank_order_centroid(ranking)
    return weights

def finalize(data, output_dir):
    mcda_concept = 'Importance'
    xmcda = weights_to_xmcda(data, mcda_concept)
    write_xmcda(xmcda, os.path.join(output_dir, 'weights.xml'))
    create_messages_file(None, ('Everything OK.',), output_dir);

def main():
    try:
        args = docopt(__doc__, version=__version__)
        output_dir = None
        input_dir, output_dir = get_dirs(args)

        data = get_input_data(input_dir, filenames, params)

        weights = get_weights(data.criteria_ranking, data.method)

        finalize(weights, output_dir)
        return 0

    except Exception, err:
        err_msg = get_error_message(err)
        log_msg = traceback.format_exc()
        print(log_msg.strip())
        create_messages_file((err_msg, ), (log_msg, ), output_dir)
        return 1

if __name__ == '__main__':
    sys.exit(main())