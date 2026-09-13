"""
Nettoyage des requetes de recherche (section 4.1, outil A1 du CDC).

Suppression des termes generiques qui font echouer la recherche AND stricte
de CKAN : "donnees", "fichier", "tableau", "csv", "excel", "xlsx", "json",
"xml". La comparaison est insensible a la casse et aux accents.
"""

import re
import unicodedata

_STOPWORDS = {"donnees", "fichier", "tableau", "csv", "excel", "xlsx", "json", "xml"}

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _fold(token: str) -> str:
    """Normalise un terme (minuscules, sans accents) pour comparaison."""
    normalized = unicodedata.normalize("NFKD", token)
    ascii_folded = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_folded.lower()


def clean_query(query: str) -> str:
    """
    Retire les termes generiques d'une requete de recherche.

    Args:
        query: Requete libre en langage naturel.

    Returns:
        La requete nettoyee, ou une chaine vide si elle ne contenait que
        des termes generiques.
    """
    if not query:
        return ""
    tokens = _WORD_RE.findall(query)
    kept = [token for token in tokens if _fold(token) not in _STOPWORDS]
    return " ".join(kept)
