"""
Hardcoded dummy data for portfolio demonstration.

All data is completely fictional with no real PII.
"""

# Dummy users with fictional names and Discord usernames
DUMMY_USERS = [
    ("Alice Johnson", "alice_tech"),
    ("Bob Smith", "bob_codes"),
    ("Carol Williams", "carol_data"),
    ("David Brown", "david_dev"),
    ("Emma Davis", "emma_design"),
    ("Frank Miller", "frank_mobile"),
    ("Grace Wilson", "grace_web"),
    ("Henry Moore", "henry_cloud"),
    ("Ivy Taylor", "ivy_backend"),
    ("Jack Anderson", "jack_frontend"),
    ("Kate Thomas", "kate_fullstack"),
    ("Liam Jackson", "liam_devops"),
]

# Pickup locations grouped by housing
FRIDAY_PICKUPS = {
    "housing_groups": {
        "North Campus": {
            "emoji": "🏛️",
            "count": 4,
            "locations": {
                "Maple Hall": [
                    {"name": "Alice Johnson", "discord_username": "alice_tech"},
                    {"name": "Bob Smith", "discord_username": "bob_codes"},
                ],
                "Oak Building": [
                    {"name": "Carol Williams", "discord_username": "carol_data"},
                    {"name": "David Brown", "discord_username": "david_dev"},
                ],
            },
        },
        "South Campus": {
            "emoji": "🏘️",
            "count": 3,
            "locations": {
                "Pine Apartments": [
                    {"name": "Emma Davis", "discord_username": "emma_design"},
                    {"name": "Frank Miller", "discord_username": "frank_mobile"},
                ],
                "Cedar Complex": [
                    {"name": "Grace Wilson", "discord_username": "grace_web"},
                ],
            },
        },
        "Off Campus": {
            "emoji": "🏠",
            "count": 3,
            "locations": {
                "Downtown Area": [
                    {"name": "Henry Moore", "discord_username": "henry_cloud"},
                ],
                "Westside District": [
                    {"name": "Ivy Taylor", "discord_username": "ivy_backend"},
                    {"name": "Jack Anderson", "discord_username": "jack_frontend"},
                ],
            },
        },
    },
    "unknown_users": [],
}

SUNDAY_PICKUPS = {
    "housing_groups": {
        "North Campus": {
            "emoji": "🏛️",
            "count": 5,
            "locations": {
                "Maple Hall": [
                    {"name": "Alice Johnson", "discord_username": "alice_tech"},
                    {"name": "Bob Smith", "discord_username": "bob_codes"},
                    {"name": "Kate Thomas", "discord_username": "kate_fullstack"},
                ],
                "Oak Building": [
                    {"name": "Carol Williams", "discord_username": "carol_data"},
                    {"name": "Liam Jackson", "discord_username": "liam_devops"},
                ],
            },
        },
        "South Campus": {
            "emoji": "🏘️",
            "count": 4,
            "locations": {
                "Pine Apartments": [
                    {"name": "Emma Davis", "discord_username": "emma_design"},
                    {"name": "Frank Miller", "discord_username": "frank_mobile"},
                ],
                "Cedar Complex": [
                    {"name": "Grace Wilson", "discord_username": "grace_web"},
                    {"name": "Henry Moore", "discord_username": "henry_cloud"},
                ],
            },
        },
    },
    "unknown_users": [],
}

# Ride coverage data - mix of covered and uncovered users
FRIDAY_COVERAGE = {
    "users": [
        {"discord_username": "alice_tech", "has_ride": False},
        {"discord_username": "bob_codes", "has_ride": False},
        {"discord_username": "carol_data", "has_ride": True},
        {"discord_username": "david_dev", "has_ride": True},
        {"discord_username": "emma_design", "has_ride": False},
        {"discord_username": "frank_mobile", "has_ride": True},
        {"discord_username": "grace_web", "has_ride": True},
        {"discord_username": "henry_cloud", "has_ride": False},
        {"discord_username": "ivy_backend", "has_ride": True},
        {"discord_username": "jack_frontend", "has_ride": True},
    ],
    "total": 10,
    "assigned": 6,
    "message_found": True,
    "has_coverage_entries": True,
}

