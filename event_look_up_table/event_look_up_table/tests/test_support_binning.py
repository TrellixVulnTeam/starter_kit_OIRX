import event_look_up_table as elut
import numpy as np
import tempfile
import os


def test_make_aperture_binning():
    apbi = elut.make_aperture_binning(aperture_binning_config={
        "bin_edge_width": 128,
        "num_bins_radius": 8})

    assert apbi["num_bins"] == 16*16

    for b in range(apbi["num_bins"]):
        ix = apbi["addressing_1D_to_2D"][b, 0]
        iy = apbi["addressing_1D_to_2D"][b, 1]
        assert apbi["addressing_2D_to_1D"][ix, iy] == b



def test_assign_aperture_binning_1():
    x_y = np.array(
        [[0, 0]],)
    aperture_binning_config = {
        "bin_edge_width": 32,
        "num_bins_radius": 4}
    xbin, ybin, x_rest, y_rest = elut.compress_x_y(
        x=x_y[:, 0],
        y=x_y[:, 1],
        aperture_binning_config=aperture_binning_config)
    assert xbin == 4
    assert x_rest == 0
    assert ybin == 4
    assert y_rest == 0
    x, y = elut.decompress_x_y(
        xbin, ybin, x_rest, y_rest, aperture_binning_config)
    assert np.abs(x - x_y[:, 0]) < .1
    assert np.abs(y - x_y[:, 1]) < .1


def test_assign_aperture_binning_2():
    x_y = np.array(
        [[50, -80],])
    aperture_binning_config = {
        "bin_edge_width": 32,
        "num_bins_radius": 4}
    xbin, ybin, x_rest, y_rest = elut.compress_x_y(
        x=x_y[:, 0],
        y=x_y[:, 1],
        aperture_binning_config=aperture_binning_config)
    assert xbin == 5
    assert x_rest == np.floor((50 - 32)/32.*256)
    assert ybin == 1
    assert y_rest == np.floor((-80 + 96)/32.*256)
    x, y = elut.decompress_x_y(
        xbin, ybin, x_rest, y_rest, aperture_binning_config)
    assert np.abs(x - x_y[:, 0]) < .1
    assert np.abs(y - x_y[:, 1]) < .1


def test_assign_aperture_binning_out_of_range():
    x_y = np.array(
        [[-1200, 400],])
    aperture_binning_config = {
        "bin_edge_width": 32,
        "num_bins_radius": 4}
    xbin, ybin, x_rest, y_rest = elut.compress_x_y(
        x=x_y[:, 0],
        y=x_y[:, 1],
        aperture_binning_config=aperture_binning_config)
    assert xbin == -34
    assert ybin == 16


def test_compression_directions_valid():
    fov_r=np.deg2rad(4)
    cx_cy = np.deg2rad(np.array(
        [[-0.5, 1.0],]))
    cx_bin, cy_bin = elut.compress_cx_cy(
        cx=cx_cy[:, 0],
        cy=cx_cy[:, 1],
        field_of_view_radius=fov_r)
    assert cx_bin == int((-.5)/(8./(2**16 - 1)) + (2**15))
    assert cy_bin == int((1.0)/(8./(2**16 - 1)) + (2**15))

    cx_back, cy_back = elut.decompress_cx_cy(
        cx_bin=cx_bin,
        cy_bin=cy_bin,
        field_of_view_radius=fov_r)
    assert np.abs(cx_back - cx_cy[:, 0]) < np.deg2rad(0.001)
    assert np.abs(cy_back - cx_cy[:, 1]) < np.deg2rad(0.001)


def test_compression_directions_out_of_range():
    cx_cy = np.deg2rad(np.array(
        [[-4.5, 5.0],]))
    cx_bin, cy_bin = elut.compress_cx_cy(
        cx=cx_cy[:, 0],
        cy=cx_cy[:, 1],
        field_of_view_radius=np.deg2rad(4))
    assert cx_bin < 0
    assert cy_bin > (2**16)


