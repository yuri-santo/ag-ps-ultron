"""Scoped migration: include the existing integral transcript in report email."""
import ast


def transform(source):
    old = '[pdf_path] + [x for x in'
    new = '[pdf_path, transcript_path] + [x for x in'
    if new in source:
        return source
    if source.count(old) != 1:
        raise ValueError('Unknown report mail attachment layout')
    source = source.replace(old, new, 1)
    source = source.replace('e relatório executivo em anexo.',
                            'e relatório executivo, com transcrição integral TXT em anexo.', 1)
    ast.parse(source)
    return source
