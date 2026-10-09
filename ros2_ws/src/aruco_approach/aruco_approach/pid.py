"""ПИД-регулятор с ограничением выхода и защитой от интегрального насыщения."""
import math
from typing import Optional


class PID:

    def __init__(self, kp: float, ki: float = 0.0, kd: float = 0.0,
                 output_limit: Optional[float] = None,
                 integral_limit: Optional[float] = None,
                 derivative_smoothing: float = 0.5):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limit = output_limit
        self.integral_limit = integral_limit
        # 0 — без сглаживания производной, ближе к 1 — сильнее сглаживание
        self.derivative_smoothing = derivative_smoothing
        self.reset()

    def reset(self):
        self.integral = 0.0
        self.prev_error = None
        self.derivative = 0.0

    def update(self, error: float, dt: float) -> float:
        dt = max(dt, 1e-3)

        if self.prev_error is not None:
            raw = (error - self.prev_error) / dt
            a = self.derivative_smoothing
            self.derivative = a * self.derivative + (1.0 - a) * raw
        self.prev_error = error

        integral = self.integral + error * dt
        if self.integral_limit is not None:
            integral = max(-self.integral_limit, min(self.integral_limit, integral))

        output = self.kp * error + self.ki * integral + self.kd * self.derivative
        limit = self.output_limit
        saturated = limit is not None and abs(output) > limit
        # условное интегрирование: в насыщении интеграл не копится в ту же сторону
        if not (saturated and math.copysign(1.0, output) == math.copysign(1.0, error)):
            self.integral = integral
        if saturated:
            output = math.copysign(limit, output)
        return output
