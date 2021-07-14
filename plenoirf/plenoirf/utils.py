import numpy as np
import datetime
import io
import tarfile


def cone_solid_angle(cone_radial_opening_angle_rad):
    cap_hight = 1.0 - np.cos(cone_radial_opening_angle_rad)
    return 2.0 * np.pi * cap_hight


def contains_same_bytes(path_a, path_b):
    with open(path_a, "rb") as fa, open(path_b, "rb") as fb:
        a_bytes = fa.read()
        b_bytes = fb.read()
        return a_bytes == b_bytes


def date_dict_now():
    dt = datetime.datetime.now()
    out = {}
    for key in ["year", "month", "day", "hour", "minute", "second"]:
        out[key] = int(dt.__getattribute__(key))
    return out


def tar_append(tarout, file_name, file_bytes):
    with io.BytesIO() as buff:
        info = tarfile.TarInfo(file_name)
        info.size = buff.write(file_bytes)
        buff.seek(0)
        tarout.addfile(info, buff)


def ray_plane_x_y_intersection(support, direction, plane_z):
    direction = np.array(direction)
    support = np.array(support)
    direction_norm = direction / np.linalg.norm(direction)
    ray_parameter = -(support[2] - plane_z) / direction_norm[2]
    intersection = support + ray_parameter * direction_norm
    assert np.abs(intersection[2] - plane_z) < 1e-3
    return intersection


def bin_centers(bin_edges, weight_lower_edge=0.5):
    assert weight_lower_edge >= 0.0 and weight_lower_edge <= 1.0
    weight_upper_edge = 1.0 - weight_lower_edge
    return (
        weight_lower_edge * bin_edges[:-1] + weight_upper_edge * bin_edges[1:]
    )


def bin_width(bin_edges):
    return bin_edges[1:] - bin_edges[:-1]


def power10_bin_edge(decade, bin, num_bins=5):
    """
    returns the lower bin_edge of bin in decade.
    The binning has num_bins_per_decade.
    """
    assert bin < num_bins
    return 10 ** (decade + np.linspace(0, 1, num_bins + 1))[bin]


_10s = 10
_1M = 60
_1h = _1M * 60
_1d = _1h * 24
_1w = _1d * 7
_1m = _1d * 30
_1y = 365 * _1d


def make_civil_times_points_in_quasi_logspace():
    """
    time-points from 1s to 100y in the civil steps of:
    s, m, h, d, week, Month, year, decade
    """

    times = []
    for _secs in np.arange(1, _10s, 1):
        times.append(_secs)
    for _10secs in np.arange(_10s, _1M, _10s):
        times.append(_10secs)
    for _mins in np.arange(_1M, _1h, _1M):
        times.append(_mins)
    for _hours in np.arange(_1h, _1d, _1h):
        times.append(_hours)
    for _days in np.arange(_1d, _1w, _1d):
        times.append(_days)
    for _weeks in np.arange(_1w, 4 * _1w, _1w):
        times.append(_weeks)
    for _months in np.arange(_1m, 12 * _1m, _1m):
        times.append(_months)
    for _years in np.arange(_1y, 10 * _1y, _1y):
        times.append(_years)
    for _decades in np.arange(10 * _1y, 100 * _1y, 10 * _1y):
        times.append(_decades)
    return times


