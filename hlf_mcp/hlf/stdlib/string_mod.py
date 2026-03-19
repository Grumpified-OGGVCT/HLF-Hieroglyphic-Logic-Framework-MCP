"""HLF stdlib: string module."""


def STRING_LENGTH(s):
    return len(str(s))


def STRING_CONCAT(s1, s2):
    return str(s1) + str(s2)


def STRING_SPLIT(s, sep):
    return str(s).split(sep)


def STRING_JOIN(parts, sep):
    return sep.join(str(p) for p in parts)


def STRING_UPPER(s):
    return str(s).upper()


def STRING_LOWER(s):
    return str(s).lower()


def STRING_TRIM(s):
    return str(s).strip()


def STRING_REPLACE(s, old, new):
    return str(s).replace(old, new)


def STRING_CONTAINS(s, sub):
    return sub in str(s)


def STRING_STARTS_WITH(s, prefix):
    return str(s).startswith(prefix)


def STRING_ENDS_WITH(s, suffix):
    return str(s).endswith(suffix)


def STRING_SUBSTRING(s, start, end):
    return str(s)[start:end]
