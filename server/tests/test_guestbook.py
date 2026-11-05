from flypaper.guestbook import Guestbook


def test_broken_lines_are_skipped(tmp_path):
    path = tmp_path / "guestbook.txt"
    path.write_text('{"name": "Аня", "text": "1"}\nне json\n\n{"name": "Борис", "text": "2"}\n', encoding="utf-8")
    assert [e["name"] for e in Guestbook(path).entries()] == ["Борис", "Аня"]


def test_text_with_newlines_stays_one_line_in_file(tmp_path):
    path = tmp_path / "guestbook.txt"
    book = Guestbook(path)
    book.add({"name": "Аня", "text": "первая строка\nвторая"})
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    assert book.entries()[0]["text"] == "первая строка\nвторая"


def test_missing_file_means_no_entries(tmp_path):
    assert Guestbook(tmp_path / "nope.txt").entries() == []
