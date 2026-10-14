"""Compact, deterministic references from the already-authorized Wiki response.

No model call, second index, stored summary or credentials. Work text is reference
data, not instructions. Relationships use visible IDs, never similar titles.
"""
import unicodedata


def normalized(text):
    return unicodedata.normalize("NFKC", str(text or "")).casefold()


def catalog(view):
    works = {}
    for group, kind in (("drafts", "draft"), ("tracks", "track"), ("albums", "album"), ("images", "image")):
        for row in view.get(group, []):
            if row.get("status") == "deleted" or (kind == "image" and row.get("available") is False):
                continue
            works[(kind, row["id"])] = row
    links = {key: set() for key in works}

    def connect(left, right):
        if left != right and left in works and right in works:
            links[left].add(right)
            links[right].add(left)

    for key, row in works.items():
        kind, _ = key
        if kind in ("track", "album"):
            connect(key, ("image", row.get("jacket_id")))
        if kind == "album":
            for song in row.get("tracks", []):
                draft, track = ("draft", song.get("draft_id")), ("track", song.get("track_id"))
                connect(key, draft)
                connect(key, track)
                connect(draft, track)
        if kind == "draft":
            connect(key, ("album", row.get("album_id")))
            generation = row.get("generation") or {}
            connect(key, ("image", generation.get("portrait_id")))
            # Review references describe a duplication check, not creative influence.
    return works, links


def summary(key, works, links, query="", include_lyrics=False):
    row = works[key]
    kind, identity = key
    text = str(row.get("lyrics") or "")
    flat = " ".join(text.split())
    position = normalized(flat).find(normalized(query)) if query else 0
    start = max(0, position - 60)
    related = sorted(links[key])
    result = {"kind": kind, "id": identity, "title": str(row.get("title") or "")[:200],
              "related": [{"kind": k, "id": i, "title": str(works[(k, i)].get("title") or "")[:200]} for k, i in related[:12]],
              "related_count": len(related), "related_has_more": len(related) > 12}
    for field in ("created_at", "status", "current"):
        if row.get(field) is not None:
            result[field] = row[field]
    if kind == "draft":
        genre = row.get("genre")
        if genre:
            result["genre"] = {k: str(genre[k])[:120] for k in ("id", "name") if k in genre} if isinstance(genre, dict) else str(genre)[:120]
        result.update(lyrics_excerpt=flat[start:start + 240], excerpt_truncated=start > 0 or len(flat) > start + 240)
        if include_lyrics:
            result["lyrics"] = text
    if kind == "image":
        result["image_kind"] = row.get("kind")
    return result


def search(view, query="", limit=6):
    works, links = catalog(view)
    terms = normalized(query).split()
    def score(key):
        row = works[key]
        title = normalized(row.get("title"))
        body = title + " " + normalized(row.get("lyrics"))
        if terms and not all(term in body for term in terms):
            return None
        return (sum(term in title for term in terms), str(row.get("created_at") or ""), key)
    ranked = [(rank, key) for key in works if (rank := score(key)) is not None]
    ranked.sort(reverse=True)
    return {"artist_id": view["artist_id"], "name": view.get("name"), "query": query,
            "total": len(works), "matched": len(ranked), "has_more": len(ranked) > limit,
            "works": [summary(key, works, links, query) for _, key in ranked[:limit]]}


def detail(view, kind, work_id, include_lyrics=False):
    works, links = catalog(view)
    key = kind, work_id
    if key not in works:
        raise KeyError(key)
    return {"artist_id": view["artist_id"], "name": view.get("name"),
            "work": summary(key, works, links, include_lyrics=include_lyrics)}
