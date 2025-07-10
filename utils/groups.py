import os

GROUP_SHORTCUTS = {
    "SUCCUBUS_SANCTUARY": int(os.getenv("SUCCUBUS_SANCTUARY", "0")),
    "MODELS_CHAT": int(os.getenv("MODELS_CHAT", "0")),
    "TEST_GROUP": int(os.getenv("TEST_GROUP", "0")),
}

