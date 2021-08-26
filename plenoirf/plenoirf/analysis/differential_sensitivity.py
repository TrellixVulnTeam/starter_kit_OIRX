import numpy as np
import json_numpy
import os
from . import integral_sensitivity


def estimate_differential_sensitivity(
    energy_bin_edges_GeV,
    signal_area_vs_energy_m2,
    signal_rate_vs_energy_per_s,
):
    """
    Returns the diff.Flux-sensitivity df/dE / m^{-2} s^{-1} (GeV)^{-1}
    required to reach the critical signal rate.

    Parameters
    ----------
    energy_bin_edges_GeV : array 1d
            The edges of the energy-bins in GeV.
    signal_area_vs_energy_m2 : array 1d
            The effective area for the signal in m$^{2}$.
    signal_rate_vs_energy_per_s : array 1d
            The minimal rate for signal to claim a detection in s$^{-1}$.
    """
    num_bins = len(energy_bin_edges_GeV) - 1
    dfdE_per_s_per_m2_per_GeV = np.nan * np.ones(num_bins)
    for e in range(num_bins):
        dE_GeV = energy_bin_edges_GeV[e + 1] - energy_bin_edges_GeV[e]
        assert dE_GeV > 0.0
        if signal_area_vs_energy_m2[e] > 0:
            f_per_s_per_m2 = (
                signal_rate_vs_energy_per_s[e] / signal_area_vs_energy_m2[e]
            )
        else:
            f_per_s_per_m2 = np.nan

        dfdE_per_s_per_m2_per_GeV[e] = f_per_s_per_m2 / dE_GeV
    return dfdE_per_s_per_m2_per_GeV


SCENARIOS = {
    "perfect_energy": {
        "energy_axes_label": "",
    },
    "broad_spectrum": {
        "energy_axes_label": "reco.",
    },
    "line_spectrum": {
        "energy_axes_label": "reco.",
    },
    "bell_spectrum": {
        "energy_axes_label": "",
    },
}


def make_energy_confusion_matrices_for_signal_and_background(
    signal_energy_confusion_matrix,
    signal_energy_confusion_matrix_abs_unc,
    scenario_key="broad_spectrum",
):
    s_cm = signal_energy_confusion_matrix
    s_cm_u = signal_energy_confusion_matrix_abs_unc

    if scenario_key == "perfect_energy":
        _s_cm = np.eye(N=s_cm.shape[0])
        _s_cm_u = np.zeros(shape=s_cm.shape) # zero uncertainty

        _bg_integral_mask = np.eye(N=s_cm.shape[0])
        _energy_axes_label = ""

    elif scenario_key == "broad_spectrum":
        _s_cm = np.array(s_cm)
        _s_cm_u = np.array(s_cm_u) # adopt as is

        _bg_integral_mask = np.eye(N=s_cm.shape[0])
        _energy_axes_label = "reco."

    elif scenario_key == "line_spectrum":
        eye = np.eye(N=s_cm.shape[0])
        _s_cm = eye * np.diag(s_cm)
        _s_cm_u = eye * np.diag(s_cm_u) # only the diagonal

        _bg_integral_mask = np.eye(N=s_cm.shape[0])
        _energy_axes_label = "reco."

    elif scenario_key == "bell_spectrum":
        containment = 0.68
        _s_cm = containment * np.eye(N=s_cm.shape[0]) # true energy for gammas
        _s_cm_u = np.zeros(shape=s_cm.shape) # zero uncertainty

        _bg_integral_mask = make_mask_for_energy_confusion_matrix_for_bell_spectrum(
            energy_confusion_matrix=s_cm,
            containment=containment
        )
        _energy_axes_label = ""

    else:
        raise KeyError("Unknown scenario_key: '{:s}'".format(scenario_key))

    return {
        "signal_matrix": _s_cm,
        "signal_matrix_abs_unc": _s_cm_u,
        "background_integral_mask": _bg_integral_mask,
        "energy_axes_label": _energy_axes_label,
    }


