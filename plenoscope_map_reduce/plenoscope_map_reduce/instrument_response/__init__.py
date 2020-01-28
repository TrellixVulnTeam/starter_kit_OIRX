from . import random
from . import table
from . import grid
from . import merlict
from . import logging
from . import query

import numpy as np
import os
from os import path as op
import shutil
import errno
import tempfile
import json
import tarfile
import io
import datetime
import subprocess
import PIL
import pandas as pd
import corsika_primary_wrapper as cpw
import plenopy as pl
import gzip

"""
I think I have an efficient and very simple algorithm

0) Pick a threshold photon number T1 where trigger curve starts rising
(for a given type of primary)

1) Generate shower such that particle direction hits ground at 0,0;
shower direction spread over large solid angle Omega (energy-dep.)
(for charged particles)
{could also pick (0,0) at some height, but I believe for z=0 the photon
scatter is smallest}

2) Divide ground in grid of spacing = mirror diameter; could e.g. without
too much trouble use up to M x M = 1000 x 1000 grid cells = 70 x 70 km^2;
grid area is A, grid centered on (0,0)

3) Reset photon counter for each cell

3) For each shower, shift grid randomly in x,y by 1/2 mirror diameter

4) Loop over shower photons
   4.1) reject photon if angle outside FOV
   4.2) for each photon, calculate grid cell index ix, iy
        {easy since square grid}
   4.3) calculate distance of photon from cell center;
        keep photon if distance < R_Mirror
   4.4) increment photon counter for cell
   4.5) optionally save photon in a buffer

5) Loop over grid cells
   5.1) count cells with photons > T1: N_1
   5.2) using trigger curve for given particle type;
        calculate trigger prob. for (real) trigger
        and randomly reject events: keep N_2
        {or simply use a 2nd threshold where trigger prob=0.5}
   5.3) Increment event counters by N_1, N_2
        Increment error counters by N_1^2, N_2^2

6) For detailed simulation, optionally output photons for
   few randomly selected T1-triggered cells
   (up to 10 should be fine, given that
   probably only one of 10 triggers the detailed simulation)

7) Toy effective area (x solid angle): (N_1 event counter/M^2/Nevent)*A*Omega
   error = sqrt(error counter) ...
   Somewhat better effective area: N_2 event counter ...
   Final eff. area: N1_eff area x fraction of events kept in detailed sim.

Cheers
Werner



Coordinate system
=================
                                  | z
                                  |                               starting pos.
                                  |                                  ___---O
                                  |                            ___---    / |
                                  |                      ___---     n  /   |
                                  |                ___---         io /     |
                                  |          ___---             ct /       |
                                  |    ___---                 re /         |
              starting altitude __|_---                     di /           |
                                  |                       y- /             |
                                  | _-------__          ar /               |
                                  |-    th    |_      im /                 |
                                  |   ni        |_  pr /                   |
                                  | ze            |  /                     |
                                  |               |/                       |
                      ____________|______________/________________________ |
                     /            |            /            /            / |
                    /            /|          //            /            /  |
                  3/            / |        / /            /            /   |
                  /            /  |      /  /            /            /    |
                 /____________/___|____/___/____________/____________/     |
                /            /    |  /    /            /            /      |
obs. level     /            /     |/     /    grid    /            /       |
altitude -  -2/-  -  -  -  /  -  -X-----/  <-shift y /            /        |
             /            /      /|    /            /            /         |
            /____________/______/_____/____________/____________/          |
           /            /     -|  |  /            /            /           |
          /            /      /   | /            /            /            |
        1/            /  grid     |/            /            /             |
        /            /  shift x   /            /            /              |
       /____________/____________/____________/____________/               |
      /            /            / |          /            /                |
     /            /            /  |         /            /                 |
   0/            /            /   |        /            /                  |
   /            /            /    |       /            /                   |
  /____________/____________/____________/____________/                    |
        0            1           2|             3                          |
                                  |                                  ___---O
                                  |                            ___---
                                  |                      ___--- |
                                  |                ___---        |
                                  |          ___---               |
                                  |    ___---       azimuth       |
                sea leavel z=0    |_---__________________________/______ x
                                  /
                                 /
                                /
                               /
                              /
                             /
                            /
                           /
                          /
                         /
                        / y
Drawn by Sebastian
"""


