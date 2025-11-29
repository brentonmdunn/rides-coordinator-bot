"""Contains constants"""

from app.core.enums import CampusLivingLocations, DaysOfWeek, PickupLocations

GUILD_ID = 916817752918982716

LSCC_DAYS = [DaysOfWeek.FRIDAY, DaysOfWeek.SUNDAY]

LIVING_TO_PICKUP = {
    CampusLivingLocations.SIXTH: PickupLocations.SIXTH,
    CampusLivingLocations.SEVENTH: PickupLocations.SEVENTH,
    CampusLivingLocations.MARSHALL: PickupLocations.MARSHALL,
    CampusLivingLocations.ERC: PickupLocations.ERC,
    CampusLivingLocations.MUIR: PickupLocations.MUIR,
    CampusLivingLocations.EIGHTH: PickupLocations.EIGHTH,
    CampusLivingLocations.REVELLE: PickupLocations.EIGHTH,
    CampusLivingLocations.PCE: PickupLocations.INNOVATION,
    CampusLivingLocations.PCW: PickupLocations.INNOVATION,
    CampusLivingLocations.RITA: PickupLocations.RITA,
    CampusLivingLocations.WARREN: PickupLocations.WARREN_EQL,
}

MAP_LINKS = {
    PickupLocations.SIXTH: "https://maps.app.goo.gl/z8cffnYwLi1sgYcf8",
    PickupLocations.SEVENTH: "https://maps.app.goo.gl/1zKQiGKH6ecq1qzS8",
    PickupLocations.MARSHALL: "https://maps.app.goo.gl/1NT4Q65udUvuNX7aA",
    PickupLocations.ERC: "https://maps.app.goo.gl/dqgzKGS8DsUgLkw17",
    PickupLocations.MUIR: "https://maps.app.goo.gl/qxABq7sEEQsz6Pth9",
    PickupLocations.EIGHTH: "https://maps.app.goo.gl/RySbnmJGZ7zKujgq7",
    PickupLocations.INNOVATION: "https://maps.app.goo.gl/7tDt4mT5SkPkJbRh8",
    PickupLocations.RITA: "https://maps.app.goo.gl/qcuCR5q6Tx2EEn9c9",
    PickupLocations.WARREN_EQL: "https://maps.app.goo.gl/b4vLo5ZCGdZXEoni8",
    PickupLocations.WARREN_JST: "https://maps.app.goo.gl/h5LJCGhvBUbpmkmL7",
    PickupLocations.GEISEL_LOOP: "https://maps.app.goo.gl/nEtXGDLwGeAArNtPA",
}

SCHOLARS_LOCATIONS = [
    "revelle",
    "muir",
    "sixth",
    "marshall",
    "erc",
    "seventh",
    "new marshall",
    "eighth",
]

# Configuration for housing groups used in location breakdown embeds
HOUSING_GROUPS = {
    "Scholars": {"count": 0, "people": "", "filter": SCHOLARS_LOCATIONS, "emoji": "🏫"},
    "Warren + Pepper Canyon": {
        "count": 0,
        "people": "",
        "filter": [
            "warren",
            "pcyn",
            "pce",
            "pcw",
            "pepper canyon east",
            "pepper canyon west",
        ],
        "emoji": "🏠",
    },
    "Rita": {"count": 0, "people": "", "filter": ["rita"], "emoji": "🏡"},
    "Off Campus": {"count": 0, "people": "", "filter": [], "emoji": "🌍"},
}
