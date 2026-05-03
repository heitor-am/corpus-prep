"""Normalização de texto: encoding fix + Unicode + cleanup.

Resolve a Q4 da atividade 03 (ftfy) e limpa caracteres de controle / whitespace
que vem de PDFs e OCR. Aplicado em cada Document antes da filtragem.
"""

from __future__ import annotations

import re
import unicodedata

import ftfy

# Caracteres de controle (0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F).
# Tab (0x09), LF (0x0A) e CR (0x0D) são preservados.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")

# Múltiplos espaços/tabs viram um espaço só (sem afetar newlines).
_INLINE_WHITESPACE_RE = re.compile(r"[ \t]+")

# 3+ newlines consecutivos viram parágrafo único (\n\n).
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def normalize(text: str) -> str:
    """Pipeline de normalização de texto.

    Etapas (na ordem):
        1. ftfy.fix_text — corrige mojibake (ex.: 'Ã©' → 'é').
        2. NFC — normaliza decomposições Unicode (combinadores → forma composta).
        3. Remove caracteres de controle (preservando tab/LF/CR).
        4. Colapsa múltiplos espaços/tabs em um espaço.
        5. Colapsa 3+ newlines em parágrafo (\\n\\n).
        6. Strip de whitespace nas bordas.
    """
    if not text:
        return ""
    text = ftfy.fix_text(text)
    text = unicodedata.normalize("NFC", text)
    text = _CONTROL_CHARS_RE.sub("", text)
    text = _INLINE_WHITESPACE_RE.sub(" ", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    return text.strip()
