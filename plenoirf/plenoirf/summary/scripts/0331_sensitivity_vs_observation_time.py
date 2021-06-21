#!/usr/bin/python
import sys
import numpy as np
import plenoirf as irf
import spectral_energy_distribution_units as sed
from plenoirf.analysis import spectral_energy_distribution as sed_styles
import cosmic_fluxes
import os
import sebastians_matplotlib_addons as seb

argv = irf.summary.argv_since_py(sys.argv)
pa = irf.summary.paths_from_argv(argv)

irf_config = irf.summary.read_instrument_response_config(run_dir=pa["run_dir"])
sum_config = irf.summary.read_summary_config(summary_dir=pa["summary_dir"])

os.makedirs(pa["out_dir"], exist_ok=True)

diff_sensitivity = irf.json_numpy.read_tree(
    os.path.join(pa["summary_dir"], "0327_differential_sensitivity_plot")
)

energy_lower = sum_config["energy_binning"]["lower_edge_GeV"]
energy_upper = sum_config["energy_binning"]["upper_edge_GeV"]
energy_bin_edges = np.geomspace(
    energy_lower,
    energy_upper,
    sum_config["energy_binning"]["num_bins"]["trigger_acceptance_onregion"]
    + 1,
)
energy_bin_centers = irf.utils.bin_centers(energy_bin_edges)

fermi = irf.other_instruments.fermi_lat
cta = irf.other_instruments.cherenkov_telescope_array_south


# gamma-ray-flux of crab-nebula
# -----------------------------
crab_flux = cosmic_fluxes.read_crab_nebula_flux_from_resources()

internal_sed_style = sed_styles.PLENOIRF_SED_STYLE

output_sed_styles = {
    "portal": sed_styles.PLENOIRF_SED_STYLE,
    "science": sed_styles.SCIENCE_SED_STYLE,
    "fermi": sed_styles.FERMI_SED_STYLE,
    "cta": sed_styles.CHERENKOV_TELESCOPE_ARRAY_SED_STYLE,
}

oridx = 1

PIVOT_ENERGY_GEV = 25.0

enidx = irf.utils.find_closest_index_in_array_for_value(
        arr=energy_bin_edges,
        val=PIVOT_ENERGY_GEV,
        max_rel_error=0.25,
)

x_lim_s = np.array([1e0, 1e9])
e_lim_GeV = np.array([1e-1, 1e4])
y_lim_per_m2_per_s_per_GeV = np.array([1e3, 1e-16])


for site_key in irf_config["config"]["sites"]:

    observation_times = np.array(diff_sensitivity[
                site_key]["differential_sensitivity"]["observation_times"])

    components = []

    # Crab reference fluxes
    # ---------------------
    for i in range(4):
        scale_factor = np.power(10.0, (-1) * i)
        _flux = scale_factor * np.interp(
            x=PIVOT_ENERGY_GEV,
            xp=np.array(crab_flux["energy"]["values"]),
            fp=np.array(crab_flux["differential_flux"]["values"]),
        )
        com = {}
        com["observation_time"] = observation_times
        com["energy"] = PIVOT_ENERGY_GEV * np.ones(len(observation_times))
        com["differential_flux"] = _flux * np.ones(len(observation_times))
        com["label"] = "{:1.1e} Crab".format(scale_factor) if i == 0 else None
        com["color"] = "k"
        com["alpha"] = 1.0 / (1.0 + i)
        com["linestyle"] = "--"
        components.append(com.copy())


    # Fermi-LAT
    # ---------
    fermi_s_vs_t = irf.other_instruments.fermi_lat.sensitivity_vs_observation_time(
        energy_GeV=PIVOT_ENERGY_GEV
    )
    com = {}
    com["energy"] = PIVOT_ENERGY_GEV * np.ones(len(fermi_s_vs_t["observation_time"]["values"]))
    com["observation_time"] = np.array(fermi_s_vs_t["observation_time"]["values"])
    com["differential_flux"] = np.array(fermi_s_vs_t["differential_flux"]["values"])
    com["label"] = irf.other_instruments.fermi_lat.LABEL
    com["color"] = irf.other_instruments.fermi_lat.COLOR
    com["alpha"] = 1.0
    com["linestyle"] = "-"
    components.append(com)


    # CTA South
    # ---------
    cta_s_vs_t = irf.other_instruments.cherenkov_telescope_array_south.sensitivity_vs_observation_time(
        energy_GeV=PIVOT_ENERGY_GEV
    )
    com = {}
    com["energy"] = PIVOT_ENERGY_GEV * np.ones(len(cta_s_vs_t["observation_time"]["values"]))
    com["observation_time"] = np.array(cta_s_vs_t["observation_time"]["values"])
    com["differential_flux"] = np.array(cta_s_vs_t["differential_flux"]["values"])
    com["label"] = irf.other_instruments.cherenkov_telescope_array_south.LABEL
    com["color"] = irf.other_instruments.cherenkov_telescope_array_south.COLOR
    com["alpha"] = 1.0
    com["linestyle"] = "-"
    components.append(com)

    # Plenoscope
    # ----------

    portal_dFdE = np.array(diff_sensitivity[
                site_key]["differential_sensitivity"]["differential_flux"])
    com = {}
    com["observation_time"] = observation_times
    com["energy"] = PIVOT_ENERGY_GEV * np.ones(len(observation_times))
    com["differential_flux"] = portal_dFdE[enidx, oridx, :]
    com["label"] = "Portal"
    com["color"] = "black"
    com["alpha"] = 1.0
    com["linestyle"] = "-"
    components.append(com)

    for sed_style_key in output_sed_styles:
        sed_style = output_sed_styles[sed_style_key]

        fig = seb.figure(seb.FIGURE_16_9)
        ax = seb.add_axes(fig, (0.1, 0.1, 0.8, 0.8))

        for com in components:

            _energy, _dFdE = sed.convert_units_with_style(
                x=com["energy"],
                y=com["differential_flux"],
                input_style=internal_sed_style,
                target_style=sed_style,
            )
            _ = _energy
            ax.plot(
                com["observation_time"],
                _dFdE,
                label=com["label"],
                color=com["color"],
                alpha=com["alpha"],
                linestyle=com["linestyle"],
            )

        _E_lim, _dFdE_lim = sed.convert_units_with_style(
            x=e_lim_GeV,
            y=y_lim_per_m2_per_s_per_GeV,
            input_style=internal_sed_style,
            target_style=sed_style,
        )
        _ = _E_lim

        ax.set_xlim(x_lim_s)
        ax.set_ylim(np.sort(_dFdE_lim))
        ax.loglog()
        ax.legend(loc="best", fontsize=10)
        ax.set_xlabel("observation-time / s")
        ax.set_ylabel(sed_style["y_label"] + " / " + sed_style["y_unit"])
        fig.savefig(
            os.path.join(
                pa["out_dir"],
                "{:s}_sensitivity_vs_obseravtion_time_{:s}.jpg".format(
                    site_key, sed_style_key
                ),
            )
        )
        seb.close_figure(fig)