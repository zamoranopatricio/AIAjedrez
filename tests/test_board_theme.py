import config


def test_board_uses_chess_com_green_and_cream_squares():
    assert config.C_LIGHT_SQ == (238, 238, 210)
    assert config.C_DARK_SQ == (118, 150, 86)
