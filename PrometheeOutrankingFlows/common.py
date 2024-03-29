# -*- coding: utf-8 -*-

import os
import re
from functools import partial

import PyXMCDA as px
from lxml import etree


HEADER = ("<?xml version='1.0' encoding='UTF-8'?>\n"
          "<xmcda:XMCDA xmlns:xmcda='http://www.decision-deck.org/2012/XMCDA-2.2.1'\n"
          "  xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance'\n"
          "  xsi:schemaLocation='http://www.decision-deck.org/2012/XMCDA-2.2.1 http://www.decision-deck.org/xmcda/_downloads/XMCDA-2.2.1.xsd'>\n")
FOOTER = "</xmcda:XMCDA>"

INPUT_DATA_ERROR_MSG = ("There's a problem with some of your input files, "
                        "namely:")
INPUT_DATA_ERROR_HINT = ("Please check if the contents of this file matches "
                         "the method parameters that you've specified.")

THRESHOLDS = ['indifference', 'preference', 'veto', 'reinforced_preference',
              'counter_veto', 'pre_veto', 'sigma']

THRESHOLDS_OLD_TO_NEW = {'ind': 'indifference', 'pref': 'preference'}


class InputDataError(Exception):
    pass


###############################################################################
# Data structures etc.                                                        #
###############################################################################

class Vividict(dict):
    def __missing__(self, key):
        value = self[key] = type(self)()
        return value


class InputData(object):
    # same as: InputData = type('InputData', (object,), {})
    pass


def _create_data_object(params):
    obj = InputData()
    for p in params:
        setattr(obj, p, None)
    return obj


###############################################################################
# Shared 'business logic'.                                                    #
###############################################################################

def get_relation_type(x, y, outranking):
    """Determines an exact type of relation for (x, y) based on the outranking
    relation produced by the 'cutRelationCrisp' module.
    """
    if outranking[x][y] and outranking[y][x]:
        relation = 'indifference'
    elif outranking[x][y] and not outranking[y][x]:
        relation = 'preference'
    elif not outranking[x][y] and not outranking[y][x]:
        relation = 'incomparability'
    else:
        relation = None
    return relation

#use
def get_linear(pref_directions, ga, gb, threshold):
    """Check if the given threshold is defined as linear and if yes, then
    calculate its value - otherwise (i.e. when the threshold is a constant)
    just return it w/o any processing.
    In most cases it may be a good idea to wrap this function using
    functools.partial and pass here only the 'threshold' argument.
    """
    if type(threshold) is not dict:  # true when threshold is constant
        value = threshold
    else:
        # we calculate the thresold value from the alternative (or profile)
        # which performs weaker on the given criterion
        if pref_directions == 'max':
            perf = gb if ga > gb else ga
        if pref_directions == 'min':
            perf = ga if ga > gb else gb
        slope = threshold.get('slope', 0)
        intercept = threshold.get('intercept', 0)
        value = slope * perf + intercept
    return value


def omega(pref_directions, criterion, x, y):
    if pref_directions[criterion] == 'max':
        return x - y
    if pref_directions[criterion] == 'min':
        return y - x


###############################################################################
# Getting the input data and related stuff.                                   #
# Functions prefixed with the underscore are meant for the internal use only. #
###############################################################################

def get_dirs(args):
    input_dir = args.get('-i')
    output_dir = args.get('-o')
    for d in (input_dir, output_dir):
        if not os.path.isdir(d):
            raise InputDataError("Directory '{}' doesn't exist. Aborting."
                                 .format(d))
    return input_dir, output_dir


def _get_trees(input_dir, filenames):
    trees = {}
    for f, is_optional in filenames:
        file_name = os.path.join(input_dir, f)
        if not os.path.isfile(file_name):
            if is_optional:
                continue
            else:
                raise InputDataError("Problem with the input file: '{}'."
                                     .format(f))
        tree = None
        tree = px.parseValidate(file_name)
        if tree is None:
            raise InputDataError("Validation error with the file: '{}'."
                                 .format(f))
        tree_name = os.path.splitext(f)[0]
        # although we use 'classes' and 'classes_profiles' in the names of
        # the input files and in the documentation, we want to use them as
        # 'categories' (and 'categories_profiles') internally
        if 'classes' in tree_name:
            tree_name = tree_name.replace('classes', 'categories')
        trees.update({tree_name: tree})
    return trees


