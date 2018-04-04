#!/usr/bin/env python
""" Extracts the electrostatic potential (ESP) from a GPAW .gpw restart file given as command line argument. """
#setup the gpaw calculation

from ase.io import read
from ase.io import write

from gpaw import GPAW
from gpaw import restart

from ase.units import Bohr
from ase.units import Hartree
import numpy as np

import argparse

parser = argparse.ArgumentParser(description='Extracts the electrostatic'
        ' potential (ESP) from a GPAW .gpw restart file given as command line'
        ' argument.')
parser.add_argument('infile')
parser.add_argument('outfile_cube', nargs='?', metavar='outfile.cube', 
        default='esp.cube', help="Electrostatic potential in GAUSSIAN-native"
        " .cube format, default 'esp.cube'")
parser.add_argument('outfile_csv', nargs='?', metavar='outfile.csv', 
        default='esp.csv', help="Electrostatic potential and x,y,z coordinates"
                " as four-valued lines of .8 digits precision mantissa"
                " notation, default 'esp.csv'")
parser.add_argument('outfile_rho_cube', nargs='?', metavar='outfile_rho.cube',
        default='rho.cube', help="All-electron density in GAUSSIAN-native .cube"
        " format, default 'rho.cube'")
parser.add_argument('outfile_rho_pseudo_cube', nargs='?', 
        metavar='outfile_rho_pseudo.cube', default='rho_pseudo.cube',
        help="All-electron density in GAUSSIAN-native .cube format, default"
        "'rho_pseudo.cube'")

args = parser.parse_args()

gpw_file = args.infile
print("Reading input file '{}'".format(gpw_file))

# The file .gpw is a binary file containing wave functions, densities, positions and everything else (also the 
# parameters characterizing the PAW calculator used for the calculation).
# source: https://wiki.fysik.dtu.dk/gpaw/documentation/manual.html#restarting-a-calculation
struc, calc = restart(gpw_file)

phi = calc.get_electrostatic_potential()
# potential query comes from gpaw/hamiltonian.py
#     def get_electrostatic_potential(self, dens):
#        self.update(dens)
#
#        v_g = self.finegd.collect(self.vHt_g, broadcast=True)
#        v_g = self.finegd.zero_pad(v_g)
#        if hasattr(self.poisson, 'correction'):
#            assert self.poisson.c == 2
#            v_g[:, :, 0] = self.poisson.correction
#        return v_g
#
# A comment from the same file ...
#    The XC-potential and the Hartree potential are evaluated on the fine grid, and the sum is then restricted
#    to the coarse grid.
# ... and a note from https://wiki.fysik.dtu.dk/gpaw/algorithms.html?highlight=fine%20grid ...
#    Finite-difference (FD):
#    Uniform real-space orthorhombic grids. Two kinds of grids are involved in the calculations:
#    A coarse grid used for the wave functions and a fine grid (23=8 times higher grid point density) used for
#    densities and potentials. The pseudo electron density is first calculated on the coarse grid from the wave
#    functions, and then interpolated to the fine grid, where compensation charges are added for achieving
#    normalization. The effective potential is evaluated on the fine grid (solve the Poisson equation and calculate
#    the exchange-correlation potential) and then restricted to the coarse grid where it needs to act on the wave
#    functions (also on the coarse grid).
# ... tell us: potential has twice as many grid points in each spatial dimension as the actual number of coarse grid
# points queried by "calc.get_number_of_grid_points()"
nX = phi.shape # = 2 * calc.get_number_of_grid_points()
X = struc.cell.diagonal()
x_grid = np.linspace(0,X[0],nX[0])
y_grid = np.linspace(0,X[1],nX[1])
z_grid = np.linspace(0,X[2],nX[2])

x_grid3,y_grid3,z_grid3=np.meshgrid(x_grid,y_grid,z_grid)