def absjoin(*args):
    return op.abspath(op.join(*args))


def date_dict_now():
    dt = datetime.datetime.now()
    out = {}
    for key in ["year", "month", "day", "hour", "minute", "second"]:
        out[key] = int(dt.__getattribute__(key))
    return out


CORSIKA_PRIMARY_PATH = absjoin(
        "build",
        "corsika",
        "modified",
        "corsika-75600",
        "run",
        "corsika75600Linux_QGSII_urqmd")

MERLICT_PLENOSCOPE_PROPAGATOR_PATH = absjoin(
        "build",
        "merlict",
        "merlict-plenoscope-propagation")

LIGHT_FIELD_GEOMETRY_PATH = absjoin(
        "run",
        "light_field_geometry")

EXAMPLE_PLENOSCOPE_SCENERY_PATH = absjoin(
        "resources",
        "acp",
        "71m",
        "scenery")

MERLICT_PLENOSCOPE_PROPAGATOR_CONFIG_PATH = absjoin(
        "resources",
        "acp",
        "merlict_propagation_config.json")

EXAMPLE_SITE = {
    "observation_level_asl_m": 5000,
    "earth_magnetic_field_x_muT": 20.815,
    "earth_magnetic_field_z_muT": -11.366,
    "atmosphere_id": 26,
}

EXAMPLE_PLENOSCOPE_POINTING = {
    "azimuth_deg": 0.,
    "zenith_deg": 0.
}

EXAMPLE_PARTICLE = {
    "particle_id": 14,
    "energy_bin_edges_GeV": [5, 100],
    "max_scatter_angle_deg": 30,
    "energy_power_law_slope": -2.0,
}

EXAMPLE_GRID = {
    "num_bins_radius": 512,
    "threshold_num_photons": 50
}

EXAMPLE_SUM_TRIGGER = {
    "patch_threshold": 103,
    "integration_time_in_slices": 10,
    "min_num_neighbors": 3,
    "object_distances": [10e3, 15e3, 20e3],
}

EXAMPLE_LOG_DIRECTORY = op.join(".", "_log3")
EXAMPLE_PAST_TRIGGER_DIRECTORY = op.join(".", "_past_trigger3")
EXAMPLE_FEATURE_DIRECTORY = op.join(".", "_features3")
EXAMPLE_WORK_DIR = op.join(".", "_work3")

EXAMPLE_JOB = {
    "run_id": 1,
    "num_air_showers": 100,
    "particle": EXAMPLE_PARTICLE,
    "plenoscope_pointing": EXAMPLE_PLENOSCOPE_POINTING,
    "site": EXAMPLE_SITE,
    "grid": EXAMPLE_GRID,
    "sum_trigger": EXAMPLE_SUM_TRIGGER,
    "corsika_primary_path": CORSIKA_PRIMARY_PATH,
    "plenoscope_scenery_path": EXAMPLE_PLENOSCOPE_SCENERY_PATH,
    "merlict_plenoscope_propagator_path": MERLICT_PLENOSCOPE_PROPAGATOR_PATH,
    "light_field_geometry_path": LIGHT_FIELD_GEOMETRY_PATH,
    "merlict_plenoscope_propagator_config_path":
        MERLICT_PLENOSCOPE_PROPAGATOR_CONFIG_PATH,
    "log_dir": EXAMPLE_LOG_DIRECTORY,
    "past_trigger_dir": EXAMPLE_PAST_TRIGGER_DIRECTORY,
    "feature_dir": EXAMPLE_FEATURE_DIRECTORY,
    "non_temp_work_dir": EXAMPLE_WORK_DIR,
    "date": date_dict_now(),
}


def _cone_solid_angle(cone_radial_opening_angle_rad):
    cap_hight = (1.0 - np.cos(cone_radial_opening_angle_rad))
    return 2.0*np.pi*cap_hight


def ray_plane_x_y_intersection(support, direction, plane_z):
    direction = np.array(direction)
    support = np.array(support)
    direction_norm = direction/np.linalg.norm(direction)
    ray_parameter = -(support[2] - plane_z)/direction_norm[2]
    intersection = support + ray_parameter*direction_norm
    assert np.abs(intersection[2] - plane_z) < 1e-3
    return intersection


