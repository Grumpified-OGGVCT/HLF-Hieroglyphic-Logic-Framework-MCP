"""HLF stdlib: math module."""

import math as _math


def MATH_ABS(x):
    return abs(x)


def MATH_FLOOR(x):
    return _math.floor(x)


def MATH_CEIL(x):
    return _math.ceil(x)


def MATH_ROUND(x):
    return round(x)


def MATH_MIN(a, b):
    return min(a, b)


def MATH_MAX(a, b):
    return max(a, b)


def MATH_POW(base, exp):
    return _math.pow(base, exp)


def MATH_SQRT(x):
    return _math.sqrt(x)


def MATH_LOG(x):
    return _math.log(x)


def MATH_SIN(x):
    return _math.sin(x)


def MATH_COS(x):
    return _math.cos(x)


def MATH_TAN(x):
    return _math.tan(x)


def MATH_PI():
    return _math.pi


def MATH_E():
    return _math.e
