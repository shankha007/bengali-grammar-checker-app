"""256-word ASCII list for recovery phrases.

ASCII on purpose: the phrase has to survive being typed on a Bengali keyboard,
read aloud over a phone, and pasted into a Latin-only form field. 256 words means
one word per byte, which keeps encode/decode trivially auditable.

The list is append-only-forbidden: changing any entry invalidates every recovery
phrase ever issued. `RECOVERY_WORDLIST_VERSION` is stored with each device row so
a future list can coexist with this one.
"""

from __future__ import annotations

RECOVERY_WORDLIST_VERSION = 1

WORDS: tuple[str, ...] = (
    "able", "acid", "acre", "also", "amber", "amid", "ankle", "apple",
    "apron", "arch", "arena", "arm", "armor", "army", "arrow", "art",
    "ash", "atlas", "atom", "aunt", "auto", "axis", "bacon", "badge",
    "bag", "baker", "balm", "bamboo", "band", "bank", "bar", "barn",
    "basil", "basin", "bath", "bay", "beach", "bean", "bear", "beat",
    "bell", "belt", "bench", "berry", "best", "bike", "bird", "black",
    "blade", "blend", "bliss", "block", "bloom", "blue", "board", "boat",
    "bold", "bolt", "bone", "bonus", "book", "boot", "borax", "boss",
    "bowl", "box", "brain", "branch", "brass", "brave", "bread", "brick",
    "bridge", "brief", "bright", "bronze", "brook", "broom", "brown", "brush",
    "bubble", "bucket", "bud", "buffalo", "bulb", "bull", "bunch", "bundle",
    "bunny", "burst", "bush", "cabin", "cable", "cactus", "cage", "cake",
    "calm", "camel", "camp", "canal", "candle", "cane", "canoe", "canvas",
    "canyon", "cape", "card", "cargo", "carpet", "carrot", "cart", "carve",
    "case", "cash", "cast", "castle", "cat", "cave", "cedar", "cell",
    "chain", "chair", "chalk", "charm", "chart", "cheese", "cherry", "chess",
    "chest", "chief", "chill", "chime", "chip", "choir", "chord", "cider",
    "circle", "city", "civic", "claim", "clam", "clay", "clean", "clerk",
    "cliff", "climb", "clock", "cloth", "cloud", "clover", "coach", "coal",
    "coast", "coat", "cobalt", "cocoa", "coin", "cold", "collar", "colony",
    "color", "comb", "comet", "coral", "cork", "corn", "cotton", "couch",
    "court", "cover", "cow", "crab", "crane", "crate", "cream", "creek",
    "crest", "crew", "crisp", "crop", "cross", "crown", "cube", "cup",
    "curl", "curve", "cycle", "daisy", "dance", "dawn", "deck", "deer",
    "delta", "dense", "desk", "dew", "diary", "dice", "diet", "dime",
    "diner", "dish", "dive", "dock", "dodge", "dog", "dome", "donut",
    "door", "dove", "draft", "drama", "dream", "dress", "drift", "drum",
    "dry", "duck", "dune", "dusk", "dust", "eagle", "earth", "east",
    "echo", "edge", "eel", "egg", "elbow", "elder", "elm", "ember",
    "engine", "envoy", "epoch", "equal", "era", "ermine", "essay", "ether",
    "exit", "fable", "fabric", "falcon", "fan", "farm", "fawn", "feast",
    "fence", "fern", "ferry", "fiber", "field", "fig", "film", "filter",
)

if len(WORDS) != 256 or len(set(WORDS)) != 256:  # pragma: no cover - import guard
    raise RuntimeError(
        f"recovery wordlist must be 256 unique words, got {len(WORDS)} "
        f"({len(set(WORDS))} unique)"
    )

INDEX: dict[str, int] = {w: i for i, w in enumerate(WORDS)}
