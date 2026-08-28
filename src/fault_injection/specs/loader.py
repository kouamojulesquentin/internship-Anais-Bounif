import json


class SpecsError(Exception):
    pass


def load_specs(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise SpecsError('specs.json doit contenir un objet JSON.')

    specs = {}

    for name, limits in data.items():
        if not isinstance(limits, dict):
            raise SpecsError('Specification invalide: {}'.format(name))

        lower = limits.get('min')
        upper = limits.get('max')

        if lower is None and upper is None:
            raise SpecsError('{} doit avoir min et/ou max.'.format(name))

        if lower is not None:
            lower = float(lower)
        if upper is not None:
            upper = float(upper)

        if lower is not None and upper is not None and lower > upper:
            raise SpecsError('min > max pour {}'.format(name))

        specs[name.lower()] = {'name': name, 'min': lower, 'max': upper}

    return specs
