import math
import numpy as np
from ursina import *
from ursina.prefabs.input_field import InputField

from physics import BallPhysics

app = Ursina(title='Table Tennis Simulation', width=1400, height=800)
window.color = color.rgb(15/255, 15/255, 25/255)
window.fps_counter.enabled = False
window.exit_button.visible = False
window.editor_ui.enabled = False

BALL_R = 0.020
TABLE_W = 1.525
TABLE_L = 2.74
NET_H = 0.1525
DT = 0.001
MAX_STEPS = 5

phys = BallPhysics()
acc = 0.0

c_table     = color.hsv(120, 0.7, 0.35)
c_line      = color.hsv(0, 0, 0.95)
c_net       = color.rgba(1, 1, 1, 0.25)
c_net_post  = color.hsv(0, 0, 0.25)
c_floor     = color.hsv(240, 0.1, 0.07)
c_ball      = color.hsv(25, 0.9, 0.95)
c_bg_panel  = color.rgba(0, 0, 0, 0.85)
c_play      = color.hsv(130, 0.6, 0.35)
c_reset     = color.hsv(0, 0.6, 0.4)

Entity(model='plane', scale=(TABLE_W, 1, TABLE_L), color=c_table, y=0)
Entity(model='cube', scale=(0.004, 0.003, TABLE_L), position=(-TABLE_W/2, 0.002, 0), color=c_line)
Entity(model='cube', scale=(0.004, 0.003, TABLE_L), position=( TABLE_W/2, 0.002, 0), color=c_line)
Entity(model='cube', scale=(TABLE_W, 0.003, 0.004), position=(0, 0.002, -TABLE_L/2), color=c_line)
Entity(model='cube', scale=(TABLE_W, 0.003, 0.004), position=(0, 0.002,  TABLE_L/2), color=c_line)
Entity(model='cube', scale=(TABLE_W, 0.003, 0.004), position=(0, 0.002, 0), color=c_line)
Entity(model='cube', scale=(TABLE_W-0.02, NET_H, 0.006), position=(0, NET_H/2, 0), color=c_net)
Entity(model='cube', scale=(0.014, NET_H+0.01, 0.014), position=(-TABLE_W/2-0.017, (NET_H+0.01)/2, 0), color=c_net_post)
Entity(model='cube', scale=(0.014, NET_H+0.01, 0.014), position=( TABLE_W/2+0.017, (NET_H+0.01)/2, 0), color=c_net_post)
Entity(model='plane', scale=(12, 1, 12), position=(0, -0.76, 0), color=c_floor)
for x in [-TABLE_W/2+0.05, TABLE_W/2-0.05]:
    for z in [-TABLE_L/2+0.05, TABLE_L/2-0.05]:
        Entity(model='cube', scale=(0.04, 0.72, 0.04), position=(x, -0.38, z), color=c_net_post)
DirectionalLight(y=5, z=-3, shadows=False)
AmbientLight(color=color.rgba(180, 180, 190, 255))

ball = Entity(model='sphere', scale=BALL_R*2,
              position=Vec3(float(phys.pos[0]), float(phys.pos[1]), float(phys.pos[2])),
              color=c_ball)

trail = []

trail_t = 0.0

def clear_trail():
    global trail
    for ent, _ in trail:
        destroy(ent)
    trail = []

def add_trail_point(pos):
    ent = Entity(model='quad', position=pos, scale=0.007, billboard=True,
                 color=color.rgb(1.0, 0.55, 0.0))
    trail.append((ent, pos))

def update_trail():
    global trail_t
    if not phys.active:
        return
    trail_t += time.dt
    if trail_t < 0.025:
        return
    trail_t = 0.0
    p = Vec3(float(phys.pos[0]), float(phys.pos[1]), float(phys.pos[2]))
    if trail and (p - trail[-1][1]).length() < 0.005:
        return
    add_trail_point(p)

cam_pos = Vec3(0, 2, -6)
cam_yaw = 0
cam_pitch = 20

ui = Entity(parent=camera.ui)
Entity(parent=ui, model='quad', color=c_bg_panel, scale=(0.40, 1.0), position=(0.80, 0))

fields = {}

def lbl(txt, y):
    Text(text=txt, parent=ui, position=(0.67, y), scale=0.7, color=color.white, origin=(0,0))

def fld(key, default, y, lab):
    Text(text=lab, parent=ui, position=(0.65, y), scale=0.7, color=color.white, origin=(0,0))
    f = InputField(parent=ui, default_value=str(default), label='',
                   position=(0.83, y), scale=(0.26, 0.024),
                   limit_content_to='0123456789.-', text_size=0.6)
    fields[key] = f
    return f

def gv(key, default):
    t = fields[key].text
    if t and t.strip():
        try: return float(t.strip())
        except: pass
    return default

Y = 0.44
lbl('Position (m)', Y); Y -= 0.034
fld('x0', 0.0, Y, 'X'); Y -= 0.034
fld('y0', 0.3, Y, 'Y'); Y -= 0.034
fld('z0', -1.5, Y, 'Z'); Y -= 0.06