def draw_corsika_primary_steering(
    run_id=1,
    site=EXAMPLE_SITE,
    particle=EXAMPLE_PARTICLE,
    plenoscope_pointing=EXAMPLE_PLENOSCOPE_POINTING,
    num_events=100
):
    particle_id = particle["particle_id"]
    energy_bin_edges_GeV = particle["energy_bin_edges_GeV"]
    max_scatter_angle_deg = particle["max_scatter_angle_deg"]
    energy_power_law_slope = particle["energy_power_law_slope"]

    assert(run_id > 0)
    assert(np.all(np.diff(energy_bin_edges_GeV) >= 0))
    assert(len(energy_bin_edges_GeV) == 2)
    max_scatter_rad = np.deg2rad(max_scatter_angle_deg)
    assert(num_events <= table.MAX_NUM_EVENTS_IN_RUN)

    np.random.seed(run_id)
    energies = random.draw_power_law(
        lower_limit=np.min(energy_bin_edges_GeV),
        upper_limit=np.max(energy_bin_edges_GeV),
        power_slope=energy_power_law_slope,
        num_samples=num_events)
    steering = {}
    steering["run"] = {
        "run_id": int(run_id),
        "event_id_of_first_event": 1}
    for key in site:
        steering["run"][key] = site[key]

    steering["primaries"] = []
    for e in range(energies.shape[0]):
        event_id = e + 1
        primary = {}
        primary["particle_id"] = int(particle_id)
        primary["energy_GeV"] = float(energies[e])
        az, zd = random.draw_azimuth_zenith_in_viewcone(
            azimuth_rad=np.deg2rad(plenoscope_pointing["azimuth_deg"]),
            zenith_rad=np.deg2rad(plenoscope_pointing["zenith_deg"]),
            min_scatter_opening_angle_rad=0.,
            max_scatter_opening_angle_rad=max_scatter_rad)
        primary["max_scatter_rad"] = max_scatter_rad
        primary["zenith_rad"] = zd
        primary["azimuth_rad"] = az
        primary["depth_g_per_cm2"] = 0.0
        primary["random_seed"] = cpw._simple_seed(
            table.random_seed_based_on(run_id=run_id, airshower_id=event_id))

        steering["primaries"].append(primary)
    return steering


def tar_append(tarout, file_name, file_bytes):
    with io.BytesIO() as buff:
        info = tarfile.TarInfo(file_name)
        info.size = buff.write(file_bytes)
        buff.seek(0)
        tarout.addfile(info, buff)


def _append_trigger_truth(
    trigger_dict,
    trigger_responses,
    detector_truth,
):
    tr = trigger_dict
    tr["num_cherenkov_pe"] = int(detector_truth.number_air_shower_pulses())
    tr["response_pe"] = int(np.max(
        [layer['patch_threshold'] for layer in trigger_responses]))
    for o in range(len(trigger_responses)):
        tr["refocus_{:d}_object_distance_m".format(o)] = float(
            trigger_responses[o]['object_distance'])
        tr["refocus_{:d}_respnse_pe".format(o)] = int(
            trigger_responses[o]['patch_threshold'])
    return tr


def _append_bunch_ssize(cherenkovsise_dict, cherenkov_bunches):
    cb = cherenkov_bunches
    ase = cherenkovsise_dict
    ase["num_bunches"] = int(cb.shape[0])
    ase["num_photons"] = float(np.sum(cb[:, cpw.IBSIZE]))
    return ase


def _append_bunch_statistics(airshower_dict, cherenkov_bunches):
    cb = cherenkov_bunches
    ase = airshower_dict
    assert cb.shape[0] > 0
    ase["maximum_asl_m"] = float(cpw.CM2M*np.median(cb[:, cpw.IZEM]))
    ase["wavelength_median_nm"] = float(np.abs(np.median(cb[:, cpw.IWVL])))
    ase["cx_median_rad"] = float(np.median(cb[:, cpw.ICX]))
    ase["cy_median_rad"] = float(np.median(cb[:, cpw.ICY]))
    ase["x_median_m"] = float(cpw.CM2M*np.median(cb[:, cpw.IX]))
    ase["y_median_m"] = float(cpw.CM2M*np.median(cb[:, cpw.IY]))
    ase["bunch_size_median"] = float(np.median(cb[:, cpw.IBSIZE]))
    return ase


