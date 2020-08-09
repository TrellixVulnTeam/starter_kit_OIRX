#!/usr/bin/python
import sys
import numpy as np
import plenoirf as irf
import spectral_energy_distribution_units as sed
from plenoirf.analysis import spectral_energy_distribution as sed_styles
import cosmic_fluxes
import os
import gamma_limits_sensitivity as gls
import scipy

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

argv = irf.summary.argv_since_py(sys.argv)
pa = irf.summary.paths_from_argv(argv)

irf_config = irf.summary.read_instrument_response_config(run_dir=pa['run_dir'])
sum_config = irf.summary.read_summary_config(summary_dir=pa['summary_dir'])

os.makedirs(pa['out_dir'], exist_ok=True)

'''
In Sebastian's phd-thesis, the trigger-rate for gamma-rays was estiamted by
taking the overall acceptance for gamma-rays from a  point-source and
multiplying it with the PSF-containment-factor of 0.68.

Cosmic-ray background only included protons and leptons, but nu Helium.
The trigger-rate for cosmic-rays was based on the acceptance over the entire
field-of-view and multiplied by the ratio of the entire field-of-view's
solid angle over the onregions's solid angle.

The psf-enclosure-radius was only 0.31 deg as there was no magnetic deflection.
'''

PHD_PSF_RADIUS_DEG = 0.31
PHD_PSF_CONTAINMENT_FACTOR = 0.68
PHD_COSMIC_RAY_KEYS = ['electron', 'proton']

PHD_DETECTION_THRESHOLD_STD = 5.0
PHD_ON_OVER_OFF_RATIO = 1.0/5.0
PHD_OBSERVATION_TIME_S = 50*3600

all_fov_acceptance = irf.json_numpy.read_tree(
    os.path.join(
        pa['summary_dir'],
        "0100_trigger_acceptance_for_cosmic_particles"
    )
)

all_fov_rates = irf.json_numpy.read_tree(
    os.path.join(
        pa['summary_dir'],
        "0105_trigger_rates_for_cosmic_particles"
    )
)

trigger_thresholds = np.array(sum_config['trigger']['ratescan_thresholds_pe'])
analysis_trigger_threshold = sum_config['trigger']['threshold_pe']
trigger_threshold_key = np.where(
    trigger_thresholds == analysis_trigger_threshold
)[0][0]

cosmic_ray_keys = list(irf_config['config']['particles'].keys())
cosmic_ray_keys.remove('gamma')

fermi_broadband = irf.analysis.fermi_lat_integral_spectral_exclusion_zone()
assert fermi_broadband[
    'energy']['unit_tex'] == "GeV"
assert fermi_broadband[
    'differential_flux']['unit_tex'] == "m$^{-2}$ s$^{-1}$ GeV$^{-1}$"

fig_16_by_9 = sum_config['plot']['16_by_9']
num_isez_energy_supports = 7

# gamma-ray-flux of crab-nebula
# -----------------------------
crab_flux = cosmic_fluxes.read_crab_nebula_flux_from_resources()

internal_sed_style = sed_styles.PLENOIRF_SED_STYLE

output_sed_styles = {
    'plenoirf': sed_styles.PLENOIRF_SED_STYLE,
    'science': sed_styles.SCIENCE_SED_STYLE,
    'fermi': sed_styles.FERMI_SED_STYLE,
}

# background rates
# ----------------
FOV_RADIUS_DEG = 0.5*irf_config[
    'light_field_sensor_geometry'][
    'max_FoV_diameter_deg']
onregion_over_all_fov_ratio = PHD_PSF_RADIUS_DEG**2 / FOV_RADIUS_DEG**2

cosmic_ray_rate_onregion = {}
electron_rate_onregion = {}
for site_key in irf_config['config']['sites']:

    electron_rate_onregion[site_key] = all_fov_rates[
            site_key][
            'electron'][
            'integral_rate'][
            'mean'][
            trigger_threshold_key]*onregion_over_all_fov_ratio

    cosmic_ray_rate_onregion[site_key] = 0
    for cosmic_ray_key in PHD_COSMIC_RAY_KEYS:
        cosmic_ray_rate_onregion[site_key] += all_fov_rates[
            site_key][
            cosmic_ray_key][
            'integral_rate'][
            'mean'][
            trigger_threshold_key]*onregion_over_all_fov_ratio

x_lim_GeV = np.array([1e-1, 1e4])
y_lim_per_m2_per_s_per_GeV = np.array([1e-0, 1e-16])

