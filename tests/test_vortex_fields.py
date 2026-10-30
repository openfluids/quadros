"""Check vortex scalars on curved spectral elements."""

from __future__ import annotations

import numpy as np

from quadros._legacy_render_nek_isosurface_views import (
    extract_isosurfaces_for_field,
    gll_nodes,
    parse_iso_specs,
    renderable_field_names,
    scalar_values,
    velocity_gradient,
)


class _Elem:
    def __init__(self, pos: np.ndarray, vel: np.ndarray) -> None:
        self.pos = pos
        self.vel = vel


class _Field:
    def __init__(self, elem: _Elem) -> None:
        self.elem = [elem]


class _Scene:
    roi_bounds = None
    surface_smooth_method = "none"
    surface_smooth_iterations = 0
    surface_smooth_relaxation = 0.0
    surface_taubin_pass_band = 0.1
    surface_smooth_edge_angle = 15.0
    surface_smooth_feature_angle = 45.0
    surface_smooth_boundary = True
    surface_smooth_feature = False


def _curved_geometry(lx: int, ly: int, lz: int):
    """Sample one curved hex at Gauss-Lobatto-Legendre nodes.

    The map is quadratic, so a grid of order 2 or higher resolves it.
    """
    r = gll_nodes(lx).reshape(1, 1, lx)
    s = gll_nodes(ly).reshape(1, ly, 1)
    t = gll_nodes(lz).reshape(lz, 1, 1)
    shape = (lz, ly, lx)
    r3 = np.broadcast_to(r, shape)
    s3 = np.broadcast_to(s, shape)
    t3 = np.broadcast_to(t, shape)
    x = r3 + 0.15 * r3 * s3
    y = s3 + 0.10 * s3 * t3
    z = t3 + 0.08 * r3 * t3 + 0.05 * s3**2
    return r3, s3, t3, x, y, z


def _element(lx: int, ly: int, lz: int, velocity) -> _Elem:
    r3, s3, t3, x, y, z = _curved_geometry(lx, ly, lz)
    pos = np.stack((x, y, z), axis=0)
    vel = np.stack(velocity(r3, s3, t3, x, y, z), axis=0)
    return _Elem(pos, vel)


def _assert_close(got: np.ndarray, expected: float, rtol: float = 1e-10) -> None:
    np.testing.assert_allclose(got, expected, rtol=rtol, atol=1e-12)


def test_solid_body_rotation_on_a_curved_element() -> None:
    """Check solid-body rotation about x on a curved element.

    The rotation rate is Omega.
    omx equals 2*Omega.
    omy and omz equal 0.
    q equals Omega**2.
    lambda2 equals -Omega**2.
    """
    omega = 0.8
    elem = _element(
        6,
        5,
        7,
        lambda _r, _s, _t, _x, y, z: (np.zeros_like(y), -omega * z, omega * y),
    )
    _assert_close(scalar_values(elem, "omx"), 2.0 * omega)
    _assert_close(scalar_values(elem, "omy"), 0.0)
    _assert_close(scalar_values(elem, "omz"), 0.0)
    _assert_close(scalar_values(elem, "q"), omega**2)
    _assert_close(scalar_values(elem, "lambda2"), -(omega**2))
    assert velocity_gradient(elem) is velocity_gradient(elem)


def test_pure_strain_middle_eigenvalue() -> None:
    """Check pure strain u=a*x, v=-a*y, w=0 on a curved element.

    Vorticity is 0.
    q equals -a**2.
    Eigenvalues of S^2 + Omega^2 follow lambda1 >= lambda2 >= lambda3.
    lambda2 is the middle eigenvalue.
    For diag(a**2, a**2, 0) the middle eigenvalue is a**2.
    The value 0 is lambda3.
    """
    rate = 0.7
    elem = _element(
        5,
        6,
        5,
        lambda _r, _s, _t, x, y, z: (rate * x, -rate * y, np.zeros_like(z)),
    )
    _assert_close(scalar_values(elem, "omx"), 0.0)
    _assert_close(scalar_values(elem, "omy"), 0.0)
    _assert_close(scalar_values(elem, "omz"), 0.0)
    _assert_close(scalar_values(elem, "q"), -(rate**2))
    _assert_close(scalar_values(elem, "lambda2"), rate**2)
    moment = np.diag([rate**2, rate**2, 0.0])
    descending = np.sort(np.linalg.eigvalsh(moment))[::-1]
    assert descending[1] == rate**2
    assert descending[2] == 0.0


