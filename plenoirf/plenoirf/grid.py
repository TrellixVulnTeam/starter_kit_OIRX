import numpy as np
import gzip
import os
import io
import tarfile
import shutil
import json_numpy
import corsika_primary as cpw
from . import unique


def init_geometry(
    instrument_aperture_outer_diameter,
    bin_width_overhead,
    instrument_field_of_view_outer_radius_deg,
    instrument_pointing_direction,
    field_of_view_overhead,
    num_bins_radius,
):
    """
     num_bins_radius = 2
     _______^______
    /              -
    +-------+-------+-------+-------+-
    |       |       |       |       | |
    |       |       |       |       | |
    |       |       |       |       | |
    +-------+-------+-------+-------+ |
    |       |       |       |       |  > num_bins_radius = 2
    |       |       |       |       | |
    |       |       |(0,0)  |       | |
    +-------+-------+-------+-------+/
    |       |       |       |       |
    |       |       |       |       |
    |       |       |       |       |
    +-------+-------+-------+-------+ <-- bin edge
    |       |       |       |       |
    |       |       |       |   X <-- bin center
    |       |       |       |       |
    +-------+-------+-------+-------+

    """
    assert num_bins_radius > 0

    assert instrument_aperture_outer_diameter > 0.0
    assert bin_width_overhead >= 1.0

    assert instrument_field_of_view_outer_radius_deg > 0.0
    assert field_of_view_overhead >= 1.0

    assert len(instrument_pointing_direction) == 3
    assert np.abs(np.linalg.norm(instrument_pointing_direction) - 1.0) < 1e-6

    g = {}
    g["num_bins_radius"] = num_bins_radius
    g["num_bins_diameter"] = 2 * g["num_bins_radius"]

    g["bin_width"] = instrument_aperture_outer_diameter * bin_width_overhead
    g["bin_area"] = g["bin_width"] ** 2

    g["xy_bin_edges"] = np.linspace(
        start=-g["bin_width"] * g["num_bins_radius"],
        stop=g["bin_width"] * g["num_bins_radius"],
        num=2 * g["num_bins_radius"] + 1,
    )
    g["xy_bin_centers"] = 0.5 * (
        g["xy_bin_edges"][:-1] + g["xy_bin_edges"][1:]
    )
    assert g["num_bins_diameter"] == len(g["xy_bin_edges"]) - 1

    g["total_num_bins"] = g["num_bins_diameter"] ** 2
    g["total_area"] = g["total_num_bins"] * g["bin_area"]

    g["field_of_view_radius_deg"] = (
        instrument_field_of_view_outer_radius_deg * field_of_view_overhead
    )
    g["pointing_direction"] = instrument_pointing_direction

    return g


def _make_bunch_direction(cx, cy):
    d = np.zeros(shape=(cx.shape[0], 3))
    d[:, 0] = cx
    d[:, 1] = cy
    d[:, 2] = -1.0 * np.sqrt(1.0 - cx ** 2 - cy ** 2)
    return d


def _normalize_rows_in_matrix(mat):
    return mat / np.sqrt(np.sum(mat ** 2, axis=1, keepdims=1))


def _make_angle_between(directions, direction):
    direction = direction / np.linalg.norm(direction)
    directions = _normalize_rows_in_matrix(mat=directions)
    return np.arccos(np.dot(directions, direction))


def cut_cherenkov_bunches_in_field_of_view(
    cherenkov_bunches, field_of_view_radius_deg, pointing_direction,
):
    bunch_directions = _make_bunch_direction(
        cx=cherenkov_bunches[:, cpw.I.BUNCH.CX],
        cy=cherenkov_bunches[:, cpw.I.BUNCH.CY],
    )
    bunch_incidents = -1.0 * bunch_directions
    angle_bunch_pointing = _make_angle_between(
        directions=bunch_incidents, direction=pointing_direction
    )
    mask_inside_field_of_view = angle_bunch_pointing < np.deg2rad(
        field_of_view_radius_deg
    )
    return cherenkov_bunches[mask_inside_field_of_view, :]