def _get_thresholds(xmltree):
    """This is basically the same as px.getConstantThresholds, but with the
    added ability to get linear thresholds as well.
    It also checks for valid threshold names (raises an error when an unknown
    name is found), and corrects some old/known ones too (e.g., 'ind', 'pref').
    """
    thresholds = {}
    for criterion in xmltree.findall('.//criterion'):
        criterion_id = criterion.get('id')
        xml_thresholds = criterion.find('thresholds')
        if xml_thresholds is not None:
            crit_thresholds = {}
            for xml_threshold in xml_thresholds.findall('threshold'):
                xml_constant = xml_threshold.find('constant')
                if xml_constant is not None:
                    xml_val = xml_constant.find('real')
                    if xml_val is None:
                        xml_val = xml_constant.find('integer')
                    if xml_val is not None:
                        mcda_concept = xml_threshold.get('mcdaConcept')
                        # XXX for backwards compatibility only!
                        mcda_concept = THRESHOLDS_OLD_TO_NEW.get(mcda_concept,
                                                                 mcda_concept)
                        if mcda_concept not in THRESHOLDS:
                            ts = ", ".join(["'" + t + "'" for t in THRESHOLDS])
                            msg = ("Unrecognized threshold name '{}'. Depending "
                                   "on your context, you may be interested in "
                                   "one of these: {}."
                                   .format(mcda_concept, ts))
                            raise InputDataError(msg)
                        if mcda_concept is not None:
                            crit_thresholds[mcda_concept] = float(xml_val.text)
                xml_linear = xml_threshold.find('linear')
                if xml_linear is not None:
                    xml_slope = xml_linear.find('slope/real')
                    if xml_slope is None:
                        xml_slope = xml_linear.find('slope/integer')
                    xml_intercept = xml_linear.find('intercept/real')
                    if xml_intercept is None:
                        xml_intercept = xml_linear.find('intercept/integer')
                    if xml_slope is not None or xml_intercept is not None:
                        mcda_concept = xml_threshold.get('mcdaConcept')
                        if mcda_concept is not None:
                            if xml_slope is not None:
                                slope = float(xml_slope.text)
                            else:
                                slope = 0.0
                            if xml_intercept is not None:
                                intercept = float(xml_intercept.text)
                            else:
                                intercept = 0.0
                            threshold = {'slope': slope, 'intercept': intercept}
                            crit_thresholds[mcda_concept] = threshold
            thresholds[criterion_id] = crit_thresholds
        else:
            thresholds[criterion_id] = {}
    return thresholds


def _get_intersection_distillation(xmltree, altId):
    """Allows for using 'intersection_distillation.xml' file  instead of
    'outranking.xml'.
    """
    mcdaConcept = 'Intersection of upwards and downwards distillation'
    strSearch = (".//alternativesComparisons"
                 "[@mcdaConcept=\'" + mcdaConcept + "\']")
    comparisons = xmltree.xpath(strSearch)
    if comparisons == []:
        return
    else:
        comparisons = comparisons[0]
        datas = {}
        for pair in comparisons.findall("pairs/pair"):
            init = pair.find("initial/alternativeID").text
            term = pair.find("terminal/alternativeID").text
            if altId.count(init) > 0:
                if altId.count(term) > 0:
                    if init not in datas:
                        datas[init] = {}
                    datas[init][term] = 1.0
        return datas


def _get_outranking_crisp(xmltree, mcda_concept=None):
    if xmltree is None:
        return None
    if mcda_concept is None:
        str_search = ".//alternativesComparisons"
    else:
        str_search = (".//alternativesComparisons"
                      "[@mcdaConcept=\'" + mcda_concept + "\']")
    comparisons = xmltree.xpath(str_search)[0]
    if comparisons is None:
        return {}
    else:
        ret = Vividict()
        for pair in comparisons.findall("pairs/pair"):
            initial = pair.find("initial/alternativeID").text
            terminal = pair.find("terminal/alternativeID").text
            ret[initial][terminal] = True
        return ret


