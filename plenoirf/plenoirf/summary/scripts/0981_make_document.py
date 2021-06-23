#!/usr/bin/python
import sys
import numpy as np
import plenoirf as irf
import sparse_numeric_table as spt
import os
import sebastians_matplotlib_addons as seb
import pylatex as ltx
import warnings
import json
import yaml


argv = irf.summary.argv_since_py(sys.argv)
pa = irf.summary.paths_from_argv(argv)

irf_config = irf.summary.read_instrument_response_config(run_dir=pa["run_dir"])
sum_config = irf.summary.read_summary_config(summary_dir=pa["summary_dir"])


production_dirname = irf.summary.production_name_from_run_dir(pa["run_dir"])
fname = os.path.join(pa["summary_dir"], "{:s}_ltx".format(production_dirname))

site_key = "namibia"
SED_STYLE_KEY = "portal"

geometry_options = {
    "paperwidth": "18cm",
    "paperheight": "32cm",
    "head": "0cm",
    "left": "2cm",
    "right": "2cm",
    "top": "0cm",
    "bottom": "2cm",
    "includehead": True,
    "includefoot": True,
}

def read_json_but_forgive(path, default={}):
    try:
        with open(path, "rt") as f:
            out = json.loads(f.read())
    except Exception as e:
        print(e)
        warnings.warn("Failed to load '{:s}'".format(path))
        out = default
    return out

production_provenance = read_json_but_forgive(
    path=os.path.join(pa["run_dir"], "event_table", "provenance.json")
)
analysis_provenance = read_json_but_forgive(
    path=os.path.join(pa["summary_dir"], "provenance.json")
)

def make_basic_version_str(
    production_dirname,
    production_provenance,
    analysis_provenance
):
    pp = production_provenance
    ap = analysis_provenance

    ver = ""
    ver += "Production\n"
    ver += "    dirname: {:s}\n".format(production_dirname)
    ver += "    date: {:s}\n".format(pp["time"]["iso"][0:16])
    ver += "    git-commit: {:s}\n".format(pp["starter_kit"]["git"]["commit"][0:9])
    ver += "    hostname: {:s}\n".format(pp["hostname"])
    ver += "Analysis\n"
    ver += "    date: {:s}\n".format(ap["time"]["iso"][0:16])
    ver += "    git-commit:   {:s}\n".format(ap["starter_kit"]["git"]["commit"][0:9])
    ver += "    hostname: {:s}\n".format(ap["hostname"])
    return ver


def pretty_str(dictionary):
    return yaml.dump(dictionary, default_flow_style=False)


def ppath(*args):
    p1 = os.path.join(*args)
    p2 = os.path.normpath(p1)
    return os.path.abspath(p2)

energy_resolution_figure_path = ppath(
    pa["summary_dir"],
    "0066_energy_estimate_quality",
    site_key + "_gamma_resolution.jpg"
)

angular_resolution_figure_path = ppath(
    pa["summary_dir"],
    "0230_point_spread_function",
    site_key + "_gamma.jpg"
)

differential_sensitivity_figure_path = ppath(
    pa["summary_dir"],
    "0330_differential_sensitivity_plot",
    site_key + "_differential_sensitivity_sed-style-{:s}.jpg".format(SED_STYLE_KEY)
)

sens_vs_observation_time_figure_path = ppath(
    pa["summary_dir"],
    "0331_sensitivity_vs_observation_time",
    site_key + "_sensitivity_vs_obseravtion_time_{:s}.jpg".format(SED_STYLE_KEY)
)

ratescan_figure_path = ppath(
    pa["summary_dir"],
    "0130_trigger_ratescan_plot",
    site_key + "_ratescan.jpg"
)

diff_trigger_rates_figure_path = ppath(
    pa["summary_dir"],
    "0106_trigger_rates_for_cosmic_particles_plot",
    site_key + "_differential_trigger_rate.jpg"
)

