#!../promethee python

"""
PrometheeAggregatedPreferenceReinforcedPreference - computes aggregated preference indices

This module is an extended version of 'PrometheeAggregatedPreference' - it brings the
concept of 'reinforced_preference', which boils down to the new threshold of
the same name and a new input file where the 'reinforcement factors' are
defined (one for each criterion where 'reinforced_preference' threshold is
present).

Usage:
    PrometheeAggregatedPreferenceReinforcedPreference.py -i DIR -o DIR

Options:
    -i DIR     Specify input directory. It should contain the following files:
                   alternatives.xml
                   classes_profiles.xml (optional)
                   criteria.xml
                   method_parameters.xml
                   performance_table.xml
                   profiles_performance_table.xml (optional)
                   weights.xml
                   reinforcement_factors.xml
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
    ('reinforcement_factors.xml', True),
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
    'reinforcement_factors',
    'thresholds',
    'weights',
    'generalised_criteria_without_gaussian',
]

def get_aggregated_preference_indices(comparables_a, comparables_perf_a, comparables_b,
                    comparables_perf_b, criteria, generalised_criteria, thresholds, pref_directions,
                    weights, reinforcement_factors):

    generalised_criteria_function = {
        1: UsualCriterion,
        2: UShapeCriterion,
        3: VShapeCriterion,
        4: LevelCriterion,
        5: VShapeWithIndifferenceCriterion,
    }

    def preference_on_one_criterion(ga,gb,pref_direction,functionNo, threshold):
        preference_function = generalised_criteria_function[functionNo];

        _get_linear = partial(get_linear, pref_direction, ga, gb)
        preference_threshold = _get_linear(threshold.get('preference', 0))
        indifference_threshold = _get_linear(threshold.get('indifference', 0))
        reinforced_threshold = _get_linear(threshold.get('reinforced_preference', 0))

        difference_between_evaulations = get_difference_between_evaluations(pref_direction, ga, gb)

        crossed = False
        if reinforced_threshold is not None \
             and difference_between_evaulations > reinforced_threshold:
            crossed = True
        calculated_preference = preference_function(
                                    difference_between_evaulations,
                                    preference_threshold,
                                    indifference_threshold)
        return (calculated_preference, crossed)

    def get_partial_preferences(comp_a, comp_b, comp_perf_a, comp_perf_b, criteria, gen_criteria, pref_dir, thresholds, reinforcement_factors, two_way_comp):
        partial_preferences = Vividict()
        rp_crossed = {}
        for a in comp_a:
            for b in comp_b:
                for c in criteria:
                    pp, crossed = preference_on_one_criterion(
                                        comp_perf_a[a][c],
                                        comp_perf_b[b][c],
                                        pref_dir[c],
                                        gen_criteria[c],
                                        thresholds[c])
                    if crossed:
                        rf = reinforcement_factors.get(c, 1)
                        rp_crossed.update({(a, b, c): rf})
                    partial_preferences[a][b][c] = pp

                    if two_way_comp:
                        pp, crossed = preference_on_one_criterion(
                                            comp_perf_b[b][c],
                                            comp_perf_a[a][c],
                                            pref_dir[c],
                                            gen_criteria[c],
                                            thresholds[c])
                        if crossed:
                            rf = reinforcement_factors.get(c, 1)
                            rp_crossed.update({(b, a, c): rf})
                        partial_preferences[b][a][c] = pp
        return (partial_preferences, rp_crossed)

    def get_aggregated_preference(a, b, rp_crossed, partial_preferences, criteria, weights):
        sum_of_weights = sum([weights[criterion] *
                              rp_crossed.get((a, b, criterion), 1)
                              for criterion in criteria])
        s = sum([weights[criterion] *
                 rp_crossed.get((a, b, criterion), 1) *
                 partial_preferences[a][b][criterion]
                 for criterion in criteria])
        preference = s / sum_of_weights
        return preference

    two_way_comparison = True if comparables_a != comparables_b else False

    partial_preferences, rp_crossed = get_partial_preferences(comparables_a,
                                                  comparables_b,
                                                  comparables_perf_a,
                                                  comparables_perf_b,
                                                  criteria,
                                                  generalised_criteria,
                                                  pref_directions,
                                                  thresholds,
                                                  reinforcement_factors,
                                                  two_way_comparison)
    aggregated_preferences = Vividict()
    for a in comparables_a:
        for b in comparables_b:
            ap = get_aggregated_preference(a, b, rp_crossed, partial_preferences, criteria, weights)
            aggregated_preferences[a][b] = ap
            if two_way_comparison:
                ap = get_aggregated_preference(b, a, rp_crossed)
                aggregated_preferences[b][a] = ap
    return aggregated_preferences

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
                                        data.generalised_criteria_without_gaussian,
                                        data.thresholds,
                                        data.pref_directions,
                                        data.weights,
                                        data.reinforcement_factors)

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