def _get_alternatives_comparisons(xmltree, alternatives,
                                  categories_profiles=None, use_partials=False,
                                  mcda_concept=None):
    """Parameter 'use_partials' designates whether the input contains 'partial'
    (i.e. per-criterion) comparisons.
    """
    def _get_value(value_node):
        if value_node.find('integer') is not None:
            value = int(value_node.find('integer').text)
        elif value_node.find('real') is not None:
            value = float(value_node.find('real').text)
        elif value_node.find('label') is not None:
            value = value_node.find('label').text
        elif value_node.find('boolean') is not None:
            value = value_node.find('boolean').text
            if value == 'true':
                value = True
            elif value == 'false':
                value = False
            else:
                value = None
        else:
            value = None
        return value

    if xmltree is None:
        return None
    if mcda_concept is None:
        str_search = ".//alternativesComparisons"
    else:
        str_search = (".//alternativesComparisons"
                      "[@mcdaConcept=\'" + mcda_concept + "\']")
    comparisons = xmltree.xpath(str_search)[0]
    if comparisons is None:
        return {}
    else:
        ret = Vividict()
        for pair in comparisons.findall("pairs/pair"):
            initial = pair.find("initial/alternativeID").text
            terminal = pair.find("terminal/alternativeID").text
            if not use_partials:
                value_node = pair.find("value")
                if value_node is None:
                    f = os.path.split(xmltree.base)[-1]
                    msg = ("Corrupted '{}' file or wrong value of the "
                           "'use_partials' parameter.".format(f))
                    raise InputDataError(msg)
                value = _get_value(value_node)
            else:
                value_nodes = pair.find("values")
                if value_nodes is None:
                    f = os.path.split(xmltree.base)[-1]
                    msg = ("Corrupted '{}' file or wrong value of the "
                           "'use_partials' parameter.".format(f))
                    raise InputDataError(msg)
                values = Vividict()
                for value_node in value_nodes:
                    value_node_id = value_node.get("id")
                    values[value_node_id] = _get_value(value_node)
            if initial in alternatives or initial in categories_profiles:
                if terminal in alternatives or terminal in categories_profiles:
                    if initial not in ret:
                        ret[initial] = Vividict()
                    ret[initial][terminal] = values if use_partials else value
        return ret


# XXX not sure if it's a good idea to return two different data structures
# here, i.e.: for boundary profiles: ['b1', 'b2', 'b3', 'b4'], for central
# profiles: {'b1': 'C2', 'b2': 'C2', 'b3': 'C3'}.
def _get_categories_profiles(tree, comparison_with):

    def _get_profiles_ordering(last_found, profiles):
        """Gets the ordering of categories (classes) profiles."""
        for i in categories_profiles_full.values():
            if i.get('lower') == last_found:
                if i.get('upper') is None:
                    return
                profiles.append(i.get('upper'))
                last_found = profiles[-1]
                break
        _get_profiles_ordering(last_found, profiles)

    if tree is None and comparison_with in ('boundary_profiles',
                                            'central_profiles'):
        raise InputDataError("Missing definitions of profiles (did you "
                             "forget about 'classes_profiles.xml'?).")
    if comparison_with == 'alternatives':
        categories_profiles = None
    elif comparison_with == 'boundary_profiles':
        categories_profiles = []
        # ####### different options which are available here:
        # ### categories_profiles e.g. ['pMG', 'pBM']
        # path = '//categoriesProfiles//alternativeID/text()'
        # categories_profiles = [profile for profile in tree.xpath(path)]
        # ### categories_names e.g. ['Bad', 'Medium', 'Good']
        # categories_names = list(set(tree.xpath('//categoriesProfiles//limits//categoryID/text()')))
        # ### categories_profiles_full e.g.:
        # {'Bad': {'upper': 'pBM'}, 'Medium': {'upper': 'pMG', 'lower': 'pBM'},
        #  'Good': {'lower': 'pMG'}}
        # categories_profiles_full = px.getCategoriesProfiles(tree, categories_names)
        if len(tree.findall('.//limits')) > 0:
            xpath = '//categoriesProfiles//limits//categoryID/text()'
            categories_names = list(set(tree.xpath(xpath)))
            categories_profiles_full = px.getCategoriesProfiles(tree, categories_names)
            _get_profiles_ordering(None, categories_profiles)
    elif comparison_with == 'central_profiles':
        categories_profiles = {}
        for xmlprofile in tree.findall(".//categoryProfile"):
            try:
                profile_id = xmlprofile.find("alternativeID").text
                category = xmlprofile.find("central/categoryID").text
                categories_profiles[profile_id] = category
            except:
                categories_profiles = {}
                break
    else:
        raise InputDataError("Wrong comparison type ('{}') specified."
                             .format(comparison_with))
    return categories_profiles