basic_version_str = make_basic_version_str(
    production_dirname=production_dirname,
    production_provenance=production_provenance,
    analysis_provenance=analysis_provenance
)

doc = ltx.Document(
    default_filepath=fname,
    documentclass="article",
    document_options=[],
    geometry_options=geometry_options,
    font_size="small",
    page_numbers=True,
)

def Verbatim(string):
    return r"\begin{verbatim}" + r"{:s}".format(string) + r"\end{verbatim}"

doc.preamble.append(ltx.utils.NoEscape(r"\usepackage{multicol}"))
doc.preamble.append(ltx.utils.NoEscape(r"\usepackage{lipsum}"))
doc.preamble.append(ltx.utils.NoEscape(r"\usepackage{float}"))
doc.preamble.append(ltx.utils.NoEscape(r"\usepackage{verbatim}"))

doc.preamble.append(ltx.Command('title',  ltx.utils.NoEscape(r'Simulating the Performance of the 71\,m Portal Cherenkov-Plenoscope')))
doc.preamble.append(ltx.Command('author', 'Sebastian A. Mueller'))
doc.preamble.append(ltx.Command('date', ""))

doc.append(ltx.utils.NoEscape(r'\maketitle'))
doc.append(ltx.utils.NoEscape(r"\begin{multicols}{2}"))

"""
doc.change_length(r"\TPHorizModule", "1cm")
doc.change_length(r"\TPVertModule", "1cm")
with doc.create(ltx.TextBlock(width=10, horizontal_pos=0, vertical_pos=0)) as blk:
    blk.append('Plenoscope')
"""

with doc.create(ltx.Section('Version', numbering=False)):
    doc.append(ltx.utils.NoEscape(Verbatim(basic_version_str)))

with doc.create(ltx.Section('Performance', numbering=False)):
    with doc.create(ltx.Figure(position='H')) as fig:
        fig.add_image(
            differential_sensitivity_figure_path,
            width=ltx.utils.NoEscape(r'1.0\linewidth')
        )
        fig.add_caption("Differential sensitivity.")

    with doc.create(ltx.Figure(position='H')) as fig:
        fig.add_image(
            sens_vs_observation_time_figure_path,
            width=ltx.utils.NoEscape(r'1.0\linewidth')
        )
        fig.add_caption(ltx.utils.NoEscape("Sensitivity vs. observation-time at 25\,GeV."))

    with doc.create(ltx.Figure(position='H')) as fig:
        fig.add_image(
            angular_resolution_figure_path,
            width=ltx.utils.NoEscape(r'1.0\linewidth')
        )
        fig.add_caption("Angular resolution.")

    with doc.create(ltx.Figure(position='H')) as fig:
        fig.add_image(
            energy_resolution_figure_path,
            width=ltx.utils.NoEscape(r'1.0\linewidth')
        )
        fig.add_caption("Energy resolution.")


doc.append(ltx.utils.NoEscape(r"\columnbreak"))

with doc.create(ltx.Section('Trigger', numbering=False)):

    with doc.create(ltx.Figure(position='H')) as fig:
        fig.add_image(
            ratescan_figure_path,
            width=ltx.utils.NoEscape(r'1.0\linewidth')
        )
        fig.add_caption("Ratescan.")

    with doc.create(ltx.Figure(position='H')) as fig:
        fig.add_image(
            diff_trigger_rates_figure_path,
            width=ltx.utils.NoEscape(r'1.0\linewidth')
        )
        fig.add_caption("Trigger-rate on {:s}".format(sum_config['gamma_ray_reference_source']['name_3fgl']))

with doc.create(ltx.Section('Site: ' + site_key, numbering=False)):
    doc.append(ltx.utils.NoEscape(Verbatim(pretty_str(irf_config["config"]["sites"][site_key]))))

doc.append(ltx.utils.NoEscape(r"\end{multicols}{2}"))
doc.generate_pdf(clean_tex=False)
