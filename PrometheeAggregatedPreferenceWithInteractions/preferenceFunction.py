from math import exp

def UsualCriterion(difference_between_evaulations, p, q, s):
    if difference_between_evaulations <= 0:
        return 0;
    else:
        return 1;

def UShapeCriterion(difference_between_evaulations, p, q, s):
    if difference_between_evaulations <= q:
        return 0;
    else:
        return 1;

def VShapeCriterion(difference_between_evaulations, p, q, s):
    if difference_between_evaulations <= 0:
        return 0;
    if difference_between_evaulations > p:
        return 1;
    return difference_between_evaulations/p;

def LevelCriterion(difference_between_evaulations, p, q, s):
    if difference_between_evaulations <= q:
        return 0;
    if difference_between_evaulations > p:
        return 1;
    return 1/2;

def VShapeWithIndifferenceCriterion(difference_between_evaulations, p, q, s):
    if difference_between_evaulations <= q:
        return 0;
    if difference_between_evaulations > p:
        return 1;
    return (difference_between_evaulations-q)/(p-q);

def GaussianCriterion(difference_between_evaulations, p, q, s):
    if difference_between_evaulations <= 0:
        return 0;
    return 1-exp(-(difference_between_evaulations*difference_between_evaulations/2*s*s))

def get_difference_between_evaluations(pref_direction, ga, gb):
    difference_between_evaulations = 0
    if (pref_direction=="max"):
        difference_between_evaulations = ga - gb
    if (pref_direction=="min"):
        difference_between_evaulations = gb - ga
    return difference_between_evaulations