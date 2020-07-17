#!/usr/bin/python
import sys
import numpy as np
import plenoirf as irf
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


argv = irf.summary.argv_since_py(sys.argv)
pa = irf.summary.paths_from_argv(argv)

irf_config = irf.summary.read_instrument_response_config(run_dir=pa['run_dir'])
sum_config = irf.summary.read_summary_config(summary_dir=pa['summary_dir'])

os.makedirs(pa['out_dir'], exist_ok=True)

energy_lower = sum_config['energy_binning']['lower_edge_GeV']
energy_upper = sum_config['energy_binning']['upper_edge_GeV']
fine_energy_bin_edges = np.geomspace(
    sum_config['energy_binning']['lower_edge_GeV'],
    sum_config['energy_binning']['upper_edge_GeV'],
    sum_config['energy_binning']['num_bins']['interpolation'] + 1
)
fine_energy_bin_centers = irf.summary.bin_centers(fine_energy_bin_edges)


fig_16_by_9 = sum_config['plot']['16_by_9']
particle_colors = sum_config['plot']['particle_colors']

# cosmic-ray-flux
# ----------------
airshower_fluxes = irf.summary.read_airshower_differential_flux(
    summary_dir=pa['summary_dir'],
    energy_bin_centers=fine_energy_bin_centers,
    sites=irf_config['config']['sites'],
    geomagnetic_cutoff_fraction=sum_config[
        'airshower_flux'][
        'fraction_of_flux_below_geomagnetic_cutoff'],
)

for site_key in irf_config['config']['sites']:

    fig = irf.summary.figure.figure(fig_16_by_9)
    ax = fig.add_axes((.1, .1, .8, .8))
    for particle_key in airshower_fluxes[site_key]:
        ax.plot(
            fine_energy_bin_centers,
            airshower_fluxes[site_key][particle_key]['differential_flux'],
            label=particle_key,
            color=particle_colors[particle_key],
        )
    ax.set_xlabel('energy / GeV')
    ax.set_ylabel(
        'differential flux of airshowers / ' +
        'm$^{-2}$ s$^{-1}$ sr$^{-1}$ (GeV)$^{-1}$'
    )
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.grid(color='k', linestyle='-', linewidth=0.66, alpha=0.1)
    ax.loglog()
    ax.set_xlim([energy_lower, energy_upper])
    ax.legend()
    fig.savefig(
        os.path.join(
            pa['out_dir'],
            '{:s}_airshower_differential_flux.jpg'.format(site_key)
        )
    )
    plt.close(fig)