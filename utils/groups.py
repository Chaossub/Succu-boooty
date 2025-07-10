# utils/groups.py

import os

GROUP_SHORTCUTS = {
    "SUCCUBUS_SANCTUARY": int(os.environ.get("SUCCUBUS_SANCTUARY", "0")),
    "MODELS_CHAT": int(os.environ.get("MODELS_CHAT", "0")),
    "TEST_GROUP": int(os.environ.get("TEST_GROUP", "0")),
}