def make_civil_time_str(time_s, format_seconds="{:f}"):
    try:
        years = int(time_s // _1y)
        tr = time_s - years * _1y

        days = int(tr // _1d)
        tr = tr - days * _1d

        hours = int(tr // _1h)
        tr = tr - hours * _1h

        minutes = int(tr // _1M)
        tr = tr - minutes * _1M

        s = ""
        if years:
            s += "{:d}y ".format(years)
        if days:
            s += "{:d}d ".format(days)
        if hours:
            s += "{:d}h ".format(hours)
        if minutes:
            s += "{:d}min ".format(minutes)
        if tr:
            s += (format_seconds + "s").format(tr)
        if s[-1] == " ":
            s = s[0:-1]
        return s
    except Exception as err:
        print(str(err))
        return (format_seconds + "s").format(time_s)


def find_closest_index_in_array_for_value(arr, val, max_rel_error=0.1):
    arr = np.array(arr)
    idx = np.argmin(np.abs(arr - val))
    assert np.abs(arr[idx] - val) < max_rel_error * val
    return idx


def latex_scientific(real, format_template="{:e}", nan_template="nan"):
    if real != real:
        return nan_template
    assert format_template.endswith("e}")
    s = format_template.format(real)
    pos_e = s.find("e")
    assert pos_e >= 0
    mantisse = s[0:pos_e]
    exponent = str(int(s[pos_e + 1 :]))
    out = mantisse + r"\times{}10^{" + exponent + r"}"
    return out



def apply_confusion_matrix(x, confusion_matrix, x_unc=None):
    """
    Parameters
    ----------
    x : 1D-array
            E.g. Effective acceptance vs. true energy.
    confusion_matrix : 2D-array
            Confusion between e.g. true and reco. energy.
            The rows are expected to be notmalized:
            CM[i, :] == 1.0
    """
    cm = confusion_matrix
    n = cm.shape[0]
    assert cm.shape[1] == n
    assert x.shape[0] == n

    # assert confusion matrix is normalized
    for i in range(n):
        s = np.sum(cm[i, :])
        assert np.abs(s-1) < 1e-3 or s < 1e-3

    y = np.zeros(shape=(n))
    for r in range(n):
        for t in range(n):
            y[r] += cm[t, r] * x[t]

    return y


def apply_confusion_matrix_uncertainty(x_unc, confusion_matrix):
    cm = confusion_matrix
    n = cm.shape[0]
    assert cm.shape[1] == n
    assert x_unc.shape[0] == n

    y_unc = np.zeros(shape=(n))
    for r in range(n):
        for t in range(n):
            if not np.isnan(x_unc[t]):
                y_unc[r] += (cm[t, r] * x_unc[t]) ** 2.0
    y_unc = np.sqrt(y_unc)
    y_unc[y_unc == 0.0] = np.nan

    return y_unc


def make_confusion_matrix(
    ax0_key,
    ax0_values,
    ax0_bin_edges,
    ax1_key,
    ax1_values,
    ax1_bin_edges,
    ax0_weights=None,
    min_exposure_ax0=100,
    default_low_exposure=np.nan,
):
    assert len(ax0_values) == len(ax1_values)
    if ax0_weights is not None:
        assert len(ax0_values) == len(ax0_weights)

    num_bins_ax0 = len(ax0_bin_edges) - 1
    assert num_bins_ax0 >= 1

    num_bins_ax1 = len(ax1_bin_edges) - 1
    assert num_bins_ax1 >= 1

    confusion_bins = np.histogram2d(
        ax0_values,
        ax1_values,
        weights=ax0_weights,
        bins=[ax0_bin_edges, ax1_bin_edges],
    )[0]

    exposure_bins_no_weights = np.histogram2d(
        ax0_values, ax1_values, bins=[ax0_bin_edges, ax1_bin_edges],
    )[0]

    confusion_bins_normalized_on_ax0 = confusion_bins.copy()
    for i0 in range(num_bins_ax0):
        if np.sum(exposure_bins_no_weights[i0, :]) >= min_exposure_ax0:
            confusion_bins_normalized_on_ax0[i0, :] /= np.sum(
                confusion_bins[i0, :]
            )
        else:
            confusion_bins_normalized_on_ax0[i0, :] = (
                np.ones(num_bins_ax1) * default_low_exposure
            )

    return {
        "ax0_key": ax0_key,
        "ax1_key": ax1_key,
        "ax0_bin_edges": ax0_bin_edges,
        "ax1_bin_edges": ax1_bin_edges,
        "confusion_bins": confusion_bins,
        "confusion_bins_normalized_on_ax0": confusion_bins_normalized_on_ax0,
        "exposure_bins_ax0_no_weights": np.sum(exposure_bins_no_weights, axis=1),
        "exposure_bins_ax0": np.sum(confusion_bins, axis=1),
        "min_exposure_ax0": min_exposure_ax0,
    }
