from helpers.i18n import SUPPORTED_LANGS, normalize_lang, t


def test_supported_langs() -> None:
    assert SUPPORTED_LANGS == ("ar", "en", "fr")


def test_normalize_lang_valid() -> None:
    assert normalize_lang("ar") == "ar"
    assert normalize_lang("en") == "en"
    assert normalize_lang("fr") == "fr"


def test_normalize_lang_falls_back_to_french() -> None:
    assert normalize_lang("de") == "fr"
    assert normalize_lang(None) == "fr"
    assert normalize_lang("") == "fr"


def test_t_default_french() -> None:
    assert t("Organisation") == "Organisation"


def test_t_english() -> None:
    assert t("Organisation", "en") == "Organization"
    assert t("Licence", "en") == "License"


def test_t_arabic() -> None:
    assert t("Organisation", "ar") == "المنظمة"
    assert t("Licence", "ar") == "الترخيص"
    assert t("Oui", "ar") == "نعم"


def test_t_unknown_language_falls_back() -> None:
    assert t("Organisation", "de") == "Organisation"


def test_t_unknown_label_returns_label() -> None:
    assert t("Label inconnu") == "Label inconnu"