def histogram2d_overflow_and_bin_idxs(x, y, weights, xy_bin_edges):
    _xy_bin_edges = [-np.inf] + xy_bin_edges.tolist() + [np.inf]

    # histogram num photons, i.e. use bunchsize weights.
    grid_histogram_flow = np.histogram2d(
        x=x, y=y, bins=(_xy_bin_edges, _xy_bin_edges), weights=weights
    )[0]

    # cut out the inner grid, use outer rim to estimate under-, and overflow
    grid_histogram = grid_histogram_flow[1:-1, 1:-1]
    assert grid_histogram.shape[0] == len(xy_bin_edges) - 1
    assert grid_histogram.shape[1] == len(xy_bin_edges) - 1

    overflow = {}
    overflow["overflow_x"] = np.sum(grid_histogram_flow[-1, :])
    overflow["underflow_x"] = np.sum(grid_histogram_flow[0, :])
    overflow["overflow_y"] = np.sum(grid_histogram_flow[:, -1])
    overflow["underflow_y"] = np.sum(grid_histogram_flow[:, 0])

    # assignment
    x_bin_idxs = np.digitize(x, bins=xy_bin_edges)
    y_bin_idxs = np.digitize(y, bins=xy_bin_edges)

    return grid_histogram, overflow, x_bin_idxs, y_bin_idxs


def assign(
    cherenkov_bunches,
    grid_geometry,
    shift_x,
    shift_y,
    threshold_num_photons,
    prng,
    bin_idxs_limitation=None,
):
    pgg = grid_geometry

    bunches_in_fov = cut_cherenkov_bunches_in_field_of_view(
        cherenkov_bunches=cherenkov_bunches,
        field_of_view_radius_deg=pgg["field_of_view_radius_deg"],
        pointing_direction=pgg["pointing_direction"],
    )

    # Supports
    # --------
    CM2M = 1e-2
    M2CM = 1e2
    bunch_x_wrt_grid_m = CM2M * bunches_in_fov[:, cpw.I.BUNCH.X] + shift_x
    bunch_y_wrt_grid_m = CM2M * bunches_in_fov[:, cpw.I.BUNCH.Y] + shift_y
    bunch_weight = bunches_in_fov[:, cpw.I.BUNCH.BSIZE]

    (
        grid_histogram,
        grid_overflow,
        bunch_x_bin_idxs,
        bunch_y_bin_idxs,
    ) = histogram2d_overflow_and_bin_idxs(
        x=bunch_x_wrt_grid_m,
        y=bunch_y_wrt_grid_m,
        xy_bin_edges=pgg["xy_bin_edges"],
        weights=bunch_weight,
    )

    bin_idxs_above_threshold = np.where(grid_histogram > threshold_num_photons)

    if bin_idxs_limitation:
        bin_idxs_above_threshold = apply_bin_limitation_and_warn(
            bin_idxs_above_threshold=bin_idxs_above_threshold,
            bin_idxs_limitation=bin_idxs_limitation,
        )

    num_bins_above_threshold = bin_idxs_above_threshold[0].shape[0]

    if num_bins_above_threshold == 0:
        choice = None
    else:
        _choice_bin = prng.choice(np.arange(num_bins_above_threshold))
        bin_idx_x = bin_idxs_above_threshold[0][_choice_bin]
        bin_idx_y = bin_idxs_above_threshold[1][_choice_bin]
        num_photons_in_bin = grid_histogram[bin_idx_x, bin_idx_y]
        choice = {}
        choice["bin_idx_x"] = bin_idx_x
        choice["bin_idx_y"] = bin_idx_y
        choice["core_x_m"] = pgg["xy_bin_centers"][bin_idx_x] - shift_x
        choice["core_y_m"] = pgg["xy_bin_centers"][bin_idx_y] - shift_y
        match_bin_idx_x = bunch_x_bin_idxs - 1 == bin_idx_x
        match_bin_idx_y = bunch_y_bin_idxs - 1 == bin_idx_y
        match_bin = np.logical_and(match_bin_idx_x, match_bin_idx_y)
        num_photons_in_recovered_bin = np.sum(
            bunches_in_fov[match_bin, cpw.I.BUNCH.BSIZE]
        )
        abs_diff_num_photons = np.abs(
            num_photons_in_recovered_bin - num_photons_in_bin
        )
        if abs_diff_num_photons > 1e-2 * num_photons_in_bin:
            msg = "".join(
                [
                    "num_photons_in_bin: {:E}\n".format(
                        float(num_photons_in_bin)
                    ),
                    "num_photons_in_recovered_bin: {:E}\n".format(
                        float(num_photons_in_recovered_bin)
                    ),
                    "abs(diff): {:E}\n".format(abs_diff_num_photons),
                    "bin_idx_x: {:d}\n".format(bin_idx_x),
                    "bin_idx_y: {:d}\n".format(bin_idx_y),
                    "sum(match_bin): {:d}\n".format(np.sum(match_bin)),
                ]
            )
            assert False, msg
        choice["cherenkov_bunches"] = bunches_in_fov[match_bin, :].copy()
        choice["cherenkov_bunches"][:, cpw.I.BUNCH.X] -= (
            M2CM * choice["core_x_m"]
        )
        choice["cherenkov_bunches"][:, cpw.I.BUNCH.Y] -= (
            M2CM * choice["core_y_m"]
        )

    out = {}
    out["random_choice"] = choice
    out["histogram"] = grid_histogram
    for overflow_key in grid_overflow:
        out[overflow_key] = grid_overflow[overflow_key]
    out["num_bins_above_threshold"] = num_bins_above_threshold
    return out


