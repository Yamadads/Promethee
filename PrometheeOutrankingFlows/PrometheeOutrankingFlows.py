#!../promethee python

"""
PrometheeOutrankingFlows - computes positive and negative outranking flows using aggregated preference indices

Usage:
    PrometheeOutrankingFlows.py -i DIR -o DIR

Options:
    -i DIR     Specify input directory. It should contain the following files:
                   alternatives.xml
                   classes_profiles.xml (optional)
                   aggregated_preferences.xml
                   method_parameters.xml
    -o DIR     Specify output directory. Files generated as output:
                   positive_outranking_flows.xml
                   negitive_outranking_flows.xml
                   messages.xml
    --version  Show version.
    -h --help  Show this screen.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys
import traceback
from functools import partial
from docopt import docopt
from common import comparisons_to_xmcda, create_messages_file, get_dirs, \
    get_error_message, get_input_data, get_linear, omega, write_xmcda, Vividict, outranking_flows_to_xmcda

__version__ = '0.2.0'

filenames = [
    # every tuple below == (filename, is_optional)
    ('alternatives.xml', False),
    ('classes_profiles.xml', True),
    ('aggregated_preferences.xml', True),
    ('method_parameters.xml', False),
]

params = [
    'alternatives',
    'categories_profiles',
    'aggregated_preferences',
    'comparison_with',
]

def get_positive_outranking_flow(a, compare_with,  aggregated_preferences):
    flow = 0
    for i in compare_with:
        flow += aggregated_preferences[a][i]
    flow /= len(compare_with)
    return flow

def get_negative_outranking_flow(a, compare_with, aggregated_preferences):
    flow = 0
    for i in compare_with:
        flow += aggregated_preferences[i][a]
    flow /= len(compare_with)
    return flow

def get_alternatives_flow(alternatives, aggregated_preferences):
    positive_flow = {}
    negative_flow = {}
    for i in alternatives:
        compare_with = list(alternatives)
        compare_with.remove(i)
        positive_flow[i] = get_positive_outranking_flow(i, compare_with, aggregated_preferences)
        negative_flow[i] = get_negative_outranking_flow(i, compare_with, aggregated_preferences)
    return positive_flow, negative_flow

def get_profiles_flow(alternatives, profiles, aggregated_preferences):
    positive_flow = {}
    negative_flow = {}
    compare_with = list(profiles)
    for i in alternatives:
        positive_flow[i] = get_positive_outranking_flow(i, compare_with, aggregated_preferences)
        negative_flow[i] = get_negative_outranking_flow(i, compare_with, aggregated_preferences)
    for i in profiles:
        compare_with = list(profiles)
        compare_with.remove(i)
        positive_flow[i] = get_positive_outranking_flow(i, compare_with, aggregated_preferences)
        negative_flow[i] = get_negative_outranking_flow(i, compare_with, aggregated_preferences)
    return positive_flow, negative_flow

def finalize(positive_outranking_flow, negative_outranking_flow, output_dir, comparison_with):
    mcda_concept = comparison_with + '_outranking_flows'
    xmcda = outranking_flows_to_xmcda(positive_outranking_flow, mcda_concept)
    write_xmcda(xmcda, os.path.join(output_dir, 'positive_flows.xml'))
    xmcda = outranking_flows_to_xmcda(negative_outranking_flow, mcda_concept)
    write_xmcda(xmcda, os.path.join(output_dir, 'negative_flows.xml'))
    create_messages_file(None, ('Everything OK.',), output_dir);

def main():
    try:
        args = docopt(__doc__, version=__version__)
        output_dir = None
        input_dir, output_dir = get_dirs(args)

        data = get_input_data(input_dir, filenames, params)

        positive_outranking_flow = {}
        negative_outranking_flow = {}
        if data.comparison_with in ('boundary_profiles', 'central_profiles'):
            (positive_outranking_flow,negative_outranking_flow) = get_profiles_flow(
                                                                    data.alternatives,
                                                                    data.categories_profiles,
                                                                    data.aggregated_preferences)
        else:
            (positive_outranking_flow,negative_outranking_flow) = get_alternatives_flow(
                                                                    data.alternatives,
                                                                    data.aggregated_preferences)

        finalize(positive_outranking_flow, negative_outranking_flow, output_dir, data.comparison_with)
        return 0

    except Exception, err:
        err_msg = get_error_message(err)
        log_msg = traceback.format_exc()
        print(log_msg.strip())
        create_messages_file((err_msg, ), (log_msg, ), output_dir)
        return 1

if __name__ == '__main__':
    sys.exit(main())