#use
def _get_criteria_interactions(xmltree, criteria_allowed):
    """In the returned dict 'interactions', the most outer key designates
    direction of the interaction effect (i.e. which criterion is affected),
    which is significant in case of 'antagonistic' interaction.
    """
    interaction_types_allowed = ['strengthening', 'weakening', 'antagonistic']
    path = 'criteriaValues[@mcdaConcept="criteriaInteractions"]/criterionValue'
    interactions = {}
    cvs = xmltree.xpath(path)
    if not cvs:
        raise InputDataError("Wrong or missing definitions for criteria "
                             "interactions.")
    for cv in cvs:
        interaction_type = cv.attrib.get('mcdaConcept')
        if interaction_type not in interaction_types_allowed:
            raise InputDataError("Wrong interaction type '{}'."
                                 .format(interaction_type))
        criteria_involved = cv.xpath('.//criterionID/text()')
        if len(criteria_involved) != 2:
            raise InputDataError("Wrong number of criteria for '{}' interaction."
                                 .format(interaction_type))
        for criterion in criteria_involved:
            if criterion not in criteria_allowed:
                raise InputDataError("Unknown criterion '{}' for '{}' interaction."
                                     .format(criterion, interaction_type))
        interaction_value = float(cv.find('./value//').text)
        if ((interaction_value > 0 and interaction_type == 'weakening') or
                (interaction_value < 0 and interaction_type in ('strengthening', 'antagonistic')) or
                (interaction_value == 0)):
            raise InputDataError("Wrong value for '{}' interaction."
                                 .format(interaction_type))
        if interaction_type == 'strengthening' and 'weakening' in interactions.keys():
            for i in interactions['weakening']:
                if set(i[:2]) == set(criteria_involved):
                    raise InputDataError("'strengthening' and 'weakening' "
                                         "interactions are mutually exclusive.")
        elif interaction_type == 'weakening' and 'strengthening' in interactions.keys():
            for i in interactions['strengthening']:
                if set(i[:2]) == set(criteria_involved):
                    raise InputDataError("'strengthening' and 'weakening' "
                                         "interactions are mutually exclusive.")
        c1, c2 = criteria_involved
        try:
            interactions[interaction_type].append((c1, c2, interaction_value))
        except KeyError:
            interactions.update({interaction_type: [(c1, c2, interaction_value)]})
    return interactions