def safe_copy(src, dst):
    try:
        shutil.copytree(src, dst+".tmp")
    except OSError as exc:
        if exc.errno == errno.ENOTDIR:
            shutil.copy2(src, dst+".tmp")
        else:
            raise
    shutil.move(dst+".tmp", dst)


def run_job(job=EXAMPLE_JOB):
    os.makedirs(job["log_dir"], exist_ok=True)
    os.makedirs(job["past_trigger_dir"], exist_ok=True)
    os.makedirs(job["feature_dir"], exist_ok=True)
    run_id_str = "{:06d}".format(job["run_id"])
    time_log_path = op.join(job["log_dir"], run_id_str+"_log.jsonl")
    logger = logging.JsonlLog(time_log_path+".tmp")
    job_path = op.join(job["feature_dir"], run_id_str+"_job.json")
    with open(job_path, "wt") as f:
        f.write(json.dumps(job, indent=4))
    remove_tmp = True if job["non_temp_work_dir"] is None else False
    print('{{"run_id": {:d}"}}\n'.format(job["run_id"]))

    # assert resources exist
    # ----------------------
    assert op.exists(job["corsika_primary_path"])
    assert op.exists(job["merlict_plenoscope_propagator_path"])
    assert op.exists(job["merlict_plenoscope_propagator_config_path"])
    assert op.exists(job["plenoscope_scenery_path"])
    assert op.exists(job["light_field_geometry_path"])
    logger.log("assert resource-paths exist.")

    # set up plenoscope grid
    # ----------------------
    assert job["plenoscope_pointing"]["zenith_deg"] == 0.
    assert job["plenoscope_pointing"]["azimuth_deg"] == 0.
    plenoscope_pointing_direction = np.array([0, 0, 1])  # For now this is fix.

    _scenery_path = op.join(job["plenoscope_scenery_path"], "scenery.json")
    _light_field_sensor_geometry = merlict.read_plenoscope_geometry(
        merlict_scenery_path=_scenery_path)
    plenoscope_diameter = 2.0*_light_field_sensor_geometry[
        "expected_imaging_system_aperture_radius"]
    plenoscope_radius = .5*plenoscope_diameter
    plenoscope_field_of_view_radius_deg = 0.5*_light_field_sensor_geometry[
        "max_FoV_diameter_deg"]
    plenoscope_grid_geometry = grid.init(
        plenoscope_diameter=plenoscope_diameter,
        num_bins_radius=job["grid"]["num_bins_radius"])
    logger.log("set plenoscope-grid")

    # draw primaries
    # --------------
    corsika_primary_steering = draw_corsika_primary_steering(
        run_id=job["run_id"],
        site=job["site"],
        particle=job["particle"],
        plenoscope_pointing=job["plenoscope_pointing"],
        num_events=job["num_air_showers"])
    logger.log("draw primaries")

    with tempfile.TemporaryDirectory(prefix="plenoscope_irf_") as tmp_dir:
        if job["non_temp_work_dir"] is not None:
            tmp_dir = job["non_temp_work_dir"]
            os.makedirs(tmp_dir, exist_ok=True)
        logger.log("make temp_dir:'{:s}'".format(tmp_dir))

        # run CORSIKA
        # -----------
        corsika_run_path = op.join(tmp_dir, run_id_str+"_corsika.tar")
        if not op.exists(corsika_run_path):
            cpw_rc = cpw.corsika_primary(
                corsika_path=job["corsika_primary_path"],
                steering_dict=corsika_primary_steering,
                output_path=corsika_run_path,
                stdout_postfix=".stdout",
                stderr_postfix=".stderr")
            safe_copy(
                corsika_run_path+".stdout",
                op.join(job["log_dir"], run_id_str+"_corsika.stdout"))
            safe_copy(
                corsika_run_path+".stderr",
                op.join(job["log_dir"], run_id_str+"_corsika.stderr"))
            logger.log("run CORSIKA")

        with open(corsika_run_path+".stdout", "rt") as f:
            assert cpw.stdout_ends_with_end_of_run_marker(f.read())
        logger.log("assert CORSIKA quit ok")
        corsika_run_size = os.stat(corsika_run_path).st_size
        logger.log("corsika_run size: {:d}".format(corsika_run_size))

        # loop over air-showers
        # ---------------------
        table_prim = []
        table_fase = []
        table_grhi = []
        table_rase = []
        table_rcor = []
        table_crsz = []
        table_crszpart = []

        run = cpw.Tario(corsika_run_path)
        reuse_run_path = op.join(tmp_dir, run_id_str+"_reuse.tar")
        tmp_imgtar_path = op.join(tmp_dir, run_id_str+"_grid.tar")
        with tarfile.open(reuse_run_path, "w") as tarout,\
                tarfile.open(tmp_imgtar_path, "w") as imgtar:
            tar_append(tarout, cpw.TARIO_RUNH_FILENAME, run.runh.tobytes())
            for event_idx, event in enumerate(run):
                event_header, cherenkov_bunches = event

                # assert match
                run_id = int(cpw._evth_run_number(event_header))
                assert (run_id == corsika_primary_steering["run"]["run_id"])
                event_id = event_idx + 1
                assert (event_id == cpw._evth_event_number(event_header))
                primary = corsika_primary_steering["primaries"][event_idx]
                event_seed = primary["random_seed"][0]["SEED"]
                ide = {"run_id":  int(run_id), "airshower_id": int(event_id)}
                assert (event_seed == table.random_seed_based_on(
                    run_id=run_id,
                    airshower_id=event_id))

                np.random.seed(event_seed)
                grid_random_shift_x, grid_random_shift_y = np.random.uniform(
                    low=-plenoscope_radius,
                    high=plenoscope_radius,
                    size=2)

                # export primary table
                # --------------------
                prim = ide.copy()
                prim["particle_id"] = int(primary["particle_id"])
                prim["energy_GeV"] = float(primary["energy_GeV"])
                prim["azimuth_rad"] = float(primary["azimuth_rad"])
                prim["zenith_rad"] = float(primary["zenith_rad"])
                prim["max_scatter_rad"] = float(primary["max_scatter_rad"])
                prim["solid_angle_thrown_sr"] = float(_cone_solid_angle(
                    prim["max_scatter_rad"]))
                prim["depth_g_per_cm2"] = float(primary["depth_g_per_cm2"])
                prim["momentum_x_GeV_per_c"] = float(
                    cpw._evth_px_momentum_in_x_direction_GeV_per_c(
                        event_header))
                prim["momentum_y_GeV_per_c"] = float(
                    cpw._evth_py_momentum_in_y_direction_GeV_per_c(
                        event_header))
                prim["momentum_z_GeV_per_c"] = float(
                    -1.0*cpw._evth_pz_momentum_in_z_direction_GeV_per_c(
                        event_header))
                prim["first_interaction_height_asl_m"] = float(
                    -1.0*cpw.CM2M *
                    cpw._evth_z_coordinate_of_first_interaction_cm(
                        event_header))
                prim["starting_height_asl_m"] = float(
                    cpw.CM2M*cpw._evth_starting_height_cm(event_header))
                obs_lvl_intersection = ray_plane_x_y_intersection(
                    support=[0, 0, prim["starting_height_asl_m"]],
                    direction=[
                        prim["momentum_x_GeV_per_c"],
                        prim["momentum_y_GeV_per_c"],
                        prim["momentum_z_GeV_per_c"]],
                    plane_z=job["site"]["observation_level_asl_m"])
                prim["starting_x_m"] = -float(obs_lvl_intersection[0])
                prim["starting_y_m"] = -float(obs_lvl_intersection[1])
                table_prim.append(prim)

                # cherenkov size
                # --------------
                crsz = ide.copy()
                crsz = _append_bunch_ssize(crsz, cherenkov_bunches)
                table_crsz.append(crsz)

                # assign grid
                # -----------
                grid_result = grid.assign(
                    cherenkov_bunches=cherenkov_bunches,
                    plenoscope_field_of_view_radius_deg=(
                        plenoscope_field_of_view_radius_deg),
                    plenoscope_pointing_direction=(
                        plenoscope_pointing_direction),
                    plenoscope_grid_geometry=plenoscope_grid_geometry,
                    grid_random_shift_x=grid_random_shift_x,
                    grid_random_shift_y=grid_random_shift_y,
                    threshold_num_photons=job["grid"]["threshold_num_photons"])

                tar_append(
                    tarout=imgtar,
                    file_name="{:06d}.f4".format(event_id),
                    file_bytes=grid.histogram_to_bytes(
                        grid_result["histogram"]))

                # grid statistics
                # ---------------
                grhi = ide.copy()
                grhi["num_bins_radius"] = int(
                    plenoscope_grid_geometry["num_bins_radius"])
                grhi["plenoscope_diameter_m"] = float(
                    plenoscope_grid_geometry["plenoscope_diameter"])
                grhi["plenoscope_field_of_view_radius_deg"] = float(
                    plenoscope_field_of_view_radius_deg)
                grhi["plenoscope_pointing_direction_x"] = float(
                    plenoscope_pointing_direction[0])
                grhi["plenoscope_pointing_direction_y"] = float(
                    plenoscope_pointing_direction[1])
                grhi["plenoscope_pointing_direction_z"] = float(
                    plenoscope_pointing_direction[2])
                grhi["random_shift_x_m"] = grid_random_shift_x
                grhi["random_shift_y_m"] = grid_random_shift_y
                for i in range(len(grid_result["intensity_histogram"])):
                    grhi["hist_{:02d}".format(i)] = int(
                        grid_result["intensity_histogram"][i])
                grhi["num_bins_above_threshold"] = int(
                    grid_result["num_bins_above_threshold"])
                grhi["overflow_x"] = int(grid_result["overflow_x"])
                grhi["underflow_x"] = int(grid_result["underflow_x"])
                grhi["overflow_y"] = int(grid_result["overflow_y"])
                grhi["underflow_y"] = int(grid_result["underflow_y"])
                grhi["area_thrown_m2"] = float(plenoscope_grid_geometry[
                    "total_area"])
                table_grhi.append(grhi)

                # cherenkov statistics
                # --------------------
                if cherenkov_bunches.shape[0] > 0:
                    fase = ide.copy()
                    fase = _append_bunch_statistics(
                        airshower_dict=fase,
                        cherenkov_bunches=cherenkov_bunches)
                    table_fase.append(fase)

                reuse_event = grid_result["random_choice"]
                if reuse_event is not None:
                    IEVTH_NUM_REUSES = 98-1
                    IEVTH_CORE_X = IEVTH_NUM_REUSES + 1
                    IEVTH_CORE_Y = IEVTH_NUM_REUSES + 11
                    reuse_evth = event_header.copy()
                    reuse_evth[IEVTH_NUM_REUSES] = 1.0
                    reuse_evth[IEVTH_CORE_X] = cpw.M2CM*reuse_event["core_x_m"]
                    reuse_evth[IEVTH_CORE_Y] = cpw.M2CM*reuse_event["core_y_m"]

                    tar_append(
                        tarout=tarout,
                        file_name=cpw.TARIO_EVTH_FILENAME.format(event_id),
                        file_bytes=reuse_evth.tobytes())
                    tar_append(
                        tarout=tarout,
                        file_name=cpw.TARIO_BUNCHES_FILENAME.format(event_id),
                        file_bytes=reuse_event["cherenkov_bunches"].tobytes())

                    crszp = ide.copy()
                    crszp = _append_bunch_ssize(crszp, cherenkov_bunches)
                    table_crszpart.append(crszp)

                    rase = ide.copy()
                    rase = _append_bunch_statistics(
                        airshower_dict=rase,
                        cherenkov_bunches=reuse_event["cherenkov_bunches"])
                    table_rase.append(rase)

                    rcor = ide.copy()
                    rcor["bin_idx_x"] = int(reuse_event["bin_idx_x"])
                    rcor["bin_idx_y"] = int(reuse_event["bin_idx_y"])
                    rcor["core_x_m"] = float(reuse_event["core_x_m"])
                    rcor["core_y_m"] = float(reuse_event["core_y_m"])
                    table_rcor.append(rcor)
        logger.log("reuse, grid")

        if remove_tmp:
            os.remove(corsika_run_path)

        table.write_level(
            path=op.join(job["feature_dir"], run_id_str+"_primary.csv"),
            list_of_dicts=table_prim,
            config=table.CONFIG,
            level='primary')
        table.write_level(
            path=op.join(job["feature_dir"], run_id_str+"_cherenkovsize.csv"),
            list_of_dicts=table_crsz,
            config=table.CONFIG,
            level='cherenkovsize')
        table.write_level(
            path=op.join(job["feature_dir"], run_id_str+"_grid.csv"),
            list_of_dicts=table_grhi,
            config=table.CONFIG,
            level="grid")
        table.write_level(
            path=op.join(job["feature_dir"], run_id_str+"_cherenkovpool.csv"),
            list_of_dicts=table_fase,
            config=table.CONFIG,
            level="cherenkovpool")

        table.write_level(
            path=op.join(job["feature_dir"], run_id_str+"_core.csv"),
            list_of_dicts=table_rcor,
            config=table.CONFIG,
            level="core")
        table.write_level(
            path=op.join(
                job["feature_dir"],
                run_id_str+"_cherenkovsizepart.csv"),
            list_of_dicts=table_crszpart,
            config=table.CONFIG,
            level="cherenkovsizepart")
        table.write_level(
            path=op.join(
                job["feature_dir"],
                run_id_str+"_cherenkovpoolpart.csv"),
            list_of_dicts=table_rase,
            config=table.CONFIG,
            level="cherenkovpoolpart")

        safe_copy(
            tmp_imgtar_path,
            op.join(job["feature_dir"], run_id_str+"_grid_images.tar"))

        logger.log("export, level 1, and level 2")

        # run merlict
        # -----------
        merlict_run_path = op.join(tmp_dir, run_id_str+"_merlict.cp")
        if not op.exists(merlict_run_path):
            merlict_rc = merlict.plenoscope_propagator(
                corsika_run_path=reuse_run_path,
                output_path=merlict_run_path,
                light_field_geometry_path=job[
                    "light_field_geometry_path"],
                merlict_plenoscope_propagator_path=job[
                    "merlict_plenoscope_propagator_path"],
                merlict_plenoscope_propagator_config_path=job[
                    "merlict_plenoscope_propagator_config_path"],
                random_seed=run_id,
                stdout_postfix=".stdout",
                stderr_postfix=".stderr")
            safe_copy(
                merlict_run_path+".stdout",
                op.join(job["log_dir"], run_id_str+"_merlict.stdout"))
            safe_copy(
                merlict_run_path+".stderr",
                op.join(job["log_dir"], run_id_str+"_merlict.stderr"))
            logger.log("run merlict")
            assert(merlict_rc == 0)

        if remove_tmp:
            os.remove(reuse_run_path)

        # prepare trigger
        # ---------------
        merlict_run = pl.Run(merlict_run_path)
        trigger_preparation = pl.trigger.prepare_refocus_sum_trigger(
            light_field_geometry=merlict_run.light_field_geometry,
            object_distances=job["sum_trigger"]["object_distances"])
        logger.log("prepare refocus-sum-trigger")

        table_trigger_truth = []
        table_past_trigger = []
        table_past_trigger_paths = []

        # loop over sensor responses
        # --------------------------
        for event in merlict_run:
            trigger_responses = pl.trigger.apply_refocus_sum_trigger(
                event=event,
                trigger_preparation=trigger_preparation,
                min_number_neighbors=job["sum_trigger"]["min_num_neighbors"],
                integration_time_in_slices=(
                    job["sum_trigger"]["integration_time_in_slices"]))
            sum_trigger_info_path = op.join(
                event._path,
                "refocus_sum_trigger.json")
            with open(sum_trigger_info_path, "wt") as f:
                f.write(json.dumps(trigger_responses, indent=4))

            cevth = event.simulation_truth.event.corsika_event_header.raw
            run_id = int(cpw._evth_run_number(cevth))
            airshower_id = int(cpw._evth_event_number(cevth))
            ide = {"run_id": run_id, "airshower_id": airshower_id}

            trigger_truth = ide.copy()
            trigger_truth = _append_trigger_truth(
                trigger_dict=trigger_truth,
                trigger_responses=trigger_responses,
                detector_truth=event.simulation_truth.detector)
            table_trigger_truth.append(trigger_truth)

            if (trigger_truth["response_pe"] >=
                    job["sum_trigger"]["patch_threshold"]):
                table_past_trigger_paths.append(event._path)
                pl.tools.acp_format.compress_event_in_place(event._path)
                final_event_filename = '{run_id:06d}{airshower_id:06d}'.format(
                    run_id=run_id,
                    airshower_id=airshower_id)
                final_event_path = op.join(
                    job["past_trigger_dir"],
                    final_event_filename)
                safe_copy(event._path, final_event_path)
                past_trigger = ide.copy()
                table_past_trigger.append(past_trigger)
        logger.log("run sum-trigger")

        table.write_level(
            path=op.join(job["feature_dir"], run_id_str+"_trigger.csv"),
            list_of_dicts=table_trigger_truth,
            config=table.CONFIG,
            level="trigger")
        table.write_level(
            path=op.join(job["feature_dir"], run_id_str+"_pasttrigger.csv"),
            list_of_dicts=table_past_trigger,
            config=table.CONFIG,
            level="pasttrigger")

        # Cherenkov classification
        # ------------------------
        table_cherenkov_classification_scores = []
        for past_trigger_event_path in table_past_trigger_paths:
            event = pl.Event(
                path=past_trigger_event_path,
                light_field_geometry=merlict_run.light_field_geometry)
            roi = pl.classify.center_for_region_of_interest(event)
            photons = pl.classify.RawPhotons.from_event(event)
            (
                cherenkov_photons,
                roi_settings
            ) = pl.classify.cherenkov_photons_in_roi_in_image(
                roi=roi,
                photons=photons)
            pl.classify.write_dense_photon_ids_to_event(
                event_path=op.abspath(event._path),
                photon_ids=cherenkov_photons.photon_ids,
                settings=roi_settings)
            score = pl.classify.benchmark(
                pulse_origins=event.simulation_truth.detector.pulse_origins,
                photon_ids_cherenkov=cherenkov_photons.photon_ids)
            score["run_id"] = int(
                event.simulation_truth.event.corsika_run_header.number)
            score["airshower_id"] = int(
                event.simulation_truth.event.corsika_event_header.number)
            table_cherenkov_classification_scores.append(score)
        table.write_level(
            path=op.join(
                job["feature_dir"],
                run_id_str+"_cherenkovclassification.csv"),
            list_of_dicts=table_cherenkov_classification_scores,
            config=table.CONFIG,
            level="cherenkovclassification")
        logger.log("Cherenkov classification")

        # extracting features
        # -------------------
        lfg = merlict_run.light_field_geometry
        lfg_addon = {}
        lfg_addon["paxel_radius"] = (
            lfg.sensor_plane2imaging_system.
            expected_imaging_system_max_aperture_radius /
            lfg.sensor_plane2imaging_system.number_of_paxel_on_pixel_diagonal)
        lfg_addon["nearest_neighbor_paxel_enclosure_radius"] = \
            3*lfg_addon["paxel_radius"]
        lfg_addon["paxel_neighborhood"] = (
            pl.features.estimate_nearest_neighbors(
                x=lfg.paxel_pos_x,
                y=lfg.paxel_pos_y,
                epsilon=lfg_addon["nearest_neighbor_paxel_enclosure_radius"]))
        lfg_addon["fov_radius"] = \
            .5*lfg.sensor_plane2imaging_system.max_FoV_diameter
        lfg_addon["fov_radius_leakage"] = 0.9*lfg_addon["fov_radius"]
        lfg_addon["num_pixel_on_diagonal"] = \
            np.floor(2*np.sqrt(lfg.number_pixel/np.pi))
        logger.log("create light_field_geometry addons")

        table_features = []
        for event_path in table_past_trigger_paths:
            event = pl.Event(path=event_path, light_field_geometry=lfg)
            run_id = int(
                event.simulation_truth.event.corsika_run_header.number)
            airshower_id = int(
                event.simulation_truth.event.corsika_event_header.number)
            try:
                cp = event.cherenkov_photons
                if cp is None:
                    raise RuntimeError("No Cherenkov-photons classified yet.")
                f = pl.features.extract_features(
                    cherenkov_photons=cp,
                    light_field_geometry=lfg,
                    light_field_geometry_addon=lfg_addon)
                f["run_id"] = int(run_id)
                f["airshower_id"] = int(airshower_id)
                table_features.append(f)
            except Exception as e:
                print(
                    "run_id {:d}, airshower_id: {:d} :".format(
                        run_id,
                        airshower_id),
                    e)
        table.write_level(
            path=op.join(job["feature_dir"], run_id_str+"_features.csv"),
            list_of_dicts=table_features,
            config=table.CONFIG,
            level="features")
        logger.log("extract features from light-field")

        logger.log("end")
        shutil.move(time_log_path+".tmp", time_log_path)