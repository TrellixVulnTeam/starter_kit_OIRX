import numpy as np
import lima1983analysis
import binning_utils


def _power_law(energy, flux_density, spectral_index, pivot_energy):
    """
    power-law:
    f(energy) = flux_density * (energy/pivot_energy) ** spectral_index
    """
    return flux_density * (energy / pivot_energy) ** (spectral_index)


def estimate_signal_rate_per_s_for_power_law(
    effective_area_m2,
    effective_area_energy_bin_centers_GeV,
    effective_area_energy_bin_width_GeV,
    power_law_flux_density_per_m2_per_GeV_per_s,
    power_law_spectral_index,
    power_law_pivot_energy_GeV,
):
    """
    Estimate the rate of signal-counts in the on-region $R_S$ given the
    emission's energy-spectrum is a power-law.
    power-law:
    f(energy) = flux_density * (energy/pivot_energy) ** spectral_index

    Parameters
    ----------
    effective_area_m2 : list of N floats
        The effective area where signal is collected in the on-region.
    effective_area_energy_bin_centers_GeV : list of N floats
        The centers of the energy-bins used for the effective area.
    effective_area_energy_bin_width_GeV : list of N floats
        The widths of the energy-bins used for the effective area.
    power_law_flux_density_per_m2_per_GeV_per_s : float
        The power-law's flux-density.
    power_law_spectral_index : float
        The power-law's spectral-index.
    power_law_pivot_energy_GeV : float
        The power-law's pivot-energy.

    Returns
    -------
    The signal-rate $R_S$ : float
    """

    differential_flux_per_m2_per_s_per_GeV = _power_law(
        energy=effective_area_energy_bin_centers_GeV,
        flux_density=power_law_flux_density_per_m2_per_GeV_per_s,
        spectral_index=power_law_spectral_index,
        pivot_energy=power_law_pivot_energy_GeV,
    )

    differential_rate_per_s_per_GeV = (
        differential_flux_per_m2_per_s_per_GeV * effective_area_m2
    )

    rate_per_s = np.sum(
        differential_rate_per_s_per_GeV * effective_area_energy_bin_width_GeV
    )
    return rate_per_s


def _relative_ratio(a, b):
    return np.abs(a - b) / (0.5 * (a + b))


def estimate_critical_power_law_flux_densities(
    effective_area_m2,
    effective_area_energy_bin_edges_GeV,
    critical_rate_per_s,
    power_law_spectral_indices,
    power_law_pivot_energy_GeV=1.0,
    margin=1e-2,
    upper_flux_density_per_m2_per_GeV_per_s=1e6,
    max_num_iterations=10000,
):
    """
    Estimates the flux-density of the critical power-laws which are still
    detectable.

    power-law:
    f(energy) = flux_density * (energy/pivot_energy) ** spectral_index

    Parameters
    ----------
    effective_area_m2 : list of N floats
        The effective area where signal is collected in the on-region.
    effective_area_energy_bin_edges_GeV : list of (N+1) floats
        The edges of the energy-bins used for the effective area.
    critical_rate_per_s : float
        The critical rate of signal in the on-region which is required
        to claim a detection.
    power_law_spectral_indices : list of floats
        A list of the power-law's spectral-indices.
    power_law_pivot_energy_GeV : float
        Same for all power-laws.
    margin : float
        Stopping-criteria for iterative search of flux-density. When the
        relative ratio of the critical_rate_per_s and the acual rate_per_s
        caused by a particular power-law is below this margin, the search
        is complete.
    upper_flux_density_per_m2_per_GeV_per_s : float
        Starting point for iterative search of flux-density. This should be
        larger than the expected flux.
    max_num_iterations : int
        Stop the iterative search of flux-density in any case after
        this many iterations.

    Returns
    -------
    power_law_flux_densities : list of floats
    """
    assert (
        len(effective_area_energy_bin_edges_GeV) == len(effective_area_m2) + 1
    )
    assert np.all(effective_area_m2 >= 0.0)
    assert np.all(effective_area_energy_bin_edges_GeV > 0.0)
    assert np.all(np.gradient(effective_area_energy_bin_edges_GeV) > 0.0)

    assert critical_rate_per_s > 0.0

    assert power_law_pivot_energy_GeV > 0.0
    assert margin > 0.0
    assert upper_flux_density_per_m2_per_GeV_per_s > 0.0
    assert max_num_iterations > 0

    effective_area_energy_bin_centers_GeV = binning_utils.centers(
        bin_edges=effective_area_energy_bin_edges_GeV,
    )
    effective_area_energy_bin_width_GeV = binning_utils.widths(
        bin_edges=effective_area_energy_bin_edges_GeV,
    )

    power_law_flux_densities = []

    for i, power_law_spectral_index in enumerate(power_law_spectral_indices):

        flux_dens = float(upper_flux_density_per_m2_per_GeV_per_s)

        iteration = 0
        while True:
            assert iteration < max_num_iterations

            rate_per_s = estimate_signal_rate_per_s_for_power_law(
                effective_area_m2=effective_area_m2,
                effective_area_energy_bin_centers_GeV=effective_area_energy_bin_centers_GeV,
                effective_area_energy_bin_width_GeV=effective_area_energy_bin_width_GeV,
                power_law_flux_density_per_m2_per_GeV_per_s=flux_dens,
                power_law_spectral_index=power_law_spectral_index,
                power_law_pivot_energy_GeV=power_law_pivot_energy_GeV,
            )

            ratio = _relative_ratio(rate_per_s, critical_rate_per_s)

            if ratio < margin:
                break

            rr = ratio / 3
            if rate_per_s > critical_rate_per_s:
                flux_dens *= 1 - rr
            else:
                flux_dens *= 1 + rr

            iteration += 1

        power_law_flux_densities.append(float(flux_dens))
    return power_law_flux_densities
