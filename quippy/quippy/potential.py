"""
ASE-compatible Calculator from a quip-potential object

"""

import ase
import ase.calculators.calculator
import numpy as np

import _quippy
import quippy


class potential(ase.calculators.calculator.Calculator):

    callback_map = {}

    implemented_properties = ['energy', 'forces']
    # earlier in quippy
    # ['energy', 'energies', 'forces', 'stress', 'stresses',
    #  'numeric_forces', 'elastic_constants',
    #  'unrelaxed_elastic_constants']

    def __init__(self, args_str, param_str, atoms=None, **kwargs):

        # update_docstring not implemented yet, it was oo_quip.update_doc_string() in the earlier version

        """

        from quip_docstring:

        args_str : str
            Valid arguments are 'Sum', 'ForceMixing', 'EVB', 'Local_E_Mix' and 'ONIOM', and any type of simple_potential
        param_str : str
            contents of xml parameter file for potential initializers, if needed

        -----------------------------------------------------------------------

        ase calculator has the following arguments for initialisation:

        let's not care about files for now, so just take them as None

        nay     restart: str
                    Prefix for restart file.  May contain a directory.  Default
                    is None: don't restart.
        nay     ignore_bad_restart_file: bool
                    Ignore broken or missing restart file.  By default, it is an
                    error if the restart file is missing or broken.
        nay     label: str
                    Name used for all files.  May contain a directory.
                atoms: Atoms object
                    Optional Atoms object to which the calculator will be
                    attached.  When restarting, atoms will get its positions and
                    unit-cell updated from file.

        ------------------------------------------------------------------------
        from old quippy arguments:

        used:
            init_args=None, param_str=None, atoms=None

        not used:
            calculator=None
            fpointer=None
            error=None

        not implemented yet:
            pot1=None, pot2=None
            param_filename=None
            bulk_scale=None
            mpi_obj=None
            callback=None
            calculation_always_required=False
            finalise=True
                """

        ase.calculators.calculator.Calculator.__init__(self, restart=None, ignore_bad_restart_file=False, label=None,
                                                       atoms=atoms, **kwargs)
        # init the quip potential
        self._quip_potential = quippy.potential_module.Potential(args_str=args_str, param_str=param_str)
        # init the quip atoms as None, to have the variable
        self._quip_atoms = None

        # from old
        if atoms is not None:
            atoms.set_calculator(self)
        self.name = args_str

        pass

    def calculate(self, atoms=None, properties=None,
                  system_changes=None):
        """Do the calculation.

        properties: list of str
            List of what needs to be calculated.  Can be any combination
            of 'energy', 'forces', 'stress', 'dipole', 'charges', 'magmom'
            and 'magmoms'.
        system_changes: list of str
            List of what has changed since last calculation.  Can be
            any combination of these six: 'positions', 'numbers', 'cell',
            'pbc', 'initial_charges' and 'initial_magmoms'.

        Subclasses need to implement this, but can ignore properties
        and system_changes if they want.  Calculated properties should
        be inserted into results dictionary like shown in this dummy
        example::

            self.results = {'energy': 0.0,
                            'forces': np.zeros((len(atoms), 3)),
                            'stress': np.zeros(6),
                            'dipole': np.zeros(3),
                            'charges': np.zeros(len(atoms)),
                            'magmom': 0.0,
                            'magmoms': np.zeros(len(atoms))}

        The subclass implementation should first call this
        implementation to set the atoms attribute.



        from docstring of quippy.potential_module.Potential.calc

        Each physical quantity has a
corresponding optional argument, which can either be an 'True'
to store the result inside the Atoms object (i.e. in
Atoms%params' or in 'Atoms%properties' with the
default name, a string to specify a different property or
parameter name, or an array of the the correct shape to
receive the quantity in question, as set out in the table
below.

        ================ ============= ================ =========================
        Array argument Quantity Shape Default storage location
        ================ ============= ================ =========================
        ``energy``        Energy        ``()``                  ``energy`` param
        ``local_energy`` Local energy ``(at.n,)`` ``local_energy`` property
        ``force``         Force         ``(3,at.n)``     ``force`` property
        ``virial``        Virial tensor ``(3,3)``        ``virial`` param
        ``local_virial`` Local virial ``(3,3,at.n)`` ``local_virial`` property
        ================ ============= ================ =========================


        """

        # handling the property inputs
        if properties is None:
            properties = ['energy', 'forces']
            #properties = ['energy', 'forces', 'stress']

        if len(properties) == 0:
            raise RuntimeError('Nothing to calculate')

        for property in properties:
            if property not in self.implemented_properties:
                raise RuntimeError("Don't know how to calculate property '%s'" % property)

        if atoms is not None:
            self.atoms = atoms.copy()

        ase.calculators.calculator.Calculator.calculate(self, atoms, properties, system_changes)
        if not self.calculation_required(atoms, properties):
            # fixme: is this required+correct?
            return

        # construct the quip atoms object which we will use to calculate on
        self._quip_atoms = quippy.convert.ase_to_quip(self.atoms, self._quip_atoms)

        # construct adequate arrays to put the results into
        energy = 0
        local_energy = np.zeros(self._quip_atoms.n, order='F')
        force = np.zeros((3, self._quip_atoms.n), order='F')
        virial = np.zeros((3, 3), order='F')
        local_virial = np.zeros((9, self._quip_atoms.n), order='F')

        # perform the calculation
        energy, _ferror = self._quip_potential.calc(self._quip_atoms, force=force, virial=virial,
                                                    local_energy=local_energy, local_virial=local_virial)

        # store the results according to ase's standards
        self.results = {'energy': energy,
                        'forces': np.copy(force.T),
                        'virial': virial,
                        'local_energy': local_energy,
                        'local_virial': local_virial
                        }

        # TODO: add logic for what to calculate and what not

        if 'stress' in properties:
            stress = -virial.copy() / self._quip_atoms.get_volume()
            # convert to 6-element array in Voigt order
            self.results['stress'] = np.array([stress[0, 0], stress[1, 1], stress[2, 2],
                                               stress[1, 2], stress[0, 2], stress[0, 1]])

