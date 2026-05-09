from __future__ import annotations

import re
from typing import Any


class CharacterSourceTools:
    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks

    def get_source_snippets(
        self,
        references: list[dict[str, Any]],
        query_terms: list[str] | None = None,
        *,
        max_snippets: int = 4,
        window_chars: int = 900,
    ) -> list[dict[str, Any]]:
        """
        Recupera fragmentos originales asociados a referencias de personaje.
        """
        snippets: list[dict[str, Any]] = []
        seen: set[tuple[int, str]] = set()

        for reference in references or []:
            chunk_index = reference.get("chunk_index")
            local_id = str(reference.get("local_id") or "")

            if not isinstance(chunk_index, int):
                continue

            if chunk_index < 0 or chunk_index >= len(self.chunks):
                continue

            key = (chunk_index, local_id)
            if key in seen:
                continue
            seen.add(key)

            snippet = self._best_snippet(
                self.chunks[chunk_index],
                query_terms=query_terms or [local_id],
                window_chars=window_chars,
            )

            snippets.append(
                {
                    "chunk_index": chunk_index,
                    "local_id": local_id,
                    "snippet": snippet,
                }
            )

            if len(snippets) >= max_snippets:
                break

        return snippets

    def find_character_mentions(
        self,
        name_or_aliases: list[str],
        *,
        max_mentions: int = 6,
        window_chars: int = 500,
    ) -> list[dict[str, Any]]:
        """
        Busca menciones textuales de nombres o alias en todos los chunks.
        """
        terms = self._clean_terms(name_or_aliases)
        mentions: list[dict[str, Any]] = []

        if not terms:
            return mentions

        seen_locations: set[tuple[int, str, int]] = set()

        for chunk_index, chunk_text in enumerate(self.chunks):
            for term in terms:
                match = self._find_term(chunk_text, term)
                if not match:
                    continue

                key = (chunk_index, term.lower(), match.start())
                if key in seen_locations:
                    continue
                seen_locations.add(key)

                mentions.append(
                    {
                        "chunk_index": chunk_index,
                        "query": term,
                        "matched_text": match.group(0),
                        "snippet": self._window_around(
                            chunk_text,
                            start=match.start(),
                            end=match.end(),
                            window_chars=window_chars,
                        ),
                    }
                )

                if len(mentions) >= max_mentions:
                    return mentions

        return mentions

    def _best_snippet(
        self,
        chunk_text: str,
        *,
        query_terms: list[str],
        window_chars: int,
    ) -> str:
        for term in self._clean_terms(query_terms):
            match = self._find_term(chunk_text, term)
            if match:
                return self._window_around(
                    chunk_text,
                    start=match.start(),
                    end=match.end(),
                    window_chars=window_chars,
                )

        return self._trim_text(chunk_text, window_chars)

    def _find_term(self, text: str, term: str) -> re.Match[str] | None:
        pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", flags=re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return match

        return re.search(re.escape(term), text, flags=re.IGNORECASE)

    def _window_around(self, text: str, *, start: int, end: int, window_chars: int) -> str:
        half_window = max(80, window_chars // 2)
        snippet_start = max(0, start - half_window)
        snippet_end = min(len(text), end + half_window)
        snippet = text[snippet_start:snippet_end].strip()

        if snippet_start > 0:
            snippet = "..." + snippet
        if snippet_end < len(text):
            snippet = snippet + "..."

        return snippet

    def _trim_text(self, text: str, max_chars: int) -> str:
        cleaned = text.strip()

        if len(cleaned) <= max_chars:
            return cleaned

        return cleaned[:max_chars].rstrip() + "..."

    def _clean_terms(self, values: list[str]) -> list[str]:
        terms: list[str] = []
        seen: set[str] = set()

        for value in values:
            if not isinstance(value, str):
                continue

            term = value.strip()
            normalized = term.lower()

            if len(term) < 2 or normalized in seen:
                continue

            terms.append(term)
            seen.add(normalized)

        return terms
