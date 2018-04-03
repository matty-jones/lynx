import mbuild as mb
import numpy as np
import argparse
import copy
import os
from lynx.definitions import PDB_LIBRARY, FF_LIBRARY
import xml.etree.cElementTree as ET
from collections import OrderedDict


# The crystallographic unit cell parameters
# Taken from Desanto2006 (10.1007/s11244-006-0068-8)
x_extent = 2.148490
y_extent = 2.664721
z_extent = 0.400321

# Set the defaults for all the required arguments
defaults_dict = {'stoichiometry': {'Mo': 1, 'V': 0.3, 'Nb': 0.15, 'Te': 0.15},
                 'dimensions': [1, 1, 1],
                 'template': 'templateM1.pdb',
                 'organic': 'ethane.pdb',
                 'crystal_separation': 25.0,
                 'z_box_size': 20.0,
                 'bonds_periodic': True,
                 'number_of_organic_mols': 200,
                 'forcefield': None}


class m1_unit_cell(mb.Compound):
    # This class will contain the unit cell for manipulation and replication
    def __init__(self, template, stoichiometry_dict):
        # Call the mb.Compound initialisation
        super().__init__()
        # Load the unit cell
        mb.load(os.path.join(PDB_LIBRARY, template), compound=self)
        # Replacable atoms in the matrix are assigned as type `X'
        # Note: In both Py2 and Py3, subsequent calls to keys() and values()
        # with no intervening modifications will directly correspond
        # \cite{PyDocumentation}
        atom_types = list(stoichiometry_dict.keys())
        atom_ratios = np.array(list(stoichiometry_dict.values()))
        probabilities = list(atom_ratios / np.sum(atom_ratios))
        for particle in self.particles():
            if particle.name == 'X':
                # `Randomly' select an atom type based on the biases given in
                # stoichiometry_dict
                particle.name = np.random.choice(atom_types, p=probabilities)
        # # Check all the 'X' atom_types got updated
        # assert('X' not in [particle.name for particle in self.particles()])


class m1_surface(mb.Compound):
    # This class will describe the surface and consist of several m1_unit_cell
    # instances in a specified dimension
    # Default stoichiometry found in: Nanostructured Catalysts: Selective
    # Oxidations (Hess and Schl\"ogl, 2011, RSC)
    def __init__(self, surface_dimensions, template, stoichiometry_dict):
        # Call the mb.Compound initialisation
        super().__init__()
        # OUTER LOOP: Create multiple layers based on the input dimensions
        for z_repeat in range(surface_dimensions[2]):
            # MIDDLE LOOP: Multiply up each x_row to create as many y repeats
            # as specified
            # complete_cell_matrix is required to keep track of new bonds
            # across diagonal elements
            complete_cell_matrix = []
            previous_row = None
            for y_repeat in range(surface_dimensions[1]):
                current_row = []
                # INNER LOOP: First, create as many x repeats as specified
                # Note: Each cell has 159 atoms in it
                previous_cell = None
                for x_repeat in range(surface_dimensions[0]):
                    print("\rAdding " + repr([x_repeat, y_repeat, z_repeat])
                          + " to system...", end=" ")
                    current_cell = m1_unit_cell(template, stoichiometry_dict)
                    current_row.append(current_cell)
                    current_cell.translate([x_repeat * x_extent,
                                            y_repeat * y_extent,
                                            z_repeat * z_extent])
                    self.add(current_cell)
                    if previous_cell is not None:
                        self.add_x_connecting_bonds(previous_cell,
                                                    current_cell)
                    previous_cell = current_cell
                if previous_row is not None:
                    for cell_ID, current_cell_y in enumerate(current_row):
                        previous_cell_y = previous_row[cell_ID]
                        self.add_y_connecting_bonds(previous_cell_y,
                                                    current_cell_y)
                complete_cell_matrix.append(current_row)
                previous_row = current_row
            # Now that the cell_matrix is complete for this layer, there might
            # be a few more bonds to add in.
            # Go across all rows first
            for y_coord in range(surface_dimensions[1]):
                # Now each column
                for x_coord in range(surface_dimensions[0]):
                    # Bonds located across the diagonals (i.e. [0, 0] bonded
                    # to [1, 1]; [0, 1] bonded to [1, 2] etc.)
                    if (x_coord + 1 < surface_dimensions[0])\
                       and (y_coord + 1 < surface_dimensions[1]):
                        first_cell = complete_cell_matrix[x_coord][y_coord]
                        second_cell = complete_cell_matrix[
                            x_coord + 1][y_coord + 1]
                        self.add_diagonal_connecting_bonds(first_cell,
                                                           second_cell)
        print()

    def add_x_connecting_bonds(self, cell1, cell2):
        self.add_bond([cell1[60], cell2[21]])
        self.add_bond([cell1[137], cell2[13]])
        self.add_bond([cell1[134], cell2[16]])
        self.add_bond([cell1[122], cell2[16]])
        self.add_bond([cell1[19], cell2[119]])
        self.add_bond([cell1[66], cell2[33]])
        self.add_bond([cell1[18], cell2[65]])

    def add_y_connecting_bonds(self, cell1, cell2):
        self.add_bond([cell1[72], cell2[27]])
        self.add_bond([cell1[1], cell2[58]])
        self.add_bond([cell1[1], cell2[73]])
        self.add_bond([cell1[4], cell2[123]])
        self.add_bond([cell1[4], cell2[141]])
        self.add_bond([cell1[6], cell2[141]])
        self.add_bond([cell1[6], cell2[156]])
        self.add_bond([cell1[114], cell2[12]])
        self.add_bond([cell1[159], cell2[12]])

    def add_diagonal_connecting_bonds(self, cell1, cell2):
        self.add_bond([cell1[61], cell2[21]])


