import numpy as np
from . import effective_quantity


def estimate(
    light_front_cx,
    light_front_cy,
    image_infinity_cx_mean,
    image_infinity_cy_mean,
):
    rec_cx = -0.5 * (light_front_cx + image_infinity_cx_mean)
    rec_cy = -0.5 * (light_front_cy + image_infinity_cy_mean)
    return rec_cx, rec_cy


def momentum_to_cx_cy_wrt_aperture(
    momentum_x_GeV_per_c,
    momentum_y_GeV_per_c,
    momentum_z_GeV_per_c,
    plenoscope_pointing,
):
    assert plenoscope_pointing["zenith_deg"] == 0.0
    assert plenoscope_pointing["azimuth_deg"] == 0.0
    WRT_APERTURE = -1.0
    momentum = np.array(
        [momentum_x_GeV_per_c, momentum_y_GeV_per_c, momentum_z_GeV_per_c,]
    ).T
    momentum_norm = np.linalg.norm(momentum, axis=1)
    for m in range(len(momentum_norm)):
        momentum[m, :] /= momentum_norm[m]
    return WRT_APERTURE * momentum[:, 0], WRT_APERTURE * momentum[:, 1]


def histogram_point_spread_function(
    theta_deg, theta_square_bin_edges_deg2, psf_containment_factor,
):
    """
    angle between truth and reconstruction for each event.

    psf_containment_factor e.g. 0.68
    """
    num_airshower = theta_deg.shape[0]

    if num_airshower > 0:
        theta_square_hist = np.histogram(
            theta_deg ** 2, bins=theta_square_bin_edges_deg2
        )[0]
        theta_square_hist_relunc = effective_quantity._divide_silent(
            np.sqrt(theta_square_hist), theta_square_hist, np.nan
        )
    else:
        theta_square_hist = np.zeros(
            len(theta_square_bin_edges_deg2) - 1, dtype=np.int64
        )
        theta_square_hist_relunc = np.nan * np.ones(
            len(theta_square_bin_edges_deg2) - 1, dtype=np.float64
        )

    if num_airshower > 0:
        theta_deg = np.quantile(theta_deg, q=psf_containment_factor)
        theta_square_deg2 = theta_deg ** 2

        theta_square_deg2_relunc = np.sqrt(num_airshower) / num_airshower
    else:
        theta_square_deg2 = np.nan

        theta_square_deg2_relunc = np.nan

    return {
        "theta_square_hist": theta_square_hist,
        "theta_square_hist_relunc": theta_square_hist_relunc,
        "containment_angle_deg": np.sqrt(theta_square_deg2),
        "containment_angle_deg_relunc": theta_square_deg2_relunc,
    }


def estimate_fix_opening_angle_for_onregion(
    energy_bin_centers_GeV,
    point_spread_function_containment_opening_angle_deg,
    pivot_energy_GeV,
    num_rise=8,
):
    """
    Estimates and returns the psf's opening angle at a given pivot_energy when
    given psf's opening angle vs energy.
    Uses weighted interpolation in the vicinity of the pivot_energy.
    """
    smooth_kernel_energy = np.geomspace(
        pivot_energy_GeV / 2, pivot_energy_GeV * 2, num_rise * 2
    )
    triangle_kernel_weight = np.hstack(
        [np.cumsum(np.ones(num_rise)), np.flip(np.cumsum(np.ones(num_rise)))]
    )
    triangle_kernel_weight /= np.sum(triangle_kernel_weight)
    pivot_containtment_deg = np.interp(
        x=smooth_kernel_energy,
        xp=energy_bin_centers_GeV,
        fp=point_spread_function_containment_opening_angle_deg,
    )
    fix_onregion_radius_deg = np.sum(
        pivot_containtment_deg * triangle_kernel_weight
    )
    return fix_onregion_radius_deg