# https://theochem.github.io/horton/2.1.0b3/lib/mod_horton_units.html?highlight=units#module-horton.units
# apparently, Horton internally uses atomic units.
# If this applies strictly, we have electron mass m_e = 1, electron charge e = 1,
# reduced Planck's constant h_bar = 1 and Coulomb force constant k_e = 1 / (4 Pi eps_0 ) = 1 per definition
# Furthermore, it should expect
# length in Bohr (a_0) , defined as 4 Pi eps_0 h_bar^2 / (m_e e^2) = 1
# energy in Hartree (E_h), defined as m_e e^4 / (4 Pi eps_0 h_bar)^2 = 1
# electric potential, defined as E_h / e = 1

# thus, GPAW potential in units of "eV"
# are to be converted to units of "E_h / e = m_e e^3 / (4 Pi eps_0 h_bar)^2"
#     U_hor = U_gpw * E_h / (e*eV)
# we use
#    ase.units.Hartree = 27.211386024367243 (eV)
phi_hartree = phi / Hartree

# put potential in grid points and xyz-coordinates in csv-file format (four %.8e values, seperated by whitespace)
#as expected by resp FORTRAN code 2.1 (October 1994 Jim Caldwell)
dat = np.vstack( ( phi_hartree.flatten(), x_grid3.flatten()/Bohr, y_grid3.flatten()/Bohr, z_grid3.flatten()/Bohr ) ).T
# spatial units are converted to Bohr. What unit is the potential?
# Division (not multiplication)  is necessary here, as ase.units.Bohr is defined as
#     u['Bohr'] = (4e10 * pi * u['_eps0'] * u['_hbar']**2 / u['_me'] / u['_e']**2)  # Bohr radius
# with unit [ Bohr ] = Angstrom / Bohr
#     ase.units.Bohr = 0.5291772105638411 (Ang)

write(args.outfile_cube, struc, data=phi_hartree) # apparently the native GAUSSIAN format for ESP, readible by Horton
np.savetxt(args.outfile_csv,dat,fmt='%.8e',delimiter=' ')

# the code below could be used to interpolate the potential onto a coarser or finer grid
# however, I got errors (most of the time)

# Transformer:
# t = PS2AE(calc, h=0.4)

# phi_grid_ps = t.get_electrostatic_potential(ae=False) # pseude wave-functions
# phi_grid_ae = t.get_electrostatic_potential() # all-electron wave-functions

# x_grid3,y_grid3,z_grid3=np.meshgrid(t.gd.coords(0)*Bohr,t.gd.coords(1)*Bohr,t.gd.coords(2)*Bohr)

# dat_ae = np.array( [ phi_grid_ae.flatten(), x_grid3.flatten(), y_grid3.flatten(), z_grid3.flatten() ] )
# np.savetxt('phi_grid_ae.csv',dat_ae.T,fmt='%.8e',delimiter=' ')

# dat_ps = np.array( [ phi_grid_ps.flatten(), x_grid3.flatten(), y_grid3.flatten(), z_grid3.flatten() ] )
# np.savetxt('phi_grid_ps.csv',dat_ps.T,fmt='%.8e',delimiter=' ')



# https://wiki.fysik.dtu.dk/gpaw/tutorials/bader/bader.html#bader-analysis


rho_pseudo      = calc.get_pseudo_density()
rho             = calc.get_all_electron_density()
# https://wiki.fysik.dtu.dk/gpaw/tutorials/all-electron/all_electron_density.html:
# As the all-electron density has more structure than the pseudo-density, it is
# necessary to refine the density grid used to represent the pseudo-density.
# This can be done using the gridrefinement keyword of the
# get_all_electron_density method:
#
# >>> n = calc.get_all_electron_density(gridrefinement=2)
#
# Current only the values 1, 2, and 4 are supported (2 is default).
rho_pseudo_per_bohr_cube = rho_pseudo * Bohr**3
rho_per_bohr_cube = rho * Bohr**3
write(args.outfile_rho_cube, struc, data=rho_per_bohr_cube) 
write(args.outfile_rho_pseudo_cube, struc, data=rho_pseudo_per_bohr_cube) 