class m1_system(mb.Compound):
    # This class will describe the surface and consist of several m1_unit_cell
    # instances in a specified dimension
    # Default stoichiometry found in: Nanostructured Catalysts: Selective
    # Oxidations (Hess and Schl\"ogl, 2011, RSC)
    def __init__(self, bottom_crystal, top_crystal, crystal_separation,
                 solvent):
        # Call the mb.Compound initialisation
        super().__init__()
        # Firstly, get the current COM positions for each plane. This will be
        # important later
        top_COM = copy.deepcopy(top_crystal.pos)
        bottom_COM = copy.deepcopy(bottom_crystal.pos)
        # Then, center both crystals according to their center of geometry
        # (we don't care about masses here)
        top_crystal.translate(-top_crystal.pos)
        bottom_crystal.translate(-bottom_crystal.pos)
        # Now the top crystal is centered at the origin, we have no issues
        # flipping it around
        top_crystal.rotate(np.pi, [1, 0, 0])
        # Now shift both crystals in the z-direction away from each other by
        # the (crystal_separation/2.0)
        # Note that crystal_separation is given in Angstroems but currently
        # in nm
        bottom_crystal.translate([0, 0, crystal_separation / 20.0])
        top_crystal.translate([0, 0, -crystal_separation / 20.0])
        # Add both crystal planes to the system
        self.add(bottom_crystal)
        self.add(top_crystal)
        # Finally, add the solvent
        if solvent is not None:
            self.add(solvent)


class mbuild_template(mb.Compound):
    # This class will contain the mb compound for hydrocarbon
    def __init__(self, template):
        # Call the mb.Compound initialisation
        super().__init__()
        # Load the unit cell
        mb.load(os.path.join(PDB_LIBRARY, template), compound=self)