def histogram_to_bytes(img):
    img_f4 = img.astype("<f4")
    img_f4_flat_c = img_f4.flatten(order="c")
    img_f4_flat_c_bytes = img_f4_flat_c.tobytes()
    img_gzip_bytes = gzip.compress(img_f4_flat_c_bytes)
    return img_gzip_bytes


def bytes_to_histogram(img_bytes_gz):
    img_bytes = gzip.decompress(img_bytes_gz)
    arr = np.frombuffer(img_bytes, dtype="<f4")
    num_bins = arr.shape[0]
    num_bins_edge = int(np.sqrt(num_bins))
    assert num_bins_edge * num_bins_edge == num_bins
    return arr.reshape((num_bins_edge, num_bins_edge), order="c")


# histograms
# ----------
# A dict with the unique-id (uid) as key for the airshowers, containing the
# gzip-bytes to be read with bytes_to_histogram()


def read_all_histograms(path):
    grids = {}
    with tarfile.open(path, "r") as tarfin:
        for tarinfo in tarfin:
            idx = int(tarinfo.name[0 : unique.UID_NUM_DIGITS])
            grids[idx] = tarfin.extractfile(tarinfo).read()
    return grids


def read_histograms(path, indices=None):
    if indices is None:
        return read_all_histograms(path)
    else:
        indices_set = set(indices)
        grids = {}
        with tarfile.open(path, "r") as tarfin:
            for tarinfo in tarfin:
                idx = int(tarinfo.name[0 : unique.UID_NUM_DIGITS])
                if idx in indices_set:
                    grids[idx] = tarfin.extractfile(tarinfo).read()
        return grids


def write_histograms(path, grid_histograms):
    with tarfile.open(path + ".tmp", "w") as tarfout:
        for idx in grid_histograms:
            filename = unique.UID_FOTMAT_STR.format(idx) + ".f4.gz"
            with io.BytesIO() as buff:
                info = tarfile.TarInfo(filename)
                info.size = buff.write(grid_histograms[idx])
                buff.seek(0)
                tarfout.addfile(info, buff)
    shutil.move(path + ".tmp", path)


def reduce(list_of_grid_paths, out_path):
    with tarfile.open(out_path + ".tmp", "w") as tarfout:
        for grid_path in list_of_grid_paths:
            with tarfile.open(grid_path, "r") as tarfin:
                for tarinfo in tarfin:
                    tarfout.addfile(
                        tarinfo=tarinfo, fileobj=tarfin.extractfile(tarinfo)
                    )
    shutil.move(out_path + ".tmp", out_path)


