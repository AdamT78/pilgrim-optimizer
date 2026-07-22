from pilgrim.model.workforce import (
    CommittedAcolytes,
    Workforce,
    committed_total,
    mancala_total,
    total_acolytes,
)


def test_workforce_mancala_total() -> None:
    workforce = Workforce(mancala=(1, 2, 0, 0, 0, 0, 0, 0, 0))
    assert mancala_total(workforce) == 3


def test_workforce_committed_total() -> None:
    workforce = Workforce(
        mancala=(0, 0, 0, 0, 0, 0, 0, 0, 0),
        committed=CommittedAcolytes(
            roads=1,
            shrines=2,
            market_ports=3,
            pilgrimage_sites=4,
            alms_table=5,
        ),
    )
    assert committed_total(workforce) == 15


def test_workforce_overall_total_includes_all_pools() -> None:
    workforce = Workforce(
        mancala=(1, 1, 1, 0, 0, 0, 0, 0, 0),
        village=2,
        abbey=3,
        committed=CommittedAcolytes(roads=1, shrines=1),
    )
    assert total_acolytes(workforce) == 10