def test_overlap_circle():
    aperture_binning_config = {
        "bin_edge_width": 1,
        "num_bins_radius": 2}
    abc = elut.make_aperture_binning(aperture_binning_config)

    ov = elut._estimate_xy_bins_overlapping_with_circle(
        aperture_binning_config=abc,
        circle_x=0,
        circle_y=0,
        circle_radius=0.5)

    """        y
               |
               |
       +---+---+---+---+
       | 0 | 4 | 8 |12 |
       +---+---+---+---+
       | 1 | 5 | 9 |13 |
       +---+---X---+---+----> x
       | 2 | 6 |10 |14 |
       +---+---+---+---+
       | 3 | 7 |11 |15 |
       +---+---+---+---+
    """
    assert len(ov) == 4
    assert 5 in ov
    assert 6 in ov
    assert 9 in ov
    assert 10 in ov

    ov = elut._estimate_xy_bins_overlapping_with_circle(
        aperture_binning_config=abc,
        circle_x=2,
        circle_y=0,
        circle_radius=0.5)

    print(abc["addressing_1D_to_2D"])
    assert len(ov) == 2
    assert 13 in ov
    assert 14 in ov


def test_write_read_photons():
    aperture_binning_config = {
        "bin_edge_width": 64,
        "num_bins_radius": 16}
    abc = elut.make_aperture_binning(aperture_binning_config)
    field_of_view_radius = np.deg2rad(4.)

    NUM_PHOTONS = 1000*100
    C_SCALE = np.deg2rad(1.0)
    np.random.seed(0)
    x_y_cx_cy = np.array([
        np.random.normal(loc=50., scale=100, size=NUM_PHOTONS),
        np.random.normal(loc=-125., scale=150, size=NUM_PHOTONS),
        np.random.normal(loc=np.deg2rad(-.25), scale=C_SCALE*2, size=NUM_PHOTONS),
        np.random.normal(loc=np.deg2rad(0.5), scale=C_SCALE, size=NUM_PHOTONS)]).T
    print("cx_mean", np.rad2deg(np.mean(x_y_cx_cy[:, 2])), "deg")
    print("cy_mean", np.rad2deg(np.mean(x_y_cx_cy[:, 3])), "deg")

    comp_x_y_cx_cy, valid_photons = elut.compress_photons(
        x=x_y_cx_cy[:, 0],
        y=x_y_cx_cy[:, 1],
        cx=x_y_cx_cy[:, 2],
        cy=x_y_cx_cy[:, 3],
        aperture_binning_config=abc,
        field_of_view_radius=field_of_view_radius)

    num_photons_written = np.sum(valid_photons)

    with tempfile.TemporaryDirectory() as tmp:
        elut.append_compressed_photons(
            path=tmp,
            compressed_photons=comp_x_y_cx_cy)

        back_x_y_cx_cy = elut.read_photons(
            path=tmp,
            aperture_binning_config=abc,
            circle_x=0.,
            circle_y=0.,
            circle_radius=10e3,
            field_of_view_radius=field_of_view_radius)

    assert back_x_y_cx_cy.shape[0] == num_photons_written
    assert np.abs(np.mean(back_x_y_cx_cy[:, 0]) - 50.) < 10.
    assert np.abs(np.std(back_x_y_cx_cy[:, 0]) - 100.) < 10.
    assert np.abs(np.mean(back_x_y_cx_cy[:, 1]) - (-125.)) < 10.
    assert np.abs(np.std(back_x_y_cx_cy[:, 1]) - 150.) < 10.

    print("back cx_mean", np.rad2deg(np.mean(back_x_y_cx_cy[:, 2])), "deg")
    print("back cy_mean", np.rad2deg(np.mean(back_x_y_cx_cy[:, 3])), "deg")
    assert np.abs(np.mean(back_x_y_cx_cy[:, 2]) - np.deg2rad(-.25)) < np.deg2rad(0.1)
    assert np.abs(np.mean(back_x_y_cx_cy[:, 3]) - np.deg2rad(0.5)) < np.deg2rad(0.1)

    assert np.abs(np.std(back_x_y_cx_cy[:, 2]) - C_SCALE*2) < np.deg2rad(0.3)
    assert np.abs(np.std(back_x_y_cx_cy[:, 3]) - C_SCALE) < np.deg2rad(0.3)