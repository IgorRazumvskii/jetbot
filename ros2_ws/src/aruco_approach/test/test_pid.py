import pytest

from aruco_approach.pid import PID


def test_proportional_and_limit():
    pid = PID(2.0, output_limit=1.0)
    assert pid.update(0.25, 0.05) == pytest.approx(0.5)
    assert pid.update(5.0, 0.05) == pytest.approx(1.0)
    assert pid.update(-5.0, 0.05) == pytest.approx(-1.0)


def test_integral_does_not_wind_up_in_saturation():
    pid = PID(1.0, ki=1.0, output_limit=0.5)
    for _ in range(200):
        pid.update(2.0, 0.05)
    # после долгого насыщения интеграл не накопился — выход сразу меняет знак
    assert pid.update(-0.6, 0.05) < 0.0


def test_closed_loop_converges():
    """Интегратор (поворот робота) под П-регулятором сходится к нулю."""
    pid = PID(1.5, kd=0.1, output_limit=1.0)
    angle, dt = 0.8, 0.05
    for _ in range(200):
        angle -= pid.update(angle, dt) * dt
    assert abs(angle) < 1e-3