SUNDAY_COVERAGE = {
    "users": [
        {"discord_username": "alice_tech", "has_ride": True},
        {"discord_username": "bob_codes", "has_ride": False},
        {"discord_username": "carol_data", "has_ride": False},
        {"discord_username": "emma_design", "has_ride": True},
        {"discord_username": "frank_mobile", "has_ride": True},
        {"discord_username": "grace_web", "has_ride": False},
        {"discord_username": "henry_cloud", "has_ride": True},
        {"discord_username": "kate_fullstack", "has_ride": True},
        {"discord_username": "liam_devops", "has_ride": True},
    ],
    "total": 9,
    "assigned": 6,
    "message_found": True,
    "has_coverage_entries": True,
}

# Driver reactions data
DRIVER_REACTIONS = {
    "friday": {
        "day": "friday",
        "reactions": {
            "✅": [
                {"name": "Alice Johnson", "username": "alice_tech"},
                {"name": "Carol Williams", "username": "carol_data"},
                {"name": "Emma Davis", "username": "emma_design"},
            ],
            "❌": [
                {"name": "Bob Smith", "username": "bob_codes"},
            ],
            "❓": [
                {"name": "David Brown", "username": "david_dev"},
                {"name": "Frank Miller", "username": "frank_mobile"},
            ],
        },
        "message_found": True,
    },
    "sunday": {
        "day": "sunday",
        "reactions": {
            "✅": [
                {"name": "Grace Wilson", "username": "grace_web"},
                {"name": "Henry Moore", "username": "henry_cloud"},
                {"name": "Kate Thomas", "username": "kate_fullstack"},
                {"name": "Liam Jackson", "username": "liam_devops"},
            ],
            "❌": [
                {"name": "Ivy Taylor", "username": "ivy_backend"},
            ],
            "❓": [],
        },
        "message_found": True,
    },
}

# Group rides data
GROUP_RIDES_FRIDAY = {
    "summary": "Generated 2 car groups for 10 riders",
    "groupings": [
        "🚗 Car 1 (Driver: Alice Johnson - 4 riders):\n"
        "  1. Alice Johnson (Maple Hall)\n"
        "  2. Bob Smith (Maple Hall)\n"
        "  3. Carol Williams (Oak Building)\n"
        "  4. David Brown (Oak Building)\n",
        "🚗 Car 2 (Driver: Emma Davis - 4 riders):\n"
        "  1. Emma Davis (Pine Apartments)\n"
        "  2. Frank Miller (Pine Apartments)\n"
        "  3. Grace Wilson (Cedar Complex)\n"
        "  4. Henry Moore (Downtown Area)\n",
    ],
}

GROUP_RIDES_SUNDAY = {
    "summary": "Generated 2 car groups for 9 riders",
    "groupings": [
        "🚗 Car 1 (Driver: Kate Thomas - 4 riders):\n"
        "  1. Kate Thomas (Maple Hall)\n"
        "  2. Alice Johnson (Maple Hall)\n"
        "  3. Bob Smith (Maple Hall)\n"
        "  4. Carol Williams (Oak Building)\n",
        "🚗 Car 2 (Driver: Grace Wilson - 4 riders):\n"
        "  1. Grace Wilson (Cedar Complex)\n"
        "  2. Emma Davis (Pine Apartments)\n"
        "  3. Frank Miller (Pine Apartments)\n"
        "  4. Henry Moore (Cedar Complex)\n",
    ],
}

# Feature flags
FEATURE_FLAGS = {
    "flags": [
        {"id": 1, "feature": "ask_rides_friday", "enabled": True},
        {"id": 2, "feature": "ask_rides_sunday", "enabled": True},
        {"id": 3, "feature": "ask_rides_sunday_class", "enabled": False},
        {"id": 4, "feature": "experimental_ai_grouping", "enabled": False},
    ]
}

# Ask rides status
ASK_RIDES_STATUS = {
    "friday": {
        "next_run": "2025-01-03T10:00:00",
        "last_run": "2024-12-27T10:00:00",
        "status": "scheduled",
        "enabled": True,
    },
    "sunday": {
        "next_run": "2025-01-05T08:00:00",
        "last_run": "2024-12-29T08:00:00",
        "status": "scheduled",
        "enabled": True,
    },
    "sunday_class": {
        "next_run": "2025-01-05T08:00:00",
        "last_run": None,
        "status": "disabled",
        "enabled": False,
    },
}