class GridReader:
    def __init__(self, path):
        self.path = str(path)
        self.tar = tarfile.open(name=self.path, mode="r|")
        self.next_info = self.tar.next()

    def __next__(self):
        if self.next_info is None:
            raise StopIteration

        idx = int(self.next_info.name[0 : unique.UID_NUM_DIGITS])
        bimg = self.tar.extractfile(self.next_info).read()
        img = bytes_to_histogram(bimg)
        self.next_info = self.tar.next()
        return idx, img

    def close(self):
        self.tar.close()

    def __iter__(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def __repr__(self):
        out = "{:s}(path='{:s}')".format(self.__class__.__name__, self.path)
        return out


# artificial core limitation
# --------------------------


def where_grid_idxs_within_radius(grid_geometry, radius, center_x, center_y):
    """
    Returns the idxs in x, and y of the grid where the bin is within a circle
    of radius and center_x/y.
    Same format as np.where()
    """
    pgg = grid_geometry
    radius_bins = int(np.ceil(1.1 * radius / pgg["bin_width"]))

    x_bin_center = int(np.round(center_x / pgg["bin_width"]))
    x_bin_range = (
        x_bin_center
        + pgg["num_bins_radius"]
        + np.arange(-radius_bins, radius_bins + 1)
    )
    y_bin_center = int(np.round(center_y / pgg["bin_width"]))
    y_bin_range = (
        y_bin_center
        + pgg["num_bins_radius"]
        + np.arange(-radius_bins, radius_bins + 1)
    )

    num_bins_thrown = 0
    grid_idxs_x = []
    grid_idxs_y = []
    for x_bin in x_bin_range:
        for y_bin in y_bin_range:
            if x_bin < 0 or x_bin >= pgg["num_bins_diameter"]:
                continue
            if y_bin < 0 or y_bin >= pgg["num_bins_diameter"]:
                continue
            delta_x = pgg["xy_bin_centers"][x_bin] - center_x
            delta_y = pgg["xy_bin_centers"][y_bin] - center_y
            if delta_x ** 2 + delta_y ** 2 > radius ** 2:
                continue
            grid_idxs_x.append(x_bin)
            grid_idxs_y.append(y_bin)

    return np.array(grid_idxs_x), np.array(grid_idxs_y)


def intersection_of_bin_idxs(a_bin_idxs, b_bin_idxs):
    """
    Returns only bin-idxs which are both in a_bins and b_bins.
    """
    a = a_bin_idxs
    b = b_bin_idxs
    assert len(a[0]) == len(a[1])
    assert len(b[0]) == len(b[1])
    a_set = set()
    for ia in range(len(a[0])):
        a_set.add((a[0][ia], a[1][ia]))
    b_set = set()
    for ib in range(len(b[0])):
        b_set.add((b[0][ib], b[1][ib]))
    ab_set = a_set.intersection(b_set)
    ab = list(ab_set)
    x_idxs = np.array([idx[0] for idx in ab])
    y_idxs = np.array([idx[1] for idx in ab])
    return (x_idxs, y_idxs)


def apply_bin_limitation_and_warn(
    bin_idxs_above_threshold, bin_idxs_limitation
):
    bin_idxs_above_threshold_and_in_limits = intersection_of_bin_idxs(
        a_bin_idxs=bin_idxs_above_threshold, b_bin_idxs=bin_idxs_limitation
    )
    msg = {}
    msg["artificial_core_limitation"] = {
        "num_grid_bins_in_limits": len(bin_idxs_limitation[0]),
        "num_grid_bins_above_threshold": len(bin_idxs_above_threshold[0]),
        "num_grid_bins_above_threshold_and_in_limits": len(
            bin_idxs_above_threshold_and_in_limits[0]
        ),
    }
    print(json_numpy.dumps(msg))

    return bin_idxs_above_threshold_and_in_limits
