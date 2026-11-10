"""Generate the TierwiseAgents banner and logo: python3 make_art.py <output dir>

Needs numpy, Pillow and the JetBrains Mono font. Colours are the constants below.
"""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]
INK   = (15, 20, 18)      # near-black with a green cast
BONE  = (236, 228, 208)   # paper
RUST  = (214, 72, 31)     # top tier
OCHRE = (226, 164, 44)    # mid tier
MOSS  = (74, 110, 92)     # small tier
JB = "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-%s.ttf"

BAYER = np.array([[0,32,8,40,2,34,10,42],[48,16,56,24,50,18,58,26],[12,44,4,36,14,46,6,38],
                  [60,28,52,20,62,30,54,22],[3,35,11,43,1,33,9,41],[51,19,59,27,49,17,57,25],
                  [15,47,7,39,13,45,5,37],[63,31,55,23,61,29,53,21]]) / 64.0

def terrain(w, h, peaks, seed, wobble=0.10):
    """Height field in 0..1: gaussian peaks plus low-frequency waves."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w].astype(float)
    z = np.zeros((h, w))
    for cx, cy, sx, sy, a in peaks:
        z += a * np.exp(-(((x - cx * w) / (sx * w)) ** 2 + ((y - cy * h) / (sy * w)) ** 2))
    for _ in range(7):
        fx, fy = rng.uniform(0.6, 3.2, 2) * 2 * np.pi / w
        z += wobble * rng.uniform(0.3, 1) * np.sin(x * fx + rng.uniform(0, 6.3)) * np.cos(y * fy + rng.uniform(0, 6.3))
    z -= z.min()
    return z / z.max()

def render(z, fade=None, levels=14, t_mid=0.45, t_top=0.72, cuts=None):
    h, w = z.shape
    img = np.empty((h, w, 3), np.uint8); img[:] = INK
    thr = np.tile(BAYER, (h // 8 + 1, w // 8 + 1))[:h, :w]
    f = np.ones_like(z) if fade is None else fade
    # three tiers, each with its own colour and dither density rising with height
    low = (z < t_mid); mid = (z >= t_mid) & (z < t_top); top = z >= t_top
    dens = np.where(low, 0.04 + 0.30 * (z / t_mid),
            np.where(mid, 0.22 + 0.45 * ((z - t_mid) / (t_top - t_mid)),
                     0.55 + 0.45 * ((z - t_top) / (1 - t_top)))) * f
    on = dens > thr
    for mask, col in ((low, MOSS), (mid, OCHRE), (top, RUST)):
        img[on & mask] = col
    # contour lines where the quantised level changes
    q = np.digitize(z, cuts) if cuts is not None else np.minimum(np.floor(z * levels), levels - 1)
    edge = np.zeros_like(on)
    edge[:, 1:] |= q[:, 1:] != q[:, :-1]; edge[1:, :] |= q[1:, :] != q[:-1, :]
    line_on = edge & (f > thr * 0.9)
    img[line_on] = BONE
    return img

def up(img, s):
    return Image.fromarray(img).resize((img.shape[1] * s, img.shape[0] * s), Image.NEAREST)

def pixel_text(size, text, font, fill):
    """Text rendered without anti-aliasing on a transparent low-res layer."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer); d.fontmode = "1"
    return layer, d

# ---------- banner 1600x480 ----------
S = 4; W, H = 400, 120
z = terrain(W, H, [(0.84, 0.44, 0.11, 0.10, 1.0), (0.72, 0.80, 0.09, 0.08, 0.5),
                   (0.99, 0.92, 0.08, 0.08, 0.5), (0.70, 0.05, 0.10, 0.08, 0.3)], seed=7)