def get_input_data(input_dir, filenames, params, **kwargs):
    """Looks for files specified by 'filenames' in directory specified by
    'input_dir'. Gets the data from these files according to what is specified
    in 'params'. Every such param is handled (i.e., loaded and to some extent
    verified) by a function associated with it in '_functions_dict'.
    """
    #use
    def get_alternatives(*args, **kwargs):
        alternatives = px.getAlternativesID(trees['alternatives'])
        return alternatives  # list

    #use
    # TODO merge _get_categories_profiles with this function
    def get_categories_profiles(*args, **kwargs):
        comparison_with = kwargs.get('comparison_with')
        if comparison_with is None:
            comparison_with = px.getParameterByName(
                trees['method_parameters'],
                'comparison_with',
            )
        categories_profiles = _get_categories_profiles(
            trees.get('categories_profiles'),
            comparison_with,
        )
        return categories_profiles  # NoneType, dict, list

    def get_categories_rank(*args, **kwargs):
        categories = px.getCategoriesID(trees['categories'])
        categories_rank = px.getCategoriesRank(trees['categories'], categories)
        return categories_rank  # dict

    def get_concordance(*args, **kwargs):
        alternatives = px.getAlternativesID(trees['alternatives'])
        comparison_with = px.getParameterByName(
            trees['method_parameters'],
            'comparison_with',
        )
        if comparison_with in ('boundary_profiles', 'central_profiles'):
            categories_profiles = _get_categories_profiles(
                trees['categories_profiles'],
                comparison_with,
            )
            concordance = _get_alternatives_comparisons(
                trees['concordance'],
                alternatives,
                categories_profiles,
            )
        else:
            concordance = px.getAlternativesComparisons(
                trees['concordance'],
                alternatives,
            )
        return concordance  # Vividict, dict

    def get_aggregated_preferences(*args, **kwargs):
        alternatives = px.getAlternativesID(trees['alternatives'])
        comparison_with = px.getParameterByName(
            trees['method_parameters'],
            'comparison_with',
        )
        if comparison_with in ('boundary_profiles', 'central_profiles'):
            categories_profiles = _get_categories_profiles(
                trees['categories_profiles'],
                comparison_with,
            )
            concordance = _get_alternatives_comparisons(
                trees['concordance'],
                alternatives,
                categories_profiles,
            )
        else:
            concordance = px.getAlternativesComparisons(
                trees['aggregated_preferences'],
                alternatives,
            )
        return concordance  # Vividict, dict

    def get_credibility(*args, **kwargs):
        alternatives = px.getAlternativesID(trees['alternatives'])
        comparison_with = kwargs.get('comparison_with')
        if not comparison_with:
            comparison_with = px.getParameterByName(
                trees['method_parameters'],
                'comparison_with',
            )
        if comparison_with in ('boundary_profiles', 'central_profiles'):
            categories_profiles = _get_categories_profiles(
                trees['categories_profiles'],
                comparison_with,
            )
        else:
            categories_profiles = None
        eliminate_cycles_method = px.getParameterByName(
            trees.get('method_parameters'),
            'eliminate_cycles_method',
        )
        tree = trees.get('credibility')
        if eliminate_cycles_method == 'cut_weakest' and tree is None:
            raise InputDataError(
                "'cut_weakest' option requires credibility as an additional "
                "input (apart from outranking)."
            )
        credibility = _get_alternatives_comparisons(
            tree,
            alternatives,
            categories_profiles=categories_profiles,
        )
        return credibility  # NoneType, Vividict

    #use
    def get_criteria(*args, **kwargs):
        criteria = px.getCriteriaID(trees['criteria'])
        return criteria  # list

    def get_cut_threshold(*args, **kwargs):
        cut_threshold = px.getParameterByName(
            trees['method_parameters'],
            'cut_threshold',
        )
        if cut_threshold is None or not (0 <= float(cut_threshold) <= 1):
            raise InputDataError(
                "'cut_threshold' should be in range [0, 1] "
                "(most commonly used values are 0.6 or 0.7)."
            )
        return cut_threshold  # float

    def get_cv_crossed(*args, **kwargs):
        # 'cv_crossed' stands for 'counter-veto crossed'
        alternatives = px.getAlternativesID(trees['alternatives'])
        comparison_with = px.getParameterByName(
            trees['method_parameters'],
            'comparison_with',
        )
        if comparison_with in ('boundary_profiles', 'central_profiles'):
            categories_profiles = _get_categories_profiles(
                trees['categories_profiles'],
                comparison_with,
            )
        else:
            categories_profiles = None
        cv_crossed = _get_alternatives_comparisons(
            trees['counter_veto_crossed'],
            alternatives,
            categories_profiles=categories_profiles,
            use_partials=True,
            mcda_concept='counterVetoCrossed',
        )
        return cv_crossed  # Vividict

    def get_discordance(*args, **kwargs):
        alternatives = px.getAlternativesID(trees['alternatives'])
        comparison_with = px.getParameterByName(
            trees['method_parameters'],
            'comparison_with',
        )
        if kwargs.get('use_partials') is not None:
            use_partials = kwargs.get('use_partials')
        else:
            parameter = px.getParameterByName(
                trees['method_parameters'],
                'use_partials',
            )
            use_partials = True if parameter == 'true' else False
        if comparison_with in ('boundary_profiles', 'central_profiles'):
            categories_profiles = _get_categories_profiles(
                trees['categories_profiles'],
                comparison_with,
            )
        else:
            categories_profiles = None
        discordance = _get_alternatives_comparisons(
            trees['discordance'],
            alternatives,
            categories_profiles=categories_profiles,
            use_partials=use_partials,
        )
        return discordance  # Vividict

    #use
    def get_interactions(*args, **kwargs):
        criteria = px.getCriteriaID(trees['criteria'])
        interactions = _get_criteria_interactions(
            trees['interactions'],
            criteria,
        )
        return interactions  # dict

    def get_outranking(*args, **kwargs):
        outranking = _get_outranking_crisp(trees['outranking'])
        return outranking  # Vividict

    #use
    def get_performances(*args, **kwargs):
        performances = px.getPerformanceTable(trees['performance_table'], None, None)
        return performances  # dict

    #use
    def get_pref_directions(*args, **kwargs):
        criteria = px.getCriteriaID(trees['criteria'])
        pref_directions = px.getCriteriaPreferenceDirections(
            trees['criteria'],
            criteria,
        )
        return pref_directions  # dict

    #use
    def get_profiles_performance_table(*args, **kwargs):
        comparison_with = px.getParameterByName(
            trees['method_parameters'],
            'comparison_with',
        )
        if comparison_with in ('boundary_profiles', 'central_profiles'):
            tree = trees.get('profiles_performance_table')
            if tree is None:
                msg = (
                    "Missing profiles performance table (did you forget "
                    "to provide 'profiles_performance_table.xml' file?)."
                )
                raise InputDataError(msg)
            profiles_performance_table = px.getPerformanceTable(tree, None, None)
        else:
            profiles_performance_table = None
        return profiles_performance_table  # NoneType, dict

    #use
    def get_reinforcement_factors(*args, **kwargs):
        criteria = px.getCriteriaID(trees['criteria'])
        factors = {}
        for c in criteria:
            rf = px.getCriterionValue(
                trees['reinforcement_factors'],
                c,
                'reinforcement_factors'
            )
            if len(rf) == 0:
                continue
            if rf.get(c) <= 1:
                msg = (
                    "Reinforcement factor for criterion '{}' should be "
                    "higher than 1.0 (ideally between 1.2 and 1.5)."
                )
                raise InputDataError(msg)
            factors.update(rf)
        return factors  # dict

    # TODO merge _get_thresholds with this function
    def get_thresholds(*args, **kwargs):
        thresholds = _get_thresholds(trees['criteria'])
        return thresholds  # dict

    #use
    def get_weights(*args, **kwargs):
        criteria = px.getCriteriaID(trees['criteria'])
        if len(criteria) == 0:
            msg = (
                "File 'criteria.xml' doesn't contain valid data for this "
                "method."
            )
            raise InputDataError(msg)
        weights = px.getCriterionValue(trees['weights'], criteria)
        return weights  # dict

    def get_param_boolean(param_name, *args, **kwargs):
        parameter = px.getParameterByName(
            trees['method_parameters'],
            param_name,
        )
        return True if parameter == 'true' else False

    #use
    def get_param_string(param_name, *args, **kwargs):
        param = px.getParameterByName(trees['method_parameters'], param_name)
        return param

    #use
    def get_param_real(param_name, *args, **kwargs):
        param = px.getParameterByName(trees['method_parameters'], param_name)
        return float(param)

    #use
    def get_param_integer(param_name, *args, **kwargs):
        param = px.getParameterByName(trees['method_parameters'], param_name)
        return int(param)

    #use
    def get_generalised_criteria(with_gaussian, *args, **kwargs):
        function_ID_set = ('1','2','3','4','5')
        function_ID_set_int = {1,2,3,4,5}
        if with_gaussian:
            function_ID_set = ('1','2','3','4','5','6')
            function_ID_set_int = {1,2,3,4,5,6}
        generalised_param = get_param_string("generalised_criterion", *args, **kwargs)
        if generalised_param in ('specified'):
            criteria = px.getCriteriaID(trees['criteria'])
            factors = {}
            gc = px.getCriterionValue(
                    trees['generalised_criteria'],
                    criteria,
                    'generalised_criteria')
            for c in criteria:
                if gc.get(c) not in function_ID_set_int:
                    msg = ("Generalised criterion should be iteger value between 1 and 5).")
                    if with_gaussian:
                        msg = ("Generalised criterion should be iteger value between 1 and 6).")
                    raise InputDataError(msg)
            factors = gc
        else:
            if generalised_param in function_ID_set:
                criteria = px.getCriteriaID(trees['criteria'])
                factors={}
                for c in criteria:
                    values = {}
                    values[c] = int(generalised_param)
                    factors.update(values)
            else:
                factors = None;
        return factors  # dict
    #use
    def get_generalised_criteria_with_gaussian(*args, **kwargs):
        return get_generalised_criteria(True, *args, **kwargs)
    #use
    def get_generalised_criteria_without_gaussian(*args, **kwargs):
        return get_generalised_criteria(False, *args, **kwargs)

    # use
    def get_criteria_ranking(*args, **kwargs):
        criteria = px.getCriteriaID(trees['criteria'])
        if len(criteria) == 0:
            msg = (
                "File 'criteria.xml' doesn't contain valid data for this "
                "method."
            )
            raise InputDataError(msg)
        ranking = px.getCriterionValue(trees['criteria_ranking'], criteria)
        return ranking  # dict

    _functions_dict = {
        'alternatives': get_alternatives,
        'categories_profiles': get_categories_profiles,
        'categories_rank': get_categories_rank,
        'concordance': get_concordance,
        'comparison_with': partial(get_param_string, 'comparison_with'),
        'credibility': get_credibility,
        'criteria': get_criteria,
        'cut_threshold': get_cut_threshold,
        'cv_crossed': get_cv_crossed,
        'discordance': get_discordance,
        'eliminate_cycles_method': partial(get_param_string, 'eliminate_cycles_method'),
        'interactions': get_interactions,
        'only_max_discordance': partial(get_param_boolean, 'only_max_discordance'),
        'outranking': get_outranking,
        'performances': get_performances,
        'pref_directions': get_pref_directions,
        'profiles_performance_table': get_profiles_performance_table,
        'reinforcement_factors': get_reinforcement_factors,
        'thresholds': get_thresholds,
        'weights': get_weights,
        'with_denominator': partial(get_param_boolean, 'with_denominator'),
        'use_partials': partial(get_param_boolean, 'use_partials'),
        'use_pre_veto': partial(get_param_boolean, 'use_pre_veto'),
        'z_function': partial(get_param_string, 'z_function'),
        'generalised_criteria': get_generalised_criteria_with_gaussian,
        'generalised_criteria_without_gaussian': get_generalised_criteria_without_gaussian,
        'criteria_ranking': get_criteria_ranking,
        'criteria_weight_ratio': partial(get_param_real, 'criteria_weight_ratio'),
        'decimal_places': partial(get_param_integer, 'decimal_places'),
        'aggregated_preferences': get_aggregated_preferences,
    }

    args = (input_dir, filenames, params)
    trees = _get_trees(input_dir, filenames)
    d = _create_data_object(params)
    for p in params:
        try:
            f = _functions_dict[p]
        except AttributeError:
            raise InputDataError("Unknown parameter '{}' specified.".format(p))
        try:
            v = f(*args, **kwargs)
            setattr(d, p, v)
        except Exception as e:
            if type(e) is InputDataError:
                raise
            else:
                msg = (
                    "{} '{}.xml'. {}"
                    .format(INPUT_DATA_ERROR_MSG, p, INPUT_DATA_ERROR_HINT)
                )
                raise InputDataError(msg)
        # this check below may be a bit unnecessary, but it won't hurt either
        if type(v) in (list, dict, Vividict) and len(v) == 0:
            msg = (
                "File '{}.xml' doesn't contain valid data for this method."
                .format(p)
            )
            raise InputDataError(msg)
    return d


