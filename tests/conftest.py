import pytest

from rdr import Domain


@pytest.fixture
def domain() -> Domain:
    return Domain.from_dict({
        "name": "Uji",
        "default_conclusion": "Tabungan Reguler",
        "attributes": {
            "umur": {"type": "numeric", "min": 17, "max": 100},
            "gaji": "numeric",
            "risiko": {"type": "categorical", "values": ["rendah", "sedang", "tinggi"]},
            "status": "categorical",
        },
    })