lbl('Velocity (m/s)', Y); Y -= 0.034
fld('vx', 0.0, Y, 'Vx'); Y -= 0.034
fld('vy', -2.0, Y, 'Vy'); Y -= 0.034
fld('vz', 5.0, Y, 'Vz'); Y -= 0.06

lbl('Spin (rad/s)', Y); Y -= 0.034
fld('topspin', -100.0, Y, 'Topspin'); Y -= 0.034
fld('sidespin', 0.0, Y, 'Sidespin'); Y -= 0.06

lbl('Toss', Y); Y -= 0.034
fld('th', 0.5, Y, 'H'); Y -= 0.034
fld('td', 0.8, Y, 'T'); Y -= 0.06

status = Text(text='Ready', parent=ui, position=(0.75, Y), scale=1, color=color.yellow, origin=(0,0))
Y -= 0.05

play_btn  = Button(parent=ui, text='Play Out', position=(0.75, Y), scale=(0.18, 0.032),
                   color=c_play, highlight_color=color.hsv(130, 0.7, 0.45))
reset_btn = Button(parent=ui, text='Reset', position=(0.75, Y-0.05), scale=(0.18, 0.032),
                   color=c_reset, highlight_color=color.hsv(0, 0.7, 0.5))

tossing = False
toss_t = 0.0
toss_h = 0.5
toss_d = 0.8
toss_s = None

def on_play():
    global acc, tossing, toss_t, toss_s, toss_h, toss_d
    if phys.active or tossing:
        status.text = 'Already playing!'
        return
    x0 = gv('x0', 0.0)
    y0 = gv('y0', 0.3)
    z0 = gv('z0', -1.5)
    vel  = np.array([gv('vx', 0.0), gv('vy', 0.0), gv('vz', 8.0)], dtype=np.float64)
    spin = np.array([gv('topspin', -50.0), gv('sidespin', 0.0)], dtype=np.float64)
    toss_h = gv('th', 0.5)
    toss_d = gv('td', 0.8)
    phys.reset(np.array([x0, y0, z0], dtype=np.float64), vel, spin)
    phys.active = False
    acc = 0.0
    clear_trail()

    tossing = True; toss_t = 0.0
    toss_s = Vec3(x0, y0, z0)
    ball.position = toss_s
    status.text = 'Tossing...'

def on_reset():
    global tossing, acc
    tossing = False
    phys.active = False
    acc = 0.0
    ball.position = Vec3(float(phys.pos[0]), float(phys.pos[1]), float(phys.pos[2]))
    clear_trail()
    status.text = 'Ready'

play_btn.on_click = on_play
reset_btn.on_click = on_reset

def update():
    global tossing, toss_t, acc, cam_yaw, cam_pitch, cam_pos

    if tossing:
        toss_t += time.dt
        t = min(toss_t / toss_d, 1.0)
        cy = toss_s.y + 4 * toss_h * t * (1 - t)
        ball.position = Vec3(toss_s.x, cy, toss_s.z)
        strike_y = toss_s.y + max(0, toss_h - 0.6)
        if t > 0.5 and cy <= strike_y:
            tossing = False
            phys.pos[1] = cy
            ball.position = Vec3(float(phys.pos[0]), float(phys.pos[1]), float(phys.pos[2]))
            phys.active = True
            acc = 0.0
            add_trail_point(Vec3(float(phys.pos[0]), float(phys.pos[1]), float(phys.pos[2])))
            trail_t = 0.025
            status.text = 'Simulating...'

    if phys.active:
        acc += time.dt
        steps = 0
        while acc >= DT and steps < MAX_STEPS:
            phys.step(DT)
            acc -= DT
            steps += 1
        ball.position = Vec3(float(phys.pos[0]), float(phys.pos[1]), float(phys.pos[2]))
        update_trail()
        if not phys.active:
            status.text = 'Out of bounds - Reset'

    speed = 3 * time.dt
    fwd = Vec3(sin(math.radians(cam_yaw)), 0, cos(math.radians(cam_yaw))).normalized()
    rgt = Vec3(cos(math.radians(cam_yaw)), 0, -sin(math.radians(cam_yaw))).normalized()
    if held_keys['w']: cam_pos += fwd * speed
    if held_keys['s']: cam_pos -= fwd * speed
    if held_keys['a']: cam_pos -= rgt * speed
    if held_keys['d']: cam_pos += rgt * speed
    if held_keys['space']: cam_pos.y += speed
    if held_keys['shift']: cam_pos.y -= speed

    if mouse.right:
        cam_yaw += mouse.velocity[0] * 60
        cam_pitch = clamp(cam_pitch - mouse.velocity[1] * 60, -89, 89)

    camera.position = cam_pos
    camera.rotation = Vec3(cam_pitch, cam_yaw, 0)

app.run()