def create_morphology(args):
    output_file = create_output_file_name(args)
    print("Generating first surface (bottom)...")
    surface1 = m1_surface(args.dimensions, args.template, args.stoichiometry)
    print("Generating second surface (top)...")
    surface2 = m1_surface(args.dimensions, args.template, args.stoichiometry)
    if args.number_of_organic_mols > 0:
        # Now we can populate the box with hydrocarbons
        print("Surfaces generated. Generating hydrocarbons...")
        hydrocarbon = mbuild_template(args.organic)
        # Define the regions that the hydrocarbons can go in, so we don't end
        # up with them between layers
        box_top = mb.Box(mins=[-(x_extent * args.dimensions[0]) / 2.0,
                               -(y_extent * args.dimensions[1]) / 2.0,
                               args.crystal_separation / 20.0
                               + (z_extent * args.dimensions[2])],
                         maxs=[(x_extent * args.dimensions[0]) / 2.0,
                               (y_extent * args.dimensions[1]) / 2.0,
                               args.z_box_size / 2.0])
        box_bottom = mb.Box(mins=[-(x_extent * args.dimensions[0]) / 2.0,
                                  -(y_extent * args.dimensions[1]) / 2.0,
                                  -args.z_box_size / 2.0],
                            maxs=[(x_extent * args.dimensions[0]) / 2.0,
                                  (y_extent * args.dimensions[1]) / 2.0,
                                  -args.crystal_separation / 20.0
                                  - (z_extent * args.dimensions[2])])
        solvent = mb.packing.fill_region([hydrocarbon] * 2,
                                         [args.number_of_organic_mols // 2]
                                         * 2,
                                         [box_bottom, box_top])
    else:
        solvent = None
    # Now create the system by combining the two surfaces and the solvent
    system = m1_system(surface1, surface2, args.crystal_separation, solvent)
    # Generate the morphology box based on the input parameters
    system_box = mb.Box(mins=[-(x_extent * args.dimensions[0]) / 2.0,
                              -(y_extent * args.dimensions[1]) / 2.0,
                              -args.z_box_size / 2.0],
                        maxs=[(x_extent * args.dimensions[0]) / 2.0,
                              (y_extent * args.dimensions[1]) / 2.0,
                              args.z_box_size / 2.0])
    print("Morphology generated. Applying forcefield and simulation box...")
    if args.forcefield is not None:
        try:
            # Check the FF library first
            forcefield_loc = os.path.join(FF_LIBRARY, args.forcefield) + '.xml'
            with open(forcefield_loc, 'r') as file_handle:
                pass
        except FileNotFoundError:
            # Otherwise use the cwd
            forcefield_loc = args.forcefield + '.xml'
        system.save(output_file, overwrite=True, box=system_box,
                    forcefield_files=forcefield_loc)
    else:
        system.save(output_file, overwrite=True, box=system_box)
    # Finally, fix the images because mbuild doesn't set them correctly
    fix_images(output_file)
    print("Output generated. Exitting...")


def check_bonds(morphology, bond_dict, box_dims):
    for bond in morphology['bond_text']:
        posn1 = np.array(list(map(float,
                                  morphology['position_text'][int(bond[1])])))
        + (np.array(list(map(float, morphology['image_text'][int(bond[1])])))
           * box_dims)
        posn2 = np.array(list(map(float,
                                  morphology['position_text'][int(bond[2])])))
        + (np.array(list(map(float, morphology['image_text'][int(bond[2])])))
           * box_dims)
        delta_position = posn1 - posn2
        out_of_range = [np.abs(delta_position[axis]) > box_dims[axis] / 2.0
                        for axis in range(3)]
        if any(out_of_range):
            print("Periodic bond found:", bond, "because delta_position =",
                  delta_position, ">=", box_dims, "/ 2.0")
            morphology = move_bonded_atoms(bond[1], morphology, bond_dict,
                                           box_dims)
    return morphology


def zero_out_images(morphology):
    morphology['image_text'] = [['0', '0', '0']]\
        * len(morphology['position_text'])
    morphology['image_attrib'] = {'num': morphology['position_attrib']['num']}
    return morphology


def get_bond_dict(morphology):
    bond_dict = {atom_id: [] for atom_id, atom_type in
                 enumerate(morphology['type_text'])}
    for bond in morphology['bond_text']:
        bond_dict[int(bond[1])].append(int(bond[2]))
        bond_dict[int(bond[2])].append(int(bond[1]))
    return bond_dict


def move_bonded_atoms(central_atom, morphology, bond_dict, box_dims):
    for bonded_atom in bond_dict[central_atom]:
        posn1 = np.array(list(map(float,
                                  morphology['position_text'][central_atom])))
        posn2 = np.array(list(map(float,
                                  morphology['position_text'][bonded_atom])))
        delta_position = posn1 - posn2
        moved = False
        for axis, value in enumerate(delta_position):
            if value > box_dims[axis] / 2.0:
                morphology['position_text'][bonded_atom][axis] = str(
                    posn2[axis] + box_dims[axis])
                moved = True
            if value < -box_dims[axis] / 2.0:
                morphology['position_text'][bonded_atom][axis] = str(
                    posn2[axis] - box_dims[axis])
                moved = True
        if moved:
            morphology = move_bonded_atoms(bonded_atom, morphology, bond_dict,
                                           box_dims)
    return morphology


def load_morphology_xml(xml_file_name):
    morphology_dictionary = OrderedDict()
    with open(xml_file_name, 'r') as xml_file:
        xml_tree = ET.parse(xml_file)
    root = xml_tree.getroot()
    morphology_dictionary['root_tag'] = root.tag
    morphology_dictionary['root_attrib'] = root.attrib
    morphology_dictionary['root_text'] = root.text
    for config in root:
        morphology_dictionary['config_tag'] = config.tag
        morphology_dictionary['config_attrib'] = config.attrib
        morphology_dictionary['config_text'] = config.text
        for child in config:
            if len(child.attrib) > 0:
                morphology_dictionary[child.tag + '_attrib'] = {
                    key.lower(): val for key, val in child.attrib.items()}
            else:
                morphology_dictionary[child.tag + '_attrib'] = {}
            if child.text is not None:
                morphology_dictionary[child.tag + '_text'] = [
                    x.split() for x in child.text.split('\n') if len(x) > 0]
            else:
                morphology_dictionary[child.tag + '_text'] = []
    return morphology_dictionary


def check_wrapped_positions(input_dictionary):
    box_dims = [float(input_dictionary['box_attrib'][axis]) for axis in
                ['lx', 'ly', 'lz']]
    atom_positions = np.array([np.array(list(map(float, _))) for _ in
                               input_dictionary['position_text']])
    atom_images = np.array([np.array(list(map(int, _))) for _ in
                            input_dictionary['image_text']])
    xhi = box_dims[0] / 2.0
    xlo = -box_dims[0] / 2.0
    yhi = box_dims[1] / 2.0
    ylo = -box_dims[1] / 2.0
    zhi = box_dims[2] / 2.0
    zlo = -box_dims[2] / 2.0
    for atom_ID in range(len(atom_positions)):
        while atom_positions[atom_ID][0] > xhi:
            atom_positions[atom_ID][0] -= box_dims[0]
            atom_images[atom_ID][0] += 1
        while atom_positions[atom_ID][0] < xlo:
            atom_positions[atom_ID][0] += box_dims[0]
            atom_images[atom_ID][0] -= 1
        while atom_positions[atom_ID][1] > yhi:
            atom_positions[atom_ID][1] -= box_dims[1]
            atom_images[atom_ID][1] += 1
        while atom_positions[atom_ID][1] < ylo:
            atom_positions[atom_ID][1] += box_dims[1]
            atom_images[atom_ID][1] -= 1
        while atom_positions[atom_ID][2] > zhi:
            atom_positions[atom_ID][2] -= box_dims[2]
            atom_images[atom_ID][2] += 1
        while atom_positions[atom_ID][2] < zlo:
            atom_positions[atom_ID][2] += box_dims[2]
            atom_images[atom_ID][2] -= 1
    input_dictionary['position_text'] = list([list(map(str, _)) for _ in
                                              atom_positions])
    input_dictionary['image_text'] = list([list(map(str, _)) for _ in
                                           atom_images])
    return input_dictionary


def write_morphology_xml(morphology_dictionary, output_file_name):
    # morphology_dictionary is a bunch of keys with the tagnames given for
    # both attributes and text: tag + '_attrib', tag + '_text'
    # The only boilerplate bits are the 'root_tag', 'root_attrib', and
    # 'root_text', which is (obviously) the outmost layer of the xml.
    # Immediately inside are the 'config_tag', 'config_attrib', and
    # 'config_text'. Everything else is a child of config.
    morphology_dictionary = check_wrapped_positions(morphology_dictionary)
    # Build the xml tree.
    root = ET.Element(morphology_dictionary['root_tag'],
                      **morphology_dictionary['root_attrib'])
    root.text = morphology_dictionary['root_text']
    config = ET.Element(morphology_dictionary['config_tag'],
                        **morphology_dictionary['config_attrib'])
    config.text = morphology_dictionary['config_text']
    # Find the remaining elements to make (set is easier here, but a
    # disordered structure, so instead we use lists to keep the order
    # consistent with reading in).
    all_child_tags = ['_'.join(key.split('_')[:-1]) for key in
                      morphology_dictionary.keys()
                      if '_'.join(key.split('_')[:-1]) not in
                      ['root', 'config']]
    child_tags = []
    for tag in all_child_tags:
        # The list comprehension makes two blank entries for some reason and
        # I can't work out why. This will just skip those two entries, as well
        # as make the set.
        if (tag not in child_tags) and (len(tag) > 0):
            child_tags.append(tag)
    for child_tag in child_tags:
        child = ET.Element(child_tag,
                           **morphology_dictionary[child_tag + '_attrib'])
        data_to_write = '\n'.join(['\t'.join(el) for el in
                                   morphology_dictionary[
                                       child_tag + '_text']])
        if len(data_to_write) > 0:
            child.text = '\n' + data_to_write + '\n'
        child.tail = '\n'
        config.append(child)
    root.insert(0, config)
    tree = ET.ElementTree(root)
    tree.write(output_file_name, xml_declaration=True, encoding='UTF-8')
    print("XML file written to", str(output_file_name) + "!")


def fix_images(file_name):
    print("Fixing the images to ensure everything is wrapped within"
          "the box...")
    morphology = load_morphology_xml(file_name)
    morphology = zero_out_images(morphology)
    bond_dict = get_bond_dict(morphology)
    box_dims = [float(morphology['box_attrib'][axis]) for axis in
                ['lx', 'ly', 'lz']]
    morphology = check_bonds(morphology, bond_dict, box_dims)
    write_morphology_xml(morphology, file_name)


def create_output_file_name(args, file_type='hoomdxml'):
    output_file = "out"
    for (arg_name, arg_val) in sorted(args._get_kwargs()):
        print(arg_name, arg_val)
        if (arg_val == defaults_dict[arg_name]):
            continue
        output_file += "_"
        if arg_name == 'stoichiometry':
            output_file += "S"
            for key, val in arg_val.items():
                output_file += str(key) + str(val)
        elif arg_name == 'dimensions':
            output_file += "D" + "x".join(list(map(str, arg_val)))
        elif arg_name == 'template':
            output_file += "T" + args.template.split('/')[-1].split('.')[0]
        elif arg_val is False:
            output_file += arg_name[0].upper() + "Off"
        elif arg_val is True:
            output_file += arg_name[0].upper() + "On"
        else:
            output_file += arg_name[0].upper() + str(arg_val)
    return output_file + '.' + file_type


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--stoichiometry",
                        type=lambda s: {str(key[1:-1]): float(val)
                                        for [key, val] in
                                        [splitChar for splitChar
                                         in [cell.split(':') for cell in [
                                             _ for _ in s[1:-1].split(',')
                                             if len(_) > 0]]
                                         if len(splitChar) > 0]},
                        default={'Mo': 1, 'V': 0.3, 'Nb': 0.15, 'Te': 0.15},
                        required=False,
                        help='''Specify a stoichiometry for the surface.\n
                        Atoms marked as type 'X' in the template will be
                        replaced with atoms of the type given by the keys in
                        the input dictionary, with probabilities determined
                        from the ratios given by the values of the input
                        dictionary.\n
                        For example: -s "{'Mo': 1, 'V': 0.3, 'Nb': 0.15,
                        'Te': 0.15}" will create a surface where there are 5
                        Mo atoms for every V, and 0.85 Nb.\n
                        If not specified, the default stoichiometry is set to
                        {'Mo': 1, 'V': 0.3, ' b': 0.15, 'Te': 0.15}''')
    parser.add_argument("-d", "--dimensions",
                        type=lambda d: [int(dim) for dim in
                                        d.split('x') if len(dim) > 0],
                        default=[1, 1, 1],
                        required=False,
                        help='''Specify the number of cells to stitch into the
                        surface (integers), along the x- and y-directions.\n
                        For example: -d 2x2x1 will create a surface containing
                        4 unit cells, with 2 along the x-axis, 2 along the
                        y-axis, and one layer thick.\n
                        If not specified, the default dimensions are a single
                        unit cell producing a 1x1x1 surface.''')
    parser.add_argument("-t", "--template",
                        type=str,
                        default='M1UnitCell.pdb',
                        required=False,
                        help='''Identify the unit cell file to be used to
                        create the surface.\n
                        Note the unit cells are located in the PDB_LIBRARY
                        directory, which defaults to lynx/compounds.\n
                        For example: -t "M1UnitCell.pdb".\n
                        If not specified, the default
                        PDB_LIBRARY/M1UnitCell.pdb is used.''')
    parser.add_argument("-c", "--crystal_separation",
                        type=float,
                        default=25.0,
                        required=False,
                        help='''Assign a pysical separation (in Angstroems) to
                        the bottom planes of the two crystals corresponding to
                        the top and bottom of the simulation volume within the
                        periodic box.\n
                        Note that this is not the same as the z_box_size, which
                        describes the region available to hydrocarbon molecules
                        in the simulation.\n
                        This value should be larger than the interaction
                        cut-off specified in the forcefield (pair or Coulombic)
                        to prevent the self-interaction of the two
                        surfaces.\n
                        For example: -c 25.0.
                        If not specified, the default value of 2.5 nanometres
                        is used.''')
    parser.add_argument("-z", "--z_box_size",
                        type=float,
                        default=20.0,
                        required=False,
                        help='''Assign the z-axis size of the simulation
                        (in nm).\n
                        This defines the region available for hydrocarbons to
                        move around in, between the two catalyst plates
                        (region depth = z_box_size - plane_separation -
                        (z_extent * dimension[2])).\n
                        Note that this is not the same as the plane_separation,
                        which describes the physical separation between the
                        bottom layers of the two flipped M1 crystals.\n
                        For example: -z 20.0.\n
                        If not specified, the default value of 20 nanometres
                        is used.''')
    parser.add_argument("-o", "--organic",
                        type=str,
                        default='ethane.pdb',
                        required=False,
                        help='''Set the hydrocarbon file to use in the
                        simulation.\n
                        Note that the hydrocarbon files should be located in
                        the PDB_LIBRARY directory, which defaults to
                        lynx/compounds.\n
                        For example: -o "ethane.pdb".\n
                        If not specified, the default PDB_LIBRARY/ethane.pdb
                        is used.''')
    parser.add_argument("-n", "--number_of_organic_mols",
                        type=int,
                        default=200,
                        required=False,
                        help='''Set the number of organic hydrocarbons to be
                        included in the system.\n
                        For example: -n 200.\n
                        If not specified, the default value of 200 hydrocarbons
                        is used.''')
    parser.add_argument("-f", "--forcefield",
                        type=lambda f: f.split('.xml')[0],
                        default=None,
                        required=False,
                        help='''Use Foyer to set the forcefield to use when
                        running the simulation.\n
                        Note the forcefields are located in the FF_LIBRARY
                        directory, which defaults to lynx/forcefields.\n
                        For example: -f FF_opls_uff.\n
                        If not specified, the compound will not be saved with
                        forcefield information.''')
    args = parser.parse_args()
    create_morphology(args)
