#!../promethee python

"""
PrometheeAggregatedPreference - computes aggregated preference indices

The key feature of this module is its flexibility in terms of the types of
elements allowed to compare, i.e. alternatives vs alternatives, alternatives vs
boundary profiles and alternatives vs central (characteristic) profiles.
Each criterion can have its own preference function (one of six predefined functions).

Usage:
    PrometheeAggregatedPreference.py -i DIR -o DIR

Options:
    -i DIR     Specify input directory. It should contain the following files:
                   alternatives.xml
                   classes_profiles.xml (optional)
                   criteria.xml
                   method_parameters.xml
                   performance_table.xml
                   profiles_performance_table.xml (optional)
                   weights.xml
                   generalised_criteria.xml (optional)
    -o DIR     Specify output directory. Files generated as output:
                   aggregated_preferences.xml
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
from preferenceFunction import *
from common import comparisons_to_xmcda, create_messages_file, get_dirs, \
    get_error_message, get_input_data, get_linear, omega, write_xmcda, Vividict

__version__ = '0.2.0'

filenames = [
    # every tuple below == (filename, is_optional)
    ('alternatives.xml', False),
    ('classes_profiles.xml', True),
    ('criteria.xml', False),
    ('method_parameters.xml', False),
    ('performance_table.xml', False),
    ('profiles_performance_table.xml', True),
    ('weights.xml', False),
    ('generalised_criteria.xml', True)
]

params = [
    'alternatives',
    'categories_profiles',
    'comparison_with',
    'criteria',
    'performances',
    'pref_directions',
    'profiles_performance_table',
    'thresholds',
    'weights',
    'generalised_criteria',
]

def get_normalized_weights(weights):
    normalized_weights = {}
    sum_of_weights = sum(weights.values())
    for i in weights:
        normalized_weights[i] = weights[i]/sum_of_weights
    return normalized_weights

def get_aggregated_preference_indices(comparables_a, comparables_perf_a, comparables_b,
                    comparables_perf_b, criteria, generalised_criteria, thresholds, pref_directions,
                    weights):

    generalised_criteria_function = {
        1: UsualCriterion,
        2: UShapeCriterion,
        3: VShapeCriterion,
        4: LevelCriterion,
        5: VShapeWithIndifferenceCriterion,
        6: GaussianCriterion,
    }

    def preference_on_one_criterion(ga,gb,pref_direction,functionNo, threshold):
        preference_function = generalised_criteria_function[functionNo];
        _get_linear = partial(get_linear, pref_direction, ga, gb)
        preference_treshold = _get_linear(threshold.get('preference', 0))
        indifference_treshold = _get_linear(threshold.get('indifference', 0))
        sigma_treshold = _get_linear(threshold.get('sigma', 0))
        difference_between_evaulations = get_difference_between_evaluations(pref_direction, ga, gb)
        calculated_preference = preference_function(
                                    difference_between_evaulations,
                                    preference_treshold,
                                    indifference_treshold,
                                    sigma_treshold);

        return calculated_preference

    def get_aggregated_preference(ga,gb, criteria, generalised_criteria, pref_directions, thresholds, weights):
        result = 0;
        for c in criteria:
            result+=preference_on_one_criterion(
                ga[c],
                gb[c],
                pref_directions[c],
                generalised_criteria[c],
                thresholds[c]
            )*weights[c]
        return result;

    two_way_comparison = True if comparables_a != comparables_b else False

    aggregated_preferences = Vividict()
    for a in comparables_a:
        for b in comparables_b:
            temp_preference = get_aggregated_preference(
                                comparables_perf_a[a],
                                comparables_perf_b[b],
                                criteria,
                                generalised_criteria,
                                pref_directions,
                                thresholds,
                                weights)
            aggregated_preferences[a][b] = temp_preference
            if two_way_comparison:
                temp_preference = get_aggregated_preference(
                                    comparables_perf_b[b],
                                    comparables_perf_a[a],
                                    criteria,
                                    generalised_criteria,
                                    pref_directions,
                                    thresholds,
                                    weights)
                aggregated_preferences[b][a] = temp_preference
    return aggregated_preferences;

def finalize(data, comparables_a, comparables_b, aggregated_preferences, output_dir):
    if data.comparison_with in ('boundary_profiles', 'central_profiles'):
        mcda_concept = 'alternativesProfilesComparisons'
    else:
        mcda_concept = None
    comparables = (comparables_a, comparables_b)
    xmcda = comparisons_to_xmcda(aggregated_preferences, comparables,
                                 mcda_concept=mcda_concept)
    write_xmcda(xmcda, os.path.join(output_dir, 'aggregated_preferences.xml'))
    create_messages_file(None, ('Everything OK.',), output_dir);

def main():
    try:
        args = docopt(__doc__, version=__version__)
        output_dir = None
        input_dir, output_dir = get_dirs(args)

        data = get_input_data(input_dir, filenames, params)

        comparables_a = data.alternatives
        comparables_perf_a = data.performances
        normalized_weights = get_normalized_weights(data.weights)

        if data.comparison_with in ('boundary_profiles', 'central_profiles'):
            comparables_b = data.categories_profiles
            comparables_perf_b = data.profiles_performance_table
        else:
            comparables_b = data.alternatives
            comparables_perf_b = data.performances

        aggregated_preferences = get_aggregated_preference_indices(
                                        comparables_a,
                                        comparables_perf_a,
                                        comparables_b,
                                        comparables_perf_b,
                                        data.criteria,
                                        data.generalised_criteria,
                                        data.thresholds,
                                        data.pref_directions,
                                        normalized_weights)
        finalize(data, comparables_a, comparables_b, aggregated_preferences, output_dir)

        return 0

    except Exception, err:
        err_msg = get_error_message(err)
        log_msg = traceback.format_exc()
        print(log_msg.strip())
        create_messages_file((err_msg, ), (log_msg, ), output_dir)
        return 1

if __name__ == '__main__':
    sys.exit(main())