"""Parsing de valeurs numeriques au format SPICE (suffixes d'ingenierie).

Necessaire pour perturber la valeur d'un composant R/C/L natif (ex: "1k",
"50e-15", "2.2u") lors de l'injection de fautes parametriques, alors que les
parametres nommes (ex: W=2e-6) des primitives de fonderie sont deja de
simples flottants et n'ont pas besoin de ce parsing.
"""

# Ordre important : 'meg' doit etre teste avant 'm' (sinon 'm' de 'meg' matche en premier).
_SUFFIXES = [
    ('t', 1e12), ('g', 1e9), ('meg', 1e6), ('k', 1e3),
    ('m', 1e-3), ('u', 1e-6), ('n', 1e-9), ('p', 1e-12), ('f', 1e-15),
]


class SpiceValueError(ValueError):
    pass


def parse_spice_value(text):
    """Convertit une chaine SPICE (ex: '1k', '50e-15', '2.2u', '3.3') en float.
    Leve SpiceValueError si le texte n'est pas une valeur numerique reconnaissable."""
    if text is None:
        raise SpiceValueError('Valeur vide')

    s = text.strip()
    if not s:
        raise SpiceValueError('Valeur vide')

    low = s.lower()

    for suffix, multiplier in sorted(_SUFFIXES, key=lambda item: -len(item[0])):
        if low.endswith(suffix) and len(low) > len(suffix):
            number_part = low[:-len(suffix)]
            try:
                return float(number_part) * multiplier
            except ValueError:
                continue

    try:
        return float(s)
    except ValueError:
        raise SpiceValueError('Valeur SPICE non reconnue: {!r}'.format(text))


def format_spice_value(value):
    """Formate un float en notation decimale simple, toujours acceptee par
    Spectre (pas besoin de reproduire un suffixe d'ingenierie a la sortie)."""
    return repr(float(value))
