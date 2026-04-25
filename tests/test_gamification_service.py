from kechafa_app.services.gamification_service import GamificationService


def test_compute_level_scales_with_xp():
    assert GamificationService._compute_level(0) == 1
    assert GamificationService._compute_level(100) == 2
    assert GamificationService._compute_level(400) == 3