###############################################################################
# Converting the output into the XMCDA format.                                #
###############################################################################

def outranking_flows_to_xmcda(flows, mcda_concept):
    if not mcda_concept:
        xmcda = etree.Element('alternativesValues',
                              mcda_concept = 'outranking_flows')
    else:
        xmcda = etree.Element('alternativesValues',
                              mcdaConcept=mcda_concept)
    for flow in sorted(flows.items(), key=lambda x: x[0]):
        alternative_value = etree.SubElement(xmcda, 'alternativeValue')
        alternative_id = etree.SubElement(alternative_value, 'alternativeID')
        alternative_id.text = flow[0]
        value = etree.SubElement(alternative_value, 'value')
        real = etree.SubElement(value, 'real')
        real.text = str(flow[1])
    return xmcda

# 'comparables' should be a tuple e.g. (('a01', 'a02', 'a03'), ('b01', 'b02')).
# The order of nodes in xml file will be derived from its content.
# All the sorting should be done here (i.e. before serialization), I think.
def comparisons_to_xmcda(comparisons, comparables, use_partials=False,
                         mcda_concept=None):

    # XXX maybe it's better to get/set those types globally?
    # (i.e. for the whole file)
    def _get_value_type(value):
        if type(value) == float:
            value_type = 'real'
        elif type(value) == int:
            value_type = 'integer'
        elif type(value) in (str, unicode):
            value_type = 'label'
        elif type(value) == bool:
            value_type = 'boolean'
        else:
            raise RuntimeError("Unknown type '{}'.".format(type(value)))
        return value_type

    if len(comparables) != 2:
        raise RuntimeError("You have to specify exactly 2 comparables for "
                           "this serialization function (instead of {})."
                           .format(len(comparables)))
    elif comparables[0] == comparables[1]:  # alternatives vs alternatives
        ordering = [(a, b) for a in comparables[0] for b in comparables[0]]
    else:  # alternatives vs profiles
        ordering = []
        for a in comparables[0]:
            for b in comparables[1]:
                ordering.append((a, b))
        for b in comparables[1]:
            for a in comparables[0]:
                ordering.append((b, a))
    if not mcda_concept:
        xmcda = etree.Element('alternativesComparisons')
    else:
        xmcda = etree.Element('alternativesComparisons',
                              mcdaConcept=mcda_concept)
    pairs = etree.SubElement(xmcda, 'pairs')
    for alt1, alt2 in ordering:
        pair = etree.SubElement(pairs, 'pair')
        initial = etree.SubElement(pair, 'initial')
        alt_id = etree.SubElement(initial, 'alternativeID')
        alt_id.text = alt1
        terminal = etree.SubElement(pair, 'terminal')
        alt_id = etree.SubElement(terminal, 'alternativeID')
        alt_id.text = alt2
        if not use_partials:
            value_type = _get_value_type(comparisons[alt1][alt2])
            value_node = etree.SubElement(pair, 'value')
            v = etree.SubElement(value_node, value_type)
            if value_type == 'boolean':
                v.text = 'true' if comparisons[alt1][alt2] is True else 'false'
            else:
                v.text = str(comparisons[alt1][alt2])
        else:
            values = etree.SubElement(pair, 'values')
            items = comparisons[alt1][alt2].items()
            items.sort(key=lambda x: x[0])  # XXX until I find better solution
            for i in items:
                value_type = _get_value_type(i[1])
                value_node = etree.SubElement(values, 'value', id=i[0])
                v = etree.SubElement(value_node, value_type)
                if value_type == 'boolean':
                    v.text = 'true' if i[1] is True else 'false'
                else:
                    v.text = str(i[1])
    return xmcda


