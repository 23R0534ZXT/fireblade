"""The ident must be drawn, centred, and short enough not to delay a launch."""
from fireblade.ui.startup import DURATION, HEIGHT, WIDTH, StartupAnimation


def render(widget, phase):
    widget.phase = phase
    return widget.grab().toImage()


def light_in_band(image, left, right, top, bottom, step=4):
    total = 0
    for y in range(top, bottom, step):
        for x in range(left, right, step):
            colour = image.pixelColor(x, y)
            total += colour.red() + colour.green() + colour.blue()
    return total


def test_the_ident_is_short_enough_not_to_hold_a_launch(qt_application):
    widget = StartupAnimation()
    try:
        assert widget.animation.duration() == DURATION
        assert DURATION <= 6000, "un ident ne doit pas retenir le lancement"
        assert (widget.width(), widget.height()) == (WIDTH, HEIGHT)
    finally:
        widget.deleteLater()


def test_the_wordmark_appears_and_the_frame_lights_up(qt_application):
    widget = StartupAnimation()
    try:
        early = render(widget, .04)
        late = render(widget, .95)
        band = (150, 570, 196, 246)
        assert light_in_band(late, *band) > light_in_band(early, *band) * 4
    finally:
        widget.deleteLater()


def test_the_wordmark_sits_on_the_axis(qt_application):
    """Centred means the lit pixels are balanced around the middle of the window."""
    widget = StartupAnimation()
    try:
        image = render(widget, .95)
        left = light_in_band(image, 0, WIDTH // 2, 300, 430)
        right = light_in_band(image, WIDTH // 2, WIDTH, 300, 430)
        assert left and right
        assert .75 < left / right < 1.35, (left, right)
    finally:
        widget.deleteLater()


def test_the_last_frame_fades_to_the_backdrop(qt_application):
    widget = StartupAnimation()
    band = (150, 570, 196, 246)
    try:
        bright = render(widget, .90)
        dark = render(widget, 1.0)
        assert light_in_band(dark, *band) < light_in_band(bright, *band) * .5
    finally:
        widget.deleteLater()