def test_polynomial_gradient_is_spectrally_exact() -> None:
    """Check a polynomial of degree N on a curved element.

    The analytic gradient is known in closed form.
    The max error must stay below 1e-8.
    """
    nodes = gll_nodes(5)
    closed_form = np.array([-1.0, -np.sqrt(3.0 / 7.0), 0.0, np.sqrt(3.0 / 7.0), 1.0])
    np.testing.assert_allclose(nodes, closed_form, atol=1e-12)

    lx, ly, lz = 5, 6, 4
    nr, ns, nt = lx - 1, ly - 1, lz - 1
    r, s, t, x, y, z = _curved_geometry(lx, ly, lz)
    u = r**nr + 0.25 * r * s
    v = s**ns
    w = t**nt + 0.2 * r * t
    elem = _Elem(np.stack((x, y, z), axis=0), np.stack((u, v, w), axis=0))

    du = np.stack((nr * r ** (nr - 1) + 0.25 * s, 0.25 * r, np.zeros_like(r)), axis=-1)
    dv = np.stack((np.zeros_like(s), ns * s ** (ns - 1), np.zeros_like(s)), axis=-1)
    dw = np.stack((0.2 * t, np.zeros_like(t), nt * t ** (nt - 1) + 0.2 * r), axis=-1)
    reference = np.stack((du, dv, dw), axis=-2)
    dx = np.stack((1.0 + 0.15 * s, 0.15 * r, np.zeros_like(r)), axis=-1)
    dy = np.stack((np.zeros_like(s), 1.0 + 0.10 * t, 0.10 * s), axis=-1)
    dz = np.stack((0.08 * t, 0.10 * s, 1.0 + 0.08 * r), axis=-1)
    jacobian = np.stack((dx, dy, dz), axis=-2)
    assert float(np.min(np.abs(np.linalg.det(jacobian)))) > 0.2
    expected = reference @ np.linalg.inv(jacobian)
    error = float(np.max(np.abs(velocity_gradient(elem) - expected)))
    assert error < 1e-8, f"max gradient error is {error:.3e}"


def test_renderable_field_names_include_vortex_fields() -> None:
    """Check that velocity and pressure expose the vortex fields."""
    names = renderable_field_names(("u", "v", "w", "p"))
    for name in ("speed", "omx", "omy", "omz", "q", "lambda2"):
        assert name in names
    partial = renderable_field_names(("u", "v", "p"))
    for name in ("speed", "omx", "omy", "omz", "q", "lambda2"):
        assert name not in partial


def test_q_isosurface_reaches_scalar_values(monkeypatch) -> None:
    """Check that an IsoSpec on q reaches scalar_values and contours."""
    import quadros._legacy_render_nek_isosurface_views as views

    class _Silent:
        def info(self, *_args, **_kwargs) -> None:
            return None

        def warning(self, *_args, **_kwargs) -> None:
            return None

    monkeypatch.setattr(views, "log", lambda: _Silent())
    elem = _element(
        5,
        5,
        5,
        lambda r, s, t, _x, _y, _z: (r**3 + 0.2 * s, s**2 * t, 0.3 * r * t),
    )
    q_values = scalar_values(elem, "q")
    level = float(np.min(q_values) + 0.3 * (np.max(q_values) - np.min(q_values)))
    assert float(np.min(q_values)) < level < float(np.max(q_values))
    specs = parse_iso_specs(f"q={level:.16g}", ("u", "v", "w", "p"))
    assert len(specs) == 1
    assert specs[0].field == "q"
    assert scalar_values(elem, specs[0].field).shape == q_values.shape
    omx_specs = parse_iso_specs("omx=0", ("u", "v", "w"))
    assert omx_specs[0].field == "omx"
    assert scalar_values(elem, omx_specs[0].field).shape == elem.vel.shape[1:]
    _surfaces, stats = extract_isosurfaces_for_field(_Field(elem), list(specs), _Scene())
    assert stats[specs[0]]["points"] > 0