def outranking_to_xmcda(outranking, mcda_concept=None):

    def _extract(dict_in, list_of_tuples_out, outer_key=None):
        """Extracts a list of (k, v) tuples from nested dicts."""
        for key, value in dict_in.iteritems():
            if isinstance(value, dict):
                _extract(value, list_of_tuples_out, outer_key=key)
            elif isinstance(value, bool):
                list_of_tuples_out.append((outer_key, key))
        return list_of_tuples_out

    if not mcda_concept:
        xmcda = etree.Element('alternativesComparisons')
    else:
        xmcda = etree.Element('alternativesComparisons',
                              mcdaConcept=mcda_concept)
    pairs_node = etree.SubElement(xmcda, 'pairs')
    pairs = []
    _extract(outranking, pairs)
    # tuples are sorted lexographically, so there's no need for lambda as a key
    pairs.sort()
    for pair in pairs:
        pair_node = etree.SubElement(pairs_node, 'pair')
        initial_node = etree.SubElement(pair_node, 'initial')
        alt_node = etree.SubElement(initial_node, 'alternativeID')
        alt_node.text = pair[0]
        terminal_node = etree.SubElement(pair_node, 'terminal')
        alt_node = etree.SubElement(terminal_node, 'alternativeID')
        alt_node.text = pair[1]
    return xmcda


