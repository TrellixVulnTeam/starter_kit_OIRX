import numpy as np
import gamma_limits_sensitivity as gls
import scipy
import matplotlib.pyplot as plt


def estimate_integral_spectral_exclusion_zone(
    gamma_effective_area_m2,
    energy_bin_centers_GeV,
    background_rate_in_onregion_per_s,
    onregion_over_offregion_ratio,
    observation_time_s,
    num_points=27
):
    assert len(gamma_effective_area_m2) == len(energy_bin_centers_GeV)
    assert observation_time_s >= 0.0
    assert background_rate_in_onregion_per_s >= 0.0

    log10_energy_bin_centers_GeV_TeV = np.log10(1e-3*energy_bin_centers_GeV)
    gamma_effective_area_cm2 = 1e2*1e2*gamma_effective_area_m2
    _aeff = scipy.interpolate.interpolate.interp1d(
        x=log10_energy_bin_centers_GeV_TeV,
        y=gamma_effective_area_cm2,
        bounds_error=False,
        fill_value=0.
    )
    _waste_figure = plt.figure()
    _energy_range = gls.get_energy_range(_aeff)
    (
        _energy_support_TeV,
        _differential_flux_per_TeV_per_s_per_cm2
    ) = gls.plot_sens_spectrum_figure(
        sigma_bg=background_rate_in_onregion_per_s,
        alpha=onregion_over_offregion_ratio,
        t_obs=observation_time_s,
        a_eff_interpol=_aeff,
        e_0=_energy_range[0]*5.,
        n_points_to_plot=num_points,
        fmt='r',
        label=''
    )
    energy_support_GeV = 1e3*_energy_support_TeV
    differential_flux_per_GeV_per_s_per_m2 = 1e-3*1e4*(
        _differential_flux_per_TeV_per_s_per_cm2
    )
    return energy_support_GeV, differential_flux_per_GeV_per_s_per_m2



