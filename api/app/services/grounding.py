"""What the service guarantees in code, whatever the model wrote (section 3.4)."""

from __future__ import annotations

from ..schemas import Answer, Citation, Passage

ABSTENTION = Answer(
    reasoning="Nothing retrieved cleared the relevance floor.",
    answer="The documents I have do not cover this question, so I can't answer it.",
    citations=[],
    answered_from_context=False,
    confidence="low",
)
FALLBACK = Answer(
    reasoning="The model did not produce a valid answer after one retry.",
    answer="I couldn't produce a reliable answer just now. Please try again in a moment.",
    citations=[],
    answered_from_context=False,
    confidence="low",
)
UNSUPPORTED = Answer(
    reasoning="The model answered without a citation that matches a retrieved passage.",
    answer="I couldn't support an answer to this with the documents I have.",
    citations=[],
    answered_from_context=False,
    confidence="low",
)


def enforce_citations(answer: Answer, passages: list[Passage]) -> Answer:
    """Keep only citations of retrieved passages. An answer left with none is not grounded."""
    if not answer.answered_from_context:
        return answer.model_copy(update={"citations": []})
    pages = {(p.source, p.section): p.page for p in passages}
    exact = {(p.source, p.section, p.page) for p in passages}
    kept: list[Citation] = []
    for citation in answer.citations:
        key = (citation.source, citation.section)
        if key not in pages:
            continue  # fabricated: this source and section were not retrieved
        if (citation.source, citation.section, citation.page) not in exact:
            citation = Citation(source=citation.source, section=citation.section, page=pages[key])
        if citation not in kept:
            kept.append(citation)
    if not kept:
        return UNSUPPORTED
    return answer.model_copy(update={"citations": kept})
