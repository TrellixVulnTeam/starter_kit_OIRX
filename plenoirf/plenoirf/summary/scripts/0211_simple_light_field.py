#!/usr/bin/python
import sys
import numpy as np
import plenoirf as irf
import sparse_numeric_table as spt
import airshower_template_generator as atg
import os
import pandas
import plenopy as pl
import glob
import multiprocessing


PARALLEL = True

argv = irf.summary.argv_since_py(sys.argv)
pa = irf.summary.paths_from_argv(argv)

irf_config = irf.summary.read_instrument_response_config(run_dir=pa["run_dir"])
sum_config = irf.summary.read_summary_config(summary_dir=pa["summary_dir"])

lfg = pl.LightFieldGeometry(
    os.path.join(pa["run_dir"], "light_field_geometry")
)

loph_chunk_base_dir = os.path.join(
    pa["summary_dir"],
    "0068_prepare_loph_passed_trigger_and_quality"
)

def make_jobs(loph_chunk_dir, quality, site_key, particle_key):
    chunk_paths = glob.glob(os.path.join(loph_chunk_dir, "*.tar"))
    jobs = []
    for chunk_path in chunk_paths:
        job = {}
        job["loph_path"] = str(chunk_path)
        job["quality"] = dict(quality)
        job["site_key"] = str(site_key)
        job["particle_key"] = str(particle_key)
        jobs.append(job)
    return jobs


def run_job(job):
    run = pl.photon_stream.loph.LopfTarReader(job["loph_path"])

    result = []
    for event in run:
        airshower_id, loph_record = event
        print("airshower_id", airshower_id)

        slf = atg.model.SplitLightField(
            loph_record=loph_record, light_field_geometry=lfg
        )

        img = atg.model.make_image(split_light_field=slf)
        reco_cx_deg, reco_cy_deg = atg.model.argmax_image_cx_cy_deg(image=img)

        reco = {
            spt.IDX: airshower_id,
            "cx": np.deg2rad(reco_cx_deg),
            "cy": np.deg2rad(reco_cy_deg),
            "x": float("nan"),
            "y": float("nan"),
        }
        result.append(reco)

    return result


for sk in irf_config["config"]["sites"]:
    for pk in ["gamma"]:  # irf_config["config"]["particles"]:

        site_particle_dir = os.path.join(pa["out_dir"], sk, pk)
        os.makedirs(site_particle_dir, exist_ok=True)

        print("make jobs")
        jobs = make_jobs(
            loph_chunk_dir=os.path.join(loph_chunk_base_dir, sk, pk, "chunks"),
            quality=sum_config["quality"],
            site_key=sk,
            particle_key=pk,
        )

        print("run jobs")
        if PARALLEL:
            print("PARALLEL")
            pool = multiprocessing.Pool(8)
            _results = pool.map(run_job, jobs)
        else:
            print("SEQUENTIEL")
            _results = []
            for job in jobs:
                print("job", job)
                _results.append(run_job(job))
        results = []
        for chunk in _results:
            for r in chunk:
                results.append(r)

        reco_df = pandas.DataFrame(results)
        reco_di = reco_df.to_dict(orient="list")

        irf.json_numpy.write(
            path=os.path.join(site_particle_dir, "reco" + ".json"),
            out_dict=reco_di,
        )
