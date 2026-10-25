"""Extract the DRIVER'S CLAIM, not verified video observations.

Arabic/English keyword extraction is intentionally conservative. An utterance
does not constitute proof of a traffic offense or a verified vehicle identity.
"""
import re

INCIDENT_WORDS = {
    "shoulder_driving": [
        "shoulder", "emergency lane", "كتف", "حارة الطوارئ", "جانب الطريق"
    ],
    "red_light": [
        "red light", "ran a red", "traffic light", "إشارة حمراء",
        "الاشارة الحمراء", "الإشارة الحمراء", "قطع الاشارة", "قطع الإشارة"
    ],
    "littering": ["litter", "trash", "garbage", "رمي", "زبالة", "مخلفات", "نفايات"],
    "missing_plate": [
        "no plate", "missing plate", "without plate", "بدون لوحات",
        "بدون لوحة", "من غير نمر", "بلا لوحة", "مفيش نمر"
    ],
}
COLORS = {
    "blue": ["blue", "أزرق", "ازرق", "زرقاء", "زرقة"],
    "white": ["white", "أبيض", "ابيض", "بيضاء"],
    "red": ["red car", "red kia", "red vehicle", "أحمر", "احمر", "حمراء"],
    "black": ["black", "أسود", "اسود", "سوداء"],
    "silver": ["silver", "فضي", "فضية"],
    "gray": ["grey", "gray", "رمادي", "رصاصي"],
    "yellow": ["yellow", "أصفر", "اصفر"],
    "green": ["green", "أخضر", "اخضر"],
}
MAKES = {
    "kia": ["kia", "كيا"],
    "hyundai": ["hyundai", "هيونداي"],
    "toyota": ["toyota", "تويوتا"],
    "chevrolet": ["chevrolet", "شيفروليه", "شيفرولية"],
    "nissan": ["nissan", "نيسان"],
    "honda": ["honda", "هوندا"],
    "bmw": ["bmw", "بي ام دبليو"],
    "mercedes": ["mercedes", "مرسيدس"],
    "renault": ["renault", "رينو"],
}
SIDE = {
    "left": ["left", "الشمال", "اليسار", "الناحية الشمال"],
    "right": ["right", "اليمين", "الناحية اليمين"],
}


def contains(text, phrase):
    prefix = r"(?:ال)?" if phrase and "\u0600" <= phrase[0] <= "\u06ff" else ""
    return bool(re.search(r"(?<!\w)" + prefix + re.escape(phrase) + r"(?!\w)", text, flags=re.UNICODE))


def find_value(text, options):
    return next((key for key, terms in options.items()
                 if any(contains(text, term) for term in terms)), None)


def parse_driver_claim(transcript: str | None) -> dict:
    text = (transcript or "").strip()[:500]
    lowered = text.casefold()
    categories = [key for key, terms in INCIDENT_WORDS.items()
                  if any(contains(lowered, word) for word in terms)]
    return {
        "status": "parsed" if text else "unavailable",
        "source": "driver_audio_only",
        "verbatim": text or None,
        "reported_categories": categories,
        "color": find_value(lowered, COLORS),
        "make": find_value(lowered, MAKES),
        "relative_side": find_value(lowered, SIDE),
        "verified_from_video": False,
        "note": "This is the driver's statement, not a confirmed visual finding.",
    }
