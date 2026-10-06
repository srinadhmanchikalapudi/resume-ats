"""Word lists the resume health rules rely on. Plain data, easy to extend."""

from __future__ import annotations

# Base forms of verbs that open strong resume bullets. Inflections are generated (see verb_forms).
STRONG_VERB_BASES = """
accelerate achieve administer advance analyze architect author automate boost build champion collaborate
complete configure consolidate convert coordinate create customize debug decrease define deliver deploy design
develop direct diagnose drive eliminate engineer enhance establish evaluate exceed execute expand expedite
extend facilitate finalize generate guide identify implement improve increase initiate institute integrate
introduce investigate launch lead maintain manage mentor migrate modernize monitor negotiate optimize
orchestrate organize overhaul partner pioneer plan produce program promote provision publish reduce refactor
rebuild redesign refine release remediate replace resolve restructure retire review revamp scale secure ship
simplify solve spearhead standardize streamline strengthen supervise test train transform troubleshoot
upgrade validate write architect audit benchmark bootstrap centralize cut diversify document enable enforce
engage escalate forecast formalize harden inspect instrument interview iterate measure merge model
onboard operationalize parallelize patch prototype prioritize profile recommend reconcile reengineer
reorganize repair report research rewrite roll sequence stabilize stream synchronize tune unify update
""".split()

# Verbs whose past tense (or base) is irregular, mapped to every accepted form.
IRREGULAR_VERBS: dict[str, tuple[str, ...]] = {
    "build": ("build", "builds", "built", "building"),
    "lead": ("lead", "leads", "led", "leading"),
    "drive": ("drive", "drives", "drove", "driven", "driving"),
    "run": ("run", "runs", "ran", "running"),
    "write": ("write", "writes", "wrote", "written", "writing"),
    "make": ("make", "makes", "made", "making"),
    "grow": ("grow", "grows", "grew", "grown"),
    "cut": ("cut", "cuts", "cutting"),
    "set": ("set", "sets", "setting"),
    "shape": ("shape", "shapes", "shaped"),
    "win": ("win", "wins", "won"),
    "roll": ("roll", "rolls", "rolled"),
    "ship": ("ship", "ships", "shipped", "shipping"),
    "teach": ("teach", "teaches", "taught"),
    "choose": ("choose", "chooses", "chose"),
    "begin": ("begin", "begins", "began"),
    "spend": ("spend", "spends", "spent"),
    "bring": ("bring", "brings", "brought"),
}

# Common irregular past-tense verbs that are fine to open a bullet but do not end in "ed".
IRREGULAR_PAST = set(
    "took held kept found gave brought taught put saw sold became thought understood won spent sent met paid "
    "read hired got made began chose rose caught fixed built led ran wrote drove grew".split()
)

# A line like "Environment: C#, .NET, SQL" lists technologies; it is not an accomplishment to score.
TECH_LIST_PREFIXES = ("environment", "tech stack", "technologies", "technology", "tools", "stack")

# Opening phrases that make a bullet describe a duty instead of an accomplishment.
WEAK_OPENERS: tuple[tuple[str, str], ...] = (
    ("responsible for", "Describes a duty, not what you achieved."),
    ("duties included", "Describes a duty, not what you achieved."),
    ("duties include", "Describes a duty, not what you achieved."),
    ("in charge of", "Describes a duty, not what you achieved."),
    ("tasked with", "Describes a duty, not what you achieved."),
    ("worked on", "Vague about your part in it."),
    ("worked with", "Vague about your part in it."),
    ("helped", "Understates your contribution."),
    ("assisted", "Understates your contribution."),
    ("participated in", "Understates your contribution."),
    ("involved in", "Understates your contribution."),
    ("took part in", "Understates your contribution."),
    ("contributed to", "Vague about what you actually did."),
    ("handled", "Vague about what you actually did."),
    ("was ", "Passive. Lead with what you did."),
    ("were ", "Passive. Lead with what you did."),
    ("used ", "Names a tool but not what you did with it."),
)  # fmt: skip

# Filler that adds words without adding information.
FLUFF_PHRASES: tuple[str, ...] = (
    "various", "numerous", "a variety of", "a number of", "etc", "and so on", "and more", "successfully",
    "in order to", "on a daily basis", "helped to", "team player", "hard-working", "hardworking",
    "detail-oriented", "detail oriented", "results-driven", "results driven", "self-motivated", "go-getter",
    "passionate", "dynamic", "synergy", "think outside the box", "proven track record",
    "excellent communication skills", "fast-paced environment", "world-class", "highly motivated",
)  # fmt: skip

