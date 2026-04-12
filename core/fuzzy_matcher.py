"""
Fuzzy-Matching Algorithmus für Command Palette.

Implementiert Subsequenz-Scoring mit Bonus für:
- Wortgrenzen-Matches
- Präfix-Matches
- Kontinuierliche Sequenzen
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass
class FuzzyMatch:
    """Ein Fuzzy-Match-Ergebnis mit Score und ursprünglichem Item."""
    item: Any
    score: float
    display_text: str
    
    def __lt__(self, other: FuzzyMatch) -> bool:
        return self.score > other.score  # Höhere Scores zuerst


def fuzzy_match(query: str, candidates: list[tuple[str, Any]]) -> list[FuzzyMatch]:
    """
    Fuzzy-Matching mit Subsequenz-Scoring.
    
    Args:
        query: Suchstring (case-insensitive)
        candidates: Liste von (display_text, item) Tupeln
    
    Returns:
        Sortierte Liste der besten Matches
    """
    if not query.strip():
        return [FuzzyMatch(item, 0.0, text) for text, item in candidates]
    
    query = query.lower()
    matches: list[FuzzyMatch] = []
    
    for display_text, item in candidates:
        score = _calculate_score(query, display_text.lower())
        if score > 0:
            matches.append(FuzzyMatch(item, score, display_text))
    
    return sorted(matches)


def _calculate_score(query: str, text: str) -> float:
    """
    Berechnet den Fuzzy-Match-Score zwischen Query und Text.
    
    Scoring-Faktoren:
    - Subsequenz-Match (alle Zeichen in Reihenfolge gefunden)
    - Präfix-Bonus für Matches am Wortanfang
    - Kontinuierlichkeits-Bonus für aufeinanderfolgende Matches
    - Wortgrenzen-Bonus für Matches nach Leerzeichen/Punkten
    """
    if not query:
        return 1.0
    
    # Grundvoraussetzung: alle Query-Zeichen müssen als Subsequenz vorkommen
    if not _is_subsequence(query, text):
        return 0.0
    
    score = 0.0
    query_idx = 0
    consecutive_matches = 0
    
    for i, char in enumerate(text):
        if query_idx < len(query) and char == query[query_idx]:
            # Basis-Score für Match
            char_score = 1.0
            
            # Präfix-Bonus (Match am Textanfang)
            if i == 0:
                char_score *= 2.0
            
            # Wortgrenzen-Bonus (Match nach Leerzeichen, Punkt, Unterst rich)
            if i > 0 and text[i-1] in ' ._-/\\':
                char_score *= 1.5
            
            # Kontinuierlichkeits-Bonus
            consecutive_matches += 1
            char_score *= (1.0 + consecutive_matches * 0.1)
            
            score += char_score
            query_idx += 1
        else:
            consecutive_matches = 0
    
    # Normalisierung basierend auf Text- und Query-Länge
    length_penalty = 1.0 - (len(text) - len(query)) / max(len(text), 1)
    completeness_bonus = query_idx / len(query)
    
    return score * length_penalty * completeness_bonus


def _is_subsequence(query: str, text: str) -> bool:
    """Prüft ob alle Zeichen von Query in Reihenfolge in Text vorkommen."""
    query_idx = 0
    for char in text:
        if query_idx < len(query) and char == query[query_idx]:
            query_idx += 1
    return query_idx == len(query)