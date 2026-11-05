from unittest.mock import patch

from flypaper.registration import REGISTRATION_PARSER, registration_country


def test_registration_is_parsed_by_flydenity():
    assert registration_country("RA-73182") == ("Russia", "RU")
    assert registration_country("tc-lsa ") == ("Turkey", "TR")


def test_empty_registration():
    assert registration_country("") == ("", "")


def test_parser_errors_are_not_raised():
    with patch.object(REGISTRATION_PARSER, "parse", side_effect=ValueError("bad registration")):
        assert registration_country("RA-73182") == ("", "")


def test_unrecognized_registration():
    with patch.object(REGISTRATION_PARSER, "parse", return_value=None):
        assert registration_country("XX-0000") == ("", "")
