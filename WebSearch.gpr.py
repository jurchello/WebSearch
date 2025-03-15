register(
    GRAMPLET,
    id="WebSearch",
    name=_("Web Search Gramplet"),
    description=_("Lists useful genealogy-related websites for research."),
    status=STABLE,
    version="0.8.3",
    fname="WebSearch.py",
    height=20,
    detached_width=400,
    detached_height=300,
    expand=True,
    gramplet="WebSearch",
    gramplet_title=_("Web Search"),
    gramps_target_version="5.2",
    navtypes=["Person", "Place", "Source"],
    include_in_listing=True,
)