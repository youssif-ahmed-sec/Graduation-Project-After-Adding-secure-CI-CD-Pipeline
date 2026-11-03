"""
ui/theme.py
Defines the enterprise color palette and typography constants.
"""

class Colors:
    PRIMARY_BG = ("#F6F8FA", "#0F141A")
    SECONDARY_BG = ("#F0F2F5", "#161B22")
    PANEL_BG = ("#FFFFFF", "#1E242C")
    BORDER = ("#D0D7DE", "#2B313A")

    ACCENT_BLUE = ("#0969DA", "#1F6FEB")
    HOVER_BLUE = ("#218BFF", "#388BFD")

    SUCCESS = ("#1F883D", "#22C55E")
    WARNING = ("#9A6700", "#F59E0B")
    CRITICAL = ("#CF222E", "#EF4444")

    TEXT_PRIMARY = ("#24292F", "#FFFFFF")
    TEXT_SECONDARY = ("#57606A", "#8B949E")

    ACCENT_PRESETS = {
        "Cyber Blue": {"primary": ("#0969DA", "#1F6FEB"), "hover": ("#218BFF", "#388BFD")},
        "Neon Green": {"primary": ("#1F883D", "#22C55E"), "hover": ("#26A641", "#4ADE80")},
        "Red Alert":  {"primary": ("#CF222E", "#EF4444"), "hover": ("#FF9999", "#F87171")}
    }

    @classmethod
    def set_accent(cls, preset_name):
        if preset_name in cls.ACCENT_PRESETS:
            cls.ACCENT_BLUE = cls.ACCENT_PRESETS[preset_name]["primary"]
            cls.HOVER_BLUE = cls.ACCENT_PRESETS[preset_name]["hover"]

class Fonts:
    H1 = ("Roboto", 24, "bold")
    H2 = ("Roboto", 20, "bold")
    H3 = ("Roboto", 16, "bold")
    BODY = ("Roboto", 13)
    MONO = ("JetBrains Mono", 12)
    META = ("Roboto", 11)

class Dims:
    SIDEBAR_WIDTH = 240
    TOPBAR_HEIGHT = 60
    CORNER_RADIUS = 6