#! /usr/bin/env python
import os
from subprocess import call

call(['pip', 'uninstall', 'corsika_primary_wrapper'])
call(['pip', 'uninstall', 'plenopy'])
call(['pip', 'uninstall', 'gamma_limits_sensitivity'])
call(['pip', 'uninstall', 'acp_instrument_response_function'])
call(['pip', 'uninstall', 'acp_instrument_sensitivity_function'])
call(['pip', 'uninstall', 'reflector_study'])
call(['pip', 'uninstall', 'plenoscope_map_reduce'])
call(['pip', 'uninstall', 'simpleio'])
call(['rm', '-rf', 'build'])
