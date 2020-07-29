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

acceptance = {}
acceptance['grid'] = irf.json_numpy.read_tree(
    os.path.join(
        pa['summary_dir'],
        "0100_trigger_acceptance_for_cosmic_particles"
    )
)
acceptance['scatter'] = irf.json_numpy.read_tree(
    os.path.join(
        pa['summary_dir'],
        "0110_trigger_acceptance_for_cosmic_particles_reproducing_scatter_algorithm"
    )
)

energy_lower = sum_config['energy_binning']['lower_edge_GeV']
energy_upper = sum_config['energy_binning']['upper_edge_GeV']
energy_bin_edges = np.geomspace(
    energy_lower,
    energy_upper,
    sum_config['energy_binning']['num_bins']['trigger_acceptance'] + 1
)

trigger_thresholds = np.array(sum_config['trigger']['ratescan_thresholds_pe'])
analysis_trigger_threshold = sum_config['trigger']['threshold_pe']
tt = np.where(trigger_thresholds == analysis_trigger_threshold)[0][0]

sources = {
    'diffuse': {
        'label': 'area $\\times$ solid angle',
        'unit': "m$^{2}$ sr",
        'limits': [1e-1, 1e5],
    },
    'point': {
        'label': 'area',
        'unit': "m$^{2}$",
        'limits': [1e1, 1e6],
    }
}

algorithm_styles = {
    "grid": {"alpha": 0.1},
    "scatter": {"alpha": 0.5}
}

fig_16_by_9 = sum_config['plot']['16_by_9']
particle_colors = sum_config['plot']['particle_colors']

for site_key in irf_config['config']['sites']:
    for particle_key in irf_config['config']['particles']:
        for source_key in sources:

            fig = irf.summary.figure.figure(fig_16_by_9)
            ax = fig.add_axes((.1, .1, .8, .8))

            for algorithm_key in acceptance:

                Q = np.array(
                    acceptance[
                        algorithm_key][
                        site_key][
                        particle_key][
                        source_key][
                        'mean'][
                        tt]
                )
                delta_Q = np.array(
                    acceptance[
                        algorithm_key][
                        site_key][
                        particle_key][
                        source_key][
                        'relative_uncertainty'][
                        tt]
                )
                Q_lower = (1 - delta_Q)*Q
                Q_upper = (1 + delta_Q)*Q

                color = particle_colors[particle_key]
                if algorithm_key == 'grid':
                    color = 'k'
                irf.summary.figure.ax_add_hist(
                    ax=ax,
                    bin_edges=energy_bin_edges,
                    bincounts=Q,
                    linestyle=color,
                    bincounts_upper=Q_upper,
                    bincounts_lower=Q_lower,
                    face_color=color,
                    face_alpha=algorithm_styles[algorithm_key]['alpha'],
                )

            ax.set_xlabel('energy / GeV')
            ax.set_ylabel('{:s} / {:s}'.format(
                    sources[source_key]['label'],
                    sources[source_key]['unit']
                )
            )
            ax.spines['top'].set_color('none')
            ax.spines['right'].set_color('none')
            ax.set_ylim(sources[source_key]['limits'])
            ax.grid(color='k', linestyle='-', linewidth=0.66, alpha=0.1)
            ax.loglog()
            ax.set_xlim([energy_bin_edges[0], energy_bin_edges[-1]])

            fig.savefig(
                os.path.join(
                    pa['out_dir'],
                    '{:s}_{:s}_{:s}.jpg'.format(
                        site_key,
                        particle_key,
                        source_key,
                    )
                )
            )
            plt.close(fig)