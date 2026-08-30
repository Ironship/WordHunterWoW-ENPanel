"""Which game a fetch is for, and what that means for the API.

Every value here was confirmed against the live Blizzard Game Data API rather
than taken from documentation; CLASSIC_SOD_STAGE0_REPORT.md records the probes.
The two facts worth knowing before touching this file:

  * Classic has no quest endpoint at all. Not sparse fields like Retail's --
    /data/wow/quest/<id>, its indexes and search/quest are all 404 on the
    Classic namespace, for plain vanilla quest ids included. English quest text
    for Classic has to come from the addon's own harvest.

  * Season of Discovery has no namespace of its own. Its data sits in the
    Classic Era namespace, where one id has exactly one record, so an Era and a
    SoD item can never disagree. That is why "sod" is not a product you can
    fetch: there is nothing separate to fetch. The Classic artifact carries Era
    and SoD together.
"""

PRODUCTS = {
    "retail": {
        "namespace": "static-{region}",
        # Retail's cache files stay exactly where they have always been, so
        # nothing already downloaded has to move.
        "cache_prefix": "",
        "has_quests": True,
        # kind: (search path, id ceiling, starting window)
        "kinds": {
            "item":     ("/data/wow/search/item",     260000, 4000),
            "spell":    ("/data/wow/search/spell",    500000, 4000),
            "creature": ("/data/wow/search/creature", 260000, 8000),
        },
    },
    "classic": {
        # Classic Era, and Season of Discovery with it.
        "namespace": "static-classic1x-{region}",
        "cache_prefix": "classic/",
        "has_quests": False,
        "kinds": {
            # The highest item id answering in this namespace was 227385, well
            # above vanilla's ~24000 because SoD's items live here too.
            "item": ("/data/wow/search/item", 230000, 4000),
            # /data/wow/spell and /data/wow/creature are 404 on Classic.
        },
    },
}


def namespace(product, region):
    return PRODUCTS[product]["namespace"].format(region=region)


def cache_path(cache_root, product, filename):
    """Where a product's cache file lives. Retail keeps the old flat layout."""
    prefix = PRODUCTS[product]["cache_prefix"]
    path = cache_root / prefix / filename if prefix else cache_root / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