x = np.linspace(0, 1, W)[None, :].repeat(H, 0)
fade = np.clip((x - 0.615) / 0.17, 0.0, 1.0) ** 1.2          # quiet on the left for the text
img = render(z, fade)
layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer); d.fontmode = "1"
big = ImageFont.truetype(JB % "ExtraBold", 27)
d.text((16, 30), "Tierwise", font=big, fill=BONE)
wT = d.textlength("Tierwise", font=big)
d.text((16 + wT, 30), "Agents", font=big, fill=RUST)
# three tier bars under the wordmark
for i, (col, wbar) in enumerate(((RUST, 20), (OCHRE, 44), (MOSS, 80))):
    d.rectangle([16, 70 + i * 5, 16 + wbar, 72 + i * 5], fill=col)
banner = up(img, S).convert("RGBA"); banner.alpha_composite(layer.resize((W * S, H * S), Image.NEAREST))
d2 = ImageDraw.Draw(banner)
d2.text((64 + 344, 276), "THE RIGHT MODEL FOR EVERY JOB", font=ImageFont.truetype(JB % "Medium", 24), fill=BONE)
d2.text((64 + 344, 312), "plan on top  ·  build on mid  ·  chores on small", font=ImageFont.truetype(JB % "Regular", 19), fill=(150, 160, 148))
banner.convert("RGB").save(f"{OUT}/banner.png", optimize=True)

# ---------- logo 1024x1024 ----------
S = 8; N = 128
z = terrain(N, N, [(0.50, 0.46, 0.30, 0.30, 1.0), (0.70, 0.66, 0.17, 0.15, 0.40), (0.30, 0.64, 0.15, 0.18, 0.34)], seed=21, wobble=0.06)
y, x = np.mgrid[0:N, 0:N]; r = np.hypot(x - N / 2 + 0.5, y - N / 2 + 0.5) / (N / 2)
z = z * np.clip(1.08 - r ** 3.0, 0, 1); z /= z.max()
img = render(z, t_mid=0.42, t_top=0.70, cuts=[0.16, 0.29, 0.42, 0.56, 0.70, 0.86])
q0 = z >= 0.16; near = q0.copy()
for ax in (0, 1):
    for sh in (1, -1): near |= np.roll(q0, sh, ax)
img[~near] = INK                                            # clean margin, coastline kept
logo = up(img, S)
logo.save(f"{OUT}/logo.png", optimize=True)
logo.resize((512, 512), Image.NEAREST).save(f"{OUT}/logo-512.png", optimize=True)

# ---------- social preview 1280x640 ----------
S = 4; W, H = 320, 160
z = terrain(W, H, [(0.82, 0.40, 0.13, 0.12, 1.0), (0.66, 0.84, 0.10, 0.09, 0.5),
                   (1.00, 0.95, 0.09, 0.09, 0.5), (0.66, 0.02, 0.11, 0.08, 0.3)], seed=7)
x = np.linspace(0, 1, W)[None, :].repeat(H, 0)
img = render(z, np.clip((x - 0.60) / 0.17, 0.0, 1.0) ** 1.2)
layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer); d.fontmode = "1"
big = ImageFont.truetype(JB % "ExtraBold", 21)
d.text((16, 50), "Tierwise", font=big, fill=BONE)
d.text((16 + d.textlength("Tierwise", font=big), 50), "Agents", font=big, fill=RUST)
for i, (col, wbar) in enumerate(((RUST, 20), (OCHRE, 44), (MOSS, 80))):
    d.rectangle([16, 84 + i * 5, 16 + wbar, 86 + i * 5], fill=col)
social = up(img, S).convert("RGBA"); social.alpha_composite(layer.resize((W * S, H * S), Image.NEAREST))
d2 = ImageDraw.Draw(social)
d2.text((64, 424), "THE RIGHT MODEL FOR EVERY JOB", font=ImageFont.truetype(JB % "Medium", 26), fill=BONE)
d2.text((64, 464), "plan on top  ·  build on mid  ·  chores on small", font=ImageFont.truetype(JB % "Regular", 20), fill=(150, 160, 148))
social.convert("RGB").save(f"{OUT}/social-preview.png", optimize=True)
