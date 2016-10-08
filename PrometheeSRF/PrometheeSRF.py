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
    'criteria_weight_ratio',
    'decimal_places',
    'criteria_ranking',
]

def custom_round(num, places = 0, direction = floor):
    return direction(num * (10**places)) / float(10**places)

def get_non_normalized_weights(ranking, z):
    max_criterion = max(ranking, key=ranking.get)
    max_value = ranking[max_criterion]
    e = max_value - 1
    u = (z-1)/e
    non_normalized_weights = {}
    for i in ranking:
        non_normalized_weights[i] = 1+u*(ranking[i]-1)
    return non_normalized_weights;

def get_normalized_weights(non_normalized_weights):
    weights_sum = sum(non_normalized_weights.values())
    normalized_weights = {}
    for i in non_normalized_weights:
        normalized_weights[i]=non_normalized_weights[i]*100/weights_sum
    return normalized_weights

def get_rounded_weights(normalized_weights, decimal_places):
    rounded_weights = {}
    for i in normalized_weights:
        rounded_weights[i] = custom_round(normalized_weights[i], decimal_places)
    return rounded_weights;

def get_ratios_to_normalization(normalized_weights, rounded_weights, decimal_places):
    L_plus = {}
    L_minus = {}
    L_plus_greater_than_L_minus = []
    w = 10**(-decimal_places)
    for i in normalized_weights:
        L_plus[i] = (w-(normalized_weights[i]-rounded_weights[i]))/normalized_weights[i]
        L_minus[i] = (normalized_weights[i]-rounded_weights[i])/normalized_weights[i]
        if L_plus[i]>L_minus[i]:
            L_plus_greater_than_L_minus.append(i)
    return L_plus, L_minus, L_plus_greater_than_L_minus

def get_normalized_weights_up_to_100(L_plus, L_minus, L_plus_greater_than_L_minus, rounded_weights, normalized_weights, decimal_places):
    v = 10**decimal_places*(100-sum(rounded_weights.values()))
    sorted_L_minus = sorted(L_minus, key=L_minus.__getitem__, reverse=True)
    sorted_L_plus= sorted(L_plus, key=L_plus.__getitem__)
    normalized_weights_up_to_100 = {}
    if (len(L_plus_greater_than_L_minus)+v)>len(normalized_weights):
        i = len(sorted_L_plus)-1
        last_criterion = v # n-v last criteria
        while (i>=0)and(i>=last_criterion):
            criterion=sorted_L_plus[i]
            if criterion not in L_plus_greater_than_L_minus:
                normalized_weights_up_to_100[criterion] = custom_round(normalized_weights[criterion], decimal_places, floor)
                # last_criterion -= 1
                # i -= 1
                # break
                #
            i -= 1
        i = 0
        while i < len(normalized_weights):
            criterion=sorted_L_plus[i]
            if criterion not in normalized_weights_up_to_100:
                normalized_weights_up_to_100[criterion] = custom_round(normalized_weights[criterion], decimal_places, ceil)
            i += 1
    else:
        i = 0
        last_criterion = v
        while (i<len(sorted_L_minus))and(i<=last_criterion):
            criterion=sorted_L_minus[i]
            if criterion not in L_plus_greater_than_L_minus:
                normalized_weights_up_to_100[criterion] = custom_round(normalized_weights[criterion], decimal_places, ceil)
            i += 1
        i = 0
        while i < len(normalized_weights):
            criterion=sorted_L_plus[i]
            if criterion not in normalized_weights_up_to_100:
                normalized_weights_up_to_100[criterion] = custom_round(normalized_weights[criterion], decimal_places, floor)
            i += 1
    return normalized_weights_up_to_100

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

        non_normalized_weights = get_non_normalized_weights(data.criteria_ranking, data.criteria_weight_ratio)
        (normalized_weights)= get_normalized_weights(non_normalized_weights)
        rounded_weights = get_rounded_weights(normalized_weights, data.decimal_places)
        (L_plus, L_minus, L_plus_greater_than_L_minus) = get_ratios_to_normalization(normalized_weights, rounded_weights, data.decimal_places)
        normalized_weights_up_to_100 = get_normalized_weights_up_to_100(L_plus, L_minus, L_plus_greater_than_L_minus, rounded_weights, normalized_weights, data.decimal_places)
        finalize(normalized_weights_up_to_100, output_dir)

        return 0

    except Exception, err:
        err_msg = get_error_message(err)
        log_msg = traceback.format_exc()
        print(log_msg.strip())
        create_messages_file((err_msg, ), (log_msg, ), output_dir)
        return 1

if __name__ == '__main__':
    sys.exit(main())