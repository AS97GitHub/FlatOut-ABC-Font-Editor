"""Codepoint / symbol parsing helpers shared by the editor dialogs."""
import re


class CodepointMixin:
    """Parsing of codepoints, symbol lists and glyph-index lists."""

    @staticmethod
    def _format_codepoint_char(codepoint):
        if codepoint == 0x20:
            return "Space"
        if codepoint < 0x20 or codepoint == 0x7F:
            return ""
        if 0x80 <= codepoint <= 0x9F:
            return ""
        try:
            return chr(codepoint)
        except (ValueError, OverflowError):
            return ""

    def parse_symbol_delete_text(self, text):
        codepoints = set()
        token_re = re.compile(r".", re.DOTALL)

        def parse_code(token):
            try:
                return self.parse_single_codepoint(token)
            except ValueError:
                return None

        for raw in re.split(r"[\s,;]+", text):
            token = raw.strip()
            if not token:
                continue

            range_match = re.fullmatch(
                r"(U\+[0-9A-Fa-f]{1,6}|0x[0-9A-Fa-f]{1,6}|\d+|.)-(U\+[0-9A-Fa-f]{1,6}|0x[0-9A-Fa-f]{1,6}|\d+|.)",
                token,
                re.DOTALL
            )
            if range_match:
                start = parse_code(range_match.group(1))
                end = parse_code(range_match.group(2))
                if start is not None and end is not None:
                    if start > end:
                        start, end = end, start
                    codepoints.update(range(start, end + 1))
                    continue

            parsed = parse_code(token)
            if parsed is not None:
                codepoints.add(parsed)
                continue

            for match in token_re.finditer(token):
                char = match.group(0)
                if char not in "\r\n\t ":
                    parsed_char = parse_code(char)
                    if parsed_char is not None:
                        codepoints.add(parsed_char)

        return {c for c in codepoints if 0 <= c <= 0x10FFFF}

    def parse_single_codepoint(self, text):
        token = text.strip()
        if not token:
            return None
        if token.upper().startswith("U+"):
            return int(token[2:], 16)
        if token.lower().startswith("0x"):
            return int(token[2:], 16)
        if token.isdigit():
            return int(token, 10)
        return ord(token[0])

    def parse_index_delete_text(self, text):
        indexes = set()
        for raw in re.split(r"[\s,;]+", text):
            token = raw.strip()
            if not token:
                continue

            range_match = re.fullmatch(r"(\d+)-(\d+)", token)
            if range_match:
                start = int(range_match.group(1))
                end = int(range_match.group(2))
                if start > end:
                    start, end = end, start
                indexes.update(range(start, end + 1))
                continue

            if token.isdigit():
                indexes.add(int(token))

        return indexes