def fermi_lat_integral_spectral_exclusion_zone():
    '''
    https://www.slac.stanford.edu/exp/glast/groups/canda/lat_Performance_files/
        broadband_flux_sensitivity_p8r3_source_v2_10yr_zmax100_n10.0_e1.50_ts25_000_090.txt
    '''
    # broadband_flux_sensitivity_p8r2_source_v6_all_10yr_zmax100_n10.0_e1.50_ts25_000_090
    # (l, b) = (0, 90)
    # Column 0: Energy [MeV]
    # Column 1: E^2 times Broadband Flux Sensitivity [erg cm^{-2} s^{-1}]

    data = np.array([
        [31.623, 6.9842e-12],
        [35.112, 5.9694e-12],
        [38.986, 5.1021e-12],
        [43.288, 4.3608e-12],
        [48.064, 3.7272e-12],
        [53.367, 3.1857e-12],
        [59.255, 2.7229e-12],
        [65.793, 2.3272e-12],
        [73.053, 1.9891e-12],
        [81.113, 1.7062e-12],
        [90.063, 1.4784e-12],
        [100, 1.2909e-12],
        [111.03, 1.1385e-12],
        [123.28, 1.0094e-12],
        [136.89, 8.9963e-13],
        [151.99, 8.0689e-13],
        [168.76, 7.2671e-13],
        [187.38, 6.5663e-13],
        [208.06,  5.976e-13],
        [231.01, 5.4388e-13],
        [256.5, 4.9804e-13],
        [284.8, 4.5803e-13],
        [316.23, 4.2124e-13],
        [351.12, 3.8926e-13],
        [389.86, 3.6176e-13],
        [432.88, 3.3621e-13],
        [480.64, 3.1245e-13],
        [533.67, 2.9342e-13],
        [592.55, 2.7556e-13],
        [657.93, 2.5879e-13],
        [730.53, 2.4386e-13],
        [811.13, 2.3143e-13],
        [900.63, 2.1963e-13],
        [1000, 2.0843e-13],
        [1110.3, 1.9901e-13],
        [1232.8, 1.9085e-13],
        [1368.9, 1.8303e-13],
        [1519.9, 1.7552e-13],
        [1687.6, 1.6985e-13],
        [1873.8,  1.646e-13],
        [2080.6, 1.5952e-13],
        [2310.1, 1.5494e-13],
        [2565, 1.5173e-13],
        [2848, 1.4858e-13],
        [3162.3, 1.4551e-13],
        [3511.2, 1.4345e-13],
        [3898.6, 1.4196e-13],
        [4328.8, 1.4048e-13],
        [4806.4, 1.3914e-13],
        [5336.7, 1.3914e-13],
        [5925.5, 1.3914e-13],
        [6579.3, 1.3923e-13],
        [7305.3, 1.4069e-13],
        [8111.3, 1.4217e-13],
        [9006.3, 1.4367e-13],
        [10000, 1.4518e-13],
        [11103, 1.4714e-13],
        [12328, 1.5025e-13],
        [13689, 1.5343e-13],
        [15199, 1.5687e-13],
        [16876, 1.6187e-13],
        [18738, 1.6703e-13],
        [20806, 1.7236e-13],
        [23101, 1.7853e-13],
        [25650, 1.8616e-13],
        [28480, 1.9412e-13],
        [31623, 2.0242e-13],
        [35112, 2.1251e-13],
        [38986, 2.2393e-13],
        [43288, 2.3596e-13],
        [48064, 2.4884e-13],
        [53367, 2.6496e-13],
        [59255, 2.8214e-13],
        [65793, 3.0042e-13],
        [73053,  3.224e-13],
        [81113, 3.4691e-13],
        [90063, 3.7328e-13],
        [1e+05, 4.0471e-13],
        [1.1103e+05, 4.4005e-13],
        [1.2328e+05, 4.7872e-13],
        [1.3689e+05, 5.2601e-13],
        [1.5199e+05, 5.7797e-13],
        [1.6876e+05, 6.3988e-13],
        [1.8738e+05, 7.1048e-13],
        [2.0806e+05, 7.9488e-13],
        [2.3101e+05, 8.9208e-13],
        [2.565e+05, 1.0115e-12],
        [2.848e+05, 1.1537e-12],
        [3.1623e+05, 1.3267e-12],
        [3.5112e+05, 1.5408e-12],
        [3.8986e+05, 1.8027e-12],
        [4.3288e+05, 2.1091e-12],
        [4.8064e+05, 2.4677e-12],
        [5.3367e+05, 2.8871e-12],
        [5.9255e+05, 3.3779e-12],
        [6.5793e+05, 3.9521e-12],
        [7.3053e+05, 4.6239e-12],
        [8.1113e+05,   5.41e-12],
        [9.0063e+05, 6.3296e-12],
        [1e+06, 7.4055e-12],
    ])

    # 1 erg = 0.62415091 TeV
    ERG_OVER_GEV = 624.15091

    base_energy_x_in_GeV = 1e-3  # in MeV
    base_energy_y_in_GeV = ERG_OVER_GEV  # in ergs
    power_slope = 2.0
    base_area_in_m2 = 1e-4  # in cm2
    base_time_s = 1.0

    # convert energy axis to energy used on y axis
    data[:, 0] = data[:, 0]*base_energy_x_in_GeV
    data[:, 0] = data[:, 0]/base_energy_y_in_GeV

    # convert to normal flux, then convert to cm^2, convert to per TeV
    data[:, 1] = data[:, 1]/(data[:, 0]**power_slope)
    data[:, 1] = data[:, 1]/base_area_in_m2
    data[:, 1] = data[:, 1]/base_energy_y_in_GeV
    data[:, 1] = data[:, 1]/base_time_s

    # convert energy axis to GeV scale
    data[:, 0] = data[:, 0]*base_energy_y_in_GeV

    return {
        "energy": {
            "values": data[:, 0].tolist(),
            "unit_tex": "GeV",
            "unit": "GeV",
        },
        "differential_flux": {
            "values": data[:, 1].tolist(),
            "unit_tex": "m$^{-2}$ s$^{-1}$ GeV$^{-1}$",
            "unit": "per_m2_per_s_per_GeV"
        },
        "title": "Fermi-LAT broadband flux sensitivity 10years, "
            "P8R2, l=0deg, b=90deg.",
    }