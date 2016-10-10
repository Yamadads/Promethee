#!../promethee python

"""
PrometheeAggregatedPreferenceWithInteractions - computes aggregated preference indices taking into
account interactions between criteria. Possible interactions are:
'strengthening', 'weakening' and 'antagonistic

The key feature of this module is its flexibility in terms of the types of
elements allowed to compare, i.e. alternatives vs alternatives, alternatives vs
boundary profiles and alternatives vs central (characteristic) profiles.
Each criterion can have its own preference function (one of six predefined functions).

Usage:
    PrometheeAggregatedPreferenceWithInteractions.py -i DIR -o DIR

Options:
    -i DIR     Specify input directory. It should contain the following files:
                   alternatives.xml
                   classes_profiles.xml (optional)
                   criteria.xml
                   interactions.xml
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
from itertools import chain
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
    ('interactions.xml', False),
    ('generalised_criteria.xml', True)
]

params = [
    'alternatives',
    'categories_profiles',
    'comparison_with',
    'criteria',
    'interactions',
    'performances',
    'pref_directions',
    'profiles_performance_table',
    'thresholds',
    'weights',
    'generalised_criteria',
    'z_function',
]

def get_aggregated_preference_indices(comparables_a, comparables_perf_a, comparables_b,
                    comparables_perf_b, criteria, generalised_criteria, thresholds, pref_directions,
                    weights, interactions, z_function):

    generalised_criteria_function = {
        1: UsualCriterion,
        2: UShapeCriterion,
        3: VShapeCriterion,
        4: LevelCriterion,
        5: VShapeWithIndifferenceCriterion,
        6: GaussianCriterion,
    }

    def _check_net_balance(interactions, weights):
        int_weak = interactions.get('weakening', [])
        int_antag = interactions.get('antagonistic', [])
        int_chained = chain(int_weak, int_antag)
        criteria_affected = set([i[0] for i in int_chained])
        for criterion in criteria_affected:
            weak_sum = sum([abs(i[2]) for i in int_weak if i[0] == criterion])
            antag_sum = sum([i[2] for i in int_antag if i[0] == criterion])
            net_balance = weights[criterion] - weak_sum + antag_sum
            if net_balance <= 0:
                raise RuntimeError("Positive net balance condition is not "
                                   "fulfilled for criterion '{}'."
                                   .format(criterion))

    def get_z_function(z_function):
        if z_function == 'multiplication':
            Z = lambda x, y: x * y
        elif z_function == 'minimum':
            Z = lambda x, y: min(x, y)
        else:
            raise RuntimeError("Invalid Z function: '{}'.".format(z_function))
        return Z

    def preference_on_one_criterion(ga,gb,pref_direction,functionNo, threshold):
        preference_function = generalised_criteria_function[functionNo];

        _get_linear = partial(get_linear, pref_direction, ga, gb)
        preference_treshold = _get_linear(threshold.get('preference', 0))
        indifference_treshold = _get_linear(threshold.get('indifference', 0))
        sigma_treshold = _get_linear(threshold.get('sigma', 0))

        difference_between_evaulations = get_difference_between_evaluations(pref_directions, ga, gb)

        calculated_preference = preference_function(
                                    difference_between_evaulations,
                                    preference_treshold,
                                    indifference_treshold,
                                    sigma_treshold);

        return calculated_preference

    def get_partial_preferences(comp_a, comp_b, comp_perf_a, comp_perf_b, criteria, gen_criteria, pref_dir, thresholds, two_way_comp):
        partial_preferences = Vividict()
        for a in comp_a:
            for b in comp_b:
                for c in criteria:
                    pp = preference_on_one_criterion(
                            comp_perf_a[a][c],
                            comp_perf_b[b][c],
                            pref_dir[c],
                            gen_criteria[c],
                            thresholds[c])
                    partial_preferences[a][b][c] = pp
                    if two_way_comp:
                        pp = preference_on_one_criterion(
                                comp_perf_b[b][c],
                                comp_perf_a[a][c],
                                pref_dir[c],
                                gen_criteria[c],
                                thresholds[c])
        return partial_preferences

    def get_aggregated_preference(a,b, part_preference, criteria, weights, Z_function, interactions):
        print(part_preference)
        if a==b:
            aggregated_preference = 1.0
        else:
            sum_cki = sum([part_preference[a][b][c] * weights[c] for c in criteria])
            sum_kij = float(0)
            for interaction_name in ('strengthening', 'weakening'):
                for interaction in interactions.get(interaction_name, []):
                    ci = part_preference[a][b][interaction[0]]
                    cj = part_preference[a][b][interaction[1]]
                    sum_kij += Z_function(ci, cj) * interaction[2]
            sum_kih = 0.0
            for interaction in interactions.get('antagonistic', []):
                ci = part_preference[a][b][interaction[0]]
                cj = part_preference[b][a][interaction[1]]
                print(interaction[2])
                print(ci)
                print(cj)
                sum_kih += Z_function(ci, cj) * interaction[2]
            sum_ki = sum(weights.values())
            K = sum_ki + sum_kij - sum_kih
            aggregated_preference = (sum_cki + sum_kij - sum_kih) / K
        return aggregated_preference

    # some initial checks
    _check_net_balance(interactions, weights)

    Z = get_z_function(z_function)

    two_way_comparison = True if comparables_a != comparables_b else False

    partial_preferences = get_partial_preferences(comparables_a,
                                                  comparables_b,
                                                  comparables_perf_a,
                                                  comparables_perf_b,
                                                  criteria,
                                                  generalised_criteria,
                                                  pref_directions,
                                                  thresholds,
                                                  two_way_comparison)

    aggregated_preferences = Vividict()
    for a in comparables_a:
        for b in comparables_b:
            temp_preference = get_aggregated_preference(
                                a,
                                b,
                                partial_preferences,
                                criteria,
                                weights,
                                Z,
                                interactions)
            aggregated_preferences[a][b] = temp_preference
            if two_way_comparison:
                temp_preference = get_aggregated_preference(
                                    b,
                                    a,
                                    partial_preferences,
                                    criteria,
                                    weights,
                                    Z,
                                    interactions)
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
        print (data.interactions)
        comparables_a = data.alternatives
        comparables_perf_a = data.performances

        if data.comparison_with in ('boundary_profiles', 'central_profiles'):
            # central_profiles is a dict, so we need to get the keys
            comparables_b = [i for i in data.categories_profiles]
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
                                        data.weights,
                                        data.interactions,
                                        data.z_function)

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