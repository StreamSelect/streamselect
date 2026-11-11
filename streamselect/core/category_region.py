"""Fill a channel's empty prefix/region from its provider category.

Steps 2 and 2b of ``update_detected_prefixes``, kept beside — not inside —
:func:`~streamselect.core.tag_decomposer.region_code_from_category` so the
decomposer stays about turning labels into tags.
"""

from __future__ import annotations

from streamselect.core.category_headings import masks_country
from streamselect.core.region_codes import split_category_prefix
from streamselect.core.tag_decomposer import region_code_from_category


def category_region_fallback(
    prefix: str | None,
    region: str | None,
    category: str | None,
    *,
    config,
    headings: frozenset[str] = frozenset(),
) -> tuple[str | None, str | None]:
    """Fill an empty prefix/region from the provider category (fill-empty-only).

    Steps 2 and 2b of ``update_detected_prefixes``: the category's region via
    :func:`region_code_from_category`, then a bare ``"XX| REST"`` head via
    ``split_category_prefix`` — which also covers language-only codes (``AR``)
    and fills ``detected_prefix``, the field Exclusions check first. A
    continent heading (``"AM| CARIBBEAN"``) fills neither: it names no country.

    Args:
        prefix, region: The name-derived values, or None.
        category: ``ChannelDB.category``.
        config: Live ``Config``.
        headings: The source's category headings.

    Returns:
        ``(prefix, region)`` — a value already set is never overwritten.
    """
    if not category:
        return prefix, region
    if not region:
        region = region_code_from_category(category, config=config, headings=headings)
    if prefix is None or not region:
        code, _ = split_category_prefix(category)
        if code and not masks_country(category, headings):
            prefix = code if prefix is None else prefix
            region = region or code
    return prefix, region
