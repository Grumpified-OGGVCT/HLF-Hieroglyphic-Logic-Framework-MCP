"""HLF stdlib: collections module."""


def LIST_LENGTH(lst):
    return len(lst)


def LIST_APPEND(lst, item):
    return list(lst) + [item]


def LIST_CONCAT(lst1, lst2):
    return list(lst1) + list(lst2)


def LIST_FILTER(lst, pred):
    return [x for x in lst if pred(x)] if callable(pred) else lst


def LIST_MAP(lst, fn):
    return [fn(x) for x in lst] if callable(fn) else lst


def LIST_REDUCE(lst, fn, initial):
    import functools

    return functools.reduce(fn, lst, initial) if callable(fn) else initial


def DICT_GET(d, key):
    return d.get(key) if isinstance(d, dict) else None


def DICT_SET(d, key, value):
    return {**d, key: value} if isinstance(d, dict) else {key: value}


def DICT_KEYS(d):
    return list(d.keys()) if isinstance(d, dict) else []


def DICT_VALUES(d):
    return list(d.values()) if isinstance(d, dict) else []
