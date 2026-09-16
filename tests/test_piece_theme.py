import chess
import pygame

import config
from src.asset_loader import load_piece_images


def test_piece_set_uses_gray_chess_com_like_bodies_with_visible_outlines():
    pygame.init()
    pygame.display.set_mode((1, 1))

    images = load_piece_images(config.ASSETS_DIR)
    black_queen = images[chess.Piece(chess.QUEEN, chess.BLACK)]
    white_queen = images[chess.Piece(chess.QUEEN, chess.WHITE)]

    black_pixels = {tuple(black_queen.get_at((x, y))) for x in range(80) for y in range(80)}
    white_pixels = {tuple(white_queen.get_at((x, y))) for x in range(80) for y in range(80)}

    assert (75, 75, 75, 255) in black_pixels
    assert (70, 70, 70, 255) in white_pixels
