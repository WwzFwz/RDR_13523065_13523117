from rdr import Condition, difference_list

C = Condition
CASE = {"umur": 60.0, "gaji": 20.0, "risiko": "tinggi", "status": "pensiun"}
CORNER = {"umur": 30.0, "gaji": 20.0, "risiko": "tinggi", "status": "pekerja"}


def test_root_without_cornerstone_allows_all(domain):
    diff = difference_list(CASE, None, domain)
    assert diff == [
        C("umur", ">=", 60.0), C("umur", "<=", 60.0),
        C("gaji", ">=", 20.0), C("gaji", "<=", 20.0),
        C("risiko", "==", "tinggi"), C("status", "==", "pensiun"),
    ]


def test_against_cornerstone(domain):
    diff = difference_list(CASE, CORNER, domain)
    # gaji & risiko sama dengan cornerstone -> tidak ada kandidat.
    assert diff == [
        C("umur", ">", 30.0), C("umur", ">=", 60.0),
        C("status", "==", "pensiun"), C("status", "!=", "pekerja"),
    ]


def test_numeric_lower_than_cornerstone(domain):
    case = {**CORNER, "umur": 22.0}
    diff = difference_list(case, CORNER, domain)
    assert diff == [C("umur", "<", 30.0), C("umur", "<=", 22.0)]


def test_every_candidate_separates(domain):
    for cond in difference_list(CASE, CORNER, domain):
        assert cond.evaluate(CASE) and not cond.evaluate(CORNER)


def test_identical_case_gives_empty_list(domain):
    assert difference_list(dict(CORNER), CORNER, domain) == []


def test_attribute_missing_in_cornerstone(domain):
    # Atribut baru ditambahkan setelah cornerstone dibuat.
    from rdr import Attribute
    domain.add_attribute(Attribute("tanggungan", "numeric"))
    case = {**CORNER, "tanggungan": 3.0}
    diff = difference_list(case, CORNER, domain)
    assert diff == [C("tanggungan", ">=", 3.0), C("tanggungan", "<=", 3.0)]
