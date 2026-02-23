"""Configuration dataclasses and constants."""

from dataclasses import dataclass, field
from pathlib import Path

# === Direction constants ===
DIRECTION_AUTO = "auto"
DIRECTION_VERTICAL = "vertical"
DIRECTION_HORIZONTAL = "horizontal"
VALID_DIRECTIONS = (DIRECTION_AUTO, DIRECTION_VERTICAL, DIRECTION_HORIZONTAL)

# === Region constants ===
REGION_LEFT = "left"
REGION_RIGHT = "right"
REGION_FULL = "full"
VALID_REGIONS = (REGION_LEFT, REGION_RIGHT, REGION_FULL)


@dataclass
class OcrConfig:
    """OCR settings"""

    languages: list[str] = field(default_factory=lambda: ["ja", "en"])
    vertical_mode: bool = False


@dataclass
class PdfConfig:
    """PDF optimization settings"""

    garbage: int = 4
    deflate: bool = True
    clean: bool = True


@dataclass
class MarginConfig:
    """Margin settings (ratio to screen size)"""

    top: float = 0.1
    bottom: float = 0.05
    left: float = 0.05
    right: float = 0
    half_position: float = 0.5

    def __post_init__(self) -> None:
        for name in ("top", "bottom", "left", "right", "half_position"):
            value = getattr(self, name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} must be between 0.0 and 1.0, got {value}")


@dataclass
class AppConfig:
    """Application settings"""

    max_pages: int = 1000
    page_turn_delay: float = 0.6
    kindle_activation_delay: float = 2.0
    screenshot_dir: Path = field(default_factory=lambda: Path("screenshots"))
    output_dir: Path = field(default_factory=lambda: Path("output"))
    margin: MarginConfig = field(default_factory=MarginConfig)
    pdf: PdfConfig = field(default_factory=PdfConfig)
    ocr: OcrConfig = field(default_factory=OcrConfig)


def get_page_turn_key(vertical_mode: bool) -> str:
    """Return page turn key based on text direction."""
    return "left" if vertical_mode else "right"


def prompt_vertical_mode(confidence: float) -> bool:
    """Ask user whether to use vertical text mode."""
    confidence_pct = int(confidence * 100)

    print(f"\n縦書きとして検出されました（信頼度: {confidence_pct}%）")
    print("縦書きモードに切り替えますか？")
    print("  [y] 縦書き（←キーでページ送り）")
    print("  [n] 横書きのまま（→キーでページ送り）")
    print("  [Enter] 縦書きに切り替え")

    while True:
        try:
            user_input = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return True

        if user_input == "":
            return True
        elif user_input in ("y", "yes"):
            return True
        elif user_input in ("n", "no"):
            return False
        else:
            print("y または n を入力してください")
