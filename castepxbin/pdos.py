"""
Reader module for CASTEP pdos_bin

Written based on the example `pdos_bin.f90` file in open-source OptaDos code
"""
from enum import Enum, unique
import numpy as np
from scipy.io import FortranFile


@unique
class SpinEnum(Enum):
    """
    Enum type for Spin.  Only up and down.
    Usage: Spin.up, Spin.down.
    """
    up, down = (1, -1)

    def __int__(self):
        return self.value

    def __float__(self):
        return float(self.value)

    def __str__(self):
        return str(self.value)


@unique
class OrbitalType(Enum):
    """
    Enum type for orbital type. Indices are basically the azimuthal quantum
    number, l.
    """

    s = 0
    p = 1
    d = 2
    f = 3

    def __str__(self):
        return str(self.name)



@unique
class OrbitalEnum(Enum):
    """
    Enum type for specific orbitals. The value are the name reported by CASTEP.
    """

    s = "S"
    px = "Px"
    py = "Py"
    pz = "Pz"
    dxy = "Dxy"
    dyz = "Dzy"
    dz2 = "Dzz"
    dxz = "Dzx"
    dx2 = "Dxx-yy"
    f_xxx = "Fxxx"
    f_yyy = "Fyyy"
    f_zzz = "Fzzz"
    f_xyz = "Fxyz"
    f_z_xx_yy = "Fz(xx-yy)"
    f_y_zz_xx = "Fy(zz-xx)"
    f_x_yy_zz = "Fx(yy-zz)"

    def __int__(self):
        return self.value

    def __str__(self):
        return str(self.name)

    @property
    def orbital_type(self):
        """
        Returns OrbitalType of an orbital.
        """
        return OrbitalType[self.name[0]]


def read_pdos_bin(filename, endian='big'):
    """
    Read the pdos_bin file generated by CASTEP Spectral task.

    Args:
        filename (str): name of the file to be read

    Returns:
        A dictionary of the data that have been read.
        the weights of each orbital in stored in the 'pdos_weights' array
        with dimension (n_orbital, n_max_eign, n_kpoints, n_spin)
    """
    esymbol = '>' if endian.upper() == 'BIG' else '>'
    dint = np.dtype(esymbol + 'i4')
    ddouble = np.dtype(esymbol + 'f8')
    dch80 = np.dtype(esymbol + 'a80')
    diarray = lambda x: '{}({},)i4'.format(esymbol, x)
    ddarray = lambda x: '{}({},)f8'.format(esymbol, x)

    with FortranFile(filename, header_dtype=np.dtype('>u4')) as fhandle:
        fversion = fhandle.read_record(ddouble)[0]
        fheader = fhandle.read_record(dch80)[0].decode()
        num_kpoints = fhandle.read_record(dint)[0]
        num_spins = fhandle.read_record(dint)[0]
        num_popn_orb = fhandle.read_record(dint)[0]
        max_eignenv = fhandle.read_record(dint)[0]

        # Now we start to read more data
        species = fhandle.read_record(diarray(num_popn_orb))
        ion = fhandle.read_record(diarray(num_popn_orb))
        am_channel = fhandle.read_record(diarray(num_popn_orb))

        # Now we initialize the storage space for the weights
        pdos_weights = np.zeros(
            (num_popn_orb, max_eignenv, num_kpoints, num_spins),
            dtype=np.float)

        kpoint_positions = np.zeros((num_kpoints, 3), dtype=np.float)
        num_eigenvalues = np.zeros(num_spins, dtype=np.int)
        # Now we start to read the actual data
        for nk in range(num_kpoints):
            _, kpoint_positions[nk, :] = fhandle.read_record('>i4', '>(3,)f8')
            for ns in range(num_spins):
                _ = fhandle.read_record(dint)
                num_eigenvalues[ns] = fhandle.read_record(dint)
                for nb in range(num_eigenvalues[ns]):
                    pdos_weights[:, nb, nk, ns] = fhandle.read_record(
                        '>({},)f8'.format(num_popn_orb))

    output = {
        'fversion': fversion,
        'fheader': fheader,
        'num_kpoints': num_kpoints,
        'num_spins': num_spins,
        'num_popn_orb': num_popn_orb,
        'max_eigenenv': max_eignenv,
        'species': species,
        'ion': ion,
        'am_channel': am_channel,
        'pdos_weights': pdos_weights,
        'kpoints_positions': kpoint_positions,
        'num_eigenvalues': num_eigenvalues,
        'pdos_weights': pdos_weights,
    }
    return output