def estimate_critical_rate_vs_energy(
    background_rate_in_onregion_vs_energy_per_s,
    onregion_over_offregion_ratio,
    observation_time_s,
    instrument_systematic_uncertainty,
    detection_threshold_std,
    method,
):
    bg_vs_energy_per_s = background_rate_in_onregion_vs_energy_per_s
    rate_per_s = np.nan * np.ones(shape=bg_vs_energy_per_s.shape)

    for ebin in range(len(bg_vs_energy_per_s)):
        if bg_vs_energy_per_s[ebin] > 0.0:
            rate_per_s[ebin] = integral_sensitivity.estimate_critical_rate(
                background_rate_in_onregion_per_s=bg_vs_energy_per_s[ebin],
                onregion_over_offregion_ratio=onregion_over_offregion_ratio,
                observation_time_s=observation_time_s,
                instrument_systematic_uncertainty=instrument_systematic_uncertainty,
                detection_threshold_std=detection_threshold_std,
                method=method,
            )
        else:
            rate_per_s[ebin] = float("nan")
    return rate_per_s


def next_containment_and_weight(
    accumulated_containment,
    bin_containment,
    target_containment,
):
    missing_containment = target_containment - accumulated_containment
    assert missing_containment > 0
    weight = np.min([missing_containment / bin_containment, 1])
    if weight == 1:
        return accumulated_containment + bin_containment, 1
    else:
        return target_containment, weight


def make_mask_for_energy_confusion_matrix_for_bell_spectrum(
    energy_confusion_matrix,
    containment=0.68
):
    # ax0 -> true
    # ax1 -> reco
    num_bins = energy_confusion_matrix.shape[0]
    M = energy_confusion_matrix
    mask = np.zeros(shape=(num_bins, num_bins))

    # estimate containment regions:
    for etrue in range(num_bins):
        if np.sum(M[etrue, :]) > 0.0:
            assert 0.99 < np.sum(M[etrue, :]) < 1.01

            accumulated_containment = 0.0
            ereco_best = np.argmax(M[etrue, :])

            accumulated_containment, weight = next_containment_and_weight(
                accumulated_containment=accumulated_containment,
                bin_containment=M[etrue, ereco_best],
                target_containment=containment
            )

            mask[etrue, ereco_best] = weight
            start = ereco_best - 1
            stop = ereco_best + 1
            while accumulated_containment < containment:
                if start > 0 and M[etrue, start] > 0:
                    accumulated_containment, w = next_containment_and_weight(
                        accumulated_containment=accumulated_containment,
                        bin_containment=M[etrue, start],
                        target_containment=containment
                    )
                    mask[etrue, start] = w
                    start -= 1
                if accumulated_containment == containment:
                    break

                if stop + 1 < num_bins and M[etrue, stop] > 0:
                    accumulated_containment, w = next_containment_and_weight(
                        accumulated_containment=accumulated_containment,
                        bin_containment=M[etrue, stop],
                        target_containment=containment
                    )
                    mask[etrue, stop] = w
                    stop += 1
                if accumulated_containment == containment:
                    break

                if start == 0 and stop + 1 == num_bins:
                    break
    return mask


def derive_migration_matrix_by_ax0(
    migration_matrix_counts,
    migration_matrix_counts_abs_unc,
    ax0_bin_widths,
):
    M = migration_matrix_counts
    M_au = migration_matrix_counts_abs_unc

    dMdE = np.zeros(M.shape)
    dMdE_au = np.zeros(M.shape)
    for i_ax0 in range(len(ax0_bin_widths)):
        _sum = np.sum(M[i_ax0, :])
        if _sum > 0.0:
            dMdE[i_ax0, :] = M[i_ax0, :] / ax0_bin_widths[:]
            dMdE_au[i_ax0, :] = M_au[i_ax0, :] / ax0_bin_widths[:]
    return dMdE, dMdE_au



def derive_all_energy_migration(energy_migration, energy_bin_width):
    SITES = list(energy_migration.keys())

    out = {}
    for sk in SITES:
        out[sk] = {}
        PARTICLES = list(energy_migration[sk].keys())
        for pk in PARTICLES:
            out[sk][pk] = {}
            M = energy_migration[sk][pk]["confusion_matrix"]
            dMdE = {}
            dMdE["ax0_key"] = M["ax0_key"]
            dMdE["ax1_key"] = M["ax1_key"]

            counts = M["counts"]
            counts_abs_unc = M["counts_abs_unc"]

            (
                dMdE["counts"], dMdE["counts_abs_unc"]
            ) = derive_migration_matrix_by_ax0(
                migration_matrix_counts=M["counts_normalized_on_ax0"],
                migration_matrix_counts_abs_unc=M["counts_normalized_on_ax0_abs_unc"],
                ax0_bin_widths=energy_bin_width,
            )
            out[sk][pk] = dMdE

    return out
