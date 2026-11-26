from difflib import SequenceMatcher
import re
from .models import User

_STOPWORDS = {'and', 'for', 'the', 'with', 'basics', 'fundamentals', 'intro', 'introduction', 'programming', 'language', 'development', 'dev', 'design', 'skills'}
_ALIASES = {
    'js': 'javascript',
    'ts': 'typescript',
    'py': 'python',
    'ui': 'ui ux design',
    'ux': 'ui ux design',
    'ui/ux': 'ui ux design',
    'ml': 'machine learning',
    'ai': 'artificial intelligence',
    'ds': 'data science',
    'web dev': 'web development',
    'frontend': 'web development',
    'backend': 'web development',
}


def _norm_tokens(name):
    cleaned = re.sub(r'[^a-z0-9]+', ' ', name.lower()).strip()
    if cleaned in _ALIASES:
        cleaned = _ALIASES[cleaned]
    tokens = [t for t in cleaned.split() if t and t not in _STOPWORDS]
    return cleaned, set(tokens or cleaned.split())


def skill_relevance(skill_a, skill_b):
    """Return relevance weight in (0.0, 1.0] if two skills are identical or relevant, else 0.0."""
    if skill_a.id == skill_b.id:
        return 1.0

    norm_a, tok_a = _norm_tokens(skill_a.name)
    norm_b, tok_b = _norm_tokens(skill_b.name)
    if norm_a == norm_b:
        return 0.95

    if tok_a & tok_b:
        return 0.9

    if SequenceMatcher(None, norm_a, norm_b).ratio() >= 0.82:
        return 0.8

    if skill_a.category_id and skill_b.category_id and skill_a.category_id == skill_b.category_id:
        return 0.65

    return 0.0


def _best_relevant_links(teach_links, learn_links):
    """Find (teach_link, learn_link, relevance) pairs sorted by highest relevance."""
    matches = []
    for t in teach_links:
        for l in learn_links:
            rel = skill_relevance(t.skill, l.skill)
            if rel > 0:
                matches.append((t, l, rel))
    return matches


def _pair_with_relevance(a, b):
    a_teaches = [link for link in a.skills if link.direction == 'teach']
    a_learns = [link for link in a.skills if link.direction == 'learn']
    b_teaches = [link for link in b.skills if link.direction == 'teach']
    b_learns = [link for link in b.skills if link.direction == 'learn']

    a_to_b = _best_relevant_links(a_teaches, b_learns)
    b_to_a = _best_relevant_links(b_teaches, a_learns)
    if not a_to_b or not b_to_a:
        return None

    best = max(
        ((mine, rel1, theirs, rel2) for mine, _, rel1 in a_to_b for theirs, _, rel2 in b_to_a),
        key=lambda item: (
            round((item[1] + item[3]) / 2, 4),
            item[0].proficiency + item[2].proficiency,
            -item[0].skill_id,
            -item[2].skill_id,
        ),
    )
    return best[0], best[2], (best[1] + best[3]) / 2


def mutual_skill_pair(a, b):
    """Return (a's teach link, b's teach link) when both students teach a skill relevant to what the other wants."""
    result = _pair_with_relevance(a, b)
    return (result[0], result[1]) if result else None


def score_pair(a, b):
    result = _pair_with_relevance(a, b)
    if not result:
        return None

    mine, theirs, avg_rel = result
    coverage_score = 60 * avg_rel
    proficiency_score = ((mine.proficiency + theirs.proficiency) / 10) * 25
    slots_a = {(slot.weekday, slot.start_hour) for slot in a.availability}
    slots_b = {(slot.weekday, slot.start_hour) for slot in b.availability}
    availability_score = min(1, len(slots_a & slots_b) / 3) * 15 if slots_a and slots_b else 0
    return round(coverage_score + proficiency_score + availability_score)


def recommendations(user, limit=30):
    candidates = User.query.filter(User.id != user.id, User.is_active_account.is_(True)).all()
    result = []
    for candidate in candidates:
        pair = mutual_skill_pair(user, candidate)
        if not pair:
            continue
        score = score_pair(user, candidate)
        if score is not None:
            result.append((candidate, score, pair[0], pair[1]))
    return sorted(result, key=lambda row: (-row[1], row[0].name.lower()))[:limit]


def relevant_matches(user, limit=30):
    """Return one-way relevant skill matches not already covered by two-way recommendations."""
    mutual_ids = {cand.id for cand, _, _, _ in recommendations(user, limit=200)}
    candidates = User.query.filter(User.id != user.id, User.is_active_account.is_(True)).all()
    my_teaches = [link for link in user.skills if link.direction == 'teach']
    my_learns = [link for link in user.skills if link.direction == 'learn']

    result = []
    for candidate in candidates:
        if candidate.id in mutual_ids:
            continue
        their_teaches = [link for link in candidate.skills if link.direction == 'teach']
        their_learns = [link for link in candidate.skills if link.direction == 'learn']
        learn_hits = _best_relevant_links(their_teaches, my_learns)
        teach_hits = _best_relevant_links(my_teaches, their_learns)
        hits = []
        for t, l, rel in learn_hits:
            hits.append(('learn', t, l, rel))
        for t, l, rel in teach_hits:
            hits.append(('teach', t, l, rel))
        if not hits:
            continue
        kind, src_link, dst_link, rel = max(hits, key=lambda h: (h[3], h[1].proficiency, -h[1].skill_id))
        slots_a = {(slot.weekday, slot.start_hour) for slot in user.availability}
        slots_b = {(slot.weekday, slot.start_hour) for slot in candidate.availability}
        avail_bonus = min(1, len(slots_a & slots_b) / 3) * 10 if slots_a and slots_b else 0
        score = round(45 * rel + (src_link.proficiency / 5) * 15 + avail_bonus)
        result.append((candidate, score, kind, src_link, dst_link))

    return sorted(result, key=lambda row: (-row[1], row[0].name.lower()))[:limit]
