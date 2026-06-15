import numpy as np
from config import (
    BALL_RADIUS, BALL_MASS, BALL_AREA, BALL_INERTIA, AIR_DENSITY, DRAG_COEFF,
    SPIN_DECAY_COEFF, SPIN_AXIS_DECAY_COEFF,
    GRAVITY, VERT_RESTITUTION, TABLE_FRICTION_COEFF, MAX_TANG_RESTITUTION,
    GRIP_THRESHOLD, MAGNUS_COEFF_MAX, MAGNUS_S_OPTIMAL,
    TABLE_X_MIN, TABLE_X_MAX, TABLE_Z_MIN, TABLE_Z_MAX,
)


class BallPhysics:
    def __init__(self):
        self.pos = np.array([0.0, 0.3, -1.5], dtype=np.float64)
        self.vel = np.array([0.0, 0.0, 0.0], dtype=np.float64)
        self.spin = np.array([0.0, 0.0], dtype=np.float64)
        self.active = False

    def reset(self, pos, vel, spin):
        self.pos = np.array(pos, dtype=np.float64)
        self.vel = np.array(vel, dtype=np.float64)
        spin = np.array(spin, dtype=np.float64)
        if spin.shape == (3,):
            self.spin = np.array([spin[0], spin[2]], dtype=np.float64)
        else:
            self.spin = spin

    def step(self, dt):
        if not self.active:
            return

        self._rk4_step(dt)

        if (self.pos[1] < -1.0 or abs(self.pos[0]) > 6 or abs(self.pos[2]) > 6):
            self.active = False
            return

        self._handle_table_bounce()

    def _compute_acceleration(self, pos, vel, spin_2d):
        speed = np.linalg.norm(vel)
        omega_norm = np.linalg.norm(spin_2d)

        Fg = np.array([0.0, -GRAVITY * BALL_MASS, 0.0])

        if speed > 1e-8:
            Fd = -0.5 * AIR_DENSITY * DRAG_COEFF * BALL_AREA * speed * vel
        else:
            Fd = np.zeros(3)

        Fm = np.zeros(3)
        if speed > 1e-3 and omega_norm > 1e-3:
            S = (BALL_RADIUS * omega_norm) / speed
            S_opt = MAGNUS_S_OPTIMAL
            C_L = MAGNUS_COEFF_MAX * (2.0 * S * S_opt) / (S * S + S_opt * S_opt + 1e-8)
            Fm_base = 0.5 * AIR_DENSITY * C_L * BALL_AREA

            wx, wz = spin_2d[0], spin_2d[1]

            if abs(wx) > 1e-8:
                speed_h = np.sqrt(vel[0]**2 + vel[2]**2)
                if speed_h > 1e-3:
                    Fm[1] = -Fm_base * (wx / omega_norm) * (speed_h ** 2)

            if abs(wz) > 1e-8:
                Fm[0] = -Fm_base * (wz / omega_norm) * vel[1] * speed
                Fm[2] = Fm_base * (wz / omega_norm) * vel[0] * speed

        accel = (Fg + Fd + Fm) / BALL_MASS

        spin_decay_mag = SPIN_DECAY_COEFF
        spin_axis_decay = SPIN_AXIS_DECAY_COEFF * (omega_norm / (speed + 1e-3))

        return accel, spin_decay_mag, spin_axis_decay

    def _rk4_step(self, dt):
        def deriv(pos, vel, spin):
            accel, spin_decay_mag, _ = self._compute_acceleration(pos, vel, spin)
            spin_mag = np.linalg.norm(spin)
            if spin_mag > 1e-8:
                dspin = -spin_decay_mag * spin
            else:
                dspin = np.zeros(2)
            return accel, dspin

        k1v, k1s = deriv(self.pos, self.vel, self.spin)
        k1x = self.vel

        k2v, k2s = deriv(self.pos + 0.5 * dt * k1x, self.vel + 0.5 * dt * k1v, self.spin + 0.5 * dt * k1s)
        k2x = self.vel + 0.5 * dt * k1v

        k3v, k3s = deriv(self.pos + 0.5 * dt * k2x, self.vel + 0.5 * dt * k2v, self.spin + 0.5 * dt * k2s)
        k3x = self.vel + 0.5 * dt * k2v

        k4v, k4s = deriv(self.pos + dt * k3x, self.vel + dt * k3v, self.spin + dt * k3s)
        k4x = self.vel + dt * k3v

        self.pos += dt / 6.0 * (k1x + 2*k2x + 2*k3x + k4x)
        self.vel += dt / 6.0 * (k1v + 2*k2v + 2*k3v + k4v)
        self.spin += dt / 6.0 * (k1s + 2*k2s + 2*k3s + k4s)

    def _handle_table_bounce(self):
        r = BALL_RADIUS
        if (self.pos[1] <= r and
                self.vel[1] < 0 and
                TABLE_X_MIN <= self.pos[0] <= TABLE_X_MAX and
                TABLE_Z_MIN <= self.pos[2] <= TABLE_Z_MAX):

            self.pos[1] = r

            self.vel[1] = -VERT_RESTITUTION * self.vel[1]

            wx, wz = self.spin[0], self.spin[1]
            v_rel_x = self.vel[0] + r * wz
            v_rel_z = self.vel[2] - r * wx
            v_rel_mag = np.sqrt(v_rel_x**2 + v_rel_z**2)

            m_eff = BALL_MASS / (1.0 + BALL_MASS * r**2 / BALL_INERTIA)

            J_n = BALL_MASS * (1.0 + VERT_RESTITUTION) * abs(self.vel[1] / VERT_RESTITUTION)
            J_f_max = TABLE_FRICTION_COEFF * J_n

            J_stop_mag = m_eff * v_rel_mag

            if v_rel_mag < GRIP_THRESHOLD:
                e_t = MAX_TANG_RESTITUTION
                J_t_mag = -e_t * m_eff * v_rel_mag
            else:
                J_t_mag = -min(J_f_max, J_stop_mag)

            if v_rel_mag > 1e-8:
                J_t_x = J_t_mag * (v_rel_x / v_rel_mag)
                J_t_z = J_t_mag * (v_rel_z / v_rel_mag)

                self.vel[0] += J_t_x / BALL_MASS
                self.vel[2] += J_t_z / BALL_MASS

                dwx = (-r * J_t_z) / BALL_INERTIA
                dwz = (r * J_t_x) / BALL_INERTIA

                new_wx = self.spin[0] + dwx
                new_wz = self.spin[1] + dwz

                if self.spin[0] * new_wx < 0:
                    new_wx = 0.1 * self.spin[0]
                if self.spin[1] * new_wz < 0:
                    new_wz = 0.1 * self.spin[1]

                self.spin[0] = new_wx
                self.spin[1] = new_wz

            spin_mag = np.linalg.norm(self.spin)
            max_spin = (TABLE_FRICTION_COEFF * (1 + VERT_RESTITUTION) * abs(self.vel[1] / VERT_RESTITUTION) * r / BALL_INERTIA) * 2.0
            if spin_mag > max_spin and spin_mag > 1e-8:
                self.spin = self.spin * (max_spin / spin_mag)