def reorder_pdos_data(input_items, pymatgen_labels=True, use_string_as_keys=False):
    """
    Arrange the PDOS weights so it is more meaningful

    The result can be used to compute PDOS for creating CompleteDos object
    that can be used for Pymatgen

    Args:
        input_items (dict): A dictionary of the pdos information, use the
        output of  `read_pdos` function. 
        pymatgen_labels (bool): Use pymatgen Enum as the keys of the result dictionary. 
        

    Returns:
        A dictionary of {Site_index: {Orbital: {Spin: weight}}}
    """
    if pymatgen_labels is True:
        try:
            from pymatgen.electronic_structure.core import Orbital as POrbital
            from pymatgen.electronic_structure.core import Spin as PSpin
        except ImportError:
            pymatgen_labels = False

    if pymatgen_labels:
        # Note that s-p labels are inferreed from dot castep output
        # f labels - I know the first three is among the first three.
        # There is no way to tell if they are correct, f_1 is not very informative from VASP....
        orbital_mapping = [[POrbital.s], [POrbital.px, POrbital.py, POrbital.pz],
                        [
                            POrbital.dz2, POrbital.dyz, POrbital.dxz, POrbital.dx2,
                            POrbital.dxy
                        ],
                        [
                            POrbital.f_1, POrbital.f_2, POrbital.f_3, POrbital.f0,
                            POrbital.f1, POrbital.f2, POrbital.f3
                        ]]
        Spin = PSpin
    else:
        # These are the orders inferred from CASTEP output
        orbital_mapping = [[OrbitalEnum.s], [OrbitalEnum.px, OrbitalEnum.py, OrbitalEnum.pz],
                        [
                            OrbitalEnum.dz2, OrbitalEnum.dyz, OrbitalEnum.dxz, OrbitalEnum.dx2,
                            OrbitalEnum.dxy
                        ],
                        [
                            OrbitalEnum.f_xxx, OrbitalEnum.f_yyy, OrbitalEnum.f_zzz, OrbitalEnum.f_xyz,
                            OrbitalEnum.f_z_xx_yy, OrbitalEnum.f_y_zz_xx, OrbitalEnum.f_x_yy_zz
                        ]]
        Spin = SpinEnum

    # We take average of each kpoints from here
    # One might task why not take account the kpoints weight?
    # because it should be taken account of in the TDOS
    weights = input_items['pdos_weights']
    # Specie index for all orbitals
    species = input_items['species']
    # Index of each ion for all orbitals
    ion = input_items['ion']
    num_spins = input_items['num_spins']
    # Angular momentum channel all orbitals
    am_channel = input_items['am_channel']

    unique_speices = np.unique(species)
    unique_speices.sort()
    site_index = 0
    output_data = {}
    # Initialise storage space
    for specie in unique_speices:
        specie_mask = specie == species
        # Total number of ions for this specie
        total_ions = ion[specie_mask].max()
        # Note that indice are from one, not zero
        for nion in range(1, total_ions + 1):
            # Iterate through each ion
            ion_mask = (ion == nion) & specie_mask
            max_am = am_channel[ion_mask].max()
            site_dict = {}  # {Orbital: {Spin: weight}...}
            for am in range(max_am + 1):
                # Collect the angular momentum channels
                ion_am_mask = (am_channel == am) & ion_mask
                # Indices of each matched channels
                ion_am_idx = np.where(ion_am_mask)[0]
                for iam, iloc in enumerate(ion_am_idx):
                    # iloc - index of the oribtal
                    # You can have 4 orbitals for p channel - they have difference n numbers
                    this_orb = orbital_mapping[am][iam % (2 * am + 1)]
                    orb_dict = {}  # {Spin: weight...}
                    if num_spins == 2:
                        for ispin, espin in enumerate((Spin.up, Spin.down)):
                            # Sumup
                            wtmp = weights[iloc, :, :, ispin]
                            orb_dict[espin] = wtmp
                    else:
                        orb_dict[Spin.up] = weights[iloc, :, :, 0]

                    # Now we have the orb_dict populated
                    # Combined the weights if this orbital has been seen...
                    if this_orb in site_dict:
                        site_dict[this_orb] = _merge_weights(
                            site_dict[this_orb], orb_dict)
                    else:
                        site_dict[this_orb] = orb_dict
            # Now we populated site_dict add it to output_data
            output_data[site_index] = site_dict
            site_index += 1

    return output_data


def compute_pdos(pdos_bin, eigenvalues, kpoints_weights, bins):
    """
    Compute the PDOS from eigenvalue and kpoint weights
    
    Args:
        pdos_bin (str): Path to the binary pdos_bin file
        eigenvealues (str): Eigenvalue as {Spin: array_)}.
        kpoints_weights (np.ndarray): Weights of each kpoints.
        bins: The bins for computing the density of states.
    """

    # Walk through the ordred_weights dictionary and compute PDOS for each weight
    ordered_weights = reorder_pdos_data(read_pdos_bin(pdos_bin))
    pdos_data = {}
    for site, porbs_dict in ordered_weights.items():
        porbs_outdict = {}
        for orb, pspin_dict in porbs_dict.items():
            pdos_orbit = {
                spin: np.histogram(
                    eigenvalue_set,
                    bins=bins,
                    weights=kpoints_weights * pspin_dict[
                        spin]  # weight (nk, ); pspin_dict[spin] (nk, nb)
                )[0]
                for spin, eigenvalue_set in eigenvalues.items()
            }
            porbs_outdict[orb] = pdos_orbit
        pdos_data[site] = porbs_outdict
    return pdos_data


def _merge_weights(spin_d1, spin_d2):
    """Sum the weights stored in two dictionaries with keys being the spins"""
    if len(spin_d1) != len(spin_d2):
        raise RuntimeError("Critical - mismatch spin-dict length")
    out = {}
    for spin in spin_d1:
        out[spin] = spin_d1[spin] + spin_d2[spin]
    return out