for site_key in irf_config['config']['sites']:

    components = []

    # Crab reference fluxes
    # ---------------------
    for i in range(4):
        com = {}
        scale_factor = np.power(10., (-1)*i)
        com['energy'] = np.array(crab_flux['energy']['values'])
        com['differential_flux'] = scale_factor*np.array(
            crab_flux['differential_flux']['values']
        )
        com['label'] = '{:.3f} Crab'.format(scale_factor)
        com['color'] = 'k'
        com['alpha'] = 1./(1.+i)
        com['linestyle'] = '--'
        components.append(com.copy())

    # Fermi-LAT broadband
    # -------------------
    com = {}
    com['energy'] = np.array(fermi_broadband['energy']['values'])
    com['differential_flux'] = np.array(
        fermi_broadband['differential_flux']['values'])
    com['label'] = 'Fermi-LAT 10 y'
    com['color'] = 'k'
    com['alpha'] = 1.0
    com['linestyle'] = '-'
    components.append(com)

    # plenoscope
    # ----------
    all_fov_gamma_effective_area_m2 = np.array(all_fov_acceptance[
        site_key][
        'gamma'][
        'point'][
        'mean'][
        trigger_threshold_key]
    )*PHD_PSF_CONTAINMENT_FACTOR

    all_fov_energy_bin_centers = irf.summary.bin_centers(
        bin_edges=np.array(all_fov_acceptance[
            site_key][
            'gamma'][
            'point'][
            'energy_bin_edges_GeV'])
    )

    (
        isez_energy_GeV,
        isez_differential_flux_per_GeV_per_m2_per_s
    ) = irf.analysis.estimate_integral_spectral_exclusion_zone(
        gamma_effective_area_m2=all_fov_gamma_effective_area_m2,
        energy_bin_centers_GeV=all_fov_energy_bin_centers,
        background_rate_in_onregion_per_s=cosmic_ray_rate_onregion[site_key],
        onregion_over_offregion_ratio=PHD_ON_OVER_OFF_RATIO,
        observation_time_s=PHD_OBSERVATION_TIME_S,
        num_points=num_isez_energy_supports,
        std_threshold=PHD_DETECTION_THRESHOLD_STD,
    )
    com = {}
    com['energy'] = isez_energy_GeV
    com['differential_flux'] = isez_differential_flux_per_GeV_per_m2_per_s
    com['label'] = 'Portal {:2.0f} h, trigger'.format(
        PHD_OBSERVATION_TIME_S/3600.)
    com['color'] = 'r'
    com['alpha'] = 1.0
    com['linestyle'] = '-'
    components.append(com)

    # plenoscope no hadrons
    # ---------------------
    (
        e_isez_energy_GeV,
        e_isez_differential_flux_per_GeV_per_m2_per_s
    ) = irf.analysis.estimate_integral_spectral_exclusion_zone(
        gamma_effective_area_m2=all_fov_gamma_effective_area_m2,
        energy_bin_centers_GeV=all_fov_energy_bin_centers,
        background_rate_in_onregion_per_s=electron_rate_onregion[site_key],
        onregion_over_offregion_ratio=PHD_ON_OVER_OFF_RATIO,
        observation_time_s=PHD_OBSERVATION_TIME_S,
        num_points=num_isez_energy_supports,
        std_threshold=PHD_DETECTION_THRESHOLD_STD,
    )
    com = {}
    com['energy'] = e_isez_energy_GeV
    com['differential_flux'] = e_isez_differential_flux_per_GeV_per_m2_per_s
    com['label'] = 'Portal {:2.0f} h, trigger, rejecting all hadrons'.format(
            PHD_OBSERVATION_TIME_S/3600.)
    com['color'] = 'r'
    com['alpha'] = 0.5
    com['linestyle'] = '--'
    components.append(com)

    for sed_style_key in output_sed_styles:
        sed_style = output_sed_styles[sed_style_key]

        fig = irf.summary.figure.figure(fig_16_by_9)
        ax = fig.add_axes((.1, .1, .8, .8))
        ax.set_title(
            "Analysis as in Sebastian's phd-thesis.\n"
            "Only protons and electrons, "
            "fix psf-radius "
            "{:.2f}$^\\circ$, fix psf-containment {:.2f}.".format(
                PHD_PSF_RADIUS_DEG,
                PHD_PSF_CONTAINMENT_FACTOR
            )
        )

        for com in components:

            _energy, _dFdE = sed.convert_units_with_style(
                x=com['energy'],
                y=com['differential_flux'],
                input_style=internal_sed_style,
                target_style=sed_style,
            )
            ax.plot(
                _energy,
                _dFdE,
                label=com['label'],
                color=com['color'],
                alpha=com['alpha'],
                linestyle=com['linestyle'],
            )

        _x_lim, _y_lim = sed.convert_units_with_style(
            x=x_lim_GeV,
            y=y_lim_per_m2_per_s_per_GeV,
            input_style=internal_sed_style,
            target_style=sed_style,
        )

        ax.set_xlim(np.sort(_x_lim))
        ax.set_ylim(np.sort(_y_lim))
        ax.loglog()
        ax.legend(loc='best', fontsize=10)
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.grid(color='k', linestyle='-', linewidth=0.66, alpha=0.1)
        ax.set_xlabel(sed_style['x_label']+" / "+sed_style['x_unit'])
        ax.set_ylabel(sed_style['y_label']+" / "+sed_style['y_unit'])
        fig.savefig(
            os.path.join(
                pa['out_dir'],
                '{:s}_integral_spectral_exclusion_zone_style_{:s}.jpg'.format(
                    site_key,
                    sed_style_key
                )
            )
        )
        plt.close(fig)