# Words that read as boilerplate or machine-written when they pile up.
GENERIC_BUZZWORDS: tuple[str, ...] = (
    "leverage", "leveraged", "leveraging", "utilize", "utilized", "utilizing", "spearhead", "spearheaded",
    "orchestrate", "orchestrated", "seamless", "seamlessly", "robust", "cutting-edge", "innovative", "holistic",
    "delve", "tapestry", "foster", "fostered", "elevate", "elevated", "empower", "empowered", "paradigm",
    "pivotal", "game-changer", "game-changing", "transformative", "state-of-the-art", "meticulous",
    "meticulously", "synergize", "ever-evolving", "dynamic environment",
)  # fmt: skip

# What a number is counting, so "12 services" is a metric but ".NET 6" is not.
METRIC_UNITS = (
    "users customers clients requests transactions records rows services systems applications apps endpoints apis "
    "microservices teams engineers developers people members employees projects releases deployments environments "
    "tests pipelines tickets incidents bugs defects hours minutes seconds ms days weeks months years tb gb mb kb "
    "million billion thousand bps rps qps percent sprints stakeholders regions countries markets modules "
    "integrations queues jobs reports dashboards workflows tenants accounts claims orders payments"
).split()

# A number that follows one of these is a version, not a quantity (".NET 6", "Angular 12", "C# 10").
VERSION_WORDS = {
    ".net", "c#", "core", "framework", "angular", "angularjs", "react", "python", "java", "node", "server",
    "v", "version", "ef", "es", "html", "css", "bootstrap", "studio", "iis", "xunit", "nunit", "windows",
    "ubuntu", "ios", "android", "mvc", "api", "net", "jquery", "vue", "php", "ruby", "go", "swift",
    # Standards and labels followed by an identifier, not a quantity ("ISO 27001 controls", "Tier 2 support").
    "iso", "soc", "pci", "section", "rfc", "tls", "ssl", "http", "oauth", "level", "phase", "tier", "step",
    "gdpr", "hipaa", "sox", "nist", "iec", "ieee", "fips", "cmmi", "itil", "sprint", "story", "ticket", "page",
}  # fmt: skip

NUMBER_WORDS = (
    "two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
    "eighteen nineteen twenty thirty forty fifty dozen dozens hundred hundreds thousand thousands million "
    "millions billion"
).split()

# Prompts that help the user add a real number, keyed by the verb a bullet opens with (base form).
METRIC_HINTS: dict[str, str] = {
    "build": "How many users, requests or teams does it serve?",
    "create": "How many users, requests or teams does it serve?",
    "develop": "How many users, requests or teams does it serve?",
    "design": "How many users, requests or teams does it serve?",
    "implement": "How many users, requests or services did it cover?",
    "optimize": "By how much (time, cost, load or errors)?",
    "improve": "By how much (time, cost, load or errors)?",
    "reduce": "By how much, and from what to what?",
    "increase": "By how much, and from what to what?",
    "enhance": "What measurably got better, and by how much?",
    "migrate": "How many services, users or records moved?",
    "modernize": "How many services or users moved, and what improved?",
    "refactor": "How much code or how many services, and what improved?",
    "lead": "How many people or projects?",
    "manage": "How many people, projects or dollars?",
    "mentor": "How many people did you mentor?",
    "test": "What coverage, or how many defects did it prevent?",
    "automate": "How many hours or steps did it save, and how often?",
    "maintain": "How many systems, users or deployments?",
    "monitor": "What did you track, and how many systems?",
    "secure": "How many systems or users, or what risk was removed?",
    "extend": "What did it enable, and for how many users or systems?",
    "integrate": "How many systems or partners?",
    "deploy": "How many environments or how often?",
    "introduce": "What measurably improved, and by how much?",
    "strengthen": "What measurably improved, and by how much?",
}
GENERIC_METRIC_HINT = "Add a number: how many, how often, how much or how long?"

STOPWORDS = set(
    "a an and are as at be by for from has have in into is it its of on or that the their this to was were "
    "with using used use via per across within over under between through during while which who whom".split()
)  # fmt: skip

FIRST_PERSON = ("i", "my", "me", "we", "our", "myself")


def verb_forms(base: str) -> set[str]:
    """Every accepted form of a regular verb: base, -s, -ed, -ing, with doubled consonants and y to ied."""
    forms = {base, base + "s", base + "ed", base + "d", base + "ing"}
    if base.endswith("e"):
        forms.add(base[:-1] + "ing")
    if base.endswith("y") and len(base) > 2:
        forms |= {base[:-1] + "ied", base[:-1] + "ies"}
    if len(base) > 2 and base[-1] not in "aeiouwxy" and base[-2] in "aeiou":
        forms |= {base + base[-1] + "ed", base + base[-1] + "ing"}
    return forms


def build_strong_forms() -> dict[str, str]:
    """Maps every accepted verb form to its base form."""
    mapping: dict[str, str] = {}
    for base in STRONG_VERB_BASES:
        if base in IRREGULAR_VERBS:
            continue
        for form in verb_forms(base):
            mapping.setdefault(form, base)
    for base, forms in IRREGULAR_VERBS.items():
        for form in forms:
            mapping[form] = base
    return mapping


STRONG_FORMS = build_strong_forms()