# XXX maybe passing alternatives as a second argument and using them for
# sorting would be a good idea here?
def assignments_to_xmcda(assignments):
    xmcda = etree.Element('alternativesAffectations')
    for assignment in sorted(assignments.items(), key=lambda x: x[0]):
        alt_assignment = etree.SubElement(xmcda, 'alternativeAffectation')
        alt_id = etree.SubElement(alt_assignment, 'alternativeID')
        alt_id.text = assignment[0]
        category_id = etree.SubElement(alt_assignment, 'categoryID')
        category_id.text = assignment[1]
    return xmcda

# XXX maybe passing alternatives as a second argument and using them for
# sorting would be a good idea here?
def assignments_as_intervals_to_xmcda(assignments):
    xmcda = etree.Element('alternativesAffectations')
    for assignment in sorted(assignments.items(), key=lambda x: x[0]):
        alt_assignment = etree.SubElement(xmcda, 'alternativeAffectation')
        alt_id = etree.SubElement(alt_assignment, 'alternativeID')
        alt_id.text = assignment[0]
        categories_interval = etree.SubElement(alt_assignment,
                                               'categoriesInterval')
        # 'descending', 'pessimistic', 'conjunctive'
        lower_bound = etree.SubElement(categories_interval, 'lowerBound')
        category_id = etree.SubElement(lower_bound, 'categoryID')
        category_id.text = assignment[1][0]
        # 'ascending', 'optimistic', 'disjunctive'
        upper_bound = etree.SubElement(categories_interval, 'upperBound')
        category_id = etree.SubElement(upper_bound, 'categoryID')
        category_id.text = assignment[1][1]
    return xmcda

#use
def weights_to_xmcda(weights, mcda_concept):
    xmcda = etree.Element('criteriaValues',mcdaConcept=mcda_concept)
    for weight in sorted(weights.items(), key=lambda x: x[0]):
        criterion_weight = etree.SubElement(xmcda, 'criterionValue')
        criterion_weight_id = etree.SubElement(criterion_weight, 'criterionID')
        criterion_weight_id.text = weight[0]
        criterion_weight_value = etree.SubElement(criterion_weight, 'value')
        criterion_weight_real = etree.SubElement(criterion_weight_value, 'real')
        criterion_weight_real.text = str(weight[1])
    return xmcda



###############################################################################
# Dealing with the output files etc.                                          #
###############################################################################
#use
def write_xmcda(xmcda, filename):
    et = etree.ElementTree(xmcda)
    try:
        with open(filename, 'w') as f:
            f.write(HEADER)
            et.write(f, pretty_print=True, encoding='UTF-8')
            f.write(FOOTER)
    except IOError as e:
        raise IOError("{}: '{}'".format(e.strerror, e.filename))

#use
def print_xmcda(xmcda):
    """Takes etree.Element as input and pretty-prints it."""
    print(etree.tostring(xmcda, pretty_print=True))

#use
def get_error_message(err):
    exception = re.findall("\.([a-zA-Z]+)'", str(type(err)))[0]
    err_msg = ': '.join((exception, str(err)))
    return err_msg

#use
def create_messages_file(error_messages, log_messages, out_dir):
    if not out_dir:
        return
    xmcda = etree.Element('methodMessages')
    if error_messages:
        for err_msg in error_messages:
            err_msg_node = etree.SubElement(xmcda, 'errorMessage')
            err_msg_node_text = etree.SubElement(err_msg_node, 'text')
            err_msg_node_text.text = etree.CDATA(err_msg.strip())
    if log_messages:
        for log_msg in log_messages:
            log_msg_node = etree.SubElement(xmcda, 'logMessage')
            log_msg_node_text = etree.SubElement(log_msg_node, 'text')
            log_msg_node_text.text = etree.CDATA(log_msg.strip())
    write_xmcda(xmcda, os.path.join(out_dir, 'messages.xml